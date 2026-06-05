# import os
# import cv2
# from detectors.yolo_detector import Detector
# from config import VIDEOS_DIR, OUTPUTS_DIR

# def run_test():
#     # Resolve paths
#     video_path = os.path.join(VIDEOS_DIR, "video_02.mp4")
#     output_dir = OUTPUTS_DIR
#     os.makedirs(output_dir, exist_ok=True)
#     output_path = os.path.join(output_dir, "test_yolo_output.mp4")

#     print("=" * 60)
#     print("  RoadSense AI — YOLOv8 Detector Visual Test")
#     print("=" * 60)
#     print(f"[*] Input Video:  {video_path}")
#     print(f"[*] Output Video: {output_path}")

#     if not os.path.exists(video_path):
#         print(f"[!] Input video not found at: {video_path}")
#         print("Please verify your video files in the 'vedio' directory.")
#         return

#     # Initialize Detector
#     detector = Detector(model_path="yolov8n.pt", conf_threshold=0.35)

#     # Open Video Capture
#     cap = cv2.VideoCapture(video_path)
#     if not cap.isOpened():
#         print(f"[!] Failed to open input video.")
#         return

#     # Get video properties
#     width = int(cap.get(cv2.CAP_PROP_FRAME_WIDTH))
#     height = int(cap.get(cv2.CAP_PROP_FRAME_HEIGHT))
#     fps = cap.get(cv2.CAP_PROP_FPS) or 30.0

#     # Initialize Video Writer
#     fourcc = cv2.VideoWriter_fourcc(*'mp4v')
#     out = cv2.VideoWriter(output_path, fourcc, fps, (width, height))
    
#     print("[*] Processing first 60 frames...")
#     frame_count = 0
#     total_detections = 0

#     try:
#         while frame_count < 60:
#             ret, frame = cap.read()
#             if not ret:
#                 break
            
#             frame_count += 1
#             # Run detection
#             detections = detector.detect(frame)
#             total_detections += len(detections)
            
#             # Annotate frame with boxes & labels
#             annotated_frame = detector.annotate_frame(frame, detections)
            
#             # Write to output file
#             out.write(annotated_frame)
            
#             # Count labels detected in this frame
#             labels = [d.label for d in detections]
#             labels_summary = ", ".join([f"{l}: {labels.count(l)}" for l in set(labels)])
            
#             print(f"  Frame {frame_count:02d}: Detected {len(detections)} objects ({labels_summary if labels_summary else 'None'})")

#         print("-" * 60)
#         print(f"[+] Processing complete!")
#         print(f"[+] Total frames processed: {frame_count}")
#         print(f"[+] Total objects detected: {total_detections}")
#         print(f"[+] Visual output saved to: {output_path}")
#         print("=" * 60)
#     finally:
#         cap.release()
#         out.release()

# if __name__ == "__main__":
#     run_test()


"""
test_yolo.py — Standalone YOLOv8 detection test for RoadSense AI

Tests ONLY the detector. No tracker, no risk engine.
Prints detection counts per frame and shows annotated preview.

Usage:
    python test_yolo.py --video path/to/video.mp4
    python test_yolo.py --video path/to/video.mp4 --show
    python test_yolo.py --video path/to/video.mp4 --show --save
    python test_yolo.py --video path/to/video.mp4 --conf 0.35
"""

import cv2
import time
import argparse
import numpy as np
from collections import defaultdict
from ultralytics import YOLO

# ── COCO classes we care about ───────────────────────────────────────────────
RELEVANT = {
    0: ("pedestrian",   (0, 255, 255)),
    1: ("bicycle",      (255, 165, 0)),
    2: ("car",          (0, 255, 0)),
    3: ("motorcycle",   (255, 0, 255)),
    5: ("bus",          (0, 0, 255)),
    7: ("truck",        (128, 0, 128)),
}


