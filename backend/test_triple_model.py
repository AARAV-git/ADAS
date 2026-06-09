"""
test_triple_model.py — RoadSense AI: 3 models running together

Model 1: yolov8n.pt        → car, bus, truck, pedestrian
Model 2: auto_rickshaw best.pt → auto_rickshaw
Model 3: rider best.pt     → rider (person+bike as ONE box), motorcycle

Rules:
  - rider   box from Model 3 → label = "rider"     (no double count)
  - motorcycle from Model 3  → label = "motorcycle" (standalone bike, no rider)
  - person alone from Model 1 → VRU or pedestrian
  - car/bus/truck from Model 1 → kept as-is
  - person overlapping car/bus/truck → ignored (passenger)
  - auto_rickshaw overlapping car/bus/truck → whichever has higher conf wins
    (prevents van being labelled as BOTH car and auto)

Usage:
    python test_triple_model.py --video "C:\path\to\video.mp4" --save
"""

import cv2
import time
import argparse
import numpy as np
from collections import defaultdict, deque
from ultralytics import YOLO

# ── Model paths ───────────────────────────────────────────────────────────────
BASE_MODEL   = "yolov8n.pt"
AUTO_MODEL   = r"C:\Users\sunny\Desktop\ADAS Adoption\backend\runs\train\auto_rickshaw_v1\weights\best.pt"
RIDER_MODEL  = r"C:\Users\sunny\Desktop\ADAS Adoption\backend\runs\train\rider_v1-2\weights\best.pt"

# ── Colours ───────────────────────────────────────────────────────────────────
COLOURS = {
    "pedestrian":           (0,   255, 255),
    "rider":                (100, 255, 100),
    "vulnerable_road_user": (0,   0,   255),
    "motorcycle":           (255,   0, 255),
    "car":                  (0,   200,   0),
    "bus":                  (50,    0, 200),
    "truck":                (128,   0, 128),
    "auto_rickshaw":        (0,   220, 255),
    "bicycle":              (255, 165,   0),
}

RISK_ORDER = {
    "vulnerable_road_user": 0,
    "pedestrian":           1,
    "rider":                2,
    "auto_rickshaw":        3,
    "motorcycle":           4,
    "bicycle":              5,
    "car":                  6,
    "bus":                  7,
    "truck":                8,
}

# COCO classes from base model
COCO_KEEP = {
    0: "person",
    1: "bicycle",
    2: "car",
    5: "bus",
    7: "truck",
}

# Thresholds
FALSE_PED_THRESH    = 0.50   # person inside large vehicle → ignore
VRU_SPEED_THRESH    = 0.5    # px/frame — very slow
VRU_SMALL_BOX       = 0.006  # small bbox area fraction
VRU_ROAD_ZONE       = 0.65   # below this Y = on road
NMS_IOU_THRESH      = 0.40   # suppress duplicate boxes

# ── FIX: IOU threshold for auto vs car/bus/truck cross-suppression ────────────
# If an auto_rickshaw box overlaps a car/bus/truck box above this ratio,
# only the higher-confidence detection is kept. This kills the van double-count.
AUTO_VS_VEHICLE_IOU = 0.30   # lower = more aggressive suppression


# ── Detection object ──────────────────────────────────────────────────────────
class Det:
    def __init__(self, label, conf, bbox, fw, fh):
        self.label  = label
        self.conf   = conf
        self.bbox   = bbox
        self.cx     = (bbox[0] + bbox[2]) / 2
        self.cy     = (bbox[1] + bbox[3]) / 2
        self.w      = bbox[2] - bbox[0]
        self.h      = bbox[3] - bbox[1]
        self.area   = self.w * self.h
        self.fw     = fw
        self.fh     = fh
        self.speed  = 0.0


def iou(a, b):
    xA = max(a[0], b[0]); yA = max(a[1], b[1])
    xB = min(a[2], b[2]); yB = min(a[3], b[3])
    inter = max(0, xB-xA) * max(0, yB-yA)
    areaA = (a[2]-a[0]) * (a[3]-a[1])
    areaB = (b[2]-b[0]) * (b[3]-b[1])
    union = areaA + areaB - inter
    return inter / union if union > 0 else 0.0


