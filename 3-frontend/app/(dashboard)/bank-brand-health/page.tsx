"use client";

import { useEffect, useMemo, useRef, useState } from "react";
import DashboardTopbar from "@/components/layout/DashboardTopbar";
import TopDigitalHealthBarChart from "@/components/bankBrandHealth/TopDigitalHealthBarChart";
import TrendLineChartCard, {
  type TrendFrequency,
  type TrendLine,
  type TrendRow,
} from "@/components/bankBrandHealth/TrendLineChartCard";
import ExportExcelButton from "@/components/ui/ExportExcelButton";
import { Award, BarChart3, TrendingUp } from "lucide-react";
import {
  getBrandIQSnapshot,
  getBrandIQTrend,
  type BrandIQSegment,
  type TopDigitalHealthItem,
} from "@/lib/bankBrandHealth";
import { getBankColor } from "@/lib/bankColors";

function formatBankName(bank: string) {
  return bank
    .replace(/_/g, " ")
    .replace(/\b\w/g, (letter) => letter.toUpperCase());
}

const TREND_PERIOD_KEYS = ["period", "date", "month"];
const MAX_SELECTED_TREND_BANKS = 5;

function pickStringValue(row: Record<string, unknown>, keys: string[], fallback = "") {
  for (const key of keys) {
    const value = row[key];
    if (typeof value === "string" && value.trim()) return value.trim();
    if (typeof value === "number" && Number.isFinite(value)) return String(value);
  }

  return fallback;
}

function pickNumberValue(row: Record<string, unknown>, keys: string[]): number | null {
  for (const key of keys) {
    const value = row[key];
    if (typeof value === "number" && Number.isFinite(value)) return value;
    if (typeof value === "string" && value.trim() && Number.isFinite(Number(value))) {
      return Number(value);
    }
  }

  return null;
}

const TREND_BANK_KEYS = ["bank", "name", "brand"];
const TREND_SCORE_KEYS = ["avg_score", "digital_equity_score", "score", "value"];

function formatSnapshotCell(value: number | null, decimals = 2, suffix = "") {
  return value === null ? "—" : `${value.toFixed(decimals)}${suffix}`;
}

function averageValues(values: (number | null)[]): number | null {
  const present = values.filter((value): value is number => value !== null);
  return present.length > 0 ? present.reduce((sum, value) => sum + value, 0) / present.length : null;
}

