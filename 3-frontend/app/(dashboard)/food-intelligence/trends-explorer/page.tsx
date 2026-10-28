"use client";

import {
  Suspense, useCallback, useEffect, useMemo, useRef, useState, useSyncExternalStore,
} from "react";
import { usePathname, useRouter, useSearchParams } from "next/navigation";
import { motion, MotionConfig } from "framer-motion";
import {
  ResponsiveContainer, AreaChart, Area, XAxis, YAxis, CartesianGrid, Tooltip as RTooltip,
  PieChart, Pie, Cell,
} from "recharts";
import {
  ArrowLeft, ArrowUpRight, ArrowDownRight, MessageCircle, Heart, Eye, Check,
  TrendingUp, CalendarDays, ChevronDown, ChevronLeft, ChevronRight,
} from "lucide-react";

import DashboardTopbar from "@/components/layout/DashboardTopbar";
import {
  TopbarSearch, radarTickFill, chartGridStroke,
  CardGridSkeleton, InlineError, LoadingAnnouncer, Skel,
} from "@/components/ui/FoodPanels";
import MarketSelect, { useMarket } from "@/components/ui/MarketSelect";
import {
  QUADRANT_META, TREND_JOURNEY, SOURCE_META, CHART_SERIES,
  graphic, text, soft, softBorder, type TokenFamily,
} from "@/lib/foodPalette";
import {
  fetchTrends, fetchTrendDetail, friendlyTrendError, isAbort, MARKETS,
  type Period, type Quadrant, type TrendListItem, type TrendDetail as TrendDetailData,
  type ExamplePost, type Source, type Market,
} from "@/lib/foodTrends";

/** Which cohorts get an Example Content column on the trend detail.
 *
 *  Consumer posts are held back for now - the detail shows tracked brand and
 *  influencer accounts only. Put "community" back in this list to restore the
 *  column; the heading, the empty note and the grid width all read from here,
 *  so that one edit is the whole change. SOURCE_META keeps its consumer entry
 *  deliberately: the Source Mix chart above still counts every cohort, and a
 *  trend's real composition would be misreported without it.
 */
const POST_SOURCES: readonly Source[] = ["brand", "influencer"];

// Spelled out rather than built from the length: Tailwind scans for literal
// class strings, and an interpolated `lg:grid-cols-${n}` is never emitted.
const POST_GRID_COLS: Record<number, string> = {
  1: "lg:grid-cols-1",
  2: "lg:grid-cols-2",
  3: "lg:grid-cols-3",
};

/** Cohorts offered in the "Posts from" trend filter.
 *
 *  Consumers are left out deliberately: every one of the 174 trends has
 *  consumer posts, because that is the corpus trends are clustered from. An
 *  option that never removes a row is a control that looks broken.
 */
const FILTER_COHORTS: readonly Source[] = ["brand", "influencer"];

/** How many posts sit side by side inside one cohort column.
 *
 *  Fewer cohorts on screen means wider columns, and the post image is
 *  `aspect-square w-full` - so it grows to whatever it is given. At two cohorts
 *  one card per row rendered a single square image about half the viewport
 *  wide. Keyed off the same list so a card stays roughly one size whatever
 *  POST_SOURCES holds.
 */
const POSTS_PER_ROW: Record<number, string> = {
  1: "sm:grid-cols-3",
  2: "sm:grid-cols-2",
  3: "sm:grid-cols-1",
};

function formatPct(pct: number): string {
  if (pct === 0) return "0";
  if (pct >= 10) return pct.toFixed(1).replace(/\.0$/, "");
  if (pct >= 1) return pct.toFixed(1);
  if (pct >= 0.1) return pct.toFixed(2);
  return pct.toFixed(3);
}

const chartTooltip = {
  background: "var(--dropdown-bg)", border: "1px solid var(--card-bd)",
  borderRadius: 12, fontSize: 12, color: "var(--body-tx)",
};
const FILTERS: ("all" | Quadrant)[] = ["all", "slow-burner", "mainstream", "breakthrough", "watchlist"];

const CARD_GRID = "grid grid-cols-1 gap-5 md:grid-cols-2 xl:grid-cols-3";

/** How many trends to render at once.
 *
 *  A run holds ~820 micro trends and every one of them used to mount on load:
 *  820 cards, each with a sparkline chart, which is both a slow first paint and
 *  an unreadable wall. The sizes are multiples of the 3-column grid so a full
 *  page never ends in a ragged row.
 */
const PAGE_SIZES = [12, 18, 24, 48, 96] as const;
// Sentinel for "one page holding everything". Deliberately -1 and not 0:
// Number(null), Number("") and Number(" ") are all 0, so a 0 sentinel matched
// every absent or blank stored value and turned the no-preference case - which
// is every first visit and every server render - into "show all 820".
const ALL_PAGE_SIZE = -1;
const DEFAULT_PAGE_SIZE = 18;
const PAGE_SIZE_KEY = "fi.trends.pageSize";

/** The chosen page size, held in localStorage rather than in component state.
 *
 *  It is remembered because it describes how this person reads the board, not
 *  the question they asked today: someone who sets 96 wants 96 next week too.
 *
 *  An external store rather than `useState` plus a load effect, for three
 *  reasons: localStorage is unreadable during SSR so a lazy initialiser would
 *  hydrate wrong, reading it in an effect means a second render on every
 *  mount, and this way two open tabs stay in step for free through the
 *  `storage` event. Every access is guarded because Safari's private mode
 *  throws on localStorage rather than returning null.
 */
const pageSizeStore = {
  listeners: new Set<() => void>(),
  subscribe(fn: () => void) {
    pageSizeStore.listeners.add(fn);
    window.addEventListener("storage", fn);
    return () => {
      pageSizeStore.listeners.delete(fn);
      window.removeEventListener("storage", fn);
    };
  },
  read(): string | null {
    try { return window.localStorage.getItem(PAGE_SIZE_KEY); } catch { return null; }
  },
  write(size: number) {
    try { window.localStorage.setItem(PAGE_SIZE_KEY, String(size)); } catch { /* not fatal */ }
    pageSizeStore.listeners.forEach((fn) => fn());
  },
};

/** A stored value only counts if it is still one of the offered sizes.
 *
 *  Absence is checked before the number is parsed, not after. Every "no value"
 *  form - null from an empty key, "" from a cleared one, and the null this
 *  returns during SSR - has to land on the default, and Number() maps all of
 *  them to 0, so parsing first loses the distinction the caller depends on.
 *
 *  Anything unrecognised also falls back rather than being trusted: the size
 *  list can change between releases, and a stale "36" would leave the strip
 *  paging by a number no menu item shows as chosen.
 */
function normalisePageSize(raw: string | null): number {
  if (raw === null || raw.trim() === "") return DEFAULT_PAGE_SIZE;
  const n = Number(raw);
  if (n === ALL_PAGE_SIZE) return ALL_PAGE_SIZE;
  return PAGE_SIZES.includes(n as (typeof PAGE_SIZES)[number]) ? n : DEFAULT_PAGE_SIZE;
}

