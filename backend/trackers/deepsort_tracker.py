# """
# deepsort_tracker.py — DeepSORT multi-object tracking for RoadSense AI
# Assigns persistent IDs and builds trajectory history per object.
# """

# import numpy as np
# from collections import defaultdict, deque
# from dataclasses import dataclass, field
# from typing import List, Dict, Tuple, Optional
# from deep_sort_realtime.deepsort_tracker import DeepSort

# from detectors.yolo_detector import Detection


# @dataclass
# class TrackedObject:
#     track_id: int
#     label: str
#     bbox: List[float]
#     center: List[float]
#     width: float
#     height: float
#     frame_id: int

#     # Trajectory: list of (cx, cy, frame_id)
#     trajectory: List[Tuple[float, float, int]] = field(default_factory=list)

#     # Velocity: (vx, vy) in pixels/frame
#     velocity: Tuple[float, float] = (0.0, 0.0)

#     # Speed magnitude
#     speed: float = 0.0

#     # Direction angle in degrees (0=right, 90=down, 180=left, 270=up)
#     direction: float = 0.0

#     # How many frames this object has been tracked
#     age: int = 1


# class Tracker:
#     """
#     Wraps DeepSORT and enriches tracked objects with:
#     - Trajectory history (last N positions)
#     - Velocity / speed / direction
#     """

#     TRAJECTORY_LEN = 30   # frames to keep in history

#     def __init__(self, max_age: int = 30, n_init: int = 3):
#         print("[Tracker] Initializing DeepSORT tracker")
#         self.deepsort = DeepSort(
#             max_age=max_age,
#             n_init=n_init,
#             nms_max_overlap=1.0,
#             max_cosine_distance=0.3,
#             nn_budget=None,
#         )
#         # Per-ID history: deque of (cx, cy, frame_id)
#         self._history: Dict[int, deque] = defaultdict(
#             lambda: deque(maxlen=self.TRAJECTORY_LEN)
#         )
#         self._labels: Dict[int, str] = {}

#     def update(self, detections: List[Detection], frame: np.ndarray) -> List[TrackedObject]:
#         """Feed detections into DeepSORT, return enriched TrackedObject list."""
#         if not detections:
#             self.deepsort.update_tracks([], frame=frame)
#             return []

#         # Format for DeepSORT: list of ([x1,y1,w,h], confidence, label)
#         raw = []
#         for det in detections:
#             x1, y1, x2, y2 = det.bbox
#             w = x2 - x1
#             h = y2 - y1
#             raw.append(([x1, y1, w, h], det.confidence, det.label))

#         tracks = self.deepsort.update_tracks(raw, frame=frame)

#         tracked_objects = []
#         frame_id = detections[0].frame_id if detections else 0

#         for track in tracks:
#             if not track.is_confirmed():
#                 continue

#             tid = track.track_id
#             ltrb = track.to_ltrb()
#             x1, y1, x2, y2 = ltrb
#             cx = (x1 + x2) / 2
#             cy = (y1 + y2) / 2
#             w = x2 - x1
#             h = y2 - y1

#             # Remember label
#             if track.det_class:
#                 self._labels[tid] = track.det_class
#             label = self._labels.get(tid, "vehicle")

#             # Update history
#             self._history[tid].append((cx, cy, frame_id))

#             # Compute velocity / speed / direction
#             velocity, speed, direction = self._compute_motion(tid)

#             trajectory = list(self._history[tid])
#             age = len(trajectory)

#             tracked_objects.append(TrackedObject(
#                 track_id=tid,
#                 label=label,
#                 bbox=[x1, y1, x2, y2],
#                 center=[cx, cy],
#                 width=w,
#                 height=h,
#                 frame_id=frame_id,
#                 trajectory=trajectory,
#                 velocity=velocity,
#                 speed=speed,
#                 direction=direction,
#                 age=age,
#             ))

#         return tracked_objects

#     def _compute_motion(self, tid: int) -> Tuple[Tuple[float, float], float, float]:
#         """Compute (vx, vy), speed, and direction from last 5 frames."""
#         history = self._history[tid]
#         if len(history) < 2:
#             return (0.0, 0.0), 0.0, 0.0

#         # Average over last 5 frames for smoothness
#         window = list(history)[-5:]
#         dx = window[-1][0] - window[0][0]
#         dy = window[-1][1] - window[0][1]
#         n = len(window) - 1 if len(window) > 1 else 1

#         vx = dx / n
#         vy = dy / n
#         speed = float(np.sqrt(vx**2 + vy**2))
#         direction = float(np.degrees(np.arctan2(vy, vx)) % 360)

#         return (vx, vy), speed, direction

#     def get_trajectory(self, tid: int) -> List[Tuple[float, float, int]]:
#         return list(self._history.get(tid, []))

#     def annotate_frame(self, frame: np.ndarray, tracked: List[TrackedObject]) -> np.ndarray:
#         """Draw tracks and trajectory tails."""
#         import cv2
#         annotated = frame.copy()
#         for obj in tracked:
#             x1, y1, x2, y2 = [int(v) for v in obj.bbox]
#             cv2.rectangle(annotated, (x1, y1), (x2, y2), (0, 200, 255), 2)

#             # Draw trajectory tail
#             pts = [(int(p[0]), int(p[1])) for p in obj.trajectory]
#             for i in range(1, len(pts)):
#                 alpha = i / len(pts)
#                 color = (int(255 * alpha), int(100 * alpha), 255)
#                 cv2.line(annotated, pts[i-1], pts[i], color, 1)

