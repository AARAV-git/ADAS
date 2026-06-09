"""
explainability/llm_alerts.py — Explainable ADAS Alert Generator

Two modes:
  1. Groq + LLaMA3  → rich natural language alerts (LLM mode)
  2. Rule templates  → fast deterministic fallback (offline mode)

Auto-falls back to rule mode if Groq fails.
"""

import os
import json
from dataclasses import dataclass
from typing import List, Optional
from analytics.risk_engine import RiskEvent, RiskLevel, RiskType
from analytics.chaos_score import ChaosResult
from config import GROQ_API_KEY, LLM_MODEL, USE_LLM


# ── Alert data model ──────────────────────────────────────────────────────────
@dataclass
class ADASAlert:
    track_id:    int
    label:       str
    risk_type:   str
    risk_level:  str
    risk_score:  float
    message:     str
    action:      str
    chaos_level: str
    source:      str = "rule"

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


# ── Rule-based templates ──────────────────────────────────────────────────────
TEMPLATES = {
    RiskType.VRU_DETECTED: {
        RiskLevel.CRITICAL: ("VULNERABLE ROAD USER ahead — wheelchair/elderly/disabled person detected!",
                             "Emergency brake. Watch for others nearby."),
        RiskLevel.HIGH:     ("Vulnerable road user nearby — possible disabled or elderly person.",
                             "Reduce speed significantly. Prepare to stop."),
        RiskLevel.MEDIUM:   ("Possible vulnerable road user detected ahead.",
                             "Slow down and give extra clearance."),
    },
    RiskType.LANE_CUT: {
        RiskLevel.CRITICAL: ("{label} cutting sharply into your lane — immediate action required!",
                             "Brake firmly and steer away."),
        RiskLevel.HIGH:     ("{label} drifting into your lane from {side}.",
                             "Ease off throttle and prepare to steer away."),
        RiskLevel.MEDIUM:   ("{label} showing lane-change intent from {side}.",
                             "Monitor and hold your lane."),
        RiskLevel.LOW:      ("{label} slight lateral movement detected.",
                             "Stay alert."),
    },
    RiskType.COLLISION: {
        RiskLevel.CRITICAL: ("COLLISION IMMINENT — {label} directly ahead, closing fast!",
                             "Apply emergency brakes immediately."),
        RiskLevel.HIGH:     ("{label} dangerously close — high collision risk.",
                             "Reduce speed and increase following distance."),
        RiskLevel.MEDIUM:   ("{label} approaching. Safe distance reducing.",
                             "Slow down and maintain safe gap."),
        RiskLevel.LOW:      ("{label} in proximity. Stay aware.",
                             "Monitor and maintain speed."),
    },
    RiskType.PEDESTRIAN_CROSS: {
        RiskLevel.CRITICAL: ("Pedestrian stepping onto road ahead — brake NOW!",
                             "Emergency brake. Watch for more pedestrians."),
        RiskLevel.HIGH:     ("Pedestrian likely crossing road ahead.",
                             "Reduce speed, prepare to stop."),
        RiskLevel.MEDIUM:   ("Pedestrian near road — possible crossing.",
                             "Slow down and yield."),
        RiskLevel.LOW:      ("Pedestrian activity detected nearby.",
                             "Stay alert."),
    },
    RiskType.BLIND_SPOT: {
        RiskLevel.CRITICAL: ("{label} approaching fast in your {side} blind spot!",
                             "Do NOT change lanes. Check mirrors."),
        RiskLevel.HIGH:     ("{label} in {side} blind spot.",
                             "Avoid lane change. Check before merging."),
        RiskLevel.MEDIUM:   ("{label} in {side} peripheral zone.",
                             "Caution before lateral movement."),
        RiskLevel.LOW:      ("{label} at {side} edge.",
                             "Stay aware of side traffic."),
    },
    RiskType.TAILGATING: {
        RiskLevel.CRITICAL: ("{label} extremely close behind — dangerous tailgating!",
                             "Increase speed or change lane to let them pass."),
        RiskLevel.HIGH:     ("{label} following too close.",
                             "Allow the vehicle to overtake."),
        RiskLevel.MEDIUM:   ("{label} close following distance.",
                             "Avoid sudden braking."),
    },
    RiskType.GENERAL: {
        RiskLevel.HIGH:     ("Risky behavior from nearby {label}.",
                             "Increase alertness and reduce speed."),
        RiskLevel.MEDIUM:   ("Unusual movement from {label}.",
                             "Monitor the vehicle."),
        RiskLevel.LOW:      ("{label} in vicinity.", "Stay alert."),
    },
}


def _side(cx: float, fw: float) -> str:
    if cx < fw * 0.35:  return "left"
    if cx > fw * 0.65:  return "right"
    return "front"


