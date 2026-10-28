"use client";

import { useEffect, useMemo, useRef, useState } from "react";
import DashboardTopbar from "@/components/layout/DashboardTopbar";
import FilterSelect from "@/components/filters/FilterSelect";
import ExportExcelButton from "@/components/ui/ExportExcelButton";
import {
  Area,
  AreaChart,
  Bar,
  BarChart,
  CartesianGrid,
  Cell,
  LabelList,
  Legend,
  Line,
  LineChart,
  ResponsiveContainer,
  Tooltip,
  XAxis,
  YAxis,
} from "recharts";
import {
  getUaeBankBrandHealthAssociations,
  getSocialAssociationsDistribution,
  getSocialAssociationsOverTime,
  getSocialAvgSentimentByBank,
  getSocialAvgSentimentByTopic,
  getSocialEngagementTrend,
  getSocialFilters,
  getSocialPostsDistribution,
  getSocialTopBanksBySentiment,
  getSocialTopTopics,
  getSocialTopGrowing,
  getSocialVolumeTrend,
  type SocialAssociationItem,
  type SocialEngagementTrendItem,
  type SocialFilters,
  type SocialFiltersResponse,
  type SocialPostDistributionItem,
  type SocialSentimentItem,
  type SocialTopGrowingItem,
  type SocialTopTopicItem,
  type SocialVolumeTrendFrequency,
  type SocialVolumeTrendItem,
} from "@/lib/uaeBankBrandHealth";
import { getBankColor } from "@/lib/bankColors";
import { AxisTick, getBarChartDimensions } from "@/components/uaeBankBrandHealth/ChartAxisTick";
import {
  Heart,
  MessageCircle,
  PieChart as PieChartIcon,
  Repeat2,
  TrendingUp,
} from "lucide-react";

type ShareOfVoiceItem = {
  name: string;
  value: number;
  share: number;
};

type VolumeTrendPoint = {
  period: string;
  volume: number;
};

type EngagementTrendPoint = {
  period: string;
  engagement: number;
};

type TopicSentimentPoint = {
  name: string;
  avgSentiment: number;
  mentions: number;
};

type AssociationPoint = {
  name: string;
  value: number;
};

type AssociationTrendRow = {
  period: string;
  [key: string]: string | number;
};

type SocialAnalysisTab = "overview" | "topics" | "associations";

type FilterOption = {
  label: string;
  value: string;
};

const SOCIAL_ANALYSIS_TABS: Array<{
  id: SocialAnalysisTab;
  label: string;
  icon: typeof PieChartIcon;
}> = [
  { id: "overview", label: "Social Overview", icon: PieChartIcon },
  { id: "topics", label: "Topic Analysis", icon: MessageCircle },
  { id: "associations", label: "Associations", icon: Repeat2 },
];

const ASSOCIATION_MIN_DATE = "2025-01-01";
const ASSOCIATION_MAX_DATE = new Date().toISOString().slice(0, 10);

function normalizeFilterValues(value: unknown): string[] {
  if (!Array.isArray(value)) return [];

  return value
    .map((item) => {
      if (typeof item === "string" || typeof item === "number") {
        return String(item);
      }

      if (item && typeof item === "object") {
        const record = item as Record<string, unknown>;
        const candidate =
          record.value ?? record.label ?? record.name ?? record.bank ?? record.platform;
        if (typeof candidate === "string" || typeof candidate === "number") {
          return String(candidate);
        }
      }

      return "";
    })
    .filter(Boolean);
}

function clampAssociationDate(value: string, fallback: string) {
  const date = value || fallback;
  if (date < ASSOCIATION_MIN_DATE) return ASSOCIATION_MIN_DATE;
  if (date > ASSOCIATION_MAX_DATE) return ASSOCIATION_MAX_DATE;
  return date;
}

function getSocialFilterOptions(
  filters: SocialFiltersResponse | null,
  keys: string[],
  allLabel: string
): FilterOption[] {
  const data = filters?.data ?? {};
  const values = keys.flatMap((key) => normalizeFilterValues(data[key]));
  const uniqueValues = Array.from(new Set(values));

  return [
    { label: allLabel, value: "" },
    ...uniqueValues.map((value) => ({ label: value, value })),
  ];
}

const SOCIAL_COLORS = [
  "#8b5cf6",
  "#38bdf8",
  "#0f766e",
  "#84cc16",
  "#facc15",
  "#f59e0b",
  "#0ea5e9",
  "#8b5cf6",
  "#e76f51",
  "#14b8a6",
  "#2563eb",
  "#ef4444",
  "#be185d",
  "#64748b",
  "#0891b2",
  "#4f46e5",
  "#7c2d12",
];
const MAX_SELECTED_ASSOCIATIONS = 5;

function formatNumber(value: number) {
  return new Intl.NumberFormat("en-US").format(Math.round(value));
}

function formatCompactNumber(value: number) {
  if (Math.abs(value) < 1000) return formatNumber(value);

  return new Intl.NumberFormat("en-US", {
    notation: "compact",
    maximumFractionDigits: 2,
  }).format(value);
}

function formatPercent(value: number) {
  return `${value.toFixed(value >= 10 ? 1 : 2)}%`;
}

function isCurrentMonthPeriod(period: string): boolean {
  const parsed = new Date(period.length <= 7 ? `${period}-01` : period);
  if (Number.isNaN(parsed.getTime())) return false;

  const now = new Date();
  return (
    parsed.getUTCFullYear() === now.getUTCFullYear() &&
    parsed.getUTCMonth() === now.getUTCMonth()
  );
}

function formatPeriodLabel(period: string): string {
  return isCurrentMonthPeriod(period) ? "Month to date" : period;
}

function pickStringValue(row: SocialSentimentItem, keys: string[], fallback = "Unknown") {
  for (const key of keys) {
    const value = row[key];
    if (typeof value === "string" && value.trim()) return value.trim();
    if (typeof value === "number" && Number.isFinite(value)) return String(value);
  }

  return fallback;
}

function pickNumberValue(row: SocialSentimentItem, keys: string[], fallback = 0) {
  for (const key of keys) {
    const value = row[key];
    if (typeof value === "number" && Number.isFinite(value)) return value;
    if (typeof value === "string" && value.trim() && Number.isFinite(Number(value))) {
      return Number(value);
    }
  }

  return fallback;
}

function normalizeSentimentRows(rows: SocialSentimentItem[]): TopicSentimentPoint[] {
  return rows.map((row) => ({
    name: pickStringValue(row, ["name", "topic", "bank", "brand", "category"]),
    avgSentiment: pickNumberValue(row, [
      "avg_sentiment",
      "average_sentiment",
      "sentiment",
      "score",
      "value",
    ]),
    mentions: pickNumberValue(row, [
      "mentions",
      "mention_count",
      "total_mentions",
      "count",
      "volume",
      "total",
    ]),
  }));
}

function normalizeAssociationRows(rows: SocialAssociationItem[]): AssociationPoint[] {
  return rows
    .map((row) => ({
      name: pickStringValue(row, [
        "name",
        "association",
        "label",
        "topic",
        "keyword",
        "category",
      ]),
      value: pickNumberValue(row, [
        "value",
        "total_mentions",
        "count",
        "mentions",
        "mention_count",
        "volume",
        "total",
        "score",
        "frequency",
      ]),
    }))
    .filter((item) => item.value > 0);
}

function normalizeAssociationTrendRows(rows: SocialAssociationItem[]): AssociationTrendRow[] {
  const longFormRows = rows
    .map((row) => ({
      association: pickStringValue(row, [
        "association",
        "name",
        "label",
        "topic",
        "keyword",
        "category",
      ]),
      period: pickStringValue(row, ["period", "month", "date", "week"], ""),
      value: pickNumberValue(row, [
        "total_mentions",
        "mentions",
        "mention_count",
        "value",
        "count",
        "volume",
        "total",
        "frequency",
      ]),
    }))
    .filter((row) => row.association && row.period && row.value > 0);

  if (longFormRows.length > 0) {
    const periodMap = new Map<string, AssociationTrendRow>();

    longFormRows.forEach((row) => {
      const existing = periodMap.get(row.period) ?? { period: row.period };
      const currentValue = existing[row.association];
      existing[row.association] =
        (typeof currentValue === "number" ? currentValue : 0) + row.value;
      periodMap.set(row.period, existing);
    });

    return Array.from(periodMap.values()).sort((a, b) =>
      String(a.period).localeCompare(String(b.period))
    );
  }

  return rows.map((row) => {
    const period = pickStringValue(row, ["period", "month", "date", "week"], "");
    const normalized: AssociationTrendRow = { period };

    const nested = row.data ?? row.values ?? row.associations;
    if (nested && typeof nested === "object" && !Array.isArray(nested)) {
      Object.entries(nested as Record<string, unknown>).forEach(([key, value]) => {
        if (typeof value === "number" && Number.isFinite(value)) {
          normalized[key] = value;
        }
      });
    }

    Object.entries(row).forEach(([key, value]) => {
      if (["period", "month", "date", "week", "data", "values", "associations"].includes(key)) return;
      if (typeof value === "number" && Number.isFinite(value)) {
        normalized[key] = value;
      }
    });

    return normalized;
  });
}

