"""
database/models.py — SQLAlchemy ORM models for RoadSense AI

Tables:
  video_sessions   — one row per streaming session
  frame_telemetry  — per-frame chaos/object stats (sampled)
  detections       — each tracked object per frame
  alerts           — each generated ADAS alert
"""

import json
from datetime import datetime
from sqlalchemy import (
    Column, Integer, Float, String, Text,
    DateTime, ForeignKey, Index
)
from sqlalchemy.orm import DeclarativeBase, relationship


class Base(DeclarativeBase):
    pass


class VideoSession(Base):
    """One row per streaming/processing session."""
    __tablename__ = "video_sessions"

    id               = Column(Integer, primary_key=True, autoincrement=True)
    video_name       = Column(String(256), nullable=False, index=True)
    started_at       = Column(DateTime, default=datetime.utcnow, nullable=False)
    ended_at         = Column(DateTime, nullable=True)
    total_frames     = Column(Integer, default=0)
    avg_fps          = Column(Float, default=0.0)
    avg_chaos_score  = Column(Float, default=0.0)
    max_chaos_score  = Column(Float, default=0.0)
    peak_risk_level  = Column(String(16), default="LOW")   # LOW/MEDIUM/HIGH/CRITICAL
    # JSON blob: {"car": 42, "bus": 5, "motorcycle": 12, ...}
    detection_summary = Column(Text, default="{}")
    source_type      = Column(String(16), default="file")  # "file" or "camera"

    # Relationships
    telemetry  = relationship("FrameTelemetry", back_populates="session",
                               cascade="all, delete-orphan")
    detections = relationship("Detection",      back_populates="session",
                               cascade="all, delete-orphan")
    alerts     = relationship("Alert",          back_populates="session",
                               cascade="all, delete-orphan")

    def summary_dict(self):
        try:
            det_summary = json.loads(self.detection_summary or "{}")
        except Exception:
            det_summary = {}
        return {
            "id":               self.id,
            "video_name":       self.video_name,
            "source_type":      self.source_type,
            "started_at":       self.started_at.isoformat() if self.started_at else None,
            "ended_at":         self.ended_at.isoformat()   if self.ended_at   else None,
            "total_frames":     self.total_frames,
            "avg_fps":          round(self.avg_fps, 1),
            "avg_chaos_score":  round(self.avg_chaos_score, 1),
            "max_chaos_score":  round(self.max_chaos_score, 1),
            "peak_risk_level":  self.peak_risk_level,
            "detection_summary": det_summary,
        }


class FrameTelemetry(Base):
    """Per-frame chaos + object count — sampled every N frames to keep DB small."""
    __tablename__ = "frame_telemetry"

    id           = Column(Integer, primary_key=True, autoincrement=True)
    session_id   = Column(Integer, ForeignKey("video_sessions.id", ondelete="CASCADE"),
                          nullable=False, index=True)
    frame_id     = Column(Integer, nullable=False)
    timestamp    = Column(DateTime, default=datetime.utcnow)
    fps          = Column(Float, default=0.0)
    chaos_score  = Column(Float, default=0.0)
    chaos_level  = Column(String(16), default="Calm")
    object_count = Column(Integer, default=0)
    alert_count  = Column(Integer, default=0)

    session = relationship("VideoSession", back_populates="telemetry")

    __table_args__ = (
        Index("ix_frame_telemetry_session_frame", "session_id", "frame_id"),
    )

    def to_dict(self):
        return {
            "frame_id":     self.frame_id,
            "timestamp":    self.timestamp.isoformat() if self.timestamp else None,
            "fps":          round(self.fps, 1),
            "chaos_score":  round(self.chaos_score, 1),
            "chaos_level":  self.chaos_level,
            "object_count": self.object_count,
            "alert_count":  self.alert_count,
        }


class Detection(Base):
    """Each tracked object snapshot per sampled frame."""
    __tablename__ = "detections"

    id         = Column(Integer, primary_key=True, autoincrement=True)
    session_id = Column(Integer, ForeignKey("video_sessions.id", ondelete="CASCADE"),
                        nullable=False, index=True)
    frame_id   = Column(Integer, nullable=False)
    track_id   = Column(Integer, nullable=False)
    label      = Column(String(64), nullable=False, index=True)
    conf       = Column(Float, default=0.0)
    speed      = Column(Float, default=0.0)
    cx         = Column(Float, default=0.0)
    cy         = Column(Float, default=0.0)
    risk_level = Column(String(16), default="LOW")

    session = relationship("VideoSession", back_populates="detections")

    def to_dict(self):
        return {
            "frame_id":   self.frame_id,
            "track_id":   self.track_id,
            "label":      self.label,
            "conf":       round(self.conf, 2),
            "speed":      round(self.speed, 2),
            "cx":         round(self.cx, 1),
            "cy":         round(self.cy, 1),
            "risk_level": self.risk_level,
        }


class Alert(Base):
    """Every ADAS alert generated during a session."""
    __tablename__ = "alerts"

    id         = Column(Integer, primary_key=True, autoincrement=True)
    session_id = Column(Integer, ForeignKey("video_sessions.id", ondelete="CASCADE"),
                        nullable=False, index=True)
    frame_id   = Column(Integer, nullable=False)
    track_id   = Column(Integer, nullable=False)
    label      = Column(String(64))
    risk_type  = Column(String(64))
    risk_level = Column(String(16), index=True)
    risk_score = Column(Float, default=0.0)
    message    = Column(Text, default="")

    session = relationship("VideoSession", back_populates="alerts")

    def to_dict(self):
        return {
            "frame_id":   self.frame_id,
            "track_id":   self.track_id,
            "label":      self.label,
            "risk_type":  self.risk_type,
            "risk_level": self.risk_level,
            "risk_score": round(self.risk_score, 2),
            "message":    self.message,
        }
