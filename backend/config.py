import os
from dotenv import load_dotenv

load_dotenv()

# ── Paths ──────────────────────────────────────────────────────────────────────
BASE_DIR    = os.path.dirname(os.path.abspath(__file__))
VIDEOS_DIR  = os.path.join(BASE_DIR, "..", "vedio")   # actual folder is 'vedio'
OUTPUTS_DIR = os.path.join(BASE_DIR, "outputs")
MODELS_DIR  = os.path.join(BASE_DIR, "..", "models")

# ── YOLO ───────────────────────────────────────────────────────────────────────
YOLO_MODEL      = "yolov8n.pt"         # swap to yolov8s.pt for better accuracy
YOLO_CONFIDENCE = 0.40
YOLO_IOU        = 0.45
YOLO_CLASSES    = [0, 1, 2, 3, 5, 7]  # person, bicycle, car, motorcycle, bus, truck

CLASS_NAMES = {
    0: "pedestrian",
    1: "bicycle",
    2: "car",
    3: "motorcycle",
    5: "bus",
    7: "truck",
}

# ── DeepSORT ───────────────────────────────────────────────────────────────────
DEEPSORT_MAX_AGE    = 30
DEEPSORT_N_INIT     = 3
DEEPSORT_MAX_COSINE = 0.4

# ── Risk engine ────────────────────────────────────────────────────────────────
RISK_PROXIMITY_THRESHOLD   = 200   # pixels — objects closer than this are "near"
RISK_SPEED_THRESHOLD       = 15    # px/frame — fast-moving object
RISK_LANE_OFFSET_THRESHOLD = 0.15  # fraction of frame width
RISK_TRAJECTORY_CHANGE_DEG = 25   # degrees — sudden direction change

# ── Chaos score weights ────────────────────────────────────────────────────────
CHAOS_W_DENSITY    = 0.30
CHAOS_W_SPEED_VAR  = 0.20
CHAOS_W_LANE       = 0.30
CHAOS_W_PEDESTRIAN = 0.20

# ── LLM ────────────────────────────────────────────────────────────────────────
GROQ_API_KEY   = os.getenv("GROQ_API_KEY", "")
GROQ_MODEL     = "llama3-8b-8192"
LLM_MAX_TOKENS = 120

# ── Video processing ───────────────────────────────────────────────────────────
FRAME_SKIP        = 2            # process every Nth frame for speed
OUTPUT_FPS        = 20
OUTPUT_RESOLUTION = (1280, 720)  # (width, height)