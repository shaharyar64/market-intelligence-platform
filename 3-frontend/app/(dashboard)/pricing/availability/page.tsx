"use client";

import { useEffect, useState } from "react";
import DashboardTopbar from "@/components/layout/DashboardTopbar";
import {
  getFilters,
  getKPIs,
  getRetailers,
  getPriceTrend,
  getAvailabilityTrend,
  getOutOfStockSkusTrend,
  getShareOfVisibilityHeinekenPortfolio
} from "@/lib/pricingAnalysis";
import { getPricingBrandColor } from "@/lib/pricingBrandColors";
import MultiLineChartCard from "@/components/analytics/charts/MultiLineChartCard";
import FilterSelect from "@/components/filters/FilterSelect";
import FilterMultiSelect from "@/components/filters/FilterMultiSelect";

/* =========================
   TYPES
========================= */

interface FiltersResponse {
  markets: string[];
  cities: string[];
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
  subTypes: string[];
  comp: string[];
  brands: string[];
  types: string[];
  quantity: string[];
  skus: number[];
  local: boolean;
}

type KpiSummary = {
  latest_data_point_used_date?: string;
};

type TrendRow = {
  date: string;
  [key: string]: string | number | null;
};

type VisibilityPoint = {
  date: string;
  visibility_pct?: number | null;
};

type VisibilitySeries = Record<string, VisibilityPoint[]>;

const DEFAULT_SELECTED_FILTERS: SelectedFilters = {
  markets: [],
  cities: [],
  retailers: [],
  subTypes: [],
  comp: [],
  brands: ["heineken"],
  types: [],
  quantity: [],
  skus: [],
  local: false,
};

/* =========================
   CURRENCY SWITCH
========================= */

const CurrencySwitch = ({ value, onChange }: { value: boolean; onChange: (v: boolean) => void }) => (
  <div style={{ background: "var(--card-bg-2)", border: "1px solid var(--card-bd)", width: "fit-content" }} className="inline-flex items-center gap-0.5 rounded-full p-0.5">
    <button type="button" onClick={() => onChange(true)}  style={{ color: value  ? "#ffffff" : "var(--muted-tx)", background: value  ? "#2563eb" : "transparent" }} className="h-6 rounded-full px-2.5 text-[11px] font-semibold leading-none transition-colors">Local</button>
    <button type="button" onClick={() => onChange(false)} style={{ color: !value ? "#ffffff" : "var(--muted-tx)", background: !value ? "#2563eb" : "transparent" }} className="h-6 rounded-full px-2.5 text-[11px] font-semibold leading-none transition-colors">USD</button>
  </div>
);

/* =========================
   PAGE
========================= */

