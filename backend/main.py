"""
main.py — RoadSense AI FastAPI Backend

Endpoints:
  GET  /                        → health check
  GET  /api/videos              → list available videos
  GET  /api/videos/{name}/info  → video metadata
  POST /api/process             → process a video file, return analytics JSON
  GET  /api/stream/{name}       → MJPEG stream of annotated video (SSE)
  WS   /ws/stream/{name}        → WebSocket MJPEG stream
  POST /api/explain             → LLM-explain a single risk event on demand
"""

import os
import sys
import json
import asyncio
import time
from pathlib import Path
from typing import Optional, List

# ── Ensure backend/ is on sys.path so relative imports work ──────────────────
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

import cv2
import numpy as np

from fastapi import FastAPI, WebSocket, WebSocketDisconnect, HTTPException, Query
from fastapi.responses import StreamingResponse, JSONResponse
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel

from config import (
    VIDEOS_DIR, OUTPUTS_DIR,
    YOLO_MODEL, YOLO_CONFIDENCE,
    FRAME_SKIP, OUTPUT_FPS, OUTPUT_RESOLUTION,
    GROQ_API_KEY, GROQ_MODEL,
    DEEPSORT_MAX_AGE, DEEPSORT_N_INIT,
)
from services.video_processor import VideoProcessor
from services.video_writer import VideoWriter
from utils.drawing import frame_to_jpeg

# ─────────────────────────────────────────────────────────────────────────────
# App setup
# ─────────────────────────────────────────────────────────────────────────────

app = FastAPI(
    title="RoadSense AI",
    description="Context-Aware Explainable ADAS for Indian Traffic",
    version="1.0.0",
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)

# Resolve video directory (handles the ../videos relative path in config)
VIDEOS_PATH = Path(VIDEOS_DIR).resolve()
OUTPUTS_PATH = Path(OUTPUTS_DIR).resolve()
OUTPUTS_PATH.mkdir(parents=True, exist_ok=True)

# Singleton processor (lazy init)
_processor: Optional[VideoProcessor] = None


def get_processor(use_llm: bool = True) -> VideoProcessor:
    global _processor
    if _processor is None:
        _processor = VideoProcessor(
            model_path=YOLO_MODEL,
            conf_threshold=YOLO_CONFIDENCE,
            frame_skip=FRAME_SKIP,
            output_resolution=OUTPUT_RESOLUTION,
            use_llm=use_llm,
            groq_api_key=GROQ_API_KEY,
        )
    return _processor


# ─────────────────────────────────────────────────────────────────────────────
# Request / Response Models
# ─────────────────────────────────────────────────────────────────────────────

class ProcessRequest(BaseModel):
    video_name: str
    use_llm: bool = True
    save_output: bool = False
    max_frames: int = 0          # 0 = process all frames


class ExplainRequest(BaseModel):
    label: str
    risk_type: str
    risk_level: str
    risk_score: float
    speed: float
    chaos_level: str
    chaos_score: float
    side: str = "front"


# ─────────────────────────────────────────────────────────────────────────────
# Routes
# ─────────────────────────────────────────────────────────────────────────────

@app.get("/", tags=["Health"])
def root():
    return {
        "service": "RoadSense AI",
        "status": "running",
        "version": "1.0.0",
        "description": "Context-Aware Explainable ADAS for Indian Traffic",
    }


@app.get("/api/videos", tags=["Videos"])
def list_videos():
    """List all .mp4 videos in the videos directory."""
    if not VIDEOS_PATH.exists():
        raise HTTPException(status_code=404, detail=f"Videos directory not found: {VIDEOS_PATH}")

    videos = []
    for f in sorted(VIDEOS_PATH.glob("*.mp4")):
        cap = cv2.VideoCapture(str(f))
        info = {
            "name":     f.name,
            "stem":     f.stem,
            "size_mb":  round(f.stat().st_size / 1_048_576, 1),
            "fps":      cap.get(cv2.CAP_PROP_FPS),
            "frames":   int(cap.get(cv2.CAP_PROP_FRAME_COUNT)),
            "width":    int(cap.get(cv2.CAP_PROP_FRAME_WIDTH)),
            "height":   int(cap.get(cv2.CAP_PROP_FRAME_HEIGHT)),
        }
        duration = info["frames"] / info["fps"] if info["fps"] > 0 else 0
        info["duration_s"] = round(duration, 1)
        cap.release()
        videos.append(info)

    return {"videos": videos, "count": len(videos)}