/** Page numbers to render, collapsing the middle once there are too many.
 *
 *  First and last are always reachable so "jump to the end" never needs a
 *  dozen clicks, and the current page keeps a neighbour on each side so the
 *  row does not reflow to a different width as you step through it.
 */
function pageWindow(current: number, total: number): (number | "gap")[] {
  if (total <= 7) return Array.from({ length: total }, (_, i) => i + 1);
  const out: (number | "gap")[] = [1];
  const from = Math.max(2, Math.min(current - 1, total - 4));
  const to = Math.min(total - 1, Math.max(current + 1, 5));
  if (from > 2) out.push("gap");
  for (let p = from; p <= to; p += 1) out.push(p);
  if (to < total - 1) out.push("gap");
  out.push(total);
  return out;
}

/* ─── small bits ─────────────────────────────────────────────────────── */
function PlatformPill({ platform }: { platform: string }) {
  return (
    <span className="rounded-full px-2 py-0.5 text-xs font-semibold capitalize"
      style={{ background: "var(--card-bg-2)", color: "var(--muted-tx)", border: "1px solid var(--card-bd)" }}>
      {platform}
    </span>
  );
}

/** Shows momentum_pct: the share of this trend's presence across the last two
 *  56-day windows that falls in the recent one, 0-100.
 *
 *  Two other figures were tried here and neither reads on a card. growth_pct
 *  is the true rate of change but is floored at -100 and unbounded above, so
 *  the board mixed "-74%" with "1,240%" and gave the reader no scale to judge
 *  either against. growth_index fixed the range by ranking instead, but a rank
 *  is not a rate, so it could not carry a % sign without claiming to be one.
 *
 *  This is bounded because it splits a fixed whole rather than dividing one
 *  window by another, so 0-100 is a property of the measurement and not a
 *  clamp applied after the fact. 50 is the anchor: the same share in both
 *  windows. The arrow reads off the same number, so the two can never
 *  disagree with each other.
 */
function MomentumBadge({ t }: { t: TrendListItem }) {
  if (t.is_new) {
    return (
      <span className="rounded-full px-2 py-0.5 text-xs font-bold"
        style={{ background: "var(--fi-breakthrough-soft)", color: "var(--fi-breakthrough-tx)" }}>New</span>
    );
  }
  const pct = t.momentum_pct;
  const down = (pct ?? 50) < 50;
  return (
    <div className="flex items-center gap-1 text-lg font-bold tabular-nums"
      style={{ color: down ? "var(--fi-danger-tx)" : "var(--fi-growth-tx)" }}
      title={pct == null
        ? "Momentum unavailable for this trend"
        : `${pct}% of this trend's activity across the last two 56-day windows falls in the recent one. `
          + `50% is flat, so this trend is ${down ? "losing" : "gaining"} ground.`}>
      {down ? <ArrowDownRight size={18} aria-hidden="true" /> : <ArrowUpRight size={18} aria-hidden="true" />}
      {pct == null ? "—" : `${pct}%`}
    </div>
  );
}

function Spark({ data, token }: { data: number[]; token: TokenFamily }) {
  const series = data.map((v, i) => ({ i, v }));
  const id = `spk-${token}`;
  return (
    <div className="h-12 w-full" aria-hidden="true" style={{ color: graphic(token) }}>
      <ResponsiveContainer width="100%" height="100%">
        <AreaChart data={series} margin={{ top: 4, right: 0, bottom: 0, left: 0 }}>
          <defs>
            <linearGradient id={id} x1="0" y1="0" x2="0" y2="1">
              <stop offset="0%" stopColor="currentColor" stopOpacity={0.35} />
              <stop offset="100%" stopColor="currentColor" stopOpacity={0} />
            </linearGradient>
          </defs>
          <Area type="monotone" dataKey="v" stroke="currentColor" strokeWidth={2} fill={`url(#${id})`} isAnimationActive={false} />
        </AreaChart>
      </ResponsiveContainer>
    </div>
  );
}

/* ─── LIST: snapshot card (one per trend) ────────────────────────────── */
function TrendSnapshotCard({ t, i, onSelect }: { t: TrendListItem; i: number; onSelect: () => void }) {
  const meta = QUADRANT_META[t.quadrant];
  return (
    <motion.button
      type="button"
      onClick={onSelect}
      initial={{ opacity: 0, y: 12 }} animate={{ opacity: 1, y: 0 }}
      transition={{ duration: 0.4, delay: Math.min(i, 8) * 0.035, ease: [0.16, 1, 0.3, 1] }}
      className="group chart-card flex flex-col rounded-2xl p-5 text-left transition-all hover:-translate-y-0.5 hover:shadow-md"
    >
      <div className="mb-2 flex items-start justify-between gap-3">
        <div>
          <h3 style={{ color: "var(--title-tx)" }} className="text-base font-semibold">{t.name}</h3>
          <span className="mt-1 inline-block rounded-full px-2 py-0.5 text-xs font-semibold"
            style={{ background: soft(meta.token), color: text(meta.token) }}>{meta.label}</span>
          {t.origin === "chat" && (
            // Same measurement, different provenance. Worth marking on the card
            // so a trend someone asked for is never mistaken for one the corpus
            // surfaced on its own.
            <span className="ml-1.5 mt-1 inline-block rounded-full px-2 py-0.5 text-xs font-semibold"
              style={{ background: "var(--fi-watchlist-soft)", color: "var(--fi-watchlist-tx)" }}
              title={t.source_query ? `Generated from: ${t.source_query}` : "Generated from chat"}>
              Chat-generated
            </span>
          )}
        </div>
        <MomentumBadge t={t} />
      </div>

      <Spark data={t.sparkline.length ? t.sparkline : [0]} token={meta.token} />

      <p style={{ color: "var(--body-tx)" }} className="my-3 line-clamp-2 flex-1 text-sm leading-relaxed">{t.summary}</p>

      <div className="flex items-center justify-between border-t pt-3" style={{ borderColor: "var(--card-bd)" }}>
        <div className="flex items-center gap-2">{t.platforms.map((p) => <PlatformPill key={p} platform={p} />)}</div>
      </div>

      <div className="mt-3 flex items-center justify-between text-xs" style={{ color: "var(--muted-tx)" }}>
        <span>Posts <b style={{ color: "var(--body-tx)" }} className="tabular-nums">{t.post_count.toLocaleString()}</b></span>
        <span className="inline-flex items-center gap-1 font-semibold opacity-0 transition group-hover:opacity-100 group-focus-visible:opacity-100"
          style={{ color: "var(--fi-growth-tx)" }}>
          View details <ArrowUpRight size={12} aria-hidden="true" />
        </span>
      </div>
    </motion.button>
  );
}

