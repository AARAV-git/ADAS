# """
# llm_alerts.py — Explainable ADAS alert generation for RoadSense AI

# Two modes:
#   1. LLM mode  — Groq + LLaMA3 generates natural-language warnings
#   2. Rule mode — Fast deterministic templates (fallback / offline)

# The rule-based fallback is production-safe; LLM adds richness for demo.
# """

# import os
# import json
# from dataclasses import dataclass
# from typing import List, Optional

# from analytics.risk_engine import RiskEvent, RiskLevel, RiskType
# from analytics.chaos_score import ChaosResult


# # ─── Data model ──────────────────────────────────────────────────────────────

# @dataclass
# class ADASAlert:
#     track_id: int
#     label: str
#     risk_type: str
#     risk_level: str
#     risk_score: float
#     message: str           # Human-readable warning
#     action: str            # Recommended driver action
#     chaos_level: str
#     source: str = "rule"   # "rule" | "llm"

#     def to_dict(self):
#         return {
#             "track_id":   self.track_id,
#             "label":      self.label,
#             "risk_type":  self.risk_type,
#             "risk_level": self.risk_level,
#             "risk_score": round(self.risk_score, 3),
#             "message":    self.message,
#             "action":     self.action,
#             "chaos_level": self.chaos_level,
#             "source":     self.source,
#         }


# # ─── Rule-based templates ─────────────────────────────────────────────────────

# TEMPLATES = {
#     RiskType.LANE_CUT: {
#         RiskLevel.CRITICAL: (
#             "{label} cutting sharply into your lane — immediate evasive action required!",
#             "Brake firmly and move away from the intruding vehicle."
#         ),
#         RiskLevel.HIGH: (
#             "{label} drifting into your lane from the {side}.",
#             "Ease off throttle, prepare to steer away."
#         ),
#         RiskLevel.MEDIUM: (
#             "{label} showing lane-change intent from the {side}.",
#             "Monitor the vehicle and hold your lane."
#         ),
#         RiskLevel.LOW: (
#             "{label} slight lateral movement detected.",
#             "Stay alert."
#         ),
#     },
#     RiskType.COLLISION: {
#         RiskLevel.CRITICAL: (
#             "COLLISION IMMINENT — {label} directly ahead, closing fast!",
#             "Apply emergency brakes immediately."
#         ),
#         RiskLevel.HIGH: (
#             "{label} dangerously close ahead — high collision risk.",
#             "Reduce speed and increase following distance."
#         ),
#         RiskLevel.MEDIUM: (
#             "{label} approaching rapidly. Safe distance reducing.",
#             "Slow down and maintain safe gap."
#         ),
#         RiskLevel.LOW: (
#             "{label} in proximity. Stay aware.",
#             "Monitor and maintain speed."
#         ),
#     },
#     RiskType.PEDESTRIAN_CROSS: {
#         RiskLevel.CRITICAL: (
#             "Pedestrian stepping onto road ahead — brake NOW!",
#             "Emergency brake. Watch for more pedestrians."
#         ),
#         RiskLevel.HIGH: (
#             "Pedestrian likely crossing the road ahead.",
#             "Reduce speed, prepare to stop."
#         ),
#         RiskLevel.MEDIUM: (
#             "Pedestrian near road edge — possible crossing.",
#             "Slow down and stay ready to yield."
#         ),
#         RiskLevel.LOW: (
#             "Pedestrian activity detected nearby.",
#             "Remain alert."
#         ),
#     },
#     RiskType.BLIND_SPOT: {
#         RiskLevel.CRITICAL: (
#             "{label} approaching rapidly in your {side} blind spot!",
#             "Do NOT change lanes. Check mirrors immediately."
#         ),
#         RiskLevel.HIGH: (
#             "{label} in {side} blind spot, moving fast.",
#             "Avoid lane change. Check blind spot before merging."
#         ),
#         RiskLevel.MEDIUM: (
#             "{label} in {side} peripheral zone.",
#             "Be cautious before any lateral movement."
#         ),
#         RiskLevel.LOW: (
#             "{label} detected at {side} edge.",
#             "Stay aware of side traffic."
#         ),
#     },
#     RiskType.TAILGATING: {
#         RiskLevel.CRITICAL: (
#             "{label} extremely close behind — tailgating dangerously!",
#             "Increase speed slightly or change lane to let them pass."
#         ),
#         RiskLevel.HIGH: (
#             "{label} following too close behind.",
#             "Consider allowing the vehicle to overtake."
#         ),
#         RiskLevel.MEDIUM: (
#             "{label} maintaining close following distance.",
#             "Stay steady; avoid sudden braking."
#         ),
#         RiskLevel.LOW: (
#             "{label} behind at moderate distance.",
#             "Normal monitoring."
#         ),
#     },
#     RiskType.GENERAL: {
#         RiskLevel.HIGH: (
#             "Risky behavior detected from nearby {label}.",
#             "Increase alertness and reduce speed."
#         ),
#         RiskLevel.MEDIUM: (
#             "Unusual movement from {label} detected.",
#             "Monitor the vehicle carefully."
#         ),
#         RiskLevel.LOW: (
#             "{label} in vicinity.",
#             "Stay alert."
#         ),
#     },
# }


