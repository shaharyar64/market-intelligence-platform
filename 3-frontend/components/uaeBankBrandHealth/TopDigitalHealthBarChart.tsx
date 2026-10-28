"use client";

import { useId } from "react";
import {
  Bar,
  BarChart,
  CartesianGrid,
  Cell,
  LabelList,
  ReferenceLine,
  ResponsiveContainer,
  Tooltip,
  XAxis,
  YAxis,
} from "recharts";
import { getBankColor } from "@/lib/bankColors";
import { BRANDIQ_SCORE_MAX } from "@/lib/uaeBankBrandHealth";

type ChartData = {
  name: string;
  value: number;
};

type Props = {
  data: ChartData[];
  loading?: boolean;
};

function Skeleton() {
  return (
    <div className="rounded-2xl border border-[var(--card-bd)] bg-[var(--card-bg)] p-6 shadow-sm">
      <div className="h-[480px] animate-pulse">
        <div className="flex h-full items-end gap-4 px-6 pb-14 pt-8">
          {[70, 82, 64, 58, 56, 50, 48, 47, 45, 43, 40, 38, 36, 34].map((height, index) => (
            <div key={index} className="flex flex-1 flex-col items-center gap-3">
              <div
                className="w-full rounded-t-lg bg-[var(--card-bd)]"
                style={{ height: `${height}%` }}
              />
              <div className="h-3 w-full rounded bg-[var(--card-bd)]" />
            </div>
          ))}
        </div>
      </div>
    </div>
  );
}

function VerticalAxisTick({
  x,
  y,
  payload,
}: {
  x?: number;
  y?: number;
  payload?: { value: string };
}) {
  return (
    <g transform={`translate(${x ?? 0},${y ?? 0})`}>
      <text
        x={0}
        y={0}
        dy={8}
        textAnchor="end"
        transform="rotate(-90)"
        fill="var(--muted-tx)"
        fontSize={11}
        fontWeight={600}
      >
        {payload?.value}
      </text>
    </g>
  );
}

export default function TopDigitalHealthBarChart({
  data,
  loading = false,
}: Props) {
  const clipId = `digital-health-label-clip-${useId()}`;

  if (loading) return <Skeleton />;

  if (!data.length) {
    return (
      <div className="flex h-[480px] items-center justify-center rounded-2xl border border-[var(--card-bd)] bg-[var(--card-bg)] p-6 text-sm text-[var(--muted-tx)] shadow-sm">
        No data available
      </div>
    );
  }

  const average = data.reduce((sum, item) => sum + item.value, 0) / data.length;
  const chartWidth = Math.max(data.length * 56, 640);
  const longestName = data.reduce((max, item) => Math.max(max, item.name.length), 0);
  const axisHeight = Math.min(260, Math.max(70, Math.round(longestName * 6.4) + 20));
  const chartHeight = 300 + axisHeight;

  return (
    <div className="rounded-2xl border border-[var(--card-bd)] bg-[var(--card-bg)] p-5 shadow-sm">
      <div className="overflow-x-auto" style={{ height: chartHeight }}>
        <div style={{ width: chartWidth, minWidth: "100%", height: "100%" }}>
          <ResponsiveContainer width="100%" height="100%">
            <BarChart data={data} margin={{ top: 30, right: 24, left: 4, bottom: 8 }}>
              <defs>
                <clipPath id={clipId}>
                  <rect x="0" y="0" width="100%" height="100%" />
                </clipPath>
              </defs>
              <CartesianGrid strokeDasharray="3 3" strokeOpacity={0.08} vertical={false} />
              <XAxis
                dataKey="name"
                interval={0}
                height={axisHeight}
                tick={<VerticalAxisTick />}
                tickLine={false}
                axisLine={{ stroke: "var(--card-bd)" }}
              />
              <YAxis
                domain={[0, BRANDIQ_SCORE_MAX]}
                tick={{ fill: "var(--muted-tx)", fontSize: 12, fontWeight: 600 }}
                tickLine={false}
                axisLine={false}
              />
              <Tooltip
                formatter={(value) => [`${value}`, "Average Score"]}
                contentStyle={{
                  background: "var(--tooltip-bg)",
                  border: "1px solid var(--tooltip-bd)",
                  borderRadius: 12,
                  color: "var(--tooltip-tx)",
                }}
                labelStyle={{ color: "var(--tooltip-tx)" }}
                itemStyle={{ color: "var(--tooltip-tx)" }}
                cursor={{ fill: "rgba(84,170,236,0.08)" }}
              />
              <ReferenceLine
                y={average}
                stroke="var(--muted-tx)"
                strokeDasharray="4 4"
                strokeWidth={1.5}
                ifOverflow="extendDomain"
                label={{
                  value: `Category avg ${average.toFixed(1)}`,
                  position: "insideTopRight",
                  fill: "var(--muted-tx)",
                  fontSize: 12,
                  fontWeight: 700,
                }}
              />
              <Bar dataKey="value" radius={[8, 8, 0, 0]} maxBarSize={40}>
                {data.map((entry, index) => (
                  <Cell key={index} fill={getBankColor(entry.name, index)} />
                ))}
                <LabelList
                  dataKey="value"
                  position="top"
                  formatter={(value) =>
                    typeof value === "number" ? value.toFixed(2) : `${value ?? ""}`
                  }
                  style={{
                    fill: "var(--muted-tx)",
                    fontSize: 13,
                    fontWeight: 700,
                  }}
                />
              </Bar>
            </BarChart>
          </ResponsiveContainer>
        </div>
      </div>
    </div>
  );
}