/* ─── DETAIL: trendline chart ────────────────────────────────────────── */
function Trendline({ title, subtitle, data, color, seriesId }: {
  title: string; subtitle: string; data: { label: string; v: number }[]; color: string; seriesId: string;
}) {
  const id = `grad-${seriesId}`;
  const tick = radarTickFill();
  const grid = chartGridStroke();
  return (
    <div className="chart-card rounded-2xl p-6">
      <h3 style={{ color: "var(--title-tx)" }} className="text-base font-semibold">{title}</h3>
      <p style={{ color: "var(--muted-tx)" }} className="mb-4 text-xs">{subtitle}</p>
      <div className="h-56 w-full" style={{ color }}>
        <ResponsiveContainer width="100%" height="100%">
          <AreaChart data={data} margin={{ top: 6, right: 12, bottom: 0, left: -8 }}>
            <defs>
              <linearGradient id={id} x1="0" y1="0" x2="0" y2="1">
                <stop offset="0%" stopColor="currentColor" stopOpacity={0.28} />
                <stop offset="100%" stopColor="currentColor" stopOpacity={0} />
              </linearGradient>
            </defs>
            <CartesianGrid strokeDasharray="3 3" stroke={grid} vertical={false} />
            <XAxis dataKey="label" tick={{ fontSize: 12, fill: tick }} tickLine={false} axisLine={false} />
            <YAxis tick={{ fontSize: 12, fill: tick }} tickLine={false} axisLine={false} width={48} />
            <RTooltip contentStyle={chartTooltip} />
            <Area type="monotone" dataKey="v" stroke="currentColor" strokeWidth={2.5} fill={`url(#${id})`} isAnimationActive={false} />
          </AreaChart>
        </ResponsiveContainer>
      </div>
    </div>
  );
}

function PostCard({ p }: { p: ExamplePost }) {
  const body = (
    // No h-full here: inside the stretched example-content grid, height:100%
    // makes every card as tall as the whole column and they overflow the page.
    <div className="rounded-xl p-4 transition-all hover:-translate-y-0.5" style={{ background: "var(--card-bg-2)", border: "1px solid var(--card-bd)" }}>
      {p.media_url && (
        // Intrinsic size + reserved box let the browser genuinely defer these:
        // without dimensions it cannot lay out ahead and loads them eagerly.
        // eslint-disable-next-line @next/next/no-img-element
        <img
          src={p.media_url}
          alt=""
          loading="lazy"
          decoding="async"
          width={448}
          height={448}
          className="mb-3 aspect-square w-full rounded-lg object-cover"
          style={{ background: "var(--card-bg)" }}
          onError={(e) => { e.currentTarget.style.display = "none"; }}
        />
      )}
      <div className="mb-2 flex items-start justify-between gap-2">
        <div className="min-w-0">
          <div style={{ color: "var(--title-tx)" }} className="truncate text-sm font-semibold">@{p.author}</div>
          <div style={{ color: "var(--muted-tx)" }} className="truncate text-xs capitalize">{p.platform}</div>
        </div>
        <div className="flex shrink-0 items-center gap-2 text-xs tabular-nums" style={{ color: "var(--muted-tx)" }}>
          <span className="flex items-center gap-1"><Heart size={11} aria-hidden="true" /> {p.likes.toLocaleString()}</span>
          <span className="flex items-center gap-1"><MessageCircle size={11} aria-hidden="true" /> {p.comments.toLocaleString()}</span>
          {p.views > 0 && <span className="flex items-center gap-1"><Eye size={11} aria-hidden="true" /> {p.views.toLocaleString()}</span>}
        </div>
      </div>
      {/* fixed 3-line block so every card is the same height and rows align */}
      <p dir="auto" style={{ color: "var(--body-tx)" }} className="line-clamp-3 min-h-[4.35rem] text-sm leading-relaxed">{p.caption}</p>
    </div>
  );
  return p.post_url
    ? <a key={p.post_id} href={p.post_url} target="_blank" rel="noreferrer" className="block rounded-xl">{body}</a>
    : body;
}

function TrendJourney({ current }: { current: Quadrant }) {
  const currentIdx = TREND_JOURNEY.indexOf(current);
  return (
    <div className="chart-card rounded-2xl p-6">
      <h3 style={{ color: "var(--title-tx)" }} className="mb-4 text-base font-semibold">Trend Journey</h3>
      <div className="flex flex-col items-stretch gap-2 sm:flex-row sm:items-center">
        {TREND_JOURNEY.map((q, i) => {
          const meta = QUADRANT_META[q];
          const done = i <= currentIdx;
          const isCurrent = i === currentIdx;
          return (
            <div key={q} className="flex flex-1 items-center gap-2">
              <div className="flex-1 rounded-xl p-4 text-center"
                style={{ background: isCurrent ? soft(meta.token) : "var(--card-bg-2)", border: `1px solid ${isCurrent ? softBorder(meta.token) : "var(--card-bd)"}` }}>
                <div className="mx-auto mb-2 flex h-7 w-7 items-center justify-center rounded-full text-xs font-bold"
                  style={done ? { background: graphic(meta.token), color: "#ffffff" } : { background: "var(--card-bg)", border: "1px solid var(--card-bd)", color: "var(--muted-tx)" }}>
                  {done ? <Check size={14} aria-hidden="true" /> : i + 1}
                </div>
                <div style={{ color: "var(--title-tx)" }} className="text-sm font-semibold">{meta.label}</div>
                {isCurrent && <div style={{ color: text(meta.token) }} className="mt-0.5 text-xs font-medium">Current stage</div>}
              </div>
              {i < TREND_JOURNEY.length - 1 && <span style={{ color: "var(--muted-tx)" }} aria-hidden="true" className="hidden shrink-0 sm:inline">→</span>}
            </div>
          );
        })}
      </div>
    </div>
  );
}

function DetailSkeleton() {
  return (
    <div className="space-y-6" aria-hidden="true">
      <div className="chart-card rounded-2xl p-6">
        <Skel className="h-5 w-24 rounded-full" />
        <Skel className="mt-3 h-9 w-2/3 max-w-md" />
        <Skel className="mt-3 h-4 w-full max-w-2xl" />
        <Skel className="mt-2 h-4 w-4/5 max-w-xl" />
      </div>
      <div className="grid grid-cols-1 gap-6 lg:grid-cols-2">
        <Skel className="h-80 rounded-2xl" />
        <Skel className="h-80 rounded-2xl" />
      </div>
      <div className="grid grid-cols-1 gap-6 lg:grid-cols-3">
        <Skel className="h-72 rounded-2xl" />
        <Skel className="h-72 rounded-2xl lg:col-span-2" />
      </div>
    </div>
  );
}