export default function BankBrandHealthPage() {
  const [segment, setSegment] = useState<BrandIQSegment>("normal");
  const [topDigitalHealth, setTopDigitalHealth] = useState<TopDigitalHealthItem[]>([]);
  const [loading, setLoading] = useState(true);

  const [trendBankOptions, setTrendBankOptions] = useState<string[]>([]);
  const [selectedTrendBanks, setSelectedTrendBanks] = useState<string[]>([]);
  const [trendFrequency, setTrendFrequency] = useState<TrendFrequency>("3m");
  const [equityTrend, setEquityTrend] = useState<Record<string, unknown>[]>([]);
  const [banksTrend, setBanksTrend] = useState<Record<string, unknown>[]>([]);
  const [equityTrendLoading, setEquityTrendLoading] = useState(true);
  const [banksTrendLoading, setBanksTrendLoading] = useState(true);
  const defaultTrendBanksSyncedRef = useRef(false);

  useEffect(() => {
    let active = true;

    getBrandIQSnapshot(segment)
      .then((res) => {
        if (!active) return;
        const items = res.snapshot ?? [];
        setTopDigitalHealth(items);
        setTrendBankOptions(items.map((item) => item.bank));
        defaultTrendBanksSyncedRef.current = false;
        setSelectedTrendBanks(items.slice(0, MAX_SELECTED_TREND_BANKS).map((item) => item.bank));

        if (!defaultTrendBanksSyncedRef.current) {
          const defaults = items.slice(0, MAX_SELECTED_TREND_BANKS).map((item) => item.bank);

          if (defaults.length > 0) {
            defaultTrendBanksSyncedRef.current = true;
            setSelectedTrendBanks(defaults);
            setBanksTrendLoading(true);
          }
        }
      })
      .catch(() => {
        if (!active) return;
        setTopDigitalHealth([]);
      })
      .finally(() => {
        if (active) setLoading(false);
      });

    return () => {
      active = false;
    };
  }, [segment]);

  useEffect(() => {
    let active = true;

    getBrandIQTrend(segment, selectedTrendBanks)
      .then((res) => {
        if (!active) return;
        const rows = res.trend ?? [];
        setEquityTrend(rows.filter((row) => row.bank === "Average"));
        setBanksTrend(rows.filter((row) => row.bank !== "Average"));
      })
      .catch(() => {
        if (!active) return;
        setEquityTrend([]);
      })
      .finally(() => {
        if (active) {
          setEquityTrendLoading(false);
          setBanksTrendLoading(false);
        }
      });

    return () => {
      active = false;
    };
  }, [segment, trendFrequency, selectedTrendBanks]);

  const handleTrendFrequencyChange = (frequency: TrendFrequency) => {
    if (frequency === trendFrequency) return;

    setEquityTrendLoading(true);
    setBanksTrendLoading(true);
    setTrendFrequency(frequency);
  };

  const handleTrendBankToggle = (bank: string) => {
    setSelectedTrendBanks((current) => {
      if (current.includes(bank)) {
        if (current.length === 1) return current;
        setBanksTrendLoading(true);
        return current.filter((item) => item !== bank);
      }

      if (current.length >= MAX_SELECTED_TREND_BANKS) return current;

      setBanksTrendLoading(true);
      return [...current, bank];
    });
  };

  const trendRows = useMemo<TrendRow[]>(() => {
    const merged = new Map<string, TrendRow>();

    equityTrend.forEach((row) => {
      const period = pickStringValue(row, TREND_PERIOD_KEYS);
      if (!period) return;

      const value = pickNumberValue(row, [...TREND_SCORE_KEYS, "average"]);
      if (value === null) return;

      const existing = merged.get(period) ?? { date: period };
      existing.average = Number(value.toFixed(2));
      merged.set(period, existing);
    });

    banksTrend.forEach((row) => {
      const period = pickStringValue(row, TREND_PERIOD_KEYS);
      const bank = pickStringValue(row, TREND_BANK_KEYS);
      const value = pickNumberValue(row, TREND_SCORE_KEYS);
      if (!period || !bank || value === null) return;

      const existing = merged.get(period) ?? { date: period };
      existing[bank] = Number(value.toFixed(2));
      merged.set(period, existing);
    });

    return Array.from(merged.values()).sort((a, b) =>
      String(a.date).localeCompare(String(b.date))
    );
  }, [equityTrend, banksTrend]);

  const trendLines = useMemo<TrendLine[]>(() => {
    const bankLines = selectedTrendBanks.map((bank, index) => ({
      key: bank,
      label: formatBankName(bank),
      color: getBankColor(formatBankName(bank), index),
    }));

    return [
      ...bankLines,
      { key: "average", label: "Average", color: "#f59e0b", dashed: true },
    ];
  }, [selectedTrendBanks]);

  const chartData = useMemo(
    () =>
      topDigitalHealth.map((item) => ({
        name: formatBankName(item.bank),
        value: Number(item.avg_score.toFixed(2)),
      })),
    [topDigitalHealth]
  );

  const summary = useMemo(() => {
    const topBrand = topDigitalHealth[0];
    const average =
      topDigitalHealth.length > 0
        ? topDigitalHealth.reduce((sum, item) => sum + item.avg_score, 0) / topDigitalHealth.length
        : null;

    return {
      topBrand: topBrand ? formatBankName(topBrand.bank) : "-",
      highestScore: topBrand ? topBrand.avg_score.toFixed(1) : "-",
      averageIndex: average === null ? "-" : average.toFixed(1),
    };
  }, [topDigitalHealth]);

  const snapshotRows = useMemo(
    () => topDigitalHealth.map((item) => ({
      bank: formatBankName(item.bank),
      brandiqIndex: item.avg_score,
      aiScore: item.ai_score ?? null,
      shareOfSearch: item.share_of_search_pct ?? null,
      rating: item.rating ?? null,
      reviewVolume: item.review_volume ?? null,
      socialSov: item.social_sov_pct ?? null,
      engagement: item.engagement ?? null,
    })),
    [topDigitalHealth]
  );

  const snapshotAverages = useMemo(
    () => ({
      brandiqIndex: averageValues(snapshotRows.map((row) => row.brandiqIndex)),
      aiScore: averageValues(snapshotRows.map((row) => row.aiScore)),
      shareOfSearch: averageValues(snapshotRows.map((row) => row.shareOfSearch)),
      rating: averageValues(snapshotRows.map((row) => row.rating)),
      reviewVolume: averageValues(snapshotRows.map((row) => row.reviewVolume)),
      socialSov: averageValues(snapshotRows.map((row) => row.socialSov)),
      engagement: averageValues(snapshotRows.map((row) => row.engagement)),
    }),
    [snapshotRows]
  );

  return (
    <div className="min-h-screen">
      <DashboardTopbar title="BrandIQ" />

      <main className="p-8">
        <div
          role="tablist"
          aria-label="Bank group"
          className="mb-6 inline-flex rounded-full border border-[var(--card-bd)] bg-[var(--card-bg)] p-1 shadow-sm"
        >
            {(["normal", "digital"] as BrandIQSegment[]).map((option) => (
              <button
                key={option}
                type="button"
                role="tab"
                aria-selected={segment === option}
                onClick={() => {
                  if (option !== segment) {
                    setLoading(true);
                    setSegment(option);
                  }
                }}
                className="flex h-10 items-center rounded-full px-5 text-sm font-semibold transition"
                style={{
                  background: segment === option ? "#2563eb" : "transparent",
                  color: segment === option ? "#ffffff" : "var(--muted-tx)",
                }}
              >
                {option === "normal" ? "All Banks" : "Digital Banks"}
              </button>
            ))}
        </div>
        <section className="mb-6 overflow-hidden rounded-2xl bg-gradient-to-r from-[#4242b7] via-[#757fe0] to-[#b51f91] p-6 text-white shadow-lg">
          <div className="grid gap-5 lg:grid-cols-[1.35fr_1fr_1fr_1fr]">
            <div className="flex flex-col justify-center">
              <h1 className="text-2xl font-bold">BrandIQ Overview</h1>
              <p className="mt-3 max-w-md text-sm leading-6 text-white/90">
                Brings together all insights into a single composite score, representing
                the brand&apos;s overall strength across the digital ecosystem.
              </p>
            </div>

            <div className="rounded-lg bg-white/18 px-6 py-4 text-center shadow-sm backdrop-blur-md">
              <div className="mx-auto mb-3 flex h-9 w-9 items-center justify-center rounded-xl bg-gradient-to-br from-amber-400 to-orange-600">
                <Award className="h-5 w-5" />
              </div>
              <p className="text-xl font-bold">{summary.topBrand}</p>
              <p className="mt-1 text-sm text-white/85">Top Performing Brand</p>
            </div>

            <div className="rounded-lg bg-white/18 px-6 py-4 text-center shadow-sm backdrop-blur-md">
              <div className="mx-auto mb-3 flex h-9 w-9 items-center justify-center rounded-xl bg-emerald-500">
                <TrendingUp className="h-5 w-5" />
              </div>
              <p className="text-2xl font-bold">{summary.highestScore}</p>
              <p className="mt-1 text-sm text-white/85">Highest BrandIQ Index Score</p>
            </div>

            <div className="rounded-lg bg-white/18 px-6 py-4 text-center shadow-sm backdrop-blur-md">
              <div className="mx-auto mb-3 flex h-9 w-9 items-center justify-center rounded-xl bg-sky-500">
                <BarChart3 className="h-5 w-5" />
              </div>
              <p className="text-2xl font-bold">{summary.averageIndex}</p>
              <p className="mt-1 text-sm text-white/85">Average BrandIQ Index</p>
            </div>
          </div>
        </section>

        <section className="rounded-2xl border border-[var(--card-bd)] bg-[var(--card-bg-2)] p-6 shadow-lg">
          <div className="flex flex-col gap-3 sm:flex-row sm:items-start sm:justify-between">
            <div>
              <h2 className="text-lg font-semibold text-[var(--title-tx)]">
                Top BrandIQ Index <span className="text-xs text-[var(--muted-tx)]">(Ranking)</span>
              </h2>
              <p className="mt-2 text-sm text-[var(--muted-tx)]">
                Average BrandIQ Index score by bank.
              </p>
            </div>
            <ExportExcelButton
              rows={chartData}
              filename="top_brandiq_index"
              sheetName="Top BrandIQ Index"
              disabled={loading}
            />
          </div>

          <div className="mt-5">
            <TopDigitalHealthBarChart data={chartData} loading={loading} />
          </div>
        </section>

        <div className="mt-6">
          <TrendLineChartCard
            title="Digital Index Trend by Brand"
            description="Compare brand performance over time (select up to 5 brands)"
            data={trendRows}
            lines={trendLines}
            loading={equityTrendLoading || banksTrendLoading}
            bankOptions={trendBankOptions}
            selectedBanks={selectedTrendBanks}
            onBankToggle={handleTrendBankToggle}
            maxSelectedBanks={MAX_SELECTED_TREND_BANKS}
            frequency={trendFrequency}
            onFrequencyChange={handleTrendFrequencyChange}
          />
        </div>

        <section className="mt-6 rounded-2xl border border-[var(--card-bd)] bg-[var(--card-bg-2)] p-6 shadow-lg">
          <div className="flex flex-col gap-3 sm:flex-row sm:items-start sm:justify-between">
            <div>
              <h2 className="text-lg font-semibold text-[var(--title-tx)]">
                BrandIQ Snapshot
              </h2>
              <p className="mt-2 text-sm text-[var(--muted-tx)]">
                Highlight key metrics for each bank
              </p>
            </div>
            <ExportExcelButton
              rows={snapshotRows}
              filename="digital_ecosystem_snapshot"
              sheetName="Digital Ecosystem Snapshot"
              disabled={loading}
            />
          </div>

          {loading ? (
            <div className="mt-5 h-[320px] animate-pulse rounded-2xl bg-[var(--card-bg)]" />
          ) : snapshotRows.length === 0 ? (
            <div className="mt-5 flex h-[200px] items-center justify-center rounded-2xl border border-[var(--card-bd)] bg-[var(--card-bg)] text-sm text-[var(--muted-tx)]">
              No snapshot data available
            </div>
          ) : (
            <div className="mt-5 overflow-x-auto rounded-2xl border border-[var(--card-bd)]">
              <table className="w-full min-w-[900px] border-collapse text-sm">
                <thead>
                  <tr style={{ background: "#0f1b3d", color: "#ffffff" }}>
                    <th className="px-4 py-3 text-left font-semibold">Bank</th>
                    <th className="px-4 py-3 text-left font-semibold">BrandIQ Index</th>
                    <th className="px-4 py-3 text-left font-semibold">AI Score</th>
                    <th className="px-4 py-3 text-left font-semibold">Share of Search</th>
                    <th className="px-4 py-3 text-left font-semibold">Rating</th>
                    <th className="px-4 py-3 text-left font-semibold">Review volume</th>
                    <th className="px-4 py-3 text-left font-semibold">Social SoV</th>
                    <th className="px-4 py-3 text-left font-semibold">Engagement</th>
                  </tr>
                </thead>
                <tbody>
                  {snapshotRows.map((row, index) => (
                    <tr
                      key={row.bank}
                      className="border-t border-[var(--card-bd)]"
                      style={{
                        background: index % 2 === 0 ? "var(--card-bg-2)" : "var(--card-bg)",
                      }}
                    >
                      <td className="px-4 py-3 font-semibold text-[var(--title-tx)]">{row.bank}</td>
                      <td className="px-4 py-3 text-[var(--title-tx)]">
                        {formatSnapshotCell(row.brandiqIndex, 1)}
                      </td>
                      <td className="px-4 py-3 text-[var(--title-tx)]">
                        {formatSnapshotCell(row.aiScore, 2)}
                      </td>
                      <td className="px-4 py-3 text-[var(--title-tx)]">
                        {formatSnapshotCell(row.shareOfSearch, 1, "%")}
                      </td>
                      <td className="px-4 py-3 text-[var(--title-tx)]">
                        {formatSnapshotCell(row.rating, 2)}
                      </td>
                      <td className="px-4 py-3 text-[var(--title-tx)]">
                        {row.reviewVolume === null ? "—" : Math.round(row.reviewVolume)}
                      </td>
                      <td className="px-4 py-3 text-[var(--title-tx)]">
                        {formatSnapshotCell(row.socialSov, 1, "%")}
                      </td>
                      <td className="px-4 py-3 text-[var(--title-tx)]">
                        {formatSnapshotCell(row.engagement, 2)}
                      </td>
                    </tr>
                  ))}

                  <tr
                    className="border-t border-[var(--card-bd)] font-semibold"
                    style={{ background: "var(--card-bg)" }}
                  >
                    <td className="px-4 py-3 text-[var(--title-tx)]">Category avg.</td>
                    <td className="px-4 py-3 text-[var(--title-tx)]">
                      {formatSnapshotCell(snapshotAverages.brandiqIndex, 1)}
                    </td>
                    <td className="px-4 py-3 text-[var(--title-tx)]">
                      {formatSnapshotCell(snapshotAverages.aiScore, 2)}
                    </td>
                    <td className="px-4 py-3 text-[var(--title-tx)]">
                      {formatSnapshotCell(snapshotAverages.shareOfSearch, 1, "%")}
                    </td>
                    <td className="px-4 py-3 text-[var(--title-tx)]">
                      {formatSnapshotCell(snapshotAverages.rating, 2)}
                    </td>
                    <td className="px-4 py-3 text-[var(--title-tx)]">
                      {snapshotAverages.reviewVolume === null
                        ? "—"
                        : Math.round(snapshotAverages.reviewVolume)}
                    </td>
                    <td className="px-4 py-3 text-[var(--title-tx)]">
                      {formatSnapshotCell(snapshotAverages.socialSov, 1, "%")}
                    </td>
                    <td className="px-4 py-3 text-[var(--title-tx)]">
                      {formatSnapshotCell(snapshotAverages.engagement, 2)}
                    </td>
                  </tr>
                </tbody>
              </table>
            </div>
          )}
        </section>
      </main>
    </div>
  );
}
