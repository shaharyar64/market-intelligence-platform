"use client";

// Shared rotated x-axis tick for recharts bar charts, so long/many category
// labels never get truncated with "..." — they rotate instead.
export function AxisTick({
  x,
  y,
  payload,
}: {
  x?: number;
  y?: number;
  payload?: { value?: string | number };
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

// Dynamic width/height so a bar chart's category count never crushes its
// labels — the chart scrolls horizontally instead, and the x-axis grows
// tall enough to fit the longest rotated label.
export function getBarChartDimensions(names: string[]) {
  const chartWidth = Math.max(names.length * 56, 640);
  const longestName = names.reduce((max, name) => Math.max(max, name.length), 0);
  const axisHeight = Math.min(260, Math.max(70, Math.round(longestName * 6.4) + 20));
  const chartHeight = 300 + axisHeight;

  return { chartWidth, axisHeight, chartHeight };
}
