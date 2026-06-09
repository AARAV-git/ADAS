"""
main.py — RoadSense AI Entry Point (CLI & FastAPI Server)

Usage as CLI:
    python main.py --video "C:\path\to\video.mp4" --save
    python main.py --video "C:\path\to\video.mp4" --save --skip 2

Usage as FastAPI Server (Uvicorn):
    python -m uvicorn main:app --host 127.0.0.1 --port 8000 --reload
"""

import cv2
import time
import argparse
import sys
import os
import json
import asyncio
import numpy as np
from collections import defaultdict
from typing import Optional

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from fastapi import FastAPI, WebSocket, WebSocketDisconnect, HTTPException
from fastapi.responses import HTMLResponse, FileResponse, JSONResponse
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles

from services.video_processor import RoadSensePipeline
from services.video_writer    import VideoWriter
from utils.drawing            import draw_tracked_object, draw_hud

RISK_ORDER_MAP = {
    "vulnerable_road_user": 0,
    "pedestrian":           1,
    "rider":                2,
    "auto_rickshaw":        3,
    "motorcycle":           4,
    "bicycle":              5,
    "car":                  6,
    "bus":                  7,
    "truck":                8,
}

# ── FastAPI App Setup ────────────────────────────────────────────────────────
app = FastAPI(
    title="RoadSense AI — Context-Aware Indian Traffic ADAS",
    description="Real-time object tracking, behavior analysis, and traffic chaos evaluation.",
    version="1.0.0"
)

# Enable CORS for local debugging
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Static files folder mapping
static_path = os.path.join(os.path.dirname(os.path.abspath(__file__)), "static")
os.makedirs(static_path, exist_ok=True)

# ── FastAPI Routes ───────────────────────────────────────────────────────────
@app.get("/")
async def get_index():
    index_file = os.path.join(static_path, "index.html")
    if os.path.exists(index_file):
        return FileResponse(index_file)
    return HTMLResponse(
        "<h2>Welcome to RoadSense AI</h2>"
        "<p>Please create <code>index.html</code> inside the <code>static</code> directory.</p>"
    )

