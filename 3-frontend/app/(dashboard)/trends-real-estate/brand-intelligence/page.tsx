"use client";

import { useMemo, useState } from "react";
import Link from "next/link";
import { motion, MotionConfig } from "framer-motion";
import {
  ResponsiveContainer, RadarChart, Radar, PolarGrid, PolarAngleAxis, PolarRadiusAxis, Tooltip,
} from "recharts";
import { ExternalLink, Sparkles } from "lucide-react";

import DashboardTopbar from "@/components/layout/DashboardTopbar";
import {
  TopbarSearch, BarRowsSkeleton, InlineBarsSkeleton, ChartSkeleton, EmptyNote,
  InlineError, BrandSelect, PanelState, radarTickFill, chartGridStroke, Skel,
} from "@/components/ui/RealEstateTrendsPanels";
import { CHART_SERIES } from "@/lib/realEstateTrendsPalette";
import { useAsyncResource, type Resource } from "@/lib/useAsyncResource";
import {
  fetchBrands, fetchBrandOverview, fetchBrandThemes, fetchBrandOfferings, fetchBrandTopContent,
  fetchBrandFunctionalVisual, fetchBrandSemiotic, fetchBrandTrendParticipation,
  fetchBrandTrendOpportunities,
  type TrendParticipationResponse, type TrendOpportunitiesResponse,
  type FacetAgg, type TopContentItem,
  type FunctionalVisualCategory,
} from "@/lib/realEstateTrendsApi";

const EMPTY_H = 288;
const VISUAL_PENDING = "Image analysis for this brand is still being processed. Check back shortly.";

/* ─── helpers ─────────────────────────────────────────────────────────── */
function compact(n: number) {
  if (n >= 1_000_000) return `${(n / 1_000_000).toFixed(1).replace(/\.0$/, "")}M`;
  if (n >= 1000) return `${(n / 1000).toFixed(1).replace(/\.0$/, "")}K`;
  return `${n}`;
}
function safeNum(n: number | null | undefined) {
  return typeof n === "number" && Number.isFinite(n) ? n : 0;
}
function clampPct(n: number) {
  return Math.max(0, Math.min(100, safeNum(n)));
}
function initials(name: string) {
  const p = name.trim().split(/\s+/);
  return (p.length >= 2 ? p[0][0] + p[1][0] : name.slice(0, 2)).toUpperCase();
}
function monthLabel(iso: string | null | undefined) {
  if (!iso) return null;
  const d = new Date(iso);
  if (Number.isNaN(d.getTime())) return null;
  return d.toLocaleDateString("en-US", { month: "short", year: "numeric" });
}
const TOOLTIP_STYLE = {
  background: "var(--dropdown-bg)",
  border: "1px solid var(--card-bd)",
  borderRadius: 12,
  color: "var(--title-tx)",
  fontSize: 12,
};

function Panel({
  title, subtitle, resource, skeleton, emptyNote, emptyMinHeight, isEmpty, children,
}: {
  title: string;
  subtitle: string;
  resource: Pick<Resource<unknown>, "loading" | "error" | "reload">;
  skeleton: React.ReactNode;
  emptyNote: string;
  emptyMinHeight?: number;
  isEmpty: boolean;
  children: React.ReactNode;
}) {
  return (
    <div className="chart-card rounded-2xl p-6">
      <h3 style={{ color: "var(--title-tx)" }} className="text-base font-semibold">{title}</h3>
      <p style={{ color: "var(--muted-tx)" }} className="mb-5 text-xs">{subtitle}</p>
      <PanelState
        loading={resource.loading}
        error={resource.error}
        isEmpty={isEmpty}
        emptyNote={emptyNote}
        emptyMinHeight={emptyMinHeight}
        skeleton={skeleton}
        loadingLabel={`Loading ${title.toLowerCase()}`}
        onRetry={resource.reload}
      >
        {children}
      </PanelState>
    </div>
  );
}

