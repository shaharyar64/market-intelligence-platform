"use client";

import { motion } from "framer-motion";
import { Megaphone, Rocket, Zap } from "lucide-react";
import type { LucideIcon } from "lucide-react";

import { TEST_TYPES } from "@/lib/ideaTestingFramework";
import type { TestType } from "@/lib/ideaTesting";

const ICONS: Record<TestType, LucideIcon> = {
  "quick-idea": Zap,
  advertising: Megaphone,
  innovation: Rocket,
};

export default function StepTestType({ onSelect }: { onSelect: (t: TestType) => void }) {
  return (
    <div className="grid gap-4 sm:grid-cols-3">
      {TEST_TYPES.map((t) => {
        const Icon = ICONS[t.id];
        return (
          <motion.button
            key={t.id}
            type="button"
            onClick={() => onSelect(t.id)}
            whileHover={{ y: -3 }}
            className="chart-card flex flex-col items-start gap-3 rounded-2xl p-5 text-left"
          >
            <span
              className="flex size-11 items-center justify-center rounded-xl text-white shadow-sm"
              style={{ background: "linear-gradient(135deg, var(--accent-from), var(--accent2-from))" }}
            >
              <Icon size={20} aria-hidden="true" />
            </span>
            <div>
              <h3 style={{ color: "var(--title-tx)" }} className="text-base font-semibold">{t.label}</h3>
              <p style={{ color: "var(--muted-tx)" }} className="mt-1 text-xs">{t.tagline}</p>
            </div>
            <p style={{ color: "var(--muted-tx)" }} className="text-sm">{t.description}</p>
          </motion.button>
        );
      })}
    </div>
  );
}
