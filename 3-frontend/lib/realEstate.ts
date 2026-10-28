import { apiFetch } from "./apiClient";

export const BRANDIQ_SCORE_MAX = 60;

/**
 * The real-estate service's response contract is documented as reusing
 * digital-brand-health's field names (e.g. "bank") even though the value is
 * a developer name. Live testing has shown "developer" instead in at least
 * one endpoint. Entity-name fields below accept either key; use
 * `entityName()` to read them so the UI works regardless of which is sent.
 */
export type EntityNamed = {
  bank?: string | null;
  developer?: string | null;
};

export function entityName(item: EntityNamed | null | undefined): string {
  if (!item) return "";
  return (item.developer ?? item.bank ?? "").toString().trim();
}

export type TopDigitalHealthItem = EntityNamed & {
  avg_score: number;
  // Snapshot columns backed by realestate_dbh.brand_iq_snapshot — present
  // since the endpoint switched from a computed proxy to real pre-ranked
  // data. Optional since older/mocked responses may not include them.
  rank?: number;
  ai_score?: number | null;
  share_of_search_pct?: number | null;
  rating?: number | null;
  review_volume?: number | null;
  social_sov_pct?: number | null;
  engagement?: number | null;
};

export type TopDigitalHealthResponse = {
  top_digital_health: TopDigitalHealthItem[];
};

export type DigitalBrandHealthFrequency = "1m" | "3m" | "6m" | "1y";

export type DigitalEquityTrendResponse = {
  digital_equity_trend: Record<string, unknown>[];
};

export type Top3BanksTrendResponse = {
  top3_banks_trend: Record<string, unknown>[];
};

export type BanksFilterResponse = {
  banks: string[];
};

export type ProductsFilterResponse = {
  products: string[];
};

export type AssociationsFilterResponse = {
  associations: string[];
};

export type AiScoreItem = EntityNamed & {
  score: number;
  // Present on all rows since the backend started tagging them (was only on
  // citations before); set when `location=all` returns multiple locations'
  // leaderboards stacked together, so callers can tell legitimate
  // same-brand-different-location rows apart from accidental duplicates.
  location?: string;
};

export type AiScoreResponse = Record<string, AiScoreItem[]>;

export type AiScoreOverallItem = EntityNamed & {
  llm?: string;
  score: number;
  location?: string;
};

export type AiScoreAudienceAffinityItem = {
  customer_segment: string;
  llm?: string;
  score: number;
  rationale: string;
};

export type AiScoreAudienceAffinityResponse = Record<string, AiScoreAudienceAffinityItem[]>;

export type AiScoreCitationItem = EntityNamed & {
  location: string;
  llm?: string | null;
  platform?: string | null;
  model: string;
  analysis_section?: string | null;
  prompt?: string | null;
  title: string;
  url: string;
};

export type AiScoreBrandProjectionItem = {
  personality: string;
  strengths: string[];
  positioning_opportunities: string[];
  projections?: Array<{
    llm: string;
    personality: string;
    points: Array<{ type: string; text: string }>;
  }>;
};

export type AiScoreBrandProjectionResponse = Record<string, AiScoreBrandProjectionItem>;

const AI_SCORE_CATEGORY_LABELS: Record<string, string> = {
  "SME & Business Support": "Business Support",
};

export function formatAiScoreCategoryLabel(category: string): string {
  return AI_SCORE_CATEGORY_LABELS[category] ?? category;
}

export type ReviewAnalysisRow = Record<string, unknown>;

export type RatedBanksResponse = {
  items: ReviewAnalysisRow[];
};

// `bank`/`developer` and `total_posts` are only populated when the request
// has no `bank` filter (comparing all developers). Filtered to a single
// `bank`, the API omits those fields (you already know who you asked for,
// and post-count isn't part of that mode's breakdown) and returns only the
// engagement fields.
export type SocialPostDistributionItem = EntityNamed & {
  total_posts: number | null;
  likes: number | null;
  shares: number | null;
  comments: number | null;
  views: number | null;
  total_engagement: number | null;
};

export type SocialPostDistributionResponse = {
  distribution: SocialPostDistributionItem[];
};

export type SocialTopGrowingItem = EntityNamed & {
  growth: number;
  current_share_of_volume: number;
};

export type SocialTopGrowingResponse = {
  data: SocialTopGrowingItem[];
};