@app.get("/api/videos/{video_name}/info", tags=["Videos"])
def video_info(video_name: str):
    """Return metadata for a specific video."""
    path = VIDEOS_PATH / video_name
    if not path.exists():
        raise HTTPException(status_code=404, detail=f"Video not found: {video_name}")

    cap = cv2.VideoCapture(str(path))
    fps     = cap.get(cv2.CAP_PROP_FPS)
    frames  = int(cap.get(cv2.CAP_PROP_FRAME_COUNT))
    width   = int(cap.get(cv2.CAP_PROP_FRAME_WIDTH))
    height  = int(cap.get(cv2.CAP_PROP_FRAME_HEIGHT))
    cap.release()

    return {
        "name":       video_name,
        "size_mb":    round(path.stat().st_size / 1_048_576, 1),
        "fps":        fps,
        "frames":     frames,
        "width":      width,
        "height":     height,
        "duration_s": round(frames / fps, 1) if fps > 0 else 0,
    }


@app.post("/api/process", tags=["Processing"])
def process_video(req: ProcessRequest):
    """
    Process a video file end-to-end and return aggregated analytics.
    For long videos use /api/stream instead.
    """
    path = VIDEOS_PATH / req.video_name
    if not path.exists():
        raise HTTPException(status_code=404, detail=f"Video not found: {req.video_name}")

    processor = get_processor(use_llm=req.use_llm)

    all_chaos   = []
    all_risks   = []
    all_alerts  = []
    frame_count = 0
    total_objects = 0

    output_writer: Optional[VideoWriter] = None
    if req.save_output:
        out_path = str(OUTPUTS_PATH / f"processed_{req.video_name}")
        output_writer = VideoWriter(out_path, fps=OUTPUT_FPS, resolution=OUTPUT_RESOLUTION)
        output_writer.open()

    try:
        for result in processor.process_file(str(path)):
            frame_count += 1
            total_objects += len(result.tracked_objects)
            all_chaos.append(result.chaos.score)
            all_risks.extend([r.to_dict() for r in result.risk_events])
            all_alerts.extend([a.to_dict() for a in result.alerts])

            if output_writer:
                output_writer.write(result.annotated_frame)

            if req.max_frames > 0 and frame_count >= req.max_frames:
                break
    finally:
        if output_writer:
            output_writer.close()

    # Aggregate stats
    avg_chaos = sum(all_chaos) / len(all_chaos) if all_chaos else 0
    risk_counts = {"LOW": 0, "MEDIUM": 0, "HIGH": 0, "CRITICAL": 0}
    for r in all_risks:
        lvl = r.get("risk_level", "LOW")
        risk_counts[lvl] = risk_counts.get(lvl, 0) + 1

    return {
        "video":          req.video_name,
        "frames_processed": frame_count,
        "total_objects_detected": total_objects,
        "avg_chaos_score": round(avg_chaos, 1),
        "peak_chaos_score": round(max(all_chaos), 1) if all_chaos else 0,
        "risk_distribution": risk_counts,
        "total_alerts": len(all_alerts),
        "sample_alerts": all_alerts[:10],
        "output_saved": req.save_output,
    }


@app.get("/api/stream/{video_name}", tags=["Streaming"])
async def stream_mjpeg(
    video_name: str,
    use_llm: bool = Query(True),
):
    """
    MJPEG streaming endpoint. Open in browser or connect via <img> tag.
    Content-Type: multipart/x-mixed-replace
    """
    path = VIDEOS_PATH / video_name
    if not path.exists():
        raise HTTPException(status_code=404, detail=f"Video not found: {video_name}")

    processor = get_processor(use_llm=use_llm)

    async def generate():
        boundary = b"--frame\r\nContent-Type: image/jpeg\r\n\r\n"
        async for jpeg_bytes in processor.stream_file(str(path)):
            yield boundary + jpeg_bytes + b"\r\n"

    return StreamingResponse(
        generate(),
        media_type="multipart/x-mixed-replace; boundary=frame",
    )


