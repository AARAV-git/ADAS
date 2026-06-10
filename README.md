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

## ⚡ Quick Start (Local Development)

### 1. Install Dependencies
Navigate to the `backend` folder and run the installer script:
```bash
cd backend
python install.py
```

### 2. Configure Environment Variables
Create a `.env` file in the root directory (and/or in `backend/`) and add your variables (see `.env.example`):
```env
GROQ_API_KEY=your_groq_api_key_here
DATABASE_URL=sqlite+aiosqlite:///./roadsense.db
```

### 3. Run the Backend Server
Start the Uvicorn development server:
- **Windows:** Run `backend/start_server.bat` OR execute:
  ```bash
  cd backend
  python -m uvicorn main:app --host 0.0.0.0 --port 8000
  ```
- **Linux/macOS:** Run `backend/start_server.sh` OR execute:
  ```bash
  cd backend
  chmod +x start_server.sh
  ./start_server.sh
  ```

---

## 🐳 Docker Deployment (Hackathon Ready)

RoadSense AI is fully containerized and ready for quick deployment. It includes optional Nvidia GPU pass-through support.

### Prerequisites
1. Install [Docker](https://www.docker.com/) and [Docker Compose](https://docs.docker.com/compose/).
2. (Optional for GPU acceleration) Install [NVIDIA Container Toolkit](https://docs.nvidia.com/datacenter/cloud-native/container-toolkit/latest/install-guide.html).

### 1. Build and Start the Stack
From the project root directory, run:
```bash
docker compose up --build -d
```
This command:
* Compiles the multi-stage, production-grade Docker image.
* Starts the FastAPI backend with Uvicorn.
* Mounts local volumes `./data/videos` and `./data/db` for persistent video uploads and database sessions.

### 2. GPU vs CPU Configuration
By default, `docker-compose.yml` attempts to allocate 1 Nvidia GPU. 
* If you are running on a machine without a dedicated GPU, simply comment out or remove the `deploy:` block from the `docker-compose.yml` file.
* The backend will automatically fall back to CPU mode (reducing image resolution to `320` for speed).

---

## 📊 Database & Historical Session Analytics

The system features automatic SQLite/PostgreSQL persistent database integration. 

### Database Architecture
* Every video processed or streamed generates a unique `VideoSession` in the database.
* Frame-by-frame chaos scores, vehicle densities, and warning telemetry are sampled and saved to the database.
* Historical records can be explored directly in the web UI.

### Using the Session History Panel
1. Open the dashboard in your browser (`http://localhost:8000`).
2. Click the **📊 History** button in the top-right toolbar.
3. A slide-over panel will appear showing global overview statistics (Total Sessions, Average Chaos, Total Alerts).
4. Click any listed session to view:
   * A detailed metadata summary.
   * An interactive, canvas-rendered **Traffic Chaos Timeline** chart.
   * A complete list of all **Triggered ADAS Alerts** during that run.
5. Delete any session by clicking the trash can icon (🗑).

