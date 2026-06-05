# """
# risk_engine.py — Behavioral risk prediction for RoadSense AI

# Computes per-object risk using heuristic rules based on:
#   - Speed
#   - Direction change (trajectory angle delta)
#   - Proximity to ego vehicle (bottom-center of frame)
#   - Lane offset / horizontal drift
#   - Object type

# Returns RiskEvent objects consumed by the explainability module.
# """

# import numpy as np
# from dataclasses import dataclass, field
# from typing import List, Optional

# from trackers.deepsort_tracker import TrackedObject


# # ─── Risk Levels ─────────────────────────────────────────────────────────────

# class RiskLevel:
#     LOW      = "LOW"
#     MEDIUM   = "MEDIUM"
#     HIGH     = "HIGH"
#     CRITICAL = "CRITICAL"


# # ─── Risk Types ──────────────────────────────────────────────────────────────

# class RiskType:
#     LANE_CUT         = "lane_cut"
#     COLLISION        = "collision"
#     PEDESTRIAN_CROSS = "pedestrian_crossing"
#     TAILGATING       = "tailgating"
#     BLIND_SPOT       = "blind_spot"
#     SUDDEN_BRAKE     = "sudden_brake"
#     GENERAL          = "general"


# @dataclass
# class RiskEvent:
#     track_id: int
#     label: str
#     risk_type: str
#     risk_level: str
#     risk_score: float          # 0.0–1.0
#     details: dict = field(default_factory=dict)

#     def to_dict(self):
#         return {
#             "track_id":   self.track_id,
#             "label":      self.label,
#             "risk_type":  self.risk_type,
#             "risk_level": self.risk_level,
#             "risk_score": round(self.risk_score, 3),
#             "details":    self.details,
#         }


# # ─── Tunable thresholds ──────────────────────────────────────────────────────

# SPEED_HIGH        = 8.0    # px/frame — fast-moving object
# SPEED_VERY_HIGH   = 14.0
# PROX_CRITICAL     = 120    # px from ego center — very close
# PROX_HIGH         = 220
# PROX_MEDIUM       = 380
# ANGLE_CHANGE_HIGH = 25     # degrees — sharp direction change
# ANGLE_CHANGE_CRIT = 45
# HORIZ_DRIFT_HIGH  = 4.0    # px/frame horizontal drift
# HORIZ_DRIFT_CRIT  = 7.0


# class RiskEngine:
#     """
#     Stateless (per-frame) risk assessor.
#     For each tracked object, applies a set of rule-based checks
#     and aggregates a composite risk score.
#     """

#     def __init__(self, frame_width: int = 1280, frame_height: int = 720):
#         self.frame_width  = frame_width
#         self.frame_height = frame_height
#         # Ego vehicle assumed at bottom-center
#         self.ego_center = (frame_width / 2, frame_height - 50)

#     def assess(self, tracked_objects: List[TrackedObject]) -> List[RiskEvent]:
#         """Return a RiskEvent for every object with risk score > 0.15."""
#         events = []
#         for obj in tracked_objects:
#             event = self._assess_object(obj)
#             if event and event.risk_score > 0.15:
#                 events.append(event)
#         # Sort by risk score descending
#         events.sort(key=lambda e: e.risk_score, reverse=True)
#         return events

#     def _assess_object(self, obj: TrackedObject) -> Optional[RiskEvent]:
#         scores = {}

#         proximity  = self._proximity_score(obj)
#         lane_cut   = self._lane_cut_score(obj)
#         ped_cross  = self._pedestrian_crossing_score(obj)
#         blind_spot = self._blind_spot_score(obj)
#         tailgate   = self._tailgating_score(obj)

#         scores["proximity"]  = proximity
#         scores["lane_cut"]   = lane_cut
#         scores["ped_cross"]  = ped_cross
#         scores["blind_spot"] = blind_spot
#         scores["tailgate"]   = tailgate

#         # Composite score — weighted
#         weights = {
#             "proximity":  0.30,
#             "lane_cut":   0.25,
#             "ped_cross":  0.20,
#             "blind_spot": 0.15,
#             "tailgate":   0.10,
#         }
#         total = sum(scores[k] * weights[k] for k in weights)

#         # Determine dominant risk type
#         dominant = max(scores, key=scores.get)
#         risk_type_map = {
#             "proximity":  RiskType.COLLISION,
#             "lane_cut":   RiskType.LANE_CUT,
#             "ped_cross":  RiskType.PEDESTRIAN_CROSS,
#             "blind_spot": RiskType.BLIND_SPOT,
#             "tailgate":   RiskType.TAILGATING,
#         }
#         risk_type  = risk_type_map.get(dominant, RiskType.GENERAL)
#         risk_level = self._score_to_level(total)

