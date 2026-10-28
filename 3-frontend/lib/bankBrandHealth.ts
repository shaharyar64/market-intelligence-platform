import { apiFetch } from "./apiClient";

export const BRANDIQ_SCORE_MAX = 60;

export type TopDigitalHealthItem = {
  bank: string;
  avg_score: number;
  rank?: number;
  ai_score?: number | null;
  share_of_search_pct?: number | null;
  rating?: number | null;
  review_volume?: number | null;
  social_sov_pct?: number | null;
  engagement?: number | null;
  project?: string;
  calculated_at?: string;
};

export type TopDigitalHealthResponse = {
  top_digital_health: TopDigitalHealthItem[];
};

export type BrandIQSegment = "normal" | "digital";
export type BrandIQSnapshotResponse = { snapshot: TopDigitalHealthItem[] };
export type BrandIQTrendItem = {
  period: string;
  bank: string;
  avg_score: number;
  project?: string;
  calculated_at?: string;
};
export type BrandIQTrendResponse = { trend: BrandIQTrendItem[] };

export async function getBrandIQSnapshot(
  segment: BrandIQSegment
): Promise<BrandIQSnapshotResponse> {
  const res = await apiFetch(
    `/api/v1/bank-brand-health/exclusive-summary/brand-iq/${segment}/snapshot`
  );
  if (!res.ok) throw new Error("Failed to fetch BrandIQ snapshot");
  return res.json();
}

export async function getBrandIQTrend(
  segment: BrandIQSegment,
  banks: string[] = []
): Promise<BrandIQTrendResponse> {
  const params = new URLSearchParams();
  banks.filter(Boolean).slice(0, 5).forEach((bank) => params.append("banks", bank));
  const query = params.toString();
  const res = await apiFetch(
    `/api/v1/bank-brand-health/exclusive-summary/brand-iq/${segment}/trend${query ? `?${query}` : ""}`
  );
  if (!res.ok) throw new Error("Failed to fetch BrandIQ trend");
  return res.json();
}

export type BankBrandHealthFrequency = "1m" | "3m" | "6m" | "1y";

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

export type AiScoreItem = {
  bank: string;
  score: number;
};

export type AiScoreResponse = Record<string, AiScoreItem[]>;

export type AiScoreOverallItem = {
  bank: string;
  llm?: string;
  score: number;
};

export type AiScoreAudienceAffinityItem = {
  customer_segment: string;
  llm?: string;
  score: number;
  rationale: string;
};

export type AiScoreAudienceAffinityResponse = Record<string, AiScoreAudienceAffinityItem[]>;

export type AiScoreCitationItem = {
  location: string;
  bank?: string | null;
  llm?: string | null;
  platform?: string | null;
  model: string;
  analysis_section?: string | null;
  prompt?: string | null;
  category?: string | null;
  title: string;
  url: string;
};

export type AiScoreCitationsKpi = {
  total_citations: number;
  assistant_count: number;
  assistants: string[];
  unique_urls: number;
  cited_by_all_assistants: number;
  max_overlap: number;
  overlap_distribution: Record<string, number>;
};

export type AiScoreCitationsResponse = {
  citations: AiScoreCitationItem[];
  kpi: AiScoreCitationsKpi;
};

export type CitationAnalysisResponse = {
  kpi: {
    total_citations: number;
    bank_citations: number;
    market_level_citations: number;
    unique_domains: number;
    unique_urls: number;
    cited_by_all_assistants: number;
  };
  by_category: Array<{ category: string; citations: number; share_pct: number }>;
  by_category_assistant: Array<{ category: string; llm: string; citations: number }>;
  by_category_bank: Array<{ bank: string; category: string; citations: number }>;
  by_bank: Array<{
    bank: string;
    citations: number;
    unique_urls: number;
    unique_domains: number;
    share_pct: number;
  }>;
  by_bank_assistant: Array<{ bank: string; llm: string; citations: number }>;
  by_bank_section: Array<{ bank: string; analysis_section: string; citations: number }>;
  top_domains: Array<{ domain: string; citations: number; banks: number; assistants: string[]; sections: string[] }>;
  domain_by_bank: Array<{ bank: string; domain: string; citations: number }>;
  source_mix: Array<{
    bank: string;
    kind: "own_site" | "other_bank_site" | "third_party";
    citations: number;
  }>;
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

export type SocialPostDistributionItem = {
  bank: string;
  total_posts: number;
  likes: number | null;
  shares: number | null;
  comments: number | null;
  views: number | null;
  total_engagement: number | null;
};

export type SocialPostDistributionResponse = {
  distribution: SocialPostDistributionItem[];
};

export type SocialTopGrowingItem = {
  bank: string;
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
    "/api/v1/bank-brand-health/exclusive-summary/top-digital-health"
  );

  if (!res.ok) {
    throw new Error("Failed to fetch top digital health");
  }

  return res.json();
}