/* ─── DETAIL view (fetches live) ─────────────────────────────────────── */
function TrendDetailView({ trendId, market, onBack }: {
  trendId: string; market: Market | null; onBack: () => void;
}) {
  const [detail, setDetail] = useState<TrendDetailData | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [dateFrom, setDateFrom] = useState("");
  const [dateTo, setDateTo] = useState("");
  const [reloadKey, setReloadKey] = useState(0);

  useEffect(() => {
    const ac = new AbortController();
    setDetail(null);
    setError(null);
    fetchTrendDetail(trendId, dateFrom || null, dateTo || null, ac.signal, market)
      .then(setDetail)
      .catch((e) => { if (!isAbort(e)) setError(friendlyTrendError(e)); });
    return () => ac.abort();
  }, [trendId, market, dateFrom, dateTo, reloadKey]);

  const back = (
    <button onClick={onBack} className="inline-flex min-h-11 items-center gap-1.5 rounded-lg text-sm font-medium" style={{ color: "var(--muted-tx)" }}>
      <ArrowLeft size={15} aria-hidden="true" /> Back to trends
    </button>
  );
  const inputStyle = { background: "var(--card-bg)", border: "1px solid var(--card-bd)", color: "var(--body-tx)" };
  const range = (
    <div className="flex flex-wrap items-center gap-2 text-xs" style={{ color: "var(--muted-tx)" }}>
      <CalendarDays size={14} aria-hidden="true" />
      <span id={`range-${trendId}`}>Date range</span>
      <input type="date" value={dateFrom} max={dateTo || undefined}
        aria-label="From date"
        onChange={(e) => setDateFrom(e.target.value)}
        className="min-h-11 rounded-lg px-2.5 py-1 text-sm" style={inputStyle} />
      <span>to</span>
      <input type="date" value={dateTo} min={dateFrom || undefined}
        aria-label="To date"
        onChange={(e) => setDateTo(e.target.value)}
        className="min-h-11 rounded-lg px-2.5 py-1 text-sm" style={inputStyle} />
      {(dateFrom || dateTo) && (
        <button onClick={() => { setDateFrom(""); setDateTo(""); }}
          className="min-h-11 rounded-full px-3 py-1 text-xs font-semibold"
          style={{ border: "1px solid var(--card-bd)", color: "var(--body-tx)" }}>
          Clear
        </button>
      )}
    </div>
  );
  const header = (
    <div className="flex flex-wrap items-center justify-between gap-3">{back}{range}</div>
  );
  if (error) {
    return (
      <div className="space-y-6">{header}
        <InlineError message={error} onRetry={() => setReloadKey((k) => k + 1)} />
      </div>
    );
  }
  if (!detail) {
    return (
      <div className="space-y-6">{header}<LoadingAnnouncer label="Loading trend detail" /><DetailSkeleton /></div>
    );
  }

  const meta = QUADRANT_META[detail.quadrant];
  const socialSeries = detail.timeline.map((t) => ({ label: t.week_start.slice(5), v: t.post_count }));
  const engagementSeries = detail.timeline.map((t) => ({ label: t.week_start.slice(5), v: t.engagement }));
  const totalSourced = Object.values(detail.source_mix).reduce((a, b) => a + (b ?? 0), 0) || 1;
  const sourceMix = Object.entries(detail.source_mix).map(([src, count]) => {
    const n = count ?? 0;
    const pct = totalSourced ? (n / totalSourced) * 100 : 0;
    const token = SOURCE_META[src as Source]?.token;
    return {
      label: SOURCE_META[src as Source]?.label ?? src,
      value: pct,
      count: n,
      display: `${formatPct(pct)}%`,
      color: token ? graphic(token) : CHART_SERIES[5],
    };
  });

  return (
    <div className="space-y-6">
      {header}

      {/* hero */}
      <motion.section key={detail.id} initial={{ opacity: 0, y: 12 }} animate={{ opacity: 1, y: 0 }}
        transition={{ duration: 0.45, ease: [0.16, 1, 0.3, 1] }}
        className="chart-card rounded-2xl p-6" style={{ background: soft(meta.token) }}>
        <div className="flex flex-wrap items-start justify-between gap-4">
          <div className="max-w-2xl">
            <span className="inline-block rounded-full px-3 py-0.5 text-xs font-semibold"
              style={{ background: "var(--card-bg)", color: text(meta.token), border: `1px solid ${softBorder(meta.token)}` }}>{meta.label}</span>
            <h1 style={{ color: "var(--title-tx)" }} className="mt-3 text-3xl font-bold tracking-tight">{detail.name}</h1>
            <p style={{ color: "var(--body-tx)" }} className="mt-2 text-sm leading-relaxed">{detail.summary}</p>
          </div>
          <div className="flex gap-3">
            <div className="rounded-xl px-4 py-3 text-center" style={{ background: "var(--card-bg)", border: "1px solid var(--card-bd)" }}>
              <div style={{ color: "var(--title-tx)" }} className="text-xl font-bold tabular-nums">{detail.post_count.toLocaleString()}</div>
              <div style={{ color: "var(--muted-tx)" }} className="text-xs">Posts</div>
            </div>
          </div>
        </div>
        {detail.opportunity_summary && (
          <div className="mt-5 border-t pt-4" style={{ borderColor: "var(--card-bd)" }}>
            <p style={{ color: "var(--body-tx)" }} className="text-sm leading-relaxed">
              <span style={{ color: "var(--fi-growth-tx)" }} className="font-semibold">Opportunity summary: </span>{detail.opportunity_summary}
            </p>
          </div>
        )}
      </motion.section>

      {/* trendlines */}
      <div className="grid grid-cols-1 gap-6 lg:grid-cols-2">
        <Trendline title="Social Trendline" subtitle="Weekly community posts in this trend" data={socialSeries} color={CHART_SERIES[0]} seriesId="social" />
        <Trendline title="Engagement Trendline" subtitle="Weekly likes, comments and views in this trend"
          data={engagementSeries} color={CHART_SERIES[1]} seriesId="engagement" />
      </div>

      {/* source mix + related themes */}
      <div className="grid grid-cols-1 gap-6 lg:grid-cols-3">
        <div className="chart-card rounded-2xl p-6">
          <h3 style={{ color: "var(--title-tx)" }} className="mb-2 text-base font-semibold">Source Mix</h3>
          <div className="h-44 w-full">
            <ResponsiveContainer width="100%" height="100%">
              <PieChart>
                <Pie data={sourceMix} dataKey="value" nameKey="label" cx="50%" cy="50%" innerRadius={46} outerRadius={72} paddingAngle={2} stroke="none" isAnimationActive={false}>
                  {sourceMix.map((s) => <Cell key={s.label} style={{ fill: s.color }} />)}
                </Pie>
                <RTooltip contentStyle={chartTooltip}
                  formatter={(v, _n, item) => `${formatPct(Number(v))}% (${(item?.payload?.count ?? 0).toLocaleString()} posts)`} />
              </PieChart>
            </ResponsiveContainer>
          </div>
          <div className="mt-3 grid grid-cols-2 gap-y-2">
            {sourceMix.map((s) => (
              <div key={s.label} className="flex items-center justify-between gap-2 pr-2">
                <span className="flex items-center gap-1.5 text-xs" style={{ color: "var(--body-tx)" }}>
                  <span className="h-2.5 w-2.5 rounded-full" style={{ background: s.color }} aria-hidden="true" /> {s.label}
                </span>
                <span style={{ color: "var(--muted-tx)" }} className="text-xs font-semibold tabular-nums">{s.display}</span>
              </div>
            ))}
          </div>
        </div>

        <div className="chart-card rounded-2xl p-6 lg:col-span-2">
          <h3 style={{ color: "var(--title-tx)" }} className="mb-4 text-base font-semibold">Related Themes</h3>
          <div className="flex flex-wrap gap-2">
            {detail.related_themes.map((t) => (
              <span key={t} className="rounded-full px-3.5 py-1.5 text-sm font-medium" style={{ background: "var(--card-bg-2)", border: "1px solid var(--card-bd)", color: "var(--body-tx)" }}>{t}</span>
            ))}
          </div>
          {detail.keywords.length > 0 && (
            <>
              <h3 style={{ color: "var(--title-tx)" }} className="mb-3 mt-6 text-base font-semibold">Distinctive Keywords</h3>
              <div className="flex flex-wrap gap-2">
                {detail.keywords.map((k) => (
                  <span key={k} dir="auto" className="rounded-full px-3 py-1 text-xs" style={{ background: "var(--card-bg-2)", border: "1px solid var(--card-bd)", color: "var(--body-tx)" }}>{k}</span>
                ))}
              </div>
            </>
          )}
        </div>
      </div>

      {/* example content — one column per source */}
      <div>
        <h3 style={{ color: "var(--title-tx)" }} className="mb-4 text-base font-bold">Example Content</h3>
        <div className={`grid grid-cols-1 gap-6 ${POST_GRID_COLS[POST_SOURCES.length] ?? "lg:grid-cols-3"}`}>
          {POST_SOURCES.map((src) => {
            const posts = detail.example_posts_by_source[src] ?? [];
            const sm = SOURCE_META[src];
            return (
              // space-y-6 matches the grid's column gap so the card lattice is even
              <div key={src} className="space-y-6">
                <h4 className="text-xs font-bold uppercase tracking-wider" style={{ color: text(sm.token) }}>
                  {src === "community" ? "Consumer Posts" : `${sm.label.slice(0, -1)} Posts`}
                </h4>
                {posts.length ? (
                  <div className={`grid grid-cols-1 gap-6 ${POSTS_PER_ROW[POST_SOURCES.length] ?? "sm:grid-cols-1"}`}>
                    {posts.map((p) => <PostCard key={`${p.platform}-${p.post_id}`} p={p} />)}
                  </div>
                ) : (
                  <div className="rounded-xl border border-dashed p-4 text-xs" style={{ borderColor: "var(--card-bd)", color: "var(--muted-tx)" }}>
                    No {src === "community" ? "consumer" : src} posts assigned to this trend in the current window.
                  </div>
                )}
              </div>
            );
          })}
        </div>
      </div>

      <TrendJourney current={detail.quadrant} />
    </div>
  );
}

