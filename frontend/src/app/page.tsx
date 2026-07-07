"use client";

import { useState, useEffect, useCallback } from "react";
import { motion, AnimatePresence } from "framer-motion";
import { LayoutDashboard, Radio, Database, Brain, Play, Square, RefreshCw, Camera } from "lucide-react";
import { Header } from "@/components/dashboard/Header";
import { StatsCards } from "@/components/dashboard/StatsCards";
import { ChaosGauge } from "@/components/dashboard/ChaosGauge";
import { AlertFeed } from "@/components/dashboard/AlertFeed";
import { TelemetryChart } from "@/components/dashboard/TelemetryChart";
import { VideoStream, LiveCameraStream } from "@/components/dashboard/VideoStream";
import { SessionTable, VideoUpload } from "@/components/dashboard/SessionTable";
import { AIExplainPanel } from "@/components/dashboard/AIExplainPanel";
import { DetectionBreakdown } from "@/components/dashboard/DetectionBreakdown";
import { useStats, useVideoStream } from "@/hooks/useBackend";
import { apiGetVideos } from "@/lib/api";
import {
  generateChaosData,
  generateAlert,
  generateTrackedObject,
  generateTelemetryHistory,
} from "@/lib/mock-data";
import type { Alert, ChaosData, TrackedObject, Session } from "@/lib/types";

type TabId = "overview" | "live" | "history" | "ai";

const TABS: { id: TabId; label: string; icon: React.ComponentType<{ className?: string }> }[] = [
  { id: "overview",  label: "Overview",          icon: LayoutDashboard },
  { id: "live",      label: "Live Stream",        icon: Radio           },
  { id: "history",   label: "Sessions & Uploads", icon: Database        },
  { id: "ai",        label: "AI Analysis",        icon: Brain           },
];

// Deterministic "calm" initial chaos — identical on server and client
const INITIAL_CHAOS: ChaosData = {
  score: 0,
  level: "Calm",
  breakdown: { vehicle_density: 0, speed_variance: 0, lane_intrusion: 0, pedestrian_density: 0 },
};