function extractAssociationTrendSeries(rows: AssociationTrendRow[]) {
  return Array.from(
    new Set(rows.flatMap((row) => Object.keys(row).filter((key) => key !== "period")))
  );
}

function ShareOfVoiceTooltip({
  active,
  payload,
}: {
  active?: boolean;
  payload?: Array<{ payload: ShareOfVoiceItem }>;
}) {
  if (!active || !payload?.length) return null;

  const item = payload[0].payload as ShareOfVoiceItem;

  return (
    <div className="rounded-xl border border-[var(--card-bd)] bg-[var(--card-bg)] px-3 py-2 shadow-xl">
      <p className="text-sm font-bold text-[var(--title-tx)]">{item.name}</p>
      <p className="mt-1 text-xs text-[var(--muted-tx)]">
        {formatNumber(item.value)} posts · {formatPercent(item.share)}
      </p>
    </div>
  );
}

function ShareOfVoiceCard({
  data,
  loading,
}: {
  data: ShareOfVoiceItem[];
  loading: boolean;
}) {
  const sorted = [...data].sort((a, b) => b.value - a.value);

  const { chartWidth, axisHeight, chartHeight } = getBarChartDimensions(
    sorted.map((item) => item.name)
  );

  return (
    <section className="rounded-2xl border border-[var(--card-bd)] bg-[var(--card-bg)] p-6 shadow-sm">
      <div className="flex items-start justify-between gap-4">
        <div>
          <h2 className="text-xl font-bold text-[var(--title-tx)]">
            Share of Voice
          </h2>
          <p className="mt-1 text-sm text-[var(--muted-tx)]">
            Social presence share by total posts.
          </p>
        </div>
        <ExportExcelButton
          rows={sorted}
          filename="share_of_voice"
          sheetName="Share of Voice"
          disabled={loading}
        />
      </div>

      {loading ? (
        <div
          className="mt-6 animate-pulse rounded-2xl border border-[var(--card-bd)] bg-[var(--card-bg-2)] p-5 shadow-sm"
          style={{ height: chartHeight }}
        />
      ) : sorted.length === 0 ? (
        <div
          className="mt-6 flex items-center justify-center rounded-2xl border border-[var(--card-bd)] bg-[var(--card-bg-2)] p-5 text-sm text-[var(--muted-tx)] shadow-sm"
          style={{ height: chartHeight }}
        >
          No social post distribution data available
        </div>
      ) : (
        <div
          className="mt-6 overflow-x-auto rounded-2xl border border-[var(--card-bd)] bg-[var(--card-bg-2)] px-4 py-5 shadow-sm"
          style={{ height: chartHeight }}
        >
          <div style={{ width: chartWidth, minWidth: "100%", height: "100%" }}>
            <ResponsiveContainer
              width="100%"
              height="100%"
              initialDimension={{ width: chartWidth, height: chartHeight }}
            >
              <BarChart data={sorted} margin={{ top: 28, right: 24, left: 0, bottom: 8 }}>
                <CartesianGrid strokeDasharray="3 3" strokeOpacity={0.12} vertical={false} />
                <XAxis
                  dataKey="name"
                  interval={0}
                  height={axisHeight}
                  tick={<AxisTick />}
                  tickLine={false}
                  axisLine={{ stroke: "var(--card-bd)" }}
                />
                <YAxis
                  width={52}
                  tick={{ fill: "var(--muted-tx)", fontSize: 12, fontWeight: 700 }}
                  tickFormatter={(value) => formatCompactNumber(Number(value))}
                  tickLine={false}
                  axisLine={false}
                />
                <Tooltip
                  content={<ShareOfVoiceTooltip />}
                  cursor={{ fill: "rgba(37, 99, 235, 0.08)" }}
                />
                <Bar dataKey="value" radius={[8, 8, 0, 0]} maxBarSize={40}>
                  {sorted.map((item, index) => (
                    <Cell key={item.name} fill={getBankColor(item.name, index)} />
                  ))}
                  <LabelList
                    dataKey="value"
                    position="top"
                    formatter={(value) =>
                      typeof value === "number" ? formatCompactNumber(value) : `${value ?? ""}`
                    }
                    style={{ fill: "var(--muted-tx)", fontSize: 11, fontWeight: 700 }}
                  />
                </Bar>
              </BarChart>
            </ResponsiveContainer>
          </div>
        </div>
      )}
    </section>
  );
}

type SocialTrendMetric = "volume" | "engagement";

function SocialTrendCard({
  metric,
  onMetricChange,
  volumeData,
  engagementData,
  frequency,
  onFrequencyChange,
  volumeLoading,
  engagementLoading,
}: {
  metric: SocialTrendMetric;
  onMetricChange: (metric: SocialTrendMetric) => void;
  volumeData: VolumeTrendPoint[];
  engagementData: EngagementTrendPoint[];
  frequency: SocialVolumeTrendFrequency;
  onFrequencyChange: (frequency: SocialVolumeTrendFrequency) => void;
  volumeLoading: boolean;
  engagementLoading: boolean;
}) {
  const loading = metric === "volume" ? volumeLoading : engagementLoading;
  const accent = metric === "volume" ? "#2563eb" : "#db2777";
  const data =
    metric === "volume"
      ? volumeData.map((item) => ({ period: item.period, value: item.volume }))
      : engagementData.map((item) => ({ period: item.period, value: item.engagement }));
  const peak = data.reduce<{ period: string; value: number } | null>(
    (best, item) => (!best || item.value > best.value ? item : best),
    null
  );
  const valueLabel = metric === "volume" ? "Posts" : "Engagement";

  return (
    <section className="rounded-2xl border border-[var(--card-bd)] bg-[var(--card-bg)] p-6 shadow-sm">
      <div className="flex flex-col gap-4 sm:flex-row sm:items-start sm:justify-between">
        <div>
          <h2 className="text-xl font-bold text-[var(--title-tx)]">
            Social Trend
          </h2>
          <p className="mt-1 text-sm text-[var(--muted-tx)]">
            {metric === "volume"
              ? "Social post volume over time."
              : "Social engagement momentum over time."}
          </p>
        </div>

        <div className="flex flex-wrap items-start justify-end gap-3">
          <ExportExcelButton
            rows={data}
            filename={metric === "volume" ? "post_volume_trend" : "engagement_trend"}
            sheetName={metric === "volume" ? "Post Volume Trend" : "Engagement Trend"}
            disabled={loading}
          />
          <div className="rounded-xl border border-[var(--card-bd)] bg-[var(--card-bg-2)] px-3 py-2 text-right shadow-sm">
            <p className="text-[10px] font-bold uppercase tracking-wide text-[var(--muted-tx)]">
              Peak Period
            </p>
            <p className="mt-0.5 text-sm font-bold text-[var(--title-tx)]">
              {loading || !peak ? "-" : formatPeriodLabel(peak.period)}
            </p>
          </div>
        </div>
      </div>

      <div className="mt-4 flex flex-wrap items-center justify-between gap-3">
        <div className="inline-flex rounded-full border border-[var(--card-bd)] bg-[var(--card-bg-2)] p-1">
          {(
            [
              { id: "volume" as const, label: "Post volume" },
              { id: "engagement" as const, label: "Engagement" },
            ]
          ).map((item) => {
            const active = item.id === metric;

            return (
              <button
                key={item.id}
                type="button"
                onClick={() => onMetricChange(item.id)}
                className="h-8 rounded-full px-3 text-xs font-bold transition"
                style={{
                  background: active ? accent : "transparent",
                  color: active ? "#ffffff" : "var(--muted-tx)",
                }}
              >
                {item.label}
              </button>
            );
          })}
        </div>

        <div className="inline-flex rounded-full border border-[var(--card-bd)] bg-[var(--card-bg-2)] p-1">
          {(["1m", "3m", "6m", "1y"] as SocialVolumeTrendFrequency[]).map(
            (item) => {
              const active = item === frequency;

              return (
                <button
                  key={item}
                  type="button"
                  onClick={() => onFrequencyChange(item)}
                  className="h-8 rounded-full px-3 text-xs font-bold transition"
                  style={{
                    background: active ? accent : "transparent",
                    color: active ? "#ffffff" : "var(--muted-tx)",
                  }}
                >
                  {item}
                </button>
              );
            }
          )}
        </div>
      </div>

      {loading ? (
        <div className="mt-6 h-[290px] animate-pulse rounded-2xl bg-[var(--card-bg-2)]" />
      ) : data.length === 0 ? (
        <div className="mt-6 flex h-[290px] items-center justify-center text-sm text-[var(--muted-tx)]">
          No {metric === "volume" ? "volume" : "engagement"} trend data available
        </div>
      ) : (
        <div className="mt-6 h-[290px]">
          <ResponsiveContainer width="100%" height="100%">
            <AreaChart
              data={data}
              margin={{ top: 12, right: 16, left: 0, bottom: 8 }}
            >
              <defs>
                <linearGradient id="socialTrendFill" x1="0" y1="0" x2="0" y2="1">
                  <stop offset="0%" stopColor={accent} stopOpacity={0.28} />
                  <stop offset="100%" stopColor={accent} stopOpacity={0.03} />
                </linearGradient>
              </defs>
              <CartesianGrid strokeDasharray="3 3" strokeOpacity={0.12} vertical={false} />
              <XAxis
                dataKey="period"
                tickFormatter={formatPeriodLabel}
                tick={{ fill: "var(--muted-tx)", fontSize: 11, fontWeight: 700 }}
                tickLine={false}
                axisLine={{ stroke: "var(--card-bd)" }}
              />
              <YAxis
                width={48}
                tick={{ fill: "var(--muted-tx)", fontSize: 11, fontWeight: 700 }}
                tickFormatter={(value) => formatCompactNumber(Number(value))}
                tickLine={false}
                axisLine={false}
              />
              <Tooltip
                formatter={(value) => [formatNumber(Number(value)), valueLabel]}
                labelFormatter={(label) => `Period: ${formatPeriodLabel(String(label))}`}
                contentStyle={{
                  background: "var(--tooltip-bg)",
                  border: "1px solid var(--tooltip-bd)",
                  borderRadius: 12,
                  color: "var(--tooltip-tx)",
                }}
                labelStyle={{ color: "var(--tooltip-tx)" }}
                itemStyle={{ color: "var(--tooltip-tx)" }}
              />
              <Area
                type="monotone"
                dataKey="value"
                stroke={accent}
                strokeWidth={3}
                fill="url(#socialTrendFill)"
                dot={{ r: 3, fill: accent, strokeWidth: 0 }}
                activeDot={{ r: 5, fill: accent, stroke: "#ffffff", strokeWidth: 2 }}
              />
            </AreaChart>
          </ResponsiveContainer>
        </div>
      )}
    </section>
  );
}

