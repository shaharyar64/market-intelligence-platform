"use client";

import { BarChart, Bar, XAxis, YAxis, CartesianGrid, Tooltip, ResponsiveContainer, Cell, LabelList } from "recharts";

type ChartData = { name: string; value: number };
type Props = { title: string; data?: ChartData[] | null; colors?: string[]; height?: number | string; loading?: boolean };

function Skeleton({ height }: { height: number | string }) {
  const rows = [85, 60, 95, 45, 75, 55, 80, 40, 70, 50];
  return (
    <div className="chart-card rounded-2xl p-6 animate-pulse">
      <div style={{ background: "var(--card-bd)" }} className="h-5 w-48 rounded-md mb-6" />
      <div style={{ height }} className="flex flex-col justify-around gap-3 py-2">
        {rows.map((w, i) => (
          <div key={i} className="flex items-center gap-3">
            <div className="w-[120px] shrink-0">
              <div style={{ background: "var(--card-bd)", width: `${40 + (i % 4) * 15}%` }} className="h-3 rounded-sm" />
            </div>
            <div style={{ width: `${w}%`, maxWidth: `${w}%`, background: "var(--card-bd)" }} className="h-5 rounded-r-lg" />
            <div style={{ background: "var(--card-bd)" }} className="h-3 w-8 rounded-sm shrink-0" />
          </div>
        ))}
      </div>
    </div>
  );
}

export default function HorizontalBarChartCard({
  title, data, height = 300, loading = false,
  colors = ["#6366f1", "#8b5cf6", "#06b6d4", "#10b981", "#f59e0b"],
}: Props) {
  if (loading) return <Skeleton height={height} />;
  const safeData = data ?? [];

  return (
    <div className="chart-card relative rounded-2xl p-6">
      <h3 style={{ color: "var(--title-tx)" }} className="text-base font-semibold mb-6">{title}</h3>

      {safeData.length === 0 ? (
        <div style={{ height, color: "var(--muted-tx)" }} className="flex items-center justify-center text-sm">
          No data available
        </div>
      ) : (
        <div style={{ height }}>
          <ResponsiveContainer width="100%" height="100%">
            <BarChart layout="vertical" data={safeData} margin={{ top: 4, right: 36, left: 8, bottom: 4 }}>
              <CartesianGrid strokeDasharray="3 3" strokeOpacity={0.08} />
              <XAxis type="number" tick={{ fill: "var(--muted-tx)", fontSize: 11 }} axisLine={false} tickLine={false} />
              <YAxis type="category" dataKey="name" tick={{ fill: "var(--muted-tx)", fontSize: 11 }} axisLine={false} tickLine={false} width={120} />
              <Tooltip
                contentStyle={{ background: "var(--tooltip-bg)", borderRadius: 12, border: "1px solid var(--tooltip-bd)" }}
                labelStyle={{ color: "var(--tooltip-tx)" }}
                itemStyle={{ color: "var(--tooltip-tx)" }}
                cursor={{ fill: "rgba(99,102,241,0.06)" }}
              />
              <Bar dataKey="value" radius={[0, 8, 8, 0]} animationDuration={800} maxBarSize={18}>
                {safeData.map((_, i) => <Cell key={i} fill={colors[i % colors.length]} />)}
                <LabelList dataKey="value" position="right" style={{ fill: "var(--muted-tx)", fontSize: 11, fontWeight: 600 }} />
              </Bar>
            </BarChart>
          </ResponsiveContainer>
        </div>
      )}
    </div>
  );
}