export type SocialVolumeTrendFrequency = "1m" | "3m" | "6m" | "1y";

export type SocialVolumeTrendItem = {
  period: string;
  volume: number;
};

export type SocialVolumeTrendResponse = {
  trend: SocialVolumeTrendItem[];
};

export type SocialEngagementTrendItem = {
  period: string;
  engagement: number;
};

export type SocialEngagementTrendResponse = {
  trend: SocialEngagementTrendItem[];
};

export type SocialTopTopicItem = {
  name: string;
  avg_sentiment: number;
  mentions: number;
};

export type SocialTopTopicsResponse = {
  data: SocialTopTopicItem[];
};

export type SocialSentimentItem = Record<string, unknown>;

export type SocialSentimentListResponse = {
  data: SocialSentimentItem[];
};

export type SocialAssociationItem = Record<string, unknown>;

export type SocialAssociationsResponse = {
  data: SocialAssociationItem[];
};

export type SocialFilters = {
  bank?: string;
  platform?: string;
  startDate?: string;
  endDate?: string;
};

export type SocialFiltersResponse = {
  data: Record<string, unknown>;
};

function buildSocialQueryParams(
  filters?: SocialFilters,
  extra?: Record<string, string | number | undefined>
) {
  const params = new URLSearchParams();

  if (filters?.bank) params.append("bank", filters.bank);
  if (filters?.platform) params.append("platform", filters.platform);

  Object.entries(extra ?? {}).forEach(([key, value]) => {
    if (value !== undefined && value !== "") {
      params.append(key, String(value));
    }
  });

  const query = params.toString();
  return query ? `?${query}` : "";
}

export async function getTopDigitalHealth(): Promise<TopDigitalHealthResponse> {
  const res = await apiFetch(
    "/api/v1/real-estate/exclusive-summary/top-digital-health"
  );

  if (!res.ok) {
    throw new Error("Failed to fetch top digital health");
  }

  return res.json();
}

export async function getDigitalEquityTrend(
  freq: DigitalBrandHealthFrequency
): Promise<DigitalEquityTrendResponse> {
  const params = new URLSearchParams({ freq });
  const res = await apiFetch(
    `/api/v1/real-estate/exclusive-summary/digital-equity-trend?${params.toString()}`
  );

  if (!res.ok) {
    throw new Error("Failed to fetch digital equity trend");
  }

  return res.json();
}

export async function getTop3BanksTrend(
  freq: DigitalBrandHealthFrequency,
  banks: string[] = []
): Promise<Top3BanksTrendResponse> {
  const params = new URLSearchParams({ freq });
  banks
    .filter(Boolean)
    .slice(0, 5)
    .forEach((bank) => params.append("bank", bank));

  const res = await apiFetch(
    `/api/v1/real-estate/exclusive-summary/top3-banks-trend?${params.toString()}`
  );

  if (!res.ok) {
    throw new Error("Failed to fetch top 3 banks trend");
  }

  return res.json();
}

export async function getDigitalBrandHealthBanks(): Promise<BanksFilterResponse> {
  const endpoints = [
    "/api/v1/real-estate/filters/banks",
    "/api/v1/filters/banks",
  ];

  for (const endpoint of endpoints) {
    const res = await apiFetch(endpoint);

    if (res.ok) {
      return res.json();
    }

    if (res.status !== 404) {
      throw new Error("Failed to fetch bank filters");
    }
  }

  throw new Error("Failed to fetch bank filters");
}

export async function getDigitalBrandHealthProducts(): Promise<ProductsFilterResponse> {
  const endpoints = [
    "/api/v1/real-estate/filters/products",
    "/api/v1/filters/products",
  ];

  for (const endpoint of endpoints) {
    const res = await apiFetch(endpoint);

    if (res.ok) {
      return res.json();
    }

    if (res.status !== 404) {
      throw new Error("Failed to fetch product filters");
    }
  }

  throw new Error("Failed to fetch product filters");
}

export async function getDigitalBrandHealthAssociations(): Promise<AssociationsFilterResponse> {
  const endpoints = [
    "/api/v1/real-estate/filters/associations",
    "/api/v1/filters/associations",
  ];

  for (const endpoint of endpoints) {
    const res = await apiFetch(endpoint);

    if (res.ok) {
      return res.json();
    }

    if (res.status !== 404) {
      throw new Error("Failed to fetch association filters");
    }
  }

  throw new Error("Failed to fetch association filters");
}

