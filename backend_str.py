import os

folders = [
    "backend",
    "backend/detectors",
    "backend/trackers",
    "backend/analytics",
    "backend/explainability",
    "backend/services",
    "backend/utils",
    "backend/outputs",
    "videos"
]

files = [
    "backend/main.py",
    "backend/config.py",

    "backend/detectors/yolo_detector.py",

    "backend/trackers/deepsort_tracker.py",

    "backend/analytics/chaos_score.py",
    "backend/analytics/behavior_engine.py",
    "backend/analytics/risk_engine.py",

    "backend/explainability/llm_alerts.py",

    "backend/services/video_processor.py",
    "backend/services/video_writer.py",

    "backend/utils/drawing.py",
    "backend/utils/geometry.py",

    # "requirements.txt"
]

for folder in folders:
    os.makedirs(folder, exist_ok=True)

for file in files:
    open(file, "a").close()

print("RoadSense AI backend structure created successfully.")