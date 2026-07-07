"use client";

import { motion } from "framer-motion";
import { useEffect, useState } from "react";
import {
  Activity,
  AlertTriangle,
  BarChart3,
  Shield,
} from "lucide-react";
import type { StatsOverview } from "@/lib/types";

interface StatsCardsProps {
  stats: StatsOverview;
}

function AnimatedNumber({ value, decimals = 0 }: { value: number; decimals?: number }) {
  const [displayValue, setDisplayValue] = useState(0);

  useEffect(() => {
    const duration = 1500;
    const startTime = Date.now();
    const startValue = 0;
    const endValue = value;

    const animate = () => {
      const elapsed = Date.now() - startTime;
      const progress = Math.min(elapsed / duration, 1);
      // Ease out cubic
      const eased = 1 - Math.pow(1 - progress, 3);
      setDisplayValue(startValue + (endValue - startValue) * eased);

      if (progress < 1) {
        requestAnimationFrame(animate);
      }
    };

    requestAnimationFrame(animate);
  }, [value]);

  return <>{displayValue.toFixed(decimals)}</>;
}

const cardVariants = {
  hidden: { opacity: 0, y: 20, scale: 0.95 },
  visible: (i: number) => ({
    opacity: 1,
    y: 0,
    scale: 1,
    transition: { delay: i * 0.1, duration: 0.5, ease: "easeOut" },
  }),
};

export function StatsCards({ stats }: StatsCardsProps) {
  const cards = [
    {
      title: "Total Sessions",
      value: stats.total_sessions,
      icon: BarChart3,
      color: "from-amber-500/20 to-amber-600/5",
      iconColor: "text-amber-400",
      borderColor: "border-amber-500/20",
      suffix: "",
      decimals: 0,
    },
    {
      title: "Frames Processed",
      value: stats.total_frames,
      icon: Activity,
      color: "from-cyan-500/20 to-cyan-600/5",
      iconColor: "text-cyan-400",
      borderColor: "border-cyan-500/20",
      suffix: "",
      decimals: 0,
    },
    {
      title: "Active Alerts",
      value: stats.total_alerts,
      icon: AlertTriangle,
      color: "from-red-500/20 to-red-600/5",
      iconColor: "text-red-400",
      borderColor: "border-red-500/20",
      suffix: "",
      decimals: 0,
    },
    {
      title: "Avg Chaos Score",
      value: stats.avg_chaos_score,
      icon: Shield,
      color: "from-orange-500/20 to-orange-600/5",
      iconColor: "text-orange-400",
      borderColor: "border-orange-500/20",
      suffix: "%",
      decimals: 1,
    },
  ];

  return (
    <div className="grid grid-cols-2 lg:grid-cols-4 gap-3 sm:gap-4">
      {cards.map((card, i) => (
        <motion.div
          key={card.title}
          custom={i}
          variants={cardVariants as any}
          initial="hidden"
          animate="visible"
          className={`glass-card glass-card-hover rounded-xl p-4 sm:p-5 border ${card.borderColor} relative overflow-hidden`}
        >
          {/* Gradient Background */}
          <div className={`absolute inset-0 bg-gradient-to-br ${card.color} opacity-50`} />

          <div className="relative z-10">
            <div className="flex items-center justify-between mb-3">
              <span className="text-xs font-medium text-muted-foreground uppercase tracking-wider">
                {card.title}
              </span>
              <div className={`p-1.5 rounded-lg bg-background/50 ${card.iconColor}`}>
                <card.icon className="w-4 h-4" />
              </div>
            </div>
            <div className="flex items-baseline gap-1">
              <span className="text-2xl sm:text-3xl font-bold text-foreground">
                <AnimatedNumber value={card.value} decimals={card.decimals} />
              </span>
              {card.suffix && (
                <span className="text-sm text-muted-foreground">{card.suffix}</span>
              )}
            </div>
          </div>
        </motion.div>
      ))}
    </div>
  );
}
