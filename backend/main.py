"""
main.py — RoadSense AI Entry Point (FastAPI Server + CLI)

Usage as FastAPI Server:
    python -m uvicorn main:app --host 0.0.0.0 --port 8000

Usage as CLI:
    python main.py --video /path/to/video.mp4 --save
"""

import cv2
import time
import argparse
import sys
import os
import json
import asyncio
import shutil
import numpy as np
from collections import defaultdict
from contextlib import asynccontextmanager
from typing import Optional

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from fastapi import (
    FastAPI, WebSocket, WebSocketDisconnect,
    HTTPException, UploadFile, File, Depends, Query
)
from fastapi.responses import HTMLResponse, FileResponse, JSONResponse
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
from sqlalchemy.ext.asyncio import AsyncSession

from services.video_processor import RoadSensePipeline
from services.video_writer    import VideoWriter
from utils.drawing            import draw_tracked_object, draw_hud
from database.db              import init_db, get_db, AsyncSessionLocal
from database import crud

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

RISK_RANK = {"LOW": 0, "MEDIUM": 1, "HIGH": 2, "CRITICAL": 3}


# ── Lifespan (replaces deprecated @app.on_event) ─────────────────────────────
@asynccontextmanager
async def lifespan(app: FastAPI):
    # ── Startup ───────────────────────────────────────────────────────────────
    print("[Startup] Initializing database...")
    await init_db()

    print("[Startup] Pre-loading YOLOv8 models...")
    try:
        _ = RoadSensePipeline(640, 480)
        print("[Startup] Models loaded and cached successfully.")
    except Exception as e:
        print(f"[Startup] Error loading models: {e}")

    yield   # ← server is running

    # ── Shutdown ──────────────────────────────────────────────────────────────
    print("[Shutdown] Server shutting down.")


# ── FastAPI App ───────────────────────────────────────────────────────────────
app = FastAPI(
    title       = "RoadSense AI — Context-Aware Indian Traffic ADAS",
    description = "Real-time object tracking, behavior analysis, and traffic chaos evaluation.",
    version     = "2.0.0",
    lifespan    = lifespan,
)

app.add_middleware(
    CORSMiddleware,
    allow_origins     = ["*"],
    allow_credentials = True,
    allow_methods     = ["*"],
    allow_headers     = ["*"],
)

static_path = os.path.join(os.path.dirname(os.path.abspath(__file__)), "static")
os.makedirs(static_path, exist_ok=True)


# ── Static / Index ────────────────────────────────────────────────────────────
@app.get("/")
async def get_index():
    index_file = os.path.join(static_path, "index.html")
    if os.path.exists(index_file):
        return FileResponse(index_file)
    return HTMLResponse("<h2>RoadSense AI</h2><p>Place index.html in /static.</p>")


# ── Videos API ───────────────────────────────────────────────────────────────
@app.get("/api/videos")
async def get_videos():
    """Returns list of all available videos."""
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


@app.post("/api/upload")
async def upload_video(file: UploadFile = File(...)):
    """
    Upload a video file for processing.
    Accepts: .mp4, .avi, .mov, .mkv, .wmv
    Max size: set MAX_UPLOAD_BYTES in .env (default 2 GB)
    """
    from config import VIDEOS_DIR, MAX_UPLOAD_BYTES

    allowed = {".mp4", ".avi", ".mov", ".mkv", ".wmv"}
    ext = os.path.splitext(file.filename or "")[-1].lower()
    if ext not in allowed:
        raise HTTPException(
            status_code=400,
            detail=f"Unsupported file type '{ext}'. Allowed: {', '.join(allowed)}"
        )

    # Sanitize filename
    safe_name = "".join(
        c if c.isalnum() or c in "._- " else "_"
        for c in (file.filename or "upload")
    ).strip()
    dest = os.path.join(VIDEOS_DIR, safe_name)

    # Stream to disk in chunks — handles large files without memory pressure
    try:
        bytes_written = 0
        with open(dest, "wb") as out:
            while chunk := await file.read(1024 * 1024):  # 1 MB chunks
                bytes_written += len(chunk)
                if bytes_written > MAX_UPLOAD_BYTES:
                    out.close()
                    os.remove(dest)
                    raise HTTPException(status_code=413, detail="File too large")
                out.write(chunk)
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Upload failed: {e}")

    size_mb = round(bytes_written / (1024 * 1024), 1)
    return JSONResponse(content={
        "filename": safe_name,
        "size_mb":  size_mb,
        "message":  f"Uploaded '{safe_name}' ({size_mb} MB) successfully.",
    })