def overlap_ratio(inner, outer):
    xA = max(inner[0], outer[0]); yA = max(inner[1], outer[1])
    xB = min(inner[2], outer[2]); yB = min(inner[3], outer[3])
    inter = max(0, xB-xA) * max(0, yB-yA)
    area  = (inner[2]-inner[0]) * (inner[3]-inner[1])
    return inter / area if area > 0 else 0.0


# ── Speed tracker ─────────────────────────────────────────────────────────────
class SpeedTracker:
    def __init__(self):
        self._tracks = {}

    def update(self, dets):
        new_tracks = {}
        for det in dets:
            key = self._nearest(det.cx, det.cy)
            nkey = (round(det.cx/40), round(det.cy/40))
            if key and key in self._tracks:
                hist = self._tracks[key]
                hist.append((det.cx, det.cy))
                if len(hist) >= 2:
                    dx = hist[-1][0] - hist[-2][0]
                    dy = hist[-1][1] - hist[-2][1]
                    det.speed = float(np.sqrt(dx**2 + dy**2))
                new_tracks[nkey] = hist
            else:
                q = deque(maxlen=8)
                q.append((det.cx, det.cy))
                new_tracks[nkey] = q
                det.speed = 0.0
        self._tracks = new_tracks
        return dets

    def _nearest(self, cx, cy):
        gx, gy = round(cx/40), round(cy/40)
        for dx in range(-1, 2):
            for dy in range(-1, 2):
                k = (gx+dx, gy+dy)
                if k in self._tracks:
                    return k
        return None


# ── Cross-model NMS ───────────────────────────────────────────────────────────
def suppress_auto_vs_vehicle(auto_dets, vehicle_dets):
    """
    For every (auto_rickshaw, car/bus/truck) pair that overlaps above
    AUTO_VS_VEHICLE_IOU, keep only the higher-confidence detection.

    This is the core fix for vans being double-labelled as both car and auto.

    Returns: (filtered_auto_dets, filtered_vehicle_dets)
    """
    drop_auto    = set()
    drop_vehicle = set()

    for ai, a in enumerate(auto_dets):
        for vi, v in enumerate(vehicle_dets):
            if iou(a.bbox, v.bbox) >= AUTO_VS_VEHICLE_IOU:
                # They overlap — keep the more confident prediction
                if a.conf >= v.conf:
                    drop_vehicle.add(vi)
                else:
                    drop_auto.add(ai)

    filtered_auto    = [d for i, d in enumerate(auto_dets)    if i not in drop_auto]
    filtered_vehicle = [d for i, d in enumerate(vehicle_dets) if i not in drop_vehicle]
    return filtered_auto, filtered_vehicle


