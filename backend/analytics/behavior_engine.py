"""
analytics/behavior_engine.py — Indian Traffic Classifier for RoadSense AI

Converts raw triple-model detections into clean semantic categories:
  rider   = person + motorcycle merged (NO double count)
  VRU     = slow/small/road-zone person
  pedestrian = normal walking person
  auto_rickshaw = from fine-tuned model (cross-NMS'd vs car/bus/truck)
"""

from typing import List, Tuple
from detectors.yolo_detector import RawDetection
from utils.geometry import iou, overlap_ratio
from config import (
    FALSE_PED_THRESH, RIDER_OVERLAP_THRESH,
    AUTO_VS_VEH_IOU, NMS_IOU_THRESH,
    VRU_SPEED_THRESH, VRU_SMALL_BOX, VRU_ROAD_ZONE
)


class IndianBehaviorEngine:
    """
    Applies India-specific detection rules:
      1. Cross-NMS: auto_rickshaw vs car/bus/truck — keep higher conf
      2. Rider merge: person overlapping motorcycle → ONE rider box
      3. Lone person classification: pedestrian vs VRU
      4. Passenger suppression: person inside large vehicle → ignored
    """

    def __init__(self, frame_w: int = 1280, frame_h: int = 720):
        self.fw = frame_w
        self.fh = frame_h
        self.frame_area = frame_w * frame_h

    def process(
        self,
        base_dets:  List[RawDetection],
        rider_dets: List[RawDetection],
        auto_dets:  List[RawDetection],
    ) -> List[RawDetection]:
        """
        Main entry. Returns clean merged detection list.
        """
        # Separate base detections
        persons       = [d for d in base_dets if d.label == "person"]
        bicycles      = [d for d in base_dets if d.label == "bicycle"]
        large_vehs    = [d for d in base_dets if d.label in ("car","bus","truck")]

        # Step 1: Cross-NMS auto vs large vehicles
        auto_dets, large_vehs = self._cross_nms_auto(auto_dets, large_vehs)

        result = []

        # Step 2: Keep rider model detections as-is (already merged)
        for d in rider_dets:
            result.append(d)

        # Step 3: Keep autos and large vehicles
        for d in auto_dets + large_vehs:
            result.append(d)

        # Step 4: Bicycles not covered by rider model
        for b in bicycles:
            if not any(iou(b.bbox, r.bbox) > NMS_IOU_THRESH for r in rider_dets):
                result.append(b)

        # Step 5: Classify lone persons
        for p in persons:
            # Already inside a rider box?
            if any(
                iou(p.bbox, r.bbox) > NMS_IOU_THRESH or
                overlap_ratio(p.bbox, r.bbox) > 0.40
                for r in rider_dets
            ):
                continue

            # Passenger inside large vehicle?
            if any(
                overlap_ratio(p.bbox, v.bbox) >= FALSE_PED_THRESH
                for v in large_vehs
            ):
                continue

            p.label = self._classify_person(p)
            result.append(p)

        return result

    # ── Cross-NMS ─────────────────────────────────────────────────────────────

    def _cross_nms_auto(
        self,
        auto_dets:  List[RawDetection],
        large_vehs: List[RawDetection],
    ) -> Tuple[List[RawDetection], List[RawDetection]]:
        drop_auto = set()
        drop_veh  = set()
        for ai, a in enumerate(auto_dets):
            for vi, v in enumerate(large_vehs):
                if iou(a.bbox, v.bbox) >= AUTO_VS_VEH_IOU:
                    if a.conf >= v.conf:
                        drop_veh.add(vi)
                    else:
                        drop_auto.add(ai)
        return (
            [d for i, d in enumerate(auto_dets)  if i not in drop_auto],
            [d for i, d in enumerate(large_vehs) if i not in drop_veh],
        )

    # ── Person classifier ─────────────────────────────────────────────────────

    def _classify_person(self, p: RawDetection) -> str:
        on_road   = p.cy > self.fh * VRU_ROAD_ZONE
        very_slow = p.speed < VRU_SPEED_THRESH
        small_box = (p.area / self.frame_area) < VRU_SMALL_BOX
        score     = sum([on_road, very_slow, small_box])
        return "vulnerable_road_user" if score >= 3 else "pedestrian"