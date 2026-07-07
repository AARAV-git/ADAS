// RoadSense AI — Backend API Client
// Dynamically resolves backend URL from the page's own hostname so that
// mobile phones on the same WiFi connect correctly (not localhost).

function resolveBaseUrl(): string {
  // Server-side: use env var or default
  if (typeof window === "undefined") {
    return (process.env.NEXT_PUBLIC_API_URL || "http://localhost:8000").replace(/\/$/, "");
  }
  // Client-side: if env var is explicitly set and non-localhost, use it
  const envUrl = process.env.NEXT_PUBLIC_API_URL?.replace(/\/$/, "");
  if (envUrl && !envUrl.includes("localhost") && !envUrl.includes("127.0.0.1")) {
    return envUrl;
  }
  // Otherwise derive from the page host — works for both localhost dev
  // AND mobile phones visiting via LAN IP (e.g. http://192.168.1.5:3000)
  const host = window.location.hostname;         // e.g. "192.168.1.5" or "localhost"
  const proto = window.location.protocol;        // "http:" or "https:"
  return `${proto}//${host}:8000`;
}

function resolveWsUrl(): string {
  if (typeof window === "undefined") return "ws://localhost:8000";
  const base = resolveBaseUrl();
  // Always use wss:// when page is served over https:// to avoid
  // "mixed content" browser errors on Vercel/production deployments
  const wsProto = window.location.protocol === "https:" ? "wss" : "ws";
  return base.replace(/^https?/, wsProto);
}

const BASE_URL = resolveBaseUrl();
const WS_BASE  = resolveWsUrl();

// ── URL helpers ──────────────────────────────────────────────────────────────
export const API = {
  // REST
  videos:           `${BASE_URL}/api/videos`,
  upload:           `${BASE_URL}/api/upload`,
  deleteVideo:      (name: string) => `${BASE_URL}/api/videos/${encodeURIComponent(name)}`,
  sessions:         `${BASE_URL}/api/sessions`,
  session:          (id: number) => `${BASE_URL}/api/sessions/${id}`,
  sessionTelemetry: (id: number) => `${BASE_URL}/api/sessions/${id}/telemetry`,
  sessionAlerts:    (id: number) => `${BASE_URL}/api/sessions/${id}/alerts`,
  deleteSession:    (id: number) => `${BASE_URL}/api/sessions/${id}`,
  statsOverview:    `${BASE_URL}/api/stats/overview`,
  explain:          `${BASE_URL}/api/explain`,
  networkInfo:      `${BASE_URL}/api/network-info`,

  // WebSocket — re-evaluated at call time so hostname is always current
  wsStream: (videoName: string) => `${resolveWsUrl()}/ws/stream/${encodeURIComponent(videoName)}`,
  wsCamera:  () => `${resolveWsUrl()}/ws/camera`,
};

// ── Typed helpers ────────────────────────────────────────────────────────────
import type { Session, StatsOverview, ExplainRequest, ExplainResponse } from "./types";

async function get<T>(url: string): Promise<T> {
  const res = await fetch(url);
  if (!res.ok) throw new Error(`GET ${url} → ${res.status} ${res.statusText}`);
  return res.json() as Promise<T>;
}

async function post<T>(url: string, body: unknown): Promise<T> {
  const res = await fetch(url, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(body),
  });
  if (!res.ok) throw new Error(`POST ${url} → ${res.status} ${res.statusText}`);
  return res.json() as Promise<T>;
}

async function del(url: string): Promise<void> {
  const res = await fetch(url, { method: "DELETE" });
  if (!res.ok) throw new Error(`DELETE ${url} → ${res.status} ${res.statusText}`);
}

// ── API functions ────────────────────────────────────────────────────────────
export const apiGetVideos   = ()          => get<string[]>(API.videos);
export const apiGetSessions = (limit = 20, offset = 0) =>
  get<Session[]>(`${API.sessions}?limit=${limit}&offset=${offset}`);
export const apiGetSession  = (id: number) => get<Session>(API.session(id));
export const apiGetStats    = ()          => get<StatsOverview>(API.statsOverview);
export const apiDeleteSession = (id: number) => del(API.deleteSession(id));
export const apiDeleteVideo   = (name: string) => del(API.deleteVideo(name));

export const apiExplain = (req: ExplainRequest) =>
  post<ExplainResponse>(API.explain, req);

export async function apiUploadVideo(
  file: File,
  onProgress?: (pct: number) => void
): Promise<{ filename: string; size_mb: number; message: string }> {
  return new Promise((resolve, reject) => {
    const xhr = new XMLHttpRequest();
    xhr.open("POST", API.upload);

    xhr.upload.onprogress = (e) => {
      if (e.lengthComputable && onProgress) {
        onProgress(Math.round((e.loaded / e.total) * 100));
      }
    };

    xhr.onload = () => {
      if (xhr.status >= 200 && xhr.status < 300) {
        resolve(JSON.parse(xhr.responseText));
      } else {
        reject(new Error(`Upload failed: ${xhr.statusText}`));
      }
    };

    xhr.onerror = () => reject(new Error("Network error during upload"));

    const fd = new FormData();
    fd.append("file", file);
    xhr.send(fd);
  });
}
