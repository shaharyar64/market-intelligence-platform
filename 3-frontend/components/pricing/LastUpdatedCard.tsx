"use client";

import { CalendarClock } from "lucide-react";

interface LastUpdatedCardProps {
  value?: string | null;
  loading?: boolean;
  className?: string;
}

function formatLastUpdated(value?: string | null) {
  if (!value) return "Waiting for data";

  const parsed = new Date(value);
  if (Number.isNaN(parsed.getTime())) return value;

  return parsed.toLocaleDateString("en-GB", {
    day: "2-digit",
    month: "short",
    year: "numeric",
  });
}

export default function LastUpdatedCard({
  value,
  loading = false,
  className = "",
}: LastUpdatedCardProps) {
  return (
    <div className={`flex justify-end ${className}`.trim()}>
      <div
        className="inline-flex items-center gap-2.5 rounded-xl px-3 py-2 shadow-md"
        style={{
          background: "linear-gradient(135deg, var(--card-bg-2), rgba(59,130,246,0.08))",
          border: "1px solid var(--card-bd)",
          backdropFilter: "var(--blur)",
          WebkitBackdropFilter: "var(--blur)",
        }}
      >
        <div
          className="flex h-8 w-8 items-center justify-center rounded-lg"
          style={{
            background: "linear-gradient(135deg, rgba(59,130,246,0.18), rgba(14,165,233,0.14))",
            border: "1px solid rgba(59,130,246,0.18)",
            color: "var(--title-tx)",
          }}
        >
          <CalendarClock size={15} />
        </div>
        <div className="leading-tight">
          <div
            className="text-[9px] font-semibold uppercase tracking-[0.22em]"
            style={{ color: "var(--muted-tx)" }}
          >
            Last Updated
          </div>
          <div
            className="mt-0.5 text-xs font-semibold"
            style={{ color: "var(--title-tx)" }}
          >
            {loading ? "Refreshing dashboard data..." : formatLastUpdated(value)}
          </div>
        </div>
      </div>
    </div>
  );
}