# def _side_from_center(cx: float, frame_width: float) -> str:
#     if cx < frame_width * 0.35:
#         return "left"
#     elif cx > frame_width * 0.65:
#         return "right"
#     else:
#         return "front"


# # ─── Main class ───────────────────────────────────────────────────────────────

# class ExplainabilityEngine:
#     """
#     Converts RiskEvent objects into human-readable ADASAlert objects.
#     Optionally uses Groq LLaMA3 for richer explanations.
#     """

#     def __init__(
#         self,
#         use_llm: bool = False,
#         groq_api_key: Optional[str] = None,
#         frame_width: int = 1280,
#     ):
#         self.use_llm     = use_llm
#         self.groq_api_key = groq_api_key or os.getenv("GROQ_API_KEY", "")
#         self.frame_width  = frame_width
#         self.groq_client  = None

#         if use_llm and self.groq_api_key:
#             try:
#                 from groq import Groq
#                 self.groq_client = Groq(api_key=self.groq_api_key)
#                 print("[Explainability] LLM mode: Groq + LLaMA3 enabled")
#             except ImportError:
#                 print("[Explainability] groq package not found, falling back to rule-based")
#                 self.use_llm = False
#         else:
#             print("[Explainability] Rule-based mode active")

#     def generate_alerts(
#         self,
#         risk_events: List[RiskEvent],
#         chaos: ChaosResult,
#         object_centers: Optional[dict] = None,   # track_id → (cx, cy)
#     ) -> List[ADASAlert]:
#         """Generate ADASAlert for each RiskEvent."""
#         alerts = []
#         for event in risk_events:
#             cx = (
#                 object_centers.get(event.track_id, (self.frame_width / 2, 0))[0]
#                 if object_centers else self.frame_width / 2
#             )
#             side = _side_from_center(cx, self.frame_width)

#             if (
#                 self.use_llm
#                 and self.groq_client
#                 and event.risk_level in (RiskLevel.HIGH, RiskLevel.CRITICAL)
#             ):
#                 alert = self._llm_alert(event, chaos, side)
#             else:
#                 alert = self._rule_alert(event, chaos, side)

#             alerts.append(alert)

#         return alerts

#     # ── Rule-based ───────────────────────────────────────────────────────────

#     def _rule_alert(self, event: RiskEvent, chaos: ChaosResult, side: str) -> ADASAlert:
#         template_group = TEMPLATES.get(event.risk_type, TEMPLATES[RiskType.GENERAL])
#         for level in [event.risk_level, RiskLevel.MEDIUM, RiskLevel.LOW]:
#             if level in template_group:
#                 msg_tpl, action_tpl = template_group[level]
#                 break
#         else:
#             msg_tpl, action_tpl = "{label} detected.", "Stay alert."

#         label_fmt = event.label.replace("_", " ")
#         message = msg_tpl.format(label=label_fmt.capitalize(), side=side)
#         action  = action_tpl.format(label=label_fmt.capitalize(), side=side)

#         if chaos.level == "Chaotic":
#             message += f" [Chaotic traffic — chaos score: {chaos.score:.0f}]"

#         return ADASAlert(
#             track_id=event.track_id,
#             label=event.label,
#             risk_type=event.risk_type,
#             risk_level=event.risk_level,
#             risk_score=event.risk_score,
#             message=message,
#             action=action,
#             chaos_level=chaos.level,
#             source="rule",
#         )