/* ─── Communication Themes ───────────────────────────────────────────── */
function ThemesPanel({ resource }: { resource: Resource<FacetAgg[]> }) {
  const items = resource.data ?? [];
  const max = Math.max(1, ...items.map((t) => safeNum(t.post_count)));
  return (
    <Panel
      title="Communication Themes"
      subtitle="Topics the brand consistently communicates"
      resource={resource}
      skeleton={<BarRowsSkeleton rows={8} />}
      isEmpty={items.length === 0}
      emptyNote="Not enough repeated evidence yet to surface communication themes."
      emptyMinHeight={204}
    >
      <div className="space-y-4">
        {items.map((t, i) => (
          <div key={t.label ?? i}>
            <div className="mb-1 flex items-center justify-between gap-3">
              <span dir="auto" style={{ color: "var(--title-tx)" }} className="min-w-0 truncate text-sm font-medium">{t.label}</span>
              <span style={{ color: "var(--muted-tx)" }} className="shrink-0 text-xs font-semibold tabular-nums">{safeNum(t.post_count)}</span>
            </div>
            <div className="h-2 w-full overflow-hidden rounded-full" style={{ background: "var(--card-bg-2)" }}>
              <div className="h-full rounded-full" style={{ width: `${clampPct((safeNum(t.post_count) / max) * 100)}%`, background: "linear-gradient(90deg, var(--accent-from), var(--accent-to))" }} />
            </div>
          </div>
        ))}
      </div>
    </Panel>
  );
}

/* ─── Offering Focus ──────────────────────────────────────────────────── */
function OfferingsPanel({ resource }: { resource: Resource<FacetAgg[]> }) {
  const items = resource.data ?? [];
  const max = Math.max(1, ...items.map((p) => safeNum(p.post_count)));
  return (
    <Panel
      title="Offering Focus"
      subtitle="Most discussed offerings"
      resource={resource}
      skeleton={<InlineBarsSkeleton rows={8} />}
      isEmpty={items.length === 0}
      emptyNote="Not enough repeated evidence yet to surface offering focus."
      emptyMinHeight={204}
    >
      <div className="space-y-3">
        {items.map((p, i) => (
          <div key={p.offering ?? i} className="flex items-center gap-3">
            <span
              title={p.offering_native ? `${p.offering} (${p.offering_native})` : p.offering}
              style={{ color: "var(--body-tx)" }}
              className="flex w-28 shrink-0 items-baseline justify-end gap-1 truncate text-right text-xs xl:w-40"
            >
              <span dir="ltr" className="truncate">{p.offering}</span>
              {p.offering_native && (
                <span dir="rtl" style={{ color: "var(--muted-tx)" }} className="shrink-0">
                  ({p.offering_native})
                </span>
              )}
            </span>
            <div className="h-3 flex-1 overflow-hidden rounded-full" style={{ background: "var(--card-bg-2)" }}>
              <div className="h-full rounded-full" style={{ width: `${clampPct((safeNum(p.post_count) / max) * 100)}%`, background: "linear-gradient(90deg, var(--accent2-from), var(--accent2-to))" }} />
            </div>
          </div>
        ))}
      </div>
    </Panel>
  );
}

