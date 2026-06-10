"""
detectors/yolo_detector.py — Triple-model YOLOv8 detector for RoadSense AI

Runs 3 models per frame:
  Model 1 (base)  → car, bus, truck, person, bicycle
  Model 2 (auto)  → auto_rickshaw
  Model 3 (rider) → rider, motorcycle
"""

import numpy as np
from dataclasses import dataclass, field
from typing import List
from concurrent.futures import ThreadPoolExecutor, as_completed
from ultralytics import YOLO
from config import MODELS, CONF, COCO_KEEP, YOLO_IMGSZ


@dataclass
class RawDetection:
    label:   str
    conf:    float
    bbox:    List[float]   # [x1, y1, x2, y2]
    cx:      float = 0.0
    cy:      float = 0.0
    w:       float = 0.0
    h:       float = 0.0
    area:    float = 0.0
    frame_w: int   = 1280
    frame_h: int   = 720
    speed:   float = 0.0
    track_id: int  = -1
    trajectory: list = field(default_factory=list)

    def __post_init__(self):
        self.cx   = (self.bbox[0] + self.bbox[2]) / 2
        self.cy   = (self.bbox[1] + self.bbox[3]) / 2
        self.w    = self.bbox[2] - self.bbox[0]
        self.h    = self.bbox[3] - self.bbox[1]
        self.area = self.w * self.h


import torch

class TripleModelDetector:
    """Loads and runs all 3 YOLOv8 models."""

    def __init__(self):
        print("  [Detector] Loading 3 models...")
        self.device = "cuda" if torch.cuda.is_available() else "cpu"
        print(f"  [Detector] Using device: {self.device}")
        self.model_base  = YOLO(MODELS["base"]).to(self.device)
        self.model_auto  = YOLO(MODELS["auto"]).to(self.device)
        self.model_rider = YOLO(MODELS["rider"]).to(self.device)
        self.rider_names = self.model_rider.names
        # Thread-pool: run 3 models concurrently on CPU (GIL releases during C++ inference)
        self._pool = ThreadPoolExecutor(max_workers=3)
        print("  [Detector] All 3 models ready")

    def detect(self, frame: np.ndarray) -> dict:
        """
        Run all 3 models on frame IN PARALLEL using a thread pool.
        YOLO/PyTorch releases the GIL during C++ inference so threads
        genuinely overlap, giving ~2-3× speedup on CPU.
        """
        h, w = frame.shape[:2]

        def _run_base():
            return self.model_base(
                frame, imgsz=YOLO_IMGSZ, conf=CONF["base"],
                device=self.device, verbose=False
            )[0]

        def _run_auto():
            return self.model_auto(
                frame, imgsz=YOLO_IMGSZ, conf=CONF["auto"],
                device=self.device, verbose=False
            )[0]

        def _run_rider():
            return self.model_rider(
                frame, imgsz=YOLO_IMGSZ, conf=CONF["rider"],
                device=self.device, verbose=False
            )[0]

        fut_base  = self._pool.submit(_run_base)
        fut_auto  = self._pool.submit(_run_auto)
        fut_rider = self._pool.submit(_run_rider)

        r_base  = fut_base.result()
        r_auto  = fut_auto.result()
        r_rider = fut_rider.result()

        base_dets  = self._parse_base(r_base,  w, h)
        auto_dets  = self._parse_auto(r_auto,  w, h)
        rider_dets = self._parse_rider(r_rider, w, h)

        return {
            "base":  base_dets,
            "auto":  auto_dets,
            "rider": rider_dets,
        }

    def _parse_base(self, result, w, h):
        dets = []
        for box in result.boxes:
            cls_id = int(box.cls[0].cpu().item())
            if cls_id not in COCO_KEEP:
                continue
            dets.append(RawDetection(
                label   = COCO_KEEP[cls_id],
                conf    = float(box.conf[0].cpu().item()),
                bbox    = box.xyxy[0].cpu().tolist(),
                frame_w = w, frame_h = h,
            ))
        return dets

    def _parse_auto(self, result, w, h):
        return [
            RawDetection(
                label   = "auto_rickshaw",
                conf    = float(box.conf[0].cpu().item()),
                bbox    = box.xyxy[0].cpu().tolist(),
                frame_w = w, frame_h = h,
            )
            for box in result.boxes
        ]

    def _parse_rider(self, result, w, h):
        dets = []
        for box in result.boxes:
            cls_id = int(box.cls[0].cpu().item())
            label  = self.rider_names[cls_id].lower()  # "motorcycle" or "rider"
            dets.append(RawDetection(
                label   = label,
                conf    = float(box.conf[0].cpu().item()),
                bbox    = box.xyxy[0].cpu().tolist(),
                frame_w = w, frame_h = h,
            ))
        return dets