#     # ── LLM-based ────────────────────────────────────────────────────────────

#     def _llm_alert(self, event: RiskEvent, chaos: ChaosResult, side: str) -> ADASAlert:
#         """Generate alert using Groq LLaMA3."""
#         prompt = f"""You are an ADAS warning system for Indian roads.
# Generate a concise safety alert (max 2 sentences) for the driver.

# Context:
# - Object: {event.label} (Track #{event.track_id})
# - Risk type: {event.risk_type}
# - Risk level: {event.risk_level}
# - Risk score: {event.risk_score:.2f}
# - Position: {side} side
# - Speed: {event.details.get('speed', 'unknown')} px/frame
# - Traffic chaos: {chaos.level} ({chaos.score:.0f}/100)

# Respond with JSON only (no markdown):
# {{"message": "<ADAS warning>", "action": "<driver action>"}}
# """
#         try:
#             response = self.groq_client.chat.completions.create(
#                 model="llama3-8b-8192",
#                 messages=[{"role": "user", "content": prompt}],
#                 max_tokens=120,
#                 temperature=0.3,
#             )
#             text = response.choices[0].message.content.strip()
#             text = text.replace("```json", "").replace("```", "").strip()
#             parsed = json.loads(text)
#             return ADASAlert(
#                 track_id=event.track_id,
#                 label=event.label,
#                 risk_type=event.risk_type,
#                 risk_level=event.risk_level,
#                 risk_score=event.risk_score,
#                 message=parsed.get("message", "Risk detected."),
#                 action=parsed.get("action", "Stay alert."),
#                 chaos_level=chaos.level,
#                 source="llm",
#             )
#         except Exception as e:
#             print(f"[Explainability] LLM call failed ({e}), using rule fallback")
#             return self._rule_alert(event, chaos, side)

#     # ── Summary ──────────────────────────────────────────────────────────────

#     def summarize(self, alerts: List[ADASAlert], chaos: ChaosResult) -> dict:
#         """Return a frame-level summary dict for the dashboard."""
#         if not alerts:
#             return {
#                 "highest_risk": RiskLevel.LOW,
#                 "alert_count": 0,
#                 "chaos": chaos.to_dict(),
#                 "top_alert": None,
#             }
#         top = alerts[0]
#         return {
#             "highest_risk": top.risk_level,
#             "alert_count": len(alerts),
#             "chaos": chaos.to_dict(),
#             "top_alert": top.to_dict(),
#             "all_alerts": [a.to_dict() for a in alerts],
#         }


"""
explainability.py — Explainable ADAS alert generation for RoadSense AI

Two modes:
  1. LLM mode  — Groq + LLaMA3 generates natural-language warnings
  2. Rule mode — Fast deterministic templates (fallback / offline)

The rule-based fallback is production-safe; LLM adds richness for demo.
"""

import os
import json
import random
from dataclasses import dataclass, field
from typing import List, Optional

from analytics.risk_engine import RiskEvent, RiskLevel, RiskType
from analytics.chaos_score import ChaosResult


# ─── Data model ──────────────────────────────────────────────────────────────

@dataclass
class ADASAlert:
    track_id: int
    label: str
    risk_type: str
    risk_level: str
    risk_score: float
    message: str           # Human-readable warning
    action: str            # Recommended driver action
    chaos_level: str
    source: str = "rule"   # "rule" | "llm"

    def to_dict(self):
        return {
            "track_id":   self.track_id,
            "label":      self.label,
            "risk_type":  self.risk_type,
            "risk_level": self.risk_level,
            "risk_score": round(self.risk_score, 3),
            "message":    self.message,
            "action":     self.action,
            "chaos_level": self.chaos_level,
            "source":     self.source,
        }


# ─── Rule-based templates ─────────────────────────────────────────────────────