/* ─── Trend Opportunities ────────────────────────────────────────────── */
function TrendOpportunities({ resource }: { resource: Resource<TrendOpportunitiesResponse> }) {
  const items = resource.data?.opportunities ?? [];
  return (
    <div className="chart-card rounded-2xl p-6">
      <div className="mb-4">
        <h3 style={{ color: "var(--title-tx)" }} className="text-base font-semibold">Trend Opportunities</h3>
        <p style={{ color: "var(--muted-tx)" }} className="text-xs">
          Trends this brand has no posts in, that competitors are already active in
        </p>
      </div>

      <PanelState
        loading={resource.loading}
        error={resource.error}
        isEmpty={items.length === 0}
        emptyNote="No open trends where a tracked competitor is present and this brand is not."
        emptyMinHeight={120}
        loadingLabel="Loading trend opportunities"
        onRetry={resource.reload}
        skeleton={
          <div className="grid grid-cols-2 gap-4 lg:grid-cols-4" aria-hidden="true">
            {Array.from({ length: 4 }).map((_, i) => (
              <div key={i} className="rounded-xl p-4" style={{ background: "var(--card-bg-2)", border: "1px solid var(--card-bd)" }}>
                <Skel className="h-4 w-3/4" />
                <Skel className="mt-2 h-6 w-16" />
                <Skel className="mt-2 h-3 w-full" />
              </div>
            ))}
          </div>
        }
      >
        <div className="grid grid-cols-2 gap-4 lg:grid-cols-4">
          {items.map((o) => (
            <Link
              key={o.trend_id}
              href={`/trends-real-estate/trends-explorer?trend=${encodeURIComponent(o.trend_id)}`}
              className="flex flex-col rounded-xl p-4 transition-all hover:-translate-y-0.5 hover:shadow-md"
              style={{ background: "var(--card-bg-2)", border: "1px solid var(--card-bd)" }}
            >
              <div dir="auto" style={{ color: "var(--body-tx)" }} className="text-sm font-medium">{o.name}</div>
              <div className="mt-2 flex items-baseline gap-1.5">
                <span style={{ color: "var(--accent-tx)" }} className="text-3xl font-bold tabular-nums">
                  {o.competitors}
                </span>
                <span style={{ color: "var(--muted-tx)" }} className="text-xs">
                  {o.competitors === 1 ? "competitor" : "competitors"} active
                </span>
              </div>
              {o.competitor_names.length > 0 && (
                <div dir="auto" style={{ color: "var(--muted-tx)" }} className="mt-1 text-xs">
                  {o.competitor_names.join(", ")}
                </div>
              )}
              <div style={{ color: "var(--muted-tx)" }} className="mt-2 flex flex-wrap gap-x-2 text-xs tabular-nums">
                <span>Growth {o.growth}</span>
                <span aria-hidden="true">·</span>
                <span>{o.trend_posts.toLocaleString()} posts in trend</span>
              </div>
              <div style={{ color: "var(--muted-tx)" }} className="mt-1 text-xs tabular-nums">
                based on {o.competitor_posts} competitor {o.competitor_posts === 1 ? "post" : "posts"}
              </div>
            </Link>
          ))}
        </div>
      </PanelState>
    </div>
  );
}

/* ─── Trend Participation ────────────────────────────────────────────── */
function TrendParticipation({ resource }: { resource: Resource<TrendParticipationResponse> }) {
  const data = resource.data;
  return (
    <div className="chart-card rounded-2xl p-6">
      <div className="mb-4">
        <h3 style={{ color: "var(--title-tx)" }} className="text-base font-semibold">Trend Participation</h3>
        <p style={{ color: "var(--muted-tx)" }} className="text-xs">
          {data
            ? `${data.posts_in_trends} of this brand's ${data.posts_in_corpus} posts joined a trend`
            : "Trends this brand's posts were assigned to"}
        </p>
      </div>

      <PanelState
        loading={resource.loading}
        error={resource.error}
        isEmpty={!data?.trends.length}
        emptyNote="None of this brand's posts were assigned to a trend in the latest run."
        emptyMinHeight={120}
        loadingLabel="Loading trend participation"
        onRetry={resource.reload}
        skeleton={
          <div className="grid grid-cols-2 gap-4 lg:grid-cols-4" aria-hidden="true">
            {Array.from({ length: 4 }).map((_, i) => (
              <div key={i} className="rounded-xl p-4" style={{ background: "var(--card-bg-2)", border: "1px solid var(--card-bd)" }}>
                <Skel className="h-4 w-3/4" />
                <Skel className="mt-2 h-8 w-12" />
                <Skel className="mt-2 h-3 w-full" />
              </div>
            ))}
          </div>
        }
      >
        <div className="grid grid-cols-2 gap-4 lg:grid-cols-4">
          {(data?.trends ?? []).map((t) => (
            <Link
              key={t.trend_id}
              href={`/trends-real-estate/trends-explorer?trend=${encodeURIComponent(t.trend_id)}`}
              className="rounded-xl p-4 transition-all hover:-translate-y-0.5 hover:shadow-md"
              style={{ background: "var(--card-bg-2)", border: "1px solid var(--card-bd)" }}
            >
              <div dir="auto" style={{ color: "var(--body-tx)" }} className="text-sm font-medium">{t.name}</div>
              <div style={{ color: "var(--accent-tx)" }} className="mt-1 text-3xl font-bold tabular-nums">
                {t.posts}
              </div>
              <div style={{ color: "var(--muted-tx)" }} className="text-xs">
                {t.posts === 1 ? "post" : "posts"} · {t.share_pct}% of its trend posts
              </div>
            </Link>
          ))}
        </div>
      </PanelState>
    </div>
  );
}

