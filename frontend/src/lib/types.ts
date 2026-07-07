// RoadSense AI — TypeScript Types

export interface ChaosBreakdown {
  vehicle_density: number;
  speed_variance: number;
  lane_intrusion: number;
  pedestrian_density: number;
}

export interface ChaosData {
  score: number;
  level: "Calm" | "Low" | "Moderate" | "High" | "Critical";
  breakdown: ChaosBreakdown;
}

export interface Alert {
  track_id: number;
  label: string;
  risk_type: string;
  risk_level: "LOW" | "MEDIUM" | "HIGH" | "CRITICAL";
  risk_score: number;
  message: string;
  action: string;
  frame_id?: number;
  timestamp?: string;
}

export interface TrackedObject {
  track_id: number;
  label: string;
  conf: number;
  bbox: [number, number, number, number];
  cx: number;
  cy: number;
  speed: number;
  velocity: [number, number];
  direction: number;
  frame_w: number;
  frame_h: number;
}

export interface TelemetryFrame {
  frame_id: number;
  fps: number;
  session_id: number;
  chaos: ChaosData;
  alerts: Alert[];
  tracked: TrackedObject[];
  counts: Record<string, number>;
}

export interface Session {
  id: number;
  video_name: string;
  started_at: string;
  ended_at: string;
  total_frames: number;
  avg_fps: number;
  avg_chaos_score: number;
  max_chaos_score: number;
  peak_risk_level: "LOW" | "MEDIUM" | "HIGH" | "CRITICAL";
  detection_summary: Record<string, number>;
}

export interface StatsOverview {
  total_sessions: number;
  total_frames: number;
  total_alerts: number;
  avg_chaos_score: number;
  top_risk_level: "LOW" | "MEDIUM" | "HIGH" | "CRITICAL";
  alert_breakdown: Record<string, number>;
  top_classes: { label: string; count: number }[];
}

export interface ExplainRequest {
  event: {
    track_id: number;
    label: string;
    risk_type: string;
    risk_level: string;
    risk_score: number;
    message: string;
  };
  chaos: ChaosData;
  position: string;
}

export interface ExplainResponse {
  risk_level: string;
  message: string;
  action: string;
}

export type ChaosLevel = "Calm" | "Low" | "Moderate" | "High" | "Critical";

export const CHAOS_LEVEL_CONFIG: Record<ChaosLevel, { color: string; bg: string; label: string }> = {
  Calm: { color: "text-emerald-400", bg: "bg-emerald-500/20", label: "CALM" },
  Low: { color: "text-green-400", bg: "bg-green-500/20", label: "LOW" },
  Moderate: { color: "text-amber-400", bg: "bg-amber-500/20", label: "MODERATE" },
  High: { color: "text-orange-400", bg: "bg-orange-500/20", label: "HIGH" },
  Critical: { color: "text-red-400", bg: "bg-red-500/20", label: "CRITICAL" },
};

export const RISK_LEVEL_CONFIG: Record<string, { color: string; bg: string; border: string }> = {
  LOW: { color: "text-emerald-400", bg: "bg-emerald-500/15", border: "border-emerald-500/30" },
  MEDIUM: { color: "text-amber-400", bg: "bg-amber-500/15", border: "border-amber-500/30" },
  HIGH: { color: "text-orange-400", bg: "bg-orange-500/15", border: "border-orange-500/30" },
  CRITICAL: { color: "text-red-400", bg: "bg-red-500/15", border: "border-red-500/30" },
};