TEMPLATES = {
    RiskType.LANE_CUT: {
        RiskLevel.CRITICAL: (
            "{label} cutting sharply into your lane — immediate evasive action required!",
            "Brake firmly and move away from the intruding vehicle."
        ),
        RiskLevel.HIGH: (
            "{label} drifting into your lane from {side}.",
            "Ease off throttle, prepare to steer away."
        ),
        RiskLevel.MEDIUM: (
            "{label} showing lane-change intent from {side}.",
            "Monitor the vehicle and hold your lane."
        ),
        RiskLevel.LOW: (
            "{label} slight lateral movement detected.",
            "Stay alert."
        ),
    },
    RiskType.COLLISION: {
        RiskLevel.CRITICAL: (
            "COLLISION IMMINENT — {label} directly ahead, closing fast!",
            "Apply emergency brakes immediately."
        ),
        RiskLevel.HIGH: (
            "{label} dangerously close ahead — high collision risk.",
            "Reduce speed and increase following distance."
        ),
        RiskLevel.MEDIUM: (
            "{label} approaching rapidly. Safe distance reducing.",
            "Slow down and maintain safe gap."
        ),
        RiskLevel.LOW: (
            "{label} in proximity. Stay aware.",
            "Monitor and maintain speed."
        ),
    },
    RiskType.PEDESTRIAN_CROSS: {
        RiskLevel.CRITICAL: (
            "Pedestrian stepping onto road ahead — brake NOW!",
            "Emergency brake. Watch for more pedestrians."
        ),
        RiskLevel.HIGH: (
            "Pedestrian likely crossing the road ahead.",
            "Reduce speed, prepare to stop."
        ),
        RiskLevel.MEDIUM: (
            "Pedestrian near road edge — possible crossing.",
            "Slow down and stay ready to yield."
        ),
        RiskLevel.LOW: (
            "Pedestrian activity detected nearby.",
            "Remain alert."
        ),
    },
    RiskType.BLIND_SPOT: {
        RiskLevel.CRITICAL: (
            "{label} approaching rapidly in your {side} blind spot!",
            "Do NOT change lanes. Check mirrors."
        ),
        RiskLevel.HIGH: (
            "{label} in {side} blind spot, moving fast.",
            "Avoid lane change. Check blind spot before merging."
        ),
        RiskLevel.MEDIUM: (
            "{label} in {side} peripheral zone.",
            "Be cautious before any lateral movement."
        ),
        RiskLevel.LOW: (
            "{label} detected at {side} edge.",
            "Stay aware of side traffic."
        ),
    },
    RiskType.TAILGATING: {
        RiskLevel.CRITICAL: (
            "{label} extremely close behind — tailgating dangerously!",
            "Increase speed slightly or change lane to let them pass."
        ),
        RiskLevel.HIGH: (
            "{label} following too close behind.",
            "Consider allowing the vehicle to overtake."
        ),
        RiskLevel.MEDIUM: (
            "{label} maintaining close following distance.",
            "Stay steady; avoid sudden braking."
        ),
        RiskLevel.LOW: (
            "{label} behind at moderate distance.",
            "Normal monitoring."
        ),
    },
    RiskType.GENERAL: {
        RiskLevel.HIGH: (
            "Risky behavior detected from nearby {label}.",
            "Increase alertness and reduce speed."
        ),
        RiskLevel.MEDIUM: (
            "Unusual movement from {label} detected.",
            "Monitor the vehicle."
        ),
        RiskLevel.LOW: (
            "{label} in vicinity.",
            "Stay alert."
        ),
    },
}


def _side_from_center(cx: float, frame_width: float) -> str:
    if cx < frame_width * 0.35:
        return "left"
    elif cx > frame_width * 0.65:
        return "right"
    else:
        return "front"


# ─── Main class ───────────────────────────────────────────────────────────────

