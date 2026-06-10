"""
database/crud.py — Create/Read/Update/Delete operations for RoadSense AI DB

All functions are async and accept an AsyncSession.
"""

import json
from datetime import datetime
from typing import Optional, List, Dict, Any
from sqlalchemy import select, func, desc
from sqlalchemy.ext.asyncio import AsyncSession

from database.models import VideoSession, FrameTelemetry, Detection, Alert


# ── Session CRUD ──────────────────────────────────────────────────────────────

async def create_session(
    db: AsyncSession,
    video_name: str,
    source_type: str = "file",
) -> VideoSession:
    """Open a new video processing session."""
    session = VideoSession(
        video_name   = video_name,
        source_type  = source_type,
        started_at   = datetime.utcnow(),
    )
    db.add(session)
    await db.flush()   # get the auto-incremented ID without committing
    return session


async def close_session(
    db: AsyncSession,
    session_id: int,
    total_frames: int,
    avg_fps: float,
    avg_chaos: float,
    max_chaos: float,
    peak_risk: str,
    detection_counts: Dict[str, int],
) -> Optional[VideoSession]:
    """Mark a session as ended and write summary stats."""
    result = await db.get(VideoSession, session_id)
    if not result:
        return None
    result.ended_at          = datetime.utcnow()
    result.total_frames      = total_frames
    result.avg_fps           = round(avg_fps, 1)
    result.avg_chaos_score   = round(avg_chaos, 1)
    result.max_chaos_score   = round(max_chaos, 1)
    result.peak_risk_level   = peak_risk
    result.detection_summary = json.dumps(detection_counts)
    return result


async def list_sessions(
    db: AsyncSession,
    limit: int = 50,
    offset: int = 0,
) -> List[VideoSession]:
    """Return sessions ordered newest-first."""
    result = await db.execute(
        select(VideoSession)
        .order_by(desc(VideoSession.started_at))
        .limit(limit)
        .offset(offset)
    )
    return result.scalars().all()


async def get_session(db: AsyncSession, session_id: int) -> Optional[VideoSession]:
    return await db.get(VideoSession, session_id)


async def delete_session(db: AsyncSession, session_id: int) -> bool:
    session = await db.get(VideoSession, session_id)
    if not session:
        return False
    await db.delete(session)
    return True


# ── Telemetry CRUD ────────────────────────────────────────────────────────────

async def save_frame_telemetry(
    db: AsyncSession,
    session_id: int,
    frame_id: int,
    fps: float,
    chaos_score: float,
    chaos_level: str,
    object_count: int,
    alert_count: int,
) -> FrameTelemetry:
    row = FrameTelemetry(
        session_id   = session_id,
        frame_id     = frame_id,
        fps          = fps,
        chaos_score  = chaos_score,
        chaos_level  = chaos_level,
        object_count = object_count,
        alert_count  = alert_count,
    )
    db.add(row)
    return row


async def get_session_telemetry(
    db: AsyncSession,
    session_id: int,
) -> List[FrameTelemetry]:
    result = await db.execute(
        select(FrameTelemetry)
        .where(FrameTelemetry.session_id == session_id)
        .order_by(FrameTelemetry.frame_id)
    )
    return result.scalars().all()


# ── Detections CRUD ───────────────────────────────────────────────────────────

async def save_detections_bulk(
    db: AsyncSession,
    session_id: int,
    frame_id: int,
    tracked_objects: List[Any],
    risks: List[Any],
) -> None:
    """Bulk-insert tracked objects for a frame."""
    # Build a risk_level lookup by track_id
    risk_map: Dict[int, str] = {}
    for r in (risks or []):
        risk_map[r.track_id] = r.risk_level

    rows = [
        Detection(
            session_id = session_id,
            frame_id   = frame_id,
            track_id   = obj.track_id,
            label      = obj.label,
            conf       = float(obj.conf),
            speed      = float(obj.speed),
            cx         = float(obj.cx),
            cy         = float(obj.cy),
            risk_level = risk_map.get(obj.track_id, "LOW"),
        )
        for obj in tracked_objects
    ]
    if rows:
        db.add_all(rows)


# ── Alerts CRUD ───────────────────────────────────────────────────────────────

async def save_alerts_bulk(
    db: AsyncSession,
    session_id: int,
    frame_id: int,
    alerts: List[Any],
) -> None:
    """Bulk-insert generated ADAS alerts for a frame."""
    rows = []
    for a in (alerts or []):
        ad = a.to_dict() if hasattr(a, "to_dict") else a
        rows.append(Alert(
            session_id = session_id,
            frame_id   = frame_id,
            track_id   = ad.get("track_id", -1),
            label      = ad.get("label", ""),
            risk_type  = ad.get("risk_type", ""),
            risk_level = ad.get("risk_level", "LOW"),
            risk_score = float(ad.get("risk_score", 0.0)),
            message    = ad.get("message", ""),
        ))
    if rows:
        db.add_all(rows)


async def get_session_alerts(
    db: AsyncSession,
    session_id: int,
) -> List[Alert]:
    result = await db.execute(
        select(Alert)
        .where(Alert.session_id == session_id)
        .order_by(Alert.frame_id, desc(Alert.risk_score))
    )
    return result.scalars().all()


# ── Global Stats ──────────────────────────────────────────────────────────────

async def get_overview_stats(db: AsyncSession) -> Dict[str, Any]:
    """Aggregate stats across all sessions for the dashboard."""
    # Total sessions
    total_sessions_r = await db.execute(select(func.count(VideoSession.id)))
    total_sessions = total_sessions_r.scalar() or 0

    # Total frames processed
    total_frames_r = await db.execute(select(func.sum(VideoSession.total_frames)))
    total_frames = total_frames_r.scalar() or 0

    # Average chaos
    avg_chaos_r = await db.execute(select(func.avg(VideoSession.avg_chaos_score)))
    avg_chaos = round(float(avg_chaos_r.scalar() or 0), 1)

    # Most common peak risk level
    risk_count_r = await db.execute(
        select(VideoSession.peak_risk_level, func.count(VideoSession.peak_risk_level).label("cnt"))
        .group_by(VideoSession.peak_risk_level)
        .order_by(desc("cnt"))
        .limit(1)
    )
    top_risk_row = risk_count_r.first()
    top_risk = top_risk_row[0] if top_risk_row else "LOW"

    # Total alerts
    total_alerts_r = await db.execute(select(func.count(Alert.id)))
    total_alerts = total_alerts_r.scalar() or 0

    # Alert breakdown by risk level
    alert_breakdown_r = await db.execute(
        select(Alert.risk_level, func.count(Alert.id).label("cnt"))
        .group_by(Alert.risk_level)
    )
    alert_breakdown = {row[0]: row[1] for row in alert_breakdown_r.all()}

    # Most detected class
    det_class_r = await db.execute(
        select(Detection.label, func.count(Detection.id).label("cnt"))
        .group_by(Detection.label)
        .order_by(desc("cnt"))
        .limit(10)
    )
    top_classes = [{"label": row[0], "count": row[1]} for row in det_class_r.all()]

    return {
        "total_sessions":  total_sessions,
        "total_frames":    total_frames,
        "total_alerts":    total_alerts,
        "avg_chaos_score": avg_chaos,
        "top_risk_level":  top_risk,
        "alert_breakdown": alert_breakdown,
        "top_classes":     top_classes,
    }
