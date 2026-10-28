"use client";

import { Suspense, useCallback, useEffect, useState } from "react";
import Link from "next/link";
import { motion, MotionConfig } from "framer-motion";
import {
  Activity, Eye, Zap, Flame, Users, Building2, Search, Bell,
  CalendarDays, Layers, ArrowUpRight,
} from "lucide-react";

import DashboardTopbar from "@/components/layout/DashboardTopbar";
import {
  CardGridSkeleton, InlineError, LoadingAnnouncer, Skel,
} from "@/components/ui/RealEstateTrendsPanels";
import MarketSelect, { useMarket } from "@/components/ui/MarketSelect";
import {
  QUADRANT_META, QUADRANT_ORDER, KPI_TOKEN, graphic, text, soft, softBorder,
} from "@/lib/realEstateTrendsPalette";
import {
  fetchTrendsOverview, friendlyTrendError, isAbort,
  type Period, type Quadrant, type TrendsOverview,
} from "@/lib/realEstateTrends";

const KPI_ICONS: Record<string, React.ElementType> = {
  trends: Activity, watchlist: Eye, breakthrough: Zap, slow: Flame,
  mainstream: Users, brands: Building2,
};

/* ─── topbar accessory ───────────────────────────────────────────────── */
function OverviewSearch() {
  return (
    <div className="hidden items-center gap-2 md:flex">
      <div className="relative">
        <Search size={14} className="pointer-events-none absolute left-3 top-1/2 -translate-y-1/2" style={{ color: "var(--muted-tx)" }} />
        <input
          disabled
          aria-hidden="true"
          tabIndex={-1}
          placeholder="Search trends, brands, personas"
          style={{ background: "var(--card-bg)", border: "1px solid var(--card-bd)", color: "var(--title-tx)", backdropFilter: "var(--blur)" }}
          className="w-64 cursor-not-allowed rounded-full py-2 pl-9 pr-4 text-sm opacity-60 placeholder:text-[var(--muted-tx)]"
        />
      </div>
      <button
        type="button"
        disabled
        aria-label="Notifications"
        title="Notifications (preview)"
        style={{ background: "var(--card-bg)", border: "1px solid var(--card-bd)", color: "var(--muted-tx)" }}
        className="flex h-10 w-10 cursor-not-allowed items-center justify-center rounded-full opacity-60"
      >
        <Bell size={16} aria-hidden="true" />
      </button>
    </div>
  );
}

/* ─── period toggle (live) ───────────────────────────────────────────── */
const MONTH_NAMES = ["January", "February", "March", "April", "May", "June",
  "July", "August", "September", "October", "November", "December"];

/* Parsed by hand, not through Date: new Date("2026-08-01") is UTC midnight and
   renders as July in any timezone behind UTC. */
function monthLabel(month: string | null, asOf: string | null): string {
  const src = month ?? asOf;
  if (!src) return "latest";
  const [year, mon] = src.split("-");
  const name = MONTH_NAMES[Number(mon) - 1];
  return name ? `${name} ${year}` : src;
}

function PeriodToggle({ period, asOf, periodMonth, loading, onChange }: {
  period: Period; asOf: string | null; periodMonth: string | null;
  loading: boolean; onChange: (p: Period) => void;
}) {
  const base = "inline-flex min-h-11 items-center gap-1.5 rounded-full px-3.5 py-1.5 text-xs font-semibold transition-colors";
  const on = { background: "var(--fi-solid)", color: "var(--fi-solid-tx)" };
  const off = { color: "var(--muted-tx)" };
  return (
    <div className="inline-flex items-center gap-1 rounded-full p-1" style={{ background: "var(--card-bg-2)", border: "1px solid var(--card-bd)" }}>
      <button onClick={() => onChange("month")} className={base} aria-pressed={period === "month"}
        style={period === "month" ? on : off}>
        <CalendarDays size={13} aria-hidden="true" /> This month{" "}
        <span className="opacity-70">
          · {loading ? <Skel className="inline-block h-3 w-20 align-middle" /> : monthLabel(periodMonth, asOf)}
        </span>
      </button>
      <button onClick={() => onChange("cumulative")} className={base} aria-pressed={period === "cumulative"}
        style={period === "cumulative" ? on : off}>
        <Layers size={13} aria-hidden="true" /> Cumulative <span className="opacity-70">· all history</span>
      </button>
    </div>
  );
}

