# RoadSense AI — Frontend Integration & Architecture Plan

This plan compares **React** versus **Flutter** for the RoadSense AI ADAS client app, details the endpoint connection contracts, and outlines the frontend-backend integration architecture.

---

## React vs. Flutter Comparison for Hackathons

For a hackathon, the choice depends on your primary demo vehicle (Web Dashboard vs. Native Mobile In-Car App).

| Metric | ⚛️ React (Web App) | 💙 Flutter (Mobile Native) |
|---|---|---|
| **Demo Accessibility** | **Excellent:** Judges can test it instantly via a web link or local IP QR code without installing anything. | **Fair:** Judges must install an `.apk` (Android) or use TestFlight (iOS) to run it locally on their devices. |
| **Sensor Integration** | **Limited:** Access to mobile compass, GPS, and orientation is restricted by browser security policies. | **Excellent:** Native access to accelerometer, gyroscope, camera hardware settings, and fine-grained GPS. |
| **Camera Performance** | **Good:** Browser camera streaming works via WebSockets but is subject to browser thread limits. | **Excellent:** High-performance native camera controllers and binary streaming via sockets. |
| **UI Polish** | **Outstanding:** Glassmorphism, Tailwind, and chart packages (Recharts/Chart.js) are easy to style. | **Outstanding:** Smooth 60fps native animations and pre-built dashboard widgets. |
| **Recommendation** | **Best for Web Dashboards:** If your pitch highlights historical data analytics, upload features, and standard remote review. | **Best for In-Car Demos:** If you are physically mounting a smartphone in a car or bike to show real-time driver warnings. |

---

## Proposed Changes — API Connection Contracts

The frontend (whether React or Flutter) will connect to the FastAPI backend using three channels: **WebSockets** for real-time video/camera feeds, **JSON REST APIs** for history and upload settings, and the **Explainability API** for AI summaries.

### 1. WebSocket Connections

#### A. Processed Video Stream (`ws://<server_ip>:8000/ws/stream/{video_name}`)
* **Direction:** Backend → Frontend (Binary + Text)
* **Frequency:** Driven by video frame rate (~15-30 FPS)
* **Data Flow:**
  1. Frontend establishes connection.
  2. Backend sends a **Text frame** (JSON telemetry data) followed immediately by a **Binary frame** (raw JPEG bytes of the annotated image).
  3. **JSON Telemetry Schema:**
     ```json
     {
       "frame_id": 42,
       "fps": 24.5,
       "session_id": 1,
       "chaos": {
         "score": 45.2,
         "level": "Moderate",
         "breakdown": {
           "vehicle_density": 40.0,
           "speed_variance": 20.0,
           "lane_intrusion": 60.0,
           "pedestrian_density": 10.0
         }
       },
       "alerts": [
         {
           "track_id": 4,
           "label": "motorcycle",
           "risk_type": "vru_proximity",
           "risk_level": "HIGH",
           "risk_score": 7.8,
           "message": "Vulnerable user approaching rapidly",
           "action": "Slow down and watch left side"
         }
       ],
       "tracked": [
         {
           "track_id": 4,
           "label": "motorcycle",
           "conf": 0.85,
           "bbox": [120, 240, 200, 350],
           "cx": 160.0,
           "cy": 295.0,
           "speed": 12.4,
           "velocity": [-2.1, 1.2],
           "direction": 150.0,
           "frame_w": 640,
           "frame_h": 480
         }
       ],
       "counts": { "car": 3, "motorcycle": 1 }
     }
     ```

#### B. Live Device Camera Stream (`ws://<server_ip>:8000/ws/camera`)
* **Direction:** Bidirectional (Frontend Sends Binary Frames → Backend Returns JSON Telemetry)
* **Backpressure mechanism:** To prevent lag, the frontend must send the next camera frame **only after** receiving the JSON telemetry response from the previous frame.
* **Flow:**
  1. Frontend opens socket connection.
  2. Frontend captures camera frame, converts to JPEG blob (compressed to ~50% quality), and sends via `socket.send(blob)`.
  3. Backend processes frame, saves database entry, writes frame to outputs directory, and returns JSON telemetry (using the same JSON schema above).
  4. Frontend draws telemetry boxes on top of the local video stream.

---

### 2. REST Endpoints

| Method | Path | Request Body | Response JSON Schema |
|---|---|---|---|
| `GET` | `/api/videos` | None | `[ "video_01.mp4", "video_02.mp4" ]` |
| `POST` | `/api/upload` | Multipart File | `{"filename": "name.mp4", "size_mb": 45.2, "message": "Uploaded successfully."}` |
| `DELETE` | `/api/videos/{name}` | None | `{"message": "Deleted 'name.mp4'"}` |
| `GET` | `/api/sessions` | None | `[ { "id": 1, "video_name": "run.mp4", "started_at": "ISO-Date", "ended_at": "ISO-Date", "total_frames": 1000, "avg_fps": 15.0, "avg_chaos_score": 35.0, "max_chaos_score": 75.0, "peak_risk_level": "HIGH", "detection_summary": { "car": 42 } } ]` |
| `GET` | `/api/sessions/{id}` | None | Detailed Session JSON (same schema as above) |
| `GET` | `/api/sessions/{id}/telemetry` | None | `[ { "frame_id": 5, "fps": 20.0, "chaos_score": 25.0, "chaos_level": "Calm", "object_count": 3, "alert_count": 1 } ]` |
| `GET` | `/api/sessions/{id}/alerts` | None | `[ { "frame_id": 5, "track_id": 12, "label": "pedestrian", "risk_type": "pedestrian_on_road", "risk_level": "HIGH", "risk_score": 8.0, "message": "Pedestrian crossed road path" } ]` |
| `DELETE` | `/api/sessions/{id}` | None | `{"message": "Session 1 deleted"}` |
| `GET` | `/api/stats/overview` | None | `{"total_sessions": 5, "total_frames": 5000, "total_alerts": 12, "avg_chaos_score": 42.1, "top_risk_level": "HIGH", "alert_breakdown": { "HIGH": 8, "LOW": 4 }, "top_classes": [ { "label": "motorcycle", "count": 25 } ]}` |

---

### 3. AI Explainability Endpoint

* **Endpoint:** `POST http://<server_ip>:8000/api/explain`
* **Request Payload:**
  ```json
  {
    "event": {
      "track_id": 4,
      "label": "motorcycle",
      "risk_type": "vru_proximity",
      "risk_level": "HIGH",
      "risk_score": 7.8,
      "message": "Vulnerable user approaching"
    },
    "chaos": {
      "score": 45.2,
      "level": "Moderate",
      "breakdown": {
        "vehicle_density": 40.0,
        "speed_variance": 20.0,
        "lane_intrusion": 60.0,
        "pedestrian_density": 10.0
      }
    },
    "position": "left"
  }
  ```
* **Response Payload:**
  ```json
  {
    "risk_level": "HIGH",
    "message": "A motorcycle has entered your left blind spot at 42km/h under highly chaotic lane-weaving conditions. The driver is likely to cut ahead.",
    "action": "Maintain lane position, slow down slightly, and check your left mirror before executing any lateral moves."
  }
  ```

---

## Verification Plan

### Manual Verification
1. Validate REST API endpoints via the built-in Interactive Swagger docs (`http://localhost:8000/docs`).
2. Run a WebSocket mock test to confirm binary frame decoding on the frontend.
3. Simulate high-load camera uploads to verify the backpressure mechanism doesn't freeze the client.
