"use client";

import React from "react";
import { LineChart, Line, XAxis, YAxis, Tooltip, ResponsiveContainer, CartesianGrid, Legend } from "recharts";

const fmtLabel = (key: string) => key.replace(/_/g, " ").replace(/\b\w/g, (c) => c.toUpperCase());

type LineConfig = { key: string; color: string; label?: string; tooltipLabel?: string; strokeDasharray?: string; hideInLegend?: boolean; hideInTooltip?: boolean; strokeOpacity?: number };
type Props = { title: string; data: any[]; xKey: string; lines: LineConfig[]; description?: string; decimals?: number; unit?: string; yAxisLabel?: string; customTooltipContent?: (payload: readonly any[], label: string) => React.ReactNode };

export default function MultiLineChartCard({ title, data, xKey, lines, description, decimals, unit, yAxisLabel, customTooltipContent }: Props) {
  if (!data || data.length === 0) {
    return <div style={{ color: "var(--muted-tx)" }} className="p-6 text-center text-sm">{title} — No data</div>;
  }

  return (
    <div className="chart-card relative overflow-hidden rounded-2xl p-6">
      <h3 style={{ color: "var(--title-tx)" }} className="text-base font-semibold mb-1">{title}</h3>
      {description && <p style={{ color: "var(--muted-tx)" }} className="text-xs mb-5">{description}</p>}

      <div className="h-[350px]">
        <ResponsiveContainer width="100%" height="100%">
          <LineChart data={data} margin={{ top: 5, right: 28, left: 0, bottom: 0 }}>
            <CartesianGrid strokeDasharray="3 3" strokeOpacity={0.08} />
            <XAxis dataKey={xKey} interval={0} tick={{ fontSize: 11, fill: "var(--muted-tx)" }} stroke="var(--card-bd)" />
            <YAxis tick={{ fontSize: 11, fill: "var(--muted-tx)" }} stroke="var(--card-bd)" tickFormatter={(v) => unit ? `${v}${unit}` : v} label={yAxisLabel ? { value: yAxisLabel, angle: -90, position: "insideLeft", offset: 10, style: { fill: "var(--muted-tx)", fontSize: 11, fontWeight: 600 } } : undefined} />
            <Tooltip
              content={customTooltipContent ? ({ payload, label }) => (
                <div style={{ background: "var(--tooltip-bg)", borderRadius: 12, border: "1px solid var(--tooltip-bd)", color: "var(--tooltip-tx)", padding: "10px 14px", fontSize: 13 }}>
                  <div style={{ marginBottom: 6, fontWeight: 600 }}>Date: {label}</div>
                  {customTooltipContent(payload ?? [], String(label ?? ""))}
                </div>
              ) : undefined}
              formatter={customTooltipContent ? undefined : (v: any, name?: string | number) => { const l = lines.find((x) => x.key === name); const val = typeof v === "number" && decimals !== undefined ? v.toFixed(decimals) : v ?? "-"; return [unit ? `${val}${unit}` : val, l?.tooltipLabel ?? l?.label ?? fmtLabel(String(name ?? ""))]; }}
              labelFormatter={customTooltipContent ? undefined : (l) => `Date: ${l}`}
              contentStyle={customTooltipContent ? undefined : { background: "var(--tooltip-bg)", borderRadius: 12, border: "1px solid var(--tooltip-bd)", color: "var(--tooltip-tx)" }}
              labelStyle={{ color: "var(--tooltip-tx)" }}
              itemStyle={{ color: "var(--tooltip-tx)" }}
            />
            <Legend wrapperStyle={{ fontSize: 12, color: "var(--muted-tx)" }} content={() => (
              <div style={{ display: 'flex', justifyContent: 'center', gap: '20px', fontSize: 12, color: 'var(--muted-tx)', flexWrap: 'wrap', paddingTop: 8 }}>
                {lines.filter((line) => !line.hideInLegend && line.strokeOpacity !== 0).map((line) => (
                  <div key={line.key} style={{ display: 'flex', alignItems: 'center', gap: '5px' }}>
                    {line.strokeDasharray ? (
                      <svg width="18" height="8"><line x1="0" y1="4" x2="18" y2="4" stroke={line.color} strokeWidth="2" strokeDasharray={line.strokeDasharray} /></svg>
                    ) : (
                      <span style={{ display: 'inline-block', width: '8px', height: '8px', borderRadius: '50%', backgroundColor: line.color }} />
                    )}
                    {line.label || line.key}
                  </div>
                ))}
              </div>
            )} />
            {lines.map((line) => (
              <Line key={line.key} type="monotone" dataKey={line.key} name={line.label || fmtLabel(line.key)} stroke={line.color} strokeWidth={2.5} strokeDasharray={line.strokeDasharray} strokeOpacity={line.strokeOpacity ?? 1} dot={false} activeDot={line.strokeOpacity === 0 ? false : { r: 5 }} connectNulls />
            ))}
          </LineChart>
        </ResponsiveContainer>
      </div>
    </div>
  );
}