/* ─── filter dropdown ─────────────────────────────────────────────────── */
type FilterOption = { value: string; label: string; color?: string };

/** A compact filter control, single- or multi-select.
 *
 *  Multi-select keeps the menu open after a pick: choosing two cohorts is the
 *  normal case and reopening between them is pure friction. Single-select
 *  closes, because the choice is complete the moment it is made.
 *
 *  Selection is always passed as an array so both modes share one signature;
 *  a single-select caller reads index 0 and treats empty as "no filter".
 */
function FilterDropdown({
  label, allLabel, options, selected, onChange, multiple = false, disabled = false,
}: {
  label: string;
  allLabel: string;
  options: readonly FilterOption[];
  selected: readonly string[];
  onChange: (next: string[]) => void;
  multiple?: boolean;
  disabled?: boolean;
}) {
  const [open, setOpen] = useState(false);
  const rootRef = useRef<HTMLDivElement>(null);

  // A menu left open floats over the trend cards and swallows the next click,
  // so it closes on an outside press and on Escape.
  useEffect(() => {
    if (!open) return;
    const onDown = (e: MouseEvent) => {
      if (!rootRef.current?.contains(e.target as Node)) setOpen(false);
    };
    const onKey = (e: KeyboardEvent) => { if (e.key === "Escape") setOpen(false); };
    document.addEventListener("mousedown", onDown);
    document.addEventListener("keydown", onKey);
    return () => {
      document.removeEventListener("mousedown", onDown);
      document.removeEventListener("keydown", onKey);
    };
  }, [open]);

  const pick = (value: string) => {
    if (!multiple) { onChange([value]); setOpen(false); return; }
    onChange(selected.includes(value)
      ? selected.filter((v) => v !== value)
      : [...selected, value]);
  };

  const active = selected.length > 0;
  const summary = !active
    ? allLabel
    : selected.length === 1
      ? (options.find((o) => o.value === selected[0])?.label ?? allLabel)
      : `${selected.length} selected`;

  const item = (key: string, label2: string, on: boolean, onClick: () => void, color?: string) => (
    <button key={key} type="button" role="option" aria-selected={on} onClick={onClick}
      className="flex min-h-11 w-full items-center justify-between gap-3 rounded-lg px-3 py-2 text-left text-xs font-medium transition-colors hover:bg-[var(--dropdown-bg-2)]"
      style={{ color: "var(--body-tx)" }}>
      <span className="flex items-center gap-2">
        {color && <span className="h-2 w-2 rounded-full" style={{ background: color }} aria-hidden="true" />}
        {label2}
      </span>
      {on && <Check size={13} aria-hidden="true" style={{ color: "var(--accent-tx)" }} />}
    </button>
  );

  return (
    <div ref={rootRef} className="relative">
      <button type="button" onClick={() => setOpen((o) => !o)} disabled={disabled}
        aria-haspopup="listbox" aria-expanded={open}
        className="flex min-h-11 items-center gap-1.5 rounded-full px-3.5 py-1.5 text-xs font-semibold transition-colors disabled:opacity-60"
        style={{
          background: active ? "var(--fi-solid)" : "var(--card-bg-2)",
          color: active ? "var(--fi-solid-tx)" : "var(--body-tx)",
          border: `1px solid ${active ? "var(--fi-solid)" : "var(--card-bd)"}`,
        }}>
        <span style={{ opacity: 0.75 }}>{label}</span>
        {summary}
        <ChevronDown size={13} aria-hidden="true" style={{ transform: open ? "rotate(180deg)" : undefined, transition: "transform 150ms" }} />
      </button>

      {/* --dropdown-bg, not --card-bg: the card tokens are translucent by design
          (rgba(255,255,255,0.55)) so glass cards pick up the page gradient behind
          them. A menu floats over content instead, and the trend cards showed
          straight through it. These are the opaque tokens BrandSelect already uses. */}
      {open && (
        <div role="listbox" aria-label={label}
          className="absolute left-0 top-full z-30 mt-2 min-w-[13rem] rounded-xl p-1.5 shadow-xl"
          style={{ background: "var(--dropdown-bg)", border: "1px solid var(--card-bd)" }}>
          {item("__all", allLabel, !active, () => { onChange([]); setOpen(false); })}
          <div className="my-1 h-px" style={{ background: "var(--card-bd)" }} aria-hidden="true" />
          {options.map((o) =>
            item(o.value, o.label, selected.includes(o.value), () => pick(o.value), o.color))}
        </div>
      )}
    </div>
  );
}