/* ─── KPI tile ────────────────────────────────────────────────────────── */
function KpiTile({ label, value, delta, kpiKey, i }: {
  label: string; value: number; delta: number | null; kpiKey: string; i: number;
}) {
  const Icon = KPI_ICONS[kpiKey] ?? Activity;
  const token = KPI_TOKEN[kpiKey] ?? "watchlist";
  const deltaText = delta === null || delta === undefined ? null : delta > 0 ? `+${delta}` : `${delta}`;
  return (
    <motion.div
      initial={{ opacity: 0, y: 12 }}
      animate={{ opacity: 1, y: 0 }}
      transition={{ duration: 0.45, delay: i * 0.045, ease: [0.16, 1, 0.3, 1] }}
      className="chart-card rounded-2xl p-5"
    >
      <div className="mb-4 flex items-start justify-between">
        <span className="flex h-9 w-9 items-center justify-center rounded-xl"
          style={{ background: soft(token), color: text(token) }}>
          <Icon size={16} aria-hidden="true" />
        </span>
        {deltaText && (
          <span className="text-xs font-bold tabular-nums"
            style={{ color: (delta ?? 0) > 0 ? "var(--fi-growth-tx)" : "var(--muted-tx)" }}>
            {deltaText}
          </span>
        )}
      </div>
      <div style={{ color: "var(--muted-tx)" }} className="text-xs font-medium">{label}</div>
      <div style={{ color: "var(--title-tx)" }} className="mt-1 text-3xl font-bold tracking-tight tabular-nums">{value}</div>
    </motion.div>
  );
}

const KPI_GRID = "grid grid-cols-2 gap-4 md:grid-cols-3 xl:grid-cols-6";

function KpiRowSkeleton() {
  return (
    <div className={KPI_GRID} aria-hidden="true">
      {Array.from({ length: 6 }).map((_, i) => (
        <div key={i} className="chart-card rounded-2xl p-5">
          <Skel className="h-9 w-9 rounded-xl" />
          <Skel className="mt-4 h-3 w-3/4" />
          <Skel className="mt-2 h-7 w-1/2" />
        </div>
      ))}
    </div>
  );
}

/* ─── Opportunity Map (2×2 quadrant cards) ───────────────────────────── */
function QuadrantCard({ q, trends }: { q: Quadrant; trends: { id: string; name: string }[] }) {
  const meta = QUADRANT_META[q];
  return (
    <div
      className="rounded-xl p-4"
      style={{ background: soft(meta.token), border: `1px solid ${softBorder(meta.token)}` }}
    >
      <div className="mb-3 flex items-start justify-between">
        <div>
          <div className="flex items-center gap-2">
            <span className="h-2.5 w-2.5 rounded-full" style={{ background: graphic(meta.token) }} aria-hidden="true" />
            <h4 style={{ color: "var(--title-tx)" }} className="text-sm font-bold">{meta.label}</h4>
          </div>
          <p style={{ color: "var(--muted-tx)" }} className="mt-0.5 text-xs">{meta.volGrowth}</p>
        </div>
        <span
          className="flex h-6 min-w-6 items-center justify-center rounded-lg px-1.5 text-xs font-bold tabular-nums"
          style={{ background: "var(--card-bg)", border: "1px solid var(--card-bd)", color: "var(--body-tx)" }}
        >
          {trends.length}
        </span>
      </div>
      <div className="flex flex-wrap gap-1.5">
        {trends.slice(0, 12).map((t) => (
          <span
            key={t.id}
            className="rounded-full px-2.5 py-1 text-xs font-medium"
            style={{ background: "var(--card-bg)", border: "1px solid var(--card-bd)", color: "var(--body-tx)" }}
          >
            {t.name}
          </span>
        ))}
        {trends.length > 12 && (
          <span className="rounded-full px-2.5 py-1 text-xs" style={{ color: "var(--muted-tx)" }}>
            +{trends.length - 12} more
          </span>
        )}
      </div>
    </div>
  );
}

