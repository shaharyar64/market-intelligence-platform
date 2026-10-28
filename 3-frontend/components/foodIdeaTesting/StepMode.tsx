"use client";

import { motion } from "framer-motion";
import { Columns3, FileText } from "lucide-react";
import type { LucideIcon } from "lucide-react";

import type { ConceptMode } from "@/lib/foodIdeaTesting";

const MODES: { id: ConceptMode; label: string; description: string; Icon: LucideIcon }[] = [
  { id: "single", label: "Single concept", description: "Test one concept on its own.", Icon: FileText },
  {
    id: "multiple", label: "Compare up to 3",
    description: "Each concept is scored independently, then compared.", Icon: Columns3,
  },
];

export default function StepMode({ onSelect }: { onSelect: (m: ConceptMode) => void }) {
  return (
    <div className="grid gap-4 sm:grid-cols-2">
      {MODES.map(({ id, label, description, Icon }) => (
        <motion.button
          key={id}
          type="button"
          onClick={() => onSelect(id)}
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
            <h3 style={{ color: "var(--title-tx)" }} className="text-base font-semibold">{label}</h3>
            <p style={{ color: "var(--muted-tx)" }} className="mt-1 text-sm">{description}</p>
          </div>
        </motion.button>
      ))}
    </div>
  );
}
