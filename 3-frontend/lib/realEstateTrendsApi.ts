import { apiFetch } from "@/lib/apiClient";

/**
 * Real Estate Intelligence: Brand Intelligence read API.
 * Proxied through the gateway as /api/v1/trends-real-estate/{path}.
 * Backed by the enriched Postgres tables (see real_estate_intelligence_service).
 */
const BASE = "/api/v1/trends-real-estate";

/* ─── types (mirror the service's pydantic models) ───────────────────── */
export type BrandSummary = {
  key: string;
  name: string;
  /** "brand" or "influencer" — the same enrichment runs over both. */
  account_type?: string;
  post_count: number;
  platforms: string[];
};

export type PlatformAccount = {
  platform: string;
  account_username: string | null;
  followers: number;
  is_verified: boolean;
};

export type BrandOverview = {
  key: string;
  name: string;
  account_type: string;
  platforms: string[];
  accounts: PlatformAccount[];
  followers_total: number;
  post_count: number;
  total_engagement: number;
  avg_engagement_per_post: number;
  first_post_date: string | null;
  last_post_date: string | null;
  theme_count: number;
  offering_count: number;
  visual_territories: string[];
};

export type FacetAgg = {
  label?: string; // themes
  offering?: string; // offerings, canonical English
  offering_native?: string | null;
  label_native?: string | null;
  post_count: number;
  engagement: number;
  avg_confidence: number;
  evidence: string[];
  example_post_ids: string[];
};

export type ThemesResponse = { brand_key: string; min_posts: number; themes: FacetAgg[] };
export type OfferingsResponse = { brand_key: string; min_posts: number; offerings: FacetAgg[] };

export type TopContentItem = {
  post_id: string;
  platform: string;
  post_url: string | null;
  owner: { username: string | null; name: string | null } | null;
  posted_at: string | null;
  text: string;
  engagement: Record<string, number>;
  themes: string[];
  offerings: string[];
};

export type FunctionalVisualCategory = { category: string; post_count: number; pct: number };
export type BrandFunctionalVisualResponse = { brand_key: string; categories: FunctionalVisualCategory[] };
export type BrandSemioticResponse = { brand_key: string; axes: Record<string, number> };

export type FunctionalAnalysisResponse = { brand_key?: string | null; categories: FunctionalVisualCategory[] };
export type SemioticGroupedResponse = {
  group_by: string;
  brand_key?: string | null;
  groups: Record<string, Record<string, number>>;
};

export type GalleryItem = {
  post_id: string;
  platform: string;
  brand_name: string | null;
  caption: string | null;
  image_url: string | null;
};
export type GalleryResponse = {
  account_type?: string | null;
  keys?: string[] | null;
  items: GalleryItem[];
};

/* ─── helpers ────────────────────────────────────────────────────────── */

/** True when a rejection is an aborted request rather than a real failure.
 *  See the note on realEstateTrends.isAbort — switching cohort or brand cancels the
 *  previous request, and that must not paint an error. */
export function isAbort(e: unknown): boolean {
  return e instanceof DOMException && e.name === "AbortError";
}

async function getJson<T>(endpoint: string, signal?: AbortSignal): Promise<T> {
  const res = await apiFetch(endpoint, signal ? { signal } : {});
  if (!res.ok) {
    const detail = await res.text().catch(() => "");
    throw new Error(`${res.status} ${detail || res.statusText}`);
  }
  return res.json() as Promise<T>;
}

/* ─── endpoints ──────────────────────────────────────────────────────── */
export type CohortCount = {
  account_type: "brand" | "influencer" | "community";
  analysed_posts: number;
  accounts: number;
  engagement: number;
  /** Consumers are analysed from a stratified sample, not in full. */
  sampled: boolean;
};

export type CohortFacet = {
  label: string;
  offering?: string;
  label_native?: string | null;
  offering_native?: string | null;
  post_count: number;
  engagement: number;
  avg_confidence: number;
  evidence: string[];
};

export type CohortAnalysis = {
  account_type: string;
  keys: string[] | null;
  sampled: boolean;
  analysed_posts: number;
  accounts: number;
  engagement: number;
  first_post: string | null;
  last_post: string | null;
  themes: CohortFacet[];
  offerings: (CohortFacet & { offering: string })[];
  languages: { language: string; post_count: number; pct: number }[];
};

export type TerritoryGrowth = {
  territory: string;
  recent_posts: number;
  previous_posts: number;
  share_pct: number;
  growth_pct: number;
};

export type TerritoryGrowthResponse = {
  territories: TerritoryGrowth[];
  as_of: string | null;
  window_days: number;
  basis?: string;
  /** False for the consumer sample: drawn by engagement, so its mix is
   *  meaningful but its movement between two windows is not. */
  time_ordered?: boolean;
};

