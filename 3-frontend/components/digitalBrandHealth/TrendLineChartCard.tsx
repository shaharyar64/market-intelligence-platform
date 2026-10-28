"use client";

import {
  CartesianGrid,
  Legend,
  Line,
  LineChart,
  ResponsiveContainer,
  Tooltip,
  XAxis,
  YAxis,
} from "recharts";
import ExportExcelButton from "@/components/ui/ExportExcelButton";
import { getBankColor } from "@/lib/bankColors";

export type TrendRow = {
  date: string;
  [key: string]: string | number;
};

export type TrendLine = {
  key: string;
  label: string;
  color: string;
  dashed?: boolean;
};

export type TrendFrequency = "1m" | "3m" | "6m" | "1y";

type Props = {
  title: string;
  description: string;
  data: TrendRow[];
  lines: TrendLine[];
  loading?: boolean;
  bankOptions?: string[];
  selectedBanks?: string[];
  onBankToggle?: (bank: string) => void;
  maxSelectedBanks?: number;
  frequency?: TrendFrequency;
  onFrequencyChange?: (frequency: TrendFrequency) => void;
};

function formatBankName(bank: string) {
  return bank
    .replace(/_/g, " ")
    .replace(/\b\w/g, (letter) => letter.toUpperCase());
}

function Skeleton() {
  return (
    <div className="rounded-2xl border border-[var(--card-bd)] bg-[var(--card-bg)] p-5 shadow-sm">
      <div className="h-[320px] animate-pulse rounded-xl bg-[var(--card-bg-2)]" />
    </div>
  );
}

export default function TrendLineChartCard({
  title,
  description,
  data,
  lines,
  loading = false,
  bankOptions = [],
  selectedBanks = [],
  onBankToggle,
  maxSelectedBanks = 5,
  frequency,
  onFrequencyChange,
}: Props) {
  const showBankSelector = bankOptions.length > 0 && Boolean(onBankToggle);
  if (loading && !showBankSelector) return <Skeleton />;

  return (
    <section className="rounded-2xl border border-[var(--card-bd)] bg-[var(--card-bg-2)] p-6 shadow-lg">
      <h2 className="text-lg font-semibold text-[var(--title-tx)]">
        {title} <span className="text-xs text-[var(--muted-tx)]">(Trending)</span>
      </h2>
      <div className="mt-2 flex flex-col gap-3 sm:flex-row sm:items-start sm:justify-between">
        <p className="text-sm text-[var(--muted-tx)]">{description}</p>
        <div className="flex flex-wrap items-center gap-3">
          <ExportExcelButton
            rows={data}
            filename={title}
            sheetName={title}
            disabled={loading}
          />
          {frequency && onFrequencyChange && (
            <div className="inline-flex rounded-full border border-[var(--card-bd)] bg-[var(--card-bg)] p-1">
              {(["1m", "3m", "6m", "1y"] as TrendFrequency[]).map((item) => {
                const active = item === frequency;

                return (
                  <button
                    key={item}
                    type="button"
                    onClick={() => onFrequencyChange(item)}
                    className="h-8 rounded-full px-3 text-xs font-bold transition"
                    style={{
                      background: active ? "#2563eb" : "transparent",
                      color: active ? "#ffffff" : "var(--muted-tx)",
                    }}
                  >
                    {item}
                  </button>
                );
              })}
            </div>
          )}
        </div>
      </div>

      {showBankSelector && (
        <div className="mt-5 flex flex-wrap gap-2">
          {bankOptions.map((bank) => {
            const selectedIndex = selectedBanks.indexOf(bank);
            const selected = selectedIndex >= 0;
            const disabled = !selected && selectedBanks.length >= maxSelectedBanks;
            const activeColor = getBankColor(formatBankName(bank), Math.max(selectedIndex, 0));

            return (
              <button
                key={bank}
                type="button"
                onClick={() => onBankToggle?.(bank)}
                disabled={disabled}
                title={
                  disabled
                    ? `Select up to ${maxSelectedBanks} brands`
                    : formatBankName(bank)
                }
                className="h-9 rounded-full px-4 text-sm font-semibold transition disabled:cursor-not-allowed disabled:opacity-50"
                style={{
                  background: selected ? activeColor : "rgba(100, 116, 139, 0.24)",
                  color: selected ? "#ffffff" : "var(--muted-tx)",
                }}
              >
                {formatBankName(bank)}
              </button>
            );
          })}
        </div>
      )}

      <div className="mt-5 rounded-2xl border border-[var(--card-bd)] bg-[var(--card-bg)] p-5 shadow-sm">
        {loading ? (
          <div className="h-[320px] animate-pulse rounded-xl bg-[var(--card-bg-2)]" />
        ) : !data.length || !lines.length ? (
          <div className="flex h-[320px] items-center justify-center text-sm text-[var(--muted-tx)]">
            No data available
          </div>
        ) : (
          <div className="h-[320px]">
            <ResponsiveContainer width="100%" height="100%">
              <LineChart data={data} margin={{ top: 18, right: 24, left: 4, bottom: 18 }}>
                <CartesianGrid strokeDasharray="3 3" strokeOpacity={0.08} />
                <XAxis
                  dataKey="date"
                  tick={{ fill: "var(--muted-tx)", fontSize: 12, fontWeight: 600 }}
                  tickLine={false}
                  axisLine={{ stroke: "var(--card-bd)" }}
                />
                <YAxis
                  tick={{ fill: "var(--muted-tx)", fontSize: 12, fontWeight: 600 }}
                  tickLine={false}
                  axisLine={false}
                />
                <Tooltip
                  formatter={(value, name) => {
                    const line = lines.find((item) => item.key === name);
                    return [value ?? "-", line?.label ?? name];
                  }}
                  labelFormatter={(label) => `Period: ${label}`}
                  contentStyle={{
                    background: "var(--tooltip-bg)",
                    border: "1px solid var(--tooltip-bd)",
                    borderRadius: 12,
                    color: "var(--tooltip-tx)",
                  }}
                  labelStyle={{ color: "var(--tooltip-tx)" }}
                  itemStyle={{ color: "var(--tooltip-tx)" }}
                />
                <Legend
                  formatter={(value) => {
                    const line = lines.find((item) => item.key === value);
                    return line?.label ?? value;
                  }}
                  wrapperStyle={{ color: "var(--muted-tx)", fontSize: 12, fontWeight: 600 }}
                />
                {lines.map((line) => (
                  <Line
                    key={line.key}
                    type="monotone"
                    dataKey={line.key}
                    name={line.key}
                    stroke={line.color}
                    strokeWidth={line.dashed ? 2 : 2.5}
                    strokeDasharray={line.dashed ? "6 4" : undefined}
                    dot={line.dashed ? false : { r: 3 }}
                    activeDot={{ r: 5 }}
                    connectNulls
                  />
                ))}
              </LineChart>
            </ResponsiveContainer>
          </div>
        )}
      </div>
    </section>
  );
}
