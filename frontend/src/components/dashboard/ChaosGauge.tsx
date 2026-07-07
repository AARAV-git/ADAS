"use client";

import { motion } from "framer-motion";
import { useEffect, useState } from "react";
import type { ChaosData, ChaosLevel } from "@/lib/types";
import { CHAOS_LEVEL_CONFIG } from "@/lib/types";

interface ChaosGaugeProps {
  chaos: ChaosData;
}

export function ChaosGauge({ chaos }: ChaosGaugeProps) {
  const [animatedScore, setAnimatedScore] = useState(0);

  // Safe fallback — guard against any unknown level string from the backend
  const rawLevel = chaos?.level || "Calm";
  const normalizedLevel = (rawLevel.charAt(0).toUpperCase() + rawLevel.slice(1).toLowerCase()) as ChaosLevel;

  const config = CHAOS_LEVEL_CONFIG[normalizedLevel]
    ?? CHAOS_LEVEL_CONFIG["Calm"]
    ?? { color: "text-emerald-400", bg: "bg-emerald-500/20", label: "CALM" };

  useEffect(() => {
    const duration = 800;
    const startTime = Date.now();
    const startValue = animatedScore;
    const endValue = chaos?.score ?? 0;

    const animate = () => {
      const elapsed = Date.now() - startTime;
      const progress = Math.min(elapsed / duration, 1);
      const eased = 1 - Math.pow(1 - progress, 3);
      setAnimatedScore(startValue + (endValue - startValue) * eased);

      if (progress < 1) {
        requestAnimationFrame(animate);
      }
    };

    requestAnimationFrame(animate);
  }, [chaos?.score]);

  // SVG arc parameters
  const radius = 70;
  const strokeWidth = 12;
  const centerX = 100;
  const centerY = 100;
  const startAngle = -225;
  const endAngle = 45;
  const totalAngle = endAngle - startAngle; // 270 degrees

  const scoreToAngle = (score: number) =>
    startAngle + (score / 100) * totalAngle;

  const polarToCartesian = (angle: number) => ({
    x: centerX + radius * Math.cos((angle * Math.PI) / 180),
    y: centerY + radius * Math.sin((angle * Math.PI) / 180),
  });

  const arcPath = (start: number, end: number) => {
    const s = polarToCartesian(start);
    const e = polarToCartesian(end);
    const largeArc = end - start > 180 ? 1 : 0;
    return `M ${s.x} ${s.y} A ${radius} ${radius} 0 ${largeArc} 1 ${e.x} ${e.y}`;
  };

  const currentAngle = scoreToAngle(animatedScore);

  // Color gradient based on score
  const getArcColor = (score: number) => {
    if (score < 20) return "#34d399"; // emerald
    if (score < 40) return "#4ade80"; // green
    if (score < 60) return "#fbbf24"; // amber
    if (score < 80) return "#f97316"; // orange
    return "#ef4444"; // red
  };

  const getGlowColor = (score: number) => {
    if (score < 20) return "rgba(52, 211, 153, 0.3)";
    if (score < 40) return "rgba(74, 222, 128, 0.3)";
    if (score < 60) return "rgba(251, 191, 36, 0.3)";
    if (score < 80) return "rgba(249, 115, 22, 0.3)";
    return "rgba(239, 68, 68, 0.3)";
  };

  return (
    <motion.div
      initial={{ opacity: 0, scale: 0.9 }}
      animate={{ opacity: 1, scale: 1 }}
      transition={{ duration: 0.6, delay: 0.3 }}
      className="glass-card rounded-xl p-4 sm:p-5 border border-border/50"
    >
      <div className="flex items-center justify-between mb-3">
        <h3 className="text-sm font-semibold text-foreground uppercase tracking-wider">
          Chaos Score
        </h3>
        <span className={`text-xs font-bold px-2 py-0.5 rounded-full ${config.bg} ${config.color}`}>
          {config.label}
        </span>
      </div>

      <div className="flex justify-center">
        <svg width="200" height="150" viewBox="0 0 200 150">
          {/* Filter for glow */}
          <defs>
            <filter id="glow">
              <feGaussianBlur stdDeviation="3" result="coloredBlur" />
              <feMerge>
                <feMergeNode in="coloredBlur" />
                <feMergeNode in="SourceGraphic" />
              </feMerge>
            </filter>
          </defs>

          {/* Background arc */}
          <path
            d={arcPath(startAngle, endAngle)}
            fill="none"
            stroke="rgba(255,255,255,0.05)"
            strokeWidth={strokeWidth}
            strokeLinecap="round"
          />

          {/* Active arc */}
          {animatedScore > 0 && (
            <path
              d={arcPath(startAngle, currentAngle)}
              fill="none"
              stroke={getArcColor(animatedScore)}
              strokeWidth={strokeWidth}
              strokeLinecap="round"
              filter="url(#glow)"
              style={{
                transition: "stroke 0.5s ease",
              }}
            />
          )}

          {/* Score Text */}
          <text
            x={centerX}
            y={centerY - 5}
            textAnchor="middle"
            className="fill-foreground text-3xl font-bold"
            style={{ fontSize: "32px", fontFamily: "var(--font-geist-sans)" }}
          >
            {Math.round(animatedScore)}
          </text>
          <text
            x={centerX}
            y={centerY + 18}
            textAnchor="middle"
            className="fill-muted-foreground"
            style={{ fontSize: "11px", fontFamily: "var(--font-geist-sans)" }}
          >
            out of 100
          </text>

          {/* Min / Max labels */}
          <text
            x={polarToCartesian(startAngle).x - 10}
            y={polarToCartesian(startAngle).y + 15}
            textAnchor="middle"
            className="fill-muted-foreground"
            style={{ fontSize: "10px" }}
          >
            0
          </text>
          <text
            x={polarToCartesian(endAngle).x + 10}
            y={polarToCartesian(endAngle).y + 15}
            textAnchor="middle"
            className="fill-muted-foreground"
            style={{ fontSize: "10px" }}
          >
            100
          </text>
        </svg>
      </div>

      {/* Breakdown */}
      <div className="grid grid-cols-2 gap-2 mt-2">
        {chaos?.breakdown && Object.entries(chaos.breakdown).map(([key, val]) => (
          <div key={key} className="flex items-center justify-between px-2 py-1 rounded-md bg-background/30">
            <span className="text-[10px] text-muted-foreground capitalize truncate">
              {key.replace(/_/g, " ")}
            </span>
            <span className="text-xs font-semibold text-foreground">
              {val.toFixed(0)}%
            </span>
          </div>
        ))}
      </div>
    </motion.div>
  );
}
