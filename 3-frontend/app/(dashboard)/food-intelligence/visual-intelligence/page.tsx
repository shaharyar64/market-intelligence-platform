"use client";

import { useCallback, useEffect, useMemo, useState } from "react";
import { motion, MotionConfig } from "framer-motion";
import { ArrowDownRight, ArrowUpRight, Image as ImageIcon, RotateCw } from "lucide-react";

import DashboardTopbar from "@/components/layout/DashboardTopbar";
import {
  TopbarSearch, BarRowsSkeleton, InlineBarsSkeleton, InlineError,
  BrandSelect, PanelState, Skel,
} from "@/components/ui/FoodPanels";
import { useAsyncResource } from "@/lib/useAsyncResource";
import { graphic, text, type TokenFamily } from "@/lib/foodPalette";
import {
  fetchVisualCohorts, fetchVisualCohortAnalysis, fetchVisualTerritories, fetchVisualGallery,
  fetchBrands, fetchBrandOverview,
  type CohortCount, type CohortFacet, type GalleryItem, type BrandOverview,
} from "@/lib/foodIntelligence";

const MAX_TERRITORY_PILLS = 3;
const EMPTY_H = 288;
const GALLERY_STALE_MS = 14 * 60 * 1000;
const PROCESSING_NOTE = "Image analysis is still being processed. Check back shortly.";

const GALLERY_LAYOUT = [
  "col-span-2 xl:col-span-1 xl:row-span-2 xl:col-start-1 xl:row-start-1",
  "xl:col-start-2 xl:row-start-1",
  "xl:col-start-3 xl:row-start-1",
  "xl:col-start-2 xl:row-start-2",
  "xl:col-start-3 xl:row-start-2",
  "col-span-2 xl:col-span-1 xl:row-span-2 xl:col-start-4 xl:row-start-1",
];

const COHORT_META: Record<string, { label: string; token: TokenFamily; blurb: string }> = {
  brand: { label: "Brands", token: "growth", blurb: "Every post from the brands we track" },
  influencer: { label: "Influencers", token: "breakthrough", blurb: "Every post from the creators we track" },
  community: { label: "Communities", token: "mainstream", blurb: "A stratified sample of consumer posts" },
};

const COHORT_ORDER = ["brand", "influencer", "community"] as const;

function galleryGridClass(mosaic: boolean) {
  return mosaic
    ? "grid grid-cols-2 gap-4 lg:grid-cols-3 xl:grid-cols-4 xl:grid-rows-2 xl:h-[460px]"
    : "grid grid-cols-2 gap-4 lg:grid-cols-3 xl:grid-cols-4";
}

function galleryTileClass(mosaic: boolean, i: number) {
  return mosaic ? `aspect-[4/3] xl:aspect-auto xl:h-full ${GALLERY_LAYOUT[i]}` : "aspect-[4/3]";
}

function compact(n: number) {
  if (n >= 1000000) return `${(n / 1000000).toFixed(1)}m`;
  if (n >= 1000) return `${Math.round(n / 1000)}k`;
  return String(n);
}

function GalleryImageTile({ item, className }: { item: GalleryItem; className?: string }) {
  const [failed, setFailed] = useState(false);
  const [loaded, setLoaded] = useState(false);
  const label = item.brand_name || "";
  const src = item.image_url;
  const showImage = !failed && !!src;

  return (
    <div
      className={`relative overflow-hidden rounded-2xl ${className ?? ""}`}
      style={{ background: "var(--card-bg-2)", border: "1px solid var(--card-bd)" }}
    >
      <div className="absolute inset-0 flex items-center justify-center">
        <ImageIcon size={26} style={{ color: "var(--muted-tx)", opacity: 0.45 }} aria-hidden="true" />
      </div>
      {showImage && (
        // eslint-disable-next-line @next/next/no-img-element
        <img
          src={src as string}
          alt={label ? `Post image from ${label}` : "Food post image"}
          loading="lazy"
          decoding="async"
          onLoad={() => setLoaded(true)}
          onError={() => setFailed(true)}
          className={`relative h-full w-full object-cover transition-opacity duration-300 ${loaded ? "opacity-100" : "opacity-0"}`}
        />
      )}
      <div className="absolute inset-x-0 bottom-0 p-3" style={{ background: "linear-gradient(to top, rgba(0,0,0,0.62), transparent)" }}>
        <div dir="auto" className="truncate text-sm font-semibold text-white">{label || "Untitled"}</div>
        {item.caption && <div dir="auto" className="line-clamp-1 text-xs text-white/90">{item.caption}</div>}
      </div>
    </div>
  );
}