@app.get("/api/videos")
async def get_videos():
    """Returns a list of all available videos in the videos directory."""
    try:
        from config import VIDEOS_DIR
        if not os.path.exists(VIDEOS_DIR):
            return JSONResponse(content=[], status_code=200)
        videos = [
            f for f in os.listdir(VIDEOS_DIR)
            if f.lower().endswith((".mp4", ".avi", ".mov", ".mkv", ".wmv"))
            and "_triple" not in f.lower() and "_roadsense" not in f.lower()
        ]
        return JSONResponse(content=sorted(videos), status_code=200)
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@app.post("/api/explain")
async def explain_alert(payload: dict):
    """Generates a detailed LLM-based explanation for a specific risk event."""
    try:
        from explainability.llm_alerts import ExplainabilityEngine
        from analytics.risk_engine import RiskEvent
        from analytics.chaos_score import ChaosResult
        
        event_dict = payload.get("event", {})
        chaos_dict = payload.get("chaos", {})
        side = payload.get("position", "front")
        
        event = RiskEvent(
            track_id=event_dict.get("track_id", 0),
            label=event_dict.get("label", "vehicle"),
            risk_type=event_dict.get("risk_type", "general"),
            risk_level=event_dict.get("risk_level", "LOW"),
            risk_score=event_dict.get("risk_score", 0.0),
            bbox=event_dict.get("bbox", []),
            details=event_dict.get("details", {})
        )
        
        chaos_breakdown = chaos_dict.get("breakdown", {})
        chaos = ChaosResult(
            score=chaos_dict.get("score", 0.0),
            level=chaos_dict.get("level", "Calm"),
            vehicle_density=chaos_breakdown.get("vehicle_density", 0.0),
            speed_variance=chaos_breakdown.get("speed_variance", 0.0),
            lane_intrusion=chaos_breakdown.get("lane_intrusion", 0.0),
            pedestrian_density=chaos_breakdown.get("pedestrian_density", 0.0),
            object_count=chaos_dict.get("object_count", 0)
        )
        
        explainer = ExplainabilityEngine()
        from config import GROQ_API_KEY
        if GROQ_API_KEY:
            explainer.use_llm = True
            from groq import Groq
            explainer.client = Groq(api_key=GROQ_API_KEY)
            
        alert = explainer._llm_alert(event, chaos, side)
        return alert.to_dict()
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@app.websocket("/ws/stream/{video_name}")
async def websocket_stream(websocket: WebSocket, video_name: str):
    """Streams processed video frames as binary and metadata telemetry as JSON."""
    await websocket.accept()
    from config import VIDEOS_DIR
    video_path = os.path.join(VIDEOS_DIR, video_name)
    
    if not os.path.exists(video_path):
        await websocket.send_json({"error": f"Video {video_name} not found"})
        await websocket.close()
        return
        
    cap = cv2.VideoCapture(video_path)
    if not cap.isOpened():
        await websocket.send_json({"error": f"Cannot open {video_name}"})
        await websocket.close()
        return

    W = int(cap.get(cv2.CAP_PROP_FRAME_WIDTH))
    H = int(cap.get(cv2.CAP_PROP_FRAME_HEIGHT))
    FPS = cap.get(cv2.CAP_PROP_FPS) or 30.0
    frame_delay = 1.0 / FPS

    pipeline = RoadSensePipeline(frame_width=W, frame_height=H)
    fps_smooth = 0.0
    frame_idx = 0
    
    try:
        while cap.isOpened():
            t0 = time.time()
            ret, frame = cap.read()
            if not ret:
                break
                
            frame_idx += 1
            
            # Process frame in background thread pool to avoid blocking the event loop
            result = await asyncio.to_thread(pipeline.process_frame, frame)
            tracked = result["tracked"]
            risks = result["risks"]
            chaos = result["chaos"]
            alerts = result["alerts"]
            
            fps_smooth = 0.8 * fps_smooth + 0.2 * (1.0 / max(time.time() - t0, 1e-4))
            
            # Draw overlay annotations
            annotated = frame.copy()
            frame_counts = defaultdict(int)
            
            tracked_sorted = sorted(
                tracked,
                key=lambda o: RISK_ORDER_MAP.get(o.label, 9),
                reverse=True
            )
            for obj in tracked_sorted:
                draw_tracked_object(annotated, obj)
                frame_counts[obj.label] += 1
                
            draw_hud(annotated, chaos, alerts, fps_smooth, frame_idx)
            
            # Encode frame to JPEG binary format
            _, jpeg_buf = cv2.imencode('.jpg', annotated)
            jpeg_bytes = jpeg_buf.tobytes()
            
            # Convert tracked objects to dict representation
            tracked_data = []
            for obj in tracked:
                tracked_data.append({
                    "track_id": obj.track_id,
                    "label": obj.label,
                    "conf": float(obj.conf),
                    "bbox": [float(v) for v in obj.bbox],
                    "cx": float(obj.cx),
                    "cy": float(obj.cy),
                    "speed": float(obj.speed),
                    "velocity": [float(v) for v in obj.velocity],
                    "direction": float(obj.direction)
                })
            
            # Pack JSON telemetry data
            telemetry = {
                "frame_id": frame_idx,
                "fps": round(fps_smooth, 1),
                "chaos": chaos.to_dict(),
                "alerts": [a.to_dict() for a in alerts],
                "tracked": tracked_data,
                "counts": dict(frame_counts)
            }
            
            # Send JSON text, then binary JPEG bytes
            await websocket.send_text(json.dumps(telemetry))
            await websocket.send_bytes(jpeg_bytes)
            
            # Match original video framerate
            elapsed = time.time() - t0
            sleep_time = max(0.001, frame_delay - elapsed)
            await asyncio.sleep(sleep_time)
            
    except WebSocketDisconnect:
        print(f"WebSocket client disconnected from streaming {video_name}")
    except Exception as e:
        print(f"Error streaming video: {e}")
    finally:
        cap.release()
        try:
            await websocket.close()
        except Exception:
            pass


# ── Live Camera WebSocket (for real-world testing) ───────────────────────────
camera_pipeline = None          # lazy-init on first connection

