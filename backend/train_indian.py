##################################################################################
#                                                                                #
#                   AUTO RICHAW                                                             #
#                                                                                #
#                                                                                #
#                                                                                #
##################################################################################
# """
# train_indian.py — Fine-tune YOLOv8 to detect Auto Rickshaw
# while keeping all original COCO classes (car, bike, person, etc.)

# Usage:
#     python train_indian.py
# """

# import os
# import yaml
# from ultralytics import YOLO

# # ── Paths ─────────────────────────────────────────────────────────────────────
# DATASET_ROOT = r"C:\Users\sunny\Desktop\ADAS Adoption\backend\datasets\Auto-Rickshaw.v4-raw-image.yolov8"
# OUTPUT_YAML  = r"C:\Users\sunny\Desktop\ADAS Adoption\backend\datasets\auto_rickshaw_fixed.yaml"
# TRAIN_DIR    = os.path.join(DATASET_ROOT, "train", "images")
# VAL_DIR      = os.path.join(DATASET_ROOT, "valid", "images")
# TEST_DIR     = os.path.join(DATASET_ROOT, "test",  "images")
# WEIGHTS_OUT  = r"C:\Users\sunny\Desktop\ADAS Adoption\backend\runs\train\auto_rickshaw_v1\weights\best.pt"


# def check_dataset():
#     print("\n  Checking dataset structure...")
#     ok = True
#     for split, path in [("train", TRAIN_DIR), ("valid", VAL_DIR), ("test", TEST_DIR)]:
#         if os.path.exists(path):
#             count = len([f for f in os.listdir(path) if f.lower().endswith((".jpg", ".jpeg", ".png"))])
#             print(f"    {split:<8} → {count} images  ({'OK' if count > 0 else 'EMPTY!'})")
#             if count == 0:
#                 ok = False
#         else:
#             print(f"    {split:<8} → NOT FOUND: {path}")
#             ok = False
#     return ok


# def create_fixed_yaml():
#     config = {
#         "path":  DATASET_ROOT,
#         "train": TRAIN_DIR,
#         "val":   VAL_DIR,
#         "test":  TEST_DIR,
#         "nc":    1,
#         "names": {0: "auto_rickshaw"},
#     }
#     with open(OUTPUT_YAML, "w") as f:
#         yaml.dump(config, f, default_flow_style=False, allow_unicode=True)
#     print(f"  Fixed yaml → {OUTPUT_YAML}\n")
#     return OUTPUT_YAML


# def train():
#     print(f"\n{'='*60}")
#     print(f"  RoadSense AI — Auto Rickshaw Fine-tuning")
#     print(f"{'='*60}\n")

#     if not check_dataset():
#         print("\n  Fix dataset structure and retry.")
#         return

#     yaml_path = create_fixed_yaml()

#     print("  Loading YOLOv8n base model...")
#     model = YOLO("yolov8n.pt")
#     print("  Model ready. Starting training...\n")

#     results = model.train(
#         data          = yaml_path,
#         epochs        = 40,
#         imgsz         = 640,
#         batch         = 16,
#         device        = 0,
#         name          = "auto_rickshaw_v1",
#         project       = r"C:\Users\sunny\Desktop\ADAS Adoption\backend\runs\train",
#         patience      = 10,
#         save          = True,
#         plots         = True,
#         hsv_h         = 0.015,
#         hsv_s         = 0.7,
#         hsv_v         = 0.4,
#         degrees       = 5.0,
#         translate     = 0.1,
#         scale         = 0.5,
#         shear         = 2.0,
#         fliplr        = 0.5,
#         mosaic        = 1.0,
#         mixup         = 0.1,
#         optimizer     = "AdamW",
#         lr0           = 0.001,
#         lrf           = 0.01,
#         warmup_epochs = 3,
#         verbose       = True,
#     )

#     print(f"\n{'='*60}")
#     print(f"  Training complete!")
#     print(f"  Best weights → {WEIGHTS_OUT}")
#     print(f"  mAP50        : {results.results_dict.get('metrics/mAP50(B)', 0):.3f}")
#     print(f"\n  Test your model:")
#     print(f'  python test_yolo_v2.py --video "video_01.mp4" --show --model "{WEIGHTS_OUT}"')
#     print(f"{'='*60}\n")


# if __name__ == "__main__":
#     train()









"""
train_rider.py — Fine-tune YOLOv8 to detect RIDER as a single class
(person + motorcycle/bicycle/scooty as ONE combined bounding box)

Dataset to download from Roboflow:
  Go to: https://universe.roboflow.com/search?q=class:rider
  Best option: search "rider motorcycle Indian" or "two wheeler rider"
  Download as YOLOv8 format

Usage:
    python train_rider.py
"""

