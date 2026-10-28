"use client";

import { PieChart, Pie, Cell, ResponsiveContainer, Tooltip } from "recharts";

interface PieData { name: string; value: number }
interface Props { title: string; data: PieData[]; loading?: boolean }

const COLORS = ["#6366f1", "#e11d48", "#22c55e", "#f59e0b", "#0ea5e9"];

function Skeleton() {
  return (
    <div className="chart-card rounded-2xl p-6 animate-pulse">
      <div style={{ background: "var(--card-bd)" }} className="h-5 w-40 rounded-md mb-6" />
      <div className="flex gap-8 items-start">
        <div className="w-[280px] h-[280px] shrink-0 flex items-center justify-center">
          <div className="relative w-[220px] h-[220px]">
            <div style={{ background: "var(--card-bd)" }} className="absolute inset-0 rounded-full" />
            <div style={{ background: "var(--card-bg-2)" }} className="absolute inset-[40px] rounded-full" />
          </div>
        </div>
        <div className="flex-1 space-y-4 pt-2">
          {[90, 70, 80, 60, 75].map((w, i) => (
            <div key={i} className="flex items-center justify-between">
              <div className="flex items-center gap-3">
                <div style={{ background: "var(--card-bd)" }} className="w-3 h-3 rounded-full shrink-0" />
                <div style={{ background: "var(--card-bd)", width: `${w}px` }} className="h-3 rounded-sm" />
              </div>
              <div style={{ background: "var(--card-bd)" }} className="h-3 w-8 rounded-sm ml-4" />
            </div>
          ))}
        </div>
      </div>
    </div>
  );
}

export default function CustomPieChart({ title, data, loading = false }: Props) {
  if (loading) return <Skeleton />;

  return (
    <div className="chart-card relative rounded-2xl p-6">
      <h2 style={{ color: "var(--title-tx)" }} className="text-base font-semibold mb-6">{title}</h2>

      <div className="flex gap-8 items-start">
        <div className="w-[280px] h-[280px]">
          <ResponsiveContainer>
            <PieChart>
              <Pie data={data} dataKey="value" innerRadius={70} outerRadius={110} paddingAngle={3}>
                {data.map((_, i) => <Cell key={i} fill={COLORS[i % COLORS.length]} />)}
              </Pie>
              <Tooltip
                contentStyle={{ background: "var(--tooltip-bg)", borderRadius: 12, border: "1px solid var(--tooltip-bd)" }}
                labelStyle={{ color: "var(--tooltip-tx)" }}
                itemStyle={{ color: "var(--tooltip-tx)" }}
              />
            </PieChart>
          </ResponsiveContainer>
        </div>

        <div className="flex-1 max-h-[260px] max-w-[270px] overflow-y-auto pr-2 space-y-3 custom-scroll">
          {data.map((item, i) => (
            <div key={i} className="flex items-center justify-between text-sm">
              <div className="flex items-center gap-3">
                <div className="w-3 h-3 rounded-full shrink-0" style={{ backgroundColor: COLORS[i % COLORS.length] }} />
                <span style={{ color: "var(--body-tx)" }}>{item.name}</span>
              </div>
              <span style={{ color: "var(--title-tx)" }} className="font-semibold">{item.value}</span>
            </div>
          ))}
        </div>
      </div>
    </div>
  );
}