export default function Home() {
  // ── ALL HOOKS MUST BE AT THE TOP — no conditionals before hooks ─────────────
  const [mounted, setMounted] = useState(false);

  const [activeTab, setActiveTab]         = useState<TabId>("overview");
  const [availableVideos, setAvailableVideos] = useState<string[]>([]);
  const [selectedVideo, setSelectedVideo]     = useState<string | null>(null);
  const [activeSession, setActiveSession]     = useState<Session | null>(null);
  const [cameraActive, setCameraActive]       = useState(false);

  // Deterministic initial state — matches SSR
  const [chaos, setChaos]               = useState<ChaosData>(INITIAL_CHAOS);
  const [tracked, setTracked]           = useState<TrackedObject[]>([]);
  const [alerts, setAlerts]             = useState<Alert[]>([]);
  const [telemetryHistory, setTelemetryHistory] = useState<any[]>([]);
  const [frameId, setFrameId]           = useState(0);

  // Real backend data (internally uses deterministic empty initial state)
  const { stats, sessions, loading: statsLoading, refresh: refreshStats } = useStats();

  // WebSocket stream — only connects when selectedVideo is non-null
  const {
    telemetry: streamTelemetry,
    frameUrl: streamFrameUrl,
    connected: streamConnected,
    disconnect: disconnectStream,
  } = useVideoStream(selectedVideo);

  const [mountError, setMountError] = useState<string | null>(null);

  // ── Client-only mount effect ────────────────────────────────────────────────
  useEffect(() => {
    const handleErr = (e: ErrorEvent) => {
      setMountError(`${e.message} (${e.filename}:${e.lineno}:${e.colno})`);
    };
    const handleRej = (e: PromiseRejectionEvent) => {
      setMountError(`Unhandled Promise Rejection: ${String(e.reason)}`);
    };
    window.addEventListener("error", handleErr);
    window.addEventListener("unhandledrejection", handleRej);

    setMounted(true);
    // Seed simulation data client-side ONLY (avoids SSR/client Math.random() mismatch)
    setChaos(generateChaosData());
    setTelemetryHistory(generateTelemetryHistory());

    return () => {
      window.removeEventListener("error", handleErr);
      window.removeEventListener("unhandledrejection", handleRej);
    };
  }, []);

  // ── Load available videos from backend (no auto-connect) ───────────────────
  const loadVideos = useCallback(async () => {
    try {
      const vids = await apiGetVideos();
      setAvailableVideos(vids);
      // Deliberately NOT auto-selecting – user must click "Start Stream"
    } catch {
      // backend not reachable – silent fallback
    }
  }, []);

  useEffect(() => {
    if (mounted) loadVideos();
  }, [mounted, loadVideos]);

  // ── Handle real-time stream telemetry ──────────────────────────────────────
  useEffect(() => {
    if (!streamConnected || !streamTelemetry) return;
    setChaos(streamTelemetry.chaos);
    setTracked(streamTelemetry.tracked);
    setFrameId(streamTelemetry.frame_id);

    if (streamTelemetry.alerts?.length > 0) {
      setAlerts((prev) => {
        const fresh = streamTelemetry.alerts.filter(
          (a: Alert) => !prev.some((p) => p.track_id === a.track_id && p.risk_type === a.risk_type)
        );
        return [...fresh, ...prev].slice(0, 50);
      });
    }

    setTelemetryHistory((prev) => {
      const newEntry = {
        frame_id:     streamTelemetry.frame_id,
        chaos_score:  streamTelemetry.chaos.score,
        fps:          streamTelemetry.fps || 24.5,
        alert_count:  streamTelemetry.alerts?.length || 0,
        object_count: streamTelemetry.tracked?.length || 0,
      };
      return [...prev.slice(1), newEntry];
    });
  }, [streamTelemetry, streamConnected]);

  // ── Handle live camera telemetry ───────────────────────────────────────────
  const handleCameraTelemetry = useCallback((t: any) => {
    setChaos(t.chaos);
    setTracked(t.tracked);
    setFrameId(t.frame_id);
    if (t.alerts?.length > 0) {
      setAlerts((prev) => {
        const fresh = t.alerts.filter(
          (a: any) => !prev.some((p: any) => p.track_id === a.track_id && p.risk_type === a.risk_type)
        );
        return [...fresh, ...prev].slice(0, 50);
      });
    }
    setTelemetryHistory((prev) => {
      const newEntry = {
        frame_id:     t.frame_id,
        chaos_score:  t.chaos.score,
        fps:          t.fps || 15.0,
        alert_count:  t.alerts?.length || 0,
        object_count: t.tracked?.length || 0,
      };
      return [...prev.slice(1), newEntry];
    });
  }, []);

  // ── Local simulation when no live source is active ────────────────────────
  useEffect(() => {
    if (!mounted || streamConnected || cameraActive) return;

    const id = setInterval(() => {
      const newChaos = generateChaosData();
      setChaos(newChaos);
      setFrameId((f) => f + 1);

      if (Math.random() > 0.4) {
        setTracked((prev) => {
          const count = Math.max(1, Math.min(6, prev.length + (Math.random() > 0.5 ? 1 : -1)));
          return Array.from({ length: count }, () => generateTrackedObject());
        });
      }

      if (newChaos.level !== "Calm" && newChaos.level !== "Low" && Math.random() > 0.65) {
        setAlerts((prev) => [generateAlert(), ...prev].slice(0, 20));
      }

      setTelemetryHistory((prev) => {
        const last = prev[prev.length - 1] || { frame_id: 0 };
        return [
          ...prev.slice(1),
          {
            frame_id:     last.frame_id + 1,
            chaos_score:  newChaos.score,
            fps:          15 + Math.random() * 10,
            alert_count:  newChaos.level !== "Calm" && newChaos.level !== "Low" ? Math.floor(Math.random() * 3) : 0,
            object_count: Math.floor(Math.random() * 5) + 1,
          },
        ];
      });
    }, 2000);

    return () => clearInterval(id);
  }, [mounted, streamConnected, cameraActive]);

  // ── Stream toggle ──────────────────────────────────────────────────────────
  const toggleStream = () => {
    if (streamConnected) {
      disconnectStream();
      setSelectedVideo(null);
    } else {
      if (selectedVideo) {
        // trigger reconnect by resetting same video name
        setSelectedVideo((v) => v);
      } else if (availableVideos.length > 0) {
        setSelectedVideo(availableVideos[0]);
      } else {
        alert("No videos available. Please upload a video first in the Sessions tab.");
      }
    }
  };

  // ── Render guard — show spinner during SSR / first paint ──────────────────
  if (mountError) {
    return (
      <div className="min-h-screen flex items-center justify-center bg-background p-6">
        <div className="max-w-md w-full p-5 rounded-xl bg-red-500/10 border border-red-500/30 text-red-400 space-y-3">
          <div className="flex items-center gap-2">
            <div className="w-2 h-2 rounded-full bg-red-500 animate-pulse" />
            <h2 className="text-sm font-bold uppercase tracking-wider">JavaScript Execution Crash</h2>
          </div>
          <p className="text-xs font-mono break-all whitespace-pre-wrap leading-relaxed">{mountError}</p>
          <div className="pt-2 border-t border-red-500/20 text-[10px] text-muted-foreground">
            Please screenshot this error screen and report it.
          </div>
        </div>
      </div>
    );
  }

  if (!mounted) {
    return (
      <div className="min-h-screen flex items-center justify-center bg-background">
        <div className="flex flex-col items-center gap-3">
          <div className="w-8 h-8 border-2 border-amber-500 border-t-transparent rounded-full animate-spin" />
          <span className="text-sm text-muted-foreground tracking-wider">Initializing RoadSense AI...</span>
        </div>
      </div>
    );
  }

  // ── Full Dashboard ─────────────────────────────────────────────────────────
  return (
    <div className="min-h-screen flex flex-col bg-background grid-pattern">
      <Header />

      {/* Tab Navigation */}
      <nav className="sticky top-16 z-40 glass-card border-b border-border/50">
        <div className="max-w-[1600px] mx-auto px-4 sm:px-6">
          <div className="flex items-center justify-between py-2">
            <div className="flex items-center gap-1 overflow-x-auto scrollbar-none">
              {TABS.map((tab) => (
                <button
                  key={tab.id}
                  onClick={() => {
                    setActiveTab(tab.id);
                    if (tab.id !== "live") setCameraActive(false);
                  }}
                  className={`flex items-center gap-2 px-4 py-2 rounded-lg text-xs font-medium transition-all whitespace-nowrap ${
                    activeTab === tab.id
                      ? "bg-amber-500/10 text-amber-400 border border-amber-500/20"
                      : "text-muted-foreground hover:text-foreground hover:bg-background/50"
                  }`}
                >
                  <tab.icon className="w-3.5 h-3.5" />
                  {tab.label}
                </button>
              ))}
            </div>

            {/* Quick Stream Controls */}
            <div className="hidden sm:flex items-center gap-2">
              {availableVideos.length > 0 && (
                <select
                  value={selectedVideo || ""}
                  onChange={(e) => {
                    if (streamConnected) disconnectStream();
                    setSelectedVideo(e.target.value || null);
                  }}
                  className="bg-background/50 text-[10px] text-foreground border border-border/50 rounded px-2 py-1 focus:outline-none focus:border-amber-500/50"
                >
                  <option value="">-- Select Video --</option>
                  {availableVideos.map((vid) => (
                    <option key={vid} value={vid}>{vid}</option>
                  ))}
                </select>
              )}

              <button
                onClick={toggleStream}
                className={`flex items-center gap-1 px-3 py-1 rounded text-xs font-medium border transition-colors ${
                  streamConnected
                    ? "bg-red-500/10 border-red-500/30 text-red-400 hover:bg-red-500/20"
                    : "bg-amber-500/10 border-amber-500/30 text-amber-400 hover:bg-amber-500/20"
                }`}
              >
                {streamConnected
                  ? <><Square className="w-3 h-3" /> Stop</>
                  : <><Play  className="w-3 h-3" /> Stream</>}
              </button>

              <button
                onClick={refreshStats}
                disabled={statsLoading}
                className="p-1.5 rounded-lg border border-border/30 hover:bg-background/50 transition-colors text-muted-foreground hover:text-foreground"
                title="Refresh statistics"
              >
                <RefreshCw className={`w-3.5 h-3.5 ${statsLoading ? "animate-spin" : ""}`} />
              </button>
            </div>
          </div>
        </div>
      </nav>

      {/* Main Content */}
      <main className="flex-1 max-w-[1600px] mx-auto w-full px-4 sm:px-6 py-6">
        <AnimatePresence mode="wait">

          {activeTab === "overview" && (
            <motion.div key="overview"
              initial={{ opacity: 0, y: 10 }} animate={{ opacity: 1, y: 0 }}
              exit={{ opacity: 0, y: -10 }} transition={{ duration: 0.3 }}
              className="space-y-6"
            >
              <StatsCards stats={stats} />
              <div className="grid grid-cols-1 lg:grid-cols-3 gap-4 sm:gap-6">
                <div className="lg:col-span-2">
                  <VideoStream chaos={chaos} tracked={tracked} alerts={alerts.slice(0, 3)}
                    frameId={frameId} frameUrl={streamFrameUrl} wsConnected={streamConnected} />
                </div>
                <div className="space-y-4 sm:space-y-6">
                  <ChaosGauge chaos={chaos} />
                  <AlertFeed alerts={alerts} maxVisible={5} />
                </div>
              </div>
              <div className="grid grid-cols-1 lg:grid-cols-2 gap-4 sm:gap-6">
                <TelemetryChart data={telemetryHistory} />
                <DetectionBreakdown stats={stats} />
              </div>
            </motion.div>
          )}

          {activeTab === "live" && (
            <motion.div key="live"
              initial={{ opacity: 0, y: 10 }} animate={{ opacity: 1, y: 0 }}
              exit={{ opacity: 0, y: -10 }} transition={{ duration: 0.3 }}
              className="space-y-6"
            >
              <div className="grid grid-cols-1 lg:grid-cols-3 gap-4 sm:gap-6">
                <div className="lg:col-span-2">
                  {cameraActive
                    ? <LiveCameraStream onTelemetry={handleCameraTelemetry} />
                    : <VideoStream chaos={chaos} tracked={tracked} alerts={alerts}
                        frameId={frameId} frameUrl={streamFrameUrl} wsConnected={streamConnected} />
                  }
                </div>

                {/* Stream Control Panel */}
                <div className="glass-card rounded-xl p-4 sm:p-5 border border-border/50 space-y-4">
                  <h4 className="text-xs font-semibold uppercase tracking-wider text-amber-400">
                    Live Stream Control
                  </h4>
                  <p className="text-xs text-muted-foreground leading-relaxed">
                    Stream a pre-uploaded video through the ADAS pipeline, or capture live camera footage to detect and track objects in real time.
                  </p>

                  <div className="flex flex-col gap-2">
                    <button
                      onClick={() => { disconnectStream(); setCameraActive(true); }}
                      className={`w-full flex items-center justify-center gap-2 py-2.5 rounded-lg text-xs font-medium transition-colors ${
                        cameraActive
                          ? "bg-amber-400 text-black font-semibold"
                          : "bg-background/40 hover:bg-background/60 border border-border/50 text-foreground"
                      }`}
                    >
                      <Camera className="w-3.5 h-3.5" /> Mobile / Device Camera
                    </button>

                    <button
                      onClick={() => setCameraActive(false)}
                      className={`w-full flex items-center justify-center gap-2 py-2.5 rounded-lg text-xs font-medium transition-colors ${
                        !cameraActive
                          ? "bg-amber-400 text-black font-semibold"
                          : "bg-background/40 hover:bg-background/60 border border-border/50 text-foreground"
                      }`}
                    >
                      <Radio className="w-3.5 h-3.5" /> File-based Stream
                    </button>
                  </div>

                  {!cameraActive && (
                    <div className="pt-2 border-t border-border/20 space-y-2">
                      <label className="text-[10px] uppercase font-semibold text-muted-foreground">
                        Select Video File
                      </label>
                      {availableVideos.length === 0 ? (
                        <p className="text-[10px] text-muted-foreground italic">
                          No videos uploaded yet. Use the Sessions tab to upload one.
                        </p>
                      ) : (
                        <select
                          value={selectedVideo || ""}
                          onChange={(e) => { if (streamConnected) disconnectStream(); setSelectedVideo(e.target.value || null); }}
                          className="w-full bg-background border border-border/40 rounded p-1.5 text-xs text-foreground focus:outline-none focus:border-amber-500/50"
                        >
                          <option value="">-- Select File --</option>
                          {availableVideos.map((vid) => (
                            <option key={vid} value={vid}>{vid}</option>
                          ))}
                        </select>
                      )}
                      <button
                        onClick={toggleStream}
                        disabled={!selectedVideo && !streamConnected}
                        className={`w-full py-2 rounded text-xs font-medium border transition-colors disabled:opacity-40 ${
                          streamConnected
                            ? "bg-red-500/10 border-red-500/30 text-red-400"
                            : "bg-emerald-500/10 border-emerald-500/30 text-emerald-400"
                        }`}
                      >
                        {streamConnected ? "Disconnect Stream" : "Connect Stream"}
                      </button>
                    </div>
                  )}
                </div>
              </div>

              <div className="grid grid-cols-1 md:grid-cols-2 gap-4 sm:gap-6">
                <ChaosGauge chaos={chaos} />
                <AlertFeed alerts={alerts} maxVisible={8} />
              </div>
              <TelemetryChart data={telemetryHistory} />
            </motion.div>
          )}

          {activeTab === "history" && (
            <motion.div key="history"
              initial={{ opacity: 0, y: 10 }} animate={{ opacity: 1, y: 0 }}
              exit={{ opacity: 0, y: -10 }} transition={{ duration: 0.3 }}
              className="space-y-6"
            >
              <StatsCards stats={stats} />
              <div className="grid grid-cols-1 lg:grid-cols-3 gap-4 sm:gap-6">
                <div className="lg:col-span-2">
                  <SessionTable
                    sessions={sessions}
                    onRefresh={refreshStats}
                    onSelectSession={(s) => setActiveSession(s)}
                  />
                </div>
                <VideoUpload onUploadSuccess={() => { refreshStats(); loadVideos(); }} />
              </div>
              <DetectionBreakdown stats={stats} />
            </motion.div>
          )}

          {activeTab === "ai" && (
            <motion.div key="ai"
              initial={{ opacity: 0, y: 10 }} animate={{ opacity: 1, y: 0 }}
              exit={{ opacity: 0, y: -10 }} transition={{ duration: 0.3 }}
              className="space-y-6"
            >
              <StatsCards stats={stats} />
              <div className="grid grid-cols-1 lg:grid-cols-2 gap-4 sm:gap-6">
                <VideoStream chaos={chaos} tracked={tracked} alerts={alerts}
                  frameId={frameId} frameUrl={streamFrameUrl} wsConnected={streamConnected} />
                <AIExplainPanel alerts={alerts} chaos={chaos} />
              </div>
              <div className="grid grid-cols-1 lg:grid-cols-2 gap-4 sm:gap-6">
                <ChaosGauge chaos={chaos} />
                <DetectionBreakdown stats={stats} />
              </div>
            </motion.div>
          )}

        </AnimatePresence>
      </main>

      {/* Footer */}
      <footer className="mt-auto border-t border-border/30 glass-card">
        <div className="max-w-[1600px] mx-auto px-4 sm:px-6 py-4">
          <div className="flex flex-col sm:flex-row items-center justify-between gap-2">
            <div className="flex items-center gap-2">
              <div className={`w-2 h-2 rounded-full pulse-live ${streamConnected || cameraActive ? "bg-emerald-400" : "bg-amber-400"}`} />
              <span className="text-xs text-muted-foreground">RoadSense AI — ADAS Intelligence Platform</span>
            </div>
            <div className="flex items-center gap-4 text-[10px] text-muted-foreground">
              <span>{cameraActive ? "Camera Source" : streamConnected ? "WebSocket Source" : "Simulation"}</span>
              <span>•</span>
              <span>{streamConnected || cameraActive ? "Connected" : "Simulated"}</span>
              <span>•</span>
              <span>Frame #{frameId}</span>
            </div>
          </div>
        </div>
      </footer>
    </div>
  );
}