# ── Classifier ────────────────────────────────────────────────────────────────
class IndianClassifier:
    def __init__(self, fw, fh):
        self.fw = fw
        self.fh = fh
        self.frame_area = fw * fh

    def classify(self, base_dets, rider_dets, auto_dets):
        """
        Merge all detections cleanly:
        - rider_dets: already merged person+bike → keep as rider/motorcycle
        - auto_dets:  auto_rickshaw → keep as-is (after cross-NMS)
        - base_dets:  persons → classify as pedestrian/VRU (skip if near rider box)
                      cars/buses/trucks → keep as-is (after cross-NMS)

        FIX APPLIED:
        Before merging, run cross-model NMS between auto_dets and large
        vehicle dets. Whichever overlapping pair has higher confidence wins.
        This prevents a van from being labelled as both car AND auto_rickshaw.
        """
        result = []

        large_vehicles = [d for d in base_dets
                          if d.label in ("car", "bus", "truck")]
        persons        = [d for d in base_dets if d.label == "person"]
        bicycles       = [d for d in base_dets if d.label == "bicycle"]

        # ── FIX: suppress overlapping auto vs car/bus/truck detections ────────
        auto_dets, large_vehicles = suppress_auto_vs_vehicle(auto_dets, large_vehicles)
        # ─────────────────────────────────────────────────────────────────────

        # 1. Rider model detections (no double count by design)
        for d in rider_dets:
            result.append(d)

        # 2. Auto rickshaw detections (already cross-NMS'd above)
        for d in auto_dets:
            result.append(d)

        # 3. Large vehicles (already cross-NMS'd above)
        for d in large_vehicles:
            result.append(d)

        # 4. Bicycles not covered by rider model
        for b in bicycles:
            overlap_with_rider = any(
                iou(b.bbox, r.bbox) > NMS_IOU_THRESH for r in rider_dets
            )
            if not overlap_with_rider:
                result.append(b)

        # 5. Lone persons — classify as pedestrian or VRU
        for p in persons:
            # Skip if already inside a rider box
            near_rider = any(
                iou(p.bbox, r.bbox) > NMS_IOU_THRESH or
                overlap_ratio(p.bbox, r.bbox) > 0.40
                for r in rider_dets
            )
            if near_rider:
                continue

            # Skip if passenger inside large vehicle
            is_passenger = any(
                overlap_ratio(p.bbox, v.bbox) >= FALSE_PED_THRESH
                for v in large_vehicles
            )
            if is_passenger:
                continue

            p.label = self._classify_person(p)
            result.append(p)

        return result

    def _classify_person(self, p):
        on_road   = p.cy > self.fh * VRU_ROAD_ZONE
        very_slow = p.speed < VRU_SPEED_THRESH
        small_box = (p.area / self.frame_area) < VRU_SMALL_BOX
        vru_score = sum([on_road, very_slow, small_box])
        return "vulnerable_road_user" if vru_score >= 3 else "pedestrian"


