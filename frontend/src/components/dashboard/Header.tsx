"use client";

import { motion } from "framer-motion";
import { Activity, Shield, Radio } from "lucide-react";

export function Header() {
  return (
    <motion.header
      initial={{ y: -20, opacity: 0 }}
      animate={{ y: 0, opacity: 1 }}
      transition={{ duration: 0.5 }}
      className="sticky top-0 z-50 glass-card border-b border-border/50"
    >
      <div className="max-w-[1600px] mx-auto px-4 sm:px-6 h-16 flex items-center justify-between">
        {/* Logo & Title */}
        <div className="flex items-center gap-3">
          <div className="relative">
            <div className="w-10 h-10 rounded-xl bg-gradient-to-br from-amber-500 to-orange-600 flex items-center justify-center shadow-lg shadow-amber-500/20">
              <Shield className="w-5 h-5 text-white" />
            </div>
            <div className="absolute -top-0.5 -right-0.5 w-3 h-3 bg-emerald-400 rounded-full border-2 border-background pulse-live" />
          </div>
          <div>
            <h1 className="text-lg font-bold tracking-tight gradient-text">
              RoadSense AI
            </h1>
            <p className="text-[10px] text-muted-foreground tracking-widest uppercase">
              Advanced Driver Assistance
            </p>
          </div>
        </div>

        {/* Status Indicators */}
        <div className="flex items-center gap-4">
          <div className="hidden sm:flex items-center gap-2 px-3 py-1.5 rounded-full bg-emerald-500/10 border border-emerald-500/20">
            <div className="w-2 h-2 bg-emerald-400 rounded-full pulse-live" />
            <span className="text-xs font-medium text-emerald-400">System Active</span>
          </div>
          <div className="hidden md:flex items-center gap-2 px-3 py-1.5 rounded-full bg-amber-500/10 border border-amber-500/20">
            <Radio className="w-3.5 h-3.5 text-amber-400" />
            <span className="text-xs font-medium text-amber-400">Live Feed</span>
          </div>
          <div className="flex items-center gap-2 px-3 py-1.5 rounded-full bg-orange-500/10 border border-orange-500/20">
            <Activity className="w-3.5 h-3.5 text-orange-400" />
            <span className="text-xs font-medium text-orange-400">24 FPS</span>
          </div>
        </div>
      </div>
    </motion.header>
  );
}