@app.delete("/api/videos/{video_name}")
async def delete_video(video_name: str):
    """Delete a video file from the server."""
    from config import VIDEOS_DIR
    path = os.path.join(VIDEOS_DIR, video_name)
    if not os.path.exists(path):
        raise HTTPException(status_code=404, detail="Video not found")
    os.remove(path)
    return JSONResponse(content={"message": f"Deleted '{video_name}'"})


# ── Sessions API ──────────────────────────────────────────────────────────────
@app.get("/api/sessions")
async def list_sessions(
    limit:  int = Query(default=20, ge=1, le=100),
    offset: int = Query(default=0,  ge=0),
    db: AsyncSession = Depends(get_db),
):
    """List all past video sessions with summary stats."""
    sessions = await crud.list_sessions(db, limit=limit, offset=offset)
    return JSONResponse(content=[s.summary_dict() for s in sessions])


@app.get("/api/sessions/{session_id}")
async def get_session(session_id: int, db: AsyncSession = Depends(get_db)):
    """Get full details for a specific session."""
    session = await crud.get_session(db, session_id)
    if not session:
        raise HTTPException(status_code=404, detail="Session not found")
    return JSONResponse(content=session.summary_dict())


@app.get("/api/sessions/{session_id}/telemetry")
async def get_session_telemetry(session_id: int, db: AsyncSession = Depends(get_db)):
    """Get frame-by-frame chaos + object count timeline for a session."""
    session = await crud.get_session(db, session_id)
    if not session:
        raise HTTPException(status_code=404, detail="Session not found")
    rows = await crud.get_session_telemetry(db, session_id)
    return JSONResponse(content=[r.to_dict() for r in rows])


@app.get("/api/sessions/{session_id}/alerts")
async def get_session_alerts(session_id: int, db: AsyncSession = Depends(get_db)):
    """Get all ADAS alerts generated during a session."""
    session = await crud.get_session(db, session_id)
    if not session:
        raise HTTPException(status_code=404, detail="Session not found")
    alerts = await crud.get_session_alerts(db, session_id)
    return JSONResponse(content=[a.to_dict() for a in alerts])


@app.delete("/api/sessions/{session_id}")
async def delete_session(session_id: int, db: AsyncSession = Depends(get_db)):
    """Delete a session and all its data."""
    deleted = await crud.delete_session(db, session_id)
    if not deleted:
        raise HTTPException(status_code=404, detail="Session not found")
    return JSONResponse(content={"message": f"Session {session_id} deleted"})


@app.get("/api/stats/overview")
async def stats_overview(db: AsyncSession = Depends(get_db)):
    """Aggregated stats across all sessions — for a summary dashboard."""
    stats = await crud.get_overview_stats(db)
    return JSONResponse(content=stats)


