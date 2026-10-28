import { apiFetch } from "./apiClient";

function buildQueryParams(filters?: {
  cluster?: string;
  sub_cluster?: string;
  zone?: string;
  country?: string;
  category?: string;
}) {
  if (!filters) return "";

  const params = new URLSearchParams();

  if (filters.cluster) params.append("cluster", filters.cluster);
  if (filters.sub_cluster) params.append("sub_cluster", filters.sub_cluster);
  if (filters.zone) params.append("zone", filters.zone);
  if (filters.country) params.append("country", filters.country);
  if (filters.category) params.append("category", filters.category);

  return params.toString() ? `?${params.toString()}` : "";
}

/* ================= OVERVIEW ================= */

export async function getBankSpatialKPIs(filters?: any) {
  const query = buildQueryParams(filters);
  const res = await apiFetch(
    `/api/v1/bank-spatial/overview/kpis${query}`
  );

  if (!res.ok) throw new Error("Failed to fetch KPIs");
  return res.json();
}

export async function getBankSpatialCategories(filters?: any) {
  const query = buildQueryParams(filters);
  const res = await apiFetch(
    `/api/v1/bank-spatial/overview/categories${query}`
  );

  if (!res.ok) throw new Error("Failed to fetch categories");
  return res.json();
}

export async function getBankSpatialRatingDistribution(filters?: any) {
  const query = buildQueryParams(filters);
  const res = await apiFetch(
    `/api/v1/bank-spatial/overview/rating-distribution${query}`
  );

  if (!res.ok) throw new Error("Failed to fetch rating distribution");
  return res.json();
}

export async function getBankSpatialBanksMarket(filters?: any) {
  const query = buildQueryParams(filters);
  const res = await apiFetch(
    `/api/v1/bank-spatial/overview/network-strength${query}`
  );

  if (!res.ok) throw new Error("Failed to fetch network strength");
  return res.json();
}

/* ================= MAP ================= */

export async function getBankSpatialMapsData(filters?: any) {
  const query = buildQueryParams(filters);
  const res = await apiFetch(
    `/api/v1/bank-spatial/maps/map-data${query}`
  );

  if (!res.ok) throw new Error("Failed to fetch map data");
  return res.json();
}

export async function getFilters() {
  const res = await apiFetch(
    `/api/v1/bank-spatial/overview/filters`
  );

  if (!res.ok) throw new Error("Failed to fetch filters");
  return res.json();
}

/* ================= REVIEW ================= */

export async function getBankSpatialSentimentKPIs(filters?: any) {
  const query = buildQueryParams(filters);
  const res = await apiFetch(
    `/api/v1/bank-spatial/review/kpis${query}`
  );

  if (!res.ok) throw new Error("Failed to fetch sentiment KPIs");
  return res.json();
}

export async function getBankSpatialSentimentSplit(filters?: any) {
  const query = buildQueryParams(filters);
  const res = await apiFetch(
    `/api/v1/bank-spatial/review/sentiment-split${query}`
  );

  if (!res.ok) throw new Error("Failed to fetch sentiment split");
  return res.json();
}

export async function getBankSpatialSentimentDistribution(filters?: any) {
  const query = buildQueryParams(filters);
  const res = await apiFetch(
    `/api/v1/bank-spatial/review/sentiment-score-distribution${query}`
  );

  if (!res.ok)
    throw new Error("Failed to fetch sentiment distribution");
  return res.json();
}

export async function getBankSpatialBankReviews(filters?: any) {
  const query = buildQueryParams(filters);
  const res = await apiFetch(
    `/api/v1/bank-spatial/review/reviews-per-bank${query}`
  );

  if (!res.ok) throw new Error("Failed to fetch reviews");
  return res.json();
}

export async function getBankSpatialBankOutlets(filters?: any) {
  const query = buildQueryParams(filters);
  const res = await apiFetch(
    `/api/v1/bank-spatial/review/outlet-rating-analysis${query}`
  );

  if (!res.ok) throw new Error("Failed to fetch outlet analysis");
  return res.json();
}

export async function getBankSpatialBankSentiment(filters?: any) {
  const query = buildQueryParams(filters);
  const res = await apiFetch(
    `/api/v1/bank-spatial/review/sentiment-analysis${query}`
  );

  if (!res.ok) throw new Error("Failed to fetch sentiment analysis");
  return res.json();
}

export async function getBankSpatialBankCommentsByTopic(filters?: any) {
  const query = buildQueryParams(filters);
  const res = await apiFetch(
    `/api/v1/bank-spatial/review/comments-per-topic${query}`
  );

  if (!res.ok) throw new Error("Failed to fetch topic comments");
  return res.json();
}

export async function getBankSpatialBankSentimentBreakdown(filters?: any) {
  const query = buildQueryParams(filters);
  const res = await apiFetch(
    `/api/v1/bank-spatial/review/topic-sentiment-breakdown${query}`
  );

  if (!res.ok) throw new Error("Failed to fetch topic breakdown");
  return res.json();
}

export async function getBankSpatialBankSentimentBreakdownBanks(
  filters?: any
) {
  const query = buildQueryParams(filters);
  const res = await apiFetch(
    `/api/v1/bank-spatial/review/bank-sentiment-breakdown${query}`
  );

  if (!res.ok) throw new Error("Failed to fetch bank breakdown");
  return res.json();
}


export async function getBankSpatialBankTopicSentimentPercentage(filters?: any) {
  const query = buildQueryParams(filters);
  const res = await apiFetch(
    `/api/v1/bank-spatial/review/topic-distribution-percentage${query}`
  );

  if (!res.ok) throw new Error("Failed to fetch topic sentiment percentage");
  return res.json();
}