const TERRITORY_COPY: Record<string, string> = {
  indulgent: "Indulgent", modern: "Modern", traditional: "Traditional",
  natural: "Natural", sophisticated: "Sophisticated", healthy: "Healthy",
  premium: "Premium",
};

function CohortTabs({ counts, value, onChange, loading }: {
  counts: CohortCount[]; value: string; onChange: (v: string) => void; loading: boolean;
}) {
  const byType = new Map(counts.map((c) => [c.account_type, c.analysed_posts]));
  return (
    <div role="tablist" aria-label="Cohort" className="flex flex-wrap items-center gap-1 rounded-2xl p-1.5"
      style={{ background: "var(--card-bg)", border: "1px solid var(--card-bd)" }}>
      {COHORT_ORDER.map((type) => {
        const meta = COHORT_META[type];
        const active = type === value;
        const posts = byType.get(type);
        return (
          <button
            key={type}
            role="tab"
            aria-selected={active}
            onClick={() => onChange(type)}
            className="flex min-h-11 items-center gap-2 rounded-xl px-4 py-2 text-sm font-semibold transition-colors"
            style={{
              background: active ? `var(--fi-${meta.token}-soft)` : "transparent",
              color: active ? text(meta.token) : "var(--muted-tx)",
              boxShadow: active ? `inset 0 0 0 1.5px ${graphic(meta.token)}` : "none",
            }}
          >
            <span className="h-2 w-2 rounded-full" style={{ background: graphic(meta.token) }} aria-hidden="true" />
            {meta.label}
            <span className="text-xs font-normal tabular-nums" style={{ color: "var(--muted-tx)" }}>
              {loading && posts === undefined
                ? <Skel className="inline-block h-3 w-7 align-middle" />
                : posts === undefined ? "—" : compact(posts)}
            </span>
          </button>
        );
      })}
    </div>
  );
}

function TerritoryGrowthPanel({ resource, whose }: {
  resource: ReturnType<typeof useAsyncResource<Awaited<ReturnType<typeof fetchVisualTerritories>>>>;
  whose: string;
}) {
  const data = resource.data;
  const rows = data?.territories ?? [];
  return (
    <div className="chart-card rounded-2xl p-6">
      <div className="mb-4">
        <h3 style={{ color: "var(--title-tx)" }} className="text-base font-semibold">Trend Visual Territories</h3>
        {/* Naming the cohort in the subtitle: both tracked cohorts happen to
            lead with the same territory, so without it the panel reads as
            frozen when it has in fact reloaded. */}
        <p style={{ color: "var(--muted-tx)" }} className="text-xs">
          Which visual territories are growing fastest among {whose}
        </p>
      </div>
      <PanelState
        loading={resource.loading}
        error={resource.error}
        isEmpty={rows.length === 0}
        emptyNote="Not enough analysed posts to compare two windows yet."
        emptyMinHeight={140}
        loadingLabel="Loading visual territories"
        onRetry={resource.reload}
        skeleton={<InlineBarsSkeleton rows={4} />}
      >
        <>
          <div className="grid grid-cols-1 gap-3 sm:grid-cols-2 lg:grid-cols-3">
            {rows.map((t) => {
              const down = t.growth_pct < 0;
              return (
                <div key={t.territory} className="flex items-center justify-between rounded-xl px-4 py-3"
                     style={{ background: "var(--card-bg-2)", border: "1px solid var(--card-bd)" }}>
                  <div className="min-w-0">
                    <div style={{ color: "var(--title-tx)" }} className="truncate text-sm font-medium">
                      {TERRITORY_COPY[t.territory] ?? t.territory}
                    </div>
                    {/* The share is the honest headline: a territory can gain
                        ground while still being small, and lose it while still
                        being the largest. */}
                    <div style={{ color: "var(--muted-tx)" }} className="text-xs tabular-nums">
                      {t.share_pct}% of posts · {t.recent_posts} vs {t.previous_posts}
                    </div>
                  </div>
                  <span className="flex shrink-0 items-center gap-1 text-sm font-bold tabular-nums"
                        style={{ color: down ? "var(--fi-danger-tx)" : "var(--fi-growth-tx)" }}>
                    {down ? <ArrowDownRight size={14} aria-hidden="true" /> : <ArrowUpRight size={14} aria-hidden="true" />}
                    {Math.abs(t.growth_pct)}%
                  </span>
                </div>
              );
            })}
          </div>
          <p style={{ color: "var(--muted-tx)" }} className="mt-3 text-xs">
            Share of posts in the last {data?.window_days ?? 56} days
            {data?.as_of ? ` to ${data.as_of}` : ""}, against the {data?.window_days ?? 56} before it
            {data?.basis ? ` · ${data.basis}` : ""}. A post can read as more than one
            territory, so these do not add up to 100%.
          </p>
        </>
      </PanelState>
    </div>
  );
}

