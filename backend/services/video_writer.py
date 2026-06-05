"""
video_writer.py — Annotated video output writer for RoadSense AI
Saves processed frames to an MP4 file using OpenCV VideoWriter.
"""

import cv2
import os
from typing import Optional
import numpy as np


class VideoWriter:
    """
    Wraps cv2.VideoWriter with auto-directory creation and context manager support.
    """

    def __init__(
        self,
        output_path: str,
        fps: float = 20.0,
        resolution: tuple = (1280, 720),
        codec: str = "mp4v",
    ):
        self.output_path = output_path
        self.fps         = fps
        self.resolution  = resolution  # (width, height)
        self._writer: Optional[cv2.VideoWriter] = None
        self._codec = codec
        self._frame_count = 0

    def open(self):
        os.makedirs(os.path.dirname(self.output_path), exist_ok=True)
        fourcc = cv2.VideoWriter_fourcc(*self._codec)
        self._writer = cv2.VideoWriter(
            self.output_path, fourcc, self.fps, self.resolution
        )
        if not self._writer.isOpened():
            raise RuntimeError(f"[VideoWriter] Cannot open output: {self.output_path}")
        print(f"[VideoWriter] Writing to: {self.output_path}")

    def write(self, frame: np.ndarray):
        if self._writer is None:
            self.open()
        # Resize if needed
        h, w = frame.shape[:2]
        if (w, h) != self.resolution:
            frame = cv2.resize(frame, self.resolution, interpolation=cv2.INTER_LINEAR)
        self._writer.write(frame)
        self._frame_count += 1

    def close(self):
        if self._writer:
            self._writer.release()
            print(f"[VideoWriter] Saved {self._frame_count} frames → {self.output_path}")
            self._writer = None

    @property
    def frame_count(self) -> int:
        return self._frame_count

    # Context manager support
    def __enter__(self):
        self.open()
        return self

    def __exit__(self, *args):
        self.close()