/* ─── Functional Analysis ────────────────────────────────────────────── */
function FunctionalVisual({ resource }: { resource: Resource<FunctionalVisualCategory[]> }) {
  const items = resource.data ?? [];
  return (
    <Panel
      title="Functional Analysis"
      subtitle="What the brand shows in its imagery"
      resource={resource}
      skeleton={<InlineBarsSkeleton rows={5} />}
      isEmpty={items.length === 0}
      emptyNote={VISUAL_PENDING}
      emptyMinHeight={EMPTY_H}
    >
      <div className="space-y-4">
        {items.map((v) => (
          <div key={v.category} className="flex items-center gap-3">
            <span dir="auto" title={v.category} style={{ color: "var(--body-tx)" }} className="w-28 shrink-0 truncate text-right text-xs xl:w-40">{v.category}</span>
            <div className="h-3 flex-1 overflow-hidden rounded-full" style={{ background: "var(--card-bg-2)" }}>
              <div className="h-full rounded-full" style={{ width: `${clampPct(v.pct)}%`, background: "linear-gradient(90deg, var(--accent-from), var(--accent-to))" }} />
            </div>
            <span style={{ color: "var(--muted-tx)" }} className="w-10 shrink-0 text-right text-xs tabular-nums">{Math.round(clampPct(v.pct))}%</span>
          </div>
        ))}
      </div>
    </Panel>
  );
}

/* ─── Semiotic Positioning: radar ────────────────────────────────────── */
function SemioticRadar({ resource, brandName }: {
  resource: Resource<Record<string, number>>; brandName: string;
}) {
  const axes = resource.data ?? {};
  const data = Object.entries(axes).map(([axis, value]) => ({ axis, value: safeNum(value) }));
  const tickFill = radarTickFill();
  const gridStroke = chartGridStroke();
  return (
    <Panel
      title={`Semiotic Positioning: ${brandName || "Brand"}`}
      subtitle="How the developer represents property"
      resource={resource}
      skeleton={<ChartSkeleton height={288} />}
      isEmpty={data.length === 0}
      emptyNote={VISUAL_PENDING}
      emptyMinHeight={EMPTY_H}
    >
      <div className="h-72 w-full" style={{ color: CHART_SERIES[0] }}>
        <ResponsiveContainer width="100%" height="100%">
          <RadarChart data={data} outerRadius="68%">
            <PolarGrid stroke={gridStroke} />
            <PolarAngleAxis dataKey="axis" tick={{ fontSize: 12, fill: tickFill }} />
            <PolarRadiusAxis domain={[0, 100]} tickCount={3} tick={{ fontSize: 10, fill: tickFill }} axisLine={false} />
            <Tooltip formatter={(v) => `${Math.round(Number(v ?? 0))}%`} contentStyle={TOOLTIP_STYLE} />
            <Radar dataKey="value" stroke="currentColor" strokeWidth={2} fill="currentColor" fillOpacity={0.22} isAnimationActive={false} />
          </RadarChart>
        </ResponsiveContainer>
      </div>
    </Panel>
  );
}

