import { apiFetch } from "./apiClient";

/* =========================
   TYPES
========================= */

export type Filters = {
  markets?: string[];
  retailers?: string[];
  segments?: string[];
  comp?: string[];
  brands?: string[];
  types?: string[];
  quantity?: string[];
  skus?: number[];
  subTypes?: string[];
  local?: boolean;
  date?: string;
  regions?: string[];
  cities?: string[];
  startDate?: string;
  endDate?: string;
};

/* =========================
   QUERY BUILDER
========================= */

function buildQueryParams(filters?: Filters) {
  if (!filters) return "";

  const params = new URLSearchParams();

  const map: Record<string, (string | number)[] | undefined> = {
    market: filters.markets,
    region: filters.regions,
    city: filters.cities,
    retailer: filters.retailers,
    segment: filters.segments,
    comp: filters.comp,
    brand: filters.brands,
    type: filters.types,
    quantity: filters.quantity,
    sku: filters.skus,
    sub_type: filters.subTypes,
  };

  Object.entries(map).forEach(([key, values]) => {
    values?.forEach((v) => params.append(key, String(v)));
  });

  if (filters.local !== undefined) {
    params.append("local", String(filters.local));
  }

  if (filters.date) {
    params.append("date", filters.date);
  }

  if (filters.startDate) {
    params.append("start_date", filters.startDate);
  }

  if (filters.endDate) {
    params.append("end_date", filters.endDate);
  }

  return params.toString() ? `?${params.toString()}` : "";
}

/* =========================
   GENERIC FETCH WRAPPER
========================= */

async function fetchWithFilters(
  url: string,
  filters?: Filters,
  errorMessage?: string
) {
  const query = buildQueryParams(filters);
  const res = await apiFetch(`${url}${query}`);

  if (!res.ok) {
    throw new Error(errorMessage || "API request failed");
  }

  return res.json();
}

/* =========================
   FILTERS (DYNAMIC)
========================= */

/**
 * GET /api/v1/beer/filters
 * Response may additionally include:
 *   date_range?: { min: string; max: string }  // ISO yyyy-mm-dd, earliest/latest week of available pricing data
 * Optional/absent until the backend ships this field — callers must treat it as possibly undefined.
 */
export async function getFilters(filters?: Filters) {
  return fetchWithFilters(
    `/api/v1/beer/filters`,
    filters,
    "Failed to fetch filters"
  );
}

/* =========================
   RETAILERS (DEPENDENT)
========================= */

export async function getRetailers(filters?: Filters) {
  return fetchWithFilters(
    `/api/v1/beer/retailers`,
    filters,
    "Failed to fetch retailers"
  );
}

/* =========================
   KPI / OVERVIEW
========================= */

export async function getKPIs(filters?: Filters) {
  return fetchWithFilters(
    `/api/v1/beer/overview`,
    filters,
    "Failed to fetch KPIs"
  );
}

/* =========================
   PRICE TREND
========================= */

export async function getPriceTrend(filters?: Filters) {
  return fetchWithFilters(
    `/api/v1/beer/price-trend`,
    filters,
    "Failed to fetch price trend"
  );
}

/* =========================
   CORE COMPETITION
========================= */

export async function getCoreCompetition(filters?: Filters) {
  return fetchWithFilters(
    `/api/v1/beer/core-competition-pricing-comparison`,
    filters,
    "Failed to fetch competition"
  );
}

/* =========================
   PROMOTION TREND
========================= */

export async function getPromotionTrend(filters?: Filters) {
  return fetchWithFilters(
    `/api/v1/beer/promotion-sku-trending`,
    filters,
    "Failed to fetch promotion trend"
  );
}

/* =========================
   DISCOUNT TREND
========================= */

export async function getDiscountTrend(filters?: Filters) {
  return fetchWithFilters(
    `/api/v1/beer/discount-trending`,
    filters,
    "Failed to fetch discount trend"
  );
}

/* =========================
   PRICE GAP
========================= */

export async function getListVsPromoPriceGap(filters?: Filters) {
  return fetchWithFilters(
    `/api/v1/beer/list-vs-promo-price-gap`,
    filters,
    "Failed to fetch price gap"
  );
}

/* =========================
   PROMOTION SKU TREND CORE COMPETITION
========================= */

export async function getPromotionTrendCoreCompetition(filters?: Filters) {
  return fetchWithFilters(
    `/api/v1/beer/promotion-sku-trending-core-competition`,
    filters,
    "Failed to fetch promotion sku trend core competition"
  );
}

/* =========================
   DISCOUNT TREND CORE COMPETITION
========================= */

export async function getDiscountTrendCoreCompetition(filters?: Filters) {
  return fetchWithFilters(
    `/api/v1/beer/discount-trending-core-competition-comparison`,
    filters,
    "Failed to fetch discount trend core competition"
  );
}

/* =========================
   DISCOUNT TREND CORE COMPETITION
========================= */

export async function getListVsPromoPriceGapCoreCompetition(filters?: Filters) {
  return fetchWithFilters(
    `/api/v1/beer/list-vs-promo-price-gap-core-competition`,
    filters,
    "Failed to fetch list vs promo price gap core competition"
  );
}

/* =========================
   AVAILABILITY TREND
========================= */

