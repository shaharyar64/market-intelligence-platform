"use client";

import { useEffect, useState } from "react";
import DashboardTopbar from "@/components/layout/DashboardTopbar";
import {
  getFilters,
  getKPIs,
  getRetailers,
  getPriceTrendsByBrand,
  getPromotionDepthByBrand,
  getAvailabilityByBrand
} from "@/lib/pricingAnalysis";
import { getPricingBrandColor } from "@/lib/pricingBrandColors";
import MultiLineChartCard from "@/components/analytics/charts/MultiLineChartCard";
import AreaChartCard from "@/components/analytics/charts/AreaChartCard";
import BarChartCard from "@/components/analytics/charts/BarChartCard";
import FilterSelect from "@/components/filters/FilterSelect";
import FilterMultiSelect from "@/components/filters/FilterMultiSelect";

import { TrendingUpDown, Tag, PercentCircle } from "lucide-react";

/* =========================
   TYPES
========================= */

interface FiltersResponse {
  markets: string[];
  cities: string[];
  segments: string[];
  sub_types: string[];
  comp: string[];
  brands: string[];
  types: string[];
  quantity: string[];
  skus: number[];
}

interface SelectedFilters {
  markets: string[];
  cities: string[];
  retailers: string[];
  segments: string[];
  subTypes: string[];
  comp: string[];
  brands: string[];
  types: string[];
  quantity: string[];
  skus: number[];
  local: boolean;
}

const DEFAULT_SELECTED_FILTERS: SelectedFilters = {
  markets: [],
  cities: [],
  retailers: [],
  segments: ["super premium"],
  subTypes: [],
  comp: [],
  brands: [],
  types: [],
  quantity: [],
  skus: [],
  local: false,
};

const RESET_SELECTED_FILTERS: SelectedFilters = {
  ...DEFAULT_SELECTED_FILTERS,
  segments: [],
};

/* =========================
   PAGE
========================= */

