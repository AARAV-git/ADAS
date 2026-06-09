"""
utils/drawing.py — OpenCV drawing helpers for RoadSense AI
"""

import cv2
import numpy as np
from config import COLOURS, RISK_COLOURS, CHAOS_COLOURS


def draw_tracked_object(frame, obj):
    """Draw bounding box + label + trajectory tail for a tracked object."""
    x1, y1, x2, y2 = [int(v) for v in obj.bbox]
    color     = COLOURS.get(obj.label, (200, 200, 200))
    thickness = 3 if obj.label in ("vulnerable_road_user", "auto_rickshaw", "rider") else 2

    cv2.rectangle(frame, (x1, y1), (x2, y2), color, thickness)

    # Label
    SHORT = {
        "vulnerable_road_user": "VRU",
        "auto_rickshaw":        "AUTO",
        "pedestrian":           "PED",
        "motorcycle":           "MOTO",
    }
    tag = f"#{obj.track_id} {SHORT.get(obj.label, obj.label.upper())} {obj.conf:.2f}"
    (tw, th), _ = cv2.getTextSize(tag, cv2.FONT_HERSHEY_SIMPLEX, 0.48, 1)
    cv2.rectangle(frame, (x1, y1 - th - 8), (x1 + tw + 6, y1), color, -1)
    cv2.putText(frame, tag, (x1 + 3, y1 - 4),
                cv2.FONT_HERSHEY_SIMPLEX, 0.48, (0, 0, 0), 1)

    # Trajectory tail
    if hasattr(obj, "trajectory") and len(obj.trajectory) > 1:
        pts = [(int(p[0]), int(p[1])) for p in obj.trajectory[-15:]]
        for i in range(1, len(pts)):
            alpha = i / len(pts)
            c = (int(color[0]*alpha), int(color[1]*alpha), int(color[2]*alpha))
            cv2.line(frame, pts[i-1], pts[i], c, 1)

    # VRU warning ring
    if obj.label == "vulnerable_road_user":
        cx, cy = int(obj.cx), int(obj.cy)
        r = int(max(obj.w, obj.h) // 2 + 12)
        cv2.circle(frame, (cx, cy), r,     (0, 0, 255), 2)
        cv2.circle(frame, (cx, cy), r + 6, (0, 0, 255), 1)


def draw_risk_overlay(frame, risk_events):
    """Draw risk level badges next to risky objects."""
    for event in risk_events[:3]:
        color = RISK_COLOURS.get(event.risk_level, (200, 200, 200))
        # Draw a small risk badge at top-right of bbox
        if hasattr(event, "bbox") and event.bbox:
            x2 = int(event.bbox[2])
            y1 = int(event.bbox[1])
            badge = f"!{event.risk_level[:3]}"
            cv2.putText(frame, badge, (x2 - 40, y1 + 16),
                        cv2.FONT_HERSHEY_SIMPLEX, 0.5, color, 2)


def draw_hud(frame, chaos, alerts, fps, frame_id):
    """Draw full HUD overlay — top bar + alert panel + bottom legend."""
    h, w = frame.shape[:2]

    vru_active = any(a.label == "vulnerable_road_user"
                     for a in alerts if hasattr(a, "label")) if alerts else False

    # ── Top bar ───────────────────────────────────────────────────────────────
    bar_col = (50, 0, 0) if vru_active else (15, 15, 15)
    cv2.rectangle(frame, (0, 0), (w, 48), bar_col, -1)

    if vru_active:
        cv2.putText(frame, "!! VRU DETECTED — REDUCE SPEED !!",
                    (10, 18), cv2.FONT_HERSHEY_SIMPLEX, 0.60, (0, 60, 255), 2)

    chaos_color = CHAOS_COLOURS.get(chaos.level, (200, 200, 200))
    info = (f"Frame:{frame_id}  CHAOS:{chaos.score:.0f}/100 [{chaos.level}]  "
            f"Objects:{chaos.object_count}  FPS:{fps:.1f}")
    cv2.putText(frame, info, (10, 38),
                cv2.FONT_HERSHEY_SIMPLEX, 0.50, chaos_color, 1)

    # ── Alert panel (left side) ───────────────────────────────────────────────
    for i, alert in enumerate(alerts[:4]):
        y = 60 + i * 52
        color = RISK_COLOURS.get(alert.risk_level, (200, 200, 200))
        cv2.putText(frame,
            f"[{alert.risk_level}] {alert.label.upper()} #{alert.track_id}",
            (10, y), cv2.FONT_HERSHEY_SIMPLEX, 0.48, color, 2)
        cv2.putText(frame, alert.message[:75],
            (10, y + 16), cv2.FONT_HERSHEY_SIMPLEX, 0.38, (220, 220, 220), 1)
        cv2.putText(frame, f"-> {alert.action[:75]}",
            (10, y + 30), cv2.FONT_HERSHEY_SIMPLEX, 0.36, (150, 255, 150), 1)

    # ── Chaos bar (bottom right) ───────────────────────────────────────────────
    bar_w = 200
    bar_h = 14
    bx    = w - bar_w - 20
    by    = h - 50
    fill  = int(bar_w * chaos.score / 100)
    cv2.rectangle(frame, (bx, by), (bx + bar_w, by + bar_h), (40, 40, 40), -1)
    cv2.rectangle(frame, (bx, by), (bx + fill,  by + bar_h), chaos_color, -1)
    cv2.putText(frame, f"CHAOS {chaos.score:.0f}",
                (bx, by - 6), cv2.FONT_HERSHEY_SIMPLEX, 0.45, chaos_color, 1)

    # ── Bottom legend ─────────────────────────────────────────────────────────
    cv2.rectangle(frame, (0, h - 26), (w, h), (15, 15, 15), -1)
    cv2.putText(frame,
        "RED=VRU  YELLOW=Ped  LT.GREEN=Rider  CYAN=Auto  MAGENTA=Moto  GREEN=Car",
        (8, h - 8), cv2.FONT_HERSHEY_SIMPLEX, 0.40, (110, 110, 110), 1)

    return frame