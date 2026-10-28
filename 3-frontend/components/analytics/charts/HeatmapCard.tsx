"use client";

import { Fragment } from "react";

interface HeatmapProps {
  title: string;
  data: any[];
  xKey: string;
  yKey: string;
  valueKey: string;
}

export default function HeatmapCard({
  title,
  data,
  xKey,
  yKey,
  valueKey,
}: HeatmapProps) {
  if (!data || data.length === 0) return null;

  // Unique labels
  const xLabels = [...new Set(data.map((d) => d[xKey]))].sort((a, b) => a - b);
  const yLabels = [...new Set(data.map((d) => d[yKey]))];

  // Build matrix
  const matrix = yLabels.map((y) =>
    xLabels.map((x) => {
      const item = data.find((d) => d[xKey] === x && d[yKey] === y);
      return item ? item[valueKey] : 0;
    })
  );

  // Color scale
  const getColor = (value: number) => {
    if (value >= 70) return "bg-red-500";
    if (value >= 55) return "bg-orange-500";
    if (value >= 40) return "bg-yellow-400";
    if (value >= 25) return "bg-green-400";
    return "bg-slate-500";
  };

  return (
    <div className="relative rounded-2xl p-6 backdrop-blur-xl bg-white/5 border border-white/10 shadow-xl">
      {/* Title */}
      <h3 className="text-lg font-semibold mb-6 text-white">{title}</h3>

      {/* Heatmap */}
      <div className="overflow-x-auto">
        <div
          className="grid gap-2 text-xs"
          style={{
            gridTemplateColumns: `120px repeat(${xLabels.length}, 1fr)`,
          }}
        >
          {/* Header row */}
          <div />

          {xLabels.map((x) => (
            <div key={x} className="text-center text-slate-400">
              {String(x).padStart(2, "0")}
            </div>
          ))}

          {/* Rows */}
          {yLabels.map((y, rowIndex) => (
            <Fragment key={y}>
              {/* Y label */}
              <div className="text-slate-400 flex items-center">{y}</div>

              {/* Cells */}
              {matrix[rowIndex].map((value, colIndex) => (
                <div
                  key={`${y}-${xLabels[colIndex]}`}
                  className={`h-7 rounded-md transition-all duration-200 hover:scale-105 ${getColor(
                    value
                  )}`}
                  title={`${y} • ${String(xLabels[colIndex]).padStart(
                    2,
                    "0"
                  )}:00 → ${value}%`}
                />
              ))}
            </Fragment>
          ))}
        </div>
      </div>

      {/* Legend */}
      <div className="flex flex-wrap items-center gap-4 mt-6 text-xs text-slate-400">
        <span className="flex items-center gap-1">
          <div className="w-3 h-3 bg-slate-500 rounded"></div>
          0–25%
        </span>

        <span className="flex items-center gap-1">
          <div className="w-3 h-3 bg-green-400 rounded"></div>
          25–40%
        </span>

        <span className="flex items-center gap-1">
          <div className="w-3 h-3 bg-yellow-400 rounded"></div>
          40–55%
        </span>

        <span className="flex items-center gap-1">
          <div className="w-3 h-3 bg-orange-500 rounded"></div>
          55–70%
        </span>

        <span className="flex items-center gap-1">
          <div className="w-3 h-3 bg-red-500 rounded"></div>
          70%+
        </span>
      </div>
    </div>
  );
}