@app.websocket("/ws/camera")
async def websocket_camera(websocket: WebSocket):
    """
    Receives live camera frames from the browser (getUserMedia / phone camera).
    Each message is a binary JPEG frame.
    Responds with: text JSON telemetry, then binary annotated JPEG.
    """
    global camera_pipeline
    await websocket.accept()
    print("[Camera] Live camera WebSocket connected")

    fps_smooth = 0.0
    frame_idx  = 0

    try:
        while True:
            # Receive a binary JPEG frame from the browser
            raw_bytes = await websocket.receive_bytes()
            t0 = time.time()

            # Decode JPEG → OpenCV frame
            np_arr = np.frombuffer(raw_bytes, dtype=np.uint8)
            frame  = cv2.imdecode(np_arr, cv2.IMREAD_COLOR)

            if frame is None:
                continue

            H, W = frame.shape[:2]

            # Lazy-init or re-init pipeline for this resolution
            if camera_pipeline is None:
                camera_pipeline = RoadSensePipeline(frame_width=W, frame_height=H)
                print(f"[Camera] Pipeline initialized at {W}x{H}")

            frame_idx += 1

            # Process through full ADAS pipeline in background thread pool
            result  = await asyncio.to_thread(camera_pipeline.process_frame, frame)
            tracked = result["tracked"]
            risks   = result["risks"]
            chaos   = result["chaos"]
            alerts  = result["alerts"]

            fps_smooth = 0.8 * fps_smooth + 0.2 * (1.0 / max(time.time() - t0, 1e-4))

            # Draw annotations on frame
            annotated    = frame.copy()
            frame_counts = defaultdict(int)

            tracked_sorted = sorted(
                tracked,
                key=lambda o: RISK_ORDER_MAP.get(o.label, 9),
                reverse=True
            )
            for obj in tracked_sorted:
                draw_tracked_object(annotated, obj)
                frame_counts[obj.label] += 1

            draw_hud(annotated, chaos, alerts, fps_smooth, frame_idx)

            # Encode annotated frame to JPEG
            _, jpeg_buf = cv2.imencode('.jpg', annotated, [cv2.IMWRITE_JPEG_QUALITY, 75])
            jpeg_bytes  = jpeg_buf.tobytes()

            # Build telemetry JSON
            tracked_data = []
            for obj in tracked:
                tracked_data.append({
                    "track_id":  obj.track_id,
                    "label":     obj.label,
                    "conf":      float(obj.conf),
                    "bbox":      [float(v) for v in obj.bbox],
                    "cx":        float(obj.cx),
                    "cy":        float(obj.cy),
                    "speed":     float(obj.speed),
                    "velocity":  [float(v) for v in obj.velocity],
                    "direction": float(obj.direction)
                })

            telemetry = {
                "frame_id": frame_idx,
                "fps":      round(fps_smooth, 1),
                "chaos":    chaos.to_dict(),
                "alerts":   [a.to_dict() for a in alerts],
                "tracked":  tracked_data,
                "counts":   dict(frame_counts)
            }

            # Send telemetry text + annotated frame binary
            await websocket.send_text(json.dumps(telemetry))
            await websocket.send_bytes(jpeg_bytes)

    except WebSocketDisconnect:
        print("[Camera] Client disconnected")
    except Exception as e:
        print(f"[Camera] Error: {e}")
    finally:
        try:
            await websocket.close()
        except Exception:
            pass


@app.get("/api/network-info")
async def get_network_info():
    """Returns the machine's local IP so a phone on the same WiFi can connect."""
    import socket as sock
    try:
        s = sock.socket(sock.AF_INET, sock.SOCK_DGRAM)
        s.connect(("8.8.8.8", 80))
        local_ip = s.getsockname()[0]
        s.close()
    except Exception:
        local_ip = "127.0.0.1"
    return JSONResponse(content={"ip": local_ip, "port": 8000, "url": f"http://{local_ip}:8000"})


# Mount static files folder
app.mount("/static", StaticFiles(directory=static_path), name="static")


