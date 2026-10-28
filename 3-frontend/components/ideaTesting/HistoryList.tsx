"use client";

import { Clock } from "lucide-react";

import { Skel } from "@/components/ui/RealEstateTrendsPanels";
import type { HistoryItem } from "@/lib/ideaTesting";

function formatDate(iso: string): string {
  return new Date(iso).toLocaleDateString(undefined, { month: "short", day: "numeric" });
}

function ScorePill({ score }: { score: number }) {
  return (
    <span
      style={{ background: "var(--card-bg)", border: "1px solid var(--card-bd)", color: "var(--title-tx)" }}
      className="shrink-0 rounded-full px-2.5 py-0.5 text-xs font-semibold"
    >
      {score}
    </span>
  );
}

export default function HistoryList({
  items, loading, onSelect,
}: {
  items: HistoryItem[];
  loading: boolean;
  onSelect: (id: string, kind: "assessment" | "comparison") => void;
}) {
  if (!loading && items.length === 0) return null;

  return (
    <section className="mt-10">
      <h3 style={{ color: "var(--muted-tx)" }} className="mb-3 text-xs font-semibold uppercase tracking-wide">
        Recent tests
      </h3>
      {loading ? (
        <div className="chart-card space-y-3 rounded-2xl p-5">
          <Skel className="h-5 w-full" />
          <Skel className="h-5 w-full" />
          <Skel className="h-5 w-2/3" />
        </div>
      ) : (
      <div className="chart-card divide-y rounded-2xl" style={{ borderColor: "var(--card-bd)" }}>
        {items.map((item) => {
          const id = item.kind === "assessment" ? item.assessment_id : item.comparison_id;
          return (
            <button
              key={id}
              type="button"
              onClick={() => onSelect(id, item.kind)}
              style={{ borderColor: "var(--card-bd)" }}
              className="flex w-full items-center gap-3 px-5 py-3 text-left transition-colors first:rounded-t-2xl last:rounded-b-2xl hover:bg-[var(--card-bg)]"
            >
              <Clock size={14} aria-hidden="true" style={{ color: "var(--muted-tx)" }} className="shrink-0" />
              {item.kind === "assessment" ? (
                <>
                  <span style={{ color: "var(--title-tx)" }} className="flex-1 truncate text-sm font-medium">
                    {item.title}
                  </span>
                  <ScorePill score={item.overall_score} />
                </>
              ) : (
                <>
                  <span style={{ color: "var(--title-tx)" }} className="flex-1 truncate text-sm font-medium">
                    {item.titles.join(" vs ")}
                  </span>
                  <div className="flex shrink-0 gap-1.5">
                    {item.scores.map((s, i) => <ScorePill key={i} score={s} />)}
                  </div>
                </>
              )}
              <span style={{ color: "var(--muted-tx)" }} className="w-14 shrink-0 text-right text-xs">
                {formatDate(item.created_at)}
              </span>
            </button>
          );
        })}
      </div>
      )}
    </section>
  );
}