#         details = {
#             "speed":        round(obj.speed, 2),
#             "direction":    round(obj.direction, 1),
#             "proximity_px": round(self._distance_to_ego(obj), 1),
#             "vx":           round(obj.velocity[0], 2),
#             "vy":           round(obj.velocity[1], 2),
#             "sub_scores":   {k: round(v, 3) for k, v in scores.items()},
#         }

#         return RiskEvent(
#             track_id=obj.track_id,
#             label=obj.label,
#             risk_type=risk_type,
#             risk_level=risk_level,
#             risk_score=min(total, 1.0),
#             details=details,
#         )

#     # ── Sub-scorers ──────────────────────────────────────────────────────────

#     def _distance_to_ego(self, obj: TrackedObject) -> float:
#         cx, cy = obj.center
#         ex, ey = self.ego_center
#         return float(np.sqrt((cx - ex)**2 + (cy - ey)**2))

#     def _proximity_score(self, obj: TrackedObject) -> float:
#         dist = self._distance_to_ego(obj)
#         if dist < PROX_CRITICAL:
#             return 1.0
#         elif dist < PROX_HIGH:
#             return 0.75
#         elif dist < PROX_MEDIUM:
#             return 0.40
#         else:
#             return max(0.0, 1.0 - dist / (self.frame_height * 1.5))

#     def _lane_cut_score(self, obj: TrackedObject) -> float:
#         """High horizontal velocity + direction change = lane cut."""
#         vx = abs(obj.velocity[0])
#         score = 0.0

#         if vx > HORIZ_DRIFT_CRIT:
#             score += 0.7
#         elif vx > HORIZ_DRIFT_HIGH:
#             score += 0.4

#         angle_change = self._trajectory_angle_change(obj)
#         if angle_change > ANGLE_CHANGE_CRIT:
#             score += 0.4
#         elif angle_change > ANGLE_CHANGE_HIGH:
#             score += 0.2

#         # Motorcycles / bicycles get a slight uplift (common lane-cutters in India)
#         if obj.label in ("motorcycle", "bicycle"):
#             score *= 1.2

#         return min(score, 1.0)

#     def _pedestrian_crossing_score(self, obj: TrackedObject) -> float:
#         if obj.label != "pedestrian":
#             return 0.0
#         score = 0.0
#         vx = abs(obj.velocity[0])
#         if vx > 1.5:
#             score += 0.4
#         cy = obj.center[1]
#         if cy > self.frame_height * 0.4:
#             score += 0.3
#         if self._distance_to_ego(obj) < PROX_MEDIUM:
#             score += 0.3
#         return min(score, 1.0)

#     def _blind_spot_score(self, obj: TrackedObject) -> float:
#         """Object in left/right edge of frame, approaching fast."""
#         cx = obj.center[0]
#         left_zone  = cx < self.frame_width * 0.20
#         right_zone = cx > self.frame_width * 0.80
#         if not (left_zone or right_zone):
#             return 0.0
#         score = 0.3
#         if obj.speed > SPEED_HIGH:
#             score += 0.4
#         if obj.speed > SPEED_VERY_HIGH:
#             score += 0.2
#         return min(score, 1.0)

#     def _tailgating_score(self, obj: TrackedObject) -> float:
#         """Object directly behind (bottom-center) and close."""
#         cx, cy = obj.center
#         center_x_zone = abs(cx - self.ego_center[0]) < self.frame_width * 0.15
#         bottom_zone   = cy > self.frame_height * 0.65
#         if not (center_x_zone and bottom_zone):
#             return 0.0
#         dist = self._distance_to_ego(obj)
#         if dist < PROX_CRITICAL:
#             return 0.9
#         elif dist < PROX_HIGH:
#             return 0.55
#         return 0.2

#     def _trajectory_angle_change(self, obj: TrackedObject) -> float:
#         """Compute total direction change across recent trajectory."""
#         traj = obj.trajectory
#         if len(traj) < 3:
#             return 0.0
#         angles = []
#         for i in range(1, len(traj)):
#             dx = traj[i][0] - traj[i-1][0]
#             dy = traj[i][1] - traj[i-1][1]
#             if abs(dx) + abs(dy) < 0.5:
#                 continue
#             angles.append(np.degrees(np.arctan2(dy, dx)))
#         if len(angles) < 2:
#             return 0.0
#         changes = [abs(angles[i] - angles[i-1]) for i in range(1, len(angles))]
#         changes = [c if c <= 180 else 360 - c for c in changes]
#         return float(np.mean(changes))

#     @staticmethod
#     def _score_to_level(score: float) -> str:
#         if score >= 0.75:
#             return RiskLevel.CRITICAL
#         elif score >= 0.50:
#             return RiskLevel.HIGH
#         elif score >= 0.30:
#             return RiskLevel.MEDIUM
#         else:
#             return RiskLevel.LOW



