"""
services/video_writer.py — Video Writer for RoadSense AI

Handles saving annotated output video with proper codec and path management.
Also supports saving a summary JSON alongside the video.
"""

import cv2
import os
import json
from datetime import datetime
from typing import Optional
from config import OUTPUTS_DIR


class VideoWriter:
    """
    Wraps OpenCV VideoWriter with:
      - Auto output path generation
      - Summary JSON export
      - Frame count + duration tracking
      - Achieved FPS calculation for live camera streams (avoids sped-up playback)
    """

    def __init__(
        self,
        input_path:   str,
        frame_width:  int,
        frame_height: int,
        fps:          float,
        skip:         int = 1,
        output_dir:   Optional[str] = None,
    ):
        self.input_path   = input_path
        self.frame_width  = frame_width
        self.frame_height = frame_height
        self.fps          = fps / (skip + 1)   # adjusted for skipped frames
        self.skip         = skip
        self.output_dir   = output_dir or OUTPUTS_DIR
        self.writer       = None
        self.out_path     = None
        self.frame_count  = 0
        self.temp_dir     = None
        self.start_time   = None
        self.end_time     = None
        self.stats        = {
            "vru_frames":     0,
            "high_risk_frames": 0,
            "total_detections": {},
            "chaos_scores":   [],
        }

        os.makedirs(self.output_dir, exist_ok=True)

    def open(self) -> str:
        """Open the frame buffer. Returns output path."""
        filename  = os.path.splitext(os.path.basename(self.input_path))[0]
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        self.out_path = os.path.join(
            self.output_dir, f"{filename}_roadsense_{timestamp}.mp4"
        )

        # Create a unique temporary directory for frame storage to handle dynamic FPS compilation
        import tempfile
        self.temp_dir = tempfile.mkdtemp(prefix="roadsense_frames_")
        print(f"  [VideoWriter] Buffering frames to temp directory: {self.temp_dir}")
        return self.out_path

    def write(self, frame, result: Optional[dict] = None):
        """Write a single annotated frame. Optionally update stats from result."""
        import time
        if self.start_time is None:
            self.start_time = time.time()

        if self.temp_dir and os.path.exists(self.temp_dir):
            frame_path = os.path.join(self.temp_dir, f"frame_{self.frame_count:06d}.jpg")
            cv2.imwrite(frame_path, frame, [cv2.IMWRITE_JPEG_QUALITY, 90])
            self.frame_count += 1

        if result:
            self._update_stats(result)

    def _update_stats(self, result: dict):
        # Chaos score history
        chaos = result.get("chaos")
        if chaos:
            self.stats["chaos_scores"].append(chaos.score)

        # VRU frames
        tracked = result.get("tracked", [])
        if any(o.label == "vulnerable_road_user" for o in tracked):
            self.stats["vru_frames"] += 1

        # High risk frames
        risks = result.get("risks", [])
        if any(r.risk_level in ("HIGH", "CRITICAL") for r in risks):
            self.stats["high_risk_frames"] += 1

        # Detection counts
        for obj in tracked:
            self.stats["total_detections"][obj.label] = \
                self.stats["total_detections"].get(obj.label, 0) + 1

    def close(self) -> dict:
        """Compile buffered frames into final video at the calculated FPS and clean up."""
        import time
        import shutil

        if self.frame_count > 0 and self.temp_dir and os.path.exists(self.temp_dir):
            if self.start_time is not None:
                self.end_time = time.time()
                elapsed = self.end_time - self.start_time
                # For live camera streams, calculate actual achieved frame rate
                if "live_camera" in self.input_path and elapsed > 0:
                    actual_fps = self.frame_count / elapsed
                    self.fps = min(max(actual_fps, 5.0), 30.0)
                    print(f"  [VideoWriter] Live camera detected. Adjusting output FPS to achieved processing rate: {self.fps:.1f} FPS")

            # Open real VideoWriter with determined FPS
            fourcc = cv2.VideoWriter_fourcc(*"mp4v")
            self.writer = cv2.VideoWriter(
                self.out_path, fourcc, self.fps,
                (self.frame_width, self.frame_height)
            )

            if not self.writer.isOpened():
                shutil.rmtree(self.temp_dir, ignore_errors=True)
                raise RuntimeError(f"Could not open VideoWriter at {self.out_path}")

            print(f"  [VideoWriter] Compiling video from buffer at {self.fps:.1f} FPS...")
            for i in range(self.frame_count):
                frame_path = os.path.join(self.temp_dir, f"frame_{i:06d}.jpg")
                if os.path.exists(frame_path):
                    img = cv2.imread(frame_path)
                    if img is not None:
                        # Safety check: ensure frame size matches exactly
                        if img.shape[1] != self.frame_width or img.shape[0] != self.frame_height:
                            img = cv2.resize(img, (self.frame_width, self.frame_height))
                        self.writer.write(img)

            self.writer.release()
            self.writer = None

            # Clean up temp files
            shutil.rmtree(self.temp_dir, ignore_errors=True)
            self.temp_dir = None
            print(f"  [VideoWriter] Saved output video → {self.out_path}")

        summary = self._build_summary()

        # Save summary JSON
        if self.out_path and self.frame_count > 0:
            json_path = self.out_path.replace(".mp4", "_summary.json")
            with open(json_path, "w") as f:
                json.dump(summary, f, indent=2)
            print(f"  [VideoWriter] Summary → {json_path}")

        return summary

    def _build_summary(self) -> dict:
        import numpy as np
        chaos_scores = self.stats["chaos_scores"]
        return {
            "output_video":       self.out_path,
            "input_video":        self.input_path,
            "frames_written":     self.frame_count,
            "duration_seconds":   round(self.frame_count / max(self.fps, 1), 1),
            "vru_frames":         self.stats["vru_frames"],
            "vru_percentage":     round(
                self.stats["vru_frames"] / max(self.frame_count, 1) * 100, 1
            ),
            "high_risk_frames":   self.stats["high_risk_frames"],
            "high_risk_percentage": round(
                self.stats["high_risk_frames"] / max(self.frame_count, 1) * 100, 1
            ),
            "chaos": {
                "avg":   round(float(np.mean(chaos_scores)),  1) if chaos_scores else 0,
                "max":   round(float(np.max(chaos_scores)),   1) if chaos_scores else 0,
                "min":   round(float(np.min(chaos_scores)),   1) if chaos_scores else 0,
            },
            "detections": self.stats["total_detections"],
        }

    def __enter__(self):
        self.open()
        return self

    def __exit__(self, *args):
        self.close()

    @property
    def is_open(self) -> bool:
        return self.temp_dir is not None