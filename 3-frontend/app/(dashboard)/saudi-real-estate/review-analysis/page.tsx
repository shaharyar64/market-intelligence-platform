"use client";

import { useEffect, useMemo, useState } from "react";
import DashboardTopbar from "@/components/layout/DashboardTopbar";
import ExportExcelButton from "@/components/ui/ExportExcelButton";
import {
  Bar,
  BarChart,
  CartesianGrid,
  Cell,
  LabelList,
  ResponsiveContainer,
  Tooltip,
  XAxis,
  YAxis,
} from "recharts";
import FilterSelect from "@/components/filters/FilterSelect";
import {
  getAvgRatingByTopic,
  getAvgSentimentByBank,
  getDigitalBrandHealthBanks,
  getRatedBanks,
  getReviewsPerBank,
  getReviewTopicsDistribution,
  getTopRatedBanks,
  type ReviewAnalysisRow,
} from "@/lib/saudiRealEstate";
import { getBankColor, getContrastText } from "@/lib/bankColors";
import { MessageSquareText, Star, TrendingUp } from "lucide-react";

type ReviewAnalysisTab = "rating" | "review";

const REVIEW_ANALYSIS_TABS: Array<{
  id: ReviewAnalysisTab;
  label: string;
  icon: typeof Star;
}> = [
  { id: "rating", label: "Rating", icon: Star },
  { id: "review", label: "Review", icon: MessageSquareText },
];

type ChartData = {
  name: string;
  value: number;
};

type TopicRatingData = {
  name: string;
  value: number | null;
  count: number | null;
};

type FilterOption = {
  label: string;
  value: string;
};

type ReviewDashboardData = {
  reviewsPerBank: ReviewAnalysisRow[];
  topRatedBanks: ReviewAnalysisRow[];
  avgSentimentByBank: ReviewAnalysisRow[];
};

const EMPTY_DATA: ReviewDashboardData = {
  reviewsPerBank: [],
  topRatedBanks: [],
  avgSentimentByBank: [],
};

type TopicsData = {
  distribution: ReviewAnalysisRow[];
  rating: ReviewAnalysisRow[];
};

const EMPTY_TOPICS_DATA: TopicsData = {
  distribution: [],
  rating: [],
};

const CHART_COLORS = [
  "#2563eb",
  "#10b981",
  "#f59e0b",
  "#ef4444",
  "#8b5cf6",
  "#06b6d4",
  "#ec4899",
  "#64748b",
];

const RATING_MIX_COLORS = {
  rating_1: "#ef4444",
  rating_2: "#f97316",
  rating_3: "#f59e0b",
  rating_4: "#3b82f6",
  rating_5: "#10b981",
};

function pickString(row: ReviewAnalysisRow, keys: string[], fallback = "Unknown") {
  for (const key of keys) {
    const value = row[key];
    if (typeof value === "string" && value.trim()) return value.trim();
    if (typeof value === "number" && Number.isFinite(value)) return String(value);
  }

  return fallback;
}

function pickNumber(row: ReviewAnalysisRow, keys: string[], fallback = 0) {
  for (const key of keys) {
    const value = row[key];
    if (typeof value === "number" && Number.isFinite(value)) return value;
    if (typeof value === "string" && value.trim() && Number.isFinite(Number(value))) {
      return Number(value);
    }
  }

  return fallback;
}

function pickNumberOrNull(row: ReviewAnalysisRow, keys: string[]): number | null {
  for (const key of keys) {
    const value = row[key];
    if (typeof value === "number" && Number.isFinite(value)) return value;
    if (typeof value === "string" && value.trim() && Number.isFinite(Number(value))) {
      return Number(value);
    }
  }

  return null;
}

function toBankName(row: ReviewAnalysisRow) {
  return pickString(row, ["developer", "bank", "bank_name", "name", "brand"]);
}

function toTopicName(row: ReviewAnalysisRow) {
  return pickString(row, ["topic", "review_topic", "category", "name"]);
}

function formatNumber(value: number) {
  return new Intl.NumberFormat("en-US").format(Math.round(value));
}

function formatScore(value: number | null) {
  return value === null ? "-" : value.toFixed(2);
}

function buildChartData(
  rows: ReviewAnalysisRow[],
  labelFor: (row: ReviewAnalysisRow) => string,
  valueKeys: string[]
): ChartData[] {
  return rows.map((row) => ({
    name: labelFor(row),
    value: Number(pickNumber(row, valueKeys).toFixed(2)),
  }));
}

function alignChartDataToOrder(order: string[], items: ChartData[]): ChartData[] {
  const byName = new Map(items.map((item) => [item.name, item.value]));
  return order.map((name) => ({ name, value: byName.get(name) ?? 0 }));
}

function alignTopicRatingToOrder(
  order: string[],
  rows: ReviewAnalysisRow[]
): TopicRatingData[] {
  const byName = new Map(
    rows.map((row) => [
      toTopicName(row),
      {
        value: pickNumberOrNull(row, ["avg_rating", "average_rating", "rating", "score", "value"]),
        count: pickNumberOrNull(row, ["review_count", "reviews", "total_reviews", "count"]),
      },
    ])
  );

  return order.map((name) => {
    const found = byName.get(name);
    return { name, value: found?.value ?? null, count: found?.count ?? null };
  });
}

