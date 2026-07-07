"use client";

import { motion } from "framer-motion";
import { useState } from "react";
import { Brain, Send, Loader2, Sparkles, AlertTriangle } from "lucide-react";
import type { Alert, ChaosData, ExplainResponse } from "@/lib/types";
import { RISK_LEVEL_CONFIG } from "@/lib/types";
import { apiExplain } from "@/lib/api";

interface AIExplainPanelProps {
  alerts: Alert[];
  chaos: ChaosData;
}

export function AIExplainPanel({ alerts, chaos }: AIExplainPanelProps) {
  const [selectedAlert, setSelectedAlert] = useState<Alert | null>(null);
  const [explanation, setExplanation] = useState<ExplainResponse | null>(null);
  const [isLoading, setIsLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);

  const handleExplain = async (alert: Alert) => {
    setSelectedAlert(alert);
    setIsLoading(true);
    setExplanation(null);
    setError(null);

    try {
      const response = await apiExplain({
        event: {
          track_id: alert.track_id,
          label: alert.label,
          risk_type: alert.risk_type,
          risk_level: alert.risk_level,
          risk_score: alert.risk_score,
          message: alert.message,
        },
        chaos: chaos,
        position: "front", // default position
      });
      setExplanation(response);
    } catch (err) {
      console.error(err);
      setError("Failed to fetch explanation from backend. Showing simulated response.");
      // Fallback to local rule-based explanation if server explain is down or key is missing
      const fallbackExplanations: Record<string, ExplainResponse> = {
        HIGH: {
          risk_level: "HIGH",
          message: `A ${alert.label} has been detected in a high-risk zone with a risk score of ${alert.risk_score}/10. Under current chaos conditions (score: ${chaos.score.toFixed(1)}, level: ${chaos.level}), this object poses an immediate threat to vehicle safety. The ${alert.risk_type.replace(/_/g, " ")} pattern suggests the object may enter your path within the next 2-3 seconds.`,
          action: `Immediately reduce speed by 15-20%, maintain current lane position, and prepare for emergency braking. Do NOT attempt lane changes until the ${alert.label} has cleared your projected path.`,
        },
        CRITICAL: {
          risk_level: "CRITICAL",
          message: `CRITICAL THREAT: A ${alert.label} has entered your immediate danger zone with a risk score of ${alert.risk_score}/10. Current chaos level is ${chaos.level} (score: ${chaos.score.toFixed(1)}), indicating highly unpredictable traffic behavior. The ${alert.risk_type.replace(/_/g, " ")} event combined with elevated vehicle density (${chaos.breakdown.vehicle_density.toFixed(0)}%) creates a collision probability exceeding 60%.`,
          action: `EXECUTE IMMEDIATE EVASIVE ACTION: Apply controlled emergency braking. Do NOT swerve. Maintain steering control and reduce speed to below 20 km/h. Sound horn to alert the ${alert.label}.`,
        },
        MEDIUM: {
          risk_level: "MEDIUM",
          message: `A ${alert.label} is operating near your vehicle path with a risk score of ${alert.risk_score}/10. Current chaos conditions are ${chaos.level} (score: ${chaos.score.toFixed(1)}). The ${alert.risk_type.replace(/_/g, " ")} pattern suggests moderate risk — the situation is manageable but requires active monitoring.`,
          action: `Maintain current speed with increased vigilance. Increase following distance by 2 seconds. Periodically check mirrors for the ${alert.label}'s position.`,
        },
        LOW: {
          risk_level: "LOW",
          message: `A ${alert.label} has been detected at a safe distance with a low risk score of ${alert.risk_score}/10. Chaos conditions are currently ${chaos.level} (score: ${chaos.score.toFixed(1)}). No immediate threat is detected.`,
          action: `Continue driving normally. Maintain standard following distance and keep the ${alert.label} in your awareness zone.`,
        },
      };
      setExplanation(fallbackExplanations[alert.risk_level] || fallbackExplanations.MEDIUM);
    } finally {
      setIsLoading(false);
    }
  };

  return (
    <motion.div
      initial={{ opacity: 0, y: 20 }}
      animate={{ opacity: 1, y: 0 }}
      transition={{ duration: 0.5, delay: 0.7 }}
      className="glass-card rounded-xl p-4 sm:p-5 border border-border/50 flex flex-col"
    >
      <div className="flex items-center justify-between mb-3">
        <h3 className="text-sm font-semibold text-foreground uppercase tracking-wider flex items-center gap-2">
          <Brain className="w-4 h-4 text-amber-400" />
          AI Explainability
        </h3>
        <Sparkles className="w-4 h-4 text-amber-400/50" />
      </div>

      {/* Alert Selection */}
      <div className="space-y-2 mb-4 max-h-40 overflow-y-auto pr-1">
        {alerts.length > 0 ? (
          alerts.map((alert, i) => {
            const config = RISK_LEVEL_CONFIG[alert.risk_level] || RISK_LEVEL_CONFIG.MEDIUM;
            const isSelected = selectedAlert?.track_id === alert.track_id && selectedAlert?.risk_type === alert.risk_type;

            return (
              <button
                key={`${alert.track_id}-${alert.risk_type}-${i}`}
                onClick={() => handleExplain(alert)}
                className={`w-full flex items-center gap-2 p-2 rounded-lg border transition-all text-left ${
                  isSelected
                    ? `${config.bg} ${config.border}`
                    : "bg-background/20 border-border/20 hover:bg-background/30 hover:border-border/40"
                }`}
              >
                <AlertTriangle className={`w-3.5 h-3.5 shrink-0 ${config.color}`} />
                <div className="flex-1 min-w-0">
                  <div className="flex items-center gap-2">
                    <span className={`text-[10px] font-bold px-1.5 py-0.5 rounded ${config.bg} ${config.color}`}>
                      {alert.risk_level}
                    </span>
                    <span className="text-xs text-foreground truncate">
                      {alert.label} — {alert.risk_type.replace(/_/g, " ")}
                    </span>
                  </div>
                </div>
                <Send className={`w-3 h-3 shrink-0 ${isSelected ? config.color : "text-muted-foreground"}`} />
              </button>
            );
          })
        ) : (
          <div className="text-center py-4">
            <p className="text-xs text-muted-foreground">No alerts to explain</p>
          </div>
        )}
      </div>

      {/* Explanation Result */}
      <div className="flex-1">
        {isLoading ? (
          <motion.div
            initial={{ opacity: 0 }}
            animate={{ opacity: 1 }}
            className="flex flex-col items-center justify-center py-8"
          >
            <Loader2 className="w-6 h-6 text-amber-400 animate-spin mb-3" />
            <p className="text-xs text-muted-foreground">Analyzing risk context via LLM...</p>
          </motion.div>
        ) : explanation ? (
          <motion.div
            initial={{ opacity: 0, y: 10 }}
            animate={{ opacity: 1, y: 0 }}
            transition={{ duration: 0.3 }}
            className="space-y-3"
          >
            {error && (
              <p className="text-[10px] text-amber-400 italic mb-1">{error}</p>
            )}
            <div className="p-3 rounded-lg bg-amber-500/5 border border-amber-500/20">
              <div className="flex items-center gap-2 mb-2">
                <Sparkles className="w-3.5 h-3.5 text-amber-400" />
                <span className="text-[10px] font-bold text-amber-400 uppercase">
                  Risk Level: {explanation.risk_level}
                </span>
              </div>
              <p className="text-xs text-foreground/80 leading-relaxed">
                {explanation.message}
              </p>
            </div>
            <div className="p-3 rounded-lg bg-emerald-500/5 border border-emerald-500/20">
              <div className="flex items-center gap-2 mb-2">
                <AlertTriangle className="w-3.5 h-3.5 text-emerald-400" />
                <span className="text-[10px] font-bold text-emerald-400 uppercase">
                  Recommended Action
                </span>
              </div>
              <p className="text-xs text-foreground/80 leading-relaxed">
                {explanation.action}
              </p>
            </div>
          </motion.div>
        ) : (
          <div className="flex flex-col items-center justify-center py-8 text-muted-foreground">
            <Brain className="w-8 h-8 mb-2 opacity-20" />
            <p className="text-xs">Select an alert to get AI analysis</p>
            <p className="text-[10px]">Click any alert above to explain</p>
          </div>
        )}
      </div>
    </motion.div>
  );
}
