"use client";

// RoadSense AI — useBackend hook
// Manages WebSocket connections to /ws/stream/{video} and /ws/camera
// Plus REST polling for sessions/stats

import { useCallback, useEffect, useRef, useState } from "react";
import { API } from "@/lib/api";
import type { TelemetryFrame, Session, StatsOverview } from "@/lib/types";
import {
  generateStatsOverview,
  generateSessions,
  generateTelemetryHistory,
} from "@/lib/mock-data";

// ── Stream hook ──────────────────────────────────────────────────────────────
// Connects to /ws/stream/{videoName}
// Protocol: server sends JSON text → binary JPEG → repeat
// Each frame is scheduled to display at its correct video timestamp so the
// stream plays at original speed regardless of backend processing rate.
export function useVideoStream(videoName: string | null) {
  const wsRef   = useRef<WebSocket | null>(null);
  const [telemetry, setTelemetry] = useState<TelemetryFrame | null>(null);
  const [frameUrl, setFrameUrl]   = useState<string | null>(null);
  const [connected, setConnected] = useState(false);

  const pendingJsonRef      = useRef<TelemetryFrame | null>(null);
  const prevBlobRef         = useRef<string | null>(null);
  const streamStartWallRef  = useRef<number>(0);   // performance.now() when first frame displayed
  const streamStartVidMsRef = useRef<number>(0);   // video timestamp of the first frame (ms)
  const fpsRef              = useRef<number>(25);  // updated from source_fps in telemetry
  
  const queueRef            = useRef<{ url: string; meta: TelemetryFrame; videoMs: number }[]>([]);
  const animFrameIdRef      = useRef<number | null>(null);

  const disconnect = useCallback(() => {
    wsRef.current?.close();
    wsRef.current = null;
    if (animFrameIdRef.current !== null) {
      cancelAnimationFrame(animFrameIdRef.current);
      animFrameIdRef.current = null;
    }
    // Revoke all pending URLs in the queue
    queueRef.current.forEach((item) => {
      URL.revokeObjectURL(item.url);
    });
    queueRef.current = [];
    // Revoke the currently displayed URL
    if (prevBlobRef.current) {
      URL.revokeObjectURL(prevBlobRef.current);
      prevBlobRef.current = null;
    }
    setConnected(false);
  }, []);

  useEffect(() => {
    if (!videoName) { disconnect(); return; }

    // Reset timing for fresh stream
    streamStartWallRef.current  = 0;
    streamStartVidMsRef.current = 0;

    // Tick function to poll and draw frames according to their video timestamps
    const tick = () => {
      const now = performance.now();
      const queue = queueRef.current;
      
      if (queue.length > 0) {
        // Anchor the stream clock if not already done
        if (streamStartWallRef.current === 0) {
          streamStartWallRef.current = now;
          streamStartVidMsRef.current = queue[0].videoMs;
        }

        // Find the latest frame that is ready to be displayed
        let lastReadyIdx = -1;
        for (let i = 0; i < queue.length; i++) {
          const scheduledWall = streamStartWallRef.current + (queue[i].videoMs - streamStartVidMsRef.current);
          if (scheduledWall <= now) {
            lastReadyIdx = i;
          } else {
            break; // Since queue is chronologically ordered, we can stop
          }
        }

        if (lastReadyIdx >= 0) {
          const readyFrame = queue[lastReadyIdx];

          // Revoke the previous frame's URL if different
          if (prevBlobRef.current && prevBlobRef.current !== readyFrame.url) {
            URL.revokeObjectURL(prevBlobRef.current);
          }
          prevBlobRef.current = readyFrame.url;

          // Revoke any skipped frames
          for (let i = 0; i < lastReadyIdx; i++) {
            if (queue[i].url !== prevBlobRef.current) {
              URL.revokeObjectURL(queue[i].url);
            }
          }

          // Display the frame and update metadata
          setFrameUrl(readyFrame.url);
          setTelemetry(readyFrame.meta);

          // Keep remaining frames in the queue
          queueRef.current = queue.slice(lastReadyIdx + 1);
        }
      }

      animFrameIdRef.current = requestAnimationFrame(tick);
    };

    // Start playback loop
    animFrameIdRef.current = requestAnimationFrame(tick);

    const ws = new WebSocket(API.wsStream(videoName));
    ws.binaryType = "arraybuffer";
    wsRef.current = ws;

    ws.onopen  = () => setConnected(true);
    ws.onclose = () => setConnected(false);
    ws.onerror = (e) => console.error("[WS Stream] error", e);

    ws.onmessage = (event) => {
      if (typeof event.data === "string") {
        try {
          pendingJsonRef.current = JSON.parse(event.data) as TelemetryFrame;
          // Grab the true video FPS from the first telemetry message
          const fps = (pendingJsonRef.current as any)?.source_fps;
          if (fps && fps > 0) fpsRef.current = fps;
        } catch {
          console.warn("[WS Stream] Invalid JSON", event.data);
        }
      } else {
        // Binary JPEG arrives after its JSON header
        const meta = pendingJsonRef.current;
        pendingJsonRef.current = null;
        if (!meta) return;

        // Create the blob URL
        const blob = new Blob([event.data], { type: "image/jpeg" });
        const url  = URL.createObjectURL(blob);

        // Convert frame_id to its video timestamp (ms)
        const videoMs = (meta.frame_id / fpsRef.current) * 1000;

        // Queue the frame
        queueRef.current.push({ url, meta, videoMs });
      }
    };

    return () => {
      ws.close();
      if (animFrameIdRef.current !== null) {
        cancelAnimationFrame(animFrameIdRef.current);
        animFrameIdRef.current = null;
      }
      queueRef.current.forEach((item) => {
        URL.revokeObjectURL(item.url);
      });
      queueRef.current = [];
      if (prevBlobRef.current) {
        URL.revokeObjectURL(prevBlobRef.current);
        prevBlobRef.current = null;
      }
    };
  }, [videoName, disconnect]);

  return { telemetry, frameUrl, connected, disconnect };
}