export default function PricingAnalysisAvailabilityPage() {
  const [filters, setFilters] = useState<FiltersResponse | null>(null);
  const [retailers, setRetailers] = useState<string[]>([]);
  const [kpis, setKpis] = useState<KpiSummary | null>(null);
  const [loading, setLoading] = useState(true);

  const [availabilityTrend, setAvailabilityTrend] = useState<TrendRow[]>([]);
  const [activeSkusTrend, setActiveSkusTrend] = useState<TrendRow[]>([]);
  const [outOfStockSkusTrend, setOutOfStockSkusTrend] = useState<TrendRow[]>([]);
  const [shareOfVisibilityTop10, setShareOfVisibilityTop10] = useState<VisibilitySeries>({});
  const [shareOfVisibilityFirstPage, setShareOfVisibilityFirstPage] = useState<VisibilitySeries>({});
  const [brandTrendData, setBrandTrendData] = useState<Record<string, any[]>>({});
  const [brandTrendLoading, setBrandTrendLoading] = useState(false);
  const [brandTrendCurrency, setBrandTrendCurrency] = useState<string>("USD");

  const [selectedFilters, setSelectedFilters] = useState<SelectedFilters>(DEFAULT_SELECTED_FILTERS);
  const [draftSelectedFilters, setDraftSelectedFilters] = useState<SelectedFilters>(DEFAULT_SELECTED_FILTERS);

  /* =========================
     API CALLS (FIXED)
  ========================== */

  useEffect(() => {
    const { markets, cities, retailers, brands, subTypes } = draftSelectedFilters;
    getFilters({ markets, cities, retailers, brands, subTypes })
      .then((res) => setFilters(res.data))
      .catch(() => setFilters(null));
  }, [draftSelectedFilters]);

  useEffect(() => {
    getRetailers()
      .then((res) => setRetailers(res.data))
      .catch(() => setRetailers([]));
  }, []);

  useEffect(() => {
    getKPIs(selectedFilters)
      .then((res) => setKpis(res.data))
      .finally(() => setLoading(false));
  }, [selectedFilters]);

  useEffect(() => {
    getAvailabilityTrend(selectedFilters)
      .then((res) => setAvailabilityTrend(Array.isArray(res.data ?? res) ? (res.data ?? res) : []))
      .catch(() => setAvailabilityTrend([]));
  }, [selectedFilters]);

  // /out-of-stock-skus-trending now returns { active_skus: [...], out_of_stock_skus: [...] }
  useEffect(() => {
    getOutOfStockSkusTrend(selectedFilters)
      .then((res) => {
        const d = res.data ?? res;
        setActiveSkusTrend(Array.isArray(d.active_skus) ? d.active_skus : []);
        setOutOfStockSkusTrend(Array.isArray(d.out_of_stock_skus) ? d.out_of_stock_skus : []);
      })
      .catch(() => { setActiveSkusTrend([]); setOutOfStockSkusTrend([]); });
  }, [selectedFilters]);

  useEffect(() => {
    getShareOfVisibilityHeinekenPortfolio(selectedFilters)
      .then((res) => {
        setShareOfVisibilityTop10(res.data.features_in_top10);
        setShareOfVisibilityFirstPage(res.data.features_on_first_page);
      })
      .catch(() => {
        setShareOfVisibilityTop10({});
        setShareOfVisibilityFirstPage({});
      });
  }, [selectedFilters]);

  useEffect(() => {
    const brandsToFetch = (selectedFilters.brands ?? []).slice(0, 3);
    Promise.resolve()
      .then(() => {
        setBrandTrendLoading(true);
        return Promise.all(
          brandsToFetch.map((brand) =>
            getPriceTrend({ ...selectedFilters, brands: [brand] })
              .then((res: { data?: { data?: TrendRow[]; pricing_currency?: string } }) => ({
                brand,
                data: res.data?.data ?? [],
                currency: res.data?.pricing_currency ?? null,
              }))
              .catch(() => ({ brand, data: [] as TrendRow[], currency: null as string | null }))
          )
        );
      })
      .then((results) => {
        const map: Record<string, TrendRow[]> = {};
        let detectedCurrency: string | null = null;
        results.forEach(({ brand, data, currency }) => {
          map[brand] = data;
          if (!detectedCurrency && currency) detectedCurrency = currency;
        });
        setBrandTrendCurrency(detectedCurrency ?? "USD");
        setBrandTrendData(map);
      })
      .finally(() => setBrandTrendLoading(false));
  }, [selectedFilters]);

  /* =========================
     SAFE DATA
  ========================== */

  const formatDateString = (dateStr: string) => {
    const d = new Date(dateStr);
    const day = String(d.getUTCDate()).padStart(2, "0");
    const months = ["Jan", "Feb", "Mar", "Apr", "May", "Jun", "Jul", "Aug", "Sep", "Oct", "Nov", "Dec"];
    const month = months[d.getUTCMonth()];
    return `${day} ${month}`;
  };

  const formatted = (data: TrendRow[]): TrendRow[] =>
    Array.isArray(data)
      ? data.map((item) => ({
          ...item,
          date: formatDateString(item.date),
        }))
      : [];

  const formattedAvailabilityTrend = formatted(availabilityTrend);
  const formattedActiveSkusTrend = formatted(activeSkusTrend);
  const formattedOutOfStockSkusTrend = formatted(outOfStockSkusTrend);

  const brandKeysFrom = (rows: TrendRow[]) => Object.keys(rows[0] ?? {}).filter((k) => k !== "date");

  const availabilityBrands = brandKeysFrom(formattedAvailabilityTrend);
  const availabilityLines = availabilityBrands.map((b, i) => ({ key: b, color: getPricingBrandColor(b, i), label: b }));

  // Merge active + OOS into one dataset with prefixed keys
  const skuBrands = brandKeysFrom(formattedActiveSkusTrend.length ? formattedActiveSkusTrend : formattedOutOfStockSkusTrend);
  const mergedSkusData = formattedActiveSkusTrend.map((row, idx) => {
    const obj: TrendRow = { date: row.date };
    skuBrands.forEach((b) => {
      obj[`${b}__active`] = (formattedActiveSkusTrend[idx]?.[b] ?? null) as number | null;
      obj[`${b}__oos`] = (formattedOutOfStockSkusTrend[idx]?.[b] ?? null) as number | null;
    });
    return obj;
  });
  const transformVisibilityData = (data: VisibilitySeries) => {
    if (!data || typeof data !== "object") return [];

    const brands = Object.keys(data);
    if (!brands.length) return [];

    const dates = data[brands[0]]?.map((item) => item.date) || [];

    return dates.map((date: string, i: number) => {
      const obj: TrendRow = {
        date: formatDateString(date),
      };

      brands.forEach((brand) => {
        obj[brand] = data[brand]?.[i]?.visibility_pct ?? null;
      });

      return obj;
    });
  };

  const shareOfVisibilityTop10Data = transformVisibilityData(shareOfVisibilityTop10);
  const shareOfVisibilityFirstPageData = transformVisibilityData(shareOfVisibilityFirstPage);

  const brandTrendBrands = Object.keys(brandTrendData);
  const mergedBrandTrend = (() => {
    const firstBrand = brandTrendBrands.find((b) => brandTrendData[b]?.length > 0);
    if (!firstBrand) return [];
    return brandTrendData[firstBrand].map((item: any, i: number) => {
      const obj: any = {
        date: new Date(item.date).toLocaleDateString("en-GB", { day: "2-digit", month: "short" }),
      };
      brandTrendBrands.forEach((brand) => {
        const listing = brandTrendData[brand]?.[i]?.listing_price ?? null;
        const promo   = brandTrendData[brand]?.[i]?.promo_price   ?? null;
        obj[`${brand}__listing`] = listing;
        obj[`${brand}__promo`]   = promo;
        obj[`${brand}__gap`]     = listing != null && promo != null ? Math.round((listing - promo) * 100) / 100 : null;
      });
      return obj;
    });
  })();
  const brandTrendLines = brandTrendBrands.flatMap((brand, idx) => {
    const color = getPricingBrandColor(brand, idx);
    return [
      { key: `${brand}__listing`, color, label: `${brand} (Regular)` },
      { key: `${brand}__promo`,   color, label: `${brand} (Promo)`,   strokeDasharray: "5 3" },
      { key: `${brand}__gap`,     color: "transparent", label: `${brand} (Gap)`, hideInLegend: true },
    ];
  });

  /* =========================
     HANDLERS (FIXED)
  ========================== */

  const handleChange = (key: keyof SelectedFilters, value: string) => {
    setDraftSelectedFilters((prev) => {
      const updated = {
        ...prev,
        [key]: value ? [value] : [],
      };

      if (key === "markets") {
        updated.cities = [];
        updated.retailers = [];
        updated.brands = DEFAULT_SELECTED_FILTERS.brands;
        updated.subTypes = [];
        updated.comp = [];
      }

      if (key === "brands") {
        updated.comp = [];
      }

      return updated;
    });
  };

  const resetFilters = () => {
    setDraftSelectedFilters(DEFAULT_SELECTED_FILTERS);
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
      <style>{`
        @keyframes avail-shimmer { 0%{background-position:200% 0} 100%{background-position:-200% 0} }
        .avail-shimmer { background: linear-gradient(90deg,#2a3142 25%,#323a50 50%,#2a3142 75%); background-size:200% 100%; animation: avail-shimmer 1.4s infinite; border-radius: 6px; }
      `}</style>
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
              <FilterSelect label="Retailer" value={draftSelectedFilters.retailers[0] || ""} onChange={(val) => handleChange("retailers", val)} options={buildOptions((filters?.["all-retailers"] && filters["all-retailers"].length > 0) ? filters["all-retailers"] : retailers, "All Retailers", true)} />
              <FilterMultiSelect label="Brand" values={draftSelectedFilters.brands} onChange={(values) => setDraftSelectedFilters((prev) => ({ ...prev, brands: values, comp: [] }))} options={buildOptions(filters.brands, "All Brands")} allLabel="All Brands" maxValues={3} />
              <FilterSelect label="Sub Type" value={draftSelectedFilters.subTypes[0] || ""} onChange={(val) => handleChange("subTypes", val)} options={buildOptions(filters.sub_types ?? [], "All Sub Types")} />
              <FilterSelect label="Competition" value={draftSelectedFilters.comp[0] || ""} onChange={(val) => handleChange("comp", val)} options={buildOptions(filters.comp, "All Competition")} />
              <FilterSelect label="Type" value={draftSelectedFilters.types[0] || ""} onChange={(val) => handleChange("types", val)} options={buildOptions(filters.types, "All Types")} />
              <FilterSelect label="Quantity" value={draftSelectedFilters.quantity[0] || ""} onChange={(val) => handleChange("quantity", val)} options={buildOptions(filters.quantity, "All Quantities")} />
              <FilterSelect label="Product Listing" value={draftSelectedFilters.skus[0]?.toString() || ""} onChange={(val) => handleChange("skus", val)} options={buildOptions(filters.skus.map(String), "All Product Listings")} />
              <div style={{ display: "flex", flexDirection: "column", gap: 4 }}>
                <span style={{ fontSize: 11, fontWeight: 600, color: "var(--muted-tx)", letterSpacing: "0.05em", textTransform: "uppercase" }}>Currency</span>
                <CurrencySwitch value={draftSelectedFilters.local} onChange={(v) => setDraftSelectedFilters((prev) => ({ ...prev, local: v }))} />
              </div>
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

        {/* BRAND PRICE TREND */}
        <div className="rounded-2xl bg-[var(--card-bg-2)] border border-[var(--card-bd)] p-6 shadow-lg mt-6">
          <div className="text-lg font-semibold text-white mb-1">
            Price Trend Over Time <span className="text-xs text-[#7A7A73]">(Brands)</span>
          </div>
          <div className="text-sm text-[#7A7A73] mb-4">
            Regular price trend per brand. Select up to 3 brands in the Brand filter to compare.
          </div>
          {brandTrendLoading ? (
            <div className="avail-shimmer" style={{ height: 350, width: "100%" }} />
          ) : brandTrendBrands.length === 0 ? (
            <div className="flex items-center justify-center h-[350px]" style={{ color: "var(--muted-tx)", fontSize: 13 }}>Select up to 3 brands in the Brand filter and click Apply.</div>
          ) : (
            <MultiLineChartCard
              title=""
              data={mergedBrandTrend}
              xKey="date"
              lines={brandTrendLines}
              yAxisLabel={brandTrendCurrency}
            />
          )}
        </div>

        {/* VISIBILITY CHARTS */}
        <div className="rounded-2xl bg-[var(--card-bg-2)] border border-[var(--card-bd)] p-6 shadow-lg mt-6">
          <div className="grid grid-cols-1 lg:grid-cols-2 gap-6">

            <div>
              <p className="text-lg font-semibold text-white mb-1">
                Share of Visibility <span className="text-xs text-[#7A7A73]">(Top 10)</span>
              </p>
              <div className="text-sm text-[#7A7A73] mb-4">Share of Sirocco Product Listings visible in top 10.</div>
              {loading ? <div className="avail-shimmer" style={{ height: 350 }} /> : <MultiLineChartCard
                title=""
                data={shareOfVisibilityTop10Data}
                xKey="date"
                lines={Object.keys(shareOfVisibilityTop10).map((brand, idx) => ({
                  key: brand,
                  color: getPricingBrandColor(brand, idx),
                  label: brand,
                }))}
                decimals={1}
                unit="%"
              />}
            </div>

            <div>
              <p className="text-lg font-semibold text-white mb-1">
                Share of Visibility <span className="text-xs text-[#7A7A73]">(First Page)</span>
              </p>
              <div className="text-sm text-[#7A7A73] mb-4">Share of Sirocco Product Listings visible on the first page.</div>
              {loading ? <div className="avail-shimmer" style={{ height: 350 }} /> : <MultiLineChartCard
                title=""
                data={shareOfVisibilityFirstPageData}
                xKey="date"
                lines={Object.keys(shareOfVisibilityFirstPage).map((brand, idx) => ({
                  key: brand,
                  color: getPricingBrandColor(brand, idx),
                  label: brand,
                }))}
                decimals={1}
                unit="%"
              />}
            </div>

          </div>
        </div>

        {/* CHARTS */}
        <div className="mt-6 grid grid-cols-1 gap-6 xl:grid-cols-2">
          <div className="rounded-2xl bg-[var(--card-bg-2)] border border-[var(--card-bd)] p-6 shadow-lg">
            <p className="text-lg font-semibold text-white mb-1">Availability % <span className="text-xs text-[#7A7A73]">(by Brand)</span></p>
            <div className="text-sm text-[#7A7A73] mb-4">Percentage of Product Listings currently in stock, per brand.</div>
            {loading ? <div className="avail-shimmer" style={{ height: 350 }} /> : <MultiLineChartCard title="" data={formattedAvailabilityTrend} xKey="date" lines={availabilityLines} decimals={1} unit="%" />}
          </div>

          <div className="rounded-2xl bg-[var(--card-bg-2)] border border-[var(--card-bd)] p-6 shadow-lg">
            <p className="text-lg font-semibold text-white mb-1">Out of Stock SKUs <span className="text-xs text-[#7A7A73]">(by Brand)</span></p>
            <div className="text-sm text-[#7A7A73] mb-4">Out-of-stock count per brand. Hover to see active SKUs.</div>
            {loading ? <div className="avail-shimmer" style={{ height: 350 }} /> : <MultiLineChartCard
              title=""
              data={mergedSkusData}
              xKey="date"
              lines={skuBrands.flatMap((b, i) => {
                const color = getPricingBrandColor(b, i);
                return [
                  { key: `${b}__oos`, color, label: b },
                  { key: `${b}__active`, color, label: `${b} active`, strokeOpacity: 0, hideInLegend: true, hideInTooltip: true },
                ];
              })}
              customTooltipContent={(payload) => {
                type Entry = { dataKey: string; value: number | null; color: string };
                const entries = payload as Entry[];
                const oosEntries = entries.filter((p) => p.dataKey?.endsWith("__oos"));
                return (
                  <div>
                    {oosEntries.map((p) => {
                      const brand = p.dataKey.replace("__oos", "");
                      const activeEntry = entries.find((x) => x.dataKey === `${brand}__active`);
                      const oos = p.value ?? "-";
                      const active = activeEntry?.value ?? "-";
                      return (
                        <div key={brand} style={{ display: "flex", alignItems: "center", gap: 8, marginBottom: 3 }}>
                          <span style={{ display: "inline-block", width: 8, height: 8, borderRadius: "50%", backgroundColor: p.color }} />
                          <span>{brand}: <strong>{oos} OOS</strong> ({active} Active)</span>
                        </div>
                      );
                    })}
                  </div>
                );
              }}
            />}
          </div>
        </div>

      </div>
    </div>
  );
}