# ── CLI Runner Mode ──────────────────────────────────────────────────────────
def run(video_path: str, save: bool, skip: int):
    print(f"\n{'='*62}")
    print(f"  RoadSense AI — Full Pipeline")
    print(f"  Video : {video_path}")
    print(f"  Save  : {save}  |  Skip every {skip+1} frames")
    print(f"{'='*62}")

    cap = cv2.VideoCapture(video_path)
    if not cap.isOpened():
        print(f"\n  ERROR: Cannot open {video_path}")
        return

    W     = int(cap.get(cv2.CAP_PROP_FRAME_WIDTH))
    H     = int(cap.get(cv2.CAP_PROP_FRAME_HEIGHT))
    FPS   = cap.get(cv2.CAP_PROP_FPS) or 30
    TOTAL = int(cap.get(cv2.CAP_PROP_FRAME_COUNT))
    print(f"\n  {W}x{H} | {FPS:.0f}fps | {TOTAL} frames | {TOTAL/FPS:.1f}s\n")

    # Init pipeline
    pipeline = RoadSensePipeline(frame_width=W, frame_height=H)

    # Init video writer
    vwriter = None
    if save:
        vwriter = VideoWriter(
            input_path   = video_path,
            frame_width  = W,
            frame_height = H,
            fps          = FPS,
            skip         = skip,
        )
        vwriter.open()

    fps_smooth  = 0.0
    frame_idx   = processed = 0

    print(f"  {'Frame':>6}  {'VRU':>4}  {'Ped':>4}  {'Rider':>5}  "
          f"{'Auto':>5}  {'Car':>4}  {'Risk':>8}  {'Chaos':>7}  {'FPS':>5}")
    print(f"  {'-'*65}")

    try:
        while cap.isOpened():
            ret, frame = cap.read()
            if not ret:
                break

            frame_idx += 1
            if frame_idx % (skip + 1) != 0:
                continue

            t0 = time.time()

            # ── Full pipeline ──────────────────────────────────────────────
            result  = pipeline.process_frame(frame)
            tracked = result["tracked"]
            risks   = result["risks"]
            chaos   = result["chaos"]
            alerts  = result["alerts"]

            fps_smooth = 0.8*fps_smooth + 0.2*(1.0/max(time.time()-t0, 1e-4))

            # ── Draw ───────────────────────────────────────────────────────
            annotated    = frame.copy()
            frame_counts = defaultdict(int)

            tracked_sorted = sorted(
                tracked,
                key=lambda o: RISK_ORDER_MAP.get(o.label, 9),
                reverse=True
            )

            for obj in tracked_sorted:
                draw_tracked_object(annotated, obj)
                frame_counts[obj.label] += 1

            draw_hud(annotated, chaos, alerts, fps_smooth, frame_idx)

            # ── Write frame ────────────────────────────────────────────────
            if vwriter:
                vwriter.write(annotated, result)

            processed += 1

            if processed % 20 == 0:
                top_risk = risks[0].risk_level if risks else "—"
                print(f"  {frame_idx:>6}  "
                      f"{frame_counts['vulnerable_road_user']:>4}  "
                      f"{frame_counts['pedestrian']:>4}  "
                      f"{frame_counts['rider']:>5}  "
                      f"{frame_counts['auto_rickshaw']:>5}  "
                      f"{frame_counts['car']:>4}  "
                      f"{top_risk:>8}  "
                      f"{chaos.score:>6.1f}  "
                      f"{fps_smooth:>5.1f}")

    finally:
        cap.release()
        summary = vwriter.close() if vwriter else {}

    # ── Final summary ──────────────────────────────────────────────────────
    print(f"\n{'='*62}")
    print(f"  RoadSense AI — Complete")
    print(f"  Frames processed    : {processed}")
    if summary:
        print(f"  VRU alert frames    : {summary['vru_frames']} ({summary['vru_percentage']}%)")
        print(f"  High risk frames    : {summary['high_risk_frames']} ({summary['high_risk_percentage']}%)")
        print(f"  Avg chaos score     : {summary['chaos']['avg']}/100")
        print(f"  Max chaos score     : {summary['chaos']['max']}/100")
        print(f"\n  Detections:")
        for lbl, cnt in sorted(summary['detections'].items(), key=lambda x: -x[1]):
            print(f"    {lbl:<24} {cnt:>8}")
        print(f"\n  Output → {summary['output_video']}")
    print(f"{'='*62}\n")


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="RoadSense AI — Full Pipeline")
    parser.add_argument("--video", required=True)
    parser.add_argument("--save",  action="store_true")
    parser.add_argument("--skip",  type=int, default=1)
    args = parser.parse_args()
    run(args.video, args.save, args.skip)