export function fetchVisualTerritories(accountType?: string | null, keys?: string[] | null, limit = 8, signal?: AbortSignal) {
  const q = new URLSearchParams({ limit: String(limit) });
  if (accountType) q.set("account_type", accountType);
  for (const k of keys ?? []) q.append("key", k);
  return getJson<TerritoryGrowthResponse>(`${BASE}/visual/territories?${q}`, signal);
}

export function fetchVisualCohorts(signal?: AbortSignal) {
  return getJson<{ cohorts: CohortCount[] }>(`${BASE}/visual/cohorts`, signal);
}

export function fetchVisualCohortAnalysis(accountType: string, keys?: string[] | null, limit = 12, signal?: AbortSignal) {
  const q = new URLSearchParams({ limit: String(limit) });
  // Repeated params rather than a joined string: an account key could contain
  // whatever separator we picked.
  for (const k of keys ?? []) q.append("key", k);
  return getJson<CohortAnalysis>(`${BASE}/visual/cohort/${accountType}?${q}`, signal);
}

export function fetchBrands(accountType: "brand" | "influencer" | "all" = "brand", signal?: AbortSignal) {
  const q = new URLSearchParams({ account_type: accountType });
  return getJson<{ brands: BrandSummary[] }>(`${BASE}/brands?${q}`, signal);
}

export function fetchBrandOverview(key: string, signal?: AbortSignal) {
  return getJson<BrandOverview>(`${BASE}/brands/${encodeURIComponent(key)}/overview`, signal);
}

export function fetchBrandThemes(key: string, minPosts?: number, limit = 12, signal?: AbortSignal) {
  const q = new URLSearchParams({ limit: String(limit) });
  if (minPosts) q.set("min_posts", String(minPosts));
  return getJson<ThemesResponse>(`${BASE}/brands/${encodeURIComponent(key)}/themes?${q}`, signal);
}

export function fetchBrandOfferings(key: string, minPosts?: number, limit = 12, signal?: AbortSignal) {
  const q = new URLSearchParams({ limit: String(limit) });
  if (minPosts) q.set("min_posts", String(minPosts));
  return getJson<OfferingsResponse>(`${BASE}/brands/${encodeURIComponent(key)}/offerings?${q}`, signal);
}

export function fetchBrandTopContent(key: string, limit = 8, platform?: string, signal?: AbortSignal) {
  const q = new URLSearchParams({ limit: String(limit) });
  if (platform) q.set("platform", platform);
  return getJson<{ brand_key: string; items: TopContentItem[] }>(
    `${BASE}/brands/${encodeURIComponent(key)}/top-content?${q}`, signal
  );
}

export function fetchBrandFunctionalVisual(key: string, signal?: AbortSignal) {
  return getJson<BrandFunctionalVisualResponse>(`${BASE}/brands/${encodeURIComponent(key)}/functional-visual`, signal);
}

export type TrendParticipationEntry = {
  trend_id: string; name: string; quadrant: string; posts: number; share_pct: number;
};
export type TrendParticipationResponse = {
  brand_key: string;
  posts_in_corpus: number;
  posts_in_trends: number;
  trends: TrendParticipationEntry[];
};

export type TrendOpportunity = {
  trend_id: string;
  name: string;
  quadrant: string;
  growth: number;
  volume: number;
  trend_posts: number;
  competitors: number;
  competitor_posts: number;
  competitor_names: string[];
  summary: string;
};
export type TrendOpportunitiesResponse = {
  brand_key: string;
  opportunities: TrendOpportunity[];
};

export function fetchBrandTrendOpportunities(key: string, signal?: AbortSignal) {
  return getJson<TrendOpportunitiesResponse>(
    `${BASE}/brands/${encodeURIComponent(key)}/trend-opportunities`, signal);
}

export function fetchBrandTrendParticipation(key: string, signal?: AbortSignal) {
  return getJson<TrendParticipationResponse>(
    `${BASE}/brands/${encodeURIComponent(key)}/trend-participation`, signal);
}

export function fetchBrandSemiotic(key: string, signal?: AbortSignal) {
  return getJson<BrandSemioticResponse>(`${BASE}/brands/${encodeURIComponent(key)}/semiotic`, signal);
}

// accountType keeps each cohort tab on its own imagery; keys narrows to the
// accounts picked above it. An empty keys array means the whole cohort.
export function fetchVisualGallery(limit = 12, keys: string[] = [], accountType?: string, signal?: AbortSignal) {
  const q = new URLSearchParams({ limit: String(limit) });
  if (accountType) q.set("account_type", accountType);
  keys.forEach((k) => q.append("key", k));
  return getJson<GalleryResponse>(`${BASE}/visual/gallery?${q}`, signal);
}