function OpportunityMap({ overview }: { overview: TrendsOverview }) {
  const byQuadrant = Object.fromEntries(overview.quadrants.map((q) => [q.quadrant, q.trends]));
  return (
    <div className="chart-card rounded-2xl p-6">
      <div className="mb-5 flex flex-wrap items-start justify-between gap-3">
        <div>
          <h3 style={{ color: "var(--title-tx)" }} className="text-xl font-bold tracking-tight">Property Trend Opportunity Matrix</h3>
          <p style={{ color: "var(--muted-tx)" }} className="mt-1 max-w-xl text-sm">
            Every tracked trend mapped by conversation volume and growth momentum across the GCC property market.
          </p>
        </div>
        <span
          className="inline-flex shrink-0 items-center gap-1.5 rounded-full px-3 py-1 text-xs font-semibold"
          style={{ background: "var(--fi-growth-soft)", color: "var(--fi-growth-tx)", border: "1px solid var(--fi-growth-soft-bd)" }}
        >
          <span className="h-1.5 w-1.5 rounded-full" style={{ background: "var(--fi-growth)" }} aria-hidden="true" />
          {overview.as_of ? `data to ${overview.as_of}` : "latest run"}
        </span>
      </div>

      <div className="grid grid-cols-1 gap-4 lg:grid-cols-2">
        {QUADRANT_ORDER.map((q) => <QuadrantCard key={q} q={q} trends={byQuadrant[q] ?? []} />)}
      </div>

      <div className="mt-4 flex flex-wrap items-center justify-between gap-2 text-xs" style={{ color: "var(--muted-tx)" }}>
        <span>← Lower volume · Higher volume →</span>
        <span>↑ Higher growth · Lower growth ↓</span>
      </div>
    </div>
  );
}

/* ─── Emerging Trends ─────────────────────────────────────────────────── */
function EmergingCard({ t }: { t: TrendsOverview["emerging"][number] }) {
  const meta = QUADRANT_META[t.quadrant];
  return (
    <div className="chart-card flex flex-col rounded-2xl p-5">
      <div className="mb-2 flex items-start justify-between gap-3">
        <h4 style={{ color: "var(--title-tx)" }} className="text-sm font-bold">{t.name}</h4>
        <span
          className="shrink-0 rounded-full px-2.5 py-0.5 text-xs font-semibold"
          style={{ background: soft(meta.token), color: text(meta.token), border: `1px solid ${softBorder(meta.token)}` }}
        >
          {meta.label}
        </span>
      </div>
      <p style={{ color: "var(--body-tx)" }} className="mb-4 flex-1 text-sm leading-relaxed">{t.summary}</p>
      <div className="flex items-center gap-1.5 text-sm font-bold" style={{ color: "var(--fi-growth-tx)" }}>
        <ArrowUpRight size={15} aria-hidden="true" /> {t.growth}{" "}
        <span style={{ color: "var(--muted-tx)" }} className="font-normal">growth index</span>
      </div>
    </div>
  );
}

