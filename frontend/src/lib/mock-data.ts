// RoadSense AI — Mock Data Generators for Demo

import type {
  StatsOverview,
  Session,
  Alert,
  TelemetryFrame,
  ChaosData,
  TrackedObject,
  ExplainResponse,
} from "./types";

// --- Random Helpers ---
const rand = (min: number, max: number) => Math.random() * (max - min) + min;
const randInt = (min: number, max: number) => Math.floor(rand(min, max + 1));
const pick = <T>(arr: readonly T[] | T[]): T => arr[Math.floor(Math.random() * arr.length)] as T;

const OBJECT_LABELS = ["car", "motorcycle", "pedestrian", "bicycle", "truck", "bus"];
const RISK_TYPES = [
  "vru_proximity",
  "lane_intrusion",
  "speed_anomaly",
  "pedestrian_on_road",
  "tailgating",
  "wrong_way",
];
const RISK_LEVELS = ["LOW", "MEDIUM", "HIGH", "CRITICAL"] as const;
const CHAOS_LEVELS = ["Calm", "Low", "Moderate", "High", "Critical"] as const;

const ALERT_MESSAGES: Record<string, string[]> = {
  vru_proximity: [
    "Vulnerable user approaching rapidly",
    "Pedestrian detected near vehicle path",
    "Motorcycle entering blind spot",
  ],
  lane_intrusion: [
    "Vehicle crossing lane boundary",
    "Lane deviation detected ahead",
    "Object drifting into lane",
  ],
  speed_anomaly: [
    "Speed variance exceeding threshold",
    "Rapid deceleration detected",
    "Vehicle approaching at high speed",
  ],
  pedestrian_on_road: [
    "Pedestrian crossed road path",
    "Person walking along roadway",
    "Pedestrian jaywalking ahead",
  ],
  tailgating: [
    "Following vehicle too close",
    "Rear approach speed high",
    "Insufficient following distance",
  ],
  wrong_way: [
    "Vehicle traveling against traffic",
    "Wrong-way driver detected",
    "Oncoming vehicle in lane",
  ],
};

const ALERT_ACTIONS: Record<string, string[]> = {
  vru_proximity: [
    "Slow down and watch left side",
    "Reduce speed, prepare to brake",
    "Check mirrors and maintain distance",
  ],
  lane_intrusion: [
    "Steer back to center lane",
    "Maintain current lane position",
    "Reduce speed and signal",
  ],
  speed_anomaly: [
    "Adjust speed to match flow",
    "Prepare for sudden stop",
    "Increase following distance",
  ],
  pedestrian_on_road: [
    "Stop immediately if safe",
    "Slow down and yield",
    "Sound horn and reduce speed",
  ],
  tailgating: [
    "Allow vehicle to pass safely",
    "Gradually increase following distance",
    "Change lane when safe",
  ],
  wrong_way: [
    "Pull over to the right immediately",
    "Reduce speed and flash lights",
    "Move to shoulder if possible",
  ],
};

// --- Data Generators ---
export function generateChaosData(overrideScore?: number): ChaosData {
  const score = overrideScore ?? rand(0, 100);
  const level =
    score < 20 ? "Calm" :
    score < 40 ? "Low" :
    score < 60 ? "Moderate" :
    score < 80 ? "High" : "Critical";

  return {
    score: Math.round(score * 10) / 10,
    level,
    breakdown: {
      vehicle_density: rand(5, 80),
      speed_variance: rand(5, 60),
      lane_intrusion: rand(0, 90),
      pedestrian_density: rand(0, 40),
    },
  };
}

export function generateAlert(frameId?: number): Alert {
  const riskType = pick(RISK_TYPES);
  const riskLevel = pick(RISK_LEVELS);
  return {
    track_id: randInt(1, 20),
    label: pick(OBJECT_LABELS),
    risk_type: riskType,
    risk_level: riskLevel,
    risk_score: Math.round(rand(1, 10) * 10) / 10,
    message: pick(ALERT_MESSAGES[riskType] || ["Risk detected"]),
    action: pick(ALERT_ACTIONS[riskType] || ["Exercise caution"]),
    frame_id: frameId ?? randInt(1, 1000),
    timestamp: new Date().toISOString(),
  };
}

export function generateTrackedObject(frameW = 640, frameH = 480): TrackedObject {
  const label = pick(OBJECT_LABELS);
  const x = randInt(50, frameW - 150);
  const y = randInt(50, frameH - 150);
  const w = randInt(40, 150);
  const h = randInt(40, 150);
  return {
    track_id: randInt(1, 20),
    label,
    conf: Math.round(rand(0.5, 0.99) * 100) / 100,
    bbox: [x, y, x + w, y + h],
    cx: x + w / 2,
    cy: y + h / 2,
    speed: Math.round(rand(0, 50) * 10) / 10,
    velocity: [Math.round(rand(-5, 5) * 10) / 10, Math.round(rand(-5, 5) * 10) / 10],
    direction: Math.round(rand(0, 360) * 10) / 10,
    frame_w: frameW,
    frame_h: frameH,
  };
}

