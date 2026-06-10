"""
utils/drawing.py — OpenCV drawing helpers for RoadSense AI
"""

import cv2
import numpy as np
from config import COLOURS, RISK_COLOURS, CHAOS_COLOURS


def draw_tracked_object(frame, obj):
    """Draw bounding box + label + trajectory tail for a tracked object."""
    h, w = frame.shape[:2]
    # Scale drawing parameters based on frame width (looks balanced on 416px or 1280px)
    scale_factor = max(w / 1280.0, 0.45)
    
    x1, y1, x2, y2 = [int(v) for v in obj.bbox]
    color     = COLOURS.get(obj.label, (200, 200, 200))
    thickness = int(max(3 * scale_factor, 1))

    # Clean bounding box with rounded/accent corners
    cv2.rectangle(frame, (x1, y1), (x2, y2), color, thickness)

    # Clean text label
    SHORT = {
        "vulnerable_road_user": "VRU",
        "auto_rickshaw":        "AUTO",
        "pedestrian":           "PED",
        "motorcycle":           "MOTO",
    }
    label_text = SHORT.get(obj.label, obj.label.upper())
    tag = f"#{obj.track_id} {label_text} {obj.conf:.2f}"
    
    font_scale = 0.40 * (w / 640.0) if w < 1000 else 0.45
    font_scale = max(min(font_scale, 0.7), 0.35)
    
    (tw, th), _ = cv2.getTextSize(tag, cv2.FONT_HERSHEY_SIMPLEX, font_scale, 1)
    
    # Elegant label background tag
    cv2.rectangle(frame, (x1, y1 - th - 6), (x1 + tw + 6, y1), color, -1)
    cv2.putText(frame, tag, (x1 + 3, y1 - 3),
                cv2.FONT_HERSHEY_SIMPLEX, font_scale, (0, 0, 0), 1, cv2.LINE_AA)

    # Trajectory tail (futuristic tracking tail)
    if hasattr(obj, "trajectory") and len(obj.trajectory) > 1:
        pts = [(int(p[0]), int(p[1])) for p in obj.trajectory[-15:]]
        for i in range(1, len(pts)):
            alpha = i / len(pts)
            c = (int(color[0]*alpha), int(color[1]*alpha), int(color[2]*alpha))
            cv2.line(frame, pts[i-1], pts[i], c, int(max(1.5 * scale_factor, 1)))

    # VRU warning rings
    if obj.label == "vulnerable_road_user":
        cx, cy = int(obj.cx), int(obj.cy)
        r = int(max(obj.w, obj.h) // 2 + 10 * scale_factor)
        cv2.circle(frame, (cx, cy), r,     (0, 0, 255), int(max(2 * scale_factor, 1)), cv2.LINE_AA)
        cv2.circle(frame, (cx, cy), int(r + 6 * scale_factor), (0, 0, 255), 1, cv2.LINE_AA)


def draw_risk_overlay(frame, risk_events):
    """Draw risk level badges next to risky objects."""
    h, w = frame.shape[:2]
    scale_factor = max(w / 1280.0, 0.45)
    font_scale = max(min(0.4 * (w / 640.0), 0.6), 0.35)
    
    for event in risk_events[:3]:
        color = RISK_COLOURS.get(event.risk_level, (200, 200, 200))
        if hasattr(event, "bbox") and event.bbox:
            x2 = int(event.bbox[2])
            y1 = int(event.bbox[1])
            badge = f"!{event.risk_level[:3]}"
            cv2.putText(frame, badge, (x2 - int(35 * scale_factor), y1 + int(14 * scale_factor)),
                        cv2.FONT_HERSHEY_SIMPLEX, font_scale, color, 1, cv2.LINE_AA)


def draw_hud(frame, chaos, alerts, fps, frame_id):
    """Draw a clean, minimal ADAS HUD overlay — no giant congested panels or black bars."""
    h, w = frame.shape[:2]
    
    # Scale HUD based on video width
    scale_factor = max(w / 1280.0, 0.45)
    font_scale = 0.45 if w > 800 else 0.38
    
    vru_active = any(a.label == "vulnerable_road_user"
                     for a in alerts if hasattr(a, "label")) if alerts else False

    # ── VRU Alert Banner (Very thin & top-centered instead of giant block) ───
    if vru_active:
        banner_h = int(32 * scale_factor)
        overlay = frame.copy()
        cv2.rectangle(overlay, (0, 0), (w, banner_h), (0, 0, 180), -1)
        cv2.addWeighted(overlay, 0.4, frame, 0.6, 0, frame)
        cv2.putText(frame, "WARNING: VRU PATH INTRUSION DETECTED",
                    (int(15 * scale_factor), int(20 * scale_factor)),
                    cv2.FONT_HERSHEY_SIMPLEX, font_scale * 1.1, (255, 255, 255), 1, cv2.LINE_AA)

    # ── Minimal Status Info (Top-right, transparent background) ─────────────────
    info_text = f"FRAME:{frame_id}  |  FPS:{fps:.1f}  |  CHAOS:{chaos.score:.0f}/100 [{chaos.level}]"
    (tw, th), _ = cv2.getTextSize(info_text, cv2.FONT_HERSHEY_SIMPLEX, font_scale, 1)
    
    # Semi-transparent tag for info
    ix = w - tw - int(20 * scale_factor)
    iy = int(10 * scale_factor) + th
    
    # Draw simple dark backing for readability
    overlay = frame.copy()
    cv2.rectangle(overlay, (ix - 8, iy - th - 6), (w - int(10 * scale_factor), iy + 6), (10, 10, 10), -1)
    cv2.addWeighted(overlay, 0.65, frame, 0.35, 0, frame)
    
    chaos_color = CHAOS_COLOURS.get(chaos.level, (200, 200, 200))
    cv2.putText(frame, info_text, (ix, iy),
                cv2.FONT_HERSHEY_SIMPLEX, font_scale, (255, 255, 255), 1, cv2.LINE_AA)

    # ── Clean Chaos Meter (Bottom-right, small progress bar) ───────────────────
    bar_w = int(150 * scale_factor)
    bar_h = int(8 * scale_factor)
    bx    = w - bar_w - int(20 * scale_factor)
    by    = h - bar_h - int(15 * scale_factor)
    fill  = int(bar_w * chaos.score / 100)
    
    # Backing progress bar
    overlay = frame.copy()
    cv2.rectangle(overlay, (bx - 5, by - int(18 * scale_factor)), (bx + bar_w + 5, by + bar_h + 5), (15, 15, 15), -1)
    cv2.addWeighted(overlay, 0.7, frame, 0.3, 0, frame)
    
    cv2.rectangle(frame, (bx, by), (bx + bar_w, by + bar_h), (50, 50, 50), -1)
    cv2.rectangle(frame, (bx, by), (bx + fill,  by + bar_h), chaos_color, -1)
    cv2.putText(frame, f"CHAOS {chaos.score:.0f}",
                (bx, by - int(5 * scale_factor)), cv2.FONT_HERSHEY_SIMPLEX, font_scale * 0.9, chaos_color, 1, cv2.LINE_AA)

    return frame