// ── Camera hook ──────────────────────────────────────────────────────────────
// Sends JPEG frames from device camera → /ws/camera
// Receives JSON telemetry back. No JPEG returned (server processes only).
export function useCameraStream() {
  const wsRef      = useRef<WebSocket | null>(null);
  const streamRef  = useRef<MediaStream | null>(null);
  const videoRef   = useRef<HTMLVideoElement | null>(null);
  const canvasRef  = useRef<HTMLCanvasElement | null>(null);
  const timerRef   = useRef<ReturnType<typeof setInterval> | null>(null);

  const [telemetry, setTelemetry] = useState<TelemetryFrame | null>(null);
  const [connected, setConnected] = useState(false);
  const [cameraActive, setCameraActive] = useState(false);
  const [facingMode, setFacingMode] = useState<"environment" | "user">("environment");
  const [error, setError] = useState<string | null>(null);
  const [fps, setFps] = useState(0);
  const frameCountRef = useRef(0);
  const lastFpsRef    = useRef(Date.now());

  const stop = useCallback(() => {
    if (timerRef.current) clearInterval(timerRef.current);
    timerRef.current = null;
    wsRef.current?.close();
    wsRef.current = null;
    streamRef.current?.getTracks().forEach((t) => t.stop());
    streamRef.current = null;
    setCameraActive(false);
    setConnected(false);
    setFps(0);
  }, []);

  const start = useCallback(async (
    vidEl: HTMLVideoElement,
    cnvEl: HTMLCanvasElement,
    facing: "environment" | "user" = "environment"
  ) => {
    setError(null);
    try {
      // Request camera — prefer rear for ADAS use, respect the facing argument
      const stream = await navigator.mediaDevices.getUserMedia({
        video: {
          facingMode: { ideal: facing },
          width:  { ideal: 640 },
          height: { ideal: 480 },
        },
        audio: false,
      });
      streamRef.current = stream;
      vidEl.srcObject  = stream;
      videoRef.current = vidEl;
      canvasRef.current = cnvEl;
      await vidEl.play();
      setCameraActive(true);
      setFacingMode(facing);

      const ws = new WebSocket(API.wsCamera());    // dynamic URL — works on mobile WiFi
      ws.binaryType = "arraybuffer";
      wsRef.current  = ws;

      ws.onopen  = () => {
        setConnected(true);
        // 120ms = 8.3fps: safe and responsive on mobile CPU + WiFi bandwidth
        timerRef.current = setInterval(() => {
          if (ws.readyState !== WebSocket.OPEN) return;
          const ctx = cnvEl.getContext("2d");
          if (!ctx) return;
          cnvEl.width  = vidEl.videoWidth  || 640;
          cnvEl.height = vidEl.videoHeight || 480;
          ctx.drawImage(vidEl, 0, 0, cnvEl.width, cnvEl.height);
          cnvEl.toBlob((blob) => {
            if (blob && ws.readyState === WebSocket.OPEN) {
              blob.arrayBuffer().then((buf) => ws.send(buf));
              // Track FPS
              frameCountRef.current++;
              const now = Date.now();
              if (now - lastFpsRef.current >= 1000) {
                setFps(frameCountRef.current);
                frameCountRef.current = 0;
                lastFpsRef.current = now;
              }
            }
          }, "image/jpeg", 0.6);   // 0.6 quality: good enough, saves mobile bandwidth
        }, 120);
      };

      ws.onclose = () => { setConnected(false); setCameraActive(false); };
      ws.onerror = () => setError(
        window.location.protocol === "https:"
          ? "WebSocket connection failed. Ensure the backend is running."
          : "WebSocket connection failed. On iOS Safari, the page must be served over HTTPS for camera access."
      );

      ws.onmessage = (event) => {
        if (typeof event.data === "string") {
          try {
            setTelemetry(JSON.parse(event.data) as TelemetryFrame);
          } catch { /* ignore */ }
        }
      };
    } catch (err) {
      const msg = err instanceof Error ? err.message : String(err);
      if (msg.includes("NotAllowedError") || msg.includes("Permission")) {
        setError("Camera permission denied. Please allow camera access in your browser settings.");
      } else if (msg.includes("NotFoundError") || msg.includes("DevicesNotFoundError")) {
        setError("No camera found on this device.");
      } else if (msg.includes("OverconstrainedError")) {
        // Retry without facingMode constraint (some Android browsers are strict)
        try {
          const stream = await navigator.mediaDevices.getUserMedia({ video: true, audio: false });
          streamRef.current = stream;
          vidEl.srcObject = stream;
          await vidEl.play();
          setCameraActive(true);
          return;
        } catch { /* fall through */ }
        setError(`Camera error: ${msg}`);
      } else {
        setError(`Camera error: ${msg}`);
      }
    }
  }, []);

  const toggleFacing = useCallback(async (
    vidEl: HTMLVideoElement,
    cnvEl: HTMLCanvasElement
  ) => {
    const next = facingMode === "environment" ? "user" : "environment";
    stop();
    // Brief delay so old tracks release before new stream opens
    await new Promise(r => setTimeout(r, 300));
    start(vidEl, cnvEl, next);
  }, [facingMode, stop, start]);

  useEffect(() => () => stop(), [stop]);

  return { telemetry, connected, cameraActive, facingMode, fps, error, start, stop, toggleFacing };
}


