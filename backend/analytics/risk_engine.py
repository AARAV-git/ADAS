"""
analytics/risk_engine.py — Behavioral Risk Prediction Engine for RoadSense AI

Per-object risk scoring using heuristic rules:
  - Proximity to ego vehicle
  - Lane cut (horizontal drift + direction change)
  - Pedestrian / VRU crossing
  - Blind spot
  - Tailgating

Returns RiskEvent list sorted by score descending.
"""

import numpy as np
from dataclasses import dataclass, field
from typing import List, Optional
from trackers.deepsort_tracker import TrackedObject
from utils.geometry import trajectory_angle_change
from config import RISK


# ── Risk level constants ──────────────────────────────────────────────────────
class RiskLevel:
    LOW      = "LOW"
    MEDIUM   = "MEDIUM"
    HIGH     = "HIGH"
    CRITICAL = "CRITICAL"


class RiskType:
    LANE_CUT         = "lane_cut"
    COLLISION        = "collision"
    PEDESTRIAN_CROSS = "pedestrian_crossing"
    VRU_DETECTED     = "vru_detected"
    TAILGATING       = "tailgating"
    BLIND_SPOT       = "blind_spot"
    GENERAL          = "general"


@dataclass
class RiskEvent:
    track_id:   int
    label:      str
    risk_type:  str
    risk_level: str
    risk_score: float
    bbox:       List[float] = field(default_factory=list)
    details:    dict        = field(default_factory=dict)

    def to_dict(self):
        return {
            "track_id":   self.track_id,
            "label":      self.label,
            "risk_type":  self.risk_type,
            "risk_level": self.risk_level,
            "risk_score": round(self.risk_score, 3),
            "details":    self.details,
        }


# ── VRU multiplier ────────────────────────────────────────────────────────────
VRU_WEIGHT = {
    "vulnerable_road_user": 2.0,
    "pedestrian":           1.2,
    "rider":                1.0,
    "auto_rickshaw":        0.9,
    "motorcycle":           0.9,
    "car":                  0.7,
    "bus":                  0.6,
    "truck":                0.6,
    "bicycle":              1.0,
}


class RiskEngine:
    def __init__(self, frame_width: int = 1280, frame_height: int = 720):
        self.fw = frame_width
        self.fh = frame_height
        self.ego = (frame_width / 2, frame_height - 50)

    def assess(self, tracked: List[TrackedObject]) -> List[RiskEvent]:
        events = []
        for obj in tracked:
            event = self._assess_object(obj)
            if event and event.risk_score > 0.15:
                events.append(event)
        events.sort(key=lambda e: e.risk_score, reverse=True)
        return events

    def _assess_object(self, obj: TrackedObject) -> Optional[RiskEvent]:
        scores = {
            "proximity":  self._proximity(obj),
            "lane_cut":   self._lane_cut(obj),
            "ped_cross":  self._ped_cross(obj),
            "blind_spot": self._blind_spot(obj),
            "tailgate":   self._tailgate(obj),
        }

        weights = {
            "proximity":  0.30,
            "lane_cut":   0.25,
            "ped_cross":  0.20,
            "blind_spot": 0.15,
            "tailgate":   0.10,
        }

        total = sum(scores[k] * weights[k] for k in weights)

        # Apply VRU multiplier
        multiplier = VRU_WEIGHT.get(obj.label, 1.0)
        total = min(total * multiplier, 1.0)

        dominant  = max(scores, key=scores.get)
        risk_type = {
            "proximity":  RiskType.COLLISION,
            "lane_cut":   RiskType.LANE_CUT,
            "ped_cross":  RiskType.PEDESTRIAN_CROSS
                          if obj.label != "vulnerable_road_user"
                          else RiskType.VRU_DETECTED,
            "blind_spot": RiskType.BLIND_SPOT,
            "tailgate":   RiskType.TAILGATING,
        }.get(dominant, RiskType.GENERAL)

        # Override for VRU
        if obj.label == "vulnerable_road_user":
            risk_type = RiskType.VRU_DETECTED
            total = max(total, 0.65)   # VRU minimum HIGH risk

        return RiskEvent(
            track_id   = obj.track_id,
            label      = obj.label,
            risk_type  = risk_type,
            risk_level = self._level(total),
            risk_score = total,
            bbox       = obj.bbox,
            details    = {
                "speed":       round(obj.speed, 2),
                "direction":   round(obj.direction, 1),
                "proximity_px": round(self._dist_ego(obj), 1),
                "vx":          round(obj.velocity[0], 2),
                "vy":          round(obj.velocity[1], 2),
                "sub_scores":  {k: round(v, 3) for k, v in scores.items()},
            },
        )

    # ── Sub-scorers ───────────────────────────────────────────────────────────

    def _dist_ego(self, obj):
        return float(np.sqrt(
            (obj.cx - self.ego[0])**2 + (obj.cy - self.ego[1])**2
        ))

    def _proximity(self, obj):
        d = self._dist_ego(obj)
        if d < RISK["prox_critical"]: return 1.0
        if d < RISK["prox_high"]:     return 0.75
        if d < RISK["prox_medium"]:   return 0.40
        return max(0.0, 1.0 - d / (self.fh * 1.5))

    def _lane_cut(self, obj):
        vx    = abs(obj.velocity[0])
        score = 0.0
        if vx > RISK["horiz_drift_crit"]: score += 0.7
        elif vx > RISK["horiz_drift_high"]: score += 0.4
        ac = trajectory_angle_change(obj.trajectory)
        if ac > RISK["angle_change_crit"]: score += 0.4
        elif ac > RISK["angle_change_high"]: score += 0.2
        if obj.label in ("motorcycle", "auto_rickshaw", "rider"):
            score *= 1.2
        return min(score, 1.0)

    def _ped_cross(self, obj):
        if obj.label not in ("pedestrian", "vulnerable_road_user"):
            return 0.0
        score = 0.0
        if abs(obj.velocity[0]) > 1.5:           score += 0.4
        if obj.cy > self.fh * 0.4:               score += 0.3
        if self._dist_ego(obj) < RISK["prox_medium"]: score += 0.3
        return min(score, 1.0)

    def _blind_spot(self, obj):
        in_left  = obj.cx < self.fw * 0.20
        in_right = obj.cx > self.fw * 0.80
        if not (in_left or in_right): return 0.0
        score = 0.3
        if obj.speed > RISK["speed_high"]:      score += 0.4
        if obj.speed > RISK["speed_very_high"]: score += 0.2
        return min(score, 1.0)

    def _tailgate(self, obj):
        center_zone = abs(obj.cx - self.ego[0]) < self.fw * 0.15
        bottom_zone = obj.cy > self.fh * 0.65
        if not (center_zone and bottom_zone): return 0.0
        d = self._dist_ego(obj)
        if d < RISK["prox_critical"]: return 0.9
        if d < RISK["prox_high"]:     return 0.55
        return 0.2

    @staticmethod
    def _level(score: float) -> str:
        if score >= 0.75: return RiskLevel.CRITICAL
        if score >= 0.50: return RiskLevel.HIGH
        if score >= 0.30: return RiskLevel.MEDIUM
        return RiskLevel.LOW