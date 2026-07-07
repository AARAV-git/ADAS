"use client";

import { motion } from "framer-motion";
import { FileVideo, Trash2, Upload, HardDrive, Loader2 } from "lucide-react";
import { useState, useRef } from "react";
import type { Session } from "@/lib/types";
import { RISK_LEVEL_CONFIG } from "@/lib/types";
import { apiUploadVideo, apiDeleteSession } from "@/lib/api";

interface SessionTableProps {
  sessions: Session[];
  onRefresh?: () => void;
  onSelectSession?: (session: Session) => void;
}

export function SessionTable({ sessions, onRefresh, onSelectSession }: SessionTableProps) {
  const handleDelete = async (id: number, e: React.MouseEvent) => {
    e.stopPropagation();
    if (confirm("Are you sure you want to delete this session?")) {
      try {
        await apiDeleteSession(id);
        if (onRefresh) onRefresh();
      } catch (err) {
        alert("Failed to delete session: " + err);
      }
    }
  };

  return (
    <motion.div
      initial={{ opacity: 0, y: 20 }}
      animate={{ opacity: 1, y: 0 }}
      transition={{ duration: 0.5, delay: 0.6 }}
      className="glass-card rounded-xl p-4 sm:p-5 border border-border/50"
    >
      <div className="flex items-center justify-between mb-4">
        <h3 className="text-sm font-semibold text-foreground uppercase tracking-wider flex items-center gap-2">
          <HardDrive className="w-4 h-4 text-amber-400" />
          Session History
        </h3>
        <span className="text-xs text-muted-foreground">
          {sessions.length} sessions
        </span>
      </div>

      <div className="overflow-x-auto">
        <table className="w-full">
          <thead>
            <tr className="border-b border-border/30">
              <th className="text-left text-[10px] font-semibold text-muted-foreground uppercase tracking-wider pb-2 pr-4">
                Video / Run
              </th>
              <th className="text-left text-[10px] font-semibold text-muted-foreground uppercase tracking-wider pb-2 pr-4 hidden sm:table-cell">
                Frames
              </th>
              <th className="text-left text-[10px] font-semibold text-muted-foreground uppercase tracking-wider pb-2 pr-4 hidden md:table-cell">
                Avg FPS
              </th>
              <th className="text-left text-[10px] font-semibold text-muted-foreground uppercase tracking-wider pb-2 pr-4">
                Chaos
              </th>
              <th className="text-left text-[10px] font-semibold text-muted-foreground uppercase tracking-wider pb-2 pr-4">
                Peak Risk
              </th>
              <th className="text-right text-[10px] font-semibold text-muted-foreground uppercase tracking-wider pb-2">
                Actions
              </th>
            </tr>
          </thead>
          <tbody>
            {sessions.length === 0 ? (
              <tr>
                <td colSpan={6} className="text-center py-6 text-xs text-muted-foreground italic">
                  No sessions found. Start a stream or record from your camera.
                </td>
              </tr>
            ) : (
              sessions.map((session, i) => {
                const riskConfig = RISK_LEVEL_CONFIG[session.peak_risk_level] || RISK_LEVEL_CONFIG.MEDIUM;
                const chaosColor =
                  session.avg_chaos_score < 30
                    ? "text-emerald-400"
                    : session.avg_chaos_score < 60
                    ? "text-amber-400"
                    : "text-red-400";

                return (
                  <motion.tr
                    key={session.id}
                    initial={{ opacity: 0, x: -10 }}
                    animate={{ opacity: 1, x: 0 }}
                    transition={{ delay: 0.2 + i * 0.03 }}
                    onClick={() => onSelectSession?.(session)}
                    className="border-b border-border/10 hover:bg-white/[0.02] transition-colors group cursor-pointer"
                  >
                    <td className="py-3 pr-4">
                      <div className="flex items-center gap-2">
                        <FileVideo className="w-3.5 h-3.5 text-amber-400/60" />
                        <div>
                          <p className="text-xs font-medium text-foreground truncate max-w-[180px]">
                            {session.video_name}
                          </p>
                          <p className="text-[10px] text-muted-foreground">
                            {new Date(session.started_at).toLocaleString()}
                          </p>
                        </div>
                      </div>
                    </td>
                    <td className="py-3 pr-4 text-xs text-muted-foreground hidden sm:table-cell">
                      {session.total_frames?.toLocaleString() || "—"}
                    </td>
                    <td className="py-3 pr-4 text-xs text-muted-foreground hidden md:table-cell">
                      {session.avg_fps ? session.avg_fps.toFixed(1) : "—"}
                    </td>
                    <td className="py-3 pr-4">
                      <span className={`text-xs font-semibold ${chaosColor}`}>
                        {session.avg_chaos_score ? session.avg_chaos_score.toFixed(1) : "—"}
                      </span>
                      {session.max_chaos_score && (
                        <span className="text-[10px] text-muted-foreground"> / {session.max_chaos_score.toFixed(1)}</span>
                      )}
                    </td>
                    <td className="py-3 pr-4">
                      <span className={`text-[10px] font-bold px-1.5 py-0.5 rounded ${riskConfig.bg} ${riskConfig.color}`}>
                        {session.peak_risk_level || "LOW"}
                      </span>
                    </td>
                    <td className="py-3 text-right">
                      <div className="flex items-center justify-end gap-1 opacity-0 group-hover:opacity-100 transition-opacity">
                        <button
                          onClick={(e) => handleDelete(session.id, e)}
                          className="p-1 rounded hover:bg-red-500/10 text-muted-foreground hover:text-red-400 transition-colors"
                          title="Delete session"
                        >
                          <Trash2 className="w-3.5 h-3.5" />
                        </button>
                      </div>
                    </td>
                  </motion.tr>
                );
              })
            )}
          </tbody>
        </table>
      </div>
    </motion.div>
  );
}

