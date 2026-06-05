# RoadSense AI — Context-Aware Explainable ADAS for Indian Traffic

RoadSense AI is an AI-powered, context-aware, and explainable behavioral intelligence layer designed specifically for Indian road environments. Unlike traditional ADAS systems that are optimized for structured Western traffic, RoadSense AI adapts to mixed traffic scenarios, lane indiscipline, and high traffic chaos.

---

## 🚀 Key Features

* **Real-Time Object Detection (YOLOv8):** Detects cars, motorcycles, auto-rickshaws, buses, trucks, and pedestrians in complex traffic scenes.
* **Multi-Object Tracking (DeepSORT):** Tracks traffic participants across frames to build trajectory history, estimate velocity, speed, and heading directions.
* **Behavioral Intent Prediction:** Uses heuristic rules to predict aggressive lane-cutting, sudden overtaking, blind-spot intrusions, and pedestrian crossing events.
* **Traffic Chaos Score:** Calculates a dynamic `0–100` chaos score measuring traffic density, speed variance, and lane violations to adapt ADAS sensitivity.
* **Explainable AI Warnings:** Generates human-understandable natural language explanations for alerts (e.g., *"Motorcycle approaching rapidly from left blind spot"*), boosting driver trust and usability.

---

## 🛠️ Tech Stack

* **Object Detection:** YOLOv8
* **Object Tracking:** DeepSORT
* **Backend API:** FastAPI & Uvicorn
* **Image Processing:** OpenCV & NumPy
* **AI Explanations:** Groq LLaMA3 API / Rule-based templates fallback

---

## 📂 Project Structure

```
ADAS Adoption/
│
├── backend/
│   ├── main.py                  # FastAPI Application Entrypoint
│   ├── config.py                # Configuration & Thresholds
│   │
│   ├── detectors/
│   │   └── yolo_detector.py     # YOLOv8 Detection Wrapper
│   │
│   ├── trackers/
│   │   └── deepsort_tracker.py  # DeepSORT Tracking Wrapper
│   │
│   ├── analytics/
│   │   ├── chaos_score.py       # Traffic Chaos Estimation Engine
│   │   ├── behavior_engine.py   # Lateral/Speed Behavior Engine
│   │   └── risk_engine.py       # Multi-Factor Proximity/Lane Risk Engine
│   │
│   ├── explainability/
│   │   └── llm_alerts.py        # Natural Language Warn & Action Generator
│   │
│   ├── services/
│   │   ├── video_processor.py   # Core processing pipeline orchestrator
│   │   └── video_writer.py      # Video export utility
│   │
│   └── utils/
│       ├── drawing.py           # OpenCV Annotation & HUD HUD Overlay drawing
│       └── geometry.py          # Math & Vector utilities
│
├── vedio/                       # Input video folder (ignored in git)
└── requirements.txt             # Python Dependencies
```

---

## ⚡ Quick Start

### 1. Install Dependencies
Navigate to the `backend` folder and run the installer script:
```bash
cd backend
python install.py
```

### 2. Configure Environment Variables
Create a `.env` file in the `backend/` directory and add your Groq API Key:
```env
GROQ_API_KEY=your_groq_api_key_here
```

### 3. Run the Backend Server
Start the Uvicorn development server:
```bash
python -m uvicorn main:app --host 127.0.0.1 --port 8000 --reload
```
Once started:
* The interactive API docs will be available at `http://127.0.0.1:8000/docs`
* You can check the health check endpoint at `http://127.0.0.1:8000/`
* You can stream processed output in real-time in your browser at `http://127.0.0.1:8000/api/stream/video_01.mp4`