@app.websocket("/ws/stream/{video_name}")
async def websocket_stream(websocket: WebSocket, video_name: str):
    """
    WebSocket endpoint — sends raw JPEG bytes per frame.
    Client receives binary messages with JPEG data.
    Analytics JSON is sent as text messages interleaved.
    """
    await websocket.accept()

    path = VIDEOS_PATH / video_name
    if not path.exists():
        await websocket.send_text(json.dumps({"error": f"Video not found: {video_name}"}))
        await websocket.close()
        return

    processor = get_processor(use_llm=True)

    try:
        loop = asyncio.get_event_loop()
        cap  = cv2.VideoCapture(str(path))
        if not cap.isOpened():
            await websocket.send_text(json.dumps({"error": "Cannot open video"}))
            await websocket.close()
            return

        raw_idx = 0
        while True:
            ret, frame = await loop.run_in_executor(None, cap.read)
            if not ret:
                break
            raw_idx += 1
            if raw_idx % FRAME_SKIP != 0:
                continue

            result = await loop.run_in_executor(None, processor._process_frame, frame)
            if result is None:
                continue

            # Send JPEG frame
            jpeg = frame_to_jpeg(result.annotated_frame)
            await websocket.send_bytes(jpeg)

            # Send analytics JSON (interleaved as text)
            await websocket.send_text(json.dumps(result.to_dict()))

            await asyncio.sleep(0.01)   # ~slight pacing

        cap.release()
        await websocket.send_text(json.dumps({"event": "stream_end"}))

    except WebSocketDisconnect:
        print(f"[WS] Client disconnected from {video_name}")
    except Exception as e:
        print(f"[WS] Error: {e}")
        try:
            await websocket.send_text(json.dumps({"error": str(e)}))
        except Exception:
            pass
    finally:
        try:
            await websocket.close()
        except Exception:
            pass


@app.post("/api/explain", tags=["Explainability"])
async def explain_risk(req: ExplainRequest):
    """
    On-demand LLM explanation for a risk event.
    Uses Groq + LLaMA3 to generate a natural-language ADAS warning.
    """
    if not GROQ_API_KEY:
        raise HTTPException(status_code=503, detail="GROQ_API_KEY not configured")

    try:
        from groq import Groq
        client = Groq(api_key=GROQ_API_KEY)

        prompt = f"""You are an expert ADAS warning system for Indian roads.
Generate a concise, actionable safety warning (max 2 sentences) in plain English.

Situation:
- Object detected: {req.label}
- Risk type: {req.risk_type}
- Severity: {req.risk_level} (score: {req.risk_score:.2f})
- Object position: {req.side} side
- Object speed: {req.speed:.1f} px/frame
- Traffic chaos: {req.chaos_level} ({req.chaos_score:.0f}/100)

Respond ONLY as JSON (no markdown):
{{"message": "<ADAS warning text>", "action": "<driver action>", "urgency": "<LOW|MEDIUM|HIGH|CRITICAL>"}}
"""
        response = client.chat.completions.create(
            model=GROQ_MODEL,
            messages=[{"role": "user", "content": prompt}],
            max_tokens=150,
            temperature=0.3,
        )
        text = response.choices[0].message.content.strip()
        text = text.replace("```json", "").replace("```", "").strip()
        parsed = json.loads(text)
        return {"source": "llm", "model": GROQ_MODEL, **parsed}

    except Exception as e:
        raise HTTPException(status_code=500, detail=f"LLM call failed: {str(e)}")


@app.get("/api/chaos/levels", tags=["Reference"])
def chaos_levels():
    """Return chaos score level reference."""
    return {
        "levels": [
            {"range": "0–30",   "label": "Calm",     "description": "Light traffic, predictable flow"},
            {"range": "31–60",  "label": "Moderate", "description": "Mixed traffic, some unpredictability"},
            {"range": "61–100", "label": "Chaotic",  "description": "Dense mixed traffic, high unpredictability"},
        ],
        "formula": {
            "vehicle_density":    "0.30",
            "speed_variance":     "0.20",
            "lane_intrusions":    "0.30",
            "pedestrian_density": "0.20",
        }
    }


@app.get("/api/risk/types", tags=["Reference"])
def risk_types():
    """Return all supported risk types and levels."""
    return {
        "risk_types": [
            "lane_cut", "collision", "pedestrian_crossing",
            "tailgating", "blind_spot", "sudden_brake", "general"
        ],
        "risk_levels": ["LOW", "MEDIUM", "HIGH", "CRITICAL"],
    }


# ─────────────────────────────────────────────────────────────────────────────
# Entry point (for direct python execution)
# ─────────────────────────────────────────────────────────────────────────────

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(
        "main:app",
        host="0.0.0.0",
        port=8000,
        reload=False,
        workers=1,
    )
