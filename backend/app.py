"""
app.py — FastAPI backend for RoadSense AI

Endpoints:
  POST /process-video   — upload video, returns full JSON analysis
  GET  /stream/{job_id} — SSE stream of per-frame results
  POST /process-frame   — send a single base64 frame, get instant result
  GET  /health          — health check
"""

import os
import cv2
import uuid
import base64
import asyncio
import numpy as np
from pathlib import Path
from typing import Optional
from fastapi import FastAPI, File, UploadFile, HTTPException, BackgroundTasks
from fastapi.responses import JSONResponse, StreamingResponse
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel

from detectors.yolo_detector import Detector
from trackers.deepsort_tracker import Tracker
from analytics.risk_engine import RiskEngine
from analytics.chaos_score import ChaosScoreEngine
from explainability.llm_alerts import ExplainabilityEngine


# ─── App setup ────────────────────────────────────────────────────────────────

app = FastAPI(title="RoadSense AI Backend", version="1.0.0")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)

# ─── Pipeline singleton ───────────────────────────────────────────────────────

detector     = Detector(model_path="yolov8n.pt", conf_threshold=0.4)
tracker      = Tracker(max_age=30, n_init=3)
risk_engine  = RiskEngine()
chaos_engine = ChaosScoreEngine()
explainer    = ExplainabilityEngine(
    use_llm=bool(os.getenv("GROQ_API_KEY")),
    groq_api_key=os.getenv("GROQ_API_KEY"),
)

# In-memory job store
jobs: dict = {}


# ─── Models ──────────────────────────────────────────────────────────────────

class FrameRequest(BaseModel):
    frame_b64: str   # base64-encoded JPEG/PNG
    frame_id: Optional[int] = 0


# ─── Routes ──────────────────────────────────────────────────────────────────

@app.get("/health")
def health():
    return {"status": "ok", "model": "yolov8n", "llm": bool(os.getenv("GROQ_API_KEY"))}


@app.post("/process-frame")
async def process_frame(req: FrameRequest):
    """
    Process a single base64-encoded frame.
    Returns detections, risks, chaos score, and ADAS alerts.
    """
    try:
        img_bytes = base64.b64decode(req.frame_b64)
        nparr = np.frombuffer(img_bytes, np.uint8)
        frame = cv2.imdecode(nparr, cv2.IMREAD_COLOR)
        if frame is None:
            raise HTTPException(status_code=400, detail="Could not decode frame")
    except Exception as e:
        raise HTTPException(status_code=400, detail=f"Frame decode error: {e}")

    h, w = frame.shape[:2]
    risk_engine.frame_width  = w
    risk_engine.frame_height = h
    chaos_engine.frame_width  = w
    chaos_engine.frame_height = h

    # Pipeline
    detections = detector.detect(frame)
    tracked    = tracker.update(detections, frame)
    risks      = risk_engine.assess(tracked)
    chaos      = chaos_engine.compute(tracked)

    centers = {obj.track_id: obj.center for obj in tracked}
    alerts  = explainer.generate_alerts(risks, chaos, centers)
    summary = explainer.summarize(alerts, chaos)

    # Annotated frame (optional)
    annotated = tracker.annotate_frame(frame, tracked)
    _, buf = cv2.imencode(".jpg", annotated, [cv2.IMWRITE_JPEG_QUALITY, 80])
    annotated_b64 = base64.b64encode(buf).decode()

    return JSONResponse({
        "frame_id":      req.frame_id,
        "object_count":  len(tracked),
        "detections":    [_obj_to_dict(o) for o in tracked],
        "risks":         [r.to_dict() for r in risks],
        "chaos":         chaos.to_dict(),
        "alerts":        [a.to_dict() for a in alerts],
        "summary":       summary,
        "annotated_frame": annotated_b64,
    })


