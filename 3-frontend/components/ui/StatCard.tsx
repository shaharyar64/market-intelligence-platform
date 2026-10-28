"use client";

import { motion } from "framer-motion";
import { TrendingUp, TrendingDown, Loader2 } from "lucide-react";

export default function GlassStatCard({
  title,
  value,
  change,
  icon,
  gradient = "from-blue-500 to-cyan-400",
  loading = false,
}: {
  title: string;
  value?: string | number;
  change?: number;
  icon: React.ReactNode;
  gradient?: string;
  loading?: boolean;
}) {
  const isPositive = change !== undefined && change > 0;

  return (
    <motion.div
      initial={{ opacity: 0, y: 8 }}
      animate={{ opacity: 1, y: 0 }}
      whileHover={{ y: -6, scale: 1.01 }}
      transition={{ type: "spring", stiffness: 200, damping: 20 }}
      style={{
        background: "var(--card-bg)",
        border: "1px solid var(--card-bd)",
        backdropFilter: "var(--blur)",
        WebkitBackdropFilter: "var(--blur)",
        boxShadow: "var(--card-shadow)",
        transition: "background 0.3s, border-color 0.3s",
      }}
      className="relative p-6 rounded-2xl overflow-hidden min-h-[140px]"
    >
      {/* Large soft glow — fills the top-right quadrant */}
      <div className={`absolute -top-10 -right-10 w-48 h-48 bg-gradient-to-br ${gradient} opacity-40 blur-3xl rounded-full pointer-events-none`} />
      {/* Tighter inner glow — adds vibrancy near the icon */}
      <div className={`absolute -top-4 -right-4 w-28 h-28 bg-gradient-to-br ${gradient} opacity-30 blur-2xl rounded-full pointer-events-none`} />
      {/* Full-card colour wash — gives each card its own tint */}
      <div className={`absolute inset-0 bg-gradient-to-br ${gradient} opacity-[0.07] rounded-2xl pointer-events-none`} />

      <div className="relative z-10">
        {/* Top row */}
        <div className="flex items-center justify-between">
          <span style={{ color: "var(--muted-tx)" }} className="text-sm font-medium">
            {title}
          </span>
          <div className={`h-11 w-11 rounded-xl flex items-center justify-center bg-gradient-to-br ${gradient} text-white shadow-lg`}>
            {icon}
          </div>
        </div>

        {/* Value */}
        {loading ? (
          <div className="mt-6 flex items-center gap-3">
            <Loader2 style={{ color: "var(--muted-tx)" }} className="w-5 h-5 animate-spin" />
            <div style={{ background: "var(--card-bd)" }} className="h-7 w-32 rounded animate-pulse" />
          </div>
        ) : (
          <>
            <div style={{ color: "var(--title-tx)" }} className="mt-4 text-3xl font-bold tracking-tight">
              {value}
            </div>
            {change !== undefined && (
              <div className="mt-2 flex items-center gap-1.5 text-sm">
                {isPositive
                  ? <TrendingUp className="h-4 w-4 text-emerald-500" />
                  : <TrendingDown className="h-4 w-4 text-red-500" />}
                <span className={isPositive ? "text-emerald-500 font-semibold" : "text-red-500 font-semibold"}>
                  {Math.abs(change)}%
                </span>
                <span style={{ color: "var(--muted-tx)" }}>vs last month</span>
              </div>
            )}
          </>
        )}
      </div>
    </motion.div>
  );
}
