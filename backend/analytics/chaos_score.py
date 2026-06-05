# """
# chaos_score.py — Traffic Chaos Score for RoadSense AI

# India-specific innovation: a single 0–100 score capturing how
# chaotic the current traffic frame is. Higher score → more sensitive
# ADAS alerts.

# Formula:
#   chaos = (vehicle_density * 0.30)
#         + (speed_variance  * 0.20)
#         + (lane_intrusions * 0.30)
#         + (pedestrian_density * 0.20)
# """

# import numpy as np
# from dataclasses import dataclass
# from typing import List
# from collections import deque

# from trackers.deepsort_tracker import TrackedObject


# @dataclass
# class ChaosResult:
#     score: float               # 0–100
#     level: str                 # "Calm" | "Moderate" | "Chaotic"
#     vehicle_density: float
#     speed_variance: float
#     lane_intrusion: float
#     pedestrian_density: float
#     object_count: int

#     def to_dict(self):
#         return {
#             "score": round(self.score, 1),
#             "level": self.level,
#             "breakdown": {
#                 "vehicle_density":    round(self.vehicle_density, 2),
#                 "speed_variance":     round(self.speed_variance, 2),
#                 "lane_intrusion":     round(self.lane_intrusion, 2),
#                 "pedestrian_density": round(self.pedestrian_density, 2),
#             },
#             "object_count": self.object_count,
#         }


# class ChaosScoreEngine:
#     """
#     Computes per-frame chaos score and maintains a smoothed rolling average.
#     """

#     # Normalization constants (tuned for Indian dashcam footage)
#     MAX_VEHICLES    = 20     # vehicles in frame → density = 1.0
#     MAX_SPEED_VAR   = 25.0   # px/frame speed std → var_score = 1.0
#     MAX_INTRUSIONS  = 8      # lateral-drifting objects → intrusion = 1.0
#     MAX_PEDESTRIANS = 6      # pedestrians in frame → ped_score = 1.0

#     SMOOTH_WINDOW = 10       # frames for rolling smoothing

#     def __init__(self, frame_width: int = 1280, frame_height: int = 720):
#         self.frame_width  = frame_width
#         self.frame_height = frame_height
#         self._history: deque = deque(maxlen=self.SMOOTH_WINDOW)

#     def compute(self, tracked_objects: List[TrackedObject]) -> ChaosResult:
#         """Compute chaos score for current frame."""
#         vehicles    = [o for o in tracked_objects if o.label != "pedestrian"]
#         pedestrians = [o for o in tracked_objects if o.label == "pedestrian"]

#         # 1. Vehicle density (normalized)
#         v_density = min(len(vehicles) / self.MAX_VEHICLES, 1.0)

#         # 2. Speed variance among vehicles
#         speeds = [o.speed for o in vehicles]
#         if len(speeds) >= 2:
#             speed_std = float(np.std(speeds))
#             v_speed_var = min(speed_std / self.MAX_SPEED_VAR, 1.0)
#         else:
#             v_speed_var = 0.0

#         # 3. Lane intrusions — vehicles with high horizontal velocity
#         intrusions = sum(1 for o in vehicles if abs(o.velocity[0]) > 3.5)
#         v_intrusion = min(intrusions / self.MAX_INTRUSIONS, 1.0)

#         # 4. Pedestrian density
#         v_ped = min(len(pedestrians) / self.MAX_PEDESTRIANS, 1.0)

#         # Weighted composite (0–1)
#         raw = (
#             v_density   * 0.30 +
#             v_speed_var * 0.20 +
#             v_intrusion * 0.30 +
#             v_ped       * 0.20
#         )

#         raw_score = raw * 100.0

#         # Smooth over rolling window
#         self._history.append(raw_score)
#         score = float(np.mean(self._history))
#         level = self._score_to_level(score)

#         return ChaosResult(
#             score=score,
#             level=level,
#             vehicle_density=v_density * 100,
#             speed_variance=v_speed_var * 100,
#             lane_intrusion=v_intrusion * 100,
#             pedestrian_density=v_ped * 100,
#             object_count=len(tracked_objects),
#         )

#     def get_alert_multiplier(self, chaos: ChaosResult) -> float:
#         """
#         Returns a sensitivity multiplier for risk thresholds.
#         Higher chaos → lower threshold (more sensitive).
#         Returns value in [1.0, 2.0].
#         """
#         return 1.0 + (chaos.score / 100.0)

