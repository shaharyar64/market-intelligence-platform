"use client";

import { useEffect, useState } from "react";
import DashboardTopbar from "@/components/layout/DashboardTopbar";
import {
  getFilters,
  getKPIs,
  getRetailers,
  getPromotionTrend,
  getDiscountTrend,
  getPromotionTrendCoreCompetition,
  getDiscountTrendCoreCompetition,
  getListVsPromoPriceGapCoreCompetition
} from "@/lib/pricingAnalysis";
import { getPricingBrandColor } from "@/lib/pricingBrandColors";
import MultiLineChartCard from "@/components/analytics/charts/MultiLineChartCard";
import AreaChartCard from "@/components/analytics/charts/AreaChartCard";
import GlassStatCard from "@/components/ui/StatCard";
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
  "all-retailers"?: string[];
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
  segments: [],
  subTypes: [],
  comp: [],
  brands: [],
  types: [],
  quantity: [],
  skus: [],
  local: false,
};

/* =========================
   CURRENCY SWITCH
========================= */

const CurrencySwitch = ({
  value,
  onChange,
}: {
  value: boolean;
  onChange: (val: boolean) => void;
}) => {
  return (
    <div
      style={{
        background: "var(--card-bg-2)",
        border: "1px solid var(--card-bd)",
        boxShadow: "0 2px 10px rgba(15, 23, 42, 0.08)",
      }}
      className="inline-flex items-center gap-0.5 rounded-full p-0.5"
    >
      <button
        type="button"
        aria-pressed={value}
        onClick={() => onChange(true)}
        style={{ color: value ? "#ffffff" : "var(--muted-tx)", background: value ? "#2563eb" : "transparent" }}
        className="h-6 rounded-full px-2.5 text-[11px] font-semibold leading-none transition-colors"
      >
        Local
      </button>
      <button
        type="button"
        aria-pressed={!value}
        onClick={() => onChange(false)}
        style={{ color: !value ? "#ffffff" : "var(--muted-tx)", background: !value ? "#2563eb" : "transparent" }}
        className="h-6 rounded-full px-2.5 text-[11px] font-semibold leading-none transition-colors"
      >
        USD
      </button>
    </div>
  );
};

const brandLine = (brand: string, fallbackIndex = 0) => ({
  key: brand,
  color: getPricingBrandColor(brand, fallbackIndex),
});

/* =========================
   PAGE
========================= */

