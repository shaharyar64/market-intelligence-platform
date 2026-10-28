import { apiFetch } from "./apiClient";


function buildQueryParams(filters?: {
  cuisine?: string[];
  horeca_type?: string[];
  price_range?: string[];
  min_rating?: number;
  max_rating?: number;
}) {
  if (!filters) return "";

  const params = new URLSearchParams();

  filters.cuisine?.forEach((c) => params.append("cuisine", c));
  filters.horeca_type?.forEach((h) => params.append("horeca_type", h));
  filters.price_range?.forEach((p) => params.append("price_range", p));

  if (filters.min_rating !== undefined)
    params.append("min_rating", filters.min_rating.toString());

  if (filters.max_rating !== undefined)
    params.append("max_rating", filters.max_rating.toString());

  return params.toString() ? `?${params.toString()}` : "";
}


/* ================= OVERVIEW ================= */

export async function getFilters() {
  const res = await apiFetch(
    `/api/v1/horeca/overview/filters`
  );

  if (!res.ok) throw new Error("Failed to fetch Horeca Spatial filters");
  return res.json();
}

export async function getHorecaSpatialKPIs(filters?: any) {
  const query = buildQueryParams(filters);
  const res = await apiFetch(
    `/api/v1/horeca/overview/kpis${query}`
  );

  if (!res.ok) throw new Error("Failed to fetch Horeca Spatial KPIs");
  return res.json();
}

export async function getHorecaSpatialHorecaSplit(filters?: any) {
  const query = buildQueryParams(filters);
  const res = await apiFetch(
    `/api/v1/horeca/overview/horeca-split${query}`
  );

  if (!res.ok) throw new Error("Failed to fetch Horeca Spatial Horeca Split");
  return res.json();
}

export async function getHorecaSpatialHorecaPopular(filters?: any) {
  const query = buildQueryParams(filters);
  const res = await apiFetch(
    `/api/v1/horeca/overview/popular-times${query}`
  );

  if (!res.ok) throw new Error("Failed to fetch Horeca Spatial Horeca Split");
  return res.json();
}

export async function getHorecaSpatialHorecaRatingDistribution(filters?: any) {
  const query = buildQueryParams(filters);
  const res = await apiFetch(
    `/api/v1/horeca/overview/rating-distribution${query}`
  );

  if (!res.ok) throw new Error("Failed to fetch Horeca Spatial Rating Distribution");
  return res.json();
}

/* ================= Maps ================= */

export async function getHorecaSpatialMaps(filters?: any) {
  const query = buildQueryParams(filters);
  const res = await apiFetch(
    `/api/v1/horeca/maps/restaurants${query}`
  );

  if (!res.ok) throw new Error("Failed to fetch Horeca Spatial Horeca Split");
  return res.json();
}


/* ================= Deep Dive ================= */

export async function getHorecaSpatialReviewTopics(filters?: any) {
  const query = buildQueryParams(filters);
  const res = await apiFetch(
    `/api/v1/horeca/deep-dive/review-topics${query}`
  );

  if (!res.ok) throw new Error("Failed to fetch Horeca Spatial Review Topics");
  return res.json();
}


export async function getHorecaSpatialTop10(filters?: any) {
  const query = buildQueryParams(filters);
  const res = await apiFetch(
    `/api/v1/horeca/deep-dive/top-rated-restaurants${query}`
  );

  if (!res.ok) throw new Error("Failed to fetch Horeca Spatial Top 10 Restaurants");
  return res.json();
}


export async function getHorecaSpatialReviewKpis(filters?: any) {
  const query = buildQueryParams(filters);
  const res = await apiFetch(
    `/api/v1/horeca/deep-dive/review-kpis${query}`
  );

  if (!res.ok) throw new Error("Failed to fetch Horeca Spatial Review KPIs");
  return res.json();
}


export async function getHorecaSpatialReviewSenDis(filters?: any) {
  const query = buildQueryParams(filters);
  const res = await apiFetch(
    `/api/v1/horeca/deep-dive/review-sentiment-distribution${query}`
  );

  if (!res.ok) throw new Error("Failed to fetch Horeca Spatial Review Sentiment Distribution");
  return res.json();
}


export async function getHorecaSpatialRestaurants(
  filters?: any,
  page: number = 1,
  pageSize: number = 25
) {
  const query = buildQueryParams(filters);

  const pagination = `page=${page}&page_size=${pageSize}`;

  const url = `/api/v1/horeca/deep-dive/restaurants${
    query ? `${query}&${pagination}` : `?${pagination}`
  }`;

  const res = await apiFetch(url);

  if (!res.ok) throw new Error("Failed to fetch Horeca Spatial Restaurants");
  return res.json();
}


/* ================= Restaurant Details ================= */

export async function getHorecaRestaurantDetails(
  placeId: string,
  filters?: {
    cuisine?: string[];
    horeca_type?: string[];
    price_range?: string[];
    min_rating?: number;
    max_rating?: number;
  }
) {
  const query = buildQueryParams(filters);

  const url = `/api/v1/horeca/deep-dive/restaurant-details?place_id=${placeId}${
    query ? `&${query.substring(1)}` : ""
  }`;

  const res = await apiFetch(url);

  if (!res.ok) throw new Error("Failed to fetch restaurant details");

  return res.json();
}


export async function getHorecaRestaurantNames() {
  const res = await apiFetch(
    `/api/v1/horeca/deep-dive/restaurant-names`
  );

  if (!res.ok) throw new Error("Failed to fetch Horeca Spatial Restaurant Names");
  return res.json();
}


/* ================= Rice Analysis ================= */

export async function getRiceKpis(filters?: any) {
  const query = buildQueryParams(filters);

  const res = await apiFetch(
    `/api/v1/horeca/rice/kpis${query}`
  );

  if (!res.ok) throw new Error("Failed to fetch Rice KPIs");

  return res.json();
}


export async function getRicePriceDistribution(filters?: any) {
  const query = buildQueryParams(filters);

  const res = await apiFetch(
    `/api/v1/horeca/rice/price-distribution${query}`
  );

  if (!res.ok) throw new Error("Failed to fetch Rice Price Distribution");

  return res.json();
}


export async function getTopRiceDishes(filters?: any) {
  const query = buildQueryParams(filters);

  const res = await apiFetch(
    `/api/v1/horeca/rice/top-dishes${query}`
  );

  if (!res.ok) throw new Error("Failed to fetch Top Rice Dishes");

  return res.json();
}


export async function getRiceByCuisine(filters?: any) {
  const query = buildQueryParams(filters);

  const res = await apiFetch(
    `/api/v1/horeca/rice/by-cuisine${query}`
  );

  if (!res.ok) throw new Error("Failed to fetch Rice by Cuisine");

  return res.json();
}


export async function getRiceMenuMix(filters?: any) {
  const query = buildQueryParams(filters);

  const res = await apiFetch(
    `/api/v1/horeca/rice/menu-mix${query}`
  );

  if (!res.ok) throw new Error("Failed to fetch Rice Menu Mix");

  return res.json();
}