export async function getDigitalEquityTrend(
  freq: BankBrandHealthFrequency
): Promise<DigitalEquityTrendResponse> {
  const params = new URLSearchParams({ freq });
  const res = await apiFetch(
    `/api/v1/bank-brand-health/exclusive-summary/digital-equity-trend?${params.toString()}`
  );

  if (!res.ok) {
    throw new Error("Failed to fetch digital equity trend");
  }

  return res.json();
}

export async function getTop3BanksTrend(
  freq: BankBrandHealthFrequency,
  banks: string[] = []
): Promise<Top3BanksTrendResponse> {
  const params = new URLSearchParams({ freq });
  banks
    .filter(Boolean)
    .slice(0, 5)
    .forEach((bank) => params.append("banks", bank));

  const res = await apiFetch(
    `/api/v1/bank-brand-health/exclusive-summary/top3-banks-trend?${params.toString()}`
  );

  if (!res.ok) {
    throw new Error("Failed to fetch top 3 banks trend");
  }

  return res.json();
}

export async function getBankBrandHealthBanks(): Promise<BanksFilterResponse> {
  const endpoints = [
    "/api/v1/bank-brand-health/filters/banks",
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

export async function getBankBrandHealthProducts(): Promise<ProductsFilterResponse> {
  const endpoints = [
    "/api/v1/bank-brand-health/filters/products",
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

export async function getBankBrandHealthAssociations(): Promise<AssociationsFilterResponse> {
  const endpoints = [
    "/api/v1/bank-brand-health/filters/associations",
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

export async function getAiScoreServices(llm = "Overall"): Promise<AiScoreResponse> {
  const params = new URLSearchParams({ llm });
  const res = await apiFetch(`/api/v1/bank-brand-health/ai-score/services?${params.toString()}`);

  if (!res.ok) {
    throw new Error("Failed to fetch AI score services");
  }

  return res.json();
}

export async function getAiScoreProducts(llm = "Overall"): Promise<AiScoreResponse> {
  const params = new URLSearchParams({ llm });
  const res = await apiFetch(`/api/v1/bank-brand-health/ai-score/products?${params.toString()}`);

  if (!res.ok) {
    throw new Error("Failed to fetch AI score products");
  }

  return res.json();
}

export async function getAiScoreOverall(llm = "Overall"): Promise<AiScoreOverallItem[]> {
  const params = new URLSearchParams({ llm });
  const res = await apiFetch(`/api/v1/bank-brand-health/ai-score/overall?${params.toString()}`);

  if (!res.ok) {
    throw new Error("Failed to fetch AI score overall");
  }

  return res.json();
}

export async function getDigitalDiscoverabilityOverall(
  llm = "Overall"
): Promise<AiScoreOverallItem[]> {
  const params = new URLSearchParams({ llm });
  const res = await apiFetch(
    `/api/v1/bank-brand-health/digital-discoverability/overall?${params.toString()}`
  );

  if (!res.ok) {
    throw new Error("Failed to fetch digital discoverability overall");
  }

  return res.json();
}

export async function getDigitalDiscoverabilityServices(
  llm = "Overall"
): Promise<AiScoreResponse> {
  const params = new URLSearchParams({ llm });
  const res = await apiFetch(
    `/api/v1/bank-brand-health/digital-discoverability/services?${params.toString()}`
  );

  if (!res.ok) {
    throw new Error("Failed to fetch digital discoverability services");
  }

  return res.json();
}

export async function getDigitalDiscoverabilityProducts(
  llm = "Overall"
): Promise<AiScoreResponse> {
  const params = new URLSearchParams({ llm });
  const res = await apiFetch(
    `/api/v1/bank-brand-health/digital-discoverability/products?${params.toString()}`
  );

  if (!res.ok) {
    throw new Error("Failed to fetch digital discoverability products");
  }

  return res.json();
}

export async function getDigitalBankingExperience(
  llm = "Overall"
): Promise<AiScoreResponse> {
  const params = new URLSearchParams({ llm });
  const res = await apiFetch(
    `/api/v1/bank-brand-health/digital-banking-experience?${params.toString()}`
  );

  if (!res.ok) {
    throw new Error("Failed to fetch digital banking experience");
  }

  return res.json();
}

export async function getAiScoreAudienceAffinity(
  llm = "Overall",
  bank?: string
): Promise<AiScoreAudienceAffinityResponse> {
  const params = new URLSearchParams({ llm });
  if (bank) params.set("bank", bank);
  const res = await apiFetch(`/api/v1/bank-brand-health/ai-score/audience-affinity?${params.toString()}`);

  if (!res.ok) {
    throw new Error("Failed to fetch AI score audience affinity");
  }

  return res.json();
}

export async function getAiScoreCitations(
  assistant?: string,
  bank?: string
): Promise<AiScoreCitationsResponse> {
  const params = new URLSearchParams();
  if (assistant) params.set("assistant", assistant);
  if (bank) params.set("bank", bank);
  const query = params.toString();
  const res = await apiFetch(
    `/api/v1/bank-brand-health/ai-score/citations${query ? `?${query}` : ""}`
  );

  if (!res.ok) {
    throw new Error("Failed to fetch AI score citations");
  }

  return res.json();
}

export async function getAiScoreBrandProjection(
  llm = "Overall",
  bank?: string
): Promise<AiScoreBrandProjectionResponse> {
  const params = new URLSearchParams({ llm });
  if (bank) params.set("bank", bank);
  const res = await apiFetch(`/api/v1/bank-brand-health/ai-score/brand-projection?${params.toString()}`);

  if (!res.ok) {
    throw new Error("Failed to fetch AI score brand projection");
  }

  return res.json();
}

export async function getAiScorePerceptionBanks(): Promise<BanksFilterResponse> {
  const res = await apiFetch("/api/v1/bank-brand-health/ai-score/banks");

  if (!res.ok) {
    throw new Error("Failed to fetch AI score perception banks");
  }

  return res.json();
}

export async function getReviewsPerBank(): Promise<ReviewAnalysisRow[]> {
  const res = await apiFetch("/api/v1/bank-brand-health/reviews/per-bank");

  if (!res.ok) {
    throw new Error("Failed to fetch reviews per bank");
  }

  return res.json();
}

export async function getTopRatedBanks(): Promise<ReviewAnalysisRow[]> {
  const res = await apiFetch("/api/v1/bank-brand-health/reviews/top-rated");

  if (!res.ok) {
    throw new Error("Failed to fetch top rated banks");
  }

  return res.json();
}

export async function getRatedBanks(rating: number): Promise<RatedBanksResponse> {
  const params = new URLSearchParams({ rating: String(rating) });
  const res = await apiFetch(
    `/api/v1/bank-brand-health/reviews/rated-banks?${params.toString()}`
  );

  if (!res.ok) {
    throw new Error("Failed to fetch rated banks");
  }

  return res.json();
}

export async function getAvgSentimentByBank(): Promise<ReviewAnalysisRow[]> {
  const res = await apiFetch(
    "/api/v1/bank-brand-health/reviews/avg-sentiment-by-bank"
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
    `/api/v1/bank-brand-health/reviews/review-topics-distribution${query ? `?${query}` : ""}`
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
    `/api/v1/bank-brand-health/reviews/avg-rating-by-topic${query ? `?${query}` : ""}`
  );

  if (!res.ok) {
    throw new Error("Failed to fetch average rating by topic");
  }

  return res.json();
}

export async function getSocialFilters(): Promise<SocialFiltersResponse> {
  const endpoints = [
    "/api/v1/bank-brand-health/social-data/filters",
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
    `/api/v1/bank-brand-health/social-data/posts-distribution${query}`,
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
    `/api/v1/bank-brand-health/social-data/volume-trend${query}`,
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
    `/api/v1/bank-brand-health/social-data/engagement-trend${query}`,
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
    `/api/v1/bank-brand-health/social-data/top-growing${query}`,
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
    `/api/v1/bank-brand-health/social-data/sentiment/top-topics?${params.toString()}`,
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
    `/api/v1/bank-brand-health/social-data/${path}${query}`,
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
    `/api/v1/bank-brand-health/social-data/${path}${query}`,
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
    banks.forEach((bank) => params.append("banks", bank));
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
    `/api/v1/bank-brand-health/search-data/${path}${query}`,
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
    `/api/v1/bank-brand-health/search-products/${path}${query}`,
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
    buildSearchQueryParams(filters)
  );
}

export async function getSearchDataMaps(
  filters?: SearchFilters
): Promise<SearchProductMapsResponse> {
  return getSearchData(
    "maps",
    "Failed to fetch search data maps",
    buildSearchQueryParams(filters)
  );
}

export async function getCitationAnalysis(
  assistant?: string
): Promise<CitationAnalysisResponse> {
  const params = new URLSearchParams();
  if (assistant) params.set("assistant", assistant);
  const query = params.toString();
  const res = await apiFetch(
    `/api/v1/bank-brand-health/ai-score/citation-analysis${query ? `?${query}` : ""}`
  );

  if (!res.ok) {
    throw new Error("Failed to fetch citation analysis");
  }

  return res.json();
}