function RatingsAcrossBrandsChart({
  data,
  loading,
}: {
  data: ChartData[];
  loading: boolean;
}) {
  const average =
    data.length > 0
      ? data.reduce((sum, item) => sum + item.value, 0) / data.length
      : null;
  const chartWidth = Math.max(data.length * 56, 640);
  const longestName = data.reduce((max, item) => Math.max(max, item.name.length), 0);
  const labelHeight = Math.min(220, Math.max(60, Math.round(longestName * 6.4) + 16));

  if (loading) {
    return (
      <section className="rounded-2xl border border-[var(--card-bd)] bg-[var(--card-bg-2)] p-6 shadow-lg">
        <div className="h-5 w-52 animate-pulse rounded bg-[var(--card-bd)]" />
        <div className="mt-6 flex h-[320px] items-end gap-3 rounded-2xl border border-[var(--card-bd)] bg-[var(--card-bg)] p-5">
          {Array.from({ length: 12 }).map((_, index) => (
            <div key={index} className="flex flex-1 flex-col items-center gap-3">
              <div
                className="w-full animate-pulse rounded-t-xl bg-[var(--card-bd)]"
                style={{ height: `${35 + (index % 5) * 10}%` }}
              />
              <div className="h-3 w-full animate-pulse rounded bg-[var(--card-bd)]" />
            </div>
          ))}
        </div>
      </section>
    );
  }

  if (!data.length) {
    return (
      <section className="rounded-2xl border border-[var(--card-bd)] bg-[var(--card-bg-2)] p-6 shadow-lg">
        <h2 className="text-lg font-semibold text-[var(--title-tx)]">
          Ratings Across Brands
        </h2>
        <div className="mt-6 flex min-h-[260px] items-center justify-center rounded-2xl border border-[var(--card-bd)] bg-[var(--card-bg)] text-sm text-[var(--muted-tx)]">
          No brand rating data available
        </div>
      </section>
    );
  }

  return (
    <section className="rounded-2xl border border-[var(--card-bd)] bg-[var(--card-bg-2)] p-6 shadow-lg">
      <div className="flex flex-col gap-4 sm:flex-row sm:items-start sm:justify-between">
        <div>
          <h2 className="text-lg font-semibold text-[var(--title-tx)]">
            Ratings Across Brands
          </h2>
          <p className="mt-2 text-sm text-[var(--muted-tx)]">
            Brands ranked by average customer rating.
          </p>
        </div>

        <div className="flex flex-wrap justify-end gap-3">
          <ExportExcelButton
            rows={data.map((item, index) => ({ rank: index + 1, ...item }))}
            filename="ratings_across_brands"
            sheetName="Ratings Across Brands"
            disabled={loading}
          />
        </div>
      </div>

      <div className="mt-6 overflow-x-auto rounded-2xl border border-[var(--card-bd)] bg-[var(--card-bg)] p-5 shadow-sm">
        <div style={{ width: chartWidth, minWidth: "100%" }}>
          <div className="grid grid-cols-[34px_1fr] gap-4">
            <div className="relative h-[320px]">
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

            <div>
              <div className="relative h-[320px]">
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
                    const height = Math.min(Math.max((item.value / 5) * 100, 4), 100);

                    return (
                      <div
                        key={`${item.name}-${index}`}
                        className="relative flex h-full min-w-0 flex-col justify-end"
                      >
                        <div
                          className="absolute left-1/2 flex -translate-x-1/2 items-center gap-1 whitespace-nowrap text-xs font-bold text-[var(--title-tx)]"
                          style={{ bottom: `calc(${height}% + 6px)` }}
                        >
                          <Star className="h-3 w-3 fill-amber-400 text-amber-400" />
                          {item.value.toFixed(2)}
                        </div>
                        <div className="relative mx-auto h-full w-full max-w-10 overflow-hidden rounded-t-xl">
                          <div
                            className="absolute inset-x-0 bottom-0 rounded-t-xl transition-all"
                            style={{
                              height: `${height}%`,
                              background: color,
                            }}
                          />
                        </div>
                      </div>
                    );
                  })}
                </div>
              </div>

              <div
                className="mt-3 grid gap-3"
                style={{ gridTemplateColumns: `repeat(${data.length}, minmax(0, 1fr))` }}
              >
                {data.map((item, index) => (
                  <div
                    key={`${item.name}-rating-label-${index}`}
                    className="flex min-w-0 items-start justify-center overflow-hidden"
                    style={{ height: labelHeight }}
                  >
                    <span
                      className="whitespace-nowrap text-[11px] font-semibold text-[var(--muted-tx)]"
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
      </div>
    </section>
  );
}

function ReviewsPerBankCard({
  data,
  loading,
}: {
  data: ChartData[];
  loading: boolean;
}) {
  const maxValue = Math.max(...data.map((item) => item.value), 0);
  const total = data.reduce((sum, item) => sum + item.value, 0);

  return (
    <section className="flex h-full flex-col rounded-2xl border border-[var(--card-bd)] bg-[var(--card-bg-2)] p-5 shadow-lg">
      <div className="flex flex-col gap-3 sm:flex-row sm:items-start sm:justify-between">
        <div>
          <h2 className="text-lg font-semibold text-[var(--title-tx)]">
            Reviews Per Developer
          </h2>
          <p className="mt-2 text-sm text-[var(--muted-tx)]">
            Ranked customer rating volume across tracked developers.
          </p>
        </div>

        <div className="flex items-start gap-3">
          <ExportExcelButton
            rows={data.map((item) => ({ ...item }))}
            filename="reviews_per_developer"
            sheetName="Reviews Per Developer"
            disabled={loading}
          />
          <div className="rounded-xl border border-[var(--card-bd)] bg-[var(--card-bg)] px-3 py-2 text-right">
            <p className="text-xs font-semibold uppercase text-[var(--muted-tx)]">
              Total Ratings
            </p>
            <p className="mt-0.5 text-xl font-bold text-[var(--title-tx)]">
              {loading ? "-" : formatNumber(total)}
            </p>
          </div>
        </div>
      </div>

      <div className="mt-5 space-y-2 xl:max-h-[760px] xl:overflow-y-auto xl:pr-1">
        {loading
          ? Array.from({ length: 8 }).map((_, index) => (
              <div
                key={index}
                className="h-11 animate-pulse rounded-lg bg-[var(--card-bg)]"
              />
            ))
          : data.length === 0
            ? (
              <div className="flex min-h-[240px] items-center justify-center rounded-xl border border-[var(--card-bd)] bg-[var(--card-bg)] text-sm text-[var(--muted-tx)]">
                No review data available
              </div>
            )
            : data.map((item, index) => {
              const percent = maxValue > 0 ? (item.value / maxValue) * 100 : 0;
              const color = getBankColor(item.name, index);

              return (
                <div
                  key={`${item.name}-${index}`}
                  className="rounded-lg border border-[var(--card-bd)] bg-[var(--card-bg)] px-3 py-2.5"
                >
                  <div className="grid grid-cols-[30px_minmax(0,1fr)_68px] items-center gap-3 lg:grid-cols-[30px_minmax(120px,220px)_1fr_68px]">
                    <div
                      className="flex h-7 w-7 items-center justify-center rounded-lg text-[11px] font-bold"
                      style={{ background: color, color: getContrastText(color) }}
                    >
                      {index + 1}
                    </div>

                    <p className="truncate text-sm font-semibold leading-none text-[var(--title-tx)]">
                      {item.name}
                    </p>

                    <div className="col-span-3 h-2 overflow-hidden rounded-full bg-[var(--card-bg-2)] lg:col-span-1">
                      <div
                        className="h-full rounded-full shadow-sm transition-all"
                        style={{
                          width: `${Math.max(percent, 2)}%`,
                          background: color,
                        }}
                      />
                    </div>

                    <p className="text-right text-sm font-bold leading-none text-[var(--title-tx)]">
                      {formatNumber(item.value)}
                    </p>
                  </div>
                </div>
              );
            })}
      </div>
    </section>
  );
}

function AverageSentimentByBankCard({
  items,
  loading,
}: {
  items: ReviewAnalysisRow[];
  loading: boolean;
}) {
  const sortedItems = useMemo(
    () =>
      [...items].sort(
        (a, b) =>
          pickNumber(b, ["avg_sentiment"]) -
          pickNumber(a, ["avg_sentiment"])
      ),
    [items]
  );

  return (
    <section className="rounded-2xl border border-[var(--card-bd)] bg-[var(--card-bg-2)] p-6 shadow-lg">
      <div className="flex flex-col gap-4 sm:flex-row sm:items-start sm:justify-between">
        <div>
          <h2 className="text-lg font-semibold text-[var(--title-tx)]">
            Sentiment Distribution by User
          </h2>
          <p className="mt-2 text-sm text-[var(--muted-tx)]">
            Average sentiment with rating distribution by star level.
          </p>
        </div>

        <div className="flex flex-wrap items-start gap-2">
          <ExportExcelButton
            rows={sortedItems}
            filename="sentiment_distribution_by_user"
            sheetName="Sentiment Distribution"
            disabled={loading}
          />
          {[
            ["rating_5", "5"],
            ["rating_4", "4"],
            ["rating_3", "3"],
            ["rating_2", "2"],
            ["rating_1", "1"],
          ].map(([key, label]) => (
            <div
              key={key}
              className="flex items-center gap-1.5 rounded-full border border-[var(--card-bd)] bg-[var(--card-bg)] px-2.5 py-1 text-xs font-semibold text-[var(--muted-tx)]"
            >
              <span
                className="h-2.5 w-2.5 rounded-full"
                style={{
                  background:
                    RATING_MIX_COLORS[key as keyof typeof RATING_MIX_COLORS],
                }}
              />
              {label}
              <Star className="h-3 w-3" />
            </div>
          ))}
        </div>
      </div>

      <div className="mt-6 space-y-3">
        {loading
          ? Array.from({ length: 8 }).map((_, index) => (
              <div
                key={index}
                className="h-[66px] animate-pulse rounded-xl bg-[var(--card-bg)]"
              />
            ))
          : sortedItems.length === 0
            ? (
              <div className="flex min-h-[280px] items-center justify-center rounded-xl border border-[var(--card-bd)] bg-[var(--card-bg)] text-sm text-[var(--muted-tx)]">
                No sentiment data available
              </div>
            )
            : sortedItems.map((item, index) => {
              const bankName = toBankName(item);
              const avgSentiment = pickNumber(item, ["avg_sentiment"]);
              const ratingCounts = {
                rating_1: pickNumber(item, ["rating_1"]),
                rating_2: pickNumber(item, ["rating_2"]),
                rating_3: pickNumber(item, ["rating_3"]),
                rating_4: pickNumber(item, ["rating_4"]),
                rating_5: pickNumber(item, ["rating_5"]),
              };
              const total = Object.values(ratingCounts).reduce(
                (sum, value) => sum + value,
                0
              );

              return (
                <div
                  key={`${bankName}-${index}`}
                  className="rounded-xl border border-[var(--card-bd)] bg-[var(--card-bg)] px-4 py-3 shadow-sm"
                >
                  <div className="grid gap-3 lg:grid-cols-[150px_76px_1fr_56px] lg:items-center">
                    <p className="truncate text-sm font-semibold text-[var(--title-tx)]">
                      {bankName}
                    </p>

                    <div className="flex items-center gap-1 rounded-full border border-emerald-400/20 bg-emerald-400/10 px-2.5 py-1 text-sm font-bold text-[var(--title-tx)]">
                      {avgSentiment.toFixed(2)}
                    </div>

                    <div className="h-3 overflow-hidden rounded-full bg-[var(--card-bg-2)]">
                      {[
                        "rating_1",
                        "rating_2",
                        "rating_3",
                        "rating_4",
                        "rating_5",
                      ].map((key) => {
                        const count =
                          ratingCounts[key as keyof typeof ratingCounts];
                        const width = total > 0 ? (count / total) * 100 : 0;

                        return (
                          <span
                            key={key}
                            className="inline-block h-full align-top"
                            title={`${key.replace("rating_", "")} star: ${count}`}
                            style={{
                              width: `${width}%`,
                              background:
                                RATING_MIX_COLORS[
                                  key as keyof typeof RATING_MIX_COLORS
                                ],
                            }}
                          />
                        );
                      })}
                    </div>

                    <p className="text-right text-xs font-semibold text-[var(--muted-tx)]">
                      {formatNumber(total)}
                    </p>
                  </div>
                </div>
              );
            })}
      </div>
    </section>
  );
}

function TopicAxisTick({
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

function TopicDistributionTooltip({
  active,
  payload,
}: {
  active?: boolean;
  payload?: Array<{ payload: ChartData }>;
}) {
  if (!active || !payload?.length) return null;

  const item = payload[0].payload;

  return (
    <div className="rounded-xl border border-[var(--card-bd)] bg-[var(--card-bg)] px-3 py-2 shadow-xl">
      <p className="text-sm font-bold text-[var(--title-tx)]">{item.name}</p>
      <p className="mt-1 text-xs text-[var(--muted-tx)]">{formatNumber(item.value)} reviews</p>
    </div>
  );
}

function ReviewTopicsDistributionCard({
  data,
  loading,
}: {
  data: ChartData[];
  loading: boolean;
}) {
  const total = data.reduce((sum, item) => sum + item.value, 0);
  const chartWidth = Math.max(data.length * 56, 640);
  const longestName = data.reduce((max, item) => Math.max(max, item.name.length), 0);
  const axisHeight = Math.min(260, Math.max(70, Math.round(longestName * 6.4) + 20));
  const chartHeight = 300 + axisHeight;

  return (
    <section className="flex h-full flex-col rounded-2xl border border-[var(--card-bd)] bg-[var(--card-bg-2)] p-6 shadow-lg">
      <div className="flex shrink-0 items-start justify-between gap-4">
        <div>
          <h2 className="text-lg font-semibold text-[var(--title-tx)]">
            Review Topics Distribution
          </h2>
          <p className="mt-2 text-sm text-[var(--muted-tx)]">
            Share of ratings grouped by review theme.
          </p>
        </div>

        <div className="flex items-start gap-2">
          <ExportExcelButton
            rows={data.map((item) => ({ ...item }))}
            filename="review_topics_distribution"
            sheetName="Topics Distribution"
            disabled={loading}
          />
          <div className="rounded-full border border-[var(--card-bd)] bg-[var(--card-bg)] px-3 py-1 text-xs font-semibold text-[var(--muted-tx)]">
            {loading ? "-" : formatNumber(total)} total
          </div>
        </div>
      </div>

      {loading ? (
        <div className="mt-6 min-h-[480px] flex-1 animate-pulse rounded-2xl bg-[var(--card-bg)]" />
      ) : data.length === 0 ? (
        <div className="mt-6 flex min-h-[480px] flex-1 items-center justify-center rounded-2xl border border-[var(--card-bd)] bg-[var(--card-bg)] text-sm text-[var(--muted-tx)]">
          No topic distribution data available
        </div>
      ) : (
        <div className="mt-6 flex-1 overflow-x-auto rounded-2xl border border-[var(--card-bd)] bg-[var(--card-bg)] p-5 shadow-sm" style={{ minHeight: chartHeight }}>
          <div style={{ width: chartWidth, minWidth: "100%", height: "100%" }}>
            <ResponsiveContainer width="100%" height="100%">
              <BarChart data={data} margin={{ top: 28, right: 24, left: 0, bottom: 8 }}>
                <CartesianGrid strokeDasharray="3 3" strokeOpacity={0.08} vertical={false} />
                <XAxis
                  dataKey="name"
                  interval={0}
                  height={axisHeight}
                  tick={<TopicAxisTick />}
                  tickLine={false}
                  axisLine={{ stroke: "var(--card-bd)" }}
                />
                <YAxis
                  tick={{ fill: "var(--muted-tx)", fontSize: 12, fontWeight: 600 }}
                  tickFormatter={(value) => formatNumber(Number(value))}
                  tickLine={false}
                  axisLine={false}
                />
                <Tooltip
                  content={<TopicDistributionTooltip />}
                  cursor={{ fill: "rgba(84,170,236,0.08)" }}
                />
                <Bar dataKey="value" radius={[8, 8, 0, 0]} maxBarSize={40}>
                  {data.map((_, index) => (
                    <Cell key={index} fill={CHART_COLORS[index % CHART_COLORS.length]} />
                  ))}
                  <LabelList
                    dataKey="value"
                    position="top"
                    formatter={(value) =>
                      typeof value === "number" ? formatNumber(value) : `${value ?? ""}`
                    }
                    style={{
                      fill: "var(--muted-tx)",
                      fontSize: 11,
                      fontWeight: 700,
                    }}
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

function TopicRatingBars({
  data,
  loading,
}: {
  data: TopicRatingData[];
  loading: boolean;
}) {
  const ticks = [5, 4, 3, 2, 1, 0];
  const chartWidth = Math.max(data.length * 56, 640);
  const longestName = data.reduce((max, item) => Math.max(max, item.name.length), 0);
  const labelHeight = Math.min(220, Math.max(60, Math.round(longestName * 6.4) + 16));

  return (
    <section className="rounded-2xl border border-[var(--card-bd)] bg-[var(--card-bg-2)] p-6 shadow-lg">
      <div className="flex items-start justify-between gap-4">
        <div>
          <h2 className="text-lg font-semibold text-[var(--title-tx)]">
            Average Rating By Topic
          </h2>
          <p className="mt-2 text-sm text-[var(--muted-tx)]">
            Ratings segmented by review themes.
          </p>
        </div>

        <div className="flex items-start gap-2">
          <ExportExcelButton
            rows={data.map((item) => ({ ...item }))}
            filename="average_rating_by_topic"
            sheetName="Rating By Topic"
            disabled={loading}
          />
          <div className="rounded-full border border-amber-400/20 bg-amber-400/10 px-3 py-1 text-xs font-semibold text-amber-500">
            5.0 max
          </div>
        </div>
      </div>

      {loading ? (
        <div className="mt-6 flex h-[320px] items-end gap-4 rounded-2xl border border-[var(--card-bd)] bg-[var(--card-bg)] p-5">
          {Array.from({ length: 7 }).map((_, index) => (
            <div key={index} className="flex flex-1 flex-col items-center gap-3">
              <div
                className="w-full animate-pulse rounded-t-2xl bg-[var(--card-bd)]"
                style={{ height: `${35 + index * 7}%` }}
              />
              <div className="h-3 w-full animate-pulse rounded bg-[var(--card-bd)]" />
            </div>
          ))}
        </div>
      ) : data.length === 0 ? (
        <div className="mt-6 flex h-[320px] items-center justify-center rounded-xl border border-[var(--card-bd)] bg-[var(--card-bg)] text-sm text-[var(--muted-tx)]">
          No topic rating data available
        </div>
      ) : (
        <div className="mt-6 overflow-x-auto rounded-2xl border border-[var(--card-bd)] bg-[var(--card-bg)] p-5 shadow-sm">
          <div style={{ width: chartWidth, minWidth: "100%" }} className="grid grid-cols-[32px_1fr] gap-4">
            <div className="relative h-[300px]">
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

            <div>
              <div className="relative h-[300px]">
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
                    const color = CHART_COLORS[index % CHART_COLORS.length];
                    const hasData = item.value !== null;
                    const height = hasData
                      ? Math.min(Math.max(((item.value as number) / 5) * 100, 3), 100)
                      : 0;
                    const tooltip = hasData
                      ? `${item.name}: ${(item.value as number).toFixed(2)} • ${item.count ?? 0} reviews`
                      : `${item.name}: No data`;

                    return (
                      <div
                        key={`${item.name}-${index}`}
                        className="relative flex h-full min-w-0 flex-col justify-end"
                        title={tooltip}
                      >
                        <span
                          className="absolute left-1/2 -translate-x-1/2 whitespace-nowrap text-xs font-bold text-[var(--title-tx)]"
                          style={{ bottom: `calc(${height}% + 6px)` }}
                        >
                          {hasData ? (item.value as number).toFixed(2) : "No data"}
                        </span>
                        <div className="relative mx-auto h-full w-full max-w-10 overflow-hidden rounded-t-2xl">
                          {hasData ? (
                            <div
                              className="absolute inset-x-0 bottom-0 rounded-t-2xl transition-all"
                              style={{
                                height: `${height}%`,
                                background: color,
                              }}
                            />
                          ) : (
                            <div className="absolute inset-x-0 bottom-0 flex h-6 items-end justify-center pb-1 text-[9px] font-semibold text-[var(--muted-tx)]">
                              —
                            </div>
                          )}
                        </div>
                      </div>
                    );
                  })}
                </div>
              </div>

              <div
                className="mt-3 grid gap-5"
                style={{ gridTemplateColumns: `repeat(${data.length}, minmax(0, 1fr))` }}
              >
                {data.map((item, index) => (
                  <div
                    key={`${item.name}-label-${index}`}
                    className="flex min-w-0 items-start justify-center overflow-hidden"
                    style={{ height: labelHeight }}
                  >
                    <span
                      className="whitespace-nowrap text-[11px] font-semibold text-[var(--muted-tx)]"
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

function RatedBanksPanel({
  rating,
  onRatingChange,
  items,
  loading,
}: {
  rating: number;
  onRatingChange: (rating: number) => void;
  items: ReviewAnalysisRow[];
  loading: boolean;
}) {
  const ratingCounts = items.map((item) =>
    pickNumber(item, ["total_ratings", "ratings", "total_reviews", "count", "total"])
  );
  const maxRatings = Math.max(...ratingCounts, 0);
  const totalRatings = ratingCounts.reduce((sum, value) => sum + value, 0);

  return (
    <section className="rounded-2xl border border-[var(--card-bd)] bg-[var(--card-bg-2)] p-6 shadow-lg">
      <div className="flex flex-col gap-4 lg:flex-row lg:items-start lg:justify-between">
        <div>
          <h2 className="text-lg font-semibold text-[var(--title-tx)]">
            Rated Developers
          </h2>
          <p className="mt-2 text-sm text-[var(--muted-tx)]">
            Total ratings by developer for the selected star level.
          </p>
        </div>

        <div className="flex flex-col gap-3 sm:flex-row sm:items-center">
          <ExportExcelButton
            rows={items.map((item, index) => ({ rank: index + 1, rating, ...item }))}
            filename={`rated_developers_${rating}_star`}
            sheetName="Rated Developers"
            disabled={loading}
          />
          <div className="rounded-xl border border-[var(--card-bd)] bg-[var(--card-bg)] px-4 py-2 text-right shadow-sm">
            <p className="text-xs font-semibold uppercase text-[var(--muted-tx)]">
              {rating}-Star Ratings
            </p>
            <p className="mt-0.5 text-xl font-bold text-[var(--title-tx)]">
              {loading ? "-" : formatNumber(totalRatings)}
            </p>
          </div>

          <div className="inline-flex rounded-full border border-[var(--card-bd)] bg-[var(--card-bg)] p-1 shadow-sm">
            {[5, 4, 3, 2, 1].map((item) => {
              const active = item === rating;

              return (
                <button
                  key={item}
                  type="button"
                  onClick={() => onRatingChange(item)}
                  className="flex h-9 min-w-12 items-center justify-center gap-1 rounded-full px-3 text-xs font-semibold transition"
                  style={{
                    background: active ? "#f59e0b" : "transparent",
                    color: active ? "#111827" : "var(--muted-tx)",
                  }}
                >
                  {item}
                  <Star className="h-3.5 w-3.5" />
                </button>
              );
            })}
          </div>
        </div>
      </div>

      <div className="mt-5 grid gap-3 md:grid-cols-2 xl:grid-cols-4">
        {loading
          ? Array.from({ length: 8 }).map((_, item) => (
              <div
                key={item}
                className="h-[118px] animate-pulse rounded-2xl bg-[var(--card-bg)]"
              />
            ))
          : items.length === 0
            ? (
              <div className="col-span-full flex min-h-[150px] items-center justify-center rounded-xl border border-[var(--card-bd)] bg-[var(--card-bg)] text-sm text-[var(--muted-tx)]">
                No developers found for this rating
              </div>
            )
            : items.map((item, index) => {
              const bankName = toBankName(item);
              const total = pickNumber(item, [
                "total_ratings",
                "ratings",
                "total_reviews",
                "count",
                "total",
              ]);
              const percent = maxRatings > 0 ? (total / maxRatings) * 100 : 0;
              const colorBg = getBankColor(bankName, index);
              const colorText = getContrastText(colorBg);

              return (
                <div
                  key={`${rating}-${bankName}-${index}`}
                  className="group relative min-h-[118px] overflow-hidden rounded-2xl border border-[var(--card-bd)] bg-[var(--card-bg)] p-4 shadow-sm transition hover:-translate-y-0.5 hover:shadow-md"
                >
                  <div
                    className="pointer-events-none absolute -right-12 -top-14 h-40 w-40 rounded-full opacity-30 blur-3xl transition group-hover:opacity-40"
                    style={{ background: colorBg }}
                  />
                  <div
                    className="pointer-events-none absolute inset-0 opacity-[0.09]"
                    style={{
                      background: `linear-gradient(135deg, transparent 0%, ${colorBg} 100%)`,
                    }}
                  />
                  <div
                    className="pointer-events-none absolute inset-y-0 right-0 w-1/2 opacity-[0.06]"
                    style={{
                      background: `linear-gradient(90deg, transparent, ${colorBg})`,
                    }}
                  />

                  <div className="relative flex items-start justify-between gap-3">
                    <div className="min-w-0">
                      <p className="truncate text-sm font-bold text-[var(--title-tx)]">
                        {bankName}
                      </p>
                      <div className="mt-2 flex items-center gap-1 text-xs font-semibold text-amber-500">
                        {rating}
                        <Star className="h-3.5 w-3.5 fill-amber-400 text-amber-400" />
                      </div>
                    </div>

                    <div
                      className="flex h-9 w-9 shrink-0 items-center justify-center rounded-xl text-xs font-bold shadow-lg"
                      style={{ background: colorBg, color: colorText }}
                    >
                      {index + 1}
                    </div>
                  </div>

                  <div className="relative mt-4">
                    <div className="flex items-end justify-between gap-3">
                      <p className="text-[26px] font-bold leading-none text-[var(--title-tx)]">
                        {formatNumber(total)}
                      </p>
                      <p className="text-[11px] font-bold uppercase tracking-wide text-[var(--muted-tx)]">
                        ratings
                      </p>
                    </div>

                    <div className="mt-3 h-2 overflow-hidden rounded-full bg-[var(--card-bg-2)]">
                      <div
                        className="h-full rounded-full transition-all"
                        style={{
                          width: `${Math.max(percent, 2)}%`,
                          background: colorBg,
                        }}
                      />
                    </div>
                  </div>
                </div>
              );
            })}
      </div>
    </section>
  );
}

export default function ReviewAnalysisPage() {
  const [activeTab, setActiveTab] = useState<ReviewAnalysisTab>("rating");
  const [data, setData] = useState<ReviewDashboardData>(EMPTY_DATA);
  const [ratedBanks, setRatedBanks] = useState<ReviewAnalysisRow[]>([]);
  const [selectedRating, setSelectedRating] = useState(5);
  const [loading, setLoading] = useState(true);
  const [ratedBanksLoading, setRatedBanksLoading] = useState(true);
  const [error, setError] = useState("");

  const [selectedTopicBank, setSelectedTopicBank] = useState("");
  const [topicBankOptions, setTopicBankOptions] = useState<FilterOption[]>([]);
  const [topicsData, setTopicsData] = useState<TopicsData>(EMPTY_TOPICS_DATA);
  const [topicsLoading, setTopicsLoading] = useState(true);
  const [topicOrder, setTopicOrder] = useState<string[]>([]);

  useEffect(() => {
    let active = true;

    Promise.all([getReviewsPerBank(), getTopRatedBanks(), getAvgSentimentByBank()])
      .then(([reviewsPerBank, topRatedBanks, avgSentimentByBank]) => {
        if (!active) return;

        setData({ reviewsPerBank, topRatedBanks, avgSentimentByBank });
        setError("");
      })
      .catch(() => {
        if (!active) return;

        setData(EMPTY_DATA);
        setError("Unable to load review analysis data.");
      })
      .finally(() => {
        if (active) setLoading(false);
      });

    return () => {
      active = false;
    };
  }, []);

  useEffect(() => {
    let active = true;

    getRatedBanks(selectedRating)
      .then((res) => {
        if (!active) return;
        setRatedBanks(res.items ?? []);
      })
      .catch(() => {
        if (!active) return;
        setRatedBanks([]);
      })
      .finally(() => {
        if (active) setRatedBanksLoading(false);
      });

    return () => {
      active = false;
    };
  }, [selectedRating]);

  useEffect(() => {
    let active = true;

    getDigitalBrandHealthBanks()
      .then((res) => {
        if (!active) return;
        setTopicBankOptions(
          (res.banks ?? []).filter(Boolean).map((bank) => ({ label: bank, value: bank }))
        );
      })
      .catch(() => {
        if (!active) return;
        setTopicBankOptions([]);
      });

    return () => {
      active = false;
    };
  }, []);

  useEffect(() => {
    let active = true;

    Promise.all([
      getReviewTopicsDistribution(selectedTopicBank || undefined),
      getAvgRatingByTopic(selectedTopicBank || undefined),
    ])
      .then(([distribution, rating]) => {
        if (!active) return;
        setTopicsData({ distribution, rating });
      })
      .catch(() => {
        if (!active) return;
        setTopicsData(EMPTY_TOPICS_DATA);
      })
      .finally(() => {
        if (active) setTopicsLoading(false);
      });

    return () => {
      active = false;
    };
  }, [selectedTopicBank]);

  // Locks the topic order in on the first non-empty load, then never changes it again —
  // this is React's documented "adjust state during render" pattern (not an effect),
  // guarded so the setState below only ever fires on the empty -> populated transition.
  if (topicOrder.length === 0) {
    const names = new Set<string>();
    topicsData.distribution.forEach((row) => names.add(toTopicName(row)));
    topicsData.rating.forEach((row) => names.add(toTopicName(row)));

    if (names.size > 0) {
      setTopicOrder(Array.from(names));
    }
  }

  const handleRatingChange = (rating: number) => {
    if (rating === selectedRating) return;

    setRatedBanksLoading(true);
    setSelectedRating(rating);
  };

  const handleTopicBankChange = (value: string) => {
    if (value === selectedTopicBank) return;
    setTopicsLoading(true);
    setSelectedTopicBank(value);
  };

  const topicBankFilterOptions = useMemo<FilterOption[]>(
    () => [{ label: "All Developers", value: "" }, ...topicBankOptions],
    [topicBankOptions]
  );

  const reviewsPerBank = useMemo(
    () =>
      buildChartData(data.reviewsPerBank, toBankName, [
        "ratings",
        "total_reviews",
        "reviews",
        "review_count",
        "count",
        "total",
        "value",
      ]),
    [data.reviewsPerBank]
  );

  const topRatedBanks = useMemo(
    () =>
      buildChartData(data.topRatedBanks, toBankName, [
        "avg_rating",
        "average_rating",
        "rating",
        "score",
        "value",
      ]),
    [data.topRatedBanks]
  );

  const avgSentimentByBank = useMemo(
    () =>
      buildChartData(data.avgSentimentByBank, toBankName, [
        "avg_sentiment",
        "average_sentiment",
        "sentiment",
        "sentiment_score",
        "score",
        "value",
      ]),
    [data.avgSentimentByBank]
  );

  const reviewTopicsDistribution = useMemo(() => {
    const built = buildChartData(topicsData.distribution, toTopicName, [
      "total_reviews",
      "reviews",
      "review_count",
      "count",
      "total",
      "value",
    ]);
    return topicOrder.length > 0 ? alignChartDataToOrder(topicOrder, built) : built;
  }, [topicsData.distribution, topicOrder]);

  const avgRatingByTopic = useMemo(() => {
    if (topicOrder.length > 0) {
      return alignTopicRatingToOrder(topicOrder, topicsData.rating);
    }

    return topicsData.rating.map((row) => ({
      name: toTopicName(row),
      value: pickNumberOrNull(row, ["avg_rating", "average_rating", "rating", "score", "value"]),
      count: pickNumberOrNull(row, ["review_count", "reviews", "total_reviews", "count"]),
    }));
  }, [topicsData.rating, topicOrder]);

  const summary = useMemo(() => {
    const highestRated = topRatedBanks.reduce<ChartData | null>(
      (best, item) => (!best || item.value > best.value ? item : best),
      null
    );
    const mostReviewed = reviewsPerBank.reduce<ChartData | null>(
      (best, item) => (!best || item.value > best.value ? item : best),
      null
    );
    const bestSentiment = avgSentimentByBank.reduce<ChartData | null>(
      (best, item) => (!best || item.value > best.value ? item : best),
      null
    );

    return {
      highestRated,
      mostReviewed,
      bestSentiment,
    };
  }, [avgSentimentByBank, reviewsPerBank, topRatedBanks]);

  return (
    <div className="min-h-screen">
      <DashboardTopbar title="BrandIQ" />

      <main className="p-8">
        <section className="mb-6 overflow-hidden rounded-2xl bg-gradient-to-r from-[#3f3fb3] via-[#6d7ddc] to-[#b21883] p-6 text-white shadow-lg">
          <div className="grid gap-6 lg:grid-cols-[1.45fr_1fr_1fr_1fr] lg:items-center">
            <div className="flex flex-col justify-center">
              <h1 className="text-2xl font-bold">Review Analysis</h1>
              <p className="mt-3 max-w-3xl text-sm leading-6 text-white/90">
                Captures the voice of experience, what customers say after
                engaging with the brand or its products. It analyzes ratings,
                review patterns, and sentiment to uncover key themes, strengths,
                and friction points.
              </p>
            </div>

            <div className="rounded-xl bg-white/20 p-4 shadow-sm ring-1 ring-white/15 backdrop-blur">
              <div className="mb-3 flex h-9 w-9 items-center justify-center rounded-xl bg-sky-500 text-white shadow-md">
                <Star className="h-5 w-5" />
              </div>
              <p className="text-2xl font-bold leading-tight">
                {loading || !summary.highestRated
                  ? "-"
                  : `${summary.highestRated.name} - ${formatScore(summary.highestRated.value)}`}
              </p>
              <p className="mt-2 text-sm font-medium text-white/75">
                Highest Rated Brand
              </p>
            </div>

            <div className="rounded-xl bg-white/20 p-4 shadow-sm ring-1 ring-white/15 backdrop-blur">
              <div className="mb-3 flex h-9 w-9 items-center justify-center rounded-xl bg-orange-500 text-white shadow-md">
                <MessageSquareText className="h-5 w-5" />
              </div>
              <p className="text-lg font-bold leading-tight">
                {loading || !summary.mostReviewed
                  ? "-"
                  : summary.mostReviewed.name}
              </p>
              <p className="mt-2 text-sm font-medium text-white/75">
                Most Reviewed Brand
              </p>
            </div>

            <div className="rounded-xl bg-white/20 p-4 shadow-sm ring-1 ring-white/15 backdrop-blur">
              <div className="mb-3 flex h-9 w-9 items-center justify-center rounded-xl bg-emerald-500 text-white shadow-md">
                <TrendingUp className="h-5 w-5" />
              </div>
              <p className="text-lg font-bold leading-tight">
                {loading || !summary.bestSentiment
                  ? "-"
                  : summary.bestSentiment.name}
              </p>
              <p className="mt-2 text-sm font-medium text-white/75">
                Best Sentiment Brand
              </p>
            </div>
          </div>
        </section>

        {error && (
          <div className="mb-6 rounded-lg border border-red-500/30 bg-red-500/10 px-4 py-3 text-sm font-medium text-red-500">
            {error}
          </div>
        )}

        <div className="mb-6 inline-flex rounded-full border border-[var(--card-bd)] bg-[var(--card-bg)] p-1 shadow-sm">
          {REVIEW_ANALYSIS_TABS.map((tab) => {
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

        {activeTab === "rating" && (
          <>
            <RatingsAcrossBrandsChart data={topRatedBanks} loading={loading} />

            <div className="mt-6">
              <RatedBanksPanel
                rating={selectedRating}
                onRatingChange={handleRatingChange}
                items={ratedBanks}
                loading={ratedBanksLoading}
              />
            </div>
          </>
        )}

        {activeTab === "review" && (
          <>
            <ReviewsPerBankCard data={reviewsPerBank} loading={loading} />

            <div className="mt-6">
              <AverageSentimentByBankCard
                items={data.avgSentimentByBank}
                loading={loading}
              />
            </div>

            <div className="mt-6 flex flex-col gap-3 sm:flex-row sm:items-end sm:justify-between">
              <div>
                <h2 className="text-lg font-semibold text-[var(--title-tx)]">
                  Topic Breakdown
                </h2>
                <p className="mt-1 text-sm text-[var(--muted-tx)]">
                  Filter both charts below by developer.
                </p>
              </div>
              <div className="w-full sm:max-w-xs">
                <FilterSelect
                  label="Developer"
                  value={selectedTopicBank}
                  onChange={handleTopicBankChange}
                  options={topicBankFilterOptions}
                />
              </div>
            </div>

            <div className="mt-4 grid grid-cols-1 gap-6 xl:grid-cols-2">
              <ReviewTopicsDistributionCard
                data={reviewTopicsDistribution}
                loading={topicsLoading}
              />

              <TopicRatingBars data={avgRatingByTopic} loading={topicsLoading} />
            </div>
          </>
        )}
      </main>
    </div>
  );
}
