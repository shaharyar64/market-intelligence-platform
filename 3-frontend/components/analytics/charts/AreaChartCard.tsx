"use client";

import { useId } from "react";
import { AreaChart, Area, XAxis, YAxis, Tooltip, ResponsiveContainer, CartesianGrid } from "recharts";

const fmtLabel = (key: string) => key.replace(/_/g, " ").replace(/\b\w/g, (c) => c.toUpperCase());

type Props = {
  title: string;
  data: Array<Record<string, string | number | null | undefined>>;
  dataKey: string;
  xKey: string;
  gradientFrom?: string;
  gradientTo?: string;
  label?: string;
  description?: string;
  decimals?: number;
  unit?: string;
};

export default function AreaChartCard({
  title, data, dataKey, xKey,
  gradientFrom = "#3b82f6", gradientTo = "#06b6d4",
  label, description, decimals, unit,
}: Props) {
  const gradientId = `ag-${useId()}`;

  if (!data || data.length === 0) {
    return (
      <section className="chart-card rounded-2xl p-6" aria-labelledby={`${title}-title`}>
        {title && <h3 id={`${title}-title`} style={{ color: "var(--title-tx)" }} className="text-base font-semibold">{title}</h3>}
        <p style={{ color: "var(--muted-tx)" }} className="mt-8 text-center text-sm">No data is available for the current filters.</p>
      </section>
    );
  }

  return (
    <section className="chart-card relative overflow-hidden rounded-2xl p-4 sm:p-6" aria-labelledby={title ? `${title}-title` : undefined}>
      {title && (
        <h3 id={`${title}-title`} style={{ color: "var(--title-tx)" }} className="mb-1 text-base font-semibold">{title}</h3>
      )}
      {description && (
        <p style={{ color: "var(--muted-tx)" }} className="text-xs mb-5">{description}</p>
      )}

      <div className="h-[260px] sm:h-[320px]" role="img" aria-label={`${title || label || fmtLabel(dataKey)} area chart`}>
        <ResponsiveContainer width="100%" height="100%">
          <AreaChart data={data}>
            <defs>
              <linearGradient id={gradientId} x1="0" y1="0" x2="0" y2="1">
                <stop offset="0%" stopColor={gradientFrom} stopOpacity={0.6} />
                <stop offset="100%" stopColor={gradientTo} stopOpacity={0} />
              </linearGradient>
            </defs>
            <CartesianGrid strokeDasharray="3 3" strokeOpacity={0.08} />
            <XAxis dataKey={xKey} tick={{ fontSize: 11, fill: "var(--muted-tx)" }} stroke="var(--card-bd)" />
            <YAxis tick={{ fontSize: 11, fill: "var(--muted-tx)" }} stroke="var(--card-bd)" tickFormatter={(v) => unit ? `${v}${unit}` : v} />
            <Tooltip
              formatter={(v) => {
                const value = Array.isArray(v) ? v[0] : v;
                const val = typeof value === "number" && decimals !== undefined ? value.toFixed(decimals) : value ?? "-";
                return [unit ? `${val}${unit}` : val, label || fmtLabel(dataKey)];
              }}
              labelFormatter={(l) => `Date: ${l}`}
              contentStyle={{ background: "var(--tooltip-bg)", borderRadius: 12, border: "1px solid var(--tooltip-bd)", color: "var(--tooltip-tx)" }}
              labelStyle={{ color: "var(--tooltip-tx)" }}
              itemStyle={{ color: "var(--tooltip-tx)" }}
            />
            <Area type="monotone" dataKey={dataKey} name={label || fmtLabel(dataKey)} stroke={gradientFrom} fill={`url(#${gradientId})`} strokeWidth={2.5} dot={{ r: 2.5 }} activeDot={{ r: 5 }} connectNulls />
          </AreaChart>
        </ResponsiveContainer>
      </div>
    </section>
  );
}
