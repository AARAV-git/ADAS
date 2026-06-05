"""
test_yolo.py — YOLOv8 detection test WITH Indian traffic remapper

Usage:
    python test_yolo.py --video "C:\Users\sunny\Desktop\ADAS Adoption\vedio\video_01.mp4" --show
    python test_yolo.py --video "C:\path\to\video.mp4" --show --save --conf 0.35
"""

import cv2
import time
import argparse
import numpy as np
from collections import defaultdict
from ultralytics import YOLO
from detectors.indian_remapper import IndianTrafficRemapper, Detection

COLOURS = {
    "pedestrian":    (0,   255, 255),
    "bicycle":       (255, 165,   0),
    "car":           (0,   255,   0),
    "motorcycle":    (255,   0, 255),
    "bus":           (0,     0, 255),
    "truck":         (128,   0, 128),
    "auto_rickshaw": (0,   200, 255),
    "scooty":        (255, 100, 200),
    "rider":         (100, 255, 100),
}

COCO_RELEVANT = {0, 1, 2, 3, 5, 7}
COCO_LABEL    = {0:"pedestrian", 1:"bicycle", 2:"car",
                 3:"motorcycle", 5:"bus",     7:"truck"}


def parse_detections(results, frame_id, conf_thresh):
    dets = []
    for box in results.boxes:
        cls_id = int(box.cls[0])
        if cls_id not in COCO_RELEVANT:
            continue
        conf = float(box.conf[0])
        if conf < conf_thresh:
            continue
        x1, y1, x2, y2 = box.xyxy[0].tolist()
        w = x2 - x1
        h = y2 - y1
        dets.append(Detection(
            track_id=-1,
            label=COCO_LABEL[cls_id],
            confidence=conf,
            bbox=[x1, y1, x2, y2],
            center=[(x1+x2)/2, (y1+y2)/2],
            width=w, height=h,
            frame_id=frame_id,
        ))
    return dets


def draw_detections(frame, dets):
    out = frame.copy()
    for d in dets:
        color = COLOURS.get(d.label, (200, 200, 200))
        x1,y1,x2,y2 = [int(v) for v in d.bbox]
        cv2.rectangle(out, (x1,y1), (x2,y2), color, 3 if d.remapped else 2)
        tag = f"{'★' if d.remapped else ''}{d.label} {d.confidence:.2f}"
        (tw, th), _ = cv2.getTextSize(tag, cv2.FONT_HERSHEY_SIMPLEX, 0.48, 1)
        cv2.rectangle(out, (x1, y1-th-6), (x1+tw+4, y1), color, -1)
        cv2.putText(out, tag, (x1+2, y1-4),
                    cv2.FONT_HERSHEY_SIMPLEX, 0.48, (0,0,0), 1)
    return out


def draw_hud(frame, dets, fps, frame_id):
    h, w = frame.shape[:2]
    counts = defaultdict(int)
    for d in dets: counts[d.label] += 1
    remapped = sum(1 for d in dets if d.remapped)
    cv2.rectangle(frame, (0,0), (w,38), (20,20,20), -1)
    cv2.putText(frame,
        f"Frame:{frame_id}  Objects:{len(dets)}  Car:{counts['car']}  "
        f"Moto:{counts['motorcycle']}  Scooty:{counts['scooty']}  "
        f"Auto:{counts['auto_rickshaw']}  Rider:{counts['rider']}  "
        f"Ped:{counts['pedestrian']}  Remapped:{remapped}  FPS:{fps:.1f}",
        (8,26), cv2.FONT_HERSHEY_SIMPLEX, 0.52, (180,255,180), 1)
    cv2.rectangle(frame, (0,h-28), (w,h), (20,20,20), -1)
    cv2.putText(frame,
        "★=remapped  auto_rickshaw=CYAN  scooty=PINK  rider=GREEN",
        (8,h-8), cv2.FONT_HERSHEY_SIMPLEX, 0.45, (160,160,160), 1)
    return frame


