"use client";

import { type ReactNode } from "react";
import { ArrowLeft } from "lucide-react";

export default function StepHeader({
  title, description, onBack, selections = [], action,
}: {
  title: string;
  description: string;
  onBack?: () => void;
  selections?: string[];
  action?: ReactNode;
}) {
  return (
    <header className="mb-8">
      {onBack && (
        <div className="mb-5 flex flex-wrap items-center gap-2">
          <button
            type="button"
            onClick={onBack}
            style={{ color: "var(--muted-tx)" }}
            className="inline-flex items-center gap-1.5 rounded-full py-1 pr-2 text-sm font-medium transition-colors hover:text-[var(--title-tx)]"
          >
            <ArrowLeft size={14} aria-hidden="true" />
            Back
          </button>
          {selections.length > 0 && (
            <span aria-hidden="true" className="mx-1 h-4 w-px" style={{ background: "var(--card-bd)" }} />
          )}
          {selections.map((s) => (
            <span
              key={s}
              style={{ border: "1px solid var(--card-bd)", color: "var(--body-tx)" }}
              className="rounded-full px-2.5 py-0.5 text-xs font-medium"
            >
              {s}
            </span>
          ))}
        </div>
      )}
      <div className="flex flex-wrap items-start justify-between gap-x-6 gap-y-3">
        <h2 style={{ color: "var(--title-tx)" }} className="text-2xl font-bold tracking-tight text-balance sm:text-3xl">
          {title}
        </h2>
        {action && <div className="shrink-0">{action}</div>}
      </div>
      <p style={{ color: "var(--muted-tx)" }} className="mt-2 max-w-2xl text-sm sm:text-base">
        {description}
      </p>
    </header>
  );
}