# ── Explain API ───────────────────────────────────────────────────────────────
@app.post("/api/explain")
async def explain_alert(payload: dict):
    """Generates a detailed LLM-based explanation for a specific risk event."""
    try:
        from explainability.llm_alerts import ExplainabilityEngine
        from analytics.risk_engine import RiskEvent
        from analytics.chaos_score import ChaosResult

        event_dict = payload.get("event", {})
        chaos_dict = payload.get("chaos", {})
        side       = payload.get("position", "front")

        event = RiskEvent(
            track_id   = event_dict.get("track_id", 0),
            label      = event_dict.get("label", "vehicle"),
            risk_type  = event_dict.get("risk_type", "general"),
            risk_level = event_dict.get("risk_level", "LOW"),
            risk_score = event_dict.get("risk_score", 0.0),
            bbox       = event_dict.get("bbox", []),
            details    = event_dict.get("details", {}),
        )

        chaos_breakdown = chaos_dict.get("breakdown", {})
        chaos = ChaosResult(
            score              = chaos_dict.get("score", 0.0),
            level              = chaos_dict.get("level", "Calm"),
            vehicle_density    = chaos_breakdown.get("vehicle_density", 0.0),
            speed_variance     = chaos_breakdown.get("speed_variance", 0.0),
            lane_intrusion     = chaos_breakdown.get("lane_intrusion", 0.0),
            pedestrian_density = chaos_breakdown.get("pedestrian_density", 0.0),
            object_count       = chaos_dict.get("object_count", 0),
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


# ── Network Info ──────────────────────────────────────────────────────────────
@app.get("/api/network-info")
async def get_network_info():
    """Returns local IP so phones on the same WiFi can connect."""
    import socket as sock
    try:
        s = sock.socket(sock.AF_INET, sock.SOCK_DGRAM)
        s.connect(("8.8.8.8", 80))
        local_ip = s.getsockname()[0]
        s.close()
    except Exception:
        local_ip = "127.0.0.1"
    from config import PORT
    return JSONResponse(content={"ip": local_ip, "port": PORT,
                                  "url": f"http://{local_ip}:{PORT}"})


# ── Helpers ───────────────────────────────────────────────────────────────────
def _tracked_to_dict(obj) -> dict:
    return {
        "track_id":  int(obj.track_id),            # force Python int — DeepSORT returns np.int64
        "label":     str(obj.label),               # force Python str — guard against np.str_
        "conf":      float(obj.conf),
        "bbox":      [float(v) for v in obj.bbox],
        "cx":        float(obj.cx),
        "cy":        float(obj.cy),
        "speed":     float(obj.speed),
        "velocity":  [float(v) for v in obj.velocity],
        "direction": float(obj.direction),
        "frame_w":   int(obj.frame_w),
        "frame_h":   int(obj.frame_h),
    }


# ── Video Stream WebSocket ────────────────────────────────────────────────────
@app.websocket("/ws/stream/{video_name}")
async def websocket_stream(websocket: WebSocket, video_name: str):
    """Streams processed video frames (binary JPEG) + JSON telemetry."""
    await websocket.accept()
    from config import VIDEOS_DIR
    video_path = os.path.join(VIDEOS_DIR, video_name)

    if not os.path.exists(video_path):
        await websocket.send_json({"error": f"Video '{video_name}' not found"})
        await websocket.close()
        return

    cap = cv2.VideoCapture(video_path)
    if not cap.isOpened():
        await websocket.send_json({"error": f"Cannot open '{video_name}'"})
        await websocket.close()
        return

    W   = int(cap.get(cv2.CAP_PROP_FRAME_WIDTH))
    H   = int(cap.get(cv2.CAP_PROP_FRAME_HEIGHT))
    FPS = cap.get(cv2.CAP_PROP_FPS) or 30.0

    VIDEO_MAX_W = 1280         # Crisp HD width for presentation-grade video streaming
    if W > VIDEO_MAX_W:
        scale = VIDEO_MAX_W / W
        out_w, out_h = VIDEO_MAX_W, int(H * scale)
    else:
        out_w, out_h = W, H

    frame_delay = 1.0 / FPS
    pipeline    = RoadSensePipeline(frame_width=out_w, frame_height=out_h)

    # ── Per-session accumulators ──────────────────────────────────────────────
    fps_smooth   = 0.0
    frame_idx    = 0
    chaos_list   : list = []
    fps_list     : list = []
    peak_risk    = "LOW"
    det_counts   : dict = defaultdict(int)
    # DB session
    db_session_id: Optional[int] = None

    async with AsyncSessionLocal() as db:
        db_sess = await crud.create_session(db, video_name, source_type="file")
        db_session_id = db_sess.id
        await db.commit()

    try:
        async with AsyncSessionLocal() as db:
            stream_start_time = time.time()
            total_frames      = int(cap.get(cv2.CAP_PROP_FRAME_COUNT)) or 999999
            
            while cap.isOpened():
                t0 = time.time()

                # Calculate when the current frame should be sent to play at original speed
                expected_send_time = stream_start_time + (frame_idx * frame_delay)
                now = time.time()

                if now < expected_send_time:
                    # We are ahead of schedule, sleep to regulate the speed
                    await asyncio.sleep(expected_send_time - now)
                elif now > expected_send_time + 0.1:
                    # We are lagging behind, calculate how many frames to skip to catch up
                    lag_sec = now - expected_send_time
                    skip_count = int(lag_sec * FPS)
                    # Clamp max skipped frames to avoid skipping the entire video at once
                    skip_count = min(skip_count, 12)
                    
                    for _ in range(skip_count):
                        if not cap.grab():
                            break
                        frame_idx += 1

                if frame_idx >= total_frames:
                    break

                ret, frame = cap.read()
                if not ret:
                    break
                frame_idx += 1

                if W > VIDEO_MAX_W:
                    frame = cv2.resize(frame, (out_w, out_h), interpolation=cv2.INTER_LINEAR)

                # Detect 1-in-3 frames, track-only for the rest.
                # Parallel YOLO (3 models concurrently) + DeepSORT prediction handles gaps cleanly.
                skip_detection = (frame_idx > 1) and (frame_idx % 3 != 1)

                result  = await asyncio.to_thread(pipeline.process_frame, frame, skip_detection)
                tracked = result["tracked"]
                risks   = result["risks"]
                chaos   = result["chaos"]
                alerts  = result["alerts"]

                # ── Accumulate stats ──────────────────────────────────────────
                chaos_list.append(chaos.score)
                fps_list.append(fps_smooth)
                for obj in tracked:
                    det_counts[obj.label] += 1
                for a in alerts:
                    ad = a.to_dict() if hasattr(a, "to_dict") else a
                    lvl = ad.get("risk_level", "LOW")
                    if RISK_RANK.get(lvl, 0) > RISK_RANK.get(peak_risk, 0):
                        peak_risk = lvl

                # ── Save to DB every 5 frames ─────────────────────────────────
                if frame_idx % 5 == 0 and db_session_id:
                    await crud.save_frame_telemetry(
                        db, db_session_id, frame_idx,
                        fps_smooth, chaos.score, chaos.level,
                        len(tracked), len(alerts)
                    )
                    if tracked:
                        await crud.save_detections_bulk(
                            db, db_session_id, frame_idx, tracked, risks
                        )
                    if alerts:
                        await crud.save_alerts_bulk(
                            db, db_session_id, frame_idx, alerts
                        )
                    # Batch commits every 50 frames to reduce disk write bottlenecks
                    if frame_idx % 50 == 0:
                        await db.commit()

                # ── Draw annotations ──────────────────────────────────────────
                annotated    = frame
                frame_counts = defaultdict(int)
                for obj in sorted(tracked, key=lambda o: RISK_ORDER_MAP.get(o.label, 9), reverse=True):
                    draw_tracked_object(annotated, obj)
                    frame_counts[obj.label] += 1
                draw_hud(annotated, chaos, alerts, fps_smooth, frame_idx)

                _, jpeg_buf = cv2.imencode(
                    '.jpg', annotated,
                    [cv2.IMWRITE_JPEG_QUALITY, 70]   # Quality 70 balances crispness and network bandwidth
                )
                jpeg_bytes = jpeg_buf.tobytes()

                telemetry = {
                    "frame_id":   frame_idx,
                    "fps":        round(fps_smooth, 1),
                    "source_fps": round(FPS, 3),          # true video FPS for client-side timing
                    "session_id": db_session_id,
                    "chaos":      chaos.to_dict(),
                    "alerts":     [a.to_dict() for a in alerts],
                    "tracked":    [_tracked_to_dict(o) for o in tracked],
                    "counts":     dict(frame_counts),
                }

                await websocket.send_text(json.dumps(telemetry))
                await websocket.send_bytes(jpeg_bytes)

                elapsed    = time.time() - t0
                fps_smooth = 0.8 * fps_smooth + 0.2 * (1.0 / max(elapsed, 1e-4))

            # ── Close session in DB ───────────────────────────────────────────
            if db_session_id:
                await db.commit()  # commit any remaining frame records first
                await crud.close_session(
                    db, db_session_id,
                    total_frames     = frame_idx,
                    avg_fps          = float(np.mean(fps_list)) if fps_list else 0.0,
                    avg_chaos        = float(np.mean(chaos_list)) if chaos_list else 0.0,
                    max_chaos        = float(max(chaos_list)) if chaos_list else 0.0,
                    peak_risk        = peak_risk,
                    detection_counts = dict(det_counts),
                )
                await db.commit()

    except WebSocketDisconnect:
        print(f"[Stream] Client disconnected from '{video_name}'")
        # Still close the session with what we have
        if db_session_id:
            async with AsyncSessionLocal() as db:
                await crud.close_session(
                    db, db_session_id,
                    total_frames     = frame_idx,
                    avg_fps          = float(np.mean(fps_list)) if fps_list else 0.0,
                    avg_chaos        = float(np.mean(chaos_list)) if chaos_list else 0.0,
                    max_chaos        = float(max(chaos_list)) if chaos_list else 0.0,
                    peak_risk        = peak_risk,
                    detection_counts = dict(det_counts),
                )
                await db.commit()
    except Exception as e:
        print(f"[Stream] Error: {e}")
    finally:
        cap.release()
        try:
            await websocket.close()
        except Exception:
            pass


# ── Live Camera WebSocket ─────────────────────────────────────────────────────
camera_pipeline = None
_camera_lock    = asyncio.Lock()
CAMERA_MAX_W    = 416    # ↓ from 640 — matches video stream resolution


def _camera_process_to_telemetry(pipeline, frame, frame_idx, fps_smooth):
    H, W = frame.shape[:2]
    if W > CAMERA_MAX_W:
        scale = CAMERA_MAX_W / W
        frame = cv2.resize(frame, (CAMERA_MAX_W, int(H * scale)), interpolation=cv2.INTER_LINEAR)
        H, W  = frame.shape[:2]
    try:
        result = pipeline.process_frame(frame)
    except Exception as exc:
        print(f"[Camera] Pipeline error: {exc}")
        return None, fps_smooth

    tracked = result["tracked"]
    chaos   = result["chaos"]
    alerts  = result["alerts"]

    frame_counts = defaultdict(int)
    for obj in tracked:
        frame_counts[obj.label] += 1

    telemetry = {
        "frame_id": frame_idx,
        "fps":      round(fps_smooth, 1),
        "chaos":    chaos.to_dict(),
        "alerts":   [a.to_dict() for a in alerts],
        "tracked":  [_tracked_to_dict(o) for o in tracked],
        "counts":   dict(frame_counts),
    }
    return telemetry, fps_smooth


@app.websocket("/ws/camera")
async def websocket_camera(websocket: WebSocket):
    """
    Receives live camera frames from the browser.
    Saves the processed video session to the DB and records it as an output video.
    Returns telemetry JSON back to the client.
    """
    global camera_pipeline
    await websocket.accept()
    print("[Camera] Live camera WebSocket connected")

    async with AsyncSessionLocal() as db:
        # ── Database Session Init ─────────────────────────────────────────────
        db_sess = await crud.create_session(db, "Live Camera Run", source_type="camera")
        db_session_id = db_sess.id
        await db.commit()

        fps_smooth   = 0.0
        frame_idx    = 0
        chaos_list   : list = []
        fps_list     : list = []
        peak_risk    = "LOW"
        det_counts   : dict = defaultdict(int)
        vwriter      = None

        # Latest frame storage and connection state
        latest_frame = None
        disconnect = False

        async def receive_loop():
            nonlocal latest_frame, disconnect
            try:
                while True:
                    raw_bytes = await websocket.receive_bytes()
                    np_arr = np.frombuffer(raw_bytes, dtype=np.uint8)
                    frame  = cv2.imdecode(np_arr, cv2.IMREAD_COLOR)
                    if frame is not None:
                        latest_frame = frame
            except WebSocketDisconnect:
                disconnect = True
            except asyncio.CancelledError:
                pass   # normal shutdown — task was cancelled by the finally block
            except Exception as e:
                print(f"[Camera] Receive error: {e}")
                disconnect = True

        receive_task = asyncio.create_task(receive_loop())

        try:
            while not disconnect:
                if latest_frame is None:
                    await asyncio.sleep(0.005)
                    continue

                # Consume the latest frame
                frame = latest_frame
                latest_frame = None
                t0 = time.time()

                H, W = frame.shape[:2]
                if W > CAMERA_MAX_W:
                    scale = CAMERA_MAX_W / W
                    frame = cv2.resize(frame, (CAMERA_MAX_W, int(H * scale)), interpolation=cv2.INTER_LINEAR)
                    H, W  = frame.shape[:2]

                # ── Initialize pipeline & VideoWriter on first frame ──────────
                async with _camera_lock:
                    if camera_pipeline is None:
                        camera_pipeline = RoadSensePipeline(frame_width=W, frame_height=H)
                        print("[Camera] Pipeline initialized")

                if vwriter is None:
                    vwriter = VideoWriter(
                        input_path="live_camera.mp4",
                        frame_width=W,
                        frame_height=H,
                        fps=15.0,
                        skip=0
                    )
                    vwriter.open()

                frame_idx += 1

                # Skip detection on 2 out of 3 frames to boost FPS and reduce CPU load
                skip_detection = (frame_idx > 1) and (frame_idx % 3 != 1)

                # Process frame on background thread
                result = await asyncio.to_thread(camera_pipeline.process_frame, frame, skip_detection)
                tracked = result["tracked"]
                risks   = result["risks"]
                chaos   = result["chaos"]
                alerts  = result["alerts"]

                # ── Accumulate stats ──────────────────────────────────────────
                chaos_list.append(chaos.score)
                fps_list.append(fps_smooth)
                for obj in tracked:
                    det_counts[obj.label] += 1
                for a in alerts:
                    ad = a.to_dict() if hasattr(a, "to_dict") else a
                    lvl = ad.get("risk_level", "LOW")
                    if RISK_RANK.get(lvl, 0) > RISK_RANK.get(peak_risk, 0):
                        peak_risk = lvl

                # ── Save to DB every 5 frames ─────────────────────────────────
                if frame_idx % 5 == 0 and db_session_id:
                    await crud.save_frame_telemetry(
                        db, db_session_id, frame_idx,
                        fps_smooth, chaos.score, chaos.level,
                        len(tracked), len(alerts)
                    )
                    if tracked:
                        await crud.save_detections_bulk(
                            db, db_session_id, frame_idx, tracked, risks
                        )
                    if alerts:
                        await crud.save_alerts_bulk(
                            db, db_session_id, frame_idx, alerts
                        )
                    # Batch commits every 50 frames to prevent disk write bottlenecks
                    if frame_idx % 50 == 0:
                        await db.commit()

                # ── Draw and write to output video ────────────────────────────
                if vwriter:
                    annotated = frame.copy()
                    frame_counts = defaultdict(int)
                    for obj in sorted(tracked, key=lambda o: RISK_ORDER_MAP.get(o.label, 9), reverse=True):
                        draw_tracked_object(annotated, obj)
                        frame_counts[obj.label] += 1
                    draw_hud(annotated, chaos, alerts, fps_smooth, frame_idx)
                    vwriter.write(annotated)
                else:
                    frame_counts = defaultdict(int)
                    for obj in tracked:
                        frame_counts[obj.label] += 1

                # ── Return Telemetry to Client ────────────────────────────────
                telemetry = {
                    "frame_id":   frame_idx,
                    "fps":        round(fps_smooth, 1),
                    "session_id": db_session_id,
                    "chaos":      chaos.to_dict(),
                    "alerts":     [a.to_dict() for a in alerts],
                    "tracked":    [_tracked_to_dict(o) for o in tracked],
                    "counts":     dict(frame_counts),
                }
                await websocket.send_text(json.dumps(telemetry))

                elapsed    = time.time() - t0
                fps_smooth = 0.8 * fps_smooth + 0.2 * (1.0 / max(elapsed, 1e-4))

        except WebSocketDisconnect:
            print("[Camera] Client disconnected")
        except Exception as e:
            print(f"[Camera] Error: {e}")
        finally:
            receive_task.cancel()
            try:
                await receive_task
            except (asyncio.CancelledError, Exception):
                # CancelledError is BaseException in Python 3.8+ — catch it explicitly
                pass

            # Close DB session
            if db_session_id:
                await db.commit()  # Commit outstanding frame data first
                await crud.close_session(
                    db, db_session_id,
                    total_frames     = frame_idx,
                    avg_fps          = float(np.mean(fps_list)) if fps_list else 0.0,
                    avg_chaos        = float(np.mean(chaos_list)) if chaos_list else 0.0,
                    max_chaos        = float(max(chaos_list)) if chaos_list else 0.0,
                    peak_risk        = peak_risk,
                    detection_counts = dict(det_counts),
                )
                await db.commit()
        # Save output video
        if vwriter:
            vwriter.close()
        try:
            await websocket.close()
        except Exception:
            pass


# ── Mount Static Files ────────────────────────────────────────────────────────
app.mount("/static", StaticFiles(directory=static_path), name="static")


# ── CLI Runner ────────────────────────────────────────────────────────────────
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

    pipeline = RoadSensePipeline(frame_width=W, frame_height=H)
    vwriter  = None
    if save:
        vwriter = VideoWriter(
            input_path=video_path, frame_width=W, frame_height=H, fps=FPS, skip=skip
        )
        vwriter.open()

    fps_smooth = 0.0
    frame_idx  = processed = 0

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
            result   = pipeline.process_frame(frame)
            tracked  = result["tracked"]
            risks    = result["risks"]
            chaos    = result["chaos"]
            alerts   = result["alerts"]
            fps_smooth = 0.8 * fps_smooth + 0.2 * (1.0 / max(time.time() - t0, 1e-4))

            annotated    = frame.copy()
            frame_counts = defaultdict(int)
            for obj in sorted(tracked, key=lambda o: RISK_ORDER_MAP.get(o.label, 9), reverse=True):
                draw_tracked_object(annotated, obj)
                frame_counts[obj.label] += 1
            draw_hud(annotated, chaos, alerts, fps_smooth, frame_idx)

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

    print(f"\n{'='*62}")
    print(f"  RoadSense AI — Complete")
    print(f"  Frames processed: {processed}")
    if summary:
        print(f"  Output → {summary.get('output_video', 'N/A')}")
    print(f"{'='*62}\n")


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="RoadSense AI")
    parser.add_argument("--video", required=True)
    parser.add_argument("--save",  action="store_true")
    parser.add_argument("--skip",  type=int, default=1)
    args = parser.parse_args()
    run(args.video, args.save, args.skip)