/* ─── Biggest Movers ──────────────────────────────────────────────────── */
function BiggestMovers({ movers }: { movers: TrendsOverview["movers"] }) {
  if (!movers.length) {
    return (
      <div className="chart-card rounded-2xl p-5 text-sm" style={{ color: "var(--muted-tx)" }}>
        Movers compare growth against the previous pipeline run — they appear once
        two runs share trends.
      </div>
    );
  }
  const max = Math.max(...movers.map((m) => m.pts));
  return (
    <div className="chart-card rounded-2xl p-5">
      <div className="space-y-4">
        {movers.map((m) => (
          <div key={m.rank} className="flex items-center gap-3">
            <span
              className="flex h-7 w-7 shrink-0 items-center justify-center rounded-full text-xs font-bold tabular-nums"
              style={{ background: "var(--card-bg-2)", border: "1px solid var(--card-bd)", color: "var(--body-tx)" }}
            >
              {m.rank}
            </span>
            <div className="min-w-0 flex-1">
              <div style={{ color: "var(--title-tx)" }} className="mb-1.5 truncate text-sm font-medium">{m.name}</div>
              <div className="h-1.5 w-full overflow-hidden rounded-full" style={{ background: "var(--card-bg-2)" }}>
                <div className="h-full rounded-full" style={{ width: `${(m.pts / max) * 100}%`, background: "var(--fi-growth)" }} />
              </div>
            </div>
            <span style={{ color: "var(--muted-tx)" }} className="shrink-0 text-xs font-semibold tabular-nums">+{m.pts} pts</span>
          </div>
        ))}
      </div>
    </div>
  );
}