export async function getAvailabilityTrend(filters?: Filters) {
  return fetchWithFilters(
    `/api/v1/beer/availability-trending`,
    filters,
    "Failed to fetch availability trend"
  );
}

/* =========================
   TOTAL ACTIVE SKUS
========================= */

export async function getTotalActiveSkusTrend(filters?: Filters) {
  return fetchWithFilters(
    `/api/v1/beer/total-active-skus-trending`,
    filters,
    "Failed to fetch total SKUs"
  );
}

/* =========================
   OUT OF STOCK SKUS
========================= */

export async function getOutOfStockSkusTrend(filters?: Filters) {
  return fetchWithFilters(
    `/api/v1/beer/out-of-stock-skus-trending`,
    filters,
    "Failed to fetch out-of-stock SKUs"
  );
}

/* =========================
   SHARE OF VISIBILITY
========================= */

export async function getShareOfVisibilityHeinekenPortfolio(
  filters?: Filters
) {
  return fetchWithFilters(
    `/api/v1/beer/share-of-visibility-heineken-portfolio`,
    filters,
    "Failed to fetch visibility"
  );
}

/* =========================
   CAN VS BOTTLE
========================= */

export async function getCanVsBottleTrend(filters?: Filters) {
  return fetchWithFilters(
    `/api/v1/beer/can-vs-bottle-trend`,
    filters,
    "Failed to fetch can vs bottle trend"
  );
}

export async function getCanVsBottleMix(filters?: Filters) {
  return fetchWithFilters(
    `/api/v1/beer/can-vs-bottle-mix`,
    filters,
    "Failed to fetch can vs bottle mix"
  );
}

/* =========================
   PACK SIZE
========================= */

export async function getPackSizeDistributionTrend(filters?: Filters) {
  return fetchWithFilters(
    `/api/v1/beer/pack-size-distribution-trend`,
    filters,
    "Failed to fetch pack size distribution"
  );
}

export async function getPackMix(filters?: Filters) {
  return fetchWithFilters(
    `/api/v1/beer/pack-mix`,
    filters,
    "Failed to fetch pack mix"
  );
}

/* =========================
   BRAND LEVEL
========================= */

export async function getPriceTrendsByBrand(filters?: Filters) {
  return fetchWithFilters(
    `/api/v1/beer/price-trends-by-brand`,
    filters,
    "Failed to fetch brand price trends"
  );
}

export async function getPromotionDepthByBrand(filters?: Filters) {
  return fetchWithFilters(
    `/api/v1/beer/promotion-depth-by-brand`,
    filters,
    "Failed to fetch promotion depth"
  );
}

export async function getAvailabilityByBrand(filters?: Filters) {
  return fetchWithFilters(
    `/api/v1/beer/availability-by-brand`,
    filters,
    "Failed to fetch brand availability"
  );
}

/* =========================
   EXPORT
========================= */

export async function getExport(
  filters?: Filters,
  page?: number,
  limit?: number
) {
  const params = new URLSearchParams();

  // 🔹 existing filters
  if (filters) {
    filters.markets?.forEach((m) => params.append("market", m));
    filters.retailers?.forEach((r) => params.append("retailer", r));
    filters.segments?.forEach((s) => params.append("segment", s));
    filters.comp?.forEach((c) => params.append("comp", c));
    filters.brands?.forEach((b) => params.append("brand", b));
    filters.types?.forEach((t) => params.append("type", t));
    filters.quantity?.forEach((q) => params.append("quantity", q));
    filters.skus?.forEach((s) => params.append("sku", s.toString()));
    filters.subTypes?.forEach((s) => params.append("sub_type", s));

    filters.cities?.forEach((c) => params.append("city", c));

    if (filters.local !== undefined) {
      params.append("local", String(filters.local));
    }

    if (filters.date) {
      params.append("date", filters.date);
    }
  }

  // 🔥 NEW PARAMS
  if (page !== undefined) {
    params.append("page", page.toString());
  }

  if (limit !== undefined) {
    params.append("limit", limit.toString());
  }

  const query = params.toString() ? `?${params.toString()}` : "";

  return apiFetch(`/api/v1/beer/export${query}`);
}


export async function getBrandSales(filters?: Filters) {
  return fetchWithFilters(
    `/api/v1/beer/brand-sales`,
    filters,
    "Failed to fetch brand sales"
  );
}


export async function getBrandVisibility(filters?: Filters) {
  return fetchWithFilters(
    `/api/v1/beer/brand-visibility-by-retailer`,
    filters,
    "Failed to fetch brand visibility"
  );
}

export async function getHeroSkuTracker(filters?: Filters) {
  return fetchWithFilters(
    `/api/v1/beer/hero-sku-tracker`,
    filters,
    "Failed to fetch Hero SKU tracker"
  );
}

export async function getHeroSkuTrend(filters?: Filters) {
  return fetchWithFilters(
    `/api/v1/beer/hero-sku-trend`,
    filters,
    "Failed to fetch Hero SKU trend"
  );
}

export async function getHeroSkuPriceTrend(filters?: Filters) {
  return fetchWithFilters(
    `/api/v1/beer/hero-sku-price-trend`,
    filters,
    "Failed to fetch Hero SKU price trend"
  );
}
