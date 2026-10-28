"use client";

import { useEffect, useMemo, useRef, useState } from "react";
import dynamic from "next/dynamic";
import DashboardTopbar from "@/components/layout/DashboardTopbar";
import FilterSelect from "@/components/filters/FilterSelect";
import ExportExcelButton from "@/components/ui/ExportExcelButton";
import {
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
import { ArrowUpRight, Map as MapIcon, Search, TrendingUp } from "lucide-react";
import {
  getDigitalBrandHealthProducts,
  getSearchBankDistribution,
  getSearchDataBanks,
  getSearchDataMaps,
  getSearchDistributionOverTime,
  getSearchProductDistribution,
  getSearchProductDistributionOverTime,
  getSearchProductMaps,
  getSearchProductTopGrowing,
  getSearchTopGrowingBanks,
  type SearchDataFrequency,
  type SearchDataRow,
  type SearchFilters,
  type SearchProductMapItem,
} from "@/lib/realEstate";
import { getBankColor } from "@/lib/bankColors";

const SearchProductUaeMap = dynamic(
  () => import("@/components/maps/SearchProductUaeMap"),
  {
    ssr: false,
    loading: () => <div className="h-[560px] animate-pulse rounded-2xl bg-[var(--card-bg-2)]" />,
  }
);

type BankValuePoint = {
  name: string;
  value: number;
};

type TrendRow = {
  period: string;
  [key: string]: string | number;
};

type MomentumRow = {
  bank: string;
  currentShareOfSearch: number;
  growth: number;
};

type SearchDataTab = "brand-search" | "product-search" | "geography";
type GeoLens = "brand" | "product";

type FilterOption = {
  label: string;
  value: string;
};

const SEARCH_DATA_TABS: Array<{
  id: SearchDataTab;
  label: string;
  icon: typeof Search;
}> = [
  { id: "brand-search", label: "Brand Search", icon: Search },
  { id: "geography", label: "Geography", icon: MapIcon },
];

const SEARCH_COLORS = [
  "#2563eb",
  "#10b981",
  "#f59e0b",
  "#ef4444",
  "#8b5cf6",
  "#06b6d4",
  "#ec4899",
  "#64748b",
];

function defaultSearchColor(_name: string, index: number) {
  return SEARCH_COLORS[index % SEARCH_COLORS.length];
}

const FREQUENCIES: { label: string; value: SearchDataFrequency }[] = [
  { label: "1m", value: "1m" },
  { label: "3m", value: "3m" },
  { label: "6m", value: "6m" },
  { label: "1y", value: "1y" },
];

const SEARCH_MIN_DATE = "2025-01-01";
const SEARCH_MAX_DATE = new Date().toISOString().slice(0, 10);
const MAX_SELECTED_BANKS = 5;
const TOP_MOVERS_COUNT = 5;

function formatCompactNumber(value: number) {
  return new Intl.NumberFormat("en-US", {
    notation: Math.abs(value) >= 1000 ? "compact" : "standard",
    maximumFractionDigits: Math.abs(value) >= 1000 ? 2 : 0,
  }).format(value);
}

function formatGrowth(value: number) {
  return `${value >= 0 ? "+" : ""}${value.toFixed(2)}%`;
}

function clampDate(value: string, fallback: string) {
  const date = value || fallback;
  if (date < SEARCH_MIN_DATE) return SEARCH_MIN_DATE;
  if (date > SEARCH_MAX_DATE) return SEARCH_MAX_DATE;
  return date;
}

function pickString(row: SearchDataRow, keys: string[], fallback = "") {
  for (const key of keys) {
    const value = row[key];
    if (typeof value === "string" && value.trim()) return value.trim();
    if (typeof value === "number" && Number.isFinite(value)) return String(value);
  }

  return fallback;
}

function pickNumber(row: SearchDataRow, keys: string[], fallback = 0) {
  for (const key of keys) {
    const value = row[key];
    if (typeof value === "number" && Number.isFinite(value)) return value;
    if (typeof value === "string" && value.trim() && Number.isFinite(Number(value))) {
      return Number(value);
    }
  }

  return fallback;
}

function normalizeBankRows(rows: SearchDataRow[]): BankValuePoint[] {
  return rows
    .map((row) => ({
      name: pickString(row, [
        "developer",
        "bank",
        "brand",
        "product",
        "products",
        "product_name",
        "name",
        "label",
      ]),
      value: pickNumber(row, [
        "avg_value",
        "percentage",
        "value",
        "total_mentions",
        "search_volume",
        "volume",
        "total",
        "count",
        "score",
        "growth",
        "growth_rate",
      ]),
    }))
    .filter((item) => item.name && item.value > 0)
    .sort((a, b) => b.value - a.value);
}

function normalizeMomentumRows(rows: SearchDataRow[]): MomentumRow[] {
  return rows
    .map((row) => ({
      bank: pickString(row, ["developer", "bank", "brand", "product", "product_name", "name", "label"]),
      currentShareOfSearch: pickNumber(row, [
        "current_share_of_search",
        "percentage",
        "share_of_search",
      ]),
      growth: pickNumber(row, ["growth", "growth_rate"]),
    }))
    .filter((row) => row.bank)
    .sort((a, b) => b.growth - a.growth);
}

function normalizeTrendRows(rows: SearchDataRow[]): TrendRow[] {
  const longRows = rows
    .map((row) => ({
      period: pickString(row, ["period", "month", "date", "week"], ""),
      bank: pickString(
        row,
        ["developer", "bank", "brand", "product", "products", "product_name", "name", "label"],
        ""
      ),
      value: pickNumber(row, [
        "percentage",
        "value",
        "total_mentions",
        "search_volume",
        "volume",
        "total",
        "count",
        "score",
        "growth",
        "growth_rate",
      ]),
    }))
    .filter((row) => row.period && row.bank && row.value > 0);

  if (longRows.length > 0) {
    const byPeriod = new Map<string, TrendRow>();

    longRows.forEach((row) => {
      const existing = byPeriod.get(row.period) ?? { period: row.period };
      existing[row.bank] = row.value;
      byPeriod.set(row.period, existing);
    });

    return Array.from(byPeriod.values()).sort((a, b) =>
      String(a.period).localeCompare(String(b.period))
    );
  }

  return rows
    .map((row) => {
      const period = pickString(row, ["period", "month", "date", "week"], "");
      const normalized: TrendRow = { period };
      const nested = row.data ?? row.values ?? row.developers ?? row.banks;

      if (nested && typeof nested === "object" && !Array.isArray(nested)) {
        Object.entries(nested as Record<string, unknown>).forEach(([key, value]) => {
          if (typeof value === "number" && Number.isFinite(value)) {
            normalized[key] = value;
          }
        });
      }

      Object.entries(row).forEach(([key, value]) => {
        if (["period", "month", "date", "week", "data", "values", "developers", "banks"].includes(key)) {
          return;
        }
        if (typeof value === "number" && Number.isFinite(value)) {
          normalized[key] = value;
        }
      });

      return normalized;
    })
    .filter((row) => row.period);
}

function extractTrendSeriesNames(rows: TrendRow[]) {
  return Array.from(
    new Set(rows.flatMap((row) => Object.keys(row).filter((key) => key !== "period")))
  );
}

function normalizeSelectionKey(value: string) {
  return value.toLowerCase().replace(/[^a-z0-9]/g, "");
}

function resolveFilterOptionValue(label: string, options: FilterOption[]) {
  const key = normalizeSelectionKey(label);

  return (
    options.find(
      (option) =>
        normalizeSelectionKey(option.value) === key ||
        normalizeSelectionKey(option.label) === key
    )?.value ?? label
  );
}

function getSelectedBankIndex(option: FilterOption, selectedBanks: string[]) {
  const optionKeys = [
    normalizeSelectionKey(option.value),
    normalizeSelectionKey(option.label),
  ];

  return selectedBanks.findIndex((bank) => {
    const bankKey = normalizeSelectionKey(bank);
    return optionKeys.includes(bankKey);
  });
}

function FrequencyControl({
  frequency,
  onChange,
  accent = "#2563eb",
}: {
  frequency: SearchDataFrequency;
  onChange: (frequency: SearchDataFrequency) => void;
  accent?: string;
}) {
  return (
    <div className="inline-flex rounded-full border border-[var(--card-bd)] bg-[var(--card-bg-2)] p-1">
      {FREQUENCIES.map((item) => {
        const active = item.value === frequency;

        return (
          <button
            key={item.value}
            type="button"
            onClick={() => onChange(item.value)}
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
  );
}

function VerticalBarAxisTick({
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

function VerticalBarCard({
  title,
  description,
  data,
  loading,
  emptyMessage,
  accent = "#2563eb",
  getColor = defaultSearchColor,
}: {
  title: string;
  description: string;
  data: BankValuePoint[];
  loading: boolean;
  emptyMessage: string;
  accent?: string;
  getColor?: (name: string, index: number) => string;
}) {
  const chartWidth = Math.max(data.length * 56, 640);
  const longestName = data.reduce((max, item) => Math.max(max, item.name.length), 0);
  const axisHeight = Math.min(260, Math.max(70, Math.round(longestName * 6.4) + 20));
  const chartHeight = 300 + axisHeight;

  return (
    <section className="rounded-2xl border border-[var(--card-bd)] bg-[var(--card-bg)] p-6 shadow-sm">
      <div className="flex flex-col gap-3 sm:flex-row sm:items-start sm:justify-between">
        <div>
          <h2 className="text-xl font-bold text-[var(--title-tx)]">{title}</h2>
          <p className="mt-1 text-sm text-[var(--muted-tx)]">{description}</p>
        </div>
        <div className="flex items-start gap-3">
          <ExportExcelButton
            rows={data}
            filename={title}
            sheetName={title}
            disabled={loading}
          />
        </div>
      </div>

      {loading ? (
        <div className="mt-6 h-[480px] animate-pulse rounded-2xl bg-[var(--card-bg-2)]" />
      ) : data.length === 0 ? (
        <div className="mt-6 flex h-[480px] items-center justify-center rounded-2xl border border-[var(--card-bd)] bg-[var(--card-bg-2)] text-sm text-[var(--muted-tx)]">
          {emptyMessage}
        </div>
      ) : (
        <div className="mt-6 overflow-x-auto rounded-2xl border border-[var(--card-bd)] bg-[var(--card-bg-2)] px-4 py-5 shadow-sm" style={{ height: chartHeight }}>
          <div style={{ width: chartWidth, minWidth: "100%", height: "100%" }}>
            <ResponsiveContainer width="100%" height="100%">
              <BarChart data={data} margin={{ top: 24, right: 12, left: 0, bottom: 8 }}>
                <CartesianGrid strokeDasharray="3 3" strokeOpacity={0.12} vertical={false} />
                <XAxis
                  dataKey="name"
                  interval={0}
                  height={axisHeight}
                  tick={<VerticalBarAxisTick />}
                  tickLine={false}
                  axisLine={{ stroke: "var(--card-bd)" }}
                />
                <YAxis
                  width={54}
                  tick={{ fill: "var(--muted-tx)", fontSize: 11, fontWeight: 700 }}
                  tickFormatter={(value) => formatCompactNumber(Number(value))}
                  tickLine={false}
                  axisLine={false}
                />
                <Tooltip
                  cursor={{ fill: `${accent}14` }}
                  formatter={(value) => [Number(value).toFixed(2), "Value"]}
                  contentStyle={{
                    background: "var(--tooltip-bg)",
                    border: "1px solid var(--tooltip-bd)",
                    borderRadius: 12,
                    color: "var(--tooltip-tx)",
                  }}
                  labelStyle={{ color: "var(--tooltip-tx)" }}
                  itemStyle={{ color: "var(--tooltip-tx)" }}
                />
                <Bar dataKey="value" radius={[10, 10, 4, 4]} maxBarSize={40}>
                  {data.map((item, index) => (
                    <Cell
                      key={`${item.name}-${index}`}
                      fill={getColor(item.name, index)}
                    />
                  ))}
                  <LabelList
                    dataKey="value"
                    position="top"
                    formatter={(value) =>
                      typeof value === "number" ? formatCompactNumber(value) : `${value ?? ""}`
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

function TrendCard({
  title,
  description,
  data,
  frequency,
  loading,
  onFrequencyChange,
  emptyMessage,
  accent,
  bankOptions = [],
  selectedBanks = [],
  onBankToggle,
  maxSelectedBanks = MAX_SELECTED_BANKS,
  getColor = defaultSearchColor,
}: {
  title: string;
  description: string;
  data: TrendRow[];
  frequency: SearchDataFrequency;
  loading: boolean;
  onFrequencyChange: (frequency: SearchDataFrequency) => void;
  emptyMessage: string;
  accent: string;
  bankOptions?: FilterOption[];
  selectedBanks?: string[];
  onBankToggle?: (bank: string) => void;
  maxSelectedBanks?: number;
  getColor?: (name: string, index: number) => string;
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
  const showBankSelector = bankOptions.length > 0 && Boolean(onBankToggle);

  return (
    <section className="rounded-2xl border border-[var(--card-bd)] bg-[var(--card-bg)] p-6 shadow-sm">
      <div className="flex flex-col gap-4 sm:flex-row sm:items-start sm:justify-between">
        <div>
          <h2 className="text-xl font-bold text-[var(--title-tx)]">{title}</h2>
          <p className="mt-1 text-sm text-[var(--muted-tx)]">{description}</p>
        </div>
        <div className="flex flex-wrap items-center gap-3">
          <ExportExcelButton
            rows={data}
            filename={title}
            sheetName={title}
            disabled={loading}
          />
          <FrequencyControl frequency={frequency} onChange={onFrequencyChange} accent={accent} />
        </div>
      </div>

      {showBankSelector && (
        <div className="mt-5 flex flex-wrap gap-2">
          {bankOptions
            .filter((option) => option.value)
            .map((option) => {
              const selectedIndex = getSelectedBankIndex(option, selectedBanks);
              const selected = selectedIndex >= 0;
              const disabled = !selected && selectedBanks.length >= maxSelectedBanks;
              const color = selected
                ? getColor(option.label, selectedIndex)
                : "rgba(100, 116, 139, 0.24)";

              return (
                <button
                  key={option.value}
                  type="button"
                  onClick={() => onBankToggle?.(option.value)}
                  disabled={disabled}
                  title={
                    disabled
                      ? `Select up to ${maxSelectedBanks} items`
                      : option.label
                  }
                  className="h-9 rounded-full px-4 text-sm font-semibold transition disabled:cursor-not-allowed disabled:opacity-50"
                  style={{
                    background: color,
                    color: selected ? "#ffffff" : "var(--muted-tx)",
                  }}
                >
                  {option.label}
                </button>
              );
            })}
        </div>
      )}

      {loading ? (
        <div className="mt-6 h-[340px] animate-pulse rounded-2xl bg-[var(--card-bg-2)]" />
      ) : data.length === 0 || series.length === 0 ? (
        <div className="mt-6 flex h-[340px] items-center justify-center text-sm text-[var(--muted-tx)]">
          {emptyMessage}
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
                width={58}
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
                  stroke={getColor(key, index)}
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

function MomentumTable({
  title,
  description,
  rows,
  loading,
  filenamePrefix,
}: {
  title: string;
  description: string;
  rows: MomentumRow[];
  loading: boolean;
  filenamePrefix: string;
}) {
  const sortedRows = [...rows].sort((a, b) => b.growth - a.growth);

  return (
    <section className="rounded-2xl border border-[var(--card-bd)] bg-[var(--card-bg)] p-6 shadow-sm">
      <div className="mb-5 flex flex-col gap-3 sm:flex-row sm:items-start sm:justify-between">
        <div>
          <h2 className="text-xl font-bold text-[var(--title-tx)]">{title}</h2>
          <p className="mt-1 text-sm text-[var(--muted-tx)]">{description}</p>
        </div>
        <ExportExcelButton
          rows={sortedRows.map((row) => ({
            bank: row.bank,
            current_share_of_search: row.currentShareOfSearch,
            growth: row.growth,
          }))}
          filename={filenamePrefix}
          sheetName={title}
          disabled={loading}
        />
      </div>

      {loading ? (
        <div className="h-[280px] animate-pulse rounded-2xl bg-[var(--card-bg-2)]" />
      ) : sortedRows.length === 0 ? (
        <div className="flex h-[200px] items-center justify-center text-sm text-[var(--muted-tx)]">
          No momentum data available
        </div>
      ) : (
        <div className="overflow-hidden rounded-2xl border border-[var(--card-bd)] bg-[var(--card-bg-2)]">
          <div className="grid grid-cols-[1.4fr_1fr_1fr] px-4 py-3 text-xs font-bold uppercase tracking-[0.1em] text-[var(--muted-tx)]">
            <div>Developer</div>
            <div className="text-right">Current Share of Search</div>
            <div className="text-right">Growth %</div>
          </div>
          {sortedRows.map((row, index) => {
            const isTopMover = index < TOP_MOVERS_COUNT && row.growth > 0;
            const isNegative = row.growth < 0;
            const rowBg = isTopMover
              ? "rgba(16,185,129,0.12)"
              : isNegative
                ? "rgba(239,68,68,0.1)"
                : "transparent";
            const growthColor = isTopMover
              ? "#059669"
              : isNegative
                ? "#dc2626"
                : "var(--title-tx)";

            return (
              <div
                key={row.bank}
                className="grid grid-cols-[1.4fr_1fr_1fr] items-center border-t border-[var(--card-bd)] px-4 py-3 text-sm"
                style={{ background: rowBg }}
              >
                <div className="font-semibold text-[var(--title-tx)]">{row.bank}</div>
                <div className="text-right font-semibold text-[var(--title-tx)]">
                  {row.currentShareOfSearch.toFixed(2)}%
                </div>
                <div className="text-right font-bold" style={{ color: growthColor }}>
                  {formatGrowth(row.growth)}
                </div>
              </div>
            );
          })}
        </div>
      )}
    </section>
  );
}

export default function SearchDataPage() {
  const [activeTab, setActiveTab] = useState<SearchDataTab>("brand-search");
  const [geoLens, setGeoLens] = useState<GeoLens>("brand");
  const [selectedBank, setSelectedBank] = useState("");
  const [selectedShareTrendBanks, setSelectedShareTrendBanks] = useState<string[]>([]);
  const [shareTrendBankOptions, setShareTrendBankOptions] = useState<FilterOption[]>([]);
  const [productTrendOptions, setProductTrendOptions] = useState<FilterOption[]>([]);
  const [selectedProductShareTrendProducts, setSelectedProductShareTrendProducts] =
    useState<string[]>([]);
  const [selectedProduct, setSelectedProduct] = useState("");
  const [startDate, setStartDate] = useState(SEARCH_MIN_DATE);
  const [endDate, setEndDate] = useState(SEARCH_MAX_DATE);
  const [distribution, setDistribution] = useState<SearchDataRow[]>([]);
  const [distributionOverTime, setDistributionOverTime] = useState<SearchDataRow[]>([]);
  const [topGrowingBanks, setTopGrowingBanks] = useState<SearchDataRow[]>([]);
  const [productDistribution, setProductDistribution] = useState<SearchDataRow[]>([]);
  const [productDistributionOverTime, setProductDistributionOverTime] = useState<SearchDataRow[]>(
    []
  );
  const [productTopGrowing, setProductTopGrowing] = useState<SearchDataRow[]>([]);
  const [productMapData, setProductMapData] = useState<SearchProductMapItem[]>([]);
  const [searchDataMapData, setSearchDataMapData] = useState<SearchProductMapItem[]>([]);
  const [shareFrequency, setShareFrequency] = useState<SearchDataFrequency>("3m");
  const [productShareFrequency, setProductShareFrequency] =
    useState<SearchDataFrequency>("3m");
  const [distributionLoading, setDistributionLoading] = useState(true);
  const [shareTrendLoading, setShareTrendLoading] = useState(true);
  const [growingLoading, setGrowingLoading] = useState(true);
  const [productDistributionLoading, setProductDistributionLoading] = useState(true);
  const [productShareTrendLoading, setProductShareTrendLoading] = useState(true);
  const [productGrowingLoading, setProductGrowingLoading] = useState(true);
  const [productMapLoading, setProductMapLoading] = useState(true);
  const [searchDataMapLoading, setSearchDataMapLoading] = useState(true);
  const [error, setError] = useState("");
  const defaultShareTrendBanksSyncedRef = useRef(false);
  const defaultProductShareTrendSyncedRef = useRef(false);

  const brandSearchFilters = useMemo<SearchFilters>(
    () => ({
      bank: selectedBank || undefined,
      startDate,
      endDate,
    }),
    [endDate, selectedBank, startDate]
  );
  const productSearchFilters = useMemo<SearchFilters>(
    () => ({
      product: selectedProduct || undefined,
      startDate,
      endDate,
    }),
    [endDate, selectedProduct, startDate]
  );
  const productMapFilters = useMemo<SearchFilters>(
    () => ({
      product: selectedProduct || undefined,
      startDate,
      endDate,
    }),
    [selectedProduct, startDate, endDate]
  );
  const brandMapFilters = useMemo<SearchFilters>(
    () => ({
      bank: selectedBank || undefined,
      startDate,
      endDate,
    }),
    [selectedBank, startDate, endDate]
  );
  const shareTrendSearchFilters = useMemo<SearchFilters>(
    () => ({
      ...brandSearchFilters,
      banks: selectedShareTrendBanks.slice(0, MAX_SELECTED_BANKS),
    }),
    [brandSearchFilters, selectedShareTrendBanks]
  );
  const productShareTrendSearchFilters = useMemo<SearchFilters>(
    () => ({
      ...productSearchFilters,
      product: undefined,
      products: selectedProductShareTrendProducts.slice(0, MAX_SELECTED_BANKS),
    }),
    [productSearchFilters, selectedProductShareTrendProducts]
  );
  const bankOptions = useMemo<FilterOption[]>(
    () => [{ label: "Top Developers", value: "" }, ...shareTrendBankOptions],
    [shareTrendBankOptions]
  );
  const productOptions = useMemo<FilterOption[]>(
    () => [{ label: "Top Products", value: "" }, ...productTrendOptions],
    [productTrendOptions]
  );
  const showBankFilter =
    activeTab === "brand-search" || (activeTab === "geography" && geoLens === "brand");
  const showProductFilter =
    activeTab === "product-search" || (activeTab === "geography" && geoLens === "product");
  const visibleFilterCount = Number(showBankFilter) + Number(showProductFilter) + 2;

  useEffect(() => {
    let active = true;

    Promise.allSettled([getSearchDataBanks(), getDigitalBrandHealthProducts()])
      .then(([banksResult, productsResult]) => {
        if (!active) return;

        setShareTrendBankOptions(
          banksResult.status === "fulfilled"
            ? (banksResult.value.banks ?? [])
                .filter(Boolean)
                .map((bank) => ({ label: bank, value: bank }))
            : []
        );

        setProductTrendOptions(
          productsResult.status === "fulfilled"
            ? (productsResult.value.products ?? [])
                .filter(Boolean)
                .map((product) => ({ label: product, value: product }))
            : []
        );
      });

    return () => {
      active = false;
    };
  }, []);

  useEffect(() => {
    let active = true;

    getSearchBankDistribution(brandSearchFilters)
      .then((res) => {
        if (!active) return;
        setDistribution(res.distribution ?? []);
      })
      .catch((err) => {
        if (!active) return;
        setError(err instanceof Error ? err.message : "Failed to load search data");
        setDistribution([]);
      })
      .finally(() => {
        if (active) setDistributionLoading(false);
      });

    return () => {
      active = false;
    };
  }, [brandSearchFilters]);

  useEffect(() => {
    let active = true;

    getSearchTopGrowingBanks(brandSearchFilters)
      .then((res) => {
        if (!active) return;
        setTopGrowingBanks(res.top_growing_banks ?? []);
      })
      .catch((err) => {
        if (!active) return;
        setError(err instanceof Error ? err.message : "Failed to load search data");
        setTopGrowingBanks([]);
      })
      .finally(() => {
        if (active) setGrowingLoading(false);
      });

    return () => {
      active = false;
    };
  }, [brandSearchFilters]);

  useEffect(() => {
    let active = true;

    getSearchDistributionOverTime(shareFrequency, shareTrendSearchFilters)
      .then((res) => {
        if (!active) return;
        const rows = res.data ?? [];
        setDistributionOverTime(rows);

        if (!defaultShareTrendBanksSyncedRef.current && selectedShareTrendBanks.length === 0) {
          const defaultBanks = extractTrendSeriesNames(normalizeTrendRows(rows))
            .map((bank) => resolveFilterOptionValue(bank, shareTrendBankOptions))
            .slice(0, MAX_SELECTED_BANKS);

          if (defaultBanks.length > 0) {
            defaultShareTrendBanksSyncedRef.current = true;
            setSelectedShareTrendBanks(defaultBanks);
            setShareTrendLoading(true);
          }
        }
      })
      .catch((err) => {
        if (!active) return;
        setError(err instanceof Error ? err.message : "Failed to load search data");
        setDistributionOverTime([]);
      })
      .finally(() => {
        if (active) setShareTrendLoading(false);
      });

    return () => {
      active = false;
    };
  }, [
    selectedShareTrendBanks.length,
    shareFrequency,
    shareTrendBankOptions,
    shareTrendSearchFilters,
  ]);

  useEffect(() => {
    let active = true;

    getSearchProductDistribution(productSearchFilters)
      .then((res) => {
        if (!active) return;
        setProductDistribution(res.distribution ?? []);
      })
      .catch((err) => {
        if (!active) return;
        setError(err instanceof Error ? err.message : "Failed to load product search data");
        setProductDistribution([]);
      })
      .finally(() => {
        if (active) setProductDistributionLoading(false);
      });

    return () => {
      active = false;
    };
  }, [productSearchFilters]);

  useEffect(() => {
    let active = true;

    getSearchProductTopGrowing(productSearchFilters)
      .then((res) => {
        if (!active) return;
        setProductTopGrowing(res.top_growing_products ?? []);
      })
      .catch((err) => {
        if (!active) return;
        setError(err instanceof Error ? err.message : "Failed to load product search data");
        setProductTopGrowing([]);
      })
      .finally(() => {
        if (active) setProductGrowingLoading(false);
      });

    return () => {
      active = false;
    };
  }, [productSearchFilters]);

  useEffect(() => {
    let active = true;

    getSearchProductDistributionOverTime(productShareFrequency, productShareTrendSearchFilters)
      .then((res) => {
        if (!active) return;
        const rows = res.data ?? [];
        setProductDistributionOverTime(rows);

        if (
          !defaultProductShareTrendSyncedRef.current &&
          selectedProductShareTrendProducts.length === 0
        ) {
          const defaultProducts = extractTrendSeriesNames(normalizeTrendRows(rows))
            .map((product) => resolveFilterOptionValue(product, productTrendOptions))
            .slice(0, MAX_SELECTED_BANKS);

          if (defaultProducts.length > 0) {
            defaultProductShareTrendSyncedRef.current = true;
            setSelectedProductShareTrendProducts(defaultProducts);
            setProductShareTrendLoading(true);
          }
        }
      })
      .catch((err) => {
        if (!active) return;
        setError(err instanceof Error ? err.message : "Failed to load product search data");
        setProductDistributionOverTime([]);
      })
      .finally(() => {
        if (active) setProductShareTrendLoading(false);
      });

    return () => {
      active = false;
    };
  }, [
    productShareFrequency,
    productShareTrendSearchFilters,
    productTrendOptions,
    selectedProductShareTrendProducts.length,
  ]);

  useEffect(() => {
    let active = true;

    getSearchProductMaps(productMapFilters)
      .then((res) => {
        if (!active) return;
        setProductMapData(res.data ?? []);
      })
      .catch((err) => {
        if (!active) return;
        setError(err instanceof Error ? err.message : "Failed to load product map data");
        setProductMapData([]);
      })
      .finally(() => {
        if (active) setProductMapLoading(false);
      });

    return () => {
      active = false;
    };
  }, [productMapFilters]);

  useEffect(() => {
    let active = true;

    getSearchDataMaps(brandMapFilters)
      .then((res) => {
        if (!active) return;
        setSearchDataMapData(res.data ?? []);
      })
      .catch((err) => {
        if (!active) return;
        setError(err instanceof Error ? err.message : "Failed to load search data map");
        setSearchDataMapData([]);
      })
      .finally(() => {
        if (active) setSearchDataMapLoading(false);
      });

    return () => {
      active = false;
    };
  }, [brandMapFilters]);

  const distributionData = useMemo(() => normalizeBankRows(distribution), [distribution]);
  const growingData = useMemo(() => normalizeMomentumRows(topGrowingBanks), [topGrowingBanks]);
  const shareTrendData = useMemo(
    () => normalizeTrendRows(distributionOverTime),
    [distributionOverTime]
  );
  const productDistributionData = useMemo(
    () => normalizeBankRows(productDistribution),
    [productDistribution]
  );
  const productGrowingData = useMemo(
    () => normalizeMomentumRows(productTopGrowing),
    [productTopGrowing]
  );
  const productShareTrendData = useMemo(
    () => normalizeTrendRows(productDistributionOverTime),
    [productDistributionOverTime]
  );

  const handleShareFrequencyChange = (frequency: SearchDataFrequency) => {
    if (frequency === shareFrequency) return;
    setShareTrendLoading(true);
    setShareFrequency(frequency);
  };

  const handleProductShareFrequencyChange = (frequency: SearchDataFrequency) => {
    if (frequency === productShareFrequency) return;
    setProductShareTrendLoading(true);
    setProductShareFrequency(frequency);
  };

  const markFilterLoading = () => {
    setDistributionLoading(true);
    setGrowingLoading(true);
    setShareTrendLoading(true);
    setProductDistributionLoading(true);
    setProductGrowingLoading(true);
    setProductShareTrendLoading(true);
    setProductMapLoading(true);
    setSearchDataMapLoading(true);
  };

  const handleBankChange = (value: string) => {
    if (value === selectedBank) return;

    markFilterLoading();
    setSelectedBank(value);
  };

  const handleProductChange = (value: string) => {
    if (value === selectedProduct) return;

    markFilterLoading();
    setSelectedProduct(value);
  };

  const handleShareTrendBankToggle = (bank: string) => {
    setSelectedShareTrendBanks((current) => {
      if (current.includes(bank)) {
        if (current.length === 1) return current;
        setShareTrendLoading(true);
        return current.filter((item) => item !== bank);
      }

      if (current.length >= MAX_SELECTED_BANKS) return current;

      setShareTrendLoading(true);
      return [...current, bank];
    });
  };

  const handleProductShareTrendProductToggle = (product: string) => {
    setSelectedProductShareTrendProducts((current) => {
      if (current.includes(product)) {
        if (current.length === 1) return current;
        setProductShareTrendLoading(true);
        return current.filter((item) => item !== product);
      }

      if (current.length >= MAX_SELECTED_BANKS) return current;

      setProductShareTrendLoading(true);
      return [...current, product];
    });
  };

  const handleStartDateChange = (value: string) => {
    const nextDate = clampDate(value, SEARCH_MIN_DATE);
    if (nextDate === startDate) return;

    markFilterLoading();
    setStartDate(nextDate);
    if (nextDate > endDate) setEndDate(nextDate);
  };

  const handleEndDateChange = (value: string) => {
    const nextDate = clampDate(value, SEARCH_MAX_DATE);
    if (nextDate === endDate) return;

    markFilterLoading();
    setEndDate(nextDate);
    if (nextDate < startDate) setStartDate(nextDate);
  };

  return (
    <div className="min-h-screen">
      <DashboardTopbar title="BrandIQ" />

      <main className="p-8">
        <section className="mb-6 overflow-hidden rounded-2xl bg-gradient-to-r from-[#3f3fb3] via-[#6d7ddc] to-[#b21883] p-6 text-white shadow-lg">
          <div className="grid gap-6 lg:grid-cols-[1.55fr_0.75fr_0.75fr_0.75fr] lg:items-center">
            <div>
              <h1 className="text-2xl font-bold">Search Intelligence</h1>
              <p className="mt-3 max-w-3xl text-sm leading-6 text-white/90">
                Reflects how much curiosity and intent the brand generates in
                online search behavior. It benchmarks search interest in a
                competitive context, showing how often and in what associations
                people look for the brand.
              </p>
            </div>

            <div className="rounded-xl bg-white/20 p-4 shadow-sm ring-1 ring-white/15 backdrop-blur">
              <div className="mb-3 flex h-9 w-9 items-center justify-center rounded-xl bg-orange-500 text-white shadow-md">
                <Search className="h-5 w-5" />
              </div>
              <p className="text-xl font-bold leading-tight">
                {distributionLoading ? "-" : distributionData.length}
              </p>
              <p className="mt-2 text-sm font-medium text-white/75">
                Developers Tracked
              </p>
            </div>

            <div className="rounded-xl bg-white/20 p-4 shadow-sm ring-1 ring-white/15 backdrop-blur">
              <div className="mb-3 flex h-9 w-9 items-center justify-center rounded-xl bg-emerald-500 text-white shadow-md">
                <ArrowUpRight className="h-5 w-5" />
              </div>
              <p className="text-xl font-bold leading-tight">
                {distributionLoading || !distributionData[0]
                  ? "-"
                  : `${distributionData[0].value.toFixed(1)}%`}
              </p>
              <p className="mt-2 text-sm font-medium text-white/75">
                Highest Share of Search
              </p>
              {!distributionLoading && distributionData[0] && (
                <p className="mt-1 truncate text-xs text-white/70">
                  {distributionData[0].name}
                </p>
              )}
            </div>

            <div className="rounded-xl bg-white/20 p-4 shadow-sm ring-1 ring-white/15 backdrop-blur">
              <div className="mb-3 flex h-9 w-9 items-center justify-center rounded-xl bg-sky-500 text-white shadow-md">
                <TrendingUp className="h-5 w-5" />
              </div>
              <p className="text-xl font-bold leading-tight">
                {growingLoading || !growingData[0] ? "-" : formatGrowth(growingData[0].growth)}
              </p>
              <p className="mt-2 text-sm font-medium text-white/75">
                Fastest-Growing Developer
              </p>
              {!growingLoading && growingData[0] && (
                <p className="mt-1 truncate text-xs text-white/70">
                  {growingData[0].bank}
                </p>
              )}
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
            {SEARCH_DATA_TABS.map((tab) => {
              const active = activeTab === tab.id;
              const Icon = tab.icon;

              return (
                <button
                  key={tab.id}
                  type="button"
                  onClick={() => setActiveTab(tab.id)}
                  className="flex h-9 items-center gap-1.5 rounded-full px-3 text-xs font-semibold transition"
                  style={{
                    background: active ? "#2563eb" : "transparent",
                    color: active ? "#ffffff" : "var(--muted-tx)",
                  }}
                >
                  <Icon className="h-3.5 w-3.5" />
                  {tab.label}
                </button>
              );
            })}
          </div>

          <div
            className="grid gap-3 sm:grid-cols-2 xl:w-auto"
            style={{
              gridTemplateColumns: `repeat(${visibleFilterCount}, minmax(160px, 1fr))`,
            }}
          >
            {showBankFilter && (
              <FilterSelect
                label="Developers"
                value={selectedBank}
                onChange={handleBankChange}
                options={bankOptions}
              />
            )}
            {showProductFilter && (
              <FilterSelect
                label="Product"
                value={selectedProduct}
                onChange={handleProductChange}
                options={productOptions}
              />
            )}
            <div className="relative w-full">
              <label
                style={{ color: "var(--muted-tx)" }}
                className="mb-1 block text-[11px] font-medium"
              >
                Start Date
              </label>
              <input
                type="date"
                value={startDate}
                min={SEARCH_MIN_DATE}
                max={SEARCH_MAX_DATE}
                onChange={(event) => handleStartDateChange(event.target.value)}
                style={{
                  background: "var(--card-bg-2)",
                  borderColor: "var(--card-bd)",
                  color: "var(--title-tx)",
                }}
                className="w-full rounded-xl border px-3 py-2 text-xs outline-none transition-colors hover:border-blue-500 focus:border-blue-500"
              />
            </div>
            <div className="relative w-full">
              <label
                style={{ color: "var(--muted-tx)" }}
                className="mb-1 block text-[11px] font-medium"
              >
                End Date
              </label>
              <input
                type="date"
                value={endDate}
                min={SEARCH_MIN_DATE}
                max={SEARCH_MAX_DATE}
                onChange={(event) => handleEndDateChange(event.target.value)}
                style={{
                  background: "var(--card-bg-2)",
                  borderColor: "var(--card-bd)",
                  color: "var(--title-tx)",
                }}
                className="w-full rounded-xl border px-3 py-2 text-xs outline-none transition-colors hover:border-blue-500 focus:border-blue-500"
              />
            </div>
          </div>
        </div>

        {activeTab === "brand-search" && (
          <div className="space-y-6">
            <VerticalBarCard
              title="Share of Search by Developer"
              description="Every tracked developer, sorted by search visibility."
              data={distributionData}
              loading={distributionLoading}
              emptyMessage="No search distribution data available"
              getColor={getBankColor}
            />

            <TrendCard
              title="Share of Search Over Time"
              description="Share of search movement for leading developers."
              data={shareTrendData}
              frequency={shareFrequency}
              loading={shareTrendLoading}
              onFrequencyChange={handleShareFrequencyChange}
              emptyMessage="No share of search over-time data available"
              accent="#2563eb"
              bankOptions={shareTrendBankOptions}
              selectedBanks={selectedShareTrendBanks}
              onBankToggle={handleShareTrendBankToggle}
              maxSelectedBanks={MAX_SELECTED_BANKS}
              getColor={getBankColor}
            />

            <MomentumTable
              title="Search Momentum"
              description="Current share of search and month-over-month growth, sorted by growth."
              rows={growingData}
              loading={growingLoading}
              filenamePrefix="search_momentum_developers"
            />
          </div>
        )}

        {activeTab === "product-search" && (
          <div className="space-y-6">
            <VerticalBarCard
              title="Share of Search by Product"
              description="Every tracked product, sorted by search visibility."
              data={productDistributionData}
              loading={productDistributionLoading}
              emptyMessage="No product search distribution data available"
            />

            <TrendCard
              title="Share of Search Over Time"
              description="Share of search movement for leading products."
              data={productShareTrendData}
              frequency={productShareFrequency}
              loading={productShareTrendLoading}
              onFrequencyChange={handleProductShareFrequencyChange}
              emptyMessage="No product share of search over-time data available"
              accent="#2563eb"
              bankOptions={productTrendOptions}
              selectedBanks={selectedProductShareTrendProducts}
              onBankToggle={handleProductShareTrendProductToggle}
              maxSelectedBanks={MAX_SELECTED_BANKS}
            />

            <MomentumTable
              title="Search Momentum"
              description="Current share of search and month-over-month growth, sorted by growth."
              rows={productGrowingData}
              loading={productGrowingLoading}
              filenamePrefix="search_momentum_products"
            />
          </div>
        )}

        {activeTab === "geography" && (
          <section className="rounded-2xl border border-[var(--card-bd)] bg-[var(--card-bg)] p-6 shadow-sm">
            <div className="mb-6 flex flex-col gap-3 sm:flex-row sm:items-start sm:justify-between">
              <div>
                <h2 className="text-xl font-bold text-[var(--title-tx)]">
                  Geography
                </h2>
                <p className="mt-1 text-sm text-[var(--muted-tx)]">
                  {geoLens === "brand"
                    ? "Brand search index score by UAE emirate."
                    : "Product search index score by UAE emirate."}
                </p>
              </div>

              <div className="flex items-center gap-3">
                <div className="inline-flex rounded-full border border-[var(--card-bd)] bg-[var(--card-bg-2)] p-1">
                  {(
                    [
                      { id: "brand" as const, label: "Brand Search Map" },
                    ]
                  ).map((lens) => {
                    const active = geoLens === lens.id;

                    return (
                      <button
                        key={lens.id}
                        type="button"
                        onClick={() => setGeoLens(lens.id)}
                        className="h-8 rounded-full px-3 text-xs font-semibold transition"
                        style={{
                          background: active ? "#2563eb" : "transparent",
                          color: active ? "#ffffff" : "var(--muted-tx)",
                        }}
                      >
                        {lens.label}
                      </button>
                    );
                  })}
                </div>
                <ExportExcelButton
                  rows={geoLens === "brand" ? searchDataMapData : productMapData}
                  filename={geoLens === "brand" ? "brand_search_map" : "search_product_map"}
                  sheetName={geoLens === "brand" ? "Brand Search Map" : "Search Product Map"}
                  disabled={geoLens === "brand" ? searchDataMapLoading : productMapLoading}
                />
              </div>
            </div>

            {geoLens === "brand" ? (
              searchDataMapLoading ? (
                <div className="h-[560px] animate-pulse rounded-2xl bg-[var(--card-bg-2)]" />
              ) : searchDataMapData.length === 0 ? (
                <div className="flex h-[420px] items-center justify-center text-sm text-[var(--muted-tx)]">
                  No brand search map available
                </div>
              ) : (
                <SearchProductUaeMap data={searchDataMapData} />
              )
            ) : productMapLoading ? (
              <div className="h-[560px] animate-pulse rounded-2xl bg-[var(--card-bg-2)]" />
            ) : productMapData.length === 0 ? (
              <div className="flex h-[420px] items-center justify-center text-sm text-[var(--muted-tx)]">
                No product map data available
              </div>
            ) : (
              <SearchProductUaeMap data={productMapData} />
            )}
          </section>
        )}
      </main>
    </div>
  );
}
