"use client";

import type { ReactNode } from "react";
import { motion } from "framer-motion";

import { soft, softBorder, text } from "@/lib/realEstateTrendsPalette";

const TOKEN = "watchlist" as const;

export function HeroStat({ value, label }: { value: ReactNode; label: string }) {
  return (
    <div
      className="min-w-20 rounded-xl px-4 py-3 text-center"
      style={{ background: "var(--card-bg)", border: "1px solid var(--card-bd)" }}
    >
      <div style={{ color: "var(--title-tx)" }} className="text-xl font-bold tabular-nums">{value}</div>
      <div style={{ color: "var(--muted-tx)" }} className="text-xs">{label}</div>
    </div>
  );
}

export default function ResultHero({
  pill, title, description, stats, verdict, footer,
}: {
  pill: ReactNode;
  title: string;
  description: string;
  stats: ReactNode;
  verdict: ReactNode;
  footer?: ReactNode;
}) {
  return (
    <motion.section
      initial={{ opacity: 0, y: 12 }}
      animate={{ opacity: 1, y: 0 }}
      transition={{ duration: 0.45, ease: [0.16, 1, 0.3, 1] }}
      className="chart-card rounded-2xl p-6"
      style={{ background: soft(TOKEN) }}
    >
      <div className="flex flex-wrap items-start justify-between gap-4">
        <div className="min-w-0 max-w-2xl">
          <span
            className="inline-flex items-center gap-1.5 rounded-full px-3 py-0.5 text-xs font-semibold"
            style={{ background: "var(--card-bg)", color: text(TOKEN), border: `1px solid ${softBorder(TOKEN)}` }}
          >
            {pill}
          </span>
          <h2 style={{ color: "var(--title-tx)" }} className="mt-3 text-3xl font-bold tracking-tight text-balance">
            {title}
          </h2>
          <p style={{ color: "var(--body-tx)" }} className="mt-2 text-sm leading-relaxed">{description}</p>
        </div>
        <div className="flex flex-wrap gap-3">{stats}</div>
      </div>
      <div className="mt-5 border-t pt-4" style={{ borderColor: "var(--card-bd)" }}>
        <p style={{ color: "var(--body-tx)" }} className="text-sm leading-relaxed">
          <span style={{ color: text(TOKEN) }} className="font-semibold">Verdict: </span>
          {verdict}
        </p>
        {footer}
      </div>
    </motion.section>
  );
}