#             label = f"#{obj.track_id} {obj.label} spd:{obj.speed:.1f}"
#             cv2.putText(annotated, label, (x1, max(y1 - 6, 12)),
#                         cv2.FONT_HERSHEY_SIMPLEX, 0.45, (0, 200, 255), 1, cv2.LINE_AA)

#         return annotated

"""
tracker.py — DeepSORT multi-object tracking for RoadSense AI
Assigns persistent IDs and builds trajectory history per object.
"""

import numpy as np
from collections import defaultdict, deque
from dataclasses import dataclass, field
from typing import List, Dict, Tuple, Optional
from deep_sort_realtime.deepsort_tracker import DeepSort

from detectors.yolo_detector import Detection


@dataclass
class TrackedObject:
    track_id: int
    label: str
    bbox: List[float]
    center: List[float]
    width: float
    height: float
    frame_id: int

    # Trajectory: list of (cx, cy, frame_id)
    trajectory: List[Tuple[float, float, int]] = field(default_factory=list)

    # Velocity: (vx, vy) in pixels/frame
    velocity: Tuple[float, float] = (0.0, 0.0)

    # Speed magnitude
    speed: float = 0.0

    # Direction angle in degrees (0=right, 90=down, 180=left, 270=up)
    direction: float = 0.0

    # How many frames this object has been tracked
    age: int = 1


class Tracker:
    """
    Wraps DeepSORT and enriches tracked objects with:
    - Trajectory history (last N positions)
    - Velocity / speed / direction
    """

    TRAJECTORY_LEN = 30   # frames to keep in history

    def __init__(self, max_age: int = 30, n_init: int = 3):
        print("[Tracker] Initializing DeepSORT tracker")
        self.deepsort = DeepSort(
            max_age=max_age,
            n_init=n_init,
            nms_max_overlap=1.0,
            max_cosine_distance=0.3,
            nn_budget=None,
        )
        # Per-ID history: deque of (cx, cy, frame_id)
        self._history: Dict[int, deque] = defaultdict(
            lambda: deque(maxlen=self.TRAJECTORY_LEN)
        )
        self._labels: Dict[int, str] = {}

    def update(self, detections: List[Detection], frame: np.ndarray) -> List[TrackedObject]:
        """
        Feed detections into DeepSORT, return enriched TrackedObject list.
        """
        if not detections:
            self.deepsort.update_tracks([], frame=frame)
            return []

        # Format for DeepSORT: list of ([x1,y1,w,h], confidence, label)
        raw = []
        for det in detections:
            x1, y1, x2, y2 = det.bbox
            w = x2 - x1
            h = y2 - y1
            raw.append(([x1, y1, w, h], det.confidence, det.label))

        tracks = self.deepsort.update_tracks(raw, frame=frame)

        tracked_objects = []
        for track in tracks:
            if not track.is_confirmed():
                continue

            tid = track.track_id
            ltrb = track.to_ltrb()
            x1, y1, x2, y2 = ltrb
            cx = (x1 + x2) / 2
            cy = (y1 + y2) / 2
            w = x2 - x1
            h = y2 - y1

            # Remember label
            if track.det_class:
                self._labels[tid] = track.det_class
            label = self._labels.get(tid, "vehicle")

            # Update history
            frame_id = detections[0].frame_id if detections else 0
            self._history[tid].append((cx, cy, frame_id))

            # Compute velocity / speed / direction
            velocity, speed, direction = self._compute_motion(tid)

            trajectory = list(self._history[tid])
            age = len(trajectory)

            tracked_objects.append(TrackedObject(
                track_id=tid,
                label=label,
                bbox=[x1, y1, x2, y2],
                center=[cx, cy],
                width=w,
                height=h,
                frame_id=frame_id,
                trajectory=trajectory,
                velocity=velocity,
                speed=speed,
                direction=direction,
                age=age,
            ))

        return tracked_objects

    def _compute_motion(self, tid: int) -> Tuple[Tuple[float, float], float, float]:
        """Compute (vx, vy), speed, and direction from last 5 frames."""
        history = self._history[tid]
        if len(history) < 2:
            return (0.0, 0.0), 0.0, 0.0

        # Average over last 5 frames for smoothness
        window = list(history)[-5:]
        dx = window[-1][0] - window[0][0]
        dy = window[-1][1] - window[0][1]
        n = len(window) - 1 if len(window) > 1 else 1

        vx = dx / n
        vy = dy / n
        speed = float(np.sqrt(vx**2 + vy**2))
        direction = float(np.degrees(np.arctan2(vy, vx)) % 360)

        return (vx, vy), speed, direction

    def get_trajectory(self, tid: int) -> List[Tuple[float, float, int]]:
        return list(self._history.get(tid, []))

    def annotate_frame(self, frame: np.ndarray, tracked: List[TrackedObject]) -> np.ndarray:
        """Draw tracks and trajectory tails."""
        import cv2
        annotated = frame.copy()
        for obj in tracked:
            x1, y1, x2, y2 = [int(v) for v in obj.bbox]
            cv2.rectangle(annotated, (x1, y1), (x2, y2), (0, 200, 255), 2)

            # Draw trajectory tail
            pts = [(int(p[0]), int(p[1])) for p in obj.trajectory]
            for i in range(1, len(pts)):
                alpha = i / len(pts)
                color = (int(255 * alpha), int(100 * alpha), 255)
                cv2.line(annotated, pts[i-1], pts[i], color, 1)

            label = f"#{obj.track_id} {obj.label} spd:{obj.speed:.1f}"
            cv2.putText(annotated, label, (x1, y1 - 6),
                        cv2.FONT_HERSHEY_SIMPLEX, 0.45, (0, 200, 255), 1)

        return annotated