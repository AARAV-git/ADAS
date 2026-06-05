"""
video_processor.py — Core video processing pipeline for RoadSense AI

Orchestrates:
  Dashcam frame → YOLO detect → DeepSORT track → Behavior analysis
  → Risk prediction → Chaos score → Explainable alerts → Annotated frame

Exposes both a synchronous file-processor and an async frame generator
for the FastAPI WebSocket streaming endpoint.
"""

import cv2
import time
import os
import asyncio
from typing import AsyncGenerator, Optional, Generator

import numpy as np

from detectors.yolo_detector import Detector
from trackers.deepsort_tracker import Tracker
from analytics.behavior_engine import BehaviorEngine
from analytics.risk_engine import RiskEngine
from analytics.chaos_score import ChaosScoreEngine
from explainability.llm_alerts import ExplainabilityEngine
from utils.drawing import (
    draw_tracked_objects,
    draw_hud,
    draw_risk_badge,
    resize_frame,
    frame_to_jpeg,
)


# ─── Pipeline result per frame ───────────────────────────────────────────────

class FrameResult:
    """All analytics data produced for a single frame."""

    def __init__(
        self,
        frame_id: int,
        annotated_frame: np.ndarray,
        tracked_objects: list,
        behavior_events: list,
        risk_events: list,
        chaos,
        alerts: list,
        summary: dict,
        fps: float,
    ):
        self.frame_id        = frame_id
        self.annotated_frame = annotated_frame
        self.tracked_objects = tracked_objects
        self.behavior_events = behavior_events
        self.risk_events     = risk_events
        self.chaos           = chaos
        self.alerts          = alerts
        self.summary         = summary
        self.fps             = fps

    def to_dict(self) -> dict:
        return {
            "frame_id":       self.frame_id,
            "fps":            round(self.fps, 1),
            "object_count":   len(self.tracked_objects),
            "risk_events":    [r.to_dict() for r in self.risk_events],
            "behavior_events": [b.to_dict() for b in self.behavior_events],
            "chaos":          self.chaos.to_dict(),
            "alerts":         [a.to_dict() for a in self.alerts],
            "summary":        self.summary,
        }


# ─── Pipeline ────────────────────────────────────────────────────────────────

class VideoProcessor:
    """
    Full RoadSense AI inference pipeline.

    Usage:
        processor = VideoProcessor(use_llm=True, groq_api_key="...")
        for result in processor.process_file("video.mp4"):
            # result.annotated_frame  → numpy BGR frame
            # result.to_dict()        → JSON-serialisable analytics
    """

    def __init__(
        self,
        model_path: str = "yolov8n.pt",
        conf_threshold: float = 0.40,
        frame_skip: int = 2,
        output_resolution: tuple = (1280, 720),
        use_llm: bool = False,
        groq_api_key: Optional[str] = None,
    ):
        self.frame_skip        = frame_skip
        self.output_resolution = output_resolution

        fw, fh = output_resolution

        # ── Component init ──────────────────────────────────────────────────
        self.detector    = Detector(model_path=model_path, conf_threshold=conf_threshold)
        self.tracker     = Tracker(max_age=30, n_init=3)
        self.behavior    = BehaviorEngine(frame_width=fw, frame_height=fh)
        self.risk_engine = RiskEngine(frame_width=fw, frame_height=fh)
        self.chaos_engine = ChaosScoreEngine(frame_width=fw, frame_height=fh)
        self.explainer   = ExplainabilityEngine(
            use_llm=use_llm,
            groq_api_key=groq_api_key,
            frame_width=fw,
        )

        self._fps_history = []
        self._frame_counter = 0

    # ── Public: file processing ──────────────────────────────────────────────

    def process_file(self, video_path: str) -> Generator[FrameResult, None, None]:
        """
        Generator: yield FrameResult for every processed frame in a video file.
        Skips frames according to self.frame_skip.
        """
        cap = cv2.VideoCapture(video_path)
        if not cap.isOpened():
            raise FileNotFoundError(f"Cannot open video: {video_path}")

        raw_frame_idx = 0
        try:
            while True:
                ret, frame = cap.read()
                if not ret:
                    break
                raw_frame_idx += 1
                if raw_frame_idx % self.frame_skip != 0:
                    continue

                result = self._process_frame(frame)
                if result:
                    yield result
        finally:
            cap.release()

    # ── Public: async frame generator (WebSocket streaming) ─────────────────

    async def stream_file(self, video_path: str) -> AsyncGenerator[bytes, None]:
        """
        Async generator yielding JPEG bytes for each annotated frame.
        Suitable for use in a FastAPI WebSocket or SSE endpoint.
        """
        loop = asyncio.get_event_loop()
        cap  = cv2.VideoCapture(video_path)
        if not cap.isOpened():
            raise FileNotFoundError(f"Cannot open video: {video_path}")

        raw_frame_idx = 0
        try:
            while True:
                ret, frame = await loop.run_in_executor(None, cap.read)
                if not ret:
                    break
                raw_frame_idx += 1
                if raw_frame_idx % self.frame_skip != 0:
                    continue

                result = await loop.run_in_executor(None, self._process_frame, frame)
                if result:
                    yield frame_to_jpeg(result.annotated_frame)
                    await asyncio.sleep(0)   # yield control to event loop
        finally:
            cap.release()

    # ── Core frame processing ────────────────────────────────────────────────

    def _process_frame(self, raw_frame: np.ndarray) -> Optional[FrameResult]:
        t0 = time.perf_counter()
        self._frame_counter += 1

        # 1. Resize
        frame = resize_frame(raw_frame, self.output_resolution)

        # 2. Detect
        detections = self.detector.detect(frame)

        # 3. Track
        tracked = self.tracker.update(detections, frame)
        if not tracked:
            # Still build empty result so UI keeps updating
            empty_chaos = self.chaos_engine.compute([])
            fps = self._calc_fps(t0)
            annotated = draw_hud(frame, empty_chaos.score, empty_chaos.level, fps, 0)
            return FrameResult(
                frame_id=self._frame_counter,
                annotated_frame=annotated,
                tracked_objects=[],
                behavior_events=[],
                risk_events=[],
                chaos=empty_chaos,
                alerts=[],
                summary=self.explainer.summarize([], empty_chaos),
                fps=fps,
            )

        # 4. Behavior analysis
        behavior_events = self.behavior.analyze(tracked)

        # 5. Risk assessment
        risk_events = self.risk_engine.assess(tracked)

        # 6. Chaos score
        chaos = self.chaos_engine.compute(tracked)

        # 7. Explainable alerts
        centers = {obj.track_id: tuple(obj.center) for obj in tracked}
        alerts  = self.explainer.generate_alerts(risk_events, chaos, centers)
        summary = self.explainer.summarize(alerts, chaos)

        # 8. Annotate frame
        risk_map = {e.track_id: e.risk_level for e in risk_events}
        annotated = draw_tracked_objects(frame, tracked, risk_map)

        alert_texts = [a.message for a in alerts[:3]]
        annotated = draw_hud(
            annotated,
            chaos_score=chaos.score,
            chaos_level=chaos.level,
            fps=self._calc_fps(t0),
            object_count=len(tracked),
            active_alerts=alert_texts,
        )

        # Top risk badge
        highest = summary.get("highest_risk", "LOW")
        if highest in ("HIGH", "CRITICAL"):
            annotated = draw_risk_badge(annotated, highest, x=540, y=68)

        fps = self._calc_fps(t0)

        return FrameResult(
            frame_id=self._frame_counter,
            annotated_frame=annotated,
            tracked_objects=tracked,
            behavior_events=behavior_events,
            risk_events=risk_events,
            chaos=chaos,
            alerts=alerts,
            summary=summary,
            fps=fps,
        )

    def _calc_fps(self, t0: float) -> float:
        elapsed = time.perf_counter() - t0
        self._fps_history.append(elapsed)
        if len(self._fps_history) > 30:
            self._fps_history.pop(0)
        avg = sum(self._fps_history) / len(self._fps_history)
        return 1.0 / avg if avg > 0 else 0.0