export default function PricingAnalysisPEPage() {
  const [filters, setFilters] = useState<FiltersResponse | null>(null);
  const [retailers, setRetailers] = useState<string[]>([]);
  const [kpis, setKpis] = useState<any>(null);
  const [promotionTrend, setPromotionTrend] = useState<any[]>([]);
  const [loading, setLoading] = useState(true);
  const [discountTrend, setDiscountTrend] = useState<any[]>([]);
  const [promotionTrendCoreCompetition, setPromotionTrendCoreCompetition] = useState<any>(null);
  const [discountTrendCoreCompetition, setDiscountTrendCoreCompetition] = useState<any>(null);
  const [listPriceGapCoreCompetition, setListPriceGapCoreCompetition] = useState<any[]>([]);


  const [selectedFilters, setSelectedFilters] = useState<SelectedFilters>(DEFAULT_SELECTED_FILTERS);
  const [draftSelectedFilters, setDraftSelectedFilters] = useState<SelectedFilters>(DEFAULT_SELECTED_FILTERS);

  /* =========================
     API CALLS (FIXED)
  ========================== */

  // ✅ dynamic filters
  useEffect(() => {
    const { markets, cities, retailers, brands, subTypes } = draftSelectedFilters;
    getFilters({ markets, cities, retailers, brands, subTypes })
      .then((res) => setFilters(res.data))
      .catch(() => setFilters(null));
  }, [draftSelectedFilters]);

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
    getPromotionTrend(selectedFilters)
      .then((res) => setPromotionTrend(res.data))
      .catch(() => setPromotionTrend([]));
  }, [selectedFilters]);

  useEffect(() => {
    getDiscountTrend(selectedFilters)
      .then((res) => setDiscountTrend(res.data))
      .catch(() => setDiscountTrend([]));
  }, [selectedFilters]);

  useEffect(() => {
    getPromotionTrendCoreCompetition(selectedFilters)
      .then((res) => setPromotionTrendCoreCompetition(res.data))
      .catch(() => setPromotionTrendCoreCompetition(null));
  }, [selectedFilters]);

  useEffect(() => {
    getDiscountTrendCoreCompetition(selectedFilters)
      .then((res) => {
        const avgDiscountData = res.data?.avg_discount_pct;
        setDiscountTrendCoreCompetition(avgDiscountData);
      })
      .catch(() => setDiscountTrendCoreCompetition(null));
  }, [selectedFilters]);

  useEffect(() => {
    getListVsPromoPriceGapCoreCompetition(selectedFilters)
      .then((res) => {
        const listingData = res.data?.listing_price || [];
        const promoData = res.data?.promo_price || [];
        // Calculate gap for each brand in the merged data
        const gapData = listingData.map((item: Record<string, unknown>, idx: number) => {
          const promoItem = (promoData[idx] || {}) as Record<string, unknown>;
          const gappedItem: Record<string, unknown> = { date: item.date };
          Object.keys(item).forEach((key) => {
            if (key !== "date") {
              const listing = item[key] as number | undefined;
              const promo = promoItem[key] as number | undefined;
              gappedItem[key] = listing && promo ? Math.round((listing - promo) * 100) / 100 : null;
            }
          });
          return gappedItem;
        });
        setListPriceGapCoreCompetition(gapData);
      })
      .catch(() => {
        setListPriceGapCoreCompetition([]);
      });
  }, [selectedFilters]);


  /* =========================
     SAFE DATA
  ========================== */

  const currency = kpis?.pricing_currency || "USD";

  const formatDate = (data: any[]) => {
    const formatDateString = (dateStr: string) => {
      const d = new Date(dateStr);
      const day = String(d.getUTCDate()).padStart(2, "0");
      const months = ["Jan", "Feb", "Mar", "Apr", "May", "Jun", "Jul", "Aug", "Sep", "Oct", "Nov", "Dec"];
      const month = months[d.getUTCMonth()];
      return `${day} ${month}`;
    };
    return Array.isArray(data)
      ? data.map((item) => ({
          ...item,
          date: formatDateString(item.date),
        }))
      : [];
  };

  const transformBrandData = (data: unknown) => {
    const formatDateString = (dateStr: string) => {
      const d = new Date(dateStr);
      const day = String(d.getUTCDate()).padStart(2, "0");
      const months = ["Jan", "Feb", "Mar", "Apr", "May", "Jun", "Jul", "Aug", "Sep", "Oct", "Nov", "Dec"];
      const month = months[d.getUTCMonth()];
      return `${day} ${month}`;
    };

    if (!data || typeof data !== "object") return [];

    // Check if data is an array (flat structure)
    if (Array.isArray(data)) {
      return (data as Array<{ date: string; [key: string]: unknown }>).map((item) => ({
        ...item,
        date: formatDateString(item.date as string),
      }));
    }

    // Handle object-keyed data (brand-indexed)
    const brands = Object.keys(data as Record<string, unknown>);
    if (!brands.length) return [];

    const dataObj = data as Record<string, unknown>;
    const firstBrandData = dataObj[brands[0]];

    // Check if first brand data is an array
    if (!Array.isArray(firstBrandData)) return [];

    const dates = firstBrandData.map((item: unknown) => (item as { date: string }).date) || [];
    return dates.map((date: string, i: number) => {
      const obj: Record<string, unknown> = {
        date: formatDateString(date),
      };
      brands.forEach((brand) => {
        const brandArray = dataObj[brand] as Array<{ avg_discount_pct?: number }>;
        obj[brand] = brandArray?.[i]?.avg_discount_pct ?? null;
      });
      return obj;
    });
  };

  const formattedTrend = formatDate(promotionTrend);
  const formattedDiscountTrend = formatDate(discountTrend);
  const formattedPromotionTrendCoreCompetition = transformBrandData(promotionTrendCoreCompetition);
  const formattedDiscountTrendCoreCompetition = transformBrandData(discountTrendCoreCompetition);

  const formattedListPriceGapCoreCompetition = transformBrandData(listPriceGapCoreCompetition);

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
        updated.subTypes = [];
        updated.comp = [];
      }

      if (key === "brands") {
        updated.comp = [];
      }

      return updated;
    });
  };

  const handleCurrencyChange = (value: boolean) => {
    setDraftSelectedFilters((prev) => ({
      ...prev,
      local: value,
    }));
  };

  const applyFilters = () => {
    setLoading(true);
    setSelectedFilters({ ...draftSelectedFilters });
  };

  const resetFilters = () => {
    setDraftSelectedFilters(DEFAULT_SELECTED_FILTERS);
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
        accessory={
          <CurrencySwitch
            value={draftSelectedFilters.local}
            onChange={handleCurrencyChange}
          />
        }
      />
      <div className="p-8">
        {/* FILTER PANEL */}
        <div className="pricing-compact-filters pricing-standard-filters rounded-2xl bg-[var(--card-bg)] p-4 shadow-xl border border-[var(--card-bd)] mb-8 flex items-end gap-3 flex-wrap">
          {filters && (
            <>
              <FilterSelect label="Market" value={draftSelectedFilters.markets[0] || ""} onChange={(val) => handleChange("markets", val)} options={buildOptions(filters.markets, "All Markets")} />
              <FilterSelect label="City" value={draftSelectedFilters.cities[0] || ""} onChange={(val) => handleChange("cities", val)} options={buildOptions(filters.cities ?? [], "All Cities")} />
              <FilterSelect label="Retailer" value={draftSelectedFilters.retailers[0] || ""} onChange={(val) => handleChange("retailers", val)} options={buildOptions((filters?.["all-retailers"] && filters["all-retailers"].length > 0) ? filters["all-retailers"] : retailers, "All Retailers", true)} />
              <FilterMultiSelect label="Brand" values={draftSelectedFilters.brands} onChange={(values) => setDraftSelectedFilters((prev) => ({ ...prev, brands: values, comp: [] }))} options={buildOptions(filters.brands, "All Brands")} allLabel="All Brands" />
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

        {/* KPI CARDS */}
        <div className="rounded-2xl bg-[var(--card-bg-2)] border border-[var(--card-bd)] p-6 shadow-lg">
          <div className="mb-4">
            <p style={{ color: "var(--title-tx)" }} className="text-lg font-semibold">KPI Overview</p>
            <p style={{ color: "var(--muted-tx)" }} className="text-xs">
              Current Week: {kpis?.latest_data_point_used_date ? new Date(kpis.latest_data_point_used_date).toLocaleDateString("en-GB", { day: "2-digit", month: "short", year: "numeric" }) : "Loading..."}
            </p>
          </div>
          <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-3 gap-6">
            <GlassStatCard title="Listing %Age On Promotion" value={`${typeof kpis?.skus_on_promotion_percentage === "number" ? kpis.skus_on_promotion_percentage.toFixed(1) : kpis?.skus_on_promotion_percentage ?? "-"} %`} loading={loading} icon={<Tag size={18} />} gradient="from-emerald-500 to-teal-500" />
            <GlassStatCard title="% Promo" value={`${typeof kpis?.avg_discount_pct === "number" ? kpis.avg_discount_pct.toFixed(1) : kpis?.avg_discount_pct ?? "-"} %`} loading={loading} icon={<PercentCircle size={18} />} gradient="from-amber-500 to-orange-500" />
            <GlassStatCard title="Listing vs. Promo Gap" value={`${kpis?.list_vs_promo_gap ?? "-"} ${currency}`} loading={loading} icon={<TrendingUpDown size={18} />} gradient="from-indigo-500 to-purple-500" />
          </div>
        </div>

        {/* CHARTS */}
        <div className="mt-6 grid grid-cols-1 gap-6 xl:grid-cols-2">
          <div className="rounded-2xl bg-[var(--card-bg-2)] border border-[var(--card-bd)] p-6 shadow-lg">
            <p className="text-lg font-semibold text-white mb-1">Listing %Age On Promotion <span className="text-xs text-[#7A7A73]">(Trending)</span></p>
            <div className="text-sm text-[#7A7A73] mb-4">Percentage of SKUs currently on promotion.</div>
            <AreaChartCard title="" data={formattedTrend} xKey="date" dataKey="promo_sku_percentage" label="Listing %Age On Promotion" gradientFrom="#54aaec" gradientTo="#315777" decimals={1} />
          </div>

          <div className="rounded-2xl bg-[var(--card-bg-2)] border border-[var(--card-bd)] p-6 shadow-lg">
            <p className="text-lg font-semibold text-white mb-1">% Promo <span className="text-xs text-[#7A7A73]">(Trending)</span></p>
            <div className="text-sm text-[#7A7A73] mb-4">Average percentage reduction from list price.</div>
            <MultiLineChartCard title="" data={formattedDiscountTrend} xKey="date" lines={[{ key: "max_discount_pct", color: "#10b981" }, { key: "avg_discount_pct", color: "#f59e0b" }]} decimals={1} />
          </div>
        </div>

        {/* CORE COMPETITION SKUS ON PROMOTION */}
        <div className="rounded-2xl bg-[var(--card-bg-2)] border border-[var(--card-bd)] p-6 shadow-lg mt-6">
          <p className="text-lg font-semibold text-white mb-6 text-center">Core Competition of Listing %Age On Promotion <span className="text-xs text-[#7A7A73]"> (%)</span></p>
          <div className="grid grid-cols-1 lg:grid-cols-2 gap-6">
            {/* Top 10 */}
            <div>
            <p className="text-lg font-semibold text-white mb-2">
                Heineken vs Corona, Stella
                <span className="text-xs text-[#7A7A73]"> (Trending)</span>
            </p>
              <MultiLineChartCard title="" data={formattedPromotionTrendCoreCompetition} xKey="date" lines={[brandLine("Heineken", 0), brandLine("Corona", 1), brandLine("Stella", 2)]} decimals={1} />
            </div>

            {/* First Page */}
            <div>
            <p className="text-lg font-semibold text-white mb-2">
                Kingfisher vs Red Horse, Tuborg, Haywards
                <span className="text-xs text-[#7A7A73]"> (Trending)</span>
            </p>
              <MultiLineChartCard title="" data={formattedPromotionTrendCoreCompetition} xKey="date" lines={[brandLine("Kingfisher", 0), brandLine("Red Horse", 1), brandLine("Tuborg", 2), brandLine("Haywards", 3)]} decimals={1} />
            </div>
          </div>

          <div className="grid grid-cols-1 lg:grid-cols-2 gap-6 mt-6">
            {/* Top 10 */}
            <div>
            <p className="text-lg font-semibold text-white mb-2">
                Birra Moretti vs Peroni, Guinness
                <span className="text-xs text-[#7A7A73]"> (Trending)</span>
            </p>
              <MultiLineChartCard title="" data={formattedPromotionTrendCoreCompetition} xKey="date" lines={[brandLine("Birra Moretti", 0), brandLine("Guinness", 1), brandLine("Peroni", 2)]} decimals={1} />
            </div>

            {/* First Page */}
            <div>
            <p className="text-lg font-semibold text-white mb-2">
                Amstel, Tiger vs Budweiser, Carlsberg 
                <span className="text-xs text-[#7A7A73]"> (Trending)</span>
            </p>
              <MultiLineChartCard title="" data={formattedPromotionTrendCoreCompetition} xKey="date" lines={[brandLine("Amstel", 0), brandLine("Tiger", 1), brandLine("Budweiser", 2), brandLine("Carlsberg", 3)]} decimals={1} />
            </div>
          </div>
        </div>

        {/* CORE COMPETITION SKUS ON % PROMO */}
        <div className="rounded-2xl bg-[var(--card-bg-2)] border border-[var(--card-bd)] p-6 shadow-lg mt-6">
          <p className="text-lg font-semibold text-white mb-6 text-center">Core Competition of % Promo <span className="text-xs text-[#7A7A73]"> (%)</span></p>
          <div className="grid grid-cols-1 lg:grid-cols-2 gap-6">
            {/* Top 10 */}
            <div>
            <p className="text-lg font-semibold text-white mb-2">
                Heineken vs Corona, Stella
                <span className="text-xs text-[#7A7A73]"> (Trending)</span>
            </p>
              <MultiLineChartCard title="" data={formattedDiscountTrendCoreCompetition} xKey="date" lines={[brandLine("Heineken", 0), brandLine("Corona", 1), brandLine("Stella", 2)]} decimals={1} />
            </div>

            {/* First Page */}
            <div>
            <p className="text-lg font-semibold text-white mb-2">
                Kingfisher vs Red Horse, Tuborg, Haywards
                <span className="text-xs text-[#7A7A73]"> (Trending)</span>
            </p>
              <MultiLineChartCard title="" data={formattedDiscountTrendCoreCompetition} xKey="date" lines={[brandLine("Kingfisher", 0), brandLine("Red Horse", 1), brandLine("Tuborg", 2), brandLine("Haywards", 3)]} decimals={1} />
            </div>
          </div>

          <div className="grid grid-cols-1 lg:grid-cols-2 gap-6 mt-6">
            {/* Top 10 */}
            <div>
            <p className="text-lg font-semibold text-white mb-2">
                Birra Moretti vs Peroni, Guinness
                <span className="text-xs text-[#7A7A73]"> (Trending)</span>
            </p>
              <MultiLineChartCard title="" data={formattedDiscountTrendCoreCompetition} xKey="date" lines={[brandLine("Birra Moretti", 0), brandLine("Guinness", 1), brandLine("Peroni", 2)]} decimals={1} />
            </div>

            {/* First Page */}
            <div>
            <p className="text-lg font-semibold text-white mb-2">
                Amstel, Tiger vs Budweiser, Carlsberg
                <span className="text-xs text-[#7A7A73]"> (Trending)</span>
            </p>
              <MultiLineChartCard title="" data={formattedDiscountTrendCoreCompetition} xKey="date" lines={[brandLine("Amstel", 0), brandLine("Tiger", 1), brandLine("Budweiser", 2), brandLine("Carlsberg", 3)]} decimals={1} />
            </div>
          </div>
        </div>

        {/* CORE COMPETITION LISTING VS. PROMO GAP */}
        <div className="rounded-2xl bg-[var(--card-bg-2)] border border-[var(--card-bd)] p-6 shadow-lg mt-6">
          <p className="text-lg font-semibold text-white mb-6 text-center">Core Competition of Listing vs. Promo Gap <span className="text-xs text-[#7A7A73]"> (${currency})</span></p>
          <p className="text-sm text-[#7A7A73] mb-4 text-center">Price difference between listing and promotional prices for core competition brands.</p>
          <div className="grid grid-cols-1 lg:grid-cols-2 gap-6">
            {/* Top 10 */}
            <div>
            <p className="text-lg font-semibold text-white mb-2">
                Heineken vs Corona, Stella
                <span className="text-xs text-[#7A7A73]"> (Trending)</span>
            </p>
              <MultiLineChartCard title="" data={formattedListPriceGapCoreCompetition} xKey="date" lines={[brandLine("Heineken", 0), brandLine("Corona", 1), brandLine("Stella", 2)]} />
            </div>

            {/* First Page */}
            <div>
            <p className="text-lg font-semibold text-white mb-2">
                Kingfisher vs Red Horse, Tuborg, Haywards
                <span className="text-xs text-[#7A7A73]"> (Trending)</span>
            </p>
              <MultiLineChartCard title="" data={formattedListPriceGapCoreCompetition} xKey="date" lines={[brandLine("Kingfisher", 0), brandLine("Red Horse", 1), brandLine("Tuborg", 2), brandLine("Haywards", 3)]} />
            </div>
          </div>

          <div className="grid grid-cols-1 lg:grid-cols-2 gap-6 mt-6">
            {/* Top 10 */}
            <div>
            <p className="text-lg font-semibold text-white mb-2">
                Birra Moretti vs Peroni, Guinness
                <span className="text-xs text-[#7A7A73]"> (Trending)</span>
            </p>
              <MultiLineChartCard title="" data={formattedListPriceGapCoreCompetition} xKey="date" lines={[brandLine("Birra Moretti", 0), brandLine("Guinness", 1), brandLine("Peroni", 2)]} />
            </div>

            {/* First Page */}
            <div>
            <p className="text-lg font-semibold text-white mb-2">
                Amstel, Tiger vs Budweiser, Carlsberg
                <span className="text-xs text-[#7A7A73]"> (Trending)</span>
            </p>
              <MultiLineChartCard title="" data={formattedListPriceGapCoreCompetition} xKey="date" lines={[brandLine("Amstel", 0), brandLine("Tiger", 1), brandLine("Budweiser", 2), brandLine("Carlsberg", 3)]} />
            </div>
          </div>
        </div>

      </div>
    </div>
  );
}