def run_test(video_path, conf, show, save, skip):
    print(f"\n{'='*60}")
    print(f"  YOLOv8 + Indian Remapper Test")
    print(f"  Video : {video_path}")
    print(f"  Conf  : {conf}  Show: {show}  Save: {save}")
    print(f"{'='*60}\n")

    model = YOLO("yolov8n.pt")
    print("  Model loaded\n")

    cap = cv2.VideoCapture(video_path)
    if not cap.isOpened():
        print(f"  Cannot open: {video_path}"); return

    W     = int(cap.get(cv2.CAP_PROP_FRAME_WIDTH))
    H     = int(cap.get(cv2.CAP_PROP_FRAME_HEIGHT))
    FPS   = cap.get(cv2.CAP_PROP_FPS) or 30
    TOTAL = int(cap.get(cv2.CAP_PROP_FRAME_COUNT))
    print(f"  {W}x{H} | {FPS:.0f}fps | {TOTAL} frames | {TOTAL/FPS:.1f}s\n")

    remapper = IndianTrafficRemapper(frame_width=W, frame_height=H)

    writer = None
    if save:
        out_path = video_path.replace(".mp4", "_indian_yolo.mp4")
        writer = cv2.VideoWriter(out_path, cv2.VideoWriter_fourcc(*"mp4v"),
                                 FPS/(skip+1), (W,H))
        print(f"  Saving → {out_path}\n")

    raw_counts = defaultdict(int)
    remap_counts = defaultdict(int)
    fps_smooth = 0.0
    frame_idx = processed = 0

    print(f"  {'Frame':>6}  {'Raw':>5}  {'After':>5}  {'Auto':>5}  {'Scooty':>6}  {'Rider':>6}")
    print(f"  {'-'*50}")

    while cap.isOpened():
        ret, frame = cap.read()
        if not ret: break
        frame_idx += 1
        if frame_idx % (skip+1) != 0: continue

        t0 = time.time()
        results   = model(frame, conf=conf, verbose=False)[0]
        raw_dets  = parse_detections(results, frame_idx, conf)
        remap_dets = remapper.remap(raw_dets)
        fps_smooth = 0.8*fps_smooth + 0.2*(1.0/max(time.time()-t0, 1e-4))

        for d in raw_dets:   raw_counts[d.label]   += 1
        for d in remap_dets: remap_counts[d.label] += 1

        annotated = draw_detections(frame, remap_dets)
        annotated = draw_hud(annotated, remap_dets, fps_smooth, frame_idx)

        if writer: writer.write(annotated)
        if show:
            cv2.imshow("RoadSense AI — Indian Detection", annotated)
            if cv2.waitKey(1) & 0xFF == ord("q"):
                print("\n  Stopped."); break

        processed += 1
        if processed % 15 == 0:
            autos   = sum(1 for d in remap_dets if d.label=="auto_rickshaw")
            scooties= sum(1 for d in remap_dets if d.label=="scooty")
            riders  = sum(1 for d in remap_dets if d.label=="rider")
            print(f"  {frame_idx:>6}  {len(raw_dets):>5}  {len(remap_dets):>5}  "
                  f"{autos:>5}  {scooties:>6}  {riders:>6}")

    cap.release()
    if writer:   writer.release()
    if show:     cv2.destroyAllWindows()

    print(f"\n{'='*60}")
    print(f"  Done — {processed} frames processed")
    print(f"\n  BEFORE (raw YOLO):")
    for l,c in sorted(raw_counts.items(),   key=lambda x:-x[1]):
        print(f"    {l:<16} {c:>6}")
    print(f"\n  AFTER (Indian remapper):")
    for l,c in sorted(remap_counts.items(), key=lambda x:-x[1]):
        tag = " ← NEW" if l in ("auto_rickshaw","scooty","rider") else ""
        print(f"    {l:<16} {c:>6}{tag}")

    new = sum(remap_counts.get(c,0) for c in ("auto_rickshaw","scooty","rider"))
    print(f"\n  Indian-specific detections: {new}")
    if new == 0:
        print("  Try --conf 0.30 if autos/scooties are missing")
    else:
        print("  Indian traffic remapping working!")
    if save:
        print(f"\n  Saved → {video_path.replace('.mp4','_indian_yolo.mp4')}")
    print(f"{'='*60}\n")


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--video", required=True)
    parser.add_argument("--conf",  type=float, default=0.35)
    parser.add_argument("--show",  action="store_true")
    parser.add_argument("--save",  action="store_true")
    parser.add_argument("--skip",  type=int, default=1)
    args = parser.parse_args()
    run_test(args.video, args.conf, args.show, args.save, args.skip)