/* ─── Top-Performing Content ─────────────────────────────────────────── */
function TopContentPanel({ resource }: { resource: Resource<TopContentItem[]> }) {
  const items = resource.data ?? [];
  return (
    <div>
      <h3 style={{ color: "var(--title-tx)" }} className="mb-4 text-base font-semibold">Top-Performing Content</h3>
      <PanelState
        loading={resource.loading}
        error={resource.error}
        isEmpty={items.length === 0}
        emptyNote="No content available for this brand yet."
        emptyMinHeight={240}
        loadingLabel="Loading top-performing content"
        onRetry={resource.reload}
        skeleton={
          <div className="grid grid-cols-1 gap-4 md:grid-cols-2" aria-hidden="true">
            {Array.from({ length: 4 }).map((_, i) => (
              <div key={i} className="chart-card rounded-2xl p-5">
                <div className="flex items-start justify-between gap-3">
                  <Skel className="h-4 w-1/3" />
                  <Skel className="h-4 w-24" />
                </div>
                <Skel className="mt-4 h-3 w-full" />
                <Skel className="mt-2 h-3 w-full" />
                <Skel className="mt-2 h-3 w-2/3" />
              </div>
            ))}
          </div>
        }
      >
        <div className="grid grid-cols-1 gap-4 md:grid-cols-2">
          {items.map((post) => {
            const eng = safeNum(post.engagement?.total ?? (safeNum(post.engagement?.likes) + safeNum(post.engagement?.comments)));
            const card = (
              <div className="chart-card h-full rounded-2xl p-5 transition-all group-hover:-translate-y-0.5 group-hover:shadow-md">
                <div className="mb-2 flex items-start justify-between gap-3">
                  <div className="min-w-0">
                    <div dir="auto" style={{ color: "var(--title-tx)" }} className="truncate text-sm font-semibold">{post.owner?.name || post.owner?.username || "Post"}</div>
                    {post.owner?.username && <div style={{ color: "var(--muted-tx)" }} className="truncate text-xs">@{post.owner.username}</div>}
                  </div>
                  <span style={{ color: "var(--accent-tx)" }} className="flex shrink-0 items-center gap-1 text-xs font-semibold tabular-nums">
                    {compact(eng)} {eng === 1 ? "engagement" : "engagements"} {post.post_url && <ExternalLink size={12} aria-hidden="true" className="opacity-40 transition group-hover:opacity-100" />}
                  </span>
                </div>
                <p dir="auto" style={{ color: "var(--body-tx)" }} className="line-clamp-3 text-sm leading-relaxed">{post.text || ""}</p>
              </div>
            );
            return post.post_url ? (
              <a key={post.post_id} href={post.post_url} target="_blank" rel="noopener noreferrer" title="Open original post" className="group block rounded-2xl no-underline">{card}</a>
            ) : (
              <div key={post.post_id} className="group">{card}</div>
            );
          })}
        </div>
      </PanelState>
    </div>
  );
}

