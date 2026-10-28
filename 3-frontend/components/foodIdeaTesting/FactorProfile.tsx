"use client";

import { FACTORS } from "@/lib/foodIdeaTestingFramework";
import type { FactorScore } from "@/lib/foodIdeaTesting";

const SIZE = 320;
const CENTER = SIZE / 2;
const HUB = 56;
const INNER = HUB + 5;
const OUTER = 154;
const GAP_DEG = 1.6;

function point(radius: number, deg: number): [number, number] {
  const rad = (deg * Math.PI) / 180;
  return [CENTER + radius * Math.cos(rad), CENTER + radius * Math.sin(rad)];
}

function sector(r0: number, r1: number, a0: number, a1: number): string {
  const [x0, y0] = point(r1, a0);
  const [x1, y1] = point(r1, a1);
  const [x2, y2] = point(r0, a1);
  const [x3, y3] = point(r0, a0);
  return `M${x0} ${y0} A${r1} ${r1} 0 0 1 ${x1} ${y1} L${x2} ${y2} A${r0} ${r0} 0 0 0 ${x3} ${y3} Z`;
}

const LABEL_RADIUS = INNER + 27;
const LABEL_CLEARANCE = INNER + 50;

function valueRadius(score: number): number {
  return Math.sqrt(INNER ** 2 + (OUTER ** 2 - INNER ** 2) * (score / 100));
}

export default function FactorProfile({ factors }: { factors: FactorScore[] }) {
  const slice = 360 / FACTORS.length;
  const rows = FACTORS.map((meta, i) => ({
    meta,
    score: Math.max(0, Math.min(100, factors.find((f) => f.factor_id === meta.id)?.score ?? 0)),
    a0: -90 + i * slice + GAP_DEG,
    a1: -90 + (i + 1) * slice - GAP_DEG,
  }));

  return (
    <svg
      viewBox={`0 0 ${SIZE} ${SIZE}`}
      className="mx-auto block w-full max-w-[320px]"
      role="img"
      aria-label={`InsightFactor profile: ${rows.map((r) => `${r.meta.label} ${r.score}`).join(", ")}`}
    >
      {rows.map(({ meta, score, a0, a1 }) => {
        const r1 = valueRadius(score);
        const [lx, ly] = point(LABEL_RADIUS, (a0 + a1) / 2);
        const words = meta.label.split(" ");
        const onFill = r1 >= LABEL_CLEARANCE;
        return (
          <g key={meta.id}>
            <title>{`${meta.label}: ${score}/100`}</title>
            <path d={sector(INNER, OUTER, a0, a1)} fill={meta.color} fillOpacity={0.14} />
            {score > 0 && <path d={sector(INNER, r1, a0, a1)} fill={meta.color} />}
            <text
              x={lx}
              y={ly - ((words.length - 1) * 12 + 15) / 2 + 4}
              textAnchor="middle"
              style={{ fill: onFill ? "var(--sidebar-bg)" : "var(--title-tx)" }}
              className="text-[10.5px] font-semibold"
            >
              {words.map((w, i) => (
                <tspan key={w} x={lx} dy={i === 0 ? 0 : 12}>{w}</tspan>
              ))}
              <tspan x={lx} dy={15} className="text-[14px] font-bold">{score}</tspan>
            </text>
          </g>
        );
      })}
      <circle cx={CENTER} cy={CENTER} r={HUB} fill="var(--fi-solid)" />
      <text
        x={CENTER}
        y={CENTER - 3}
        textAnchor="middle"
        style={{ fill: "var(--fi-solid-tx)" }}
        className="text-[12px] font-semibold"
      >
        <tspan x={CENTER}>Behavioural</tspan>
        <tspan x={CENTER} dy={15}>Impact</tspan>
      </text>
    </svg>
  );
}
