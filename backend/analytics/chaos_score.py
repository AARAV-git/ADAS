"""
analytics/chaos_score.py — Traffic Chaos Score for RoadSense AI

Novel India-specific metric: single 0–100 score measuring traffic chaos.

Formula:
  chaos = density×0.30 + speed_variance×0.20 + lane_intrusions×0.30 + pedestrians×0.20
"""

import numpy as np
from dataclasses import dataclass
from collections import deque
from typing import List
from trackers.deepsort_tracker import TrackedObject
from config import CHAOS


@dataclass
class ChaosResult:
    score:              float
    level:              str
    vehicle_density:    float
    speed_variance:     float
    lane_intrusion:     float
    pedestrian_density: float
    object_count:       int

    def to_dict(self):
        return {
            "score": round(self.score, 1),
            "level": self.level,
            "breakdown": {
                "vehicle_density":    round(self.vehicle_density, 1),
                "speed_variance":     round(self.speed_variance,  1),
                "lane_intrusion":     round(self.lane_intrusion,  1),
                "pedestrian_density": round(self.pedestrian_density, 1),
            },
            "object_count": self.object_count,
        }


class ChaosScoreEngine:
    def __init__(self, frame_width: int = 1280, frame_height: int = 720):
        self.fw = frame_width
        self.fh = frame_height
        self._history = deque(maxlen=CHAOS["smooth_window"])

    def compute(self, tracked: List[TrackedObject]) -> ChaosResult:
        vehicles    = [o for o in tracked if o.label not in
                       ("pedestrian", "vulnerable_road_user")]
        pedestrians = [o for o in tracked if o.label in
                       ("pedestrian", "vulnerable_road_user")]

        # 1. Vehicle density
        v_density = min(len(vehicles) / CHAOS["max_vehicles"], 1.0)

        # 2. Speed variance
        speeds = [o.speed for o in vehicles]
        if len(speeds) >= 2:
            v_speed_var = min(float(np.std(speeds)) / CHAOS["max_speed_var"], 1.0)
        else:
            v_speed_var = 0.0

        # 3. Lane intrusions (high horizontal velocity)
        intrusions  = sum(1 for o in vehicles if abs(o.velocity[0]) > 3.5)
        v_intrusion = min(intrusions / CHAOS["max_intrusions"], 1.0)

        # 4. Pedestrian density
        v_ped = min(len(pedestrians) / CHAOS["max_pedestrians"], 1.0)

        # Weighted composite
        w = CHAOS["weights"]
        raw = (
            v_density   * w["density"] +
            v_speed_var * w["speed_var"] +
            v_intrusion * w["intrusion"] +
            v_ped       * w["pedestrian"]
        )

        raw_score = raw * 100.0
        self._history.append(raw_score)
        score = float(np.mean(self._history))

        return ChaosResult(
            score              = score,
            level              = self._level(score),
            vehicle_density    = v_density    * 100,
            speed_variance     = v_speed_var  * 100,
            lane_intrusion     = v_intrusion  * 100,
            pedestrian_density = v_ped        * 100,
            object_count       = len(tracked),
        )

    def alert_multiplier(self, chaos: ChaosResult) -> float:
        """Higher chaos → lower risk threshold → more sensitive alerts."""
        return 1.0 + (chaos.score / 100.0)

    @staticmethod
    def _level(score: float) -> str:
        if score <= 30: return "Calm"
        if score <= 60: return "Moderate"
        return "Chaotic"