/* ─── page ────────────────────────────────────────────────────────────── */
export default function BrandIntelligencePage() {
  const brandList = useAsyncResource((s) => fetchBrands("brand", s), []);
  const brands = useMemo(() => brandList.data?.brands ?? [], [brandList.data]);

  const [selected, setSelected] = useSelectedBrand(brands);
  const on = selected.length > 0;

  const overview = useAsyncResource((s) => fetchBrandOverview(selected, s), [selected], { enabled: on });
  const themes = useAsyncResource(async (s) => (await fetchBrandThemes(selected, undefined, 12, s)).themes, [selected], { enabled: on });
  const offerings = useAsyncResource(async (s) => (await fetchBrandOfferings(selected, undefined, 12, s)).offerings, [selected], { enabled: on });
  const topContent = useAsyncResource(async (s) => (await fetchBrandTopContent(selected, 8, undefined, s)).items, [selected], { enabled: on });
  const functional = useAsyncResource(async (s) => (await fetchBrandFunctionalVisual(selected, s)).categories, [selected], { enabled: on });
  const semiotic = useAsyncResource(async (s) => (await fetchBrandSemiotic(selected, s)).axes, [selected], { enabled: on });
  const participation = useAsyncResource((s) => fetchBrandTrendParticipation(selected, s), [selected], { enabled: on });
  const opportunities = useAsyncResource((s) => fetchBrandTrendOpportunities(selected, s), [selected], { enabled: on });

  const pending = !on && !brandList.error;
  const gate = <T,>(r: Resource<T>): Resource<T> =>
    pending ? { ...r, loading: true, error: null } : r;

  const brandName = useMemo(
    () => overview.data?.name ?? brands.find((b) => b.key === selected)?.name ?? "",
    [overview.data, brands, selected]
  );

  const windowFrom = monthLabel(overview.data?.first_post_date);
  const windowTo = monthLabel(overview.data?.last_post_date);
  const windowLabel = windowFrom && windowTo ? (windowFrom === windowTo ? windowFrom : `${windowFrom} to ${windowTo}`) : null;
  const heroSummary = useMemo(() => {
    const parts = ["Cultural participation profile"];
    const posts = overview.data?.post_count;
    if (typeof posts === "number" && Number.isFinite(posts)) {
      parts.push(`${posts.toLocaleString()} ${posts === 1 ? "post" : "posts"} analysed`);
    }
    if (windowLabel) parts.push(windowLabel);
    return parts.join(" · ");
  }, [overview.data?.post_count, windowLabel]);

  const noBrands = !brandList.loading && !brandList.error && brands.length === 0;

  return (
    <MotionConfig reducedMotion="user">
      <div className="w-full">
        <DashboardTopbar title="Brand Intelligence" accessory={<TopbarSearch />} />

        <div className="mx-auto max-w-[1500px] space-y-6 p-6 sm:p-8">
          {/* select a brand */}
          <div className="flex flex-col gap-4 sm:flex-row sm:items-end sm:justify-between">
            <div>
              <h2 style={{ color: "var(--title-tx)" }} className="text-xl font-bold tracking-tight">Select a Brand</h2>
              <p style={{ color: "var(--muted-tx)" }} className="mt-0.5 text-sm">Understand how developers participate in culture</p>
              {noBrands && (
                <p style={{ color: "var(--muted-tx)" }} className="mt-2 max-w-md text-xs">
                  No brands are being tracked yet. Brands appear here once their social content has been processed.
                </p>
              )}
            </div>
            <BrandSelect brands={brands} value={selected} onChange={setSelected} loading={brandList.loading} label="Select a brand" />
          </div>

          {brandList.error && <InlineError message={brandList.error} onRetry={brandList.reload} />}

          {!brandList.error && !noBrands && (
            <>
              <motion.section initial={{ opacity: 0, y: 10 }} animate={{ opacity: 1, y: 0 }}
                transition={{ duration: 0.45, ease: [0.16, 1, 0.3, 1] }} className="chart-card rounded-2xl p-6">
                <div className="flex flex-wrap items-center justify-between gap-4">
                  <div className="flex items-center gap-4">
                    <div className="flex h-14 w-14 shrink-0 items-center justify-center rounded-2xl text-lg font-bold text-white" style={{ background: "linear-gradient(135deg, var(--accent-from), var(--accent2-from))" }}>
                      {brandName ? initials(brandName) : <Sparkles size={22} aria-hidden="true" />}
                    </div>
                    <div className="min-w-0">
                      {brandName ? (
                        <h2 dir="auto" style={{ color: "var(--title-tx)" }} className="truncate text-2xl font-bold tracking-tight">{brandName}</h2>
                      ) : (
                        <Skel className="h-8 w-48" />
                      )}
                      <p style={{ color: "var(--muted-tx)" }} className="mt-0.5 text-sm">
                        {heroSummary}
                      </p>
                    </div>
                  </div>
                  <span className="inline-flex items-center gap-1.5 rounded-full px-3 py-1 text-xs font-semibold" style={{ background: "var(--accent-soft)", color: "var(--accent-tx)", border: "1px solid var(--accent-soft-bd)" }}>
                    Tracked brand
                  </span>
                </div>
              </motion.section>

              <div className="grid grid-cols-1 gap-6 lg:grid-cols-2">
                <ThemesPanel resource={gate(themes)} />
                <OfferingsPanel resource={gate(offerings)} />
              </div>

              <TrendParticipation resource={gate(participation)} />

              <TrendOpportunities resource={gate(opportunities)} />

              <div className="grid grid-cols-1 gap-6 lg:grid-cols-2">
                <FunctionalVisual resource={gate(functional)} />
                <SemioticRadar resource={gate(semiotic)} brandName={brandName} />
              </div>

              <TopContentPanel resource={gate(topContent)} />
            </>
          )}

          {noBrands && <EmptyNote carded minHeight={EMPTY_H} message="Brand panels appear here once at least one tracked brand has been processed." />}
        </div>
      </div>
    </MotionConfig>
  );
}

function useSelectedBrand(brands: { key: string }[]): [string, (k: string) => void] {
  const [chosen, setChosen] = useState<string | null>(null);
  const selected = chosen ?? brands[0]?.key ?? "";
  return [selected, setChosen];
}