function FacetPanel({ title, subtitle, items, color, loading, error, emptyNote, onRetry }: {
  title: string; subtitle: string; items: CohortFacet[]; color: string;
  loading: boolean; error: string | null; emptyNote: string; onRetry: () => void;
}) {
  // Bars are scaled against the top row rather than the total: these are
  // overlapping labels (a post carries several themes), so a share-of-total
  // would not add to 100 and would read as if something were missing.
  const max = items.length ? Math.max(...items.map((i) => i.post_count)) : 0;
  return (
    <div className="chart-card rounded-2xl p-6">
      <div className="mb-4">
        <h3 style={{ color: "var(--title-tx)" }} className="text-base font-semibold">{title}</h3>
        <p style={{ color: "var(--muted-tx)" }} className="text-xs">{subtitle}</p>
      </div>
      <PanelState
        loading={loading} error={error} isEmpty={items.length === 0}
        emptyNote={emptyNote} emptyMinHeight={260}
        loadingLabel={`Loading ${title.toLowerCase()}`}
        onRetry={onRetry}
        skeleton={<BarRowsSkeleton rows={8} />}
      >
        <ul className="space-y-2.5">
          {items.map((it) => {
            const label = it.product ?? it.label;
            const native = it.product_native ?? it.label_native;
            return (
              <li key={label}>
                <div className="mb-1 flex items-baseline justify-between gap-3">
                  <span style={{ color: "var(--body-tx)" }} className="flex min-w-0 items-baseline gap-1.5 text-sm">
                    <span dir="ltr" className="truncate">{label}</span>
                    {native && (
                      <span dir="rtl" style={{ color: "var(--muted-tx)" }} className="shrink-0 text-xs">
                        ({native})
                      </span>
                    )}
                  </span>
                  <span style={{ color: "var(--muted-tx)" }} className="shrink-0 text-xs tabular-nums">{it.post_count}</span>
                </div>
                <div className="h-1.5 w-full overflow-hidden rounded-full" style={{ background: "var(--card-bg-2)" }}>
                  <div className="h-full rounded-full" style={{ width: `${max ? (it.post_count / max) * 100 : 0}%`, background: color }} />
                </div>
              </li>
            );
          })}
        </ul>
      </PanelState>
    </div>
  );
}