// Deterministic empty initial values — avoids SSR/client Math.random() mismatch
const EMPTY_STATS: StatsOverview = {
  total_sessions: 0,
  total_frames: 0,
  total_alerts: 0,
  avg_chaos_score: 0,
  top_risk_level: "LOW",
  alert_breakdown: {},
  top_classes: [],
};

// ── Stats & Sessions polling ─────────────────────────────────────────────────
export function useStats(intervalMs = 30_000) {
  const [stats, setStats]       = useState<StatsOverview>(EMPTY_STATS);
  const [sessions, setSessions] = useState<Session[]>([]);
  const [loading, setLoading]   = useState(false);

  // Seed mock data only on the client (avoids SSR hydration mismatch)
  useEffect(() => {
    setStats(generateStatsOverview());
    setSessions(generateSessions());
  }, []);

  const refresh = useCallback(async () => {
    setLoading(true);
    try {
      const [s, ss] = await Promise.all([
        fetch(`${API.statsOverview}`).then(r => r.ok ? r.json() : null),
        fetch(`${API.sessions}?limit=50`).then(r => r.ok ? r.json() : null),
      ]);
      if (s)  setStats(s);
      if (ss) setSessions(ss);
    } catch {
      // silently fall back to mock data already shown
    } finally {
      setLoading(false);
    }
  }, []);

  useEffect(() => {
    refresh();
    const id = setInterval(refresh, intervalMs);
    return () => clearInterval(id);
  }, [refresh, intervalMs]);

  return { stats, sessions, loading, refresh };
}

// ── Telemetry history for a finished session ─────────────────────────────────
export function useSessionTelemetry(sessionId: number | null) {
  const [history, setHistory] = useState<any[]>([]);

  // Seed mock data client-side only
  useEffect(() => {
    setHistory(generateTelemetryHistory());
  }, []);

  useEffect(() => {
    if (!sessionId) return;
    fetch(API.sessionTelemetry(sessionId))
      .then(r => r.ok ? r.json() : null)
      .then(data => { if (data) setHistory(data); })
      .catch(() => {});
  }, [sessionId]);

  return history;
}