/**
 * Region filter accepted by several ai-score endpoints. "UAE" is the
 * country-wide aggregate (the implicit default when no location is passed).
 * "all" returns every location unfiltered.
 */
export type AiScoreLocation =
  | "UAE"
  | "Abu Dhabi"
  | "Dubai"
  | "Ras Al Khaimah"
  | "Sharjah"
  | "all";

export const AI_SCORE_LOCATIONS: AiScoreLocation[] = [
  "UAE",
  "Abu Dhabi",
  "Dubai",
  "Ras Al Khaimah",
  "Sharjah",
  "all",
];

export type MarketPositioningItem = AiScoreItem;
export type MarketPositioningResponse = AiScoreResponse;

export async function getAiScoreServices(
  llm = "Overall",
  location?: AiScoreLocation
): Promise<AiScoreResponse> {
  const params = new URLSearchParams({ llm });
  if (location) params.set("location", location);
  const res = await apiFetch(`/api/v1/real-estate/ai-score/services?${params.toString()}`);

  if (!res.ok) {
    throw new Error("Failed to fetch AI score services");
  }

  return res.json();
}

export async function getAiScoreProducts(
  llm = "Overall",
  location?: AiScoreLocation
): Promise<AiScoreResponse> {
  const params = new URLSearchParams({ llm });
  if (location) params.set("location", location);
  const res = await apiFetch(`/api/v1/real-estate/ai-score/products?${params.toString()}`);

  if (!res.ok) {
    throw new Error("Failed to fetch AI score products");
  }

  return res.json();
}

export async function getAiScoreOverall(
  llm = "Overall",
  location?: AiScoreLocation
): Promise<AiScoreOverallItem[]> {
  const params = new URLSearchParams({ llm });
  if (location) params.set("location", location);
  const res = await apiFetch(`/api/v1/real-estate/ai-score/overall?${params.toString()}`);

  if (!res.ok) {
    throw new Error("Failed to fetch AI score overall");
  }

  const body: { data: AiScoreOverallItem[] } = await res.json();
  return body.data;
}

export async function getAiScoreMarketPositioning(
  llm = "Overall",
  location?: AiScoreLocation
): Promise<MarketPositioningResponse> {
  const params = new URLSearchParams({ llm });
  if (location) params.set("location", location);
  const res = await apiFetch(
    `/api/v1/real-estate/ai-score/market-positioning?${params.toString()}`
  );

  if (!res.ok) {
    throw new Error("Failed to fetch AI score market positioning");
  }

  return res.json();
}

export async function getAiScoreAudienceAffinity(
  llm = "Overall",
  bank?: string
): Promise<AiScoreAudienceAffinityResponse> {
  const params = new URLSearchParams({ llm });
  if (bank) params.set("bank", bank);
  const res = await apiFetch(`/api/v1/real-estate/ai-score/audience-affinity?${params.toString()}`);

  if (!res.ok) {
    throw new Error("Failed to fetch AI score audience affinity");
  }

  return res.json();
}

export async function getAiScoreCitations(
  location?: AiScoreLocation
): Promise<AiScoreCitationItem[]> {
  const params = new URLSearchParams();
  if (location) params.set("location", location);
  const query = params.toString();
  const res = await apiFetch(`/api/v1/real-estate/ai-score/citations${query ? `?${query}` : ""}`);

  if (!res.ok) {
    throw new Error("Failed to fetch AI score citations");
  }

  const body: { data: AiScoreCitationItem[] } = await res.json();
  return body.data;
}

export async function getAiScoreBrandProjection(
  llm = "Overall",
  bank?: string
): Promise<AiScoreBrandProjectionResponse> {
  const params = new URLSearchParams({ llm });
  if (bank) params.set("bank", bank);
  const res = await apiFetch(`/api/v1/real-estate/ai-score/brand-projection?${params.toString()}`);

  if (!res.ok) {
    throw new Error("Failed to fetch AI score brand projection");
  }

  return res.json();
}

export async function getAiScorePerceptionBanks(): Promise<BanksFilterResponse> {
  const res = await apiFetch("/api/v1/real-estate/ai-score/banks");

  if (!res.ok) {
    throw new Error("Failed to fetch AI score perception banks");
  }

  return res.json();
}