// Video Upload Component
interface VideoUploadProps {
  onUploadSuccess?: () => void;
}

export function VideoUpload({ onUploadSuccess }: VideoUploadProps) {
  const fileInputRef = useRef<HTMLInputElement>(null);
  const [uploading, setUploading] = useState(false);
  const [progress, setProgress] = useState(0);
  const [error, setError] = useState<string | null>(null);

  const handleFileChange = async (e: React.ChangeEvent<HTMLInputElement>) => {
    const file = e.target.files?.[0];
    if (!file) return;

    setUploading(true);
    setProgress(0);
    setError(null);

    try {
      await apiUploadVideo(file, (pct) => setProgress(pct));
      if (fileInputRef.current) fileInputRef.current.value = "";
      if (onUploadSuccess) onUploadSuccess();
    } catch (err) {
      setError(err instanceof Error ? err.message : "Upload failed.");
    } finally {
      setUploading(false);
    }
  };

  return (
    <motion.div
      initial={{ opacity: 0, y: 20 }}
      animate={{ opacity: 1, y: 0 }}
      transition={{ duration: 0.5, delay: 0.7 }}
      className="glass-card rounded-xl p-4 sm:p-5 border border-border/50 border-dashed"
    >
      <input
        type="file"
        ref={fileInputRef}
        onChange={handleFileChange}
        accept=".mp4,.avi,.mov,.mkv,.wmv"
        className="hidden"
      />
      <div className="flex flex-col items-center justify-center py-6 text-center">
        <div className="w-12 h-12 rounded-xl bg-amber-500/10 flex items-center justify-center mb-3">
          {uploading ? (
            <Loader2 className="w-6 h-6 text-amber-400 animate-spin" />
          ) : (
            <Upload className="w-6 h-6 text-amber-400" />
          )}
        </div>
        <h4 className="text-sm font-semibold text-foreground mb-1">
          {uploading ? `Uploading (${progress}%)` : "Upload Video"}
        </h4>
        <p className="text-xs text-muted-foreground mb-3 max-w-xs">
          {uploading ? "Please keep this browser window open until transfer completes." : "Drop or select a video to process through RoadSense ADAS pipeline."}
        </p>

        {error && (
          <p className="text-[10px] text-red-400 mb-2 max-w-xs">{error}</p>
        )}

        {!uploading && (
          <button
            onClick={() => fileInputRef.current?.click()}
            className="px-4 py-2 rounded-lg bg-amber-500/10 border border-amber-500/30 text-amber-400 text-xs font-medium hover:bg-amber-500/20 transition-colors"
          >
            Choose File
          </button>
        )}

        {uploading && (
          <div className="w-full bg-muted/40 rounded-full h-1.5 mt-2">
            <div
              className="bg-amber-400 h-1.5 rounded-full transition-all duration-300"
              style={{ width: `${progress}%` }}
            />
          </div>
        )}
      </div>
    </motion.div>
  );
}