#     @staticmethod
#     def _score_to_level(score: float) -> str:
#         if score <= 30:
#             return "Calm"
#         elif score <= 60:
#             return "Moderate"
#         else:
#             return "Chaotic"



"""
chaos_score.py — Traffic Chaos Score for RoadSense AI

India-specific innovation: a single 0–100 score capturing how
chaotic the current traffic frame is. Higher score → more sensitive
ADAS alerts.

Formula:
  chaos = (vehicle_density * 0.30)
        + (speed_variance  * 0.20)
        + (lane_intrusions * 0.30)
        + (pedestrian_density * 0.20)
"""

import numpy as np
from dataclasses import dataclass
from typing import List
from collections import deque
from trackers.deepsort_tracker import TrackedObject


@dataclass
class ChaosResult:
    score: float               # 0–100
    level: str                 # "Calm" | "Moderate" | "Chaotic"
    vehicle_density: float
    speed_variance: float
    lane_intrusion: float
    pedestrian_density: float
    object_count: int

    def to_dict(self):
        return {
            "score": round(self.score, 1),
            "level": self.level,
            "breakdown": {
                "vehicle_density":   round(self.vehicle_density, 2),
                "speed_variance":    round(self.speed_variance, 2),
                "lane_intrusion":    round(self.lane_intrusion, 2),
                "pedestrian_density": round(self.pedestrian_density, 2),
            },
            "object_count": self.object_count,
        }


class ChaosScoreEngine:
    """
    Computes per-frame chaos score and maintains a smoothed rolling average.
    """

    # Normalization constants (tuned for Indian dashcam footage)
    MAX_VEHICLES      = 20     # vehicles in frame → density = 1.0
    MAX_SPEED_VAR     = 25.0   # px/frame speed std → var_score = 1.0
    MAX_INTRUSIONS    = 8      # lateral-drifting objects → intrusion = 1.0
    MAX_PEDESTRIANS   = 6      # pedestrians in frame → ped_score = 1.0

    SMOOTH_WINDOW = 10         # frames for rolling smoothing

    def __init__(self, frame_width: int = 1280, frame_height: int = 720):
        self.frame_width = frame_width
        self.frame_height = frame_height
        self._history: deque = deque(maxlen=self.SMOOTH_WINDOW)

    def compute(self, tracked_objects: List[TrackedObject]) -> ChaosResult:
        """Compute chaos score for current frame."""

        vehicles    = [o for o in tracked_objects if o.label != "pedestrian"]
        pedestrians = [o for o in tracked_objects if o.label == "pedestrian"]

        # 1. Vehicle density (normalized)
        v_density = min(len(vehicles) / self.MAX_VEHICLES, 1.0)

        # 2. Speed variance among vehicles
        speeds = [o.speed for o in vehicles]
        if len(speeds) >= 2:
            speed_std = float(np.std(speeds))
            v_speed_var = min(speed_std / self.MAX_SPEED_VAR, 1.0)
        else:
            v_speed_var = 0.0

        # 3. Lane intrusions — vehicles with high horizontal velocity
        intrusions = sum(
            1 for o in vehicles if abs(o.velocity[0]) > 3.5
        )
        v_intrusion = min(intrusions / self.MAX_INTRUSIONS, 1.0)

        # 4. Pedestrian density
        v_ped = min(len(pedestrians) / self.MAX_PEDESTRIANS, 1.0)

        # Weighted composite (0–1)
        raw = (
            v_density   * 0.30 +
            v_speed_var * 0.20 +
            v_intrusion * 0.30 +
            v_ped       * 0.20
        )

        # Scale to 0–100
        raw_score = raw * 100.0

        # Smooth over rolling window
        self._history.append(raw_score)
        score = float(np.mean(self._history))

        level = self._score_to_level(score)

        return ChaosResult(
            score=score,
            level=level,
            vehicle_density=v_density * 100,
            speed_variance=v_speed_var * 100,
            lane_intrusion=v_intrusion * 100,
            pedestrian_density=v_ped * 100,
            object_count=len(tracked_objects),
        )

    def get_alert_multiplier(self, chaos: ChaosResult) -> float:
        """
        Returns a sensitivity multiplier for risk thresholds.
        Higher chaos → lower threshold (more sensitive).
        Returns value in [1.0, 2.0].
        """
        return 1.0 + (chaos.score / 100.0)

    @staticmethod
    def _score_to_level(score: float) -> str:
        if score <= 30:
            return "Calm"
        elif score <= 60:
            return "Moderate"
        else:
            return "Chaotic"