function TopicMentionsCard({
  data,
  loading,
}: {
  data: { name: string; value: number }[];
  loading: boolean;
}) {
  const sorted = [...data].sort((a, b) => b.value - a.value);
  const total = sorted.reduce((sum, item) => sum + item.value, 0);
  const { chartWidth, axisHeight, chartHeight } = getBarChartDimensions(
    sorted.map((item) => item.name)
  );

  return (
    <section className="flex h-full flex-col rounded-2xl border border-[var(--card-bd)] bg-[var(--card-bg)] p-6 shadow-sm">
      <div className="flex shrink-0 items-start justify-between gap-4">
        <div>
          <h2 className="text-xl font-bold text-[var(--title-tx)]">
            Top Topics by Mentions
          </h2>
          <p className="mt-1 text-sm text-[var(--muted-tx)]">
            Topics ranked by conversation volume.
          </p>
        </div>

        <div className="flex items-start gap-2">
          <ExportExcelButton
            rows={sorted}
            filename="top_topics_by_mentions"
            sheetName="Top Topics"
            disabled={loading}
          />
          <div className="rounded-full border border-[var(--card-bd)] bg-[var(--card-bg-2)] px-3 py-1 text-xs font-semibold text-[var(--muted-tx)]">
            {loading ? "-" : formatNumber(total)} mentions
          </div>
        </div>
      </div>

      {loading ? (
        <div
          className="mt-6 flex-1 animate-pulse rounded-2xl border border-[var(--card-bd)] bg-[var(--card-bg-2)] p-5 shadow-sm"
          style={{ minHeight: chartHeight }}
        />
      ) : sorted.length === 0 ? (
        <div
          className="mt-6 flex flex-1 items-center justify-center rounded-2xl border border-[var(--card-bd)] bg-[var(--card-bg-2)] p-5 text-sm text-[var(--muted-tx)] shadow-sm"
          style={{ minHeight: chartHeight }}
        >
          No topic mentions data available
        </div>
      ) : (
        <div
          className="mt-6 flex-1 overflow-x-auto rounded-2xl border border-[var(--card-bd)] bg-[var(--card-bg-2)] px-4 py-5 shadow-sm"
          style={{ minHeight: chartHeight }}
        >
          <div style={{ width: chartWidth, minWidth: "100%", height: "100%" }}>
            <ResponsiveContainer
              width="100%"
              height="100%"
              initialDimension={{ width: chartWidth, height: chartHeight }}
            >
              <BarChart data={sorted} margin={{ top: 28, right: 24, left: 0, bottom: 8 }}>
                <CartesianGrid strokeDasharray="3 3" strokeOpacity={0.12} vertical={false} />
                <XAxis
                  dataKey="name"
                  interval={0}
                  height={axisHeight}
                  tick={<AxisTick />}
                  tickLine={false}
                  axisLine={{ stroke: "var(--card-bd)" }}
                />
                <YAxis
                  width={52}
                  tick={{ fill: "var(--muted-tx)", fontSize: 12, fontWeight: 700 }}
                  tickFormatter={(value) => formatCompactNumber(Number(value))}
                  tickLine={false}
                  axisLine={false}
                />
                <Tooltip
                  cursor={{ fill: "rgba(37, 99, 235, 0.08)" }}
                  formatter={(value) => [formatNumber(Number(value)), "Mentions"]}
                  contentStyle={{
                    background: "var(--tooltip-bg)",
                    border: "1px solid var(--tooltip-bd)",
                    borderRadius: 12,
                    color: "var(--tooltip-tx)",
                  }}
                  labelStyle={{ color: "var(--tooltip-tx)" }}
                  itemStyle={{ color: "var(--tooltip-tx)" }}
                />
                <Bar dataKey="value" radius={[8, 8, 0, 0]} maxBarSize={40}>
                  {sorted.map((item, index) => (
                    <Cell
                      key={`${item.name}-${index}`}
                      fill={SOCIAL_COLORS[index % SOCIAL_COLORS.length]}
                    />
                  ))}
                  <LabelList
                    dataKey="value"
                    position="top"
                    formatter={(value) =>
                      typeof value === "number" ? formatCompactNumber(value) : `${value ?? ""}`
                    }
                    style={{ fill: "var(--muted-tx)", fontSize: 11, fontWeight: 700 }}
                  />
                </Bar>
              </BarChart>
            </ResponsiveContainer>
          </div>
        </div>
      )}
    </section>
  );
}

