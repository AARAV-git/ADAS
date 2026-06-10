"""
config.py — Central configuration for RoadSense AI
All paths, thresholds, and constants in one place.
Uses environment variables for deployment-ready configuration.
"""

import os
from dotenv import load_dotenv

# Load .env file (works in local dev; in Docker these come from environment)
load_dotenv(os.path.join(os.path.dirname(os.path.abspath(__file__)), ".env"))

# ── Directories ───────────────────────────────────────────────────────────────
BASE_DIR    = os.path.dirname(os.path.abspath(__file__))

# In deployment: set VIDEOS_DIR env var to wherever videos are stored
# Defaults to a "videos" folder next to backend/
VIDEOS_DIR  = os.getenv("VIDEOS_DIR", os.path.join(BASE_DIR, "videos"))
OUTPUTS_DIR = os.getenv("OUTPUTS_DIR", os.path.join(BASE_DIR, "outputs"))

# Create directories if they don't exist
os.makedirs(VIDEOS_DIR,  exist_ok=True)
os.makedirs(OUTPUTS_DIR, exist_ok=True)

# ── Database ──────────────────────────────────────────────────────────────────
# SQLite by default (file in backend/). Override for PostgreSQL:
#   DATABASE_URL=postgresql+asyncpg://user:pass@host/dbname
DATABASE_URL = os.getenv("DATABASE_URL", f"sqlite+aiosqlite:///{os.path.join(BASE_DIR, 'roadsense.db')}")

# ── Model Paths ───────────────────────────────────────────────────────────────
MODELS = {
    "base":   os.getenv("MODEL_BASE",  os.path.join(BASE_DIR, "yolov8n.pt")),
    "auto":   os.getenv("MODEL_AUTO",  os.path.join(BASE_DIR, "runs", "train", "auto_rickshaw_v1", "weights", "best.pt")),
    "rider":  os.getenv("MODEL_RIDER", os.path.join(BASE_DIR, "runs", "train", "rider_v1", "weights", "best.pt")),
}

# ── Dynamic GPU/CPU Performance Optimizations ─────────────────────────────────
import torch
CUDA_AVAILABLE  = torch.cuda.is_available()
YOLO_IMGSZ      = 640 if CUDA_AVAILABLE else 320   # 320 on CPU: best balance of speed vs detection
BYPASS_EMBEDDER = not CUDA_AVAILABLE   # use deep features on GPU, skip on CPU

# ── Detection Thresholds ──────────────────────────────────────────────────────
CONF = {
    "base":  float(os.getenv("CONF_BASE",  "0.40")),
    "auto":  float(os.getenv("CONF_AUTO",  "0.43")),
    "rider": float(os.getenv("CONF_RIDER", "0.45")),
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
DEEPSORT_MAX_AGE     = 60     # frames to keep a track alive without detection
DEEPSORT_N_INIT      = 1     # confirm track on FIRST detection
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
GROQ_API_KEY = os.getenv("GROQ_API_KEY", "")
LLM_MODEL    = os.getenv("LLM_MODEL", "llama-3.1-8b-instant")
USE_LLM      = bool(GROQ_API_KEY and GROQ_API_KEY.strip())

# ── Server ────────────────────────────────────────────────────────────────────
HOST = os.getenv("HOST", "0.0.0.0")
PORT = int(os.getenv("PORT", "8000"))

# Max upload size for video files (default 2 GB)
MAX_UPLOAD_BYTES = int(os.getenv("MAX_UPLOAD_BYTES", str(2 * 1024 * 1024 * 1024)))

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