/**
 * Developer operating region, from GET /filters/regions. Region filtering is
 * reviews-only for now — the backend's metadata table only reliably matches
 * developer names in google_reviews (22/22); search-data (17/22) and
 * social-data (10/23) name mismatches would silently drop most developers,
 * so don't thread this through those modules until the backend does.
 */
export type RegionsFilterResponse = {
  regions: string[];
};

export async function getRegions(): Promise<RegionsFilterResponse> {
  const res = await apiFetch("/api/v1/real-estate/filters/regions");

  if (!res.ok) {
    throw new Error("Failed to fetch regions");
  }

  return res.json();
}

export async function getReviewsPerBank(region?: string): Promise<ReviewAnalysisRow[]> {
  const params = new URLSearchParams();
  if (region) params.set("region", region);
  const query = params.toString();
  const res = await apiFetch(`/api/v1/real-estate/reviews/per-bank${query ? `?${query}` : ""}`);

  if (!res.ok) {
    throw new Error("Failed to fetch reviews per bank");
  }

  return res.json();
}

export async function getTopRatedBanks(region?: string): Promise<ReviewAnalysisRow[]> {
  const params = new URLSearchParams();
  if (region) params.set("region", region);
  const query = params.toString();
  const res = await apiFetch(`/api/v1/real-estate/reviews/top-rated${query ? `?${query}` : ""}`);

  if (!res.ok) {
    throw new Error("Failed to fetch top rated banks");
  }

  return res.json();
}

export async function getRatedBanks(
  rating: number,
  region?: string
): Promise<RatedBanksResponse> {
  const params = new URLSearchParams({ rating: String(rating) });
  if (region) params.set("region", region);
  const res = await apiFetch(
    `/api/v1/real-estate/reviews/rated-banks?${params.toString()}`
  );

  if (!res.ok) {
    throw new Error("Failed to fetch rated banks");
  }

  return res.json();
}

export async function getAvgSentimentByBank(region?: string): Promise<ReviewAnalysisRow[]> {
  const params = new URLSearchParams();
  if (region) params.set("region", region);
  const query = params.toString();
  const res = await apiFetch(
    `/api/v1/real-estate/reviews/avg-sentiment-by-bank${query ? `?${query}` : ""}`
  );

  if (!res.ok) {
    throw new Error("Failed to fetch average sentiment by bank");
  }

  return res.json();
}

export async function getReviewTopicsDistribution(
  bank?: string
): Promise<ReviewAnalysisRow[]> {
  const params = new URLSearchParams();
  if (bank) params.append("bank", bank);
  const query = params.toString();

  const res = await apiFetch(
    `/api/v1/real-estate/reviews/review-topics-distribution${query ? `?${query}` : ""}`
  );

  if (!res.ok) {
    throw new Error("Failed to fetch review topics distribution");
  }

  return res.json();
}

export async function getAvgRatingByTopic(
  bank?: string
): Promise<ReviewAnalysisRow[]> {
  const params = new URLSearchParams();
  if (bank) params.append("bank", bank);
  const query = params.toString();

  const res = await apiFetch(
    `/api/v1/real-estate/reviews/avg-rating-by-topic${query ? `?${query}` : ""}`
  );

  if (!res.ok) {
    throw new Error("Failed to fetch average rating by topic");
  }

  return res.json();
}

export async function getSocialFilters(): Promise<SocialFiltersResponse> {
  const endpoints = [
    "/api/v1/real-estate/social-data/filters",
    "/api/v1/social-data/filters",
  ];

  for (const endpoint of endpoints) {
    const res = await apiFetch(endpoint);

    if (res.ok) {
      return res.json();
    }

    if (res.status !== 404) {
      throw new Error("Failed to fetch social filters");
    }
  }

  throw new Error("Failed to fetch social filters");
}

export async function getSocialPostsDistribution(
  filters?: SocialFilters
): Promise<SocialPostDistributionResponse> {
  const query = buildSocialQueryParams(filters);
  const endpoints = [
    `/api/v1/real-estate/social-data/posts-distribution${query}`,
    `/api/v1/social-data/posts-distribution${query}`,
  ];

  for (const endpoint of endpoints) {
    const res = await apiFetch(endpoint);

    if (res.ok) {
      return res.json();
    }

    if (res.status !== 404) {
      throw new Error("Failed to fetch social posts distribution");
    }
  }

  throw new Error("Failed to fetch social posts distribution");
}