function TopicSentimentBars({
  data,
  loading,
}: {
  data: TopicSentimentPoint[];
  loading: boolean;
}) {
  const ticks = [5, 4, 3, 2, 1, 0];
  const { chartWidth, axisHeight } = getBarChartDimensions(data.map((item) => item.name));

  return (
    <section className="flex h-full flex-col rounded-2xl border border-[var(--card-bd)] bg-[var(--card-bg)] p-6 shadow-sm">
      <div className="flex shrink-0 items-start justify-between gap-4">
        <div>
          <h2 className="text-xl font-bold text-[var(--title-tx)]">
            Average Sentiment by Topic
          </h2>
          <p className="mt-1 text-sm text-[var(--muted-tx)]">
            Sentiment score segmented by discussion topic.
          </p>
        </div>

        <div className="flex items-start gap-2">
          <ExportExcelButton
            rows={data.map((item) => ({ ...item }))}
            filename="average_sentiment_by_topic"
            sheetName="Sentiment By Topic"
            disabled={loading}
          />
          <div className="rounded-full border border-amber-400/20 bg-amber-400/10 px-3 py-1 text-xs font-semibold text-amber-500">
            5.0 max
          </div>
        </div>
      </div>

      {loading ? (
        <div
          className="mt-6 flex-1 animate-pulse rounded-2xl border border-[var(--card-bd)] bg-[var(--card-bg-2)] p-5 shadow-sm"
          style={{ minHeight: 300 + axisHeight }}
        />
      ) : data.length === 0 ? (
        <div
          className="mt-6 flex flex-1 items-center justify-center rounded-2xl border border-[var(--card-bd)] bg-[var(--card-bg-2)] p-5 text-sm text-[var(--muted-tx)] shadow-sm"
          style={{ minHeight: 300 + axisHeight }}
        >
          No topic sentiment data available
        </div>
      ) : (
        <div
          className="mt-6 flex-1 overflow-x-auto rounded-2xl border border-[var(--card-bd)] bg-[var(--card-bg-2)] p-5 shadow-sm"
          style={{ minHeight: 300 + axisHeight }}
        >
          <div
            className="grid h-full grid-cols-[32px_1fr] gap-4"
            style={{ width: chartWidth, minWidth: "100%" }}
          >
            <div className="relative h-full">
              {ticks.map((tick) => (
                <div
                  key={tick}
                  className="absolute right-0 translate-y-1/2 text-xs font-semibold text-[var(--muted-tx)]"
                  style={{ bottom: `${(tick / 5) * 100}%` }}
                >
                  {tick}
                </div>
              ))}
            </div>

            <div className="flex h-full flex-col">
              <div className="relative flex-1">
                {[1, 2, 3, 4].map((tick) => (
                  <div
                    key={tick}
                    className="absolute inset-x-0 border-t border-dashed border-[var(--card-bd)] opacity-60"
                    style={{ bottom: `${(tick / 5) * 100}%` }}
                  />
                ))}
                <div className="absolute inset-x-0 bottom-0 border-t border-[var(--card-bd)]" />

                <div
                  className="relative z-10 grid h-full items-end gap-5"
                  style={{ gridTemplateColumns: `repeat(${data.length}, minmax(0, 1fr))` }}
                >
                  {data.map((item, index) => {
                    const color = SOCIAL_COLORS[index % SOCIAL_COLORS.length];
                    const height = Math.min(Math.max((item.avgSentiment / 5) * 100, 3), 100);
                    const tooltip = `${item.name}: ${item.avgSentiment.toFixed(2)} • ${formatNumber(item.mentions)} mentions`;

                    return (
                      <div
                        key={`${item.name}-${index}`}
                        className="relative flex h-full min-w-0 flex-col items-center justify-end"
                        title={tooltip}
                      >
                        <span
                          className="absolute whitespace-nowrap text-[10px] font-bold text-[var(--muted-tx)]"
                          style={{ bottom: `calc(${height}% + 6px)` }}
                        >
                          {item.avgSentiment.toFixed(2)}
                        </span>
                        <div className="mx-auto h-full w-full max-w-10 overflow-hidden rounded-t-2xl">
                          <div
                            className="absolute inset-x-0 bottom-0 mx-auto w-full max-w-10 rounded-t-2xl transition-all"
                            style={{ height: `${height}%`, background: color }}
                          />
                        </div>
                      </div>
                    );
                  })}
                </div>
              </div>

              <div
                className="mt-3 grid items-start gap-5"
                style={{ gridTemplateColumns: `repeat(${data.length}, minmax(0, 1fr))`, height: axisHeight }}
              >
                {data.map((item, index) => (
                  <div key={`${item.name}-label-${index}`} className="flex min-w-0 justify-center">
                    <span
                      className="truncate text-[11px] font-semibold text-[var(--muted-tx)]"
                      style={{ writingMode: "vertical-rl", transform: "rotate(180deg)" }}
                      title={item.name}
                    >
                      {item.name}
                    </span>
                  </div>
                ))}
              </div>
            </div>
          </div>
        </div>
      )}
    </section>
  );
}

function BankSentimentBars({
  title,
  description,
  data,
  loading,
  emptyMessage,
  filenamePrefix,
}: {
  title: string;
  description: string;
  data: TopicSentimentPoint[];
  loading: boolean;
  emptyMessage: string;
  filenamePrefix: string;
}) {
  const average =
    data.length > 0
      ? data.reduce((sum, item) => sum + item.avgSentiment, 0) / data.length
      : null;
  const { chartWidth, axisHeight } = getBarChartDimensions(data.map((item) => item.name));

  return (
    <section className="flex h-full flex-col rounded-2xl border border-[var(--card-bd)] bg-[var(--card-bg)] p-6 shadow-sm">
      <div className="flex shrink-0 items-start justify-between gap-4">
        <div>
          <h2 className="text-xl font-bold text-[var(--title-tx)]">{title}</h2>
          <p className="mt-1 text-sm text-[var(--muted-tx)]">{description}</p>
        </div>

        <ExportExcelButton
          rows={data.map((item) => ({ ...item }))}
          filename={filenamePrefix}
          sheetName={title}
          disabled={loading}
        />
      </div>

      {loading ? (
        <div
          className="mt-6 flex-1 animate-pulse rounded-2xl border border-[var(--card-bd)] bg-[var(--card-bg-2)] p-5 shadow-sm"
          style={{ minHeight: 300 + axisHeight }}
        />
      ) : data.length === 0 ? (
        <div
          className="mt-6 flex flex-1 items-center justify-center rounded-2xl border border-[var(--card-bd)] bg-[var(--card-bg-2)] p-5 text-sm text-[var(--muted-tx)] shadow-sm"
          style={{ minHeight: 300 + axisHeight }}
        >
          {emptyMessage}
        </div>
      ) : (
        <div
          className="mt-6 flex-1 overflow-x-auto rounded-2xl border border-[var(--card-bd)] bg-[var(--card-bg-2)] p-5 shadow-sm"
          style={{ minHeight: 300 + axisHeight }}
        >
          <div
            className="grid h-full grid-cols-[34px_1fr] gap-4"
            style={{ width: chartWidth, minWidth: "100%" }}
          >
            <div className="relative h-full">
              {[5, 4, 3, 2, 1, 0].map((tick) => (
                <div
                  key={tick}
                  className="absolute right-0 translate-y-1/2 text-xs font-semibold text-[var(--muted-tx)]"
                  style={{ bottom: `${(tick / 5) * 100}%` }}
                >
                  {tick}
                </div>
              ))}
            </div>

            <div className="flex h-full flex-col">
              <div className="relative flex-1">
                {[1, 2, 3, 4].map((tick) => (
                  <div
                    key={tick}
                    className="absolute inset-x-0 border-t border-dashed border-[var(--card-bd)] opacity-60"
                    style={{ bottom: `${(tick / 5) * 100}%` }}
                  />
                ))}
                <div className="absolute inset-x-0 bottom-0 border-t border-[var(--card-bd)]" />

                {average !== null && (
                  <div
                    className="absolute inset-x-0 z-20 border-t-2 border-dashed border-amber-500"
                    style={{ bottom: `${(average / 5) * 100}%` }}
                  >
                    <span className="absolute right-0 -translate-y-full rounded-full bg-amber-500 px-2 py-0.5 text-[10px] font-bold text-white">
                      Avg {average.toFixed(2)}
                    </span>
                  </div>
                )}

                <div
                  className="relative z-10 grid h-full items-end gap-3"
                  style={{ gridTemplateColumns: `repeat(${data.length}, minmax(0, 1fr))` }}
                >
                  {data.map((item, index) => {
                    const color = getBankColor(item.name, index);
                    const height = Math.min(Math.max((item.avgSentiment / 5) * 100, 4), 100);

                    return (
                      <div
                        key={`${item.name}-${index}`}
                        className="relative flex h-full min-w-0 flex-col items-center justify-end"
                      >
                        <span
                          className="absolute whitespace-nowrap text-[10px] font-bold text-[var(--muted-tx)]"
                          style={{ bottom: `calc(${height}% + 6px)` }}
                        >
                          {item.avgSentiment.toFixed(2)}
                        </span>
                        <div className="mx-auto h-full w-full max-w-10 overflow-hidden rounded-t-xl">
                          <div
                            className="absolute inset-x-0 bottom-0 mx-auto w-full max-w-10 rounded-t-xl transition-all"
                            style={{ height: `${height}%`, background: color }}
                          />
                        </div>
                      </div>
                    );
                  })}
                </div>
              </div>

              <div
                className="mt-3 grid items-start gap-3"
                style={{ gridTemplateColumns: `repeat(${data.length}, minmax(0, 1fr))`, height: axisHeight }}
              >
                {data.map((item, index) => (
                  <div key={`${item.name}-rating-label-${index}`} className="flex min-w-0 justify-center">
                    <span
                      className="truncate text-[11px] font-semibold text-[var(--muted-tx)]"
                      style={{ writingMode: "vertical-rl", transform: "rotate(180deg)" }}
                      title={item.name}
                    >
                      {item.name}
                    </span>
                  </div>
                ))}
              </div>
            </div>
          </div>
        </div>
      )}
    </section>
  );
}

