"use client";

import { motion } from "framer-motion";
import {
  useEffect, useRef, useState, useCallback, useImperativeHandle, forwardRef
} from "react";
import { Camera, FlipHorizontal, Maximize2, Pause, Play, StopCircle, Wifi, WifiOff } from "lucide-react";
import type { TrackedObject, Alert, ChaosData } from "@/lib/types";
import { API } from "@/lib/api";

interface VideoStreamProps {
  // Passed from parent (mock or real telemetry)
  chaos: ChaosData;
  tracked: TrackedObject[];
  alerts: Alert[];
  frameId: number;
  // Optional: live JPEG blob URL from /ws/stream
  frameUrl?: string | null;
  // If provided, show video-stream mode controls
  videoName?: string | null;
  onVideoSelect?: (name: string | null) => void;
  wsConnected?: boolean;
}

const OBJECT_COLORS: Record<string, string> = {
  car: "#fbbf24",
  motorcycle: "#f97316",
  pedestrian: "#ef4444",
  bicycle: "#22d3ee",
  truck: "#a78bfa",
  bus: "#34d399",
  rider: "#fb923c",
  auto_rickshaw: "#a3e635",
  vulnerable_road_user: "#f472b6",
};

export function VideoStream({
  chaos, tracked, alerts, frameId,
  frameUrl, wsConnected = false,
}: VideoStreamProps) {
  const canvasRef   = useRef<HTMLCanvasElement>(null);
  const imgRef      = useRef<HTMLImageElement | null>(null);
  const animRef     = useRef<number>(0);
  const frameRef    = useRef(0);
  const [isPlaying, setIsPlaying] = useState(true);

  // ── Draw mode: real JPEG from WS ─────────────────────────────────────────
  const drawFromJpeg = useCallback((url: string) => {
    const canvas = canvasRef.current;
    if (!canvas) return;
    const ctx = canvas.getContext("2d");
    if (!ctx) return;

    const img = imgRef.current || new Image();
    imgRef.current = img;
    img.onload = () => {
      canvas.width  = img.naturalWidth;
      canvas.height = img.naturalHeight;
      ctx.drawImage(img, 0, 0);
      frameRef.current++;
    };
    img.src = url;
  }, []);

  // ── Draw mode: simulated canvas (mock / overlay on camera) ───────────────
  const drawSimulated = useCallback(() => {
    const canvas = canvasRef.current;
    if (!canvas) return;
    const ctx = canvas.getContext("2d");
    if (!ctx) return;

    const w = canvas.width || 640;
    const h = canvas.height || 480;

    ctx.fillStyle = "#0a0a1a";
    ctx.fillRect(0, 0, w, h);

    // Grid
    ctx.strokeStyle = "rgba(255,255,255,0.03)";
    ctx.lineWidth = 1;
    for (let x = 0; x < w; x += 30) {
      ctx.beginPath(); ctx.moveTo(x, 0); ctx.lineTo(x, h); ctx.stroke();
    }
    for (let y = 0; y < h; y += 30) {
      ctx.beginPath(); ctx.moveTo(0, y); ctx.lineTo(w, y); ctx.stroke();
    }

    // Road
    const roadY = h * 0.35;
    const roadH = h * 0.5;
    ctx.fillStyle = "rgba(255,255,255,0.02)";
    ctx.fillRect(0, roadY, w, roadH);
    ctx.setLineDash([20, 20]);
    ctx.strokeStyle = "rgba(255,255,255,0.08)";
    ctx.lineWidth = 2;
    ctx.beginPath(); ctx.moveTo(0, roadY + roadH * 0.33); ctx.lineTo(w, roadY + roadH * 0.33); ctx.stroke();
    ctx.beginPath(); ctx.moveTo(0, roadY + roadH * 0.66); ctx.lineTo(w, roadY + roadH * 0.66); ctx.stroke();
    ctx.setLineDash([]);
    ctx.strokeStyle = "rgba(251,191,36,0.15)";
    ctx.lineWidth = 2;
    ctx.beginPath(); ctx.moveTo(0, roadY); ctx.lineTo(w, roadY); ctx.stroke();
    ctx.beginPath(); ctx.moveTo(0, roadY + roadH); ctx.lineTo(w, roadY + roadH); ctx.stroke();

    // Tracked bounding boxes
    tracked.forEach((obj) => {
      const color = OBJECT_COLORS[obj.label] || "#fbbf24";
      const sx = w / (obj.frame_w || 640);
      const sy = h / (obj.frame_h || 480);
      const bx = obj.bbox[0] * sx;
      const by = obj.bbox[1] * sy;
      const bw = (obj.bbox[2] - obj.bbox[0]) * sx;
      const bh = (obj.bbox[3] - obj.bbox[1]) * sy;

      ctx.strokeStyle = color; ctx.lineWidth = 2;
      ctx.strokeRect(bx, by, bw, bh);

      const cL = 8; ctx.lineWidth = 3;
      [[bx, by, 1, 0], [bx + bw, by, -1, 0], [bx, by + bh, 0, -1], [bx + bw, by + bh, -1, -1]].forEach(([x, y, dx, dy]) => {
        ctx.beginPath();
        ctx.moveTo(x as number, (y as number) + (dy as number) * cL);
        ctx.lineTo(x as number, y as number);
        ctx.lineTo((x as number) + (dx as number) * cL, y as number);
        ctx.stroke();
      });

      const lbl = `${obj.label} #${obj.track_id}`;
      ctx.font = "bold 10px monospace";
      const tw = ctx.measureText(lbl).width;
      ctx.fillStyle = color;
      ctx.fillRect(bx, by - 16, tw + 10, 16);
      ctx.fillStyle = "#000";
      ctx.fillText(lbl, bx + 5, by - 4);
      ctx.font = "9px monospace";
      ctx.fillStyle = "rgba(255,255,255,0.6)";
      ctx.fillText(`${(obj.conf * 100).toFixed(0)}%`, bx + tw + 14, by - 4);
    });

    // Alert banner
    if (alerts.length > 0) {
      ctx.fillStyle = "rgba(239,68,68,0.1)";
      ctx.fillRect(0, 0, w, 30);
      ctx.font = "bold 11px monospace";
      ctx.fillStyle = "#ef4444";
      ctx.textAlign = "left";
      ctx.fillText(`⚠ ${alerts.length} ALERT${alerts.length > 1 ? "S" : ""} DETECTED`, 10, 18);
    }

    // HUD
    ctx.font = "10px monospace";
    ctx.fillStyle = "rgba(255,255,255,0.5)";
    ctx.textAlign = "right";
    ctx.fillText(`FRAME: ${frameRef.current}`, w - 10, 18);
    ctx.fillText(`FPS: ${chaos.score > 0 ? "24.5" : "0.0"}`, w - 10, 32);

    const chaosColor = chaos.score < 30 ? "#34d399" : chaos.score < 60 ? "#fbbf24" : chaos.score < 80 ? "#f97316" : "#ef4444";
    ctx.textAlign = "left";
    ctx.fillStyle = "rgba(0,0,0,0.5)";
    ctx.fillRect(5, h - 28, 160, 23);
    ctx.fillStyle = chaosColor;
    ctx.font = "bold 11px monospace";
    ctx.fillText(`CHAOS: ${chaos.score.toFixed(1)} [${chaos.level.toUpperCase()}]`, 10, h - 12);

    ctx.textAlign = "right";
    ctx.fillStyle = "rgba(255,255,255,0.3)";
    ctx.font = "9px monospace";
    ctx.fillText(new Date().toLocaleTimeString(), w - 10, h - 12);
    ctx.textAlign = "left";

    // Scanline
    const scanY = (Date.now() / 20) % h;
    ctx.strokeStyle = "rgba(251,191,36,0.08)";
    ctx.lineWidth = 1;
    ctx.beginPath(); ctx.moveTo(0, scanY); ctx.lineTo(w, scanY); ctx.stroke();

    frameRef.current++;
  }, [tracked, alerts, chaos]);

  // ── Render loop ───────────────────────────────────────────────────────────
  useEffect(() => {
    if (frameUrl) {
      // Real JPEG from WS — draw it once per new URL
      drawFromJpeg(frameUrl);
      return;
    }

    if (!isPlaying) return;
    const animate = () => {
      drawSimulated();
      animRef.current = requestAnimationFrame(animate);
    };
    animRef.current = requestAnimationFrame(animate);
    return () => { if (animRef.current) cancelAnimationFrame(animRef.current); };
  }, [isPlaying, drawSimulated, drawFromJpeg, frameUrl]);

  const modeLabel = wsConnected ? "Live Stream" : "Simulated Preview";

  return (
    <motion.div
      initial={{ opacity: 0, y: 20 }}
      animate={{ opacity: 1, y: 0 }}
      transition={{ duration: 0.5, delay: 0.2 }}
      className="glass-card rounded-xl p-4 sm:p-5 border border-border/50"
    >
      <div className="flex items-center justify-between mb-3">
        <h3 className="text-sm font-semibold text-foreground uppercase tracking-wider flex items-center gap-2">
          <Camera className="w-4 h-4 text-amber-400" />
          {modeLabel}
          {wsConnected ? (
            <Wifi className="w-3.5 h-3.5 text-emerald-400" />
          ) : (
            <WifiOff className="w-3.5 h-3.5 text-muted-foreground" />
          )}
        </h3>
        <div className="flex items-center gap-2">
          <button
            onClick={() => setIsPlaying(!isPlaying)}
            className="p-1.5 rounded-md bg-background/50 text-muted-foreground hover:text-foreground transition-colors"
            title={isPlaying ? "Pause" : "Play"}
          >
            {isPlaying ? <Pause className="w-3.5 h-3.5" /> : <Play className="w-3.5 h-3.5" />}
          </button>
          <button
            className="p-1.5 rounded-md bg-background/50 text-muted-foreground hover:text-foreground transition-colors"
            title="Fullscreen"
            onClick={() => canvasRef.current?.requestFullscreen()}
          >
            <Maximize2 className="w-3.5 h-3.5" />
          </button>
        </div>
      </div>

      <div className="relative rounded-lg overflow-hidden border border-border/30 bg-black">
        <canvas
          ref={canvasRef}
          width={640}
          height={480}
          className="w-full h-auto aspect-[4/3]"
        />
        {isPlaying && (
          <div className="absolute top-3 left-3 flex items-center gap-1.5 px-2 py-1 rounded-md bg-red-500/20 border border-red-500/30">
            <div className="w-1.5 h-1.5 bg-red-500 rounded-full pulse-alert" />
            <span className="text-[10px] font-bold text-red-400 uppercase">
              {wsConnected ? "Live" : "Preview"}
            </span>
          </div>
        )}
        {wsConnected && (
          <div className="absolute top-3 right-3 px-2 py-1 rounded-md bg-emerald-500/20 border border-emerald-500/30">
            <span className="text-[10px] font-bold text-emerald-400">CONNECTED</span>
          </div>
        )}
      </div>

      {/* Tracked objects summary */}
      <div className="flex flex-wrap gap-2 mt-3">
        {tracked.map((obj, index) => (
          <div
            key={`${obj.track_id}-${obj.label}-${index}`}
            className="flex items-center gap-1.5 px-2 py-1 rounded-md bg-background/30 border border-border/30"
          >
            <div className="w-2 h-2 rounded-full" style={{ backgroundColor: OBJECT_COLORS[obj.label] || "#fbbf24" }} />
            <span className="text-[10px] text-muted-foreground">{obj.label} #{obj.track_id}</span>
            <span className="text-[10px] font-semibold text-foreground">{(obj.conf * 100).toFixed(0)}%</span>
          </div>
        ))}
        {tracked.length === 0 && (
          <span className="text-[10px] text-muted-foreground italic">No objects tracked</span>
        )}
      </div>
    </motion.div>
  );
}

