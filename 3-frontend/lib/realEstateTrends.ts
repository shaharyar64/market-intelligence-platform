import { apiFetch } from "@/lib/apiClient";

/**
 * Real Estate Intelligence: Trends read API.
 * Proxied through the gateway as /api/v1/trends-real-estate/trends/*.
 * Backed by realestate_intel.trends (see trend pipeline in real_estate_intelligence_service).
 */
const BASE = "/api/v1/trends-real-estate/trends";

export type Quadrant = "breakthrough" | "slow-burner" | "mainstream" | "watchlist";

export type Source = "community" | "brand" | "influencer";
export type Period = "month" | "cumulative";
/** Market a trend run is scoped to. null is the all-markets run. */
export type Market = "AE" | "SA";
export const MARKETS: { value: Market | null; label: string }[] = [
  { value: null, label: "All markets" },
  { value: "AE", label: "UAE" },
  { value: "SA", label: "KSA" },
];

/** Reads ?market= from a URL, so a shared link opens on the same market. */
export function parseMarket(value: string | null | undefined): Market | null {
  return value === "AE" || value === "SA" ? value : null;
}

function withMarket(qs: URLSearchParams, market?: Market | null) {
  if (market) qs.set("country", market);
  return qs;
}

export type TrendListItem = {
  id: string;
  name: string;
  level: "micro" | "umbrella";
  parent_trend_id: string | null;
  quadrant: Quadrant;
  growth: number;
  growth_pct: number | null;
  momentum_pct: number | null;
  is_new: boolean;
  recent_posts: number | null;
  previous_posts: number | null;
  first_post: string | null;        // growth_index 0-100
  volume: number;        // volume_index 0-100
  post_count: number;
  platforms: string[];
  source_mix: Partial<Record<Source, number>>;
  sparkline: number[];   // last <=7 weekly post counts
  summary: string;
  opportunity_summary: string;
  /** "pipeline" when clustering found it, "chat" when a user had the assistant build it. */
  origin?: "pipeline" | "chat";
  /** The question that produced a chat-generated trend. */
  source_query?: string | null;
};

export type OverviewKpi = { key: string; label: string; value: number; delta: number | null };
export type QuadrantEntry = { id: string; name: string; volume: number; growth: number };

export type TrendsOverview = {
  run_id: string;
  period: Period;
  computed_at: string | null;
  as_of: string | null;
  period_month: string | null;
  kpis: OverviewKpi[];
  quadrants: { quadrant: Quadrant; trends: QuadrantEntry[] }[];
  emerging: { id: string; name: string; growth: number; quadrant: Quadrant; summary: string }[];
  movers: { rank: number; id: string; name: string; pts: number }[];
  umbrellas: TrendListItem[];
};

export type TimelinePoint = {
  week_start: string;
  post_count: number;
  engagement: number;
  unique_authors: number;
};

export type ExamplePost = {
  platform: string;
  post_id: string;
  source: Source;
  author: string;
  caption: string;
  post_url: string | null;
  engagement: number;
  likes: number;
  comments: number;
  views: number;
  media_key: string | null;
  media_url: string | null;
};

export type TrendDetail = TrendListItem & {
  metrics: {
    volume_raw: number;
    growth_pct: number;
    engagement_total: number;
    platform_mix: Record<string, number>;
    source_mix?: Partial<Record<Source, number>>;
    as_of: string;
  };
  timeline: TimelinePoint[];
  search_timeline: { date: string; index: number }[] | null;
  related_themes: string[];
  offering_entities: string[];
  keywords: string[];
  unique_authors: number;
  example_posts: ExamplePost[];
  example_posts_by_source: Partial<Record<Source, ExamplePost[]>>;
  members?: TrendListItem[];   // umbrella only
};

export function friendlyTrendError(e: unknown): string {
  const m = e instanceof Error ? e.message : "";
  if (m.startsWith("404") && / for (AE|SA)/.test(m)) return "No trends have been built for this market yet.";
  if (m.startsWith("404")) return "No trend run is available yet. Run the trend pipeline first.";
  if (m.startsWith("401") || m.startsWith("403")) return "Your session has expired. Please sign in again.";
  return "We could not load trends right now. Please try again in a moment.";
}

/** True when a rejection is an aborted request rather than a real failure.
 *
 *  Switching a filter cancels the request the previous filter started. That
 *  cancellation surfaces here as a rejection, and rendering it would flash an
 *  error for a request nobody is waiting on any more. Callers check this before
 *  writing to error state. */
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

export function fetchTrendsOverview(period: Period = "month", signal?: AbortSignal,
                                    market?: Market | null) {
  const qs = withMarket(new URLSearchParams({ period }), market);
  return getJson<TrendsOverview>(`${BASE}/overview?${qs}`, signal);
}

export function fetchTrends(
  level: "micro" | "umbrella" = "micro",
  period: Period = "cumulative",
  signal?: AbortSignal,
  market?: Market | null,
) {
  const qs = withMarket(new URLSearchParams({ level, period }), market);
  return getJson<{ run_id: string; trends: TrendListItem[] }>(`${BASE}?${qs}`, signal);
}

export function fetchTrendDetail(
  id: string,
  dateFrom?: string | null,
  dateTo?: string | null,
  signal?: AbortSignal,
  market?: Market | null,
) {
  const qs = new URLSearchParams();
  if (dateFrom) qs.set("date_from", dateFrom);
  if (dateTo) qs.set("date_to", dateTo);
  withMarket(qs, market);
  const suffix = qs.toString() ? `?${qs}` : "";
  return getJson<TrendDetail>(`${BASE}/${encodeURIComponent(id)}${suffix}`, signal);
}