def run_yolo_test(video_path: str, conf: float, show: bool, save: bool, skip: int):
    print(f"\n{'='*55}")
    print(f"  YOLOv8 Detection Test — RoadSense AI")
    print(f"  Video : {video_path}")
    print(f"  Conf  : {conf}   Show: {show}   Save: {save}")
    print(f"{'='*55}\n")

    # Load model
    print("  Loading YOLOv8n model...")
    model = YOLO("yolov8n.pt")
    print("  ✅ Model loaded\n")

    cap = cv2.VideoCapture(video_path)
    if not cap.isOpened():
        print(f"  ❌ Cannot open video: {video_path}")
        return

    W     = int(cap.get(cv2.CAP_PROP_FRAME_WIDTH))
    H     = int(cap.get(cv2.CAP_PROP_FRAME_HEIGHT))
    FPS   = cap.get(cv2.CAP_PROP_FPS) or 30
    TOTAL = int(cap.get(cv2.CAP_PROP_FRAME_COUNT))
    print(f"  Resolution : {W}x{H}")
    print(f"  FPS        : {FPS:.1f}")
    print(f"  Frames     : {TOTAL}")
    print(f"  Duration   : {TOTAL/FPS:.1f}s\n")

    writer = None
    if save:
        out_path = video_path.replace(".mp4", "_yolo.mp4")
        fourcc   = cv2.VideoWriter_fourcc(*"mp4v")
        writer   = cv2.VideoWriter(out_path, fourcc, FPS / (skip + 1), (W, H))
        print(f"  Saving → {out_path}\n")

    # Stats
    total_detections = defaultdict(int)
    frame_counts     = []
    fps_smooth       = 0.0
    frame_idx        = 0
    processed        = 0

    print("  Running detection... (press Q to quit preview)\n")
    print(f"  {'Frame':>6}  {'Objects':>7}  {'Car':>5}  {'Moto':>5}  "
          f"{'Ped':>5}  {'Bus':>5}  {'Truck':>5}  {'FPS':>6}")
    print(f"  {'-'*55}")

    while cap.isOpened():
        ret, frame = cap.read()
        if not ret:
            break

        frame_idx += 1
        if frame_idx % (skip + 1) != 0:
            continue

        t0      = time.time()
        results = model(frame, conf=conf, verbose=False)[0]
        elapsed = time.time() - t0
        fps_smooth = 0.8 * fps_smooth + 0.2 * (1.0 / max(elapsed, 1e-4))

        # Parse detections
        frame_det = defaultdict(int)
        annotated = frame.copy()

        for box in results.boxes:
            cls_id = int(box.cls[0])
            if cls_id not in RELEVANT:
                continue

            conf_val = float(box.conf[0])
            label, color = RELEVANT[cls_id]
            x1, y1, x2, y2 = [int(v) for v in box.xyxy[0].tolist()]

            # Draw box
            cv2.rectangle(annotated, (x1, y1), (x2, y2), color, 2)
            tag = f"{label} {conf_val:.2f}"
            (tw, th), _ = cv2.getTextSize(tag, cv2.FONT_HERSHEY_SIMPLEX, 0.5, 1)
            cv2.rectangle(annotated, (x1, y1 - th - 6), (x1 + tw + 4, y1), color, -1)
            cv2.putText(annotated, tag, (x1 + 2, y1 - 4),
                        cv2.FONT_HERSHEY_SIMPLEX, 0.5, (0, 0, 0), 1)

            frame_det[label]          += 1
            total_detections[label]   += 1

        obj_count = sum(frame_det.values())
        frame_counts.append(obj_count)

        # HUD bar
        cv2.rectangle(annotated, (0, 0), (W, 36), (20, 20, 20), -1)
        cv2.putText(annotated,
            f"Objects: {obj_count}  |  "
            f"Car:{frame_det['car']}  Moto:{frame_det['motorcycle']}  "
            f"Ped:{frame_det['pedestrian']}  Bus:{frame_det['bus']}  "
            f"Truck:{frame_det['truck']}  |  FPS:{fps_smooth:.1f}  Frame:{frame_idx}",
            (8, 24), cv2.FONT_HERSHEY_SIMPLEX, 0.55, (200, 255, 200), 1)

        if writer:
            writer.write(annotated)

        if show:
            cv2.imshow("YOLOv8 Detection — RoadSense AI", annotated)
            if cv2.waitKey(1) & 0xFF == ord("q"):
                print("\n  Stopped by user.")
                break

        processed += 1

        # Console table every 20 frames
        if processed % 20 == 0:
            print(f"  {frame_idx:>6}  {obj_count:>7}  "
                  f"{frame_det['car']:>5}  {frame_det['motorcycle']:>5}  "
                  f"{frame_det['pedestrian']:>5}  {frame_det['bus']:>5}  "
                  f"{frame_det['truck']:>5}  {fps_smooth:>5.1f}")

    cap.release()
    if writer:
        writer.release()
    if show:
        cv2.destroyAllWindows()

    # ── Summary ──────────────────────────────────────────────────────────────
    avg_obj = float(np.mean(frame_counts)) if frame_counts else 0
    max_obj = max(frame_counts) if frame_counts else 0

    print(f"\n{'='*55}")
    print(f"  ✅  Detection complete")
    print(f"{'='*55}")
    print(f"  Frames processed  : {processed}")
    print(f"  Avg objects/frame : {avg_obj:.1f}")
    print(f"  Max objects/frame : {max_obj}")
    print(f"\n  Total detections by class:")
    for label, count in sorted(total_detections.items(), key=lambda x: -x[1]):
        bar = "█" * min(count // max(processed // 10, 1), 30)
        print(f"    {label:<14} {count:>6}  {bar}")

    if save:
        print(f"\n  📹 Saved → {video_path.replace('.mp4', '_yolo.mp4')}")
    print(f"{'='*55}\n")

    # Quick sanity check
    if avg_obj < 0.5:
        print("  ⚠️  Very few detections — try lowering --conf (e.g. --conf 0.25)")
    elif avg_obj > 15:
        print("  ⚠️  Many detections — try raising --conf (e.g. --conf 0.50)")
    else:
        print("  👍  Detection looks healthy! Ready for full pipeline.")


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="YOLOv8 detection test")
    parser.add_argument("--video", required=True, help="Path to input .mp4")
    parser.add_argument("--conf",  type=float, default=0.40, help="Confidence threshold (default 0.40)")
    parser.add_argument("--show",  action="store_true", help="Live preview window")
    parser.add_argument("--save",  action="store_true", help="Save annotated output")
    parser.add_argument("--skip",  type=int, default=1,   help="Process every Nth frame (default: every 2nd)")
    args = parser.parse_args()

    run_yolo_test(args.video, conf=args.conf, show=args.show, save=args.save, skip=args.skip)