"""
train_rider.py — Fine-tune YOLOv8 on rider dataset
Classes: motorcycle, rider (person+bike as ONE box)
"""

"""
train_rider.py — Fine-tune YOLOv8 to detect RIDER as a single class
(person + motorcycle/bicycle/scooty as ONE combined bounding box)

Dataset: rider.v6-new_gen_rider_1.yolov8  (Roboflow — CC BY 4.0)
  url: https://universe.roboflow.com/rider/rider-hozlt/dataset/6

Usage:
    python train_rider.py
"""

import os
import yaml
from ultralytics import YOLO

# ── Paths ────────────────────────────────────────────────────────────────────
DATASET_ROOT = r"C:\Users\sunny\Desktop\ADAS Adoption\backend\datasets\rider.v6-new_gen_rider_1.yolov8"
OUTPUT_YAML  = r"C:\Users\sunny\Desktop\ADAS Adoption\backend\datasets\rider_fixed.yaml"
TRAIN_DIR    = os.path.join(DATASET_ROOT, "train", "images")
VAL_DIR      = os.path.join(DATASET_ROOT, "valid", "images")
TEST_DIR     = os.path.join(DATASET_ROOT, "test",  "images")
WEIGHTS_OUT  = r"C:\Users\sunny\Desktop\ADAS Adoption\backend\runs\train\rider_v1\weights\best.pt"
# ─────────────────────────────────────────────────────────────────────────────


def check_dataset():
    print("\n  Checking dataset...")
    ok = True
    for split, path in [("train", TRAIN_DIR), ("valid", VAL_DIR), ("test", TEST_DIR)]:
        if os.path.exists(path):
            count = len([f for f in os.listdir(path)
                         if f.lower().endswith((".jpg", ".jpeg", ".png"))])
            print(f"    {split:<8} → {count} images  ({'OK' if count > 0 else 'EMPTY!'})")
            if count == 0:
                ok = False
        else:
            print(f"    {split:<8} → NOT FOUND: {path}")
            ok = False
    return ok


def create_yaml():
    config = {
        "path":  DATASET_ROOT,
        "train": TRAIN_DIR,
        "val":   VAL_DIR,
        "test":  TEST_DIR,
        "nc":    1,
        "names": {0: "rider"},
    }
    with open(OUTPUT_YAML, "w") as f:
        yaml.dump(config, f, default_flow_style=False)
    print(f"\n  Fixed yaml → {OUTPUT_YAML}")
    return OUTPUT_YAML


def train():
    print(f"\n{'='*62}")
    print(f"  RoadSense AI — Rider Detection Training")
    print(f"  Dataset : rider.v6-new_gen_rider_1.yolov8  (v6, CC BY 4.0)")
    print(f"  Classes : rider (person + bike as ONE box)  [nc=1]")
    print(f"{'='*62}\n")

    if not check_dataset():
        print("\n  Fix dataset path and retry.")
        return

    yaml_path = create_yaml()

    print("\n  Loading YOLOv8n base model...")
    model = YOLO("yolov8n.pt")
    print("  Model ready. Starting training...\n")

    results = model.train(
        data          = yaml_path,
        epochs        = 50,
        imgsz         = 640,
        batch         = 16,
        device        = 0,
        name          = "rider_v1",
        project       = r"C:\Users\sunny\Desktop\ADAS Adoption\backend\runs\train",
        patience      = 15,
        save          = True,
        plots         = True,

        # Augmentation
        hsv_h         = 0.015,
        hsv_s         = 0.7,
        hsv_v         = 0.4,
        degrees       = 5.0,
        translate     = 0.1,
        scale         = 0.5,
        shear         = 2.0,
        fliplr        = 0.5,
        mosaic        = 1.0,
        mixup         = 0.15,

        optimizer     = "AdamW",
        lr0           = 0.001,
        lrf           = 0.01,
        warmup_epochs = 3,
        verbose       = True,
    )

    print(f"\n{'='*62}")
    print(f"  Training complete!")
    print(f"  Best weights → {WEIGHTS_OUT}")
    print(f"  mAP50        : {results.results_dict.get('metrics/mAP50(B)', 0):.3f}")
    print(f"\n  Next step:")
    print(f'  python test_triple_model.py --video "your_video.mp4" --save')
    print(f"{'='*62}\n")


if __name__ == "__main__":
    train()