function ImageGallery({ items, loading, error, stale, onRefresh, onRetry }: {
  items: GalleryItem[];
  loading: boolean;
  error: string | null;
  stale: boolean;
  onRefresh: () => void;
  onRetry: () => void;
}) {
  const visible = items.slice(0, GALLERY_LAYOUT.length);
  const mosaic = visible.length === GALLERY_LAYOUT.length;
  const skeletonCount = visible.length > 0 ? visible.length : GALLERY_LAYOUT.length;
  const skeletonMosaic = skeletonCount === GALLERY_LAYOUT.length;

  return (
    <div>
      <div className="mb-4 flex flex-wrap items-start justify-between gap-3">
        <div>
          <h3 style={{ color: "var(--title-tx)" }} className="text-base font-semibold">Image Gallery</h3>
          <p style={{ color: "var(--muted-tx)" }} className="text-xs">Imagery this cohort is publishing right now</p>
        </div>
        {stale && !loading && (
          <button
            type="button"
            onClick={onRefresh}
            style={{ background: "var(--card-bg-2)", border: "1px solid var(--card-bd)", color: "var(--body-tx)" }}
            className="flex min-h-11 items-center gap-1.5 rounded-full px-3 py-1.5 text-xs font-medium"
          >
            <RotateCw size={13} aria-hidden="true" /> Refresh images
          </button>
        )}
      </div>
      {stale && !loading && (
        <p style={{ color: "var(--muted-tx)" }} className="mb-3 text-xs">
          These image links expire after a short time. Refresh to load them again.
        </p>
      )}
      <PanelState
        loading={loading} error={error} isEmpty={visible.length === 0}
        emptyNote={PROCESSING_NOTE} emptyMinHeight={EMPTY_H}
        loadingLabel="Loading image gallery"
        onRetry={onRetry}
        skeleton={
          <div className={galleryGridClass(skeletonMosaic)} aria-hidden="true">
            {Array.from({ length: skeletonCount }).map((_, i) => (
              <Skel key={i} className={`rounded-2xl ${galleryTileClass(skeletonMosaic, i)}`} />
            ))}
          </div>
        }
      >
        <div className={galleryGridClass(mosaic)}>
          {visible.map((item, i) => (
            <GalleryImageTile key={item.post_id} item={item} className={galleryTileClass(mosaic, i)} />
          ))}
        </div>
      </PanelState>
    </div>
  );
}

function BrandVisualTerritories({ brands, loading, error, heading, onRetry }: {
  brands: BrandOverview[]; loading: boolean; error: string | null; heading: string; onRetry: () => void;
}) {
  return (
    <div>
      <div className="mb-4">
        <h3 style={{ color: "var(--title-tx)" }} className="text-base font-semibold">{heading}</h3>
        <p style={{ color: "var(--muted-tx)" }} className="text-xs">Compare how they occupy visual space</p>
      </div>
      <PanelState
        loading={loading} error={error} isEmpty={brands.length === 0}
        emptyNote="Brand visual territories appear here once brand imagery has been processed."
        emptyMinHeight={EMPTY_H}
        loadingLabel={`Loading ${heading.toLowerCase()}`}
        onRetry={onRetry}
        skeleton={
          <div className="grid grid-cols-1 gap-4 sm:grid-cols-2 lg:grid-cols-4" aria-hidden="true">
            {Array.from({ length: 4 }).map((_, i) => (
              <div key={i} className="chart-card rounded-2xl p-5">
                <Skel className="h-5 w-2/3" />
                <div className="mt-3 flex gap-1.5">
                  <Skel className="h-5 w-16 rounded-full" />
                  <Skel className="h-5 w-20 rounded-full" />
                </div>
              </div>
            ))}
          </div>
        }
      >
        <div className="grid grid-cols-1 gap-4 sm:grid-cols-2 lg:grid-cols-4">
          {brands.map((b) => {
            const shown = b.visual_territories.slice(0, MAX_TERRITORY_PILLS);
            const overflow = b.visual_territories.length - shown.length;
            return (
              <div key={b.key} className="chart-card rounded-2xl p-5">
                <div dir="auto" style={{ color: "var(--title-tx)" }} className="text-base font-semibold">{b.name}</div>
                {shown.length === 0 ? (
                  <div className="mt-2 text-xs" style={{ color: "var(--muted-tx)" }}>No visual territories yet</div>
                ) : (
                  <div className="mt-2 flex flex-wrap gap-1.5">
                    {shown.map((t) => (
                      <span
                        key={t}
                        dir="auto"
                        style={{ background: "var(--card-bg-2)", border: "1px solid var(--card-bd)", color: "var(--body-tx)" }}
                        className="rounded-full px-2 py-0.5 text-xs"
                      >
                        {t}
                      </span>
                    ))}
                    {overflow > 0 && (
                      <span
                        style={{ border: "1px solid var(--card-bd)", color: "var(--muted-tx)" }}
                        className="rounded-full px-2 py-0.5 text-xs tabular-nums"
                      >
                        +{overflow}
                      </span>
                    )}
                  </div>
                )}
              </div>
            );
          })}
        </div>
      </PanelState>
    </div>
  );
}

