"use client";

import { Check } from "lucide-react";

const STEPS = [
  { id: "type", label: "Test type" },
  { id: "mode", label: "Single or multiple" },
  { id: "concept", label: "Add concepts" },
] as const;

export type WizardStepId = (typeof STEPS)[number]["id"];

export default function WizardStepper({ current }: { current: WizardStepId }) {
  const currentIndex = STEPS.findIndex((s) => s.id === current);
  return (
    <ol className="flex w-full items-center gap-3" aria-label="Progress">
      {STEPS.map((step, i) => {
        const done = i < currentIndex;
        const active = i === currentIndex;
        const reached = done || active;
        return (
          <li
            key={step.id}
            aria-current={active ? "step" : undefined}
            className={`flex items-center gap-3 ${i < STEPS.length - 1 ? "flex-1" : ""}`}
          >
            <span
              className="flex size-7 shrink-0 items-center justify-center rounded-full text-xs font-semibold transition-colors duration-300"
              style={{
                background: reached ? "var(--fi-solid)" : "var(--card-bg)",
                color: reached ? "var(--fi-solid-tx)" : "var(--muted-tx)",
                border: `1px solid ${reached ? "var(--fi-solid)" : "var(--card-bd)"}`,
              }}
            >
              {done ? <Check size={14} strokeWidth={3} aria-hidden="true" /> : i + 1}
            </span>
            <span
              style={{ color: reached ? "var(--title-tx)" : "var(--muted-tx)" }}
              className={`shrink-0 text-sm font-medium transition-colors duration-300 ${active ? "" : "hidden sm:inline"}`}
            >
              {step.label}
              {done && <span className="sr-only"> (completed)</span>}
            </span>
            {i < STEPS.length - 1 && (
              <span className="relative h-px min-w-4 flex-1 overflow-hidden" style={{ background: "var(--card-bd)" }}>
                <span
                  className="absolute inset-0 origin-left transition-transform duration-500 ease-out"
                  style={{ background: "var(--fi-solid)", transform: `scaleX(${done ? 1 : 0})` }}
                />
              </span>
            )}
          </li>
        );
      })}
    </ol>
  );
}