export async function getSocialVolumeTrend(
  frequency: SocialVolumeTrendFrequency,
  filters?: SocialFilters
): Promise<SocialVolumeTrendResponse> {
  const query = buildSocialQueryParams(filters, { frequency });
  const endpoints = [
    `/api/v1/real-estate/social-data/volume-trend${query}`,
    `/api/v1/social-data/volume-trend${query}`,
  ];

  for (const endpoint of endpoints) {
    const res = await apiFetch(endpoint);

    if (res.ok) {
      return res.json();
    }

    if (res.status !== 404) {
      throw new Error("Failed to fetch social volume trend");
    }
  }

  throw new Error("Failed to fetch social volume trend");
}

export async function getSocialEngagementTrend(
  frequency: SocialVolumeTrendFrequency,
  filters?: SocialFilters
): Promise<SocialEngagementTrendResponse> {
  const query = buildSocialQueryParams(filters, { frequency });
  const endpoints = [
    `/api/v1/real-estate/social-data/engagement-trend${query}`,
    `/api/v1/social-data/engagement-trend${query}`,
  ];

  for (const endpoint of endpoints) {
    const res = await apiFetch(endpoint);

    if (res.ok) {
      return res.json();
    }

    if (res.status !== 404) {
      throw new Error("Failed to fetch social engagement trend");
    }
  }

  throw new Error("Failed to fetch social engagement trend");
}

export async function getSocialTopGrowing(
  filters?: SocialFilters
): Promise<SocialTopGrowingResponse> {
  const query = buildSocialQueryParams(filters);
  const endpoints = [
    `/api/v1/real-estate/social-data/top-growing${query}`,
    `/api/v1/social-data/top-growing${query}`,
  ];

  for (const endpoint of endpoints) {
    const res = await apiFetch(endpoint);

    if (res.ok) {
      return res.json();
    }

    if (res.status !== 404) {
      throw new Error("Failed to fetch social top growing banks");
    }
  }

  throw new Error("Failed to fetch social top growing banks");
}

export async function getSocialTopTopics(
  limit = 10
): Promise<SocialTopTopicsResponse> {
  const params = new URLSearchParams({ limit: String(limit) });
  const endpoints = [
    `/api/v1/real-estate/social-data/sentiment/top-topics?${params.toString()}`,
    `/api/v1/social-data/sentiment/top-topics?${params.toString()}`,
  ];

  for (const endpoint of endpoints) {
    const res = await apiFetch(endpoint);

    if (res.ok) {
      return res.json();
    }

    if (res.status !== 404) {
      throw new Error("Failed to fetch social top topics");
    }
  }

  throw new Error("Failed to fetch social top topics");
}

async function getSocialSentimentList(
  path: string,
  errorMessage: string,
  params?: URLSearchParams
): Promise<SocialSentimentListResponse> {
  const query = params ? `?${params.toString()}` : "";
  const endpoints = [
    `/api/v1/real-estate/social-data/${path}${query}`,
    `/api/v1/social-data/${path}${query}`,
  ];

  for (const endpoint of endpoints) {
    const res = await apiFetch(endpoint);

    if (res.ok) {
      return res.json();
    }

    if (res.status !== 404) {
      throw new Error(errorMessage);
    }
  }

  throw new Error(errorMessage);
}

export async function getSocialAvgSentimentByTopic(): Promise<SocialSentimentListResponse> {
  return getSocialSentimentList(
    "sentiment/avg-by-topic",
    "Failed to fetch average sentiment by topic"
  );
}

export async function getSocialAvgSentimentByBank(): Promise<SocialSentimentListResponse> {
  return getSocialSentimentList(
    "sentiment/avg-by-bank",
    "Failed to fetch average sentiment by bank"
  );
}

export async function getSocialTopBanksBySentiment(
  limit = 10
): Promise<SocialSentimentListResponse> {
  return getSocialSentimentList(
    "sentiment/top-banks",
    "Failed to fetch top banks by sentiment",
    new URLSearchParams({ limit: String(limit) })
  );
}

