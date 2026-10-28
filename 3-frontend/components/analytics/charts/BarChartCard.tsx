"use client";

import { BarChart, Bar, XAxis, YAxis, CartesianGrid, Tooltip, ResponsiveContainer, Cell, LabelList } from "recharts";

type Props = {
  title: string;
  data: { name: string; value: number }[];
  colors?: string[];
  loading?: boolean;
  getBarColor?: (name: string, index: number) => string;
};

function Skeleton() {
  const bars = [60, 85, 45, 95, 70];
  return (
    <div className="chart-card rounded-2xl p-6 animate-pulse">
      <div style={{ background: "var(--card-bd)" }} className="h-5 w-48 rounded-md mb-6" />
      <div className="h-[300px] flex items-end gap-4 px-4">
        {bars.map((h, i) => (
          <div key={i} className="flex-1 flex flex-col items-center gap-2">
            <div style={{ background: "var(--card-bd)" }} className="h-3 w-6 rounded-sm" />
            <div style={{ height: `${h}%`, background: "var(--card-bd)" }} className="w-full rounded-t-lg" />
          </div>
        ))}
      </div>
    </div>
  );
}

export default function BarChartCard({
  title, data, loading = false,
  colors = ["#6366f1", "#e11d48", "#22c55e", "#f59e0b", "#0ea5e9"],
  getBarColor,
}: Props) {
  if (loading) return <Skeleton />;

  if (data.length === 0) {
    return (
      <section className="chart-card rounded-2xl p-6" aria-labelledby={`${title}-title`}>
        <h3 id={`${title}-title`} style={{ color: "var(--title-tx)" }} className="text-base font-semibold">{title}</h3>
        <p style={{ color: "var(--muted-tx)" }} className="mt-8 text-center text-sm">
          No data is available for the current filters.
        </p>
      </section>
    );
  }

  return (
    <section className="chart-card relative rounded-2xl p-4 sm:p-6" aria-labelledby={`${title}-title`}>
      <h3 id={`${title}-title`} style={{ color: "var(--title-tx)" }} className="mb-1 text-base font-semibold">{title}</h3>
      <p style={{ color: "var(--muted-tx)" }} className="mb-5 text-xs">
        {data.length} {data.length === 1 ? "category" : "categories"} in the current view
      </p>

      <div className="h-[260px] sm:h-[300px]" role="img" aria-label={`${title} bar chart`}>
        <ResponsiveContainer width="100%" height="100%">
          <BarChart data={data}>
            <CartesianGrid strokeDasharray="3 3" strokeOpacity={0.08} />
            <XAxis dataKey="name" tick={{ fill: "var(--muted-tx)", fontSize: 11 }} axisLine={false} tickLine={false} />
            <YAxis tick={{ fill: "var(--muted-tx)", fontSize: 11 }} axisLine={false} tickLine={false} />
            <Tooltip
              contentStyle={{ background: "var(--tooltip-bg)", borderRadius: 12, border: "1px solid var(--tooltip-bd)" }}
              labelStyle={{ color: "var(--tooltip-tx)" }}
              itemStyle={{ color: "var(--tooltip-tx)" }}
              cursor={{ fill: "rgba(99,102,241,0.06)" }}
            />
            <Bar dataKey="value" radius={[8, 8, 0, 0]} animationDuration={800}>
              {data.map((item, i) => (
                <Cell
                  key={`${item.name}-${i}`}
                  fill={getBarColor ? getBarColor(item.name, i) : colors[i % colors.length]}
                />
              ))}
              <LabelList dataKey="value" position="top" style={{ fill: "var(--muted-tx)", fontSize: 11, fontWeight: 600 }} />
            </Bar>
          </BarChart>
        </ResponsiveContainer>
      </div>
    </section>
  );
}