"""
risk_engine.py — Behavioral risk prediction for RoadSense AI

Computes per-object risk using heuristic rules based on:
  - Speed
  - Direction change (trajectory angle delta)
  - Proximity to ego vehicle (bottom-center of frame)
  - Lane offset / horizontal drift
  - Object type

Returns RiskEvent objects consumed by the explainability module.
"""

import numpy as np
from dataclasses import dataclass, field
from typing import List, Tuple, Optional
from trackers.deepsort_tracker import TrackedObject


# ─── Risk Levels ────────────────────────────────────────────────────────────

class RiskLevel:
    LOW    = "LOW"
    MEDIUM = "MEDIUM"
    HIGH   = "HIGH"
    CRITICAL = "CRITICAL"


# ─── Risk Types ─────────────────────────────────────────────────────────────

class RiskType:
    LANE_CUT         = "lane_cut"
    COLLISION        = "collision"
    PEDESTRIAN_CROSS = "pedestrian_crossing"
    TAILGATING       = "tailgating"
    BLIND_SPOT       = "blind_spot"
    SUDDEN_BRAKE     = "sudden_brake"
    GENERAL          = "general"


@dataclass
class RiskEvent:
    track_id: int
    label: str
    risk_type: str
    risk_level: str
    risk_score: float          # 0.0–1.0
    details: dict = field(default_factory=dict)

    def to_dict(self):
        return {
            "track_id": self.track_id,
            "label": self.label,
            "risk_type": self.risk_type,
            "risk_level": self.risk_level,
            "risk_score": round(self.risk_score, 3),
            "details": self.details,
        }


# ─── Tunable thresholds ──────────────────────────────────────────────────────

SPEED_HIGH         = 8.0    # px/frame — fast-moving object
SPEED_VERY_HIGH    = 14.0
PROX_CRITICAL      = 120    # px from ego center — very close
PROX_HIGH          = 220
PROX_MEDIUM        = 380
ANGLE_CHANGE_HIGH  = 25     # degrees — sharp direction change
ANGLE_CHANGE_CRIT  = 45
HORIZ_DRIFT_HIGH   = 4.0    # px/frame horizontal drift
HORIZ_DRIFT_CRIT   = 7.0