/* ─── pagination ──────────────────────────────────────────────────────── */

/** One square key in the page strip.
 *
 *  Square-ish rather than the filter row's fully round pills: these are a
 *  numeric keypad, and a row of circles reads as a row of unrelated toggles
 *  while a row of equal squares reads as one control. Every key is the same
 *  44px box whether it holds "1" or "10", so the strip does not jitter as the
 *  numbers gain a digit.
 */
const PAGE_KEY =
  "flex h-12 min-w-12 items-center justify-center rounded-2xl px-3.5 text-base font-bold "
  + "tabular-nums transition-colors disabled:cursor-not-allowed disabled:opacity-40";

function pageKeyStyle(on: boolean): React.CSSProperties {
  return {
    background: on ? "var(--fi-solid)" : "var(--card-bg-2)",
    color: on ? "var(--fi-solid-tx)" : "var(--body-tx)",
    // The current key drops its border so the fill reads as one solid block
    // rather than a filled box wearing an outline.
    border: `1px solid ${on ? "var(--fi-solid)" : "var(--card-bd)"}`,
  };
}

/** The size control's caret.
 *
 *  A filled triangle, not the line chevron the filter menus use: this is a
 *  value picker sitting on a neutral chip, and the solid mark reads as "this
 *  opens a list of values" where a stroked chevron reads as navigation.
 */
function CaretDown({ open }: { open: boolean }) {
  return (
    <svg
      width="10" height="7" viewBox="0 0 10 7" aria-hidden="true"
      style={{
        fill: "currentColor",
        transform: open ? "rotate(180deg)" : undefined,
        transition: "transform 150ms",
      }}
    >
      <path d="M5 7 0 0h10z" />
    </svg>
  );
}

/** How many trends to render at once.
 *
 *  A dropdown rather than a row of size pills: it is set once and then left
 *  alone, so it does not deserve the width five pills would take beside a
 *  control the reader actually works. Closing on outside-press and Escape
 *  matches the filter menus above.
 */
function PageSizeSelect({
  value, total, onChange,
}: {
  value: number;
  total: number;
  onChange: (size: number) => void;
}) {
  const [open, setOpen] = useState(false);
  const rootRef = useRef<HTMLDivElement>(null);

  useEffect(() => {
    if (!open) return;
    const onDown = (e: MouseEvent) => {
      if (!rootRef.current?.contains(e.target as Node)) setOpen(false);
    };
    const onKey = (e: KeyboardEvent) => { if (e.key === "Escape") setOpen(false); };
    document.addEventListener("mousedown", onDown);
    document.addEventListener("keydown", onKey);
    return () => {
      document.removeEventListener("mousedown", onDown);
      document.removeEventListener("keydown", onKey);
    };
  }, [open]);

  const choose = (size: number) => { onChange(size); setOpen(false); };
  const label = value === ALL_PAGE_SIZE ? "All" : String(value);

  return (
    <div ref={rootRef} className="relative">
      {/* Filled chip, no outline. The page keys above are outlined because they
          are a set you choose between; this one is a single value you change,
          and giving it the same border would put it in that set. */}
      <button
        type="button"
        onClick={() => setOpen((o) => !o)}
        aria-haspopup="listbox"
        aria-expanded={open}
        aria-label={`Trends per page: ${label}`}
        className="flex h-12 items-center gap-3 rounded-2xl px-5 text-base font-bold tabular-nums transition-colors"
        style={{ background: "var(--dropdown-bg-2)", color: "var(--title-tx)" }}
      >
        {label}
        <CaretDown open={open} />
      </button>

      {/* Opens upward: this control sits at the bottom of a long scroll, and a
          downward menu would open past the fold. --dropdown-bg is the opaque
          token - the card tokens are translucent and the grid shows through. */}
      {open && (
        <div
          role="listbox"
          aria-label="Trends per page"
          className="absolute bottom-full right-0 z-30 mb-2 min-w-[7.5rem] rounded-xl p-1.5 shadow-xl"
          style={{ background: "var(--dropdown-bg)", border: "1px solid var(--card-bd)" }}
        >
          {PAGE_SIZES.map((size) => (
            <button
              key={size}
              type="button"
              role="option"
              aria-selected={value === size}
              onClick={() => choose(size)}
              className="flex min-h-11 w-full items-center justify-between gap-3 rounded-lg px-3 text-left text-sm font-medium tabular-nums transition-colors hover:bg-[var(--dropdown-bg-2)]"
              style={{ color: "var(--body-tx)" }}
            >
              {size}
              {value === size && <Check size={14} aria-hidden="true" style={{ color: "var(--accent-tx)" }} />}
            </button>
          ))}
          <div className="my-1 h-px" style={{ background: "var(--card-bd)" }} aria-hidden="true" />
          <button
            type="button"
            role="option"
            aria-selected={value === ALL_PAGE_SIZE}
            onClick={() => choose(ALL_PAGE_SIZE)}
            title={`Render all ${total.toLocaleString()} trends at once`}
            className="flex min-h-11 w-full items-center justify-between gap-3 rounded-lg px-3 text-left text-sm font-medium transition-colors hover:bg-[var(--dropdown-bg-2)]"
            style={{ color: "var(--body-tx)" }}
          >
            All
            {value === ALL_PAGE_SIZE && <Check size={14} aria-hidden="true" style={{ color: "var(--accent-tx)" }} />}
          </button>
        </div>
      )}
    </div>
  );
}