function AssociationsCard({
  data,
  loading,
}: {
  data: AssociationPoint[];
  loading: boolean;
}) {
  const sorted = [...data].sort((a, b) => b.value - a.value);
  const total = sorted.reduce((sum, item) => sum + item.value, 0);

  return (
    <section className="rounded-2xl border border-[var(--card-bd)] bg-[var(--card-bg)] p-6 shadow-sm xl:col-span-2">
      <div className="flex flex-col gap-3 sm:flex-row sm:items-start sm:justify-between">
        <div>
          <h2 className="text-xl font-bold text-[var(--title-tx)]">
            Associations
          </h2>
          <p className="mt-1 text-sm text-[var(--muted-tx)]">
            Every tracked association, sorted by mentions, with share of total.
          </p>
        </div>

        <div className="flex items-start gap-3">
          <ExportExcelButton
            rows={sorted.map((item) => ({
              ...item,
              share: total > 0 ? Number(((item.value / total) * 100).toFixed(2)) : 0,
            }))}
            filename="associations"
            sheetName="Associations"
            disabled={loading}
          />
        </div>
      </div>

      {loading ? (
        <div className="mt-6 h-[360px] animate-pulse rounded-2xl border border-[var(--card-bd)] bg-[var(--card-bg-2)] p-5 shadow-sm" />
      ) : sorted.length === 0 ? (
        <div className="mt-6 flex h-[360px] items-center justify-center rounded-2xl border border-[var(--card-bd)] bg-[var(--card-bg-2)] p-5 text-sm text-[var(--muted-tx)] shadow-sm">
          No association data available
        </div>
      ) : (
        (() => {
          const { chartWidth, axisHeight, chartHeight } = getBarChartDimensions(
            sorted.map((item) => item.name)
          );

          return (
            <div className="mt-6 overflow-x-auto rounded-2xl border border-[var(--card-bd)] bg-[var(--card-bg-2)] px-4 py-5 shadow-sm">
              <div style={{ width: chartWidth, minWidth: "100%", height: chartHeight }}>
                <ResponsiveContainer
                  width="100%"
                  height="100%"
                  initialDimension={{ width: chartWidth, height: chartHeight }}
                >
                  <BarChart data={sorted} margin={{ top: 28, right: 24, left: 0, bottom: 8 }}>
                    <CartesianGrid strokeDasharray="3 3" strokeOpacity={0.12} vertical={false} />
                    <XAxis
                      dataKey="name"
                      interval={0}
                      height={axisHeight}
                      tick={<AxisTick />}
                      tickLine={false}
                      axisLine={{ stroke: "var(--card-bd)" }}
                    />
                    <YAxis
                      width={52}
                      tick={{ fill: "var(--muted-tx)", fontSize: 12, fontWeight: 700 }}
                      tickFormatter={(value) => formatCompactNumber(Number(value))}
                      tickLine={false}
                      axisLine={false}
                    />
                    <Tooltip
                      cursor={{ fill: "rgba(37, 99, 235, 0.08)" }}
                      formatter={(value) => {
                        const share =
                          total > 0 ? ((Number(value) / total) * 100).toFixed(1) : "0.0";
                        return [`${formatNumber(Number(value))} (${share}%)`, "Mentions"];
                      }}
                      labelFormatter={(label) => String(label)}
                      contentStyle={{
                        background: "var(--tooltip-bg)",
                        border: "1px solid var(--tooltip-bd)",
                        borderRadius: 12,
                        color: "var(--tooltip-tx)",
                      }}
                      labelStyle={{ color: "var(--tooltip-tx)" }}
                      itemStyle={{ color: "var(--tooltip-tx)" }}
                    />
                    <Bar dataKey="value" radius={[8, 8, 0, 0]} maxBarSize={40}>
                      {sorted.map((item, index) => (
                        <Cell
                          key={`${item.name}-${index}`}
                          fill={SOCIAL_COLORS[index % SOCIAL_COLORS.length]}
                        />
                      ))}
                      <LabelList
                        dataKey="value"
                        position="top"
                        formatter={(value) =>
                          typeof value === "number" ? formatCompactNumber(value) : `${value ?? ""}`
                        }
                        style={{ fill: "var(--muted-tx)", fontSize: 11, fontWeight: 700 }}
                      />
                    </Bar>
                  </BarChart>
                </ResponsiveContainer>
              </div>
            </div>
          );
        })()
      )}
    </section>
  );
}