async function getSocialAssociationsList(
  path: string,
  errorMessage: string,
  params?: URLSearchParams
): Promise<SocialAssociationsResponse> {
  const query = params ? `?${params.toString()}` : "";
  const endpoints = [
    `/api/v1/real-estate/social-data/${path}${query}`,
    `/api/v1/social-data/${path}${query}`,
  ];

  for (const endpoint of endpoints) {
    const res = await apiFetch(endpoint);

    if (res.ok) {
      return res.json();
    }

    if (res.status !== 404) {
      throw new Error(errorMessage);
    }
  }

  throw new Error(errorMessage);
}

export async function getSocialAssociationsDistribution(
  filters?: Pick<SocialFilters, "bank" | "platform" | "startDate" | "endDate"> & {
    associations?: string[];
  }
): Promise<SocialAssociationsResponse> {
  const params = new URLSearchParams();
  if (filters?.bank) params.append("bank", filters.bank);
  if (filters?.platform) params.append("platform", filters.platform);
  if (filters?.startDate) params.append("start_date", filters.startDate);
  if (filters?.endDate) params.append("end_date", filters.endDate);
  filters?.associations
    ?.filter(Boolean)
    .slice(0, 5)
    .forEach((association) => params.append("associations", association));

  return getSocialAssociationsList(
    "associations/distribution",
    "Failed to fetch associations distribution",
    params.size > 0 ? params : undefined
  );
}

export async function getSocialAssociationsOverTime(
  frequency: SocialVolumeTrendFrequency,
  filters?: Pick<SocialFilters, "bank" | "platform" | "startDate" | "endDate"> & {
    associations?: string[];
  }
): Promise<SocialAssociationsResponse> {
  const params = new URLSearchParams({ frequency });
  if (filters?.bank) params.append("bank", filters.bank);
  if (filters?.platform) params.append("platform", filters.platform);
  if (filters?.startDate) params.append("start_date", filters.startDate);
  if (filters?.endDate) params.append("end_date", filters.endDate);
  filters?.associations
    ?.filter(Boolean)
    .slice(0, 5)
    .forEach((association) => params.append("associations", association));

  return getSocialAssociationsList(
    "associations/top5-over-time",
    "Failed to fetch associations over time",
    params
  );
}

export type SearchDataFrequency = "1m" | "3m" | "6m" | "1y";

export type SearchDataRow = Record<string, unknown>;

export type SearchFilters = {
  bank?: string;
  banks?: string[];
  product?: string;
  products?: string[];
  startDate?: string;
  endDate?: string;
};

export type SearchFiltersResponse = {
  data: Record<string, unknown>;
};

export type SearchBankDistributionResponse = {
  distribution: SearchDataRow[];
};

export type SearchOverTimeResponse = {
  data: SearchDataRow[];
};

export type SearchTopGrowingBanksResponse = {
  top_growing_banks: SearchDataRow[];
};

export type SearchTopGrowingProductsResponse = {
  top_growing_products: SearchDataRow[];
};

export type SearchProductMapItem = {
  category?: string | null;
  keyword?: string | null;
  geo_code: string;
  geo_name: string;
  country: string;
  score: number;
};

export type SearchProductMapsResponse = {
  data: SearchProductMapItem[];
};

function buildSearchQueryParams(
  filters?: SearchFilters,
  extra?: Record<string, string | number | undefined>,
  options?: { includeDates?: boolean }
) {
  const params = new URLSearchParams();

  const banks = filters?.banks?.filter(Boolean).slice(0, 5) ?? [];
  if (banks.length > 0) {
    banks.forEach((bank) => params.append("bank", bank));
  } else if (filters?.bank) {
    params.append("bank", filters.bank);
  }

  if (filters?.product) params.append("product", filters.product);
  filters?.products
    ?.filter(Boolean)
    .slice(0, 5)
    .forEach((product) => params.append("products", product));

  if (options?.includeDates !== false) {
    if (filters?.startDate) params.append("start_date", filters.startDate);
    if (filters?.endDate) params.append("end_date", filters.endDate);
  }

  Object.entries(extra ?? {}).forEach(([key, value]) => {
    if (value !== undefined && value !== "") {
      params.append(key, String(value));
    }
  });

  return params;
}

