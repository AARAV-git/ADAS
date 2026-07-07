"use client";

import { motion } from "framer-motion";
import {
  BarChart,
  Bar,
  XAxis,
  YAxis,
  CartesianGrid,
  Tooltip,
  ResponsiveContainer,
  Cell,
} from "recharts";
import { Target } from "lucide-react";
import type { StatsOverview } from "@/lib/types";

interface DetectionBreakdownProps {
  stats: StatsOverview;
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

const BAR_COLORS = ["#fbbf24", "#f97316", "#ef4444", "#22d3ee", "#a78bfa"];

function CustomTooltip({ active, payload }: {
  active?: boolean;
  payload?: Array<{ value: number; dataKey: string; payload: { label: string; count: number } }>;
}) {
  if (!active || !payload?.length) return null;
  const data = payload[0].payload;

  return (
    <div className="glass-card rounded-lg p-3 border border-border/50 text-xs">
      <p className="text-foreground font-semibold capitalize">{data.label}</p>
      <p className="text-muted-foreground">{data.count} detections</p>
    </div>
  );
}

export function DetectionBreakdown({ stats }: DetectionBreakdownProps) {
  const chartData = stats.top_classes.map((cls) => ({
    label: cls.label,
    count: cls.count,
  }));

  // Alert breakdown for pie-style display
  const alertData = Object.entries(stats.alert_breakdown).map(([level, count]) => ({
    level,
    count,
  }));

  const alertColors: Record<string, string> = {
    CRITICAL: "#ef4444",
    HIGH: "#f97316",
    MEDIUM: "#fbbf24",
    LOW: "#34d399",
  };

  return (
    <motion.div
      initial={{ opacity: 0, y: 20 }}
      animate={{ opacity: 1, y: 0 }}
      transition={{ duration: 0.5, delay: 0.5 }}
      className="glass-card rounded-xl p-4 sm:p-5 border border-border/50"
    >
      <div className="flex items-center justify-between mb-4">
        <h3 className="text-sm font-semibold text-foreground uppercase tracking-wider flex items-center gap-2">
          <Target className="w-4 h-4 text-amber-400" />
          Detection Breakdown
        </h3>
      </div>

      {/* Object Detection Bar Chart */}
      <div className="h-40 mb-4">
        <ResponsiveContainer width="100%" height="100%">
          <BarChart data={chartData} margin={{ top: 5, right: 5, left: -20, bottom: 0 }}>
            <CartesianGrid strokeDasharray="3 3" stroke="rgba(255,255,255,0.05)" />
            <XAxis
              dataKey="label"
              stroke="rgba(255,255,255,0.2)"
              tick={{ fill: "rgba(255,255,255,0.5)", fontSize: 10 }}
              tickLine={false}
              axisLine={{ stroke: "rgba(255,255,255,0.1)" }}
            />
            <YAxis
              stroke="rgba(255,255,255,0.2)"
              tick={{ fill: "rgba(255,255,255,0.4)", fontSize: 10 }}
              tickLine={false}
              axisLine={{ stroke: "rgba(255,255,255,0.1)" }}
            />
            <Tooltip content={<CustomTooltip />} />
            <Bar dataKey="count" radius={[4, 4, 0, 0]}>
              {chartData.map((item, i) => (
                <Cell 
                  key={i} 
                  fill={OBJECT_COLORS[item.label] || BAR_COLORS[i % BAR_COLORS.length]} 
                  fillOpacity={0.8} 
                />
              ))}
            </Bar>
          </BarChart>
        </ResponsiveContainer>
      </div>

      {/* Alert Breakdown */}
      <div>
        <h4 className="text-[10px] font-semibold text-muted-foreground uppercase tracking-wider mb-2">
          Alert Distribution
        </h4>
        <div className="space-y-2">
          {alertData.map((alert) => {
            const total = alertData.reduce((s, a) => s + a.count, 0);
            const pct = total > 0 ? (alert.count / total) * 100 : 0;

            return (
              <div key={alert.level} className="flex items-center gap-3">
                <div className="w-16 text-[10px] font-bold" style={{ color: alertColors[alert.level] }}>
                  {alert.level}
                </div>
                <div className="flex-1 h-2 bg-background/30 rounded-full overflow-hidden">
                  <motion.div
                    initial={{ width: 0 }}
                    animate={{ width: `${pct}%` }}
                    transition={{ duration: 1, delay: 0.8, ease: "easeOut" }}
                    className="h-full rounded-full"
                    style={{ backgroundColor: alertColors[alert.level] }}
                  />
                </div>
                <span className="text-[10px] text-muted-foreground w-8 text-right">
                  {alert.count}
                </span>
              </div>
            );
          })}
        </div>
      </div>
    </motion.div>
  );
}
