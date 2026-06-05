"""
drawing.py — OpenCV annotation utilities for RoadSense AI
Draws bounding boxes, trajectory tails, HUD overlay, chaos bar, and alert strip.
"""

import cv2
import numpy as np
from typing import List, Optional

FONT      = cv2.FONT_HERSHEY_SIMPLEX
FONT_BOLD = cv2.FONT_HERSHEY_DUPLEX

# Colour palette per label
LABEL_COLORS = {
    "pedestrian": (0, 255, 255),
    "bicycle":    (255, 165, 0),
    "car":        (0, 255, 0),
    "motorcycle": (255, 0, 255),
    "bus":        (0, 0, 255),
    "truck":      (128, 0, 200),
    "vehicle":    (200, 200, 200),
}

# Risk level → box border colour
RISK_COLORS = {
    "LOW":      (0, 200, 0),
    "MEDIUM":   (0, 165, 255),
    "HIGH":     (0, 80, 255),
    "CRITICAL": (0, 0, 255),
}


def draw_tracked_objects(frame: np.ndarray, tracked_objects, risk_map: dict = None) -> np.ndarray:
    """
    Draw bounding boxes + trajectory tails for every tracked object.
    risk_map: track_id → risk_level string
    """
    out = frame.copy()
    risk_map = risk_map or {}

    for obj in tracked_objects:
        x1, y1, x2, y2 = [int(v) for v in obj.bbox]
        label_color = LABEL_COLORS.get(obj.label, (200, 200, 200))
        risk_level  = risk_map.get(obj.track_id, "LOW")
        box_color   = RISK_COLORS.get(risk_level, label_color)
        thickness   = 3 if risk_level in ("HIGH", "CRITICAL") else 2

        cv2.rectangle(out, (x1, y1), (x2, y2), box_color, thickness)

        # Trajectory tail
        pts = [(int(p[0]), int(p[1])) for p in obj.trajectory]
        for i in range(1, len(pts)):
            alpha = i / max(len(pts), 1)
            tail_color = (
                int(label_color[0] * alpha),
                int(label_color[1] * alpha),
                int(label_color[2] * alpha),
            )
            cv2.line(out, pts[i-1], pts[i], tail_color, 1)

        # Label tag
        tag = f"#{obj.track_id} {obj.label} {obj.speed:.1f}px/f"
        (tw, th), _ = cv2.getTextSize(tag, FONT, 0.45, 1)
        cv2.rectangle(out, (x1, max(y1 - th - 8, 0)), (x1 + tw + 4, max(y1, th + 4)), (0, 0, 0), -1)
        cv2.putText(out, tag, (x1 + 2, max(y1 - 4, th)), FONT, 0.45, box_color, 1, cv2.LINE_AA)

    return out


def draw_hud(
    frame: np.ndarray,
    chaos_score: float,
    chaos_level: str,
    fps: float,
    object_count: int,
    active_alerts: Optional[List[str]] = None,
) -> np.ndarray:
    """Draw semi-transparent top HUD bar and bottom alert strip."""
    h, w = frame.shape[:2]
    out  = frame.copy()

    # ── Top bar ──────────────────────────────────────────────────────────────
    overlay = out.copy()
    cv2.rectangle(overlay, (0, 0), (w, 60), (10, 10, 10), -1)
    cv2.addWeighted(overlay, 0.60, out, 0.40, 0, out)

    chaos_color = _chaos_color(chaos_score)

    # Chaos score label
    cv2.putText(out, "CHAOS SCORE", (12, 20), FONT, 0.45, (180, 180, 180), 1, cv2.LINE_AA)
    cv2.putText(out, f"{chaos_score:.0f}/100  {chaos_level.upper()}", (12, 48),
                FONT_BOLD, 0.75, chaos_color, 1, cv2.LINE_AA)

    # Chaos bar
    bar_x, bar_y, bar_w, bar_h = 240, 18, 260, 22
    cv2.rectangle(out, (bar_x, bar_y), (bar_x + bar_w, bar_y + bar_h), (50, 50, 50), -1)
    filled = int(bar_w * chaos_score / 100)
    cv2.rectangle(out, (bar_x, bar_y), (bar_x + filled, bar_y + bar_h), chaos_color, -1)
    cv2.rectangle(out, (bar_x, bar_y), (bar_x + bar_w, bar_y + bar_h), (120, 120, 120), 1)

    # FPS + object count (right side)
    cv2.putText(out, f"FPS {fps:.1f}", (w - 160, 28), FONT, 0.50, (200, 200, 200), 1, cv2.LINE_AA)
    cv2.putText(out, f"OBJ {object_count}", (w - 160, 52), FONT, 0.50, (200, 200, 200), 1, cv2.LINE_AA)

    # RoadSense AI watermark
    cv2.putText(out, "RoadSense AI", (w // 2 - 70, 38), FONT_BOLD, 0.55, (80, 180, 255), 1, cv2.LINE_AA)

    # ── Bottom alert strip ───────────────────────────────────────────────────
    if active_alerts:
        overlay2 = out.copy()
        cv2.rectangle(overlay2, (0, h - 48), (w, h), (10, 10, 10), -1)
        cv2.addWeighted(overlay2, 0.65, out, 0.35, 0, out)

        icon = "⚠ " if any(a for a in active_alerts) else ""
        alert_text = "  |  ".join(active_alerts[:3])
        display = (icon + alert_text)[:120]   # truncate long strings
        cv2.putText(out, display, (12, h - 16),
                    FONT, 0.46, (0, 220, 255), 1, cv2.LINE_AA)

    return out


def draw_risk_badge(frame: np.ndarray, risk_level: str, x: int = 520, y: int = 10) -> np.ndarray:
    """Draw a coloured risk-level badge in the top-center of the frame."""
    out = frame.copy()
    color = RISK_COLORS.get(risk_level, (0, 200, 0))
    badge_text = f" {risk_level} RISK "
    (tw, th), _ = cv2.getTextSize(badge_text, FONT_BOLD, 0.65, 1)
    cv2.rectangle(out, (x, y), (x + tw + 8, y + th + 12), color, -1)
    cv2.putText(out, badge_text, (x + 4, y + th + 6), FONT_BOLD, 0.65, (0, 0, 0), 1, cv2.LINE_AA)
    return out


def resize_frame(frame: np.ndarray, target_size=(1280, 720)) -> np.ndarray:
    return cv2.resize(frame, target_size, interpolation=cv2.INTER_LINEAR)


def frame_to_jpeg(frame: np.ndarray, quality: int = 80) -> bytes:
    """Encode frame as JPEG bytes for streaming."""
    _, buf = cv2.imencode(".jpg", frame, [cv2.IMWRITE_JPEG_QUALITY, quality])
    return buf.tobytes()


# ─── Helpers ─────────────────────────────────────────────────────────────────

def _chaos_color(score: float):
    if score <= 30:
        return (0, 220, 0)    # green
    elif score <= 60:
        return (0, 165, 255)  # orange
    else:
        return (0, 0, 255)    # red