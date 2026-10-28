"use client";

import { useId, useState } from "react";
import { AlertTriangle, ChevronDown } from "lucide-react";

import type { ConfidenceBreakdown } from "@/lib/foodIdeaTesting";

const COMPONENTS: { key: keyof ConfidenceBreakdown; label: string; weight: number }[] = [
  { key: "relevance", label: "Evidence relevance", weight: 35 },
  { key: "volume", label: "Evidence volume", weight: 25 },
  { key: "spread", label: "Source spread", weight: 20 },
  { key: "recency", label: "Recency", weight: 10 },
  { key: "quality", label: "Data quality", weight: 10 },
];

export default function ConfidenceMeter({
  score, label, explanation, breakdown,
}: {
  score: number;
  label: string;
  explanation: string;
  breakdown: ConfidenceBreakdown;
}) {
  const [open, setOpen] = useState(false);
  const panelId = useId();
  const low = score <= 40;

  return (
    <div className="chart-card flex flex-col rounded-2xl p-5">
      <div className="flex items-baseline justify-between gap-3">
        <h3 style={{ color: "var(--title-tx)" }} className="text-sm font-semibold">Assessment confidence</h3>
        <span style={{ color: "var(--title-tx)" }} className="text-2xl font-bold tabular-nums">{score}%</span>
      </div>

      <span
        style={
          low
            ? { background: "var(--fi-mainstream-soft)", border: "1px solid var(--fi-mainstream-soft-bd)", color: "var(--fi-mainstream-tx)" }
            : { border: "1px solid var(--card-bd)", color: "var(--body-tx)" }
        }
        className="mt-2 inline-flex w-fit items-center gap-1 rounded-full px-2.5 py-0.5 text-xs font-semibold"
      >
        {low && <AlertTriangle size={12} aria-hidden="true" />}
        {label}
      </span>

      <p style={{ color: "var(--body-tx)" }} className="mt-3 text-sm leading-relaxed">
        {explanation}
      </p>

      <button
        type="button"
        onClick={() => setOpen((v) => !v)}
        aria-expanded={open}
        aria-controls={panelId}
        style={{ color: "var(--muted-tx)" }}
        className="mt-4 inline-flex w-fit items-center gap-1 text-xs font-medium transition-colors hover:text-[var(--title-tx)]"
      >
        How confidence is calculated
        <ChevronDown
          size={14}
          aria-hidden="true"
          className={`transition-transform duration-200 ${open ? "rotate-180" : ""}`}
        />
      </button>

      {open && (
        <div id={panelId} className="mt-3 space-y-2.5">
          {COMPONENTS.map(({ key, label: name, weight }) => {
            const value = Math.max(0, Math.min(100, breakdown[key] ?? 0));
            return (
              <div key={key}>
                <div className="flex justify-between text-xs" style={{ color: "var(--muted-tx)" }}>
                  <span>
                    {name} <span className="opacity-70">· {weight}%</span>
                  </span>
                  <span className="tabular-nums">{Math.round(value)}</span>
                </div>
                <div style={{ background: "var(--card-bd)" }} className="mt-1 h-1.5 w-full rounded-full">
                  <div
                    style={{ width: `${value}%`, background: "var(--fi-solid)" }}
                    className="h-1.5 rounded-full"
                  />
                </div>
              </div>
            );
          })}
          <p style={{ color: "var(--muted-tx)" }} className="pt-1 text-xs leading-relaxed">
            Each measure is scored 0 to 100 from the posts and trends retrieved for this concept,
            then weighted. Relevance is how close the evidence is in meaning to the concept. Source
            spread is measured on the search open to every source type. Recency counts posts from
            the 12 months before the latest data.
          </p>
        </div>
      )}
    </div>
  );
}
