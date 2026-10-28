"use client";

import { useEffect, useState, useCallback, useMemo, useRef } from "react";
import DashboardTopbar from "@/components/layout/DashboardTopbar";
import { Layers, Blocks, Globe, Map, Users, Star } from "lucide-react";
import GlassStatCard from "@/components/ui/StatCard";
import PieChartCard from "@/components/analytics/charts/PieChartCard";
import BarChartCard from "@/components/analytics/charts/BarChartCard";
import HorizontalBarChartCard from "@/components/analytics/charts/HorizontalBarChartCard";
import SentimentGlassBar from "@/components/analytics/metrics/SentimentGlassBar";
import {
  getFilters,
  getHorecaSpatialHorecaRatingDistribution,
  getHorecaSpatialReviewTopics,
  getHorecaSpatialTop10,
  getHorecaSpatialReviewKpis,
  getHorecaSpatialReviewSenDis,
} from "@/lib/horecaSpatial";
import FilterSelect from "@/components/filters/FilterSelect";
import FilterRating from "@/components/filters/FilterRating";
import TopRatedRestaurantsCard from "@/components/dashboard/TopRatedRestaurantsCard";

// ─── Types ────────────────────────────────────────────────────────────────────

interface FiltersResponse {
  cuisine: string[];
  horeca_type: string[];
  price_range: string[];
  rating: { min: number; max: number };
}

interface SelectedFilters {
  cuisine: string[];
  horeca_type: string[];
  price_range: string[];
  min_rating?: number;
}

interface DashboardData {
  ratingDistribution: any[] | null;
  reviewTopics: any | null;
  top10Restaurants: any | null;
  reviewKpis: any | null;
  sentimentDistribution: any | null;
}

interface LoadingState {
  kpis: boolean;
  sentiment: boolean;
  ratingDist: boolean;
  topics: boolean;
  top10: boolean;
}

interface ErrorState {
  kpis?: string;
  sentiment?: string;
  ratingDist?: string;
  topics?: string;
  top10?: string;
}

// ─── Constants ────────────────────────────────────────────────────────────────

const DEBOUNCE_MS = 300;

const DEFAULT_FILTERS: SelectedFilters = {
  cuisine: [],
  horeca_type: [],
  price_range: [],
  min_rating: undefined,
};

const DEFAULT_LOADING: LoadingState = {
  kpis: true,
  sentiment: true,
  ratingDist: true,
  topics: true,
  top10: true,
};

// ─── Component ────────────────────────────────────────────────────────────────