# ── Main engine ───────────────────────────────────────────────────────────────
class ExplainabilityEngine:
    def __init__(self):
        self.use_llm = False
        self.client  = None
        self.use_ollama = False

        if USE_LLM and GROQ_API_KEY:
            try:
                from groq import Groq
                self.client  = Groq(api_key=GROQ_API_KEY)
                self.use_llm = True
                print("  [Explainability] Groq + LLaMA3 enabled")
            except Exception as e:
                print(f"  [Explainability] Groq initialization failed ({e})")
        
        # Check if local Ollama is available as fallback
        if not self.use_llm:
            if self._check_ollama():
                self.use_ollama = True
                self.use_llm = True
                print("  [Explainability] Local Ollama LLaMA3 enabled")
            else:
                print("  [Explainability] Rule-based mode (Groq & local Ollama offline)")

    def _check_ollama(self) -> bool:
        import urllib.request
        try:
            with urllib.request.urlopen("http://localhost:11434/api/tags", timeout=1.0) as r:
                return r.status == 200
        except Exception:
            return False

    def generate(
        self,
        risk_events:    List[RiskEvent],
        chaos:          ChaosResult,
        frame_width:    int = 1280,
    ) -> List[ADASAlert]:
        alerts = []
        for event in risk_events:
            side = _side(
                (event.bbox[0] + event.bbox[2]) / 2 if event.bbox else frame_width/2,
                frame_width
            )
            if self.use_llm and event.risk_level in (RiskLevel.HIGH, RiskLevel.CRITICAL):
                alert = self._llm_alert(event, chaos, side)
            else:
                alert = self._rule_alert(event, chaos, side)
            alerts.append(alert)
        return alerts

    # ── Rule-based ────────────────────────────────────────────────────────────
    def _rule_alert(self, event: RiskEvent, chaos: ChaosResult, side: str) -> ADASAlert:
        tg = TEMPLATES.get(event.risk_type, TEMPLATES[RiskType.GENERAL])
        for level in [event.risk_level, RiskLevel.MEDIUM, RiskLevel.LOW]:
            if level in tg:
                msg_t, act_t = tg[level]
                break
        else:
            msg_t, act_t = "{label} detected.", "Stay alert."

        label_fmt = event.label.replace("_", " ").capitalize()
        message   = msg_t.format(label=label_fmt, side=side)
        action    = act_t.format(label=label_fmt, side=side)

        if chaos.level == "Chaotic":
            message += f" [Traffic chaos: {chaos.score:.0f}/100]"

        return ADASAlert(
            track_id    = event.track_id,
            label       = event.label,
            risk_type   = event.risk_type,
            risk_level  = event.risk_level,
            risk_score  = event.risk_score,
            message     = message,
            action      = action,
            chaos_level = chaos.level,
            source      = "rule",
        )

    # ── LLM-based ─────────────────────────────────────────────────────────────
    def _llm_alert(self, event: RiskEvent, chaos: ChaosResult, side: str) -> ADASAlert:
        prompt = f"""You are an ADAS warning system for Indian roads.
Generate a concise safety alert (max 2 sentences) for the driver.

Situation:
- Object    : {event.label} (ID #{event.track_id})
- Risk type : {event.risk_type}
- Risk level: {event.risk_level}
- Risk score: {event.risk_score:.2f}
- Position  : {side} side
- Speed     : {event.details.get('speed', '?')} px/frame
- Traffic   : {chaos.level} (chaos score {chaos.score:.0f}/100)

Respond ONLY with valid JSON (no markdown):
{{"message": "<warning>", "action": "<recommended action>"}}"""

        parsed = None
        source = "rule"

        # 1. Try Groq (if client initialized and not already switched to Ollama)
        if self.client and not self.use_ollama:
            try:
                resp = self.client.chat.completions.create(
                    model       = LLM_MODEL,
                    messages    = [{"role": "user", "content": prompt}],
                    max_tokens  = 120,
                    temperature = 0.3,
                )
                text   = resp.choices[0].message.content.strip()
                text   = text.replace("```json", "").replace("```", "").strip()
                parsed = json.loads(text)
                source = "llm"
            except Exception as e:
                print(f"  [Groq LLM] Failed ({e}). Checking local Ollama...")
                if self._check_ollama():
                    self.use_ollama = True
                else:
                    print("  [Explainability] Local Ollama offline. Using rule fallback.")
                    self.use_llm = False

        # 2. Try Local Ollama fallback (if enabled)
        if self.use_ollama and not parsed:
            try:
                import urllib.request
                url = "http://localhost:11434/api/chat"
                payload = {
                    "model": "llama3:latest",
                    "messages": [
                        {"role": "user", "content": prompt}
                    ],
                    "stream": False,
                    "options": {
                        "temperature": 0.3,
                        "num_predict": 120
                    }
                }
                headers = {"Content-Type": "application/json"}
                req = urllib.request.Request(
                    url,
                    data=json.dumps(payload).encode("utf-8"),
                    headers=headers,
                    method="POST"
                )
                with urllib.request.urlopen(req, timeout=15.0) as response:
                    res = json.loads(response.read().decode("utf-8"))
                    text = res["message"]["content"].strip()
                    text = text.replace("```json", "").replace("```", "").strip()
                    parsed = json.loads(text)
                    source = "ollama"
            except Exception as e:
                print(f"  [Ollama LLM] Failed ({e}). Disabling LLM mode.")
                self.use_llm = False

        if parsed:
            return ADASAlert(
                track_id    = event.track_id,
                label       = event.label,
                risk_type   = event.risk_type,
                risk_level  = event.risk_level,
                risk_score  = event.risk_score,
                message     = parsed.get("message", "Risk detected."),
                action      = parsed.get("action",  "Stay alert."),
                chaos_level = chaos.level,
                source      = source,
            )
        else:
            return self._rule_alert(event, chaos, side)

    def summarize(self, alerts: List[ADASAlert], chaos: ChaosResult) -> dict:
        if not alerts:
            return {"highest_risk": "LOW", "alert_count": 0,
                    "chaos": chaos.to_dict(), "top_alert": None}
        top = alerts[0]
        return {
            "highest_risk": top.risk_level,
            "alert_count":  len(alerts),
            "chaos":        chaos.to_dict(),
            "top_alert":    top.to_dict(),
            "all_alerts":   [a.to_dict() for a in alerts],
        }