@app.post("/process-video")
async def process_video(
    background_tasks: BackgroundTasks,
    file: UploadFile = File(...),
    skip_frames: int = 2,
):
    """
    Upload an MP4. Returns job_id; poll /job/{job_id} for results.
    """
    job_id = str(uuid.uuid4())
    tmp_path = f"/tmp/{job_id}_{file.filename}"

    with open(tmp_path, "wb") as f:
        f.write(await file.read())

    jobs[job_id] = {"status": "queued", "progress": 0, "results": []}
    background_tasks.add_task(_process_video_job, job_id, tmp_path, skip_frames)

    return {"job_id": job_id, "status": "queued"}


@app.get("/job/{job_id}")
def get_job(job_id: str):
    job = jobs.get(job_id)
    if not job:
        raise HTTPException(status_code=404, detail="Job not found")
    return job


@app.get("/stream/{job_id}")
async def stream_job(job_id: str):
    """Server-Sent Events stream of frame results for a video job."""
    async def event_generator():
        last_sent = 0
        while True:
            job = jobs.get(job_id)
            if not job:
                yield f"data: {{'error': 'job not found'}}\n\n"
                return
            results = job.get("results", [])
            for i in range(last_sent, len(results)):
                yield f"data: {results[i]}\n\n"
                last_sent = i + 1
            if job.get("status") == "done":
                yield "data: {\"status\": \"done\"}\n\n"
                return
            await asyncio.sleep(0.1)

    return StreamingResponse(event_generator(), media_type="text/event-stream")


# ─── Background job ──────────────────────────────────────────────────────────

def _process_video_job(job_id: str, video_path: str, skip_frames: int):
    import json

    jobs[job_id]["status"] = "processing"
    cap = cv2.VideoCapture(video_path)
    total = int(cap.get(cv2.CAP_PROP_FRAME_COUNT))
    frame_idx = 0
    processed = 0

    # Reset tracker for fresh video
    local_tracker  = Tracker(max_age=30, n_init=3)
    local_risk     = RiskEngine()
    local_chaos    = ChaosScoreEngine()
    local_detector = Detector("yolov8n.pt")

    while cap.isOpened():
        ret, frame = cap.read()
        if not ret:
            break

        frame_idx += 1
        if frame_idx % (skip_frames + 1) != 0:
            continue

        h, w = frame.shape[:2]
        local_risk.frame_width  = w
        local_risk.frame_height = h
        local_chaos.frame_width  = w
        local_chaos.frame_height = h

        detections = local_detector.detect(frame)
        tracked    = local_tracker.update(detections, frame)
        risks      = local_risk.assess(tracked)
        chaos      = local_chaos.compute(tracked)
        centers    = {o.track_id: o.center for o in tracked}
        alerts     = explainer.generate_alerts(risks, chaos, centers)
        summary    = explainer.summarize(alerts, chaos)

        result = json.dumps({
            "frame_id":     frame_idx,
            "object_count": len(tracked),
            "chaos":        chaos.to_dict(),
            "risks":        [r.to_dict() for r in risks],
            "alerts":       [a.to_dict() for a in alerts],
            "summary":      summary,
        })

        jobs[job_id]["results"].append(result)
        jobs[job_id]["progress"] = round(frame_idx / max(total, 1) * 100, 1)
        processed += 1

    cap.release()
    os.remove(video_path)
    jobs[job_id]["status"]    = "done"
    jobs[job_id]["progress"]  = 100
    jobs[job_id]["total_frames_processed"] = processed
    print(f"[Job {job_id}] Done — {processed} frames processed")


# ─── Helpers ─────────────────────────────────────────────────────────────────

def _obj_to_dict(obj) -> dict:
    return {
        "track_id":  obj.track_id,
        "label":     obj.label,
        "bbox":      [round(v, 1) for v in obj.bbox],
        "center":    [round(v, 1) for v in obj.center],
        "speed":     round(obj.speed, 2),
        "direction": round(obj.direction, 1),
        "velocity":  [round(v, 2) for v in obj.velocity],
        "age":       obj.age,
    }


if __name__ == "__main__":
    import uvicorn
    uvicorn.run("app:app", host="0.0.0.0", port=8000, reload=True)