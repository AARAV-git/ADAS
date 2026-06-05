"""
behavior_engine.py — Behavioral pattern analysis for RoadSense AI

Analyzes tracked objects for:
  - Aggressive lane changes
  - Unsafe overtaking patterns
  - Erratic speed changes
  - Crowd-convergence (multiple objects moving toward ego)

Outputs BehaviorTag objects that feed into the risk engine.
"""

import numpy as np
from dataclasses import dataclass, field
from typing import List, Dict, Optional
from collections import defaultdict, deque

from trackers.deepsort_tracker import TrackedObject


# ─── Behavior Tags ───────────────────────────────────────────────────────────

class BehaviorTag:
    AGGRESSIVE_LANE_CHANGE = "aggressive_lane_change"
    ERRATIC_SPEED          = "erratic_speed"
    CONVERGING_TRAJECTORY  = "converging_trajectory"
    WEAVING                = "weaving"
    SUDDEN_STOP            = "sudden_stop"
    FAST_APPROACH          = "fast_approach"
    STATIONARY_OBSTACLE    = "stationary_obstacle"


@dataclass
class BehaviorEvent:
    track_id: int
    label: str
    tags: List[str] = field(default_factory=list)
    severity: float = 0.0   # 0.0 – 1.0

    def to_dict(self):
        return {
            "track_id": self.track_id,
            "label": self.label,
            "tags": self.tags,
            "severity": round(self.severity, 3),
        }


# ─── Thresholds ──────────────────────────────────────────────────────────────

WEAVE_MIN_REVERSALS    = 3     # direction sign-changes in lateral velocity
ERRATIC_SPEED_DELTA    = 4.0   # px/frame change in speed within short window
FAST_APPROACH_SPEED    = 10.0  # px/frame toward ego
STATIONARY_SPEED_MAX   = 0.8   # px/frame — basically stopped
CONVERGE_ANGLE_THRESH  = 30    # degrees — heading toward ego zone


class BehaviorEngine:
    """
    Per-frame behavioral analysis on top of tracker output.
    Maintains short history per track to detect patterns.
    """

    HISTORY_LEN = 20  # frames of speed/velocity history per track

    def __init__(self, frame_width: int = 1280, frame_height: int = 720):
        self.frame_width  = frame_width
        self.frame_height = frame_height
        self.ego_center   = (frame_width / 2, frame_height - 50)

        # Per-track: deque of (speed, vx, vy)
        self._speed_history: Dict[int, deque] = defaultdict(
            lambda: deque(maxlen=self.HISTORY_LEN)
        )

    def analyze(self, tracked_objects: List[TrackedObject]) -> List[BehaviorEvent]:
        """Return a BehaviorEvent for every tracked object with at least one tag."""
        events = []
        for obj in tracked_objects:
            self._speed_history[obj.track_id].append(
                (obj.speed, obj.velocity[0], obj.velocity[1])
            )
            event = self._analyze_object(obj)
            if event.tags:
                events.append(event)
        return events

    def _analyze_object(self, obj: TrackedObject) -> BehaviorEvent:
        tags = []
        severity_parts = []

        history = list(self._speed_history[obj.track_id])

        # ── 1. Aggressive lane change: high lateral velocity ─────────────────
        vx = abs(obj.velocity[0])
        if vx > 6.5:
            tags.append(BehaviorTag.AGGRESSIVE_LANE_CHANGE)
            severity_parts.append(min(vx / 10.0, 1.0))

        # ── 2. Weaving: lateral velocity reverses sign repeatedly ────────────
        if len(history) >= 6:
            lateral = [h[1] for h in history]  # vx series
            reversals = sum(
                1 for i in range(1, len(lateral))
                if lateral[i] * lateral[i - 1] < -0.5  # sign flip
            )
            if reversals >= WEAVE_MIN_REVERSALS:
                tags.append(BehaviorTag.WEAVING)
                severity_parts.append(min(reversals / 6.0, 1.0))

        # ── 3. Erratic speed: high standard deviation in recent speeds ───────
        if len(history) >= 5:
            speeds = [h[0] for h in history[-8:]]
            speed_std = float(np.std(speeds))
            if speed_std > ERRATIC_SPEED_DELTA:
                tags.append(BehaviorTag.ERRATIC_SPEED)
                severity_parts.append(min(speed_std / 12.0, 1.0))

        # ── 4. Fast approach: object moving toward ego quickly ───────────────
        if len(obj.trajectory) >= 4:
            traj = obj.trajectory
            prev_dist = _dist(traj[-4][:2], self.ego_center)
            curr_dist = _dist(traj[-1][:2], self.ego_center)
            approach_speed = (prev_dist - curr_dist) / 3  # avg over 3 frames
            if approach_speed > FAST_APPROACH_SPEED:
                tags.append(BehaviorTag.FAST_APPROACH)
                severity_parts.append(min(approach_speed / 20.0, 1.0))

        # ── 5. Sudden stop ───────────────────────────────────────────────────
        if len(history) >= 5:
            recent_speeds = [h[0] for h in history[-5:]]
            if recent_speeds[0] > 8.0 and recent_speeds[-1] < STATIONARY_SPEED_MAX:
                tags.append(BehaviorTag.SUDDEN_STOP)
                severity_parts.append(0.7)

        # ── 6. Stationary obstacle in ego path ───────────────────────────────
        if obj.speed < STATIONARY_SPEED_MAX:
            cx, cy = obj.center
            in_path = (
                abs(cx - self.ego_center[0]) < self.frame_width * 0.18
                and cy > self.frame_height * 0.55
            )
            if in_path:
                tags.append(BehaviorTag.STATIONARY_OBSTACLE)
                severity_parts.append(0.5)

        severity = float(np.mean(severity_parts)) if severity_parts else 0.0

        return BehaviorEvent(
            track_id=obj.track_id,
            label=obj.label,
            tags=tags,
            severity=severity,
        )


def _dist(p1, p2) -> float:
    return float(np.sqrt((p1[0] - p2[0])**2 + (p1[1] - p2[1])**2))