/* ─── page ────────────────────────────────────────────────────────────── */
function OverviewContent() {
  const [period, setPeriod] = useState<Period>("month");
  const [market, setMarket] = useMarket();
  const [reloadKey, setReloadKey] = useState(0);
  // The request key travels with the result. A response is rendered only when
  // its key still matches the current one, so switching period shows the
  // spinner without an effect having to clear state first - and a slow reply
  // for the previous period cannot overwrite the newer one on arrival.
  const requestKey = `${period}|${market ?? ""}|${reloadKey}`;
  const [result, setResult] = useState<{
    key: string; data: TrendsOverview | null; error: string | null;
  }>({ key: "", data: null, error: null });

  useEffect(() => {
    const ac = new AbortController();
    fetchTrendsOverview(period, ac.signal, market)
      .then((d) => setResult({ key: requestKey, data: d, error: null }))
      .catch((e) => {
        if (!isAbort(e)) setResult({ key: requestKey, data: null, error: friendlyTrendError(e) });
      });
    return () => ac.abort();
  }, [period, market, requestKey]);

  const retry = useCallback(() => setReloadKey((k) => k + 1), []);

  const fresh = result.key === requestKey;
  const overview = fresh ? result.data : null;
  const error = fresh ? result.error : null;
  const loading = overview === null && error === null;
  const emptyMonth = overview !== null && period === "month"
    && (overview.kpis.find((k) => k.key === "trends")?.value ?? 0) === 0;

  return (
    <MotionConfig reducedMotion="user">
      <div className="w-full">
        <DashboardTopbar title="Real Estate Intelligence Overview" accessory={<OverviewSearch />} />

        <div className="mx-auto max-w-[1500px] space-y-6 p-6 sm:p-8">
          <div className="flex flex-col gap-4 sm:flex-row sm:items-end sm:justify-between">
            <div>
              <h2 style={{ color: "var(--title-tx)" }} className="text-xl font-bold tracking-tight">Overview</h2>
              <p style={{ color: "var(--muted-tx)" }} className="mt-0.5 text-sm">
                {period === "month" ? "Signals captured this month" : "Signals across the full history"}
              </p>
            </div>
            <div className="flex flex-wrap items-center gap-2">
              <MarketSelect market={market} onChange={setMarket} />
              <PeriodToggle period={period} asOf={overview?.as_of ?? null} loading={loading}
                periodMonth={overview?.period_month ?? null} onChange={setPeriod} />
            </div>
          </div>

          {error ? (
            <InlineError message={error} onRetry={retry} />
          ) : loading ? (
            <>
              <LoadingAnnouncer label="Loading overview" />
              <KpiRowSkeleton />
              <div className="chart-card rounded-2xl p-6">
                <Skel className="h-6 w-72" />
                <Skel className="mt-2 h-4 w-full max-w-xl" />
                <div className="mt-5 grid grid-cols-1 gap-4 lg:grid-cols-2">
                  {Array.from({ length: 4 }).map((_, i) => (
                    <Skel key={i} className="h-36 rounded-xl" />
                  ))}
                </div>
              </div>
              <div className="grid grid-cols-1 gap-6 lg:grid-cols-3">
                <div className="lg:col-span-2">
                  <CardGridSkeleton count={4} className="grid grid-cols-1 gap-4 md:grid-cols-2" height={180} />
                </div>
                <Skel className="h-64 rounded-2xl" />
              </div>
            </>
          ) : emptyMonth ? (
            <div className="chart-card flex flex-col items-center justify-center gap-3 rounded-2xl py-20 text-center">
              <CalendarDays size={22} style={{ color: "var(--muted-tx)", opacity: 0.6 }} aria-hidden="true" />
              <p style={{ color: "var(--title-tx)" }} className="text-sm font-semibold">
                No posts collected in {monthLabel(overview.period_month, null)}
              </p>
              <p style={{ color: "var(--muted-tx)" }} className="max-w-md text-xs leading-relaxed">
                {overview.as_of
                  ? `The most recent post in the data is from ${overview.as_of}.`
                  : "There is no data for this month yet."}
              </p>
              <button
                onClick={() => setPeriod("cumulative")}
                className="mt-1 min-h-11 rounded-full px-4 py-1.5 text-xs font-semibold"
                style={{ background: "var(--fi-solid)", color: "var(--fi-solid-tx)" }}
              >
                View cumulative instead
              </button>
            </div>
          ) : overview && (
            <>
              <div className={KPI_GRID}>
                {overview.kpis.map((k, i) => (
                  <KpiTile key={k.key} label={k.label} value={k.value} delta={k.delta} kpiKey={k.key} i={i} />
                ))}
              </div>

              <OpportunityMap overview={overview} />

              <div className="grid grid-cols-1 gap-6 lg:grid-cols-3">
                <div className="space-y-4 lg:col-span-2">
                  <div className="flex items-center justify-between">
                    <h3 style={{ color: "var(--title-tx)" }} className="text-base font-bold">Top Emerging Trends</h3>
                    <Link href={market ? `/trends-real-estate/trends-explorer?market=${market}` : "/trends-real-estate/trends-explorer"}
                      className="inline-flex items-center gap-1 rounded text-xs font-semibold hover:underline"
                      style={{ color: "var(--fi-growth-tx)" }}>
                      View all <ArrowUpRight size={13} aria-hidden="true" />
                    </Link>
                  </div>
                  <div className="grid grid-cols-1 gap-4 md:grid-cols-2">
                    {overview.emerging.map((t) => <EmergingCard key={t.id} t={t} />)}
                  </div>
                </div>

                <div className="space-y-4">
                  <h3 style={{ color: "var(--title-tx)" }} className="text-base font-bold">Biggest Movers</h3>
                  <BiggestMovers movers={overview.movers} />
                </div>
              </div>
            </>
          )}
        </div>
      </div>
    </MotionConfig>
  );
}

/* The market is read from the URL (?market=), which needs a Suspense boundary
   for the page to prerender - the same arrangement Trends Explorer uses. */
export default function TrendsRealEstateOverviewPage() {
  return (
    <Suspense fallback={
      <div className="w-full">
        <DashboardTopbar title="Real Estate Intelligence Overview" accessory={<OverviewSearch />} />
        <div className="mx-auto max-w-[1500px] space-y-6 p-6 sm:p-8">
          <KpiRowSkeleton />
          <Skel className="h-72 rounded-2xl" />
        </div>
      </div>
    }>
      <OverviewContent />
    </Suspense>
  );
}
