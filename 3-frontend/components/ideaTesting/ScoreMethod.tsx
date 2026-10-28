"use client";

import { useId, useState } from "react";
import { Calculator, ChevronDown } from "lucide-react";

import { FACTORS } from "@/lib/ideaTestingFramework";
import type { FactorScore } from "@/lib/ideaTesting";

export default function ScoreMethod({ factors, overall }: { factors: FactorScore[]; overall: number }) {
  const [open, setOpen] = useState(false);
  const panelId = useId();
  const scores = FACTORS.map((f) => factors.find((s) => s.factor_id === f.id)?.score ?? 0);

  return (
    <section className="chart-card rounded-2xl">
      <button
        type="button"
        onClick={() => setOpen((v) => !v)}
        aria-expanded={open}
        aria-controls={panelId}
        className="flex w-full items-center gap-2 px-5 py-4 text-left"
      >
        <Calculator size={14} aria-hidden="true" style={{ color: "var(--muted-tx)" }} />
        <span style={{ color: "var(--muted-tx)" }} className="flex-1 text-[11px] font-semibold uppercase tracking-wide">
          How this score is calculated
        </span>
        <ChevronDown
          size={16}
          aria-hidden="true"
          className={`transition-transform duration-200 ${open ? "rotate-180" : ""}`}
          style={{ color: "var(--muted-tx)" }}
        />
      </button>
      {open && (
        <div id={panelId} className="space-y-3 border-t px-5 pb-5 pt-4 text-sm leading-relaxed" style={{ borderColor: "var(--card-bd)", color: "var(--body-tx)" }}>
          <p>
            Each factor is scored 0 to 100 against a fixed InsightFactor rubric, using only the posts
            and trends retrieved for that factor: 0 to 20 fails, 21 to 40 weak, 41 to 60 mixed,
            61 to 80 strong, 81 to 100 exceptional. A factor with no relevant evidence is capped at 60.
          </p>
          <p>The overall score is the simple average of the six:</p>
          <p
            style={{ background: "var(--card-bg-2)", color: "var(--title-tx)" }}
            className="rounded-lg px-3 py-2 font-medium tabular-nums"
          >
            ({scores.join(" + ")}) / 6 = {overall}
          </p>
        </div>
      )}
    </section>
  );
}