// ── LiveCameraStream ─────────────────────────────────────────────────────────
// Streams device camera to /ws/camera, draws AI detection telemetry overlay
// Fully optimised for mobile phones (rear camera, flip, fullscreen, touch-friendly)
interface LiveCameraProps {
  onTelemetry: (t: import("@/lib/types").TelemetryFrame) => void;
}

export function LiveCameraStream({ onTelemetry }: LiveCameraProps) {
  const videoRef    = useRef<HTMLVideoElement>(null);
  const canvasRef   = useRef<HTMLCanvasElement>(null);   // hidden — encode frames
  const overlayRef  = useRef<HTMLCanvasElement>(null);   // visible — draw detections
  const wsRef       = useRef<WebSocket | null>(null);
  const timerRef    = useRef<ReturnType<typeof setInterval> | null>(null);
  const streamRef   = useRef<MediaStream | null>(null);
  const lastTelRef  = useRef<import("@/lib/types").TelemetryFrame | null>(null);
  const animRef     = useRef<number>(0);
  const fpsCountRef = useRef(0);
  const lastFpsTs   = useRef(Date.now());

  const [active, setActive]       = useState(false);
  const [connected, setConnected] = useState(false);
  const [error, setError]         = useState<string | null>(null);
  const [facing, setFacing]       = useState<"environment" | "user">("environment");
  const [fps, setFps]             = useState(0);
  const [networkUrl, setNetworkUrl] = useState<string | null>(null);

  // Fetch network info so user knows what URL to type on mobile
  useEffect(() => {
    fetch("/api/network-info", { signal: AbortSignal.timeout(3000) })
      .then(r => r.ok ? r.json() : null)
      .then((d: { local_ip?: string } | null) => {
        if (d?.local_ip) setNetworkUrl(`http://${d.local_ip}:3000`);
      })
      .catch(() => {});
  }, []);

  // Draw detection overlay on the visible canvas
  const drawOverlay = useCallback(() => {
    const tel = lastTelRef.current;
    const cnv = overlayRef.current;
    const vid = videoRef.current;
    if (!cnv || !vid) return;

    const w = vid.videoWidth  || cnv.offsetWidth  || 640;
    const h = vid.videoHeight || cnv.offsetHeight || 480;
    if (cnv.width !== w || cnv.height !== h) {
      cnv.width  = w;
      cnv.height = h;
    }
    const ctx = cnv.getContext("2d");
    if (!ctx) return;
    ctx.clearRect(0, 0, w, h);

    if (!tel) return;

    // Bounding boxes
    tel.tracked?.forEach((obj) => {
      const color = OBJECT_COLORS[obj.label] || "#fbbf24";
      const sx = w / (obj.frame_w || w);
      const sy = h / (obj.frame_h || h);
      const bx = obj.bbox[0] * sx;
      const by = obj.bbox[1] * sy;
      const bw = (obj.bbox[2] - obj.bbox[0]) * sx;
      const bh = (obj.bbox[3] - obj.bbox[1]) * sy;

      // Box
      ctx.strokeStyle = color;
      ctx.lineWidth   = 2;
      ctx.strokeRect(bx, by, bw, bh);

      // Corner accents
      const cL = 10;
      ctx.lineWidth = 3;
      [[bx, by, 1, 1], [bx + bw, by, -1, 1], [bx, by + bh, 1, -1], [bx + bw, by + bh, -1, -1]]
        .forEach(([x, y, dx, dy]) => {
          ctx.beginPath();
          ctx.moveTo(x as number, (y as number) + (dy as number) * cL);
          ctx.lineTo(x as number, y as number);
          ctx.lineTo((x as number) + (dx as number) * cL, y as number);
          ctx.stroke();
        });

      // Label
      const lbl = `${obj.label} #${obj.track_id}`;
      ctx.font = "bold 11px monospace";
      const tw  = ctx.measureText(lbl).width;
      ctx.fillStyle = color;
      ctx.fillRect(bx, by - 18, tw + 12, 18);
      ctx.fillStyle = "#000";
      ctx.fillText(lbl, bx + 6, by - 5);
    });

    // Alert banner
    const alerts = tel.alerts || [];
    if (alerts.length > 0) {
      ctx.fillStyle = "rgba(239,68,68,0.15)";
      ctx.fillRect(0, 0, w, 30);
      ctx.font = "bold 12px monospace";
      ctx.fillStyle = "#ef4444";
      ctx.textAlign = "left";
      ctx.fillText(`⚠ ${alerts.length} ALERT${alerts.length > 1 ? "S" : ""}`, 10, 20);
      ctx.textAlign = "start";
    }

    // Chaos HUD (bottom-left)
    const chaos = tel.chaos;
    if (chaos) {
      const chaosColor = chaos.score < 30 ? "#34d399" : chaos.score < 60 ? "#fbbf24" : "#ef4444";
      ctx.fillStyle = "rgba(0,0,0,0.55)";
      ctx.fillRect(6, h - 32, 180, 26);
      ctx.font = "bold 12px monospace";
      ctx.fillStyle = chaosColor;
      ctx.textAlign = "left";
      ctx.fillText(`CHAOS ${chaos.score.toFixed(0)} · ${chaos.level.toUpperCase()}`, 12, h - 14);
    }

    // FPS HUD (top-right)
    ctx.fillStyle = "rgba(0,0,0,0.5)";
    ctx.fillRect(w - 72, 4, 68, 22);
    ctx.font = "10px monospace";
    ctx.fillStyle = "rgba(255,255,255,0.7)";
    ctx.textAlign = "right";
    ctx.fillText(`${fps} fps sent`, w - 6, 18);
    ctx.textAlign = "start";
  }, [fps]);

  // Overlay animation loop
  useEffect(() => {
    if (!active) return;
    const loop = () => {
      drawOverlay();
      animRef.current = requestAnimationFrame(loop);
    };
    animRef.current = requestAnimationFrame(loop);
    return () => cancelAnimationFrame(animRef.current);
  }, [active, drawOverlay]);

  const stop = useCallback(() => {
    if (timerRef.current) clearInterval(timerRef.current);
    timerRef.current = null;
    wsRef.current?.close();
    wsRef.current = null;
    streamRef.current?.getTracks().forEach(t => t.stop());
    streamRef.current = null;
    cancelAnimationFrame(animRef.current);
    setActive(false);
    setConnected(false);
    setFps(0);
    lastTelRef.current = null;
    // Clear overlay
    const ctx = overlayRef.current?.getContext("2d");
    if (ctx && overlayRef.current) ctx.clearRect(0, 0, overlayRef.current.width, overlayRef.current.height);
  }, []);

  const startStream = useCallback(async (facingMode: "environment" | "user") => {
    setError(null);
    const vid = videoRef.current!;
    const cnv = canvasRef.current!;

    try {
      const stream = await navigator.mediaDevices.getUserMedia({
        video: { facingMode: { ideal: facingMode }, width: { ideal: 640 }, height: { ideal: 480 } },
        audio: false,
      });
      streamRef.current = stream;
      vid.srcObject = stream;
      await vid.play();
      setActive(true);
      setFacing(facingMode);

      // Dynamic WebSocket URL — auto-resolves to LAN IP for mobile
      const wsUrl = window.location.hostname === "localhost"
        ? `ws://localhost:8000/ws/camera`
        : `ws://${window.location.hostname}:8000/ws/camera`;

      const ws = new WebSocket(wsUrl);
      ws.binaryType = "arraybuffer";
      wsRef.current  = ws;

      ws.onopen = () => {
        setConnected(true);
        // 120ms interval = 8.3 fps — smooth and responsive on mobile CPU + WiFi
        timerRef.current = setInterval(() => {
          if (ws.readyState !== WebSocket.OPEN) return;
          const ctx = cnv.getContext("2d");
          if (!ctx) return;
          cnv.width  = vid.videoWidth  || 640;
          cnv.height = vid.videoHeight || 480;
          ctx.drawImage(vid, 0, 0, cnv.width, cnv.height);
          cnv.toBlob(blob => {
            if (blob && ws.readyState === WebSocket.OPEN) {
              blob.arrayBuffer().then(buf => ws.send(buf));
              fpsCountRef.current++;
              const now = Date.now();
              if (now - lastFpsTs.current >= 1000) {
                setFps(fpsCountRef.current);
                fpsCountRef.current = 0;
                lastFpsTs.current = now;
              }
            }
          }, "image/jpeg", 0.6);
        }, 120);
      };

      ws.onclose = () => setConnected(false);
      ws.onerror = () => {
        setError(
          `Cannot connect to backend at port 8000.\n` +
          `Make sure the server is running and your device is on the same WiFi network.`
        );
      };

      ws.onmessage = ev => {
        if (typeof ev.data === "string") {
          try {
            const tel = JSON.parse(ev.data) as import("@/lib/types").TelemetryFrame;
            lastTelRef.current = tel;
            onTelemetry(tel);
          } catch { /* */ }
        }
      };
    } catch (err) {
      const msg = err instanceof Error ? err.message : String(err);
      if (msg.includes("NotAllowedError") || msg.includes("Permission denied")) {
        setError("📵 Camera permission denied.\nGo to browser Settings → Site permissions → Camera and allow access.");
      } else if (msg.includes("NotFoundError")) {
        setError("📷 No camera found on this device.");
      } else if (msg.includes("OverconstrainedError")) {
        // Retry without ideal constraint
        try {
          const s = await navigator.mediaDevices.getUserMedia({ video: true, audio: false });
          streamRef.current = s;
          vid.srcObject = s;
          await vid.play();
          setActive(true);
          return;
        } catch { /* */ }
        setError(`Camera error: ${msg}`);
      } else {
        setError(`Camera error: ${msg}`);
      }
    }
  }, [onTelemetry]);

  const flipCamera = useCallback(async () => {
    const next = facing === "environment" ? "user" : "environment";
    stop();
    await new Promise(r => setTimeout(r, 300));
    startStream(next);
  }, [facing, stop, startStream]);

  useEffect(() => () => stop(), [stop]);

  return (
    <motion.div
      initial={{ opacity: 0, y: 20 }}
      animate={{ opacity: 1, y: 0 }}
      className="glass-card rounded-xl p-4 sm:p-5 border border-border/50"
    >
      {/* Header */}
      <div className="flex items-center justify-between mb-3">
        <h3 className="text-sm font-semibold text-foreground uppercase tracking-wider flex items-center gap-2">
          <Camera className="w-4 h-4 text-amber-400" />
          Live Camera
          {connected
            ? <Wifi className="w-3.5 h-3.5 text-emerald-400" />
            : <WifiOff className="w-3.5 h-3.5 text-muted-foreground" />
          }
        </h3>
        <div className="flex items-center gap-2">
          {active && (
            <button
              onClick={flipCamera}
              title="Flip camera"
              className="p-2 rounded-lg bg-background/50 border border-border/40 text-muted-foreground hover:text-amber-400 hover:border-amber-500/40 transition-all active:scale-95"
            >
              <FlipHorizontal className="w-4 h-4" />
            </button>
          )}
          {active && (
            <button
              onClick={() => overlayRef.current?.requestFullscreen()}
              title="Fullscreen"
              className="p-2 rounded-lg bg-background/50 border border-border/40 text-muted-foreground hover:text-foreground transition-all active:scale-95"
            >
              <Maximize2 className="w-4 h-4" />
            </button>
          )}
          {active ? (
            <button
              onClick={stop}
              className="flex items-center gap-1.5 px-3 py-1.5 rounded-lg bg-red-500/10 border border-red-500/30 text-red-400 text-xs font-medium hover:bg-red-500/20 transition-colors active:scale-95"
            >
              <StopCircle className="w-3.5 h-3.5" /> Stop
            </button>
          ) : (
            <button
              onClick={() => startStream("environment")}
              className="flex items-center gap-1.5 px-3 py-1.5 rounded-lg bg-amber-500/10 border border-amber-500/30 text-amber-400 text-xs font-medium hover:bg-amber-500/20 transition-colors active:scale-95"
            >
              <Camera className="w-3.5 h-3.5" /> Start Camera
            </button>
          )}
        </div>
      </div>

      {/* Network info tip — shown when not active */}
      {!active && networkUrl && (
        <div className="mb-3 p-3 rounded-lg bg-blue-500/10 border border-blue-500/30">
          <p className="text-[11px] text-blue-400 font-medium mb-0.5">📱 To use on mobile phone:</p>
          <p className="text-[11px] text-blue-300/80">
            Connect to the same WiFi, then open <span className="font-mono bg-blue-500/20 px-1 py-0.5 rounded">{networkUrl}</span> in Chrome or Safari.
          </p>
        </div>
      )}

      {/* Error */}
      {error && (
        <div className="mb-3 p-3 rounded-lg bg-red-500/10 border border-red-500/30 text-red-400 text-xs whitespace-pre-line">
          {error}
          <button
            onClick={() => setError(null)}
            className="ml-2 underline hover:no-underline"
          >dismiss</button>
        </div>
      )}

      {/* Camera viewport — video + overlay canvas stacked */}
      <div className="relative rounded-lg overflow-hidden border border-border/30 bg-black"
           style={{ minHeight: active ? undefined : "200px" }}>
        {/* Hidden canvas — used only for JPEG encoding */}
        <canvas ref={canvasRef} className="hidden" />

        {/* Video feed */}
        <video
          ref={videoRef}
          className="w-full h-auto block"
          style={{ maxHeight: "60vh", objectFit: "cover" }}
          muted
          playsInline
          autoPlay
        />

        {/* Transparent detection overlay — same size as video, absolute on top */}
        <canvas
          ref={overlayRef}
          className="absolute inset-0 w-full h-full pointer-events-none"
          style={{ objectFit: "cover" }}
        />

        {/* Placeholder when camera is off */}
        {!active && (
          <div className="absolute inset-0 flex flex-col items-center justify-center gap-3 bg-background/80">
            <div className="p-4 rounded-full bg-amber-500/10 border border-amber-500/20">
              <Camera className="w-10 h-10 text-amber-400/60" />
            </div>
            <p className="text-muted-foreground text-sm text-center px-4">
              Press <span className="text-amber-400 font-medium">Start Camera</span> to begin live ADAS analysis
            </p>
            <p className="text-[11px] text-muted-foreground/60 text-center px-6">
              Uses your device&apos;s rear camera and sends frames to the AI backend every 400ms
            </p>
          </div>
        )}

        {/* LIVE badge */}
        {connected && (
          <div className="absolute top-3 left-3 flex items-center gap-1.5 px-2 py-1 rounded-md bg-red-500/20 border border-red-500/30 backdrop-blur-sm">
            <div className="w-1.5 h-1.5 bg-red-500 rounded-full pulse-alert" />
            <span className="text-[10px] font-bold text-red-400 uppercase">LIVE · AI</span>
          </div>
        )}

        {/* Connecting badge */}
        {active && !connected && (
          <div className="absolute top-3 left-3 px-2 py-1 rounded-md bg-yellow-500/20 border border-yellow-500/30 backdrop-blur-sm">
            <span className="text-[10px] font-bold text-yellow-400 animate-pulse">Connecting…</span>
          </div>
        )}

        {/* Camera facing badge */}
        {active && (
          <div className="absolute top-3 right-3 px-2 py-1 rounded-md bg-background/50 border border-border/40 backdrop-blur-sm">
            <span className="text-[10px] text-muted-foreground">
              {facing === "environment" ? "🔭 Rear" : "🤳 Front"}
            </span>
          </div>
        )}
      </div>

      {/* Stats strip */}
      {active && (
        <div className="flex items-center gap-3 mt-3 text-[11px] text-muted-foreground">
          <span>📡 Sending <strong className="text-foreground">{fps} fps</strong> to backend</span>
          <span>·</span>
          <span>640 × 480 · JPEG 60%</span>
          <span>·</span>
          <span className={connected ? "text-emerald-400" : "text-yellow-400"}>
            {connected ? "✓ WS Connected" : "⏳ Connecting"}
          </span>
        </div>
      )}
    </motion.div>
  );
}