function TrendPagination({
  page, pageCount, pageSize, total, from, to, onPage, onPageSize,
}: {
  page: number;
  pageCount: number;
  pageSize: number;
  total: number;
  from: number;
  to: number;
  onPage: (p: number) => void;
  onPageSize: (size: number) => void;
}) {
  const showAll = pageSize === ALL_PAGE_SIZE;
  /* One row, no rule above it. The card grid ends on a clear edge already, so
     the divider drew a boundary the layout had drawn for free, and stacking
     the count under the strip spent a whole row on eleven characters. */
  return (
    <nav
      aria-label="Trend pages"
      className="flex flex-wrap items-center gap-x-6 gap-y-4 pt-1"
    >
      {/* The page strip leads, because stepping is the thing a reader comes
          down here to do. It is dropped entirely at one page: a lone "1"
          flanked by two dead arrows is furniture. */}
      {pageCount > 1 && (
        <div className="flex flex-wrap items-center gap-2.5">
          <button
            type="button"
            onClick={() => onPage(page - 1)}
            disabled={page <= 1}
            aria-label="Previous page"
            className={PAGE_KEY}
            style={pageKeyStyle(false)}
          >
            <ChevronLeft size={18} aria-hidden="true" />
          </button>

          {pageWindow(page, pageCount).map((p, i) =>
            p === "gap" ? (
              // Keeps the box so the strip stays an even lattice, but inert:
              // there is no single page a reader could mean by "...".
              <span
                key={`gap-${i}`}
                aria-hidden="true"
                className={PAGE_KEY}
                style={{ ...pageKeyStyle(false), color: "var(--muted-tx)" }}
              >
                &hellip;
              </span>
            ) : (
              <button
                key={p}
                type="button"
                onClick={() => onPage(p)}
                aria-label={`Page ${p}`}
                aria-current={p === page ? "page" : undefined}
                className={PAGE_KEY}
                style={pageKeyStyle(p === page)}
              >
                {p}
              </button>
            )
          )}

          <button
            type="button"
            onClick={() => onPage(page + 1)}
            disabled={page >= pageCount}
            aria-label="Next page"
            className={PAGE_KEY}
            style={pageKeyStyle(false)}
          >
            <ChevronRight size={18} aria-hidden="true" />
          </button>
        </div>
      )}

      {/* The count and the size control close the row. ml-auto rather than
          justify-between on the parent, so they stay pinned right even at one
          page, when the strip is not rendered and there is nothing on the left
          to push against. */}
      <div className="ml-auto flex flex-wrap items-center gap-4">
        {/* The range is the honest version of a page number: "19-36 of 820"
            says where you are in the set, "page 2" only says how many clicks
            you have made. */}
        <p style={{ color: "var(--title-tx)" }} className="text-sm font-semibold tabular-nums" aria-live="polite">
          {total === 0
            ? "No results"
            : showAll
              ? `Results: all ${total.toLocaleString()}`
              : `Results: ${from.toLocaleString()} - ${to.toLocaleString()} of ${total.toLocaleString()}`}
        </p>
        <PageSizeSelect value={pageSize} total={total} onChange={onPageSize} />
      </div>
    </nav>
  );
}