async function getSearchData<T>(
  path: string,
  errorMessage: string,
  params?: URLSearchParams
): Promise<T> {
  const paramString = params?.toString();
  const query = paramString ? `?${paramString}` : "";
  const endpoints = [
    `/api/v1/real-estate/search-data/${path}${query}`,
    `/api/v1/search-data/${path}${query}`,
  ];

  for (const endpoint of endpoints) {
    const res = await apiFetch(endpoint);

    if (res.ok) {
      return res.json();
    }

    if (res.status !== 404) {
      throw new Error(errorMessage);
    }
  }

  throw new Error(errorMessage);
}

export async function getSearchFilters(): Promise<SearchFiltersResponse> {
  return getSearchData("filters", "Failed to fetch search filters");
}

/**
 * search-data's own developer name vocabulary (Google Trends keywords) —
 * distinct from /filters/banks (social_data's shorter names). Use this list,
 * not getDigitalBrandHealthBanks, for the bank/banks param on any
 * /search-data/* endpoint (top5, distribution, top-growing, maps, etc.) —
 * mixing vocabularies returns empty results for names that don't match
 * verbatim (e.g. "Aldar" vs. search-data's "Aldar Properties").
 */
export async function getSearchDataBanks(): Promise<BanksFilterResponse> {
  return getSearchData("banks", "Failed to fetch search data developer names");
}

export async function getSearchBankDistribution(
  filters?: SearchFilters
): Promise<SearchBankDistributionResponse> {
  return getSearchData(
    "distribution",
    "Failed to fetch search bank distribution",
    buildSearchQueryParams(filters)
  );
}

export async function getSearchDistributionOverTime(
  frequency: SearchDataFrequency,
  filters?: SearchFilters
): Promise<SearchOverTimeResponse> {
  return getSearchData(
    "distribution-over-time",
    "Failed to fetch search distribution over time",
    buildSearchQueryParams(filters, { frequency })
  );
}

export async function getSearchTopGrowingBanks(
  filters?: SearchFilters
): Promise<SearchTopGrowingBanksResponse> {
  return getSearchData(
    "top-growing",
    "Failed to fetch top growing banks",
    buildSearchQueryParams(filters)
  );
}

async function getSearchProductsData<T>(
  path: string,
  errorMessage: string,
  params?: URLSearchParams
): Promise<T> {
  const paramString = params?.toString();
  const query = paramString ? `?${paramString}` : "";
  const endpoints = [
    `/api/v1/real-estate/search-products/${path}${query}`,
    `/api/v1/search-products/${path}${query}`,
  ];

  for (const endpoint of endpoints) {
    const res = await apiFetch(endpoint);

    if (res.ok) {
      return res.json();
    }

    if (res.status !== 404) {
      throw new Error(errorMessage);
    }
  }

  throw new Error(errorMessage);
}

export async function getSearchProductDistribution(
  filters?: SearchFilters
): Promise<SearchBankDistributionResponse> {
  return getSearchProductsData(
    "distribution",
    "Failed to fetch search product distribution",
    buildSearchQueryParams(filters)
  );
}

export async function getSearchProductDistributionOverTime(
  frequency: SearchDataFrequency,
  filters?: SearchFilters
): Promise<SearchOverTimeResponse> {
  return getSearchProductsData(
    "distribution-over-time",
    "Failed to fetch search product distribution over time",
    buildSearchQueryParams(filters, { frequency })
  );
}

export async function getSearchProductTopGrowing(
  filters?: SearchFilters
): Promise<SearchTopGrowingProductsResponse> {
  return getSearchProductsData(
    "top-growing",
    "Failed to fetch top growing products",
    buildSearchQueryParams(filters)
  );
}

export async function getSearchProductMaps(
  filters?: SearchFilters
): Promise<SearchProductMapsResponse> {
  return getSearchProductsData(
    "maps",
    "Failed to fetch search product maps",
    // google_trends_regions is a periodic full re-scrape, not a daily
    // series — start_date/end_date would filter by refresh date, not
    // reporting period, and with only one snapshot so far would zero out
    // the result. Omit dates until there's more than one refresh to pick.
    buildSearchQueryParams(filters, undefined, { includeDates: false })
  );
}

export async function getSearchDataMaps(
  filters?: SearchFilters
): Promise<SearchProductMapsResponse> {
  return getSearchData(
    "maps",
    "Failed to fetch search data maps",
    buildSearchQueryParams(filters, undefined, { includeDates: false })
  );
}
