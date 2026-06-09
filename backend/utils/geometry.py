"""
utils/geometry.py — Shared geometry helpers for RoadSense AI
"""

import numpy as np
from typing import List, Tuple


def iou(a: List[float], b: List[float]) -> float:
    """Intersection over Union of two [x1,y1,x2,y2] boxes."""
    xA = max(a[0], b[0]); yA = max(a[1], b[1])
    xB = min(a[2], b[2]); yB = min(a[3], b[3])
    inter = max(0, xB - xA) * max(0, yB - yA)
    areaA = (a[2] - a[0]) * (a[3] - a[1])
    areaB = (b[2] - b[0]) * (b[3] - b[1])
    union = areaA + areaB - inter
    return inter / union if union > 0 else 0.0


def overlap_ratio(inner: List[float], outer: List[float]) -> float:
    """Fraction of inner box covered by outer box."""
    xA = max(inner[0], outer[0]); yA = max(inner[1], outer[1])
    xB = min(inner[2], outer[2]); yB = min(inner[3], outer[3])
    inter = max(0, xB - xA) * max(0, yB - yA)
    area  = (inner[2] - inner[0]) * (inner[3] - inner[1])
    return inter / area if area > 0 else 0.0


def merge_bbox(a: List[float], b: List[float]) -> List[float]:
    """Union bounding box of two boxes."""
    return [min(a[0], b[0]), min(a[1], b[1]),
            max(a[2], b[2]), max(a[3], b[3])]


def box_center(bbox: List[float]) -> Tuple[float, float]:
    return (bbox[0] + bbox[2]) / 2, (bbox[1] + bbox[3]) / 2


def box_area(bbox: List[float]) -> float:
    return (bbox[2] - bbox[0]) * (bbox[3] - bbox[1])


def distance(p1: Tuple[float, float], p2: Tuple[float, float]) -> float:
    return float(np.sqrt((p1[0] - p2[0])**2 + (p1[1] - p2[1])**2))


def angle_degrees(dx: float, dy: float) -> float:
    return float(np.degrees(np.arctan2(dy, dx)) % 360)


def trajectory_angle_change(trajectory: List[Tuple[float, float, int]]) -> float:
    """Mean angle change across a trajectory (smoothed over last 10 points)."""
    if len(trajectory) < 3:
        return 0.0
    pts = list(trajectory)[-10:]
    angles = []
    for i in range(1, len(pts)):
        dx = pts[i][0] - pts[i-1][0]
        dy = pts[i][1] - pts[i-1][1]
        if abs(dx) + abs(dy) < 0.5:
            continue
        angles.append(np.degrees(np.arctan2(dy, dx)))
    if len(angles) < 2:
        return 0.0
    changes = [abs(angles[i] - angles[i-1]) for i in range(1, len(angles))]
    changes = [c if c <= 180 else 360 - c for c in changes]
    return float(np.mean(changes))