"""
config.py — Central configuration for RoadSense AI
All paths, thresholds, and constants in one place.
"""

import os

# ── Model Paths ───────────────────────────────────────────────────────────────
BASE_DIR     = r"C:\Users\sunny\Desktop\ADAS Adoption\backend"
VIDEOS_DIR   = r"C:\Users\sunny\Desktop\ADAS Adoption\vedio"
OUTPUTS_DIR  = os.path.join(BASE_DIR, "outputs")

MODELS = {
    "base":   "yolov8n.pt",
    "auto":   os.path.join(BASE_DIR, r"runs\train\auto_rickshaw_v1\weights\best.pt"),
    "rider":  os.path.join(BASE_DIR, r"runs\train\rider_v1\weights\best.pt"),
}

# ── CPU Performance Optimizations ─────────────────────────────────────────────
YOLO_IMGSZ      = 320   # 320 or 416 for 10x faster CPU inference, 640 for CUDA GPU
BYPASS_EMBEDDER = True  # Disables PyTorch MobileNet tracking embedding extraction on CPU (saves 30-100ms/frame)

# ── Detection Thresholds ──────────────────────────────────────────────────────
CONF = {
    "base":   0.40,
    "auto":   0.43,
    "rider":  0.45,
}

# ── COCO class mapping (base model) ──────────────────────────────────────────
COCO_KEEP = {
    0: "person",
    1: "bicycle",
    2: "car",
    5: "bus",
    7: "truck",
}

# ── Classification thresholds ─────────────────────────────────────────────────
FALSE_PED_THRESH     = 0.50
RIDER_OVERLAP_THRESH = 0.25
AUTO_VS_VEH_IOU      = 0.30
NMS_IOU_THRESH       = 0.40

# VRU detection (ALL 3 must be true)
VRU_SPEED_THRESH     = 0.5    # px/frame
VRU_SMALL_BOX        = 0.006  # fraction of frame area
VRU_ROAD_ZONE        = 0.65   # bottom Y fraction of frame

# ── Tracking ──────────────────────────────────────────────────────────────────
DEEPSORT_MAX_AGE     = 30
DEEPSORT_N_INIT      = 3
TRAJECTORY_LEN       = 30     # frames to keep

# ── Risk Engine ───────────────────────────────────────────────────────────────
RISK = {
    "speed_high":        8.0,
    "speed_very_high":   14.0,
    "prox_critical":     120,
    "prox_high":         220,
    "prox_medium":       380,
    "angle_change_high": 25,
    "angle_change_crit": 45,
    "horiz_drift_high":  4.0,
    "horiz_drift_crit":  7.0,
}

# ── Chaos Score ───────────────────────────────────────────────────────────────
CHAOS = {
    "max_vehicles":    20,
    "max_speed_var":   25.0,
    "max_intrusions":  8,
    "max_pedestrians": 6,
    "smooth_window":   10,
    "weights": {
        "density":    0.30,
        "speed_var":  0.20,
        "intrusion":  0.30,
        "pedestrian": 0.20,
    }
}

# ── Explainability ────────────────────────────────────────────────────────────
from dotenv import load_dotenv
load_dotenv(os.path.join(BASE_DIR, ".env"))

GROQ_API_KEY = os.getenv("GROQ_API_KEY", "")
LLM_MODEL    = "llama-3.1-8b-instant"
USE_LLM      = bool(GROQ_API_KEY and GROQ_API_KEY.strip())   # set False if API key is not configured or empty


# ── Colours (BGR for OpenCV) ──────────────────────────────────────────────────
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

RISK_COLOURS = {
    "CRITICAL": (0,   0,   255),
    "HIGH":     (0,  100,  255),
    "MEDIUM":   (0,  200,  255),
    "LOW":      (0,  255,  180),
}

CHAOS_COLOURS = {
    "Calm":     (0,  220,   0),
    "Moderate": (0,  180,  255),
    "Chaotic":  (0,   0,   255),
}