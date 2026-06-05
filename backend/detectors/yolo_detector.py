# """
# yolo_detector.py — YOLOv8-based object detection for RoadSense AI
# Detects: cars, motorcycles, buses, trucks, bicycles, pedestrians
# """

# import cv2
# import numpy as np
# from ultralytics import YOLO
# from dataclasses import dataclass, field
# from typing import List, Optional

# # COCO class IDs we care about (standard YOLOv8 pretrained)
# COCO_RELEVANT = {0, 1, 2, 3, 5, 7}  # person, bicycle, car, motorcycle, bus, truck


# @dataclass
# class Detection:
#     track_id: int
#     label: str
#     confidence: float
#     bbox: List[float]       # [x1, y1, x2, y2]
#     center: List[float]     # [cx, cy]
#     width: float
#     height: float
#     frame_id: int


# class Detector:
#     COLOR_MAP = {
#         "pedestrian": (0, 255, 255),
#         "bicycle":    (255, 165, 0),
#         "car":        (0, 255, 0),
#         "motorcycle": (255, 0, 255),
#         "bus":        (0, 0, 255),
#         "truck":      (128, 0, 128),
#         "vehicle":    (200, 200, 200),
#     }

#     LABEL_MAP = {
#         0: "pedestrian",
#         1: "bicycle",
#         2: "car",
#         3: "motorcycle",
#         5: "bus",
#         7: "truck",
#     }

#     def __init__(self, model_path: str = "yolov8n.pt", conf_threshold: float = 0.40):
#         print(f"[Detector] Loading YOLOv8 model: {model_path}")
#         self.model = YOLO(model_path)
#         self.conf_threshold = conf_threshold
#         self.frame_id = 0

#     def detect(self, frame: np.ndarray) -> List[Detection]:
#         """Run YOLOv8 on a single frame, return list of Detection objects."""
#         self.frame_id += 1
#         results = self.model(frame, conf=self.conf_threshold, verbose=False)[0]
#         detections = []

#         for box in results.boxes:
#             cls_id = int(box.cls[0])
#             if cls_id not in COCO_RELEVANT:
#                 continue

#             conf = float(box.conf[0])
#             x1, y1, x2, y2 = box.xyxy[0].tolist()
#             cx = (x1 + x2) / 2
#             cy = (y1 + y2) / 2
#             w = x2 - x1
#             h = y2 - y1

#             label = self.LABEL_MAP.get(cls_id, "vehicle")

#             detections.append(Detection(
#                 track_id=-1,
#                 label=label,
#                 confidence=conf,
#                 bbox=[x1, y1, x2, y2],
#                 center=[cx, cy],
#                 width=w,
#                 height=h,
#                 frame_id=self.frame_id,
#             ))

#         return detections

#     def annotate_frame(self, frame: np.ndarray, detections: List[Detection]) -> np.ndarray:
#         """Draw bounding boxes on frame for visualization."""
#         annotated = frame.copy()
#         for det in detections:
#             x1, y1, x2, y2 = [int(v) for v in det.bbox]
#             color = self.COLOR_MAP.get(det.label, (200, 200, 200))
#             cv2.rectangle(annotated, (x1, y1), (x2, y2), color, 2)
#             label_text = f"{det.label} #{det.track_id} {det.confidence:.2f}"
#             cv2.putText(annotated, label_text, (x1, max(y1 - 6, 12)),
#                         cv2.FONT_HERSHEY_SIMPLEX, 0.5, color, 1, cv2.LINE_AA)
#         return annotated

"""
detector.py — YOLOv8-based object detection for RoadSense AI
Detects: cars, motorcycles, auto-rickshaws, buses, trucks, pedestrians
"""

import cv2
import numpy as np
from ultralytics import YOLO
from dataclasses import dataclass, field
from typing import List, Optional

# YOLO class IDs relevant to Indian traffic
RELEVANT_CLASSES = {
    0: "pedestrian",
    1: "bicycle",
    2: "car",
    3: "motorcycle",
    5: "bus",
    6: "auto_rickshaw",   # mapped from "train" slot or custom
    7: "truck",
}

# COCO class IDs we care about (standard YOLOv8 pretrained)
COCO_RELEVANT = {0, 1, 2, 3, 5, 7}  # person, bicycle, car, motorcycle, bus, truck

@dataclass
class Detection:
    track_id: int
    label: str
    confidence: float
    bbox: List[float]       # [x1, y1, x2, y2]
    center: List[float]     # [cx, cy]
    width: float
    height: float
    frame_id: int


class Detector:
    def __init__(self, model_path: str = "yolov8n.pt", conf_threshold: float = 0.4):
        print(f"[Detector] Loading YOLOv8 model: {model_path}")
        self.model = YOLO(model_path)
        self.conf_threshold = conf_threshold
        self.frame_id = 0

    def detect(self, frame: np.ndarray) -> List[Detection]:
        """Run YOLOv8 on a single frame, return list of Detection objects."""
        self.frame_id += 1
        results = self.model(frame, conf=self.conf_threshold, verbose=False)[0]
        detections = []

        for box in results.boxes:
            cls_id = int(box.cls[0])
            if cls_id not in COCO_RELEVANT:
                continue

            conf = float(box.conf[0])
            x1, y1, x2, y2 = box.xyxy[0].tolist()
            cx = (x1 + x2) / 2
            cy = (y1 + y2) / 2
            w = x2 - x1
            h = y2 - y1

            label = self._map_label(cls_id)

            detections.append(Detection(
                track_id=-1,           # assigned by tracker
                label=label,
                confidence=conf,
                bbox=[x1, y1, x2, y2],
                center=[cx, cy],
                width=w,
                height=h,
                frame_id=self.frame_id,
            ))

        return detections

    def _map_label(self, cls_id: int) -> str:
        mapping = {
            0: "pedestrian",
            1: "bicycle",
            2: "car",
            3: "motorcycle",
            5: "bus",
            7: "truck",
        }
        return mapping.get(cls_id, "vehicle")

    def annotate_frame(self, frame: np.ndarray, detections: List[Detection]) -> np.ndarray:
        """Draw bounding boxes on frame for visualization."""
        colors = {
            "pedestrian": (0, 255, 255),
            "bicycle": (255, 165, 0),
            "car": (0, 255, 0),
            "motorcycle": (255, 0, 255),
            "bus": (0, 0, 255),
            "truck": (128, 0, 128),
            "vehicle": (200, 200, 200),
        }
        annotated = frame.copy()
        for det in detections:
            x1, y1, x2, y2 = [int(v) for v in det.bbox]
            color = colors.get(det.label, (200, 200, 200))
            cv2.rectangle(annotated, (x1, y1), (x2, y2), color, 2)
            label_text = f"{det.label} #{det.track_id} {det.confidence:.2f}"
            cv2.putText(annotated, label_text, (x1, y1 - 6),
                        cv2.FONT_HERSHEY_SIMPLEX, 0.5, color, 1)
        return annotated