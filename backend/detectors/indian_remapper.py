"""
indian_remapper.py — Post-processing remapper for Indian traffic detection

Fixes:
  1. Auto rickshaw  — small "car" detections remapped by aspect ratio + area
  2. Rider merging  — person bbox overlapping motorcycle = rider (not pedestrian)
  3. Scooty         — narrow motorcycle with low height = scooty
  4. Wrong pedestrian filtering — removes person detections inside vehicles
"""

import numpy as np
from dataclasses import dataclass, field
from typing import List, Tuple


@dataclass
class Detection:
    track_id: int
    label: str
    confidence: float
    bbox: List[float]        # [x1, y1, x2, y2]
    center: List[float]
    width: float
    height: float
    frame_id: int
    remapped: bool = False   # was this label changed?


def iou(boxA: List[float], boxB: List[float]) -> float:
    """Intersection over Union of two [x1,y1,x2,y2] boxes."""
    xA = max(boxA[0], boxB[0])
    yA = max(boxA[1], boxB[1])
    xB = min(boxA[2], boxB[2])
    yB = min(boxA[3], boxB[3])
    interW = max(0, xB - xA)
    interH = max(0, yB - yA)
    interArea = interW * interH
    if interArea == 0:
        return 0.0
    areaA = (boxA[2]-boxA[0]) * (boxA[3]-boxA[1])
    areaB = (boxB[2]-boxB[0]) * (boxB[3]-boxB[1])
    return interArea / float(areaA + areaB - interArea)


def overlap_ratio(inner: List[float], outer: List[float]) -> float:
    """What fraction of 'inner' box is covered by 'outer' box."""
    xA = max(inner[0], outer[0])
    yA = max(inner[1], outer[1])
    xB = min(inner[2], outer[2])
    yB = min(inner[3], outer[3])
    interW = max(0, xB - xA)
    interH = max(0, yB - yA)
    interArea = interW * interH
    innerArea = (inner[2]-inner[0]) * (inner[3]-inner[1])
    if innerArea == 0:
        return 0.0
    return interArea / innerArea


class IndianTrafficRemapper:
    """
    Applies India-specific post-processing on raw YOLO detections.

    Rules applied in order:
      1. Remap small/boxy cars → auto_rickshaw
      2. Merge person-on-motorcycle → rider
      3. Remove person inside car/bus/truck (false pedestrian)
      4. Remap narrow motorcycle → scooty
    """

    # ── Thresholds (tunable) ─────────────────────────────────────────────────

    # Auto rickshaw: cars that are small AND squarish (aspect ratio near 1)
    AUTO_MAX_AREA        = 0.045   # max fraction of frame area
    AUTO_ASPECT_MIN      = 0.70    # width/height ratio min
    AUTO_ASPECT_MAX      = 1.40    # width/height ratio max

    # Rider merge: person overlapping motorcycle by this much → rider
    RIDER_OVERLAP_THRESH = 0.35

    # False pedestrian: person covered this much by a large vehicle → remove
    FALSE_PED_THRESH     = 0.55

    # Scooty: motorcycle with small width
    SCOOTY_MAX_WIDTH_FRAC = 0.07   # max fraction of frame width

    def __init__(self, frame_width: int = 1280, frame_height: int = 720):
        self.frame_width  = frame_width
        self.frame_height = frame_height
        self.frame_area   = frame_width * frame_height

    def remap(self, detections: List[Detection]) -> List[Detection]:
        """
        Main entry point. Returns cleaned + remapped detection list.
        """
        if not detections:
            return detections

        dets = [d for d in detections]  # shallow copy

        dets = self._remap_auto_rickshaw(dets)
        dets = self._merge_riders(dets)
        dets = self._remove_false_pedestrians(dets)
        dets = self._remap_scooty(dets)

        return dets

    # ── Rule 1: Auto Rickshaw ─────────────────────────────────────────────────

    def _remap_auto_rickshaw(self, dets: List[Detection]) -> List[Detection]:
        """
        Small, squarish cars in Indian footage are almost always auto rickshaws.
        Typical auto: compact body, nearly square bounding box.
        """
        for d in dets:
            if d.label != "car":
                continue

            area_frac   = (d.width * d.height) / self.frame_area
            aspect      = d.width / max(d.height, 1)

            if (area_frac < self.AUTO_MAX_AREA and
                    self.AUTO_ASPECT_MIN < aspect < self.AUTO_ASPECT_MAX):
                d.label    = "auto_rickshaw"
                d.remapped = True

        return dets

    # ── Rule 2: Rider merge ───────────────────────────────────────────────────

    def _merge_riders(self, dets: List[Detection]) -> List[Detection]:
        """
        If a 'person' bbox overlaps significantly with a 'motorcycle'
        or 'scooty' bbox → relabel the person as 'rider' (not pedestrian).
        This prevents false collision/pedestrian alerts for bike riders.
        """
        motos = [d for d in dets if d.label in ("motorcycle", "scooty", "auto_rickshaw")]
        persons = [d for d in dets if d.label == "pedestrian"]

        for person in persons:
            for moto in motos:
                overlap = overlap_ratio(person.bbox, moto.bbox)
                if overlap >= self.RIDER_OVERLAP_THRESH:
                    person.label    = "rider"
                    person.remapped = True
                    break   # one merge per person

        return dets

    # ── Rule 3: False pedestrian removal ─────────────────────────────────────

    def _remove_false_pedestrians(self, dets: List[Detection]) -> List[Detection]:
        """
        Remove 'pedestrian' detections that are mostly inside a car/bus/truck.
        These are passengers seen through windows — not road pedestrians.
        """
        vehicles = [d for d in dets if d.label in ("car", "bus", "truck", "auto_rickshaw")]
        result   = []

        for d in dets:
            if d.label != "pedestrian":
                result.append(d)
                continue

            inside_vehicle = False
            for v in vehicles:
                if overlap_ratio(d.bbox, v.bbox) >= self.FALSE_PED_THRESH:
                    inside_vehicle = True
                    break

            if not inside_vehicle:
                result.append(d)
            # else: silently drop — it's a passenger, not a road hazard

        return result

    # ── Rule 4: Scooty ────────────────────────────────────────────────────────

    def _remap_scooty(self, dets: List[Detection]) -> List[Detection]:
        """
        Scooties (Activa, Jupiter, etc.) appear as narrow motorcycles.
        Width < 7% of frame width is a good proxy.
        """
        for d in dets:
            if d.label != "motorcycle":
                continue
            width_frac = d.width / self.frame_width
            if width_frac < self.SCOOTY_MAX_WIDTH_FRAC:
                d.label    = "scooty"
                d.remapped = True

        return dets

    # ── Summary ───────────────────────────────────────────────────────────────

    def summarize_remaps(self, dets: List[Detection]) -> dict:
        from collections import Counter
        labels   = Counter(d.label for d in dets)
        remapped = Counter(d.label for d in dets if d.remapped)
        return {"labels": dict(labels), "remapped": dict(remapped)}