class ExplainabilityEngine:
    """
    Converts RiskEvent objects into human-readable ADASAlert objects.
    Optionally uses Groq LLaMA3 for richer explanations.
    """

    def __init__(
        self,
        use_llm: bool = False,
        groq_api_key: Optional[str] = None,
        frame_width: int = 1280,
    ):
        self.use_llm = use_llm
        self.groq_api_key = groq_api_key or os.getenv("GROQ_API_KEY")
        self.frame_width = frame_width

        if use_llm and self.groq_api_key:
            try:
                from groq import Groq
                self.groq_client = Groq(api_key=self.groq_api_key)
                print("[Explainability] LLM mode: Groq + LLaMA3 enabled")
            except ImportError:
                print("[Explainability] groq package not found, falling back to rule-based")
                self.use_llm = False
        else:
            print("[Explainability] Rule-based mode active")

    def generate_alerts(
        self,
        risk_events: List[RiskEvent],
        chaos: ChaosResult,
        object_centers: Optional[dict] = None,   # track_id → (cx, cy)
    ) -> List[ADASAlert]:
        """Generate ADASAlert for each RiskEvent."""
        alerts = []
        for event in risk_events:
            cx = object_centers.get(event.track_id, (self.frame_width / 2, 0))[0] if object_centers else self.frame_width / 2
            side = _side_from_center(cx, self.frame_width)

            if self.use_llm and event.risk_level in (RiskLevel.HIGH, RiskLevel.CRITICAL):
                alert = self._llm_alert(event, chaos, side)
            else:
                alert = self._rule_alert(event, chaos, side)

            alerts.append(alert)

        return alerts

    # ── Rule-based ───────────────────────────────────────────────────────────

    def _rule_alert(self, event: RiskEvent, chaos: ChaosResult, side: str) -> ADASAlert:
        template_group = TEMPLATES.get(event.risk_type, TEMPLATES[RiskType.GENERAL])
        # Find closest matching level
        for level in [event.risk_level, RiskLevel.MEDIUM, RiskLevel.LOW]:
            if level in template_group:
                msg_tpl, action_tpl = template_group[level]
                break
        else:
            msg_tpl, action_tpl = "{label} detected.", "Stay alert."

        label_fmt = event.label.replace("_", " ")
        message = msg_tpl.format(label=label_fmt.capitalize(), side=side)
        action  = action_tpl.format(label=label_fmt.capitalize(), side=side)

        # Add chaos context
        if chaos.level == "Chaotic":
            message += f" [Chaotic traffic — chaos score: {chaos.score:.0f}]"

        return ADASAlert(
            track_id=event.track_id,
            label=event.label,
            risk_type=event.risk_type,
            risk_level=event.risk_level,
            risk_score=event.risk_score,
            message=message,
            action=action,
            chaos_level=chaos.level,
            source="rule",
        )

    # ── LLM-based ────────────────────────────────────────────────────────────

    def _llm_alert(self, event: RiskEvent, chaos: ChaosResult, side: str) -> ADASAlert:
        """Generate alert using Groq LLaMA3."""
        prompt = f"""You are an ADAS system warning generator for Indian roads.
Generate a concise, clear safety alert (max 2 sentences) for the driver.

Traffic context:
- Object: {event.label} (ID #{event.track_id})
- Risk type: {event.risk_type}
- Risk level: {event.risk_level}
- Risk score: {event.risk_score:.2f}
- Position: {side} side
- Speed: {event.details.get('speed', 'unknown')} px/frame
- Traffic chaos level: {chaos.level} (score: {chaos.score:.0f}/100)

Respond with JSON only:
{{"message": "<warning sentence>", "action": "<recommended action>"}}
"""
        try:
            response = self.groq_client.chat.completions.create(
                model="llama3-8b-8192",
                messages=[{"role": "user", "content": prompt}],
                max_tokens=120,
                temperature=0.3,
            )
            text = response.choices[0].message.content.strip()
            # Strip markdown fences if present
            text = text.replace("```json", "").replace("```", "").strip()
            parsed = json.loads(text)
            return ADASAlert(
                track_id=event.track_id,
                label=event.label,
                risk_type=event.risk_type,
                risk_level=event.risk_level,
                risk_score=event.risk_score,
                message=parsed.get("message", "Risk detected."),
                action=parsed.get("action", "Stay alert."),
                chaos_level=chaos.level,
                source="llm",
            )
        except Exception as e:
            print(f"[Explainability] LLM call failed ({e}), using rule fallback")
            return self._rule_alert(event, chaos, side)

    # ── Summary ──────────────────────────────────────────────────────────────

    def summarize(self, alerts: List[ADASAlert], chaos: ChaosResult) -> dict:
        """Return a frame-level summary dict for the dashboard."""
        if not alerts:
            return {
                "highest_risk": RiskLevel.LOW,
                "alert_count": 0,
                "chaos": chaos.to_dict(),
                "top_alert": None,
            }
        top = alerts[0]
        return {
            "highest_risk": top.risk_level,
            "alert_count": len(alerts),
            "chaos": chaos.to_dict(),
            "top_alert": top.to_dict(),
            "all_alerts": [a.to_dict() for a in alerts],
        }