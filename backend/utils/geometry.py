"""
geometry.py — Geometry utilities for RoadSense AI
"""

import math
import numpy as np
from typing import List, Tuple


def bbox_center(bbox: List[float]) -> Tuple[float, float]:
    """Return (cx, cy) from [x1, y1, x2, y2]."""
    x1, y1, x2, y2 = bbox
    return ((x1 + x2) / 2, (y1 + y2) / 2)


def bbox_area(bbox: List[float]) -> float:
    x1, y1, x2, y2 = bbox
    return max(0, x2 - x1) * max(0, y2 - y1)


def euclidean(p1: Tuple[float, float], p2: Tuple[float, float]) -> float:
    return math.hypot(p1[0] - p2[0], p1[1] - p2[1])


def iou(bbox_a: List[float], bbox_b: List[float]) -> float:
    """Intersection-over-union of two [x1,y1,x2,y2] boxes."""
    ax1, ay1, ax2, ay2 = bbox_a
    bx1, by1, bx2, by2 = bbox_b

    ix1 = max(ax1, bx1)
    iy1 = max(ay1, by1)
    ix2 = min(ax2, bx2)
    iy2 = min(ay2, by2)

    inter = max(0, ix2 - ix1) * max(0, iy2 - iy1)
    union = bbox_area(bbox_a) + bbox_area(bbox_b) - inter
    return inter / union if union > 0 else 0.0


def angle_between(v1: np.ndarray, v2: np.ndarray) -> float:
    """Angle in degrees between two 2-D vectors."""
    n1, n2 = np.linalg.norm(v1), np.linalg.norm(v2)
    if n1 == 0 or n2 == 0:
        return 0.0
    cos_a = np.clip(np.dot(v1, v2) / (n1 * n2), -1, 1)
    return math.degrees(math.acos(cos_a))


def speed_pixels_per_frame(history) -> float:
    """
    Compute average speed (px/frame) from a deque of (cx, cy) positions.
    Uses last 5 points for smoothing.
    """
    pts = list(history)[-5:]
    if len(pts) < 2:
        return 0.0
    dists = [euclidean(pts[i], pts[i - 1]) for i in range(1, len(pts))]
    return sum(dists) / len(dists)


def direction_vector(history) -> np.ndarray:
    """Return the normalised direction vector from trajectory history."""
    pts = list(history)[-6:]
    if len(pts) < 2:
        return np.array([0.0, 0.0])
    vec = np.array(pts[-1]) - np.array(pts[0])
    norm = np.linalg.norm(vec)
    return vec / norm if norm > 0 else vec


def lane_offset_fraction(cx: float, frame_width: float) -> float:
    """
    How far the object centre is from the middle of the frame,
    as a fraction of frame_width. 0 = centre, ±0.5 = edge.
    """
    return abs((cx - frame_width / 2) / frame_width)


def points_to_trajectory_change(history) -> float:
    """
    Detect abrupt direction change (degrees) over the last window.
    Compares first-half direction vs second-half direction.
    """
    pts = list(history)
    if len(pts) < 6:
        return 0.0
    mid = len(pts) // 2
    v1 = np.array(pts[mid][:2]) - np.array(pts[0][:2])
    v2 = np.array(pts[-1][:2]) - np.array(pts[mid][:2])
    return angle_between(v1, v2)