function AssociationsTrendCard({
  data,
  frequency,
  loading,
  onFrequencyChange,
  associationOptions = [],
  selectedAssociations = [],
  onAssociationToggle,
  maxSelectedAssociations = 5,
}: {
  data: AssociationTrendRow[];
  frequency: SocialVolumeTrendFrequency;
  loading: boolean;
  onFrequencyChange: (frequency: SocialVolumeTrendFrequency) => void;
  associationOptions?: string[];
  selectedAssociations?: string[];
  onAssociationToggle?: (association: string) => void;
  maxSelectedAssociations?: number;
}) {
  const series = useMemo(() => {
    const keys = new Set<string>();
    data.forEach((row) => {
      Object.keys(row).forEach((key) => {
        if (key !== "period") keys.add(key);
      });
    });
    return Array.from(keys).slice(0, 5);
  }, [data]);
  const showAssociationSelector =
    associationOptions.length > 0 && Boolean(onAssociationToggle);

  return (
    <section className="rounded-2xl border border-[var(--card-bd)] bg-[var(--card-bg)] p-6 shadow-sm xl:col-span-2">
      <div className="flex flex-col gap-4 sm:flex-row sm:items-start sm:justify-between">
        <div>
          <h2 className="text-xl font-bold text-[var(--title-tx)]">
            Associations Over Time
          </h2>
          <p className="mt-1 text-sm text-[var(--muted-tx)]">
            Trend of top association mentions over time.
          </p>
        </div>
        <div className="flex flex-wrap items-center gap-3">
          <ExportExcelButton
            rows={data}
            filename="associations_over_time"
            sheetName="Associations Over Time"
            disabled={loading}
          />
          <div className="inline-flex rounded-full border border-[var(--card-bd)] bg-[var(--card-bg-2)] p-1">
            {(["1m", "3m", "6m", "1y"] as SocialVolumeTrendFrequency[]).map((item) => {
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
        </div>
      </div>

      {showAssociationSelector && (
        <div className="mt-5 flex flex-wrap gap-2">
          {associationOptions.map((association) => {
            const selectedIndex = selectedAssociations.indexOf(association);
            const selected = selectedIndex >= 0;
            const disabled =
              !selected && selectedAssociations.length >= maxSelectedAssociations;
            const color = selected
              ? SOCIAL_COLORS[selectedIndex % SOCIAL_COLORS.length]
              : "rgba(100, 116, 139, 0.24)";

            return (
              <button
                key={association}
                type="button"
                onClick={() => onAssociationToggle?.(association)}
                disabled={disabled}
                title={
                  disabled
                    ? `Select up to ${maxSelectedAssociations} associations`
                    : association
                }
                className="h-9 rounded-full px-4 text-sm font-semibold transition disabled:cursor-not-allowed disabled:opacity-50"
                style={{
                  background: color,
                  color: selected ? "#ffffff" : "var(--muted-tx)",
                }}
              >
                {association}
              </button>
            );
          })}
        </div>
      )}

      {loading ? (
        <div className="mt-6 h-[340px] animate-pulse rounded-2xl bg-[var(--card-bg-2)]" />
      ) : data.length === 0 || series.length === 0 ? (
        <div className="mt-6 flex h-[340px] items-center justify-center text-sm text-[var(--muted-tx)]">
          No associations trend data available
        </div>
      ) : (
        <div className="mt-6 h-[340px]">
          <ResponsiveContainer width="100%" height="100%">
            <LineChart data={data} margin={{ top: 14, right: 20, left: 0, bottom: 8 }}>
              <CartesianGrid strokeDasharray="3 3" strokeOpacity={0.12} vertical={false} />
              <XAxis
                dataKey="period"
                tick={{ fill: "var(--muted-tx)", fontSize: 11, fontWeight: 700 }}
                tickLine={false}
                axisLine={{ stroke: "var(--card-bd)" }}
              />
              <YAxis
                width={56}
                tick={{ fill: "var(--muted-tx)", fontSize: 11, fontWeight: 700 }}
                tickFormatter={(value) => formatCompactNumber(Number(value))}
                tickLine={false}
                axisLine={false}
              />
              <Tooltip
                formatter={(value, name) => [formatCompactNumber(Number(value)), String(name)]}
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
              <Legend wrapperStyle={{ color: "var(--muted-tx)", fontSize: 12, fontWeight: 700 }} />
              {series.map((key, index) => (
                <Line
                  key={key}
                  type="monotone"
                  dataKey={key}
                  stroke={SOCIAL_COLORS[index % SOCIAL_COLORS.length]}
                  strokeWidth={2.5}
                  dot={{ r: 3 }}
                  activeDot={{ r: 5 }}
                  connectNulls
                />
              ))}
            </LineChart>
          </ResponsiveContainer>
        </div>
      )}
    </section>
  );
}

export default function SocialAnalysisPage() {
  const [activeTab, setActiveTab] = useState<SocialAnalysisTab>("overview");
  const [filters, setFilters] = useState<SocialFiltersResponse | null>(null);
  const [selectedBank, setSelectedBank] = useState("");
  const [selectedPlatform, setSelectedPlatform] = useState("");
  const [associationStartDate, setAssociationStartDate] =
    useState(ASSOCIATION_MIN_DATE);
  const [associationEndDate, setAssociationEndDate] =
    useState(ASSOCIATION_MAX_DATE);
  const [associationOptions, setAssociationOptions] = useState<string[]>([]);
  const [selectedTrendAssociations, setSelectedTrendAssociations] = useState<
    string[]
  >([]);
  const [distribution, setDistribution] = useState<SocialPostDistributionItem[]>(
    []
  );
  const [topGrowing, setTopGrowing] = useState<SocialTopGrowingItem[]>([]);
  const [volumeTrend, setVolumeTrend] = useState<SocialVolumeTrendItem[]>([]);
  const [engagementTrend, setEngagementTrend] = useState<
    SocialEngagementTrendItem[]
  >([]);
  const [topTopics, setTopTopics] = useState<SocialTopTopicItem[]>([]);
  const [avgSentimentByTopic, setAvgSentimentByTopic] = useState<
    SocialSentimentItem[]
  >([]);
  const [avgSentimentByBank, setAvgSentimentByBank] = useState<
    SocialSentimentItem[]
  >([]);
  const [topBanksBySentiment, setTopBanksBySentiment] = useState<
    SocialSentimentItem[]
  >([]);
  const [associationsDistribution, setAssociationsDistribution] = useState<
    SocialAssociationItem[]
  >([]);
  const [associationsTrend, setAssociationsTrend] = useState<
    SocialAssociationItem[]
  >([]);
  const [socialTrendMetric, setSocialTrendMetric] = useState<SocialTrendMetric>("volume");
  const [socialTrendFrequency, setSocialTrendFrequency] =
    useState<SocialVolumeTrendFrequency>("1m");
  const [associationsFrequency, setAssociationsFrequency] =
    useState<SocialVolumeTrendFrequency>("1m");
  const [loading, setLoading] = useState(true);
  const [topGrowingLoading, setTopGrowingLoading] = useState(true);
  const [trendLoading, setTrendLoading] = useState(true);
  const [engagementLoading, setEngagementLoading] = useState(true);
  const [topTopicsLoading, setTopTopicsLoading] = useState(true);
  const [avgTopicLoading, setAvgTopicLoading] = useState(true);
  const [avgBankLoading, setAvgBankLoading] = useState(true);
  const [topBanksLoading, setTopBanksLoading] = useState(true);
  const [associationsDistributionLoading, setAssociationsDistributionLoading] =
    useState(true);
  const [associationsTrendLoading, setAssociationsTrendLoading] = useState(true);
  const [error, setError] = useState("");
  const defaultTrendAssociationsSyncedRef = useRef(false);

  const selectedSocialFilters = useMemo<SocialFilters>(
    () => ({
      bank: selectedBank || undefined,
      platform: selectedPlatform || undefined,
    }),
    [selectedBank, selectedPlatform]
  );

  const selectedAssociationFilters = useMemo<
    Pick<SocialFilters, "bank" | "platform" | "startDate" | "endDate">
  >(
    () => ({
      bank: selectedBank || undefined,
      platform: selectedPlatform || undefined,
      startDate: associationStartDate,
      endDate: associationEndDate,
    }),
    [associationEndDate, associationStartDate, selectedBank, selectedPlatform]
  );
  const selectedAssociationTrendFilters = useMemo<
    Pick<SocialFilters, "bank" | "platform" | "startDate" | "endDate"> & {
      associations?: string[];
    }
  >(
    () => ({
      bank: selectedBank || undefined,
      platform: selectedPlatform || undefined,
      startDate: associationStartDate,
      endDate: associationEndDate,
      associations: selectedTrendAssociations.slice(0, MAX_SELECTED_ASSOCIATIONS),
    }),
    [
      associationEndDate,
      associationStartDate,
      selectedBank,
      selectedPlatform,
      selectedTrendAssociations,
    ]
  );

  useEffect(() => {
    let active = true;

    getUaeBankBrandHealthAssociations()
      .then((res) => {
        if (!active) return;
        setAssociationOptions((res.associations ?? []).filter(Boolean));
      })
      .catch(() => {
        if (!active) return;
        setAssociationOptions([]);
      });

    return () => {
      active = false;
    };
  }, []);

  useEffect(() => {
    let active = true;

    getSocialFilters()
      .then((res) => {
        if (!active) return;
        setFilters(res);
      })
      .catch((err) => {
        if (!active) return;
        setError(err instanceof Error ? err.message : "Failed to load filters");
        setFilters(null);
      });

    return () => {
      active = false;
    };
  }, []);

  useEffect(() => {
    let active = true;

    getSocialPostsDistribution(selectedSocialFilters)
      .then((res) => {
        if (!active) return;
        setDistribution(res.distribution ?? []);
      })
      .catch((err) => {
        if (!active) return;
        setError(err instanceof Error ? err.message : "Failed to load data");
      })
      .finally(() => {
        if (active) setLoading(false);
      });

    return () => {
      active = false;
    };
  }, [selectedSocialFilters]);

  useEffect(() => {
    let active = true;

    getSocialTopGrowing(selectedSocialFilters)
      .then((res) => {
        if (!active) return;
        setTopGrowing(res.data ?? []);
      })
      .catch((err) => {
        if (!active) return;
        setError(err instanceof Error ? err.message : "Failed to load data");
        setTopGrowing([]);
      })
      .finally(() => {
        if (active) setTopGrowingLoading(false);
      });

    return () => {
      active = false;
    };
  }, [selectedSocialFilters]);

  useEffect(() => {
    let active = true;

    getSocialTopTopics(10)
      .then((res) => {
        if (!active) return;
        setTopTopics(res.data ?? []);
      })
      .catch((err) => {
        if (!active) return;
        setError(err instanceof Error ? err.message : "Failed to load data");
        setTopTopics([]);
      })
      .finally(() => {
        if (active) setTopTopicsLoading(false);
      });

    return () => {
      active = false;
    };
  }, []);

  useEffect(() => {
    let active = true;

    getSocialAvgSentimentByTopic()
      .then((res) => {
        if (!active) return;
        setAvgSentimentByTopic(res.data ?? []);
      })
      .catch((err) => {
        if (!active) return;
        setError(err instanceof Error ? err.message : "Failed to load data");
        setAvgSentimentByTopic([]);
      })
      .finally(() => {
        if (active) setAvgTopicLoading(false);
      });

    return () => {
      active = false;
    };
  }, []);

  useEffect(() => {
    let active = true;

    getSocialAvgSentimentByBank()
      .then((res) => {
        if (!active) return;
        setAvgSentimentByBank(res.data ?? []);
      })
      .catch((err) => {
        if (!active) return;
        setError(err instanceof Error ? err.message : "Failed to load data");
        setAvgSentimentByBank([]);
      })
      .finally(() => {
        if (active) setAvgBankLoading(false);
      });

    return () => {
      active = false;
    };
  }, []);

  useEffect(() => {
    let active = true;

    getSocialTopBanksBySentiment(10)
      .then((res) => {
        if (!active) return;
        setTopBanksBySentiment(res.data ?? []);
      })
      .catch((err) => {
        if (!active) return;
        setError(err instanceof Error ? err.message : "Failed to load data");
        setTopBanksBySentiment([]);
      })
      .finally(() => {
        if (active) setTopBanksLoading(false);
      });

    return () => {
      active = false;
    };
  }, []);

  useEffect(() => {
    let active = true;

    getSocialAssociationsDistribution(selectedAssociationFilters)
      .then((res) => {
        if (!active) return;
        setAssociationsDistribution(res.data ?? []);
      })
      .catch((err) => {
        if (!active) return;
        setError(err instanceof Error ? err.message : "Failed to load data");
        setAssociationsDistribution([]);
      })
      .finally(() => {
        if (active) setAssociationsDistributionLoading(false);
      });

    return () => {
      active = false;
    };
  }, [selectedAssociationFilters]);

  useEffect(() => {
    let active = true;

    getSocialAssociationsOverTime(
      associationsFrequency,
      selectedAssociationTrendFilters
    )
      .then((res) => {
        if (!active) return;
        const rows = res.data ?? [];
        setAssociationsTrend(rows);

        if (
          !defaultTrendAssociationsSyncedRef.current &&
          selectedTrendAssociations.length === 0
        ) {
          const defaultAssociations = extractAssociationTrendSeries(
            normalizeAssociationTrendRows(rows)
          ).slice(0, MAX_SELECTED_ASSOCIATIONS);

          if (defaultAssociations.length > 0) {
            defaultTrendAssociationsSyncedRef.current = true;
            setSelectedTrendAssociations(defaultAssociations);
            setAssociationsTrendLoading(true);
          }
        }
      })
      .catch((err) => {
        if (!active) return;
        setError(err instanceof Error ? err.message : "Failed to load data");
        setAssociationsTrend([]);
      })
      .finally(() => {
        if (active) setAssociationsTrendLoading(false);
      });

    return () => {
      active = false;
    };
  }, [
    associationsFrequency,
    selectedAssociationTrendFilters,
    selectedTrendAssociations.length,
  ]);

  useEffect(() => {
    let active = true;

    getSocialEngagementTrend(socialTrendFrequency, selectedSocialFilters)
      .then((res) => {
        if (!active) return;
        setEngagementTrend(res.trend ?? []);
      })
      .catch((err) => {
        if (!active) return;
        setError(err instanceof Error ? err.message : "Failed to load data");
        setEngagementTrend([]);
      })
      .finally(() => {
        if (active) setEngagementLoading(false);
      });

    return () => {
      active = false;
    };
  }, [socialTrendFrequency, selectedSocialFilters]);

  useEffect(() => {
    let active = true;

    getSocialVolumeTrend(socialTrendFrequency, selectedSocialFilters)
      .then((res) => {
        if (!active) return;
        setVolumeTrend(res.trend ?? []);
      })
      .catch((err) => {
        if (!active) return;
        setError(err instanceof Error ? err.message : "Failed to load data");
        setVolumeTrend([]);
      })
      .finally(() => {
        if (active) setTrendLoading(false);
      });

    return () => {
      active = false;
    };
  }, [socialTrendFrequency, selectedSocialFilters]);

  const handleSocialTrendFrequencyChange = (
    frequency: SocialVolumeTrendFrequency
  ) => {
    if (frequency === socialTrendFrequency) return;

    setTrendLoading(true);
    setEngagementLoading(true);
    setSocialTrendFrequency(frequency);
  };

  const handleAssociationsFrequencyChange = (
    frequency: SocialVolumeTrendFrequency
  ) => {
    if (frequency === associationsFrequency) return;

    setAssociationsTrendLoading(true);
    setAssociationsFrequency(frequency);
  };

  const handleAssociationTrendToggle = (association: string) => {
    setSelectedTrendAssociations((current) => {
      if (current.includes(association)) {
        if (current.length === 1) return current;
        setAssociationsTrendLoading(true);
        return current.filter((item) => item !== association);
      }

      if (current.length >= MAX_SELECTED_ASSOCIATIONS) return current;

      setAssociationsTrendLoading(true);
      return [...current, association];
    });
  };

  const markOverviewFilterLoading = () => {
    setLoading(true);
    setTopGrowingLoading(true);
    setTrendLoading(true);
    setEngagementLoading(true);
  };

  const markAssociationFilterLoading = () => {
    setAssociationsDistributionLoading(true);
    setAssociationsTrendLoading(true);
  };

  const handleBankChange = (value: string) => {
    if (value === selectedBank) return;

    markOverviewFilterLoading();
    markAssociationFilterLoading();
    setSelectedBank(value);
  };

  const handlePlatformChange = (value: string) => {
    if (value === selectedPlatform) return;

    markOverviewFilterLoading();
    markAssociationFilterLoading();
    setSelectedPlatform(value);
  };

  const handleAssociationStartDateChange = (value: string) => {
    const nextDate = clampAssociationDate(value, ASSOCIATION_MIN_DATE);
    if (nextDate === associationStartDate) return;

    markAssociationFilterLoading();
    setAssociationStartDate(nextDate);
    if (nextDate > associationEndDate) setAssociationEndDate(nextDate);
  };

  const handleAssociationEndDateChange = (value: string) => {
    const nextDate = clampAssociationDate(value, ASSOCIATION_MAX_DATE);
    if (nextDate === associationEndDate) return;

    markAssociationFilterLoading();
    setAssociationEndDate(nextDate);
    if (nextDate < associationStartDate) setAssociationStartDate(nextDate);
  };

  const shareOfVoice = useMemo(() => {
    const rows = distribution
      .filter((item) => Number.isFinite(item.total_posts) && item.total_posts > 0)
      .sort((a, b) => b.total_posts - a.total_posts);
    const total = rows.reduce((sum, item) => sum + item.total_posts, 0);

    return rows.map((item) => ({
      name: item.bank,
      value: item.total_posts,
      share: total > 0 ? (item.total_posts / total) * 100 : 0,
    }));
  }, [distribution]);

  const mostEngagingBank = useMemo(() => {
    const rows = distribution
      .filter(
        (item) =>
          Number.isFinite(item.total_engagement) && item.total_posts > 0
      )
      .map((item) => ({
        bank: item.bank,
        rate: (item.total_engagement ?? 0) / item.total_posts,
      }))
      .sort((a, b) => b.rate - a.rate);

    return rows[0] ?? null;
  }, [distribution]);

  const fastestGrowingBank = useMemo(() => {
    const rows = [...topGrowing].sort((a, b) => b.growth - a.growth);
    return rows[0] ?? null;
  }, [topGrowing]);

  const volumeTrendData = useMemo(
    () =>
      volumeTrend.map((item) => ({
        period: item.period,
        volume: item.volume,
      })),
    [volumeTrend]
  );

  const engagementTrendData = useMemo(
    () =>
      engagementTrend.map((item) => ({
        period: item.period,
        engagement: item.engagement,
      })),
    [engagementTrend]
  );

  const topicMentionsData = useMemo(
    () =>
      topTopics.map((item) => ({
        name: item.name,
        value: item.mentions,
      })),
    [topTopics]
  );

  const avgTopicSentimentData = useMemo(
    () => normalizeSentimentRows(avgSentimentByTopic),
    [avgSentimentByTopic]
  );

  const avgBankSentimentData = useMemo(
    () => normalizeSentimentRows(avgSentimentByBank),
    [avgSentimentByBank]
  );

  const topBanksSentimentData = useMemo(
    () => normalizeSentimentRows(topBanksBySentiment),
    [topBanksBySentiment]
  );

  const associationsDistributionData = useMemo(
    () => normalizeAssociationRows(associationsDistribution),
    [associationsDistribution]
  );

  const associationsTrendData = useMemo(
    () => normalizeAssociationTrendRows(associationsTrend),
    [associationsTrend]
  );

  const bankOptions = useMemo(
    () =>
      getSocialFilterOptions(
        filters,
        ["banks", "bank", "brands", "brand"],
        "All Banks"
      ),
    [filters]
  );
  const platformOptions = useMemo(
    () =>
      getSocialFilterOptions(
        filters,
        ["platforms", "platform"],
        "All Platforms"
      ),
    [filters]
  );

  return (
    <div className="min-h-screen">
      <DashboardTopbar title="BrandIQ" />

      <main className="p-8">
        <section className="mb-6 overflow-hidden rounded-2xl bg-gradient-to-r from-[#3f3fb3] via-[#6d7ddc] to-[#b21883] p-6 text-white shadow-lg">
          <div className="grid gap-6 lg:grid-cols-[1.7fr_0.65fr_0.65fr_0.65fr] lg:items-center">
            <div>
              <h1 className="text-2xl font-bold">Social Analysis</h1>
              <p className="mt-3 max-w-3xl text-sm leading-6 text-white/90">
                Explores how the brand exists and behaves across social spaces,
                mapping its presence within a competitive framework. It captures
                what people are saying, in what tone, and around which topics,
                offering a view of both presence and perception.
              </p>
            </div>

            <div className="rounded-xl bg-white/20 p-4 shadow-sm ring-1 ring-white/15 backdrop-blur">
              <div className="mb-3 flex h-9 w-9 items-center justify-center rounded-xl bg-violet-500 text-white shadow-md">
                <Heart className="h-5 w-5" />
              </div>
              <p className="text-xl font-bold leading-tight">
                {loading ? "…" : mostEngagingBank?.bank ?? "—"}
              </p>
              <p className="mt-2 text-sm font-medium text-white/75">
                Most Engaging Brand
              </p>
              <p className="mt-1 text-xs text-white/60">
                Highest engagement rate — (likes + shares + comments + views) ÷ posts
              </p>
            </div>

            <div className="rounded-xl bg-white/20 p-4 shadow-sm ring-1 ring-white/15 backdrop-blur">
              <div className="mb-3 flex h-9 w-9 items-center justify-center rounded-xl bg-fuchsia-500 text-white shadow-md">
                <MessageCircle className="h-5 w-5" />
              </div>
              <p className="text-xl font-bold leading-tight">
                {loading ? "…" : shareOfVoice[0]?.name ?? "—"}
              </p>
              <p className="mt-2 text-sm font-medium text-white/75">
                Share of Voice Leader
              </p>
              <p className="mt-1 text-xs text-white/60">
                Largest share of total posting volume across tracked banks
              </p>
            </div>

            <div className="rounded-xl bg-white/20 p-4 shadow-sm ring-1 ring-white/15 backdrop-blur">
              <div className="mb-3 flex h-9 w-9 items-center justify-center rounded-xl bg-slate-700 text-white shadow-md">
                <TrendingUp className="h-5 w-5" />
              </div>
              <p className="text-xl font-bold leading-tight">
                {topGrowingLoading ? "…" : fastestGrowingBank?.bank ?? "—"}
              </p>
              <p className="mt-2 text-sm font-medium text-white/75">
                Fastest Growing Brand
              </p>
              <p className="mt-1 text-xs text-white/60">
                Largest increase in posting share, period-over-period
              </p>
            </div>
          </div>
        </section>

        {error && (
          <div className="mb-6 rounded-lg border border-red-500/30 bg-red-500/10 px-4 py-3 text-sm font-medium text-red-500">
            {error}
          </div>
        )}

        <div className="mb-6 flex flex-col gap-4 xl:flex-row xl:items-end xl:justify-between">
          <div className="inline-flex rounded-full border border-[var(--card-bd)] bg-[var(--card-bg)] p-1 shadow-sm">
            {SOCIAL_ANALYSIS_TABS.map((tab) => {
              const active = activeTab === tab.id;
              const Icon = tab.icon;

              return (
                <button
                  key={tab.id}
                  type="button"
                  onClick={() => setActiveTab(tab.id)}
                  className="flex h-10 items-center gap-2 rounded-full px-4 text-sm font-semibold transition"
                  style={{
                    background: active ? "#2563eb" : "transparent",
                    color: active ? "#ffffff" : "var(--muted-tx)",
                  }}
                >
                  <Icon className="h-4 w-4" />
                  {tab.label}
                </button>
              );
            })}
          </div>

          <div
            className={`grid gap-3 sm:grid-cols-2 ${
              activeTab === "associations"
                ? "xl:w-[720px] 2xl:grid-cols-4 2xl:w-[980px]"
                : "xl:w-[420px]"
            }`}
          >
            <FilterSelect
              label="Bank"
              value={selectedBank}
              onChange={handleBankChange}
              options={bankOptions}
            />
            <FilterSelect
              label="Platform"
              value={selectedPlatform}
              onChange={handlePlatformChange}
              options={platformOptions}
            />
            {activeTab === "associations" && (
              <>
                <div className="relative w-full">
                  <label
                    style={{ color: "var(--muted-tx)" }}
                    className="mb-1 block text-xs font-medium"
                  >
                    Start Date
                  </label>
                  <input
                    type="date"
                    value={associationStartDate}
                    min={ASSOCIATION_MIN_DATE}
                    max={ASSOCIATION_MAX_DATE}
                    onChange={(event) =>
                      handleAssociationStartDateChange(event.target.value)
                    }
                    style={{
                      background: "var(--card-bg-2)",
                      borderColor: "var(--card-bd)",
                      color: "var(--title-tx)",
                    }}
                    className="w-full rounded-xl border px-4 py-3 text-sm outline-none transition-colors hover:border-blue-500 focus:border-blue-500"
                  />
                </div>
                <div className="relative w-full">
                  <label
                    style={{ color: "var(--muted-tx)" }}
                    className="mb-1 block text-xs font-medium"
                  >
                    End Date
                  </label>
                  <input
                    type="date"
                    value={associationEndDate}
                    min={ASSOCIATION_MIN_DATE}
                    max={ASSOCIATION_MAX_DATE}
                    onChange={(event) =>
                      handleAssociationEndDateChange(event.target.value)
                    }
                    style={{
                      background: "var(--card-bg-2)",
                      borderColor: "var(--card-bd)",
                      color: "var(--title-tx)",
                    }}
                    className="w-full rounded-xl border px-4 py-3 text-sm outline-none transition-colors hover:border-blue-500 focus:border-blue-500"
                  />
                </div>
              </>
            )}
          </div>
        </div>

        {activeTab === "overview" && (
          <div className="space-y-6">
            <ShareOfVoiceCard data={shareOfVoice} loading={loading} />
            <SocialTrendCard
              metric={socialTrendMetric}
              onMetricChange={setSocialTrendMetric}
              volumeData={volumeTrendData}
              engagementData={engagementTrendData}
              frequency={socialTrendFrequency}
              onFrequencyChange={handleSocialTrendFrequencyChange}
              volumeLoading={trendLoading}
              engagementLoading={engagementLoading}
            />
          </div>
        )}

        {activeTab === "topics" && (
          <div className="grid gap-6 xl:grid-cols-2">
            <TopicMentionsCard
              data={topicMentionsData}
              loading={topTopicsLoading}
            />
            <TopicSentimentBars
              data={avgTopicSentimentData}
              loading={avgTopicLoading}
            />
            <BankSentimentBars
              data={avgBankSentimentData}
              loading={avgBankLoading}
              title="Average Sentiment by Bank"
              description="Average sentiment score across tracked banks."
              emptyMessage="No average bank sentiment data available"
              filenamePrefix="average_sentiment_by_bank"
            />
            <BankSentimentBars
              data={topBanksSentimentData}
              loading={topBanksLoading}
              title="Top Banks by Sentiment"
              description="Highest-ranking banks by social sentiment score."
              emptyMessage="No top bank sentiment data available"
              filenamePrefix="top_banks_by_sentiment"
            />
          </div>
        )}

        {activeTab === "associations" && (
          <div className="grid gap-6 xl:grid-cols-2">
              <AssociationsCard
                data={associationsDistributionData}
                loading={associationsDistributionLoading}
              />
              <AssociationsTrendCard
                data={associationsTrendData}
                frequency={associationsFrequency}
                loading={associationsTrendLoading}
                onFrequencyChange={handleAssociationsFrequencyChange}
                associationOptions={associationOptions}
                selectedAssociations={selectedTrendAssociations}
                onAssociationToggle={handleAssociationTrendToggle}
                maxSelectedAssociations={MAX_SELECTED_ASSOCIATIONS}
              />
          </div>
        )}
      </main>
    </div>
  );
}