export function generateTelemetryFrame(frameId: number): TelemetryFrame {
  const chaos = generateChaosData();
  const alertCount = chaos.level === "Calm" || chaos.level === "Low" ? 0 : randInt(0, 3);
  const alerts = Array.from({ length: alertCount }, () => generateAlert(frameId));
  const trackedCount = randInt(1, 6);
  const tracked = Array.from({ length: trackedCount }, () => generateTrackedObject());

  const counts: Record<string, number> = {};
  tracked.forEach((t) => {
    counts[t.label] = (counts[t.label] || 0) + 1;
  });

  return {
    frame_id: frameId,
    fps: Math.round(rand(12, 30) * 10) / 10,
    session_id: 1,
    chaos,
    alerts,
    tracked,
    counts,
  };
}

// --- Stats Overview ---
export function generateStatsOverview(): StatsOverview {
  return {
    total_sessions: randInt(3, 12),
    total_frames: randInt(2000, 15000),
    total_alerts: randInt(8, 85),
    avg_chaos_score: Math.round(rand(25, 65) * 10) / 10,
    top_risk_level: pick(["HIGH", "MEDIUM", "CRITICAL"]),
    alert_breakdown: {
      CRITICAL: randInt(2, 15),
      HIGH: randInt(5, 30),
      MEDIUM: randInt(8, 25),
      LOW: randInt(3, 20),
    },
    top_classes: [
      { label: "car", count: randInt(20, 80) },
      { label: "motorcycle", count: randInt(10, 40) },
      { label: "pedestrian", count: randInt(5, 30) },
      { label: "bicycle", count: randInt(3, 15) },
      { label: "truck", count: randInt(2, 12) },
      { label: "bus", count: randInt(1, 10) },
    ],
  };
}

// --- Sessions ---
const VIDEO_NAMES = [
  "highway_morning.mp4",
  "urban_intersection.mp4",
  "residential_area.mp4",
  "expressway_night.mp4",
  "school_zone.mp4",
  "market_road.mp4",
  "ring_road.mp4",
  "flyover_descent.mp4",
];

export function generateSessions(count = 6): Session[] {
  return Array.from({ length: count }, (_, i) => {
    const totalFrames = randInt(500, 5000);
    const detectionSummary: Record<string, number> = {};
    const objCount = randInt(2, 5);
    for (let j = 0; j < objCount; j++) {
      detectionSummary[pick(OBJECT_LABELS)] = randInt(5, 50);
    }

    const startDate = new Date(Date.now() - randInt(1, 30) * 86400000);
    const endDate = new Date(startDate.getTime() + randInt(30, 300) * 1000);

    return {
      id: i + 1,
      video_name: VIDEO_NAMES[i % VIDEO_NAMES.length],
      started_at: startDate.toISOString(),
      ended_at: endDate.toISOString(),
      total_frames: totalFrames,
      avg_fps: Math.round(rand(12, 28) * 10) / 10,
      avg_chaos_score: Math.round(rand(15, 75) * 10) / 10,
      max_chaos_score: Math.round(rand(60, 98) * 10) / 10,
      peak_risk_level: pick(RISK_LEVELS),
      detection_summary: detectionSummary,
    };
  });
}

// --- Telemetry History (for charts) ---
export function generateTelemetryHistory(points = 60): {
  frame_id: number;
  chaos_score: number;
  fps: number;
  alert_count: number;
  object_count: number;
}[] {
  const data: any[] = [];
  let baseChaos = rand(20, 50);
  for (let i = 0; i < points; i++) {
    baseChaos += rand(-5, 5);
    baseChaos = Math.max(0, Math.min(100, baseChaos));
    data.push({
      frame_id: i + 1,
      chaos_score: Math.round(baseChaos * 10) / 10,
      fps: Math.round(rand(15, 28) * 10) / 10,
      alert_count: baseChaos > 60 ? randInt(1, 4) : baseChaos > 40 ? randInt(0, 2) : 0,
      object_count: randInt(1, 8),
    });
  }
  return data;
}

// --- AI Explainability ---
export function generateExplainResponse(): ExplainResponse {
  const riskLevel = pick(RISK_LEVELS);
  const explanations: Record<string, { message: string; action: string }> = {
    CRITICAL: {
      message:
        "A motorcycle has entered your left blind spot at 42km/h under highly chaotic lane-weaving conditions. The driver is likely to cut ahead, creating an immediate collision risk.",
      action:
        "Maintain lane position, slow down slightly, and check your left mirror before executing any lateral moves. Do not change lanes.",
    },
    HIGH: {
      message:
        "A vehicle is rapidly approaching from the rear in an area with elevated pedestrian activity and lane instability. Current chaos conditions suggest unpredictable traffic flow.",
      action:
        "Reduce speed gradually, increase following distance, and remain alert for sudden stops. Avoid aggressive lane changes.",
    },
    MEDIUM: {
      message:
        "Moderate risk detected: a pedestrian is walking near the roadway edge in a zone with moderate vehicle density. The situation is stable but requires attention.",
      action:
        "Maintain current speed but stay alert. Be prepared to yield if the pedestrian enters the roadway.",
    },
    LOW: {
      message:
        "A bicycle has been detected at a safe distance. Traffic conditions are calm with low chaos indicators.",
      action:
        "Continue driving normally. Maintain awareness of the cyclist's position and provide adequate space when passing.",
    },
  };

  const exp = explanations[riskLevel];
  return {
    risk_level: riskLevel,
    message: exp.message,
    action: exp.action,
  };
}

// --- Video List ---
export function generateVideoList(): string[] {
  return VIDEO_NAMES.slice(0, randInt(3, VIDEO_NAMES.length));
}