# ── Drawing ───────────────────────────────────────────────────────────────────
def draw_box(frame, det):
    x1, y1, x2, y2 = [int(v) for v in det.bbox]
    color     = COLOURS.get(det.label, (200, 200, 200))
    thickness = 3 if det.label in ("vulnerable_road_user", "auto_rickshaw", "rider") else 2

    cv2.rectangle(frame, (x1, y1), (x2, y2), color, thickness)

    labels_short = {
        "vulnerable_road_user": "VRU",
        "auto_rickshaw":        "AUTO",
        "pedestrian":           "PED",
        "motorcycle":           "MOTO",
    }
    tag = f"{labels_short.get(det.label, det.label.upper())} {det.conf:.2f}"
    (tw, th), _ = cv2.getTextSize(tag, cv2.FONT_HERSHEY_SIMPLEX, 0.50, 1)
    cv2.rectangle(frame, (x1, y1-th-8), (x1+tw+6, y1), color, -1)
    cv2.putText(frame, tag, (x1+3, y1-4),
                cv2.FONT_HERSHEY_SIMPLEX, 0.50, (0, 0, 0), 1)

    if det.label == "vulnerable_road_user":
        cx, cy = int(det.cx), int(det.cy)
        r = int(max(det.w, det.h) // 2 + 12)
        cv2.circle(frame, (cx, cy), r,   (0, 0, 255), 2)
        cv2.circle(frame, (cx, cy), r+6, (0, 0, 255), 1)


def draw_hud(frame, counts, fps, frame_id, vru_active):
    h, w = frame.shape[:2]
    bar_col = (50, 0, 0) if vru_active else (15, 15, 15)
    cv2.rectangle(frame, (0, 0), (w, 44), bar_col, -1)

    if vru_active:
        cv2.putText(frame, "!! VRU DETECTED — REDUCE SPEED IMMEDIATELY !!",
                    (10, 18), cv2.FONT_HERSHEY_SIMPLEX, 0.60, (0, 60, 255), 2)

    total = sum(counts.values())
    info  = (f"Frame:{frame_id}  Objects:{total}  "
             f"VRU:{counts['vulnerable_road_user']}  "
             f"Ped:{counts['pedestrian']}  "
             f"Rider:{counts['rider']}  "
             f"Moto:{counts['motorcycle']}  "
             f"Auto:{counts['auto_rickshaw']}  "
             f"Car:{counts['car']}  "
             f"FPS:{fps:.1f}")
    cv2.putText(frame, info, (10, 36),
                cv2.FONT_HERSHEY_SIMPLEX, 0.48, (180, 255, 180), 1)

    cv2.rectangle(frame, (0, h-26), (w, h), (15, 15, 15), -1)
    cv2.putText(frame,
        "RED=VRU  YELLOW=Ped  LT.GREEN=Rider  CYAN=Auto  MAGENTA=Moto  GREEN=Car",
        (8, h-8), cv2.FONT_HERSHEY_SIMPLEX, 0.42, (120, 120, 120), 1)


# ── Main ──────────────────────────────────────────────────────────────────────
def run(video_path, conf_base, conf_auto, conf_rider, save, skip):
    print(f"\n{'='*62}")
    print(f"  RoadSense AI — Triple Model Detection")
    print(f"  Model 1 (base)  : {BASE_MODEL}")
    print(f"  Model 2 (auto)  : auto_rickshaw_v1/best.pt")
    print(f"  Model 3 (rider) : rider_v1/best.pt")
    print(f"  Auto-vs-vehicle IOU suppress threshold: {AUTO_VS_VEHICLE_IOU}")
    print(f"{'='*62}\n")

    print("  Loading 3 models...")
    m_base  = YOLO(BASE_MODEL)
    m_auto  = YOLO(AUTO_MODEL)
    m_rider = YOLO(RIDER_MODEL)
    print("  All 3 models loaded\n")

    cap = cv2.VideoCapture(video_path)
    if not cap.isOpened():
        print(f"  ERROR: Cannot open {video_path}"); return

    W     = int(cap.get(cv2.CAP_PROP_FRAME_WIDTH))
    H     = int(cap.get(cv2.CAP_PROP_FRAME_HEIGHT))
    FPS   = cap.get(cv2.CAP_PROP_FPS) or 30
    TOTAL = int(cap.get(cv2.CAP_PROP_FRAME_COUNT))
    print(f"  {W}x{H} | {FPS:.0f}fps | {TOTAL} frames | {TOTAL/FPS:.1f}s\n")

    speed_tracker = SpeedTracker()
    classifier    = IndianClassifier(W, H)

    writer = None
    if save:
        out_path = video_path.replace(".mp4", "_triple.mp4")
        writer   = cv2.VideoWriter(
            out_path, cv2.VideoWriter_fourcc(*"mp4v"),
            FPS/(skip+1), (W, H))
        print(f"  Saving → {out_path}\n")

    total_counts = defaultdict(int)
    fps_smooth   = 0.0
    frame_idx    = processed = vru_frames = 0

    print(f"  {'Frame':>6}  {'VRU':>4}  {'Ped':>4}  "
          f"{'Rider':>5}  {'Moto':>5}  {'Auto':>5}  {'Car':>4}  {'FPS':>5}")
    print(f"  {'-'*58}")

    while cap.isOpened():
        ret, frame = cap.read()
        if not ret: break

        frame_idx += 1
        if frame_idx % (skip+1) != 0: continue

        t0 = time.time()

        # Run all 3 models
        r_base  = m_base(frame,  conf=conf_base,  verbose=False)[0]
        r_auto  = m_auto(frame,  conf=conf_auto,  verbose=False)[0]
        r_rider = m_rider(frame, conf=conf_rider, verbose=False)[0]

        fps_smooth = 0.8*fps_smooth + 0.2*(1.0/max(time.time()-t0, 1e-4))

        # Parse base model
        base_dets = []
        for box in r_base.boxes:
            cls_id = int(box.cls[0])
            if cls_id not in COCO_KEEP: continue
            base_dets.append(Det(COCO_KEEP[cls_id], float(box.conf[0]),
                                 box.xyxy[0].tolist(), W, H))

        # Parse auto model
        auto_dets = [
            Det("auto_rickshaw", float(box.conf[0]),
                box.xyxy[0].tolist(), W, H)
            for box in r_auto.boxes
        ]

        # Parse rider model (class 0=motorcycle, class 1=rider)
        rider_names = m_rider.names
        rider_dets = []
        for box in r_rider.boxes:
            cls_id = int(box.cls[0])
            label  = rider_names[cls_id].lower()
            rider_dets.append(Det(label, float(box.conf[0]),
                                  box.xyxy[0].tolist(), W, H))

        # Speed estimation
        all_raw = base_dets + auto_dets + rider_dets
        all_raw = speed_tracker.update(all_raw)

        # Classify (cross-NMS happens inside here now)
        dets = classifier.classify(base_dets, rider_dets, auto_dets)

        # Draw
        annotated    = frame.copy()
        frame_counts = defaultdict(int)
        vru_present  = False

        dets.sort(key=lambda d: RISK_ORDER.get(d.label, 9), reverse=True)

        for det in dets:
            draw_box(annotated, det)
            frame_counts[det.label] += 1
            total_counts[det.label] += 1
            if det.label == "vulnerable_road_user":
                vru_present = True

        if vru_present: vru_frames += 1
        draw_hud(annotated, frame_counts, fps_smooth, frame_idx, vru_present)

        if writer: writer.write(annotated)

        processed += 1
        if processed % 20 == 0:
            print(f"  {frame_idx:>6}  "
                  f"{frame_counts['vulnerable_road_user']:>4}  "
                  f"{frame_counts['pedestrian']:>4}  "
                  f"{frame_counts['rider']:>5}  "
                  f"{frame_counts['motorcycle']:>5}  "
                  f"{frame_counts['auto_rickshaw']:>5}  "
                  f"{frame_counts['car']:>4}  "
                  f"{fps_smooth:>5.1f}")

    cap.release()
    if writer: writer.release()

    print(f"\n{'='*62}")
    print(f"  RoadSense AI — Final Detection Summary")
    print(f"  Frames processed : {processed}")
    print(f"  VRU alert frames : {vru_frames} ({vru_frames/max(processed,1)*100:.1f}%)")
    print(f"\n  {'Category':<24} {'Count':>8}  Note")
    print(f"  {'-'*55}")
    for lbl in ["vulnerable_road_user","pedestrian","rider",
                "motorcycle","auto_rickshaw","car","bus","truck","bicycle"]:
        c = total_counts.get(lbl, 0)
        if c == 0: continue
        notes = {
            "vulnerable_road_user": "wheelchair/elderly/disabled — HIGHEST RISK",
            "rider":                "person+bike merged — no double count",
            "auto_rickshaw":        "custom fine-tuned model",
            "motorcycle":           "standalone bike (no rider)",
        }
        print(f"  {lbl:<24} {c:>8}  {notes.get(lbl,'')}")

    if save:
        print(f"\n  Saved → {video_path.replace('.mp4','_triple.mp4')}")
    print(f"{'='*62}\n")


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--video",        required=True)
    parser.add_argument("--conf-base",    type=float, default=0.40)
    parser.add_argument("--conf-auto",    type=float, default=0.43)
    parser.add_argument("--conf-rider",   type=float, default=0.45)
    parser.add_argument("--save",         action="store_true")
    parser.add_argument("--skip",         type=int,   default=1)
    # Expose the suppression threshold as a CLI arg for easy tuning
    parser.add_argument("--auto-vehicle-iou", type=float, default=0.30,
                        help="IOU threshold for auto vs car/bus/truck suppression (default 0.30)")
    args = parser.parse_args()

    # Allow CLI override of the threshold
    import sys
    AUTO_VS_VEHICLE_IOU = args.auto_vehicle_iou

    run(args.video, args.conf_base, args.conf_auto,
        args.conf_rider, args.save, args.skip)