export default function PricingAnalysisSegmentDeepDive() {

  const [filters, setFilters] = useState<FiltersResponse | null>(null);
  const [retailers, setRetailers] = useState<string[]>([]);
  const [kpis, setKpis] = useState<any>(null);
  const [loading, setLoading] = useState(true);

  const [priceTrend, setPriceTrend] = useState<any>({});
  const [promotionDepth, setPromotionDepth] = useState<any>([]);
  const [availability, setAvailability] = useState<any>([]);

  const [selectedFilters, setSelectedFilters] = useState<SelectedFilters>(DEFAULT_SELECTED_FILTERS);
  const [draftSelectedFilters, setDraftSelectedFilters] = useState<SelectedFilters>(DEFAULT_SELECTED_FILTERS);

  /* =========================
     API CALLS (FIXED)
  ========================== */

  // ✅ dynamic filters
  useEffect(() => {
    getFilters()
      .then((res) => setFilters(res.data))
      .catch(() => setFilters(null));
  }, []);

  // ✅ retailers depend on FULL filter state
  useEffect(() => {
    getRetailers()
      .then((res) => setRetailers(res.data))
      .catch(() => setRetailers([]));
  }, []);

  useEffect(() => {
    setLoading(true);
    getKPIs(selectedFilters)
      .then((res) => setKpis(res.data))
      .finally(() => setLoading(false));
  }, [selectedFilters]);

  useEffect(() => {
    getPriceTrendsByBrand(selectedFilters)
      .then((res) => setPriceTrend(res.data || {}))
      .catch(() => setPriceTrend({}));
  }, [selectedFilters]);

  useEffect(() => {
    getPromotionDepthByBrand(selectedFilters)
      .then((res) => setPromotionDepth(res.data || []))
      .catch(() => setPromotionDepth([]));
  }, [selectedFilters]);

  useEffect(() => {
    getAvailabilityByBrand(selectedFilters)
      .then((res) => setAvailability(res.data || []))
      .catch(() => setAvailability([]));
  }, [selectedFilters]);

  /* =========================
     SAFE DATA
  ========================== */

  const currency = kpis?.pricing_currency || "USD";

  const transformBrandTrendData = (data: any) => {
    if (!data || Object.keys(data).length === 0) return [];

    const brands = Object.keys(data);
    const dates = data[brands[0]]?.map((item: any) => item.date) || [];

    return dates.map((date: string, i: number) => {
      const obj: any = {
        date: new Date(date).toLocaleDateString("en-GB", {
          day: "2-digit",
          month: "short",
        }),
      };

      brands.forEach((brand) => {
        obj[`${brand}_listing`] = data[brand]?.[i]?.listing_price;
        obj[`${brand}_promo`] = data[brand]?.[i]?.promo_price;
      });

      return obj;
    });
  };

  const formattedTrend = transformBrandTrendData(priceTrend);

  const lines = Object.keys(priceTrend || {}).map((brand, index) => ({
    key: `${brand}_promo`,
    color: getPricingBrandColor(brand, index),
    label: brand,
  }));

  const barData = (promotionDepth || []).map((item: any) => ({
    name: item.brand,
    value: item.avg_discount_pct,
  }));

  const availabilityData = (availability || []).map((item: any) => ({
    brand: item.brand,
    availability_pct: item.availability_pct,
  }));

  /* =========================
     HANDLERS (FIXED)
  ========================== */

  const handleChange = (key: keyof SelectedFilters, value: string) => {
    setDraftSelectedFilters((prev) => {
      const updated = {
        ...prev,
        [key]: value ? [value] : [],
      };

      // ✅ cascading reset
      if (key === "markets") {
        updated.cities = [];
        updated.retailers = [];
        updated.brands = [];
        updated.segments = [];
        updated.subTypes = [];
        updated.comp = [];
      }

      if (key === "brands") {
        updated.segments = [];
        updated.comp = [];
      }

      if (key === "segments") {
        updated.comp = [];
      }

      return updated;
    });
  };

  const resetFilters = () => {
    setDraftSelectedFilters(RESET_SELECTED_FILTERS);
  };

  const applyFilters = () => {
    setLoading(true);
    setSelectedFilters({ ...draftSelectedFilters });
  };

  const toTitleCase = (str: string) =>
    str.replace(/\w\S*/g, (w) => w.charAt(0).toUpperCase() + w.slice(1).toLowerCase());

  const buildOptions = (items: string[], label: string, titleCase = false) => [
    { label, value: "" },
    ...items.map((item) => ({
      label: titleCase ? toTitleCase(item) : item,
      value: item,
    })),
  ];

  /* =========================
     UI (UNCHANGED)
  ========================== */

  return (
    <div className="min-h-screen bg-transparent">
      <DashboardTopbar
        title="Beer & Cider Pricing Analysis"
        lastUpdated={kpis?.latest_data_point_used_date}
        lastUpdatedLoading={loading}
      />
      <div className="p-8">
        {/* FILTER PANEL */}
        <div className="pricing-compact-filters pricing-standard-filters rounded-2xl bg-[var(--card-bg)] p-4 shadow-xl border border-[var(--card-bd)] mb-8 flex items-end gap-3 flex-wrap">
          {filters && (
            <>
              <FilterSelect label="Market" value={draftSelectedFilters.markets[0] || ""} onChange={(val) => handleChange("markets", val)} options={buildOptions(filters.markets, "All Markets")} />
              <FilterSelect label="City" value={draftSelectedFilters.cities[0] || ""} onChange={(val) => handleChange("cities", val)} options={buildOptions(filters.cities ?? [], "All Cities")} />
              <FilterSelect label="Retailer" value={draftSelectedFilters.retailers[0] || ""} onChange={(val) => handleChange("retailers", val)} options={buildOptions(retailers, "All Retailers", true)} />
              <FilterMultiSelect label="Brand" values={draftSelectedFilters.brands} onChange={(values) => setDraftSelectedFilters((prev) => ({ ...prev, brands: values, segments: [], comp: [] }))} options={buildOptions(filters.brands, "All Brands")} allLabel="All Brands" />
              <FilterSelect label="Segment" value={draftSelectedFilters.segments[0] || ""} onChange={(val) => handleChange("segments", val)} options={buildOptions(filters.segments, "All Segments")} />
              <FilterSelect label="Sub Type" value={draftSelectedFilters.subTypes[0] || ""} onChange={(val) => handleChange("subTypes", val)} options={buildOptions(filters.sub_types ?? [], "All Sub Types")} />
              <FilterSelect label="Competition" value={draftSelectedFilters.comp[0] || ""} onChange={(val) => handleChange("comp", val)} options={buildOptions(filters.comp, "All Competition")} />
              <FilterSelect label="Type" value={draftSelectedFilters.types[0] || ""} onChange={(val) => handleChange("types", val)} options={buildOptions(filters.types, "All Types")} />
              <FilterSelect label="Quantity" value={draftSelectedFilters.quantity[0] || ""} onChange={(val) => handleChange("quantity", val)} options={buildOptions(filters.quantity, "All Quantities")} />
              <FilterSelect label="SKU" value={draftSelectedFilters.skus[0]?.toString() || ""} onChange={(val) => handleChange("skus", val)} options={buildOptions(filters.skus.map(String), "All SKUs")} />
              <div className="pricing-filter-row-break" aria-hidden="true" />
              <div className="pricing-filter-actions">
                <button onClick={resetFilters} className="h-[42px] px-4 text-sm rounded-xl transition" style={{ background: "var(--card-bg-2)", color: "var(--muted-tx)", border: "1px solid var(--card-bd)" }}>Reset</button>
                <button onClick={applyFilters} disabled={loading} className="h-[42px] min-w-[84px] px-5 text-sm font-semibold rounded-xl bg-blue-600 text-white border border-blue-600 hover:bg-blue-700 shadow-sm transition disabled:opacity-60 disabled:cursor-not-allowed pricing-apply-button">
                  Apply
                </button>
              </div>
            </>
          )}
        </div>

        {/* CHARTS */}
        <div className="rounded-2xl bg-[var(--card-bg-2)] border border-[var(--card-bd)] p-6 shadow-lg mt-6">
          <p className="text-lg font-semibold text-white mb-1">
            Price Trends By Brand <span className="text-xs text-[#7A7A73]">({currency})</span>
          </p>
          <div className="text-sm text-[#7A7A73] mb-4">Compares average promo prices by brand over time.</div>
          <MultiLineChartCard title="" data={formattedTrend} xKey="date" lines={lines} />
        </div>

        <div className="rounded-2xl bg-[var(--card-bg-2)] border border-[var(--card-bd)] p-6 shadow-lg mt-6">
          <p className="text-lg font-semibold text-white mb-1">
            Promotion Depth By Brand
          </p>
          <div className="text-sm text-[#7A7A73] mb-4">Compares average discount levels by brand.</div>
          <BarChartCard
            title=""
            data={barData}
            loading={loading}
            getBarColor={(brand, index) => getPricingBrandColor(brand, index)}
          />
        </div>

        <div className="rounded-2xl bg-[var(--card-bg-2)] border border-[var(--card-bd)] p-6 shadow-lg mt-6">
          <p className="text-lg font-semibold text-white mb-1">
            Availability By Brand
          </p>
          <div className="text-sm text-[#7A7A73] mb-4">Tracks in-stock rates by brand.</div>
          <AreaChartCard
            title=""
            data={availabilityData}
            xKey="brand"
            dataKey="availability_pct"
            label="Availability %"
            gradientFrom="#54aaec"
            gradientTo="#315777"
          />
        </div>

      </div>
    </div>
  );
}