/* ─── page ────────────────────────────────────────────────────────────── */
function TrendsExplorerContent() {
  const router = useRouter();
  const pathname = usePathname();
  const searchParams = useSearchParams();
  // The open trend lives in the URL (?trend=<id>) so a refresh or a shared
  // link lands on the same detail view and browser back works naturally.
  const selectedId = searchParams.get("trend");
  const openTrend = (id: string) => router.push(`${pathname}?trend=${encodeURIComponent(id)}`);
  const closeTrend = () => router.push(pathname);

  const [market, setMarket] = useMarket();

  const [trends, setTrends] = useState<TrendListItem[] | null>(null);
  const [loadError, setLoadError] = useState<string | null>(null);
  // Set only on a 404 for the selected market: that market has no run yet
  // (Saudi is the only one tracked today), which is a normal empty state and
  // not an error worth an InlineError + retry button.
  const [marketNotFound, setMarketNotFound] = useState(false);
  const [query, setQuery] = useState("");
  const [filter, setFilter] = useState<"all" | Quadrant>("all");
  // Trends a user asked the assistant to build are stored alongside the ones
  // clustering discovered, measured and ranked identically. Provenance is the
  // only difference, so it is a filter rather than a separate screen.
  const [origin, setOrigin] = useState<"all" | "pipeline" | "chat">("all");
  const chatCount = useMemo(
    () => (trends ?? []).filter((t) => (t.origin ?? "pipeline") === "chat").length,
    [trends]
  );
  // Which cohorts a trend must have posts from. Empty means no cohort filter.
  const [cohorts, setCohorts] = useState<string[]>([]);
  // Cumulative by default: "month" is a real calendar month now, and it is
  // empty until scraping catches up with the current one.
  const [period, setPeriod] = useState<Period>("cumulative");
  const [reloadKey, setReloadKey] = useState(0);

  useEffect(() => {
    const ac = new AbortController();
    setTrends(null);
    setLoadError(null);
    setMarketNotFound(false);
    fetchTrends("micro", period, ac.signal, market)
      .then((r) => setTrends(r.trends))
      .catch((e) => {
        if (isAbort(e)) return;
        if (market && e instanceof Error && e.message.startsWith("404")) {
          setTrends([]);
          setMarketNotFound(true);
          return;
        }
        setLoadError(friendlyTrendError(e));
      });
    return () => ac.abort();
  }, [period, reloadKey, market]);

  const retry = useCallback(() => setReloadKey((k) => k + 1), []);
  const loading = trends === null && loadError === null;

  const rows = useMemo(
    () => (trends ?? []).filter((t) =>
      (filter === "all" || t.quadrant === filter) &&
      (origin === "all" || (t.origin ?? "pipeline") === origin) &&
      // Every selected cohort must be present, not merely one of them: picking
      // Brands and Influencers asks for the trends both are posting about, so
      // two picks narrows the list rather than widening it. An empty selection
      // filters nothing, because [].every() is true.
      cohorts.every((c) => ((t.source_mix ?? {})[c as Source] ?? 0) > 0) &&
      t.name.toLowerCase().includes(query.toLowerCase())
    ),
    [trends, query, filter, origin, cohorts]
  );

  /* ── paging ── */
  // The server snapshot is null so the first paint matches the markup React
  // rendered on the server; the stored value arrives on hydration.
  const pageSize = normalisePageSize(
    useSyncExternalStore(pageSizeStore.subscribe, pageSizeStore.read, () => null)
  );
  const [page, setPage] = useState(1);
  const gridTopRef = useRef<HTMLDivElement>(null);

  // Changing a filter puts the reader back at the start. Adjusted during
  // render against the previous value rather than in an effect: an effect
  // would paint page 12 of a two-page result first and correct it after, and
  // the reader sees that flash.
  const filterKey = `${query}|${filter}|${origin}|${cohorts.join(",")}|${period}|${market}`;
  const [lastFilterKey, setLastFilterKey] = useState(filterKey);
  if (filterKey !== lastFilterKey) {
    setLastFilterKey(filterKey);
    setPage(1);
  }

  const total = rows.length;
  const pageCount = pageSize === ALL_PAGE_SIZE ? 1 : Math.max(1, Math.ceil(total / pageSize));
  // Clamped on read rather than written back: a filter that shrinks the set
  // while the reader sits on page 12 should show them page 3, not an empty
  // grid, and clamping here means no extra render to get there.
  const current = Math.min(page, pageCount);
  const start = pageSize === ALL_PAGE_SIZE ? 0 : (current - 1) * pageSize;
  const pageRows = pageSize === ALL_PAGE_SIZE ? rows : rows.slice(start, start + pageSize);

  const goToPage = useCallback((next: number) => {
    setPage(next);
    // Back to the top of the grid, not the top of the document: the filter row
    // stays in view so the reader keeps the context they just paged within.
    gridTopRef.current?.scrollIntoView({ behavior: "smooth", block: "start" });
  }, []);

  const changePageSize = useCallback((size: number) => {
    pageSizeStore.write(size);
    setPage(1);
  }, []);

  return (
    <MotionConfig reducedMotion="user">
      <div className="w-full">
        <DashboardTopbar title="Trends Explorer" accessory={<TopbarSearch />} />

        <div className="mx-auto max-w-[1500px] space-y-6 p-6 sm:p-8">
          {selectedId ? (
            <TrendDetailView trendId={selectedId} market={market} onBack={closeTrend} />
          ) : (
            <>
              <section className="chart-card rounded-2xl p-6">
                <div className="flex flex-col gap-5 lg:flex-row lg:items-center lg:justify-between">
                  <div className="flex items-center gap-3">
                    <div className="flex h-12 w-12 shrink-0 items-center justify-center rounded-2xl"
                      style={{ background: "var(--fi-solid)", color: "var(--fi-solid-tx)" }}>
                      <TrendingUp size={22} aria-hidden="true" />
                    </div>
                    <div>
                      <h1 style={{ color: "var(--title-tx)" }} className="text-2xl font-bold tracking-tight">Explore Trends</h1>
                      <p style={{ color: "var(--muted-tx)" }} className="text-sm">
                        {market
                          ? `Trends from brand and influencer posts in ${market === "AE" ? "the UAE" : "Saudi Arabia"}. Open one for the full breakdown.`
                          : "Live trends generated from community posts, open one for the full breakdown"}
                      </p>
                    </div>
                  </div>

                  <div className="relative w-full lg:w-80">
                    <label htmlFor="trend-search" className="sr-only">Search trends</label>
                    <input
                      id="trend-search"
                      value={query}
                      onChange={(e) => setQuery(e.target.value)}
                      placeholder="Search trends"
                      style={{ background: "var(--card-bg-2)", border: "1px solid var(--card-bd)", color: "var(--title-tx)" }}
                      className="min-h-11 w-full rounded-xl px-4 py-2.5 text-sm"
                    />
                  </div>
                </div>

                <div className="mt-5 flex min-h-[3.25rem] flex-wrap items-center gap-2 pt-4" style={{ borderColor: "var(--card-bd)" }}>
                  {(["cumulative", "month"] as Period[]).map((p) => {
                    const on = period === p;
                    return (
                      <button key={p} onClick={() => setPeriod(p)} aria-pressed={on}
                        className="min-h-11 rounded-full px-3.5 py-1.5 text-xs font-semibold transition-colors"
                        style={{ background: on ? "var(--fi-solid)" : "var(--card-bg-2)", color: on ? "var(--fi-solid-tx)" : "var(--body-tx)", border: `1px solid ${on ? "var(--fi-solid)" : "var(--card-bd)"}` }}>
                        {p === "cumulative" ? "All history" : "This month"}
                      </button>
                    );
                  })}
                  <span className="mx-1 h-5 w-px" style={{ background: "var(--card-bd)" }} aria-hidden="true" />
                  <MarketSelect market={market} onChange={setMarket} markets={MARKETS} />
                  <FilterDropdown
                    label="Trend type"
                    allLabel="All trends"
                    options={FILTERS.filter((f): f is Quadrant => f !== "all").map((q) => ({
                      value: q,
                      label: QUADRANT_META[q].label,
                      color: graphic(QUADRANT_META[q].token),
                    }))}
                    selected={filter === "all" ? [] : [filter]}
                    onChange={(next) => setFilter((next[0] as Quadrant) ?? "all")}
                  />
                  <FilterDropdown
                    label="Posts from"
                    allLabel="All accounts"
                    multiple
                    options={FILTER_COHORTS.map((c) => ({
                      value: c,
                      label: SOURCE_META[c].label,
                      color: graphic(SOURCE_META[c].token),
                    }))}
                    selected={cohorts}
                    onChange={setCohorts}
                  />
                  {/* Provenance only earns a control once chat-built trends exist.
                      A dropdown rather than three pills: the row above already
                      carries period and quadrant, and the cohort filter needs
                      the width more than this does. */}
                  {chatCount > 0 && (
                    <FilterDropdown
                      label="Source"
                      allLabel="Any source"
                      options={[
                        { value: "pipeline", label: "Discovered" },
                        { value: "chat", label: "Chat-generated" },
                      ]}
                      selected={origin === "all" ? [] : [origin]}
                      onChange={(next) =>
                        setOrigin((next[0] as "pipeline" | "chat") ?? "all")}
                    />
                  )}
                  {/* The set size used to be reported here too. The pagination
                      row states it as "Results: 19 - 36 of 820", which is the
                      same fact next to the control that acts on it, so this
                      copy was the reader's second chance to read one number. */}
                </div>
              </section>

              {/* cards */}
              {loadError ? (
                <InlineError message={loadError} onRetry={retry} />
              ) : loading ? (
                <>
                  <LoadingAnnouncer label="Loading trends" />
                  <CardGridSkeleton count={6} className={CARD_GRID} />
                </>
              ) : marketNotFound ? (
                <div className="chart-card flex flex-col items-center gap-3 rounded-2xl py-20 text-center">
                  <p style={{ color: "var(--muted-tx)" }} className="text-sm">
                    No trends have been generated for this market yet.
                  </p>
                </div>
              ) : rows.length === 0 ? (
                <div className="chart-card flex flex-col items-center gap-3 rounded-2xl py-20 text-center">
                  <p style={{ color: "var(--muted-tx)" }} className="text-sm">
                    {period === "month" && (trends?.length ?? 0) === 0
                      ? "No posts were collected this month, so no trends were active."
                      : "No trends match your search."}
                  </p>
                  {period === "month" && (trends?.length ?? 0) === 0 && (
                    <button onClick={() => setPeriod("cumulative")}
                      className="min-h-11 rounded-full px-4 py-1.5 text-xs font-semibold"
                      style={{ background: "var(--fi-solid)", color: "var(--fi-solid-tx)" }}>
                      View all history instead
                    </button>
                  )}
                </div>
              ) : (
                <>
                  {/* Scroll anchor: sits above the grid so paging returns the
                      reader to the first card, not to the page header. */}
                  <div ref={gridTopRef} className="scroll-mt-24" />
                  <div className={CARD_GRID}>
                    {pageRows.map((t, i) => (
                      // Keyed by page as well as id so a card in slot 3 on the
                      // new page is a new element, not a mutation of slot 3
                      // from the old one - otherwise React reuses the node and
                      // the entrance never plays.
                      <TrendSnapshotCard key={`${current}-${t.id}`} t={t} i={i} onSelect={() => openTrend(t.id)} />
                    ))}
                  </div>
                  <TrendPagination
                    page={current}
                    pageCount={pageCount}
                    pageSize={pageSize}
                    total={total}
                    from={start + 1}
                    to={start + pageRows.length}
                    onPage={goToPage}
                    onPageSize={changePageSize}
                  />
                </>
              )}
            </>
          )}
        </div>
      </div>
    </MotionConfig>
  );
}

export default function TrendsExplorerPage() {
  return (
    <Suspense fallback={
      <div className="w-full">
        <DashboardTopbar title="Trends Explorer" accessory={<TopbarSearch />} />
        <div className="mx-auto max-w-[1500px] space-y-6 p-6 sm:p-8">
          <Skel className="h-40 rounded-2xl" />
          <CardGridSkeleton count={6} className={CARD_GRID} />
        </div>
      </div>
    }>
      <TrendsExplorerContent />
    </Suspense>
  );
}
