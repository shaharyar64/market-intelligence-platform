"use client";

import type { ReactNode } from "react";
import GlassStatCard from "@/components/ui/StatCard";

export type KpiOverviewCard = {
  title: string;
  value: string | number;
  icon: ReactNode;
  gradient?: string;
};

type KpiOverviewProps = {
  title?: string;
  subtitle?: string;
  cards: KpiOverviewCard[];
  loading?: boolean;
  skeletonCount?: number;
  columns?: 3 | 4 | 5;
  className?: string;
};

const DEFAULT_SURFACES = [
  "linear-gradient(105deg, #f4fffd 0%, #f8fbff 50%, #bdeee4 100%)",
  "linear-gradient(105deg, #fffaf5 0%, #fffaf8 50%, #ffd3a6 100%)",
  "linear-gradient(105deg, #faf7ff 0%, #fbf8ff 50%, #decfff 100%)",
  "linear-gradient(105deg, #f7fbff 0%, #fbfdff 50%, #c7e7ff 100%)",
];

export function kpiSurface(index: number) {
  return DEFAULT_SURFACES[index % DEFAULT_SURFACES.length];
}

export default function KpiOverview({
  title = "KPI Overview",
  subtitle,
  cards,
  loading = false,
  skeletonCount = 3,
  columns = 3,
  className = "",
}: KpiOverviewProps) {
  const gridColumns =
    columns === 5
      ? "xl:grid-cols-5"
      : columns === 4
        ? "lg:grid-cols-4"
        : "lg:grid-cols-3";

  return (
    <section
      className={`rounded-2xl border border-[var(--card-bd)] bg-[var(--card-bg-2)] p-6 shadow-lg ${className}`}
    >
      <div className="mb-4">
        <p className="text-lg font-semibold text-[var(--title-tx)]">{title}</p>
        {subtitle && (
          <p className="text-xs text-[var(--muted-tx)]">{subtitle}</p>
        )}
      </div>

      <div className={`grid grid-cols-1 gap-6 sm:grid-cols-2 ${gridColumns}`}>
        {loading && cards.length === 0
          ? Array.from({ length: skeletonCount }).map((_, index) => (
              <GlassStatCard
                key={index}
                title="Loading"
                value="-"
                loading
                icon={<span className="h-4 w-4" />}
                gradient={
                  index === 1
                    ? "from-amber-500 to-orange-500"
                    : index === 2
                      ? "from-indigo-500 to-purple-500"
                      : "from-emerald-500 to-teal-500"
                }
              />
            ))
          : cards.map((card, index) => (
              <GlassStatCard
                key={`${card.title}-${index}`}
                title={card.title}
                value={card.value}
                loading={loading}
                icon={card.icon}
                gradient={
                  card.gradient ??
                  (index === 1
                    ? "from-amber-500 to-orange-500"
                    : index === 2
                      ? "from-indigo-500 to-purple-500"
                      : "from-emerald-500 to-teal-500")
                }
              />
            ))}
      </div>
    </section>
  );
}