export default function HorecaSpatialReviewAnalysisPage() {
  const [data, setData] = useState<DashboardData>({
    ratingDistribution: null,
    reviewTopics: null,
    top10Restaurants: null,
    reviewKpis: null,
    sentimentDistribution: null,
  });

  const [loading, setLoading] = useState<LoadingState>(DEFAULT_LOADING);
  const [errors, setErrors] = useState<ErrorState>({});
  const [filters, setFilters] = useState<FiltersResponse | null>(null);
  const [selectedFilters, setSelectedFilters] =
    useState<SelectedFilters>(DEFAULT_FILTERS);

  // Track latest request to ignore stale responses
  const fetchIdRef = useRef(0);

  // ── Load available filter options once ──────────────────────────────────────
  useEffect(() => {
    getFilters()
      .then(setFilters)
      .catch((err) => console.error("Failed to load filters:", err));
  }, []);

  // ── Consolidated data fetch with debounce & stale-request guard ─────────────
  useEffect(() => {
    const fetchId = ++fetchIdRef.current;

    // Reset to loading on every filter change
    setLoading(DEFAULT_LOADING);
    setErrors({});

    const timer = setTimeout(async () => {
      // Guard: if a newer fetch has started, bail out
      if (fetchId !== fetchIdRef.current) return;

      const setKeyLoading = (key: keyof LoadingState, value: boolean) =>
        setLoading((prev) => ({ ...prev, [key]: value }));

      const setKeyError = (key: keyof ErrorState, msg: string) =>
        setErrors((prev) => ({ ...prev, [key]: msg }));

      const setKeyData = <K extends keyof DashboardData>(
        key: K,
        value: DashboardData[K]
      ) => setData((prev) => ({ ...prev, [key]: value }));

      // Fire all fetches concurrently; each updates independently
      const fetches = [
        getHorecaSpatialReviewKpis(selectedFilters)
          .then((d) => {
            if (fetchId !== fetchIdRef.current) return;
            setKeyData("reviewKpis", d);
          })
          .catch(() => setKeyError("kpis", "Failed to load KPIs"))
          .finally(() => setKeyLoading("kpis", false)),

        getHorecaSpatialReviewSenDis(selectedFilters)
          .then((d) => {
            if (fetchId !== fetchIdRef.current) return;
            setKeyData("sentimentDistribution", d);
          })
          .catch(() => setKeyError("sentiment", "Failed to load sentiment"))
          .finally(() => setKeyLoading("sentiment", false)),

        getHorecaSpatialHorecaRatingDistribution(selectedFilters)
          .then((d) => {
            if (fetchId !== fetchIdRef.current) return;
            setKeyData("ratingDistribution", d);
          })
          .catch(() => setKeyError("ratingDist", "Failed to load rating distribution"))
          .finally(() => setKeyLoading("ratingDist", false)),

        getHorecaSpatialReviewTopics(selectedFilters)
          .then((d) => {
            if (fetchId !== fetchIdRef.current) return;
            setKeyData("reviewTopics", d);
          })
          .catch(() => setKeyError("topics", "Failed to load topics"))
          .finally(() => setKeyLoading("topics", false)),

        getHorecaSpatialTop10(selectedFilters)
          .then((d) => {
            if (fetchId !== fetchIdRef.current) return;
            setKeyData("top10Restaurants", d);
          })
          .catch(() => setKeyError("top10", "Failed to load top restaurants"))
          .finally(() => setKeyLoading("top10", false)),
      ];

      await Promise.allSettled(fetches);
    }, DEBOUNCE_MS);

    return () => clearTimeout(timer);
  }, [selectedFilters]);

  // ── Handlers ─────────────────────────────────────────────────────────────────

  const handleSelectChange = useCallback(
    (key: keyof SelectedFilters, value: string) => {
      setSelectedFilters((prev) => ({
        ...prev,
        [key]: value ? [value] : [],
      }));
    },
    []
  );

  const handleRatingChange = useCallback((value: number) => {
    setSelectedFilters((prev) => ({ ...prev, min_rating: value }));
  }, []);

  const resetFilters = useCallback(() => {
    setSelectedFilters(DEFAULT_FILTERS);
  }, []);

  // ── Derived / memoised values ─────────────────────────────────────────────

  const buildOptions = useCallback(
    (items: string[], label: string) => [
      { label, value: "" },
      ...items.map((item) => ({ label: item, value: item })),
    ],
    []
  );

  const pieData = useMemo(
    () =>
      data.ratingDistribution?.map((item: any) => ({
        name: item.rating,
        value: item.percentage,
      })) ?? [],
    [data.ratingDistribution]
  );

  const barData = useMemo(
    () =>
      data.ratingDistribution?.map((item: any) => ({
        name: item.rating,
        value: item.count,
      })) ?? [],
    [data.ratingDistribution]
  );

  // ── Render ────────────────────────────────────────────────────────────────

  return (
    <div className="min-h-screen bg-transparent">
      <DashboardTopbar title="Horeca Spatial Intelligence" />
      <div className="p-8 space-y-6">
        {/* ── Filter Panel ─────────────────────────────────────────────────── */}
        <div className="rounded-2xl bg-[var(--card-bg)] p-6 shadow-xl border border-[var(--card-bd)]">
          {filters ? (
            <div className="grid grid-cols-1 md:grid-cols-4 gap-4">
              <FilterSelect
                label="Cuisine"
                value={selectedFilters.cuisine[0] || ""}
                onChange={(val) => handleSelectChange("cuisine", val)}
                options={buildOptions(filters.cuisine, "All Cuisines")}
              />
              <FilterSelect
                label="Horeca Type"
                value={selectedFilters.horeca_type[0] || ""}
                onChange={(val) => handleSelectChange("horeca_type", val)}
                options={buildOptions(filters.horeca_type, "All Horeca Types")}
              />
              <FilterSelect
                label="Price Range"
                value={selectedFilters.price_range[0] || ""}
                onChange={(val) => handleSelectChange("price_range", val)}
                options={buildOptions(filters.price_range, "All Price Ranges")}
              />
              <FilterRating
                label="Minimum Rating"
                min={filters.rating.min}
                max={filters.rating.max}
                value={selectedFilters.min_rating ?? filters.rating.min}
                onChange={handleRatingChange}
              />
            </div>
          ) : (
            // Filter skeleton while options are loading
            <div className="grid grid-cols-1 md:grid-cols-4 gap-4">
              {Array.from({ length: 4 }).map((_, i) => (
                <div
                  key={i}
                  className="h-10 rounded-xl bg-slate-700 animate-pulse"
                />
              ))}
            </div>
          )}

          <div className="flex justify-end mt-6">
            <button
              onClick={resetFilters}
              className="px-5 py-2 text-sm bg-white text-slate-900 rounded-xl hover:bg-slate-200 transition"
            >
              Reset Filters
            </button>
          </div>
        </div>

        {/* ── KPI Cards ────────────────────────────────────────────────────── */}
        <div className="rounded-2xl bg-[var(--card-bg-2)] border border-[var(--card-bd)] p-6 shadow-lg">
          {errors.kpis && <ErrorBanner message={errors.kpis} />}
          <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-4 gap-6">
            <GlassStatCard
              title="Total Reviews"
              value={data.reviewKpis?.total_reviews}
              loading={loading.kpis}
              icon={<Blocks size={18} />}
              gradient="from-emerald-500 to-teal-500"
            />
            <GlassStatCard
              title="Positive Reviews"
              value={data.reviewKpis?.positive_reviews}
              loading={loading.kpis}
              icon={<Star size={18} />}
              gradient="from-amber-500 to-orange-500"
            />
            <GlassStatCard
              title="Negative Reviews"
              value={data.reviewKpis?.negative_reviews}
              loading={loading.kpis}
              icon={<Users size={18} />}
              gradient="from-rose-500 to-red-500"
            />
            <GlassStatCard
              title="Average Rating"
              value={data.reviewKpis?.avg_rating}
              loading={loading.kpis}
              icon={<Star size={18} />}
              gradient="from-violet-500 to-purple-500"
            />
          </div>
        </div>

        {/* ── Sentiment Bar ─────────────────────────────────────────────────── */}
        <div className="rounded-2xl bg-[var(--card-bg-2)] border border-[var(--card-bd)] p-6 shadow-lg">
          {errors.sentiment && <ErrorBanner message={errors.sentiment} />}
          <SentimentGlassBar data={data.sentimentDistribution} />
        </div>

        {/* ── Rating Distribution ───────────────────────────────────────────── */}
        <div className="rounded-2xl bg-[var(--card-bg-2)] border border-[var(--card-bd)] p-6 shadow-lg">
          {errors.ratingDist && <ErrorBanner message={errors.ratingDist} />}
          <div className="grid grid-cols-1 lg:grid-cols-[33%_65%] gap-6">
            <PieChartCard
              title="Rating Distribution (%)"
              data={pieData}
              loading={loading.ratingDist}
            />
            <BarChartCard
              title="Rating Distribution (Count)"
              data={barData}
              loading={loading.ratingDist}
            />
          </div>
        </div>

        {/* ── Topics ───────────────────────────────────────────────────────── */}
        <div className="rounded-2xl bg-[var(--card-bg-2)] border border-[var(--card-bd)] p-6 shadow-lg">
          {errors.topics && <ErrorBanner message={errors.topics} />}
          <HorizontalBarChartCard
            title="Topics Wise Reviews"
            data={data.reviewTopics}
            height={900}
            loading={loading.topics}
          />
        </div>

        {/* ── Top Rated Restaurants ─────────────────────────────────────────── */}
        <div className="rounded-2xl bg-[var(--card-bg-2)] border border-[var(--card-bd)] p-6 shadow-lg">
          {errors.top10 && <ErrorBanner message={errors.top10} />}
          <TopRatedRestaurantsCard
            highRated={data.top10Restaurants?.top_high_rated ?? []}
            lowRated={data.top10Restaurants?.top_low_rated ?? []}
          />
        </div>
      </div>
    </div>
  );
}

// ─── Small reusable error banner ─────────────────────────────────────────────

function ErrorBanner({ message }: { message: string }) {
  return (
    <div className="mb-4 rounded-lg bg-rose-900/40 border border-rose-700 px-4 py-2 text-sm text-rose-300">
      {message}
    </div>
  );
}