export default function VisualIntelligencePage() {
  const [cohort, setCohort] = useState<string>("brand");
  // A set, so several accounts can be compared at once; empty means the
  // whole cohort.
  const [selectedKeys, setSelectedKeys] = useState<string[]>([]);
  const [galleryStale, setGalleryStale] = useState(false);

  const cohortsRes = useAsyncResource((s) => fetchVisualCohorts(s), []);
  const cohorts = useMemo(() => cohortsRes.data?.cohorts ?? [], [cohortsRes.data]);

  // Both types: influencer imagery is as much the subject of this screen as
  // brand imagery, and the same enrichment produces it. Brands lead the list
  // because they are the smaller, more familiar set.
  const brandsRes = useAsyncResource(async (s) => {
    const res = await fetchBrands("all", s);
    return [...res.brands].sort((a, b) =>
      (a.account_type === "influencer" ? 1 : 0) - (b.account_type === "influencer" ? 1 : 0) ||
      a.name.localeCompare(b.name));
  }, []);
  const brands = useMemo(() => brandsRes.data ?? [], [brandsRes.data]);

  // The selection, narrowed to accounts that belong to the cohort on screen.
  // Switching tabs leaves the previous cohort's selection in state, and the
  // picker falls back to its placeholder because that key is missing from the
  // filtered list - so the screen read "All accounts" while still querying
  // for one brand inside the influencer cohort, which matches nothing.
  // Consumers never take an account: the sample spans 1,730 of them.
  const cohortKeys = useMemo(
    () => (cohort === "community" ? [] : selectedKeys.filter((k) =>
      brands.some((b) => b.key === k && (b.account_type ?? "brand") === cohort))),
    [cohort, selectedKeys, brands],
  );
  const keySig = cohortKeys.join("|");

  const analysis = useAsyncResource(
    (s) => fetchVisualCohortAnalysis(cohort, cohortKeys, 12, s), [cohort, keySig]);

  const territories = useAsyncResource(
    (s) => fetchVisualTerritories(cohort, cohortKeys, 8, s), [cohort, keySig]);

  const gallery = useAsyncResource(
    async (s) => (await fetchVisualGallery(GALLERY_LAYOUT.length, cohortKeys, cohort, s)).items,
    [cohort, keySig]);

  const topAccounts = useMemo(
    () => brands
      .filter((b) => (b.account_type ?? "brand") === cohort)
      .sort((a, b) => b.post_count - a.post_count)
      .slice(0, 4)
      .map((b) => b.key),
    [brands, cohort],
  );
  const accountSig = topAccounts.join("|");

  const territoryBrands = useAsyncResource(async (s) => {
    if (topAccounts.length === 0) return [] as BrandOverview[];
    const results = await Promise.allSettled(topAccounts.map((k) => fetchBrandOverview(k, s)));
    const ok = results
      .filter((r): r is PromiseFulfilledResult<BrandOverview> => r.status === "fulfilled")
      .map((r) => r.value);
    if (ok.length === 0 && results.length > 0) {
      throw (results[0] as PromiseRejectedResult).reason;
    }
    return ok;
  }, [accountSig], { enabled: !brandsRes.loading });

  const selectCohort = useCallback((next: string) => {
    setCohort(next);
    setSelectedKeys([]);
    setGalleryStale(false);
  }, []);

  const refreshGallery = useCallback(() => {
    setGalleryStale(false);
    gallery.reload();
  }, [gallery]);

  useEffect(() => {
    if (!gallery.data?.length) return;
    const timer = setTimeout(() => setGalleryStale(true), GALLERY_STALE_MS);
    return () => clearTimeout(timer);
  }, [gallery.data]);

  const meta = COHORT_META[cohort];
  const analysisData = analysis.data;

  return (
    <MotionConfig reducedMotion="user">
      <div className="w-full">
        <DashboardTopbar title="Visual Intelligence" accessory={<TopbarSearch />} />

        <div className="mx-auto max-w-[1500px] space-y-6 p-6 sm:p-8">
          <motion.section initial={{ opacity: 0, y: 12 }} animate={{ opacity: 1, y: 0 }}
            transition={{ duration: 0.5, ease: [0.16, 1, 0.3, 1] }}
            className="chart-card rounded-2xl p-8">
            <h2 style={{ color: "var(--title-tx)" }} className="text-3xl font-bold tracking-tight">The Visual Language of Food Culture</h2>
            <p style={{ color: "var(--body-tx)" }} className="mt-3 max-w-2xl text-sm leading-relaxed">
              Compare what brands, influencers and consumers actually post about themes, products and language, side by side.
            </p>
          </motion.section>

          <div className="flex flex-col gap-4 lg:flex-row lg:items-center lg:justify-between">
            <CohortTabs counts={cohorts} value={cohort} onChange={selectCohort} loading={cohortsRes.loading} />
            {cohort !== "community" && (
              <BrandSelect
                brands={brands.filter((b) => (b.account_type ?? "brand") === cohort)}
                multiple
                values={selectedKeys}
                onChangeMany={setSelectedKeys}
                value=""
                onChange={() => {}}
                loading={brandsRes.loading}
                label={cohort === "influencer" ? "Select influencers" : "Select brands"}
                placeholder="All accounts"
              />
            )}
          </div>

          {cohortsRes.error && (
            <InlineError message={`Cohort totals unavailable — ${cohortsRes.error}`} onRetry={cohortsRes.reload} />
          )}
          {brandsRes.error && <InlineError message={brandsRes.error} onRetry={brandsRes.reload} />}

          <div className="flex flex-wrap items-baseline gap-x-3 gap-y-1">
            <h2 style={{ color: "var(--title-tx)" }} className="text-xl font-bold tracking-tight">
              {meta?.label ?? cohort}
            </h2>
            <p style={{ color: "var(--muted-tx)" }} className="text-sm">
              {meta?.blurb}
              {analysisData ? ` · ${analysisData.analysed_posts.toLocaleString()} posts analysed` : ""}
              {analysisData?.accounts ? ` · ${analysisData.accounts.toLocaleString()} accounts` : ""}
            </p>
          </div>

          <div className="grid grid-cols-1 gap-6 lg:grid-cols-2">
            <FacetPanel
              title="Themes"
              subtitle="What this cohort talks about"
              items={analysisData?.themes ?? []}
              color={graphic(meta?.token ?? "watchlist")}
              loading={analysis.loading}
              error={analysis.error}
              onRetry={analysis.reload}
              emptyNote="No themes yet for this selection."
            />
            <FacetPanel
              title="Products"
              subtitle="What it names"
              items={analysisData?.products ?? []}
              color={graphic(meta?.token ?? "watchlist")}
              loading={analysis.loading}
              error={analysis.error}
              onRetry={analysis.reload}
              emptyNote="No products named yet for this selection."
            />
          </div>

          {/* Shown for every cohort. The consumer figures come from a sample
              drawn by engagement rather than by date, which makes their share
              sound and their movement between windows softer than the brand and
              creator numbers - worth knowing when reading it, not worth hiding
              the panel over. */}
          <TerritoryGrowthPanel
            resource={territories}
            whose={cohort === "brand" ? "the brands we track"
                 : cohort === "influencer" ? "the creators we track"
                 : "consumers"}
          />

          {/* One pseudo-account stands for every consumer, so a per-account
              breakdown has nothing to break down. */}
          {cohort !== "community" && (
            <BrandVisualTerritories
              brands={territoryBrands.data ?? []}
              loading={territoryBrands.loading || brandsRes.loading}
              error={territoryBrands.error}
              onRetry={territoryBrands.reload}
              heading={cohort === "influencer" ? "Influencer Visual Territories" : "Brand Visual Territories"}
            />
          )}

          <ImageGallery
            items={gallery.data ?? []}
            loading={gallery.loading}
            error={gallery.error}
            onRetry={gallery.reload}
            stale={galleryStale}
            onRefresh={refreshGallery}
          />
        </div>
      </div>
    </MotionConfig>
  );
}
