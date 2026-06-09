"""
trackers/deepsort_tracker.py — DeepSORT tracker for RoadSense AI

Assigns persistent IDs and enriches detections with:
  - Trajectory history
  - Velocity (vx, vy)
  - Speed (magnitude)
  - Direction angle
"""

import numpy as np
from collections import defaultdict, deque
from dataclasses import dataclass, field
from typing import List, Tuple, Dict
from deep_sort_realtime.deepsort_tracker import DeepSort
from config import DEEPSORT_MAX_AGE, DEEPSORT_N_INIT, TRAJECTORY_LEN, BYPASS_EMBEDDER
from detectors.yolo_detector import RawDetection


@dataclass
class TrackedObject:
    track_id:   int
    label:      str
    conf:       float
    bbox:       List[float]
    cx:         float
    cy:         float
    w:          float
    h:          float
    frame_w:    int
    frame_h:    int
    frame_id:   int
    speed:      float = 0.0
    velocity:   Tuple[float, float] = (0.0, 0.0)
    direction:  float = 0.0
    trajectory: List[Tuple[float, float, int]] = field(default_factory=list)
    age:        int = 1

    @property
    def area(self):
        return self.w * self.h


class DeepSORTTracker:
    """
    Wraps DeepSORT and enriches tracked objects with motion data.
    Works on the merged/classified detections from IndianClassifier.
    """

    def __init__(self):
        print("  [Tracker] Initializing DeepSORT")
        embedder = None if BYPASS_EMBEDDER else "mobilenet"
        self.tracker = DeepSort(
            max_age             = DEEPSORT_MAX_AGE,
            n_init              = DEEPSORT_N_INIT,
            nms_max_overlap     = 1.0,
            max_cosine_distance = 0.3,
            nn_budget           = None,
            embedder            = embedder,
        )
        self._history:  Dict[int, deque] = defaultdict(
            lambda: deque(maxlen=TRAJECTORY_LEN)
        )
        self._labels:   Dict[int, str]   = {}
        self._frame_id: int              = 0
        print("  [Tracker] DeepSORT ready")

    def update(self, dets: List[RawDetection], frame: np.ndarray) -> List[TrackedObject]:
        """Feed classified detections into DeepSORT, return enriched objects."""
        self._frame_id += 1
        h, w = frame.shape[:2]

        if not dets:
            if BYPASS_EMBEDDER:
                self.tracker.update_tracks([], embeds=[])
            else:
                self.tracker.update_tracks([], frame=frame)
            return []

        # Format: ([x,y,w,h], conf, label)
        raw = []
        for d in dets:
            bw = d.bbox[2] - d.bbox[0]
            bh = d.bbox[3] - d.bbox[1]
            raw.append(([d.bbox[0], d.bbox[1], bw, bh], d.conf, d.label))

        if BYPASS_EMBEDDER:
            embeds = np.zeros((len(raw), 512), dtype=np.float32)
            embeds[:, 0] = 1.0  # Safe unit L2 norm to prevent division-by-zero NaN crashes in deep_sort_realtime
            tracks = self.tracker.update_tracks(raw, embeds=embeds)
        else:
            tracks = self.tracker.update_tracks(raw, frame=frame)
        result = []

        for track in tracks:
            if not track.is_confirmed():
                continue

            tid  = track.track_id
            ltrb = track.to_ltrb()
            x1, y1, x2, y2 = ltrb
            cx = (x1 + x2) / 2
            cy = (y1 + y2) / 2
            bw = x2 - x1
            bh = y2 - y1

            if track.det_class:
                self._labels[tid] = track.det_class
            label = self._labels.get(tid, "vehicle")

            # Update trajectory
            self._history[tid].append((cx, cy, self._frame_id))
            trajectory = list(self._history[tid])

            # Compute motion
            velocity, speed, direction = self._motion(tid)

            # Find original conf from dets by proximity
            conf = self._match_conf(dets, cx, cy)

            result.append(TrackedObject(
                track_id   = tid,
                label      = label,
                conf       = conf,
                bbox       = [x1, y1, x2, y2],
                cx         = cx,
                cy         = cy,
                w          = bw,
                h          = bh,
                frame_w    = w,
                frame_h    = h,
                frame_id   = self._frame_id,
                speed      = speed,
                velocity   = velocity,
                direction  = direction,
                trajectory = trajectory,
                age        = len(trajectory),
            ))

        return result

    def _motion(self, tid: int):
        hist = self._history[tid]
        if len(hist) < 2:
            return (0.0, 0.0), 0.0, 0.0
        window = list(hist)[-5:]
        dx = window[-1][0] - window[0][0]
        dy = window[-1][1] - window[0][1]
        n  = max(len(window) - 1, 1)
        vx = dx / n
        vy = dy / n
        speed     = float(np.sqrt(vx**2 + vy**2))
        direction = float(np.degrees(np.arctan2(vy, vx)) % 360)
        return (vx, vy), speed, direction

    def _match_conf(self, dets, cx, cy) -> float:
        """Find closest detection to give its confidence to the track."""
        best_conf = 0.5
        best_dist = float("inf")
        for d in dets:
            dist = np.sqrt((d.cx - cx)**2 + (d.cy - cy)**2)
            if dist < best_dist:
                best_dist = dist
                best_conf = d.conf
        return best_conf

    def get_trajectory(self, tid: int):
        return list(self._history.get(tid, []))