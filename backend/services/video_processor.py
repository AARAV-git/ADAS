"""
services/video_processor.py — Full RoadSense AI Pipeline Orchestrator

Connects all modules in order:
  Detection → Behavior Classification → Tracking → Risk → Chaos → Explainability
"""

import cv2
import numpy as np
from typing import Optional
from detectors.yolo_detector import TripleModelDetector
from trackers.deepsort_tracker import DeepSORTTracker
from analytics.behavior_engine import IndianBehaviorEngine
from analytics.risk_engine import RiskEngine
from analytics.chaos_score import ChaosScoreEngine
from explainability.llm_alerts import ExplainabilityEngine


class RoadSensePipeline:
    """
    Full pipeline per frame:
      frame
        → TripleModelDetector  (3 YOLO models)
        → IndianBehaviorEngine (merge/classify: rider, VRU, pedestrian, auto)
        → DeepSORTTracker      (persistent IDs + trajectory + velocity)
        → RiskEngine           (per-object risk score + type)
        → ChaosScoreEngine     (0-100 chaos score)
        → ExplainabilityEngine (human-readable ADAS alerts)
    """

    def __init__(self, frame_width: int = 1280, frame_height: int = 720):
        self.fw = frame_width
        self.fh = frame_height

        print("\n[RoadSense AI] Initializing pipeline...")
        self.detector    = TripleModelDetector()
        self.behavior    = IndianBehaviorEngine(frame_width, frame_height)
        self.tracker     = DeepSORTTracker()
        self.risk        = RiskEngine(frame_width, frame_height)
        self.chaos       = ChaosScoreEngine(frame_width, frame_height)
        self.explainer   = ExplainabilityEngine()
        print("[RoadSense AI] Pipeline ready\n")

    def process_frame(self, frame: np.ndarray) -> dict:
        """
        Run full pipeline on a single frame.
        Returns dict with all results.
        """
        h, w = frame.shape[:2]

        # Update frame dimensions if changed
        if w != self.fw or h != self.fh:
            self.fw = w; self.fh = h
            self.behavior = IndianBehaviorEngine(w, h)
            self.risk     = RiskEngine(w, h)
            self.chaos    = ChaosScoreEngine(w, h)

        # Step 1: Detection
        raw = self.detector.detect(frame)

        # Step 2: Behavior classification (merge/classify)
        classified = self.behavior.process(
            base_dets  = raw["base"],
            rider_dets = raw["rider"],
            auto_dets  = raw["auto"],
        )

        # Step 3: Tracking
        tracked = self.tracker.update(classified, frame)

        # Step 4: Risk assessment
        risks = self.risk.assess(tracked)

        # Step 5: Chaos score
        chaos = self.chaos.compute(tracked)

        # Step 6: Explainable alerts
        alerts  = self.explainer.generate(risks, chaos, w)
        summary = self.explainer.summarize(alerts, chaos)

        return {
            "tracked":  tracked,
            "risks":    risks,
            "chaos":    chaos,
            "alerts":   alerts,
            "summary":  summary,
        }