"use client";

import { motion, AnimatePresence } from "framer-motion";
import { AlertTriangle, ChevronRight, Clock } from "lucide-react";
import type { Alert } from "@/lib/types";
import { RISK_LEVEL_CONFIG } from "@/lib/types";

interface AlertFeedProps {
  alerts: Alert[];
  maxVisible?: number;
}

function AlertItem({ alert, index }: { alert: Alert; index: number }) {
  const config = RISK_LEVEL_CONFIG[alert.risk_level] || RISK_LEVEL_CONFIG.MEDIUM;

  return (
    <motion.div
      initial={{ opacity: 0, x: -20, height: 0 }}
      animate={{ opacity: 1, x: 0, height: "auto" }}
      exit={{ opacity: 0, x: 20, height: 0 }}
      transition={{ duration: 0.3, delay: index * 0.05 }}
      className={`flex items-start gap-3 p-3 rounded-lg border ${config.border} ${config.bg} group cursor-pointer transition-all hover:brightness-110`}
    >
      <div className={`mt-0.5 p-1.5 rounded-md ${config.bg}`}>
        <AlertTriangle className={`w-3.5 h-3.5 ${config.color}`} />
      </div>
      <div className="flex-1 min-w-0">
        <div className="flex items-center gap-2 mb-0.5">
          <span className={`text-[10px] font-bold px-1.5 py-0.5 rounded ${config.bg} ${config.color}`}>
            {alert.risk_level}
          </span>
          <span className="text-[10px] text-muted-foreground capitalize">
            {alert.label}
          </span>
          <span className="text-[10px] text-muted-foreground ml-auto">
            Score: {alert.risk_score}
          </span>
        </div>
        <p className="text-xs text-foreground/80 line-clamp-2">
          {alert.message}
        </p>
        <p className="text-[10px] text-muted-foreground mt-1 flex items-center gap-1">
          <ChevronRight className="w-3 h-3" />
          {alert.action}
        </p>
      </div>
    </motion.div>
  );
}

export function AlertFeed({ alerts, maxVisible = 8 }: AlertFeedProps) {
  const visibleAlerts = alerts.slice(0, maxVisible);

  return (
    <motion.div
      initial={{ opacity: 0, y: 20 }}
      animate={{ opacity: 1, y: 0 }}
      transition={{ duration: 0.5, delay: 0.4 }}
      className="glass-card rounded-xl p-4 sm:p-5 border border-border/50 flex flex-col"
    >
      <div className="flex items-center justify-between mb-3">
        <h3 className="text-sm font-semibold text-foreground uppercase tracking-wider flex items-center gap-2">
          <AlertTriangle className="w-4 h-4 text-amber-400" />
          Alert Feed
        </h3>
        <div className="flex items-center gap-1.5">
          {alerts.length > 0 && (
            <span className="text-[10px] text-muted-foreground flex items-center gap-1">
              <Clock className="w-3 h-3" />
              Live
            </span>
          )}
          <span className="text-xs font-bold px-2 py-0.5 rounded-full bg-red-500/20 text-red-400">
            {alerts.length}
          </span>
        </div>
      </div>

      <div className="flex-1 space-y-2 max-h-80 overflow-y-auto pr-1">
        <AnimatePresence mode="popLayout">
          {visibleAlerts.length > 0 ? (
            visibleAlerts.map((alert, i) => (
              <AlertItem key={`${alert.track_id}-${alert.timestamp}-${i}`} alert={alert} index={i} />
            ))
          ) : (
            <div className="flex flex-col items-center justify-center py-8 text-muted-foreground">
              <Shield className="w-8 h-8 mb-2 opacity-30" />
              <p className="text-xs">No active alerts</p>
              <p className="text-[10px]">All clear — safe driving</p>
            </div>
          )}
        </AnimatePresence>
      </div>
    </motion.div>
  );
}

function Shield(props: React.SVGProps<SVGSVGElement>) {
  return (
    <svg
      xmlns="http://www.w3.org/2000/svg"
      width="24"
      height="24"
      viewBox="0 0 24 24"
      fill="none"
      stroke="currentColor"
      strokeWidth="2"
      strokeLinecap="round"
      strokeLinejoin="round"
      {...props}
    >
      <path d="M20 13c0 5-3.5 7.5-7.66 8.95a1 1 0 0 1-.67-.01C7.5 20.5 4 18 4 13V6a1 1 0 0 1 1-1c2 0 4.5-1.2 6.24-2.72a1.17 1.17 0 0 1 1.52 0C14.51 3.81 17 5 19 5a1 1 0 0 1 1 1z" />
      <path d="m9 12 2 2 4-4" />
    </svg>
  );
}