class RiskEngine:
    """
    Stateless (per-frame) risk assessor.
    For each tracked object, applies a set of rule-based checks
    and aggregates a composite risk score.
    """

    def __init__(self, frame_width: int = 1280, frame_height: int = 720):
        self.frame_width = frame_width
        self.frame_height = frame_height
        # Ego vehicle assumed at bottom-center
        self.ego_center = (frame_width / 2, frame_height - 50)

    def assess(self, tracked_objects: List[TrackedObject]) -> List[RiskEvent]:
        """Return a RiskEvent for every object with risk score > 0.15."""
        events = []
        for obj in tracked_objects:
            event = self._assess_object(obj)
            if event and event.risk_score > 0.15:
                events.append(event)
        # Sort by risk score descending
        events.sort(key=lambda e: e.risk_score, reverse=True)
        return events

    def _assess_object(self, obj: TrackedObject) -> Optional[RiskEvent]:
        scores = {}
        details = {}

        proximity   = self._proximity_score(obj)
        lane_cut    = self._lane_cut_score(obj)
        ped_cross   = self._pedestrian_crossing_score(obj)
        blind_spot  = self._blind_spot_score(obj)
        tailgate    = self._tailgating_score(obj)

        scores["proximity"]   = proximity
        scores["lane_cut"]    = lane_cut
        scores["ped_cross"]   = ped_cross
        scores["blind_spot"]  = blind_spot
        scores["tailgate"]    = tailgate

        # Composite score — weighted
        weights = {
            "proximity":  0.30,
            "lane_cut":   0.25,
            "ped_cross":  0.20,
            "blind_spot": 0.15,
            "tailgate":   0.10,
        }
        total = sum(scores[k] * weights[k] for k in weights)

        # Determine dominant risk type
        dominant = max(scores, key=scores.get)
        risk_type_map = {
            "proximity":  RiskType.COLLISION,
            "lane_cut":   RiskType.LANE_CUT,
            "ped_cross":  RiskType.PEDESTRIAN_CROSS,
            "blind_spot": RiskType.BLIND_SPOT,
            "tailgate":   RiskType.TAILGATING,
        }
        risk_type = risk_type_map.get(dominant, RiskType.GENERAL)

        # Risk level
        risk_level = self._score_to_level(total)

        details = {
            "speed":      round(obj.speed, 2),
            "direction":  round(obj.direction, 1),
            "proximity_px": round(self._distance_to_ego(obj), 1),
            "vx":         round(obj.velocity[0], 2),
            "vy":         round(obj.velocity[1], 2),
            "sub_scores": {k: round(v, 3) for k, v in scores.items()},
        }

        return RiskEvent(
            track_id=obj.track_id,
            label=obj.label,
            risk_type=risk_type,
            risk_level=risk_level,
            risk_score=min(total, 1.0),
            details=details,
        )

    # ── Sub-scorers ──────────────────────────────────────────────────────────

    def _distance_to_ego(self, obj: TrackedObject) -> float:
        cx, cy = obj.center
        ex, ey = self.ego_center
        return float(np.sqrt((cx - ex)**2 + (cy - ey)**2))

    def _proximity_score(self, obj: TrackedObject) -> float:
        dist = self._distance_to_ego(obj)
        if dist < PROX_CRITICAL:
            return 1.0
        elif dist < PROX_HIGH:
            return 0.75
        elif dist < PROX_MEDIUM:
            return 0.40
        else:
            return max(0.0, 1.0 - dist / (self.frame_height * 1.5))

    def _lane_cut_score(self, obj: TrackedObject) -> float:
        """High horizontal velocity + direction change = lane cut."""
        vx = abs(obj.velocity[0])
        score = 0.0

        if vx > HORIZ_DRIFT_CRIT:
            score += 0.7
        elif vx > HORIZ_DRIFT_HIGH:
            score += 0.4

        # Direction change over trajectory
        angle_change = self._trajectory_angle_change(obj)
        if angle_change > ANGLE_CHANGE_CRIT:
            score += 0.4
        elif angle_change > ANGLE_CHANGE_HIGH:
            score += 0.2

        # Motorcycles / autos get a slight uplift (common lane-cutters)
        if obj.label in ("motorcycle", "auto_rickshaw"):
            score *= 1.2

        return min(score, 1.0)

    def _pedestrian_crossing_score(self, obj: TrackedObject) -> float:
        if obj.label != "pedestrian":
            return 0.0
        score = 0.0
        # Moving horizontally toward the road
        vx = abs(obj.velocity[0])
        vy = abs(obj.velocity[1])
        # Pedestrian moving laterally (crossing)
        if vx > 1.5:
            score += 0.4
        # Pedestrian near lane area (center vertically)
        cy = obj.center[1]
        if cy > self.frame_height * 0.4:
            score += 0.3
        # Approaching ego
        if self._distance_to_ego(obj) < PROX_MEDIUM:
            score += 0.3
        return min(score, 1.0)

    def _blind_spot_score(self, obj: TrackedObject) -> float:
        """Object in left/right edge of frame, approaching fast."""
        cx = obj.center[0]
        left_zone  = cx < self.frame_width * 0.20
        right_zone = cx > self.frame_width * 0.80
        if not (left_zone or right_zone):
            return 0.0
        score = 0.3
        if obj.speed > SPEED_HIGH:
            score += 0.4
        if obj.speed > SPEED_VERY_HIGH:
            score += 0.2
        return min(score, 1.0)

    def _tailgating_score(self, obj: TrackedObject) -> float:
        """Object directly behind (bottom-center) and close."""
        cx, cy = obj.center
        center_x_zone = abs(cx - self.ego_center[0]) < self.frame_width * 0.15
        bottom_zone   = cy > self.frame_height * 0.65
        if not (center_x_zone and bottom_zone):
            return 0.0
        dist = self._distance_to_ego(obj)
        if dist < PROX_CRITICAL:
            return 0.9
        elif dist < PROX_HIGH:
            return 0.55
        return 0.2

    def _trajectory_angle_change(self, obj: TrackedObject) -> float:
        """Compute total direction change across recent trajectory."""
        traj = obj.trajectory
        if len(traj) < 3:
            return 0.0
        angles = []
        for i in range(1, len(traj)):
            dx = traj[i][0] - traj[i-1][0]
            dy = traj[i][1] - traj[i-1][1]
            if abs(dx) + abs(dy) < 0.5:
                continue
            angles.append(np.degrees(np.arctan2(dy, dx)))
        if len(angles) < 2:
            return 0.0
        changes = [abs(angles[i] - angles[i-1]) for i in range(1, len(angles))]
        # Normalize angle diff to [0, 180]
        changes = [c if c <= 180 else 360 - c for c in changes]
        return float(np.mean(changes))

    @staticmethod
    def _score_to_level(score: float) -> str:
        if score >= 0.75:
            return RiskLevel.CRITICAL
        elif score >= 0.50:
            return RiskLevel.HIGH
        elif score >= 0.30:
            return RiskLevel.MEDIUM
        else:
            return RiskLevel.LOW