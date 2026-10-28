"use client";

import { motion } from "framer-motion";

import { scoreTone } from "@/lib/ideaTestingFramework";

export default function ScoreRing({ score, size = 76 }: { score: number; size?: number }) {
  const stroke = 6;
  const radius = (size - stroke) / 2;
  const circumference = 2 * Math.PI * radius;
  const clamped = Math.max(0, Math.min(100, score));

  return (
    <div
      role="img"
      aria-label={`Overall score ${score} out of 100`}
      className="relative shrink-0"
      style={{ width: size, height: size }}
    >
      <svg width={size} height={size} className="-rotate-90" aria-hidden="true">
        <circle cx={size / 2} cy={size / 2} r={radius} fill="none" stroke="var(--card-bd)" strokeWidth={stroke} />
        <motion.circle
          cx={size / 2}
          cy={size / 2}
          r={radius}
          fill="none"
          stroke={scoreTone(clamped)}
          strokeWidth={stroke}
          strokeLinecap="round"
          strokeDasharray={circumference}
          initial={{ strokeDashoffset: circumference }}
          animate={{ strokeDashoffset: circumference * (1 - clamped / 100) }}
          transition={{ duration: 0.9, ease: [0.16, 1, 0.3, 1] }}
        />
      </svg>
      <div className="absolute inset-0 flex flex-col items-center justify-center leading-none" aria-hidden="true">
        <span style={{ color: "var(--title-tx)" }} className="text-2xl font-bold tabular-nums">{score}</span>
        <span style={{ color: "var(--muted-tx)" }} className="mt-1 text-[10px]">/100</span>
      </div>
    </div>
  );
}
