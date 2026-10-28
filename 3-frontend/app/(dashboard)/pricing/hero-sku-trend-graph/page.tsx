"use client";

import { useEffect, useState } from "react";
import DashboardTopbar from "@/components/layout/DashboardTopbar";
import { getFilters, getHeroSkuPriceTrend, Filters } from "@/lib/pricingAnalysis";
import { getPricingBrandColor, getPricingBrandLabel } from "@/lib/pricingBrandColors";
import MultiLineChartCard from "@/components/analytics/charts/MultiLineChartCard";
import FilterSelect from "@/components/filters/FilterSelect";
import FilterDateRange from "@/components/filters/FilterDateRange";

/* =========================
   TYPES
========================= */

interface SkuPriceTrend {
  sku_label: string;
  pack_type: string;
  pack_size: string;
  pack: number;
  sub_type: string;
  eff_price: (number | null)[];
  eff_price_deltas: (number | null)[];
}
interface HeroSkuPriceTrendData {
  weeks: string[];
  pricing_currency: string;
  skus: SkuPriceTrend[];
}
interface FiltersResponse {
  markets: string[];
  cities: string[];
  "all-retailers"?: string[];
  date_range?: { min: string | null; max: string | null };
}

/* =========================
   FILTER PERSISTENCE
========================= */

const DEFAULT_FILTERS: Filters = { markets: [], cities: [], retailers: [], local: false };
const MIN_SELECTABLE_DATE = "2026-05-12";
const STORAGE_KEY = "pricing_price_trend_filters";
const loadStoredFilters = (): Filters => {
  if (typeof window === "undefined") return DEFAULT_FILTERS;
  try { const s = localStorage.getItem(STORAGE_KEY); return s ? { ...DEFAULT_FILTERS, ...JSON.parse(s) } : DEFAULT_FILTERS; }
  catch { return DEFAULT_FILTERS; }
};

/* =========================
   CURRENCY SWITCH
========================= */

const CurrencySwitch = ({ value, onChange }: { value: boolean; onChange: (v: boolean) => void }) => (
  <div style={{ background: "var(--card-bg-2)", border: "1px solid var(--card-bd)", boxShadow: "0 2px 10px rgba(15,23,42,0.08)", width: "fit-content" }} className="inline-flex items-center gap-0.5 rounded-full p-0.5">
    <button type="button" onClick={() => onChange(true)}  style={{ color: value  ? "#ffffff" : "var(--muted-tx)", background: value  ? "#2563eb" : "transparent" }} className="h-5 rounded-full px-2 text-[10px] font-semibold leading-none transition-colors">Local</button>
    <button type="button" onClick={() => onChange(false)} style={{ color: !value ? "#ffffff" : "var(--muted-tx)", background: !value ? "#2563eb" : "transparent" }} className="h-5 rounded-full px-2 text-[10px] font-semibold leading-none transition-colors">USD</button>
  </div>
);

/* =========================
   PAGE
========================= */

export default function PriceTrendPage() {
  const [apiFilters, setApiFilters] = useState<FiltersResponse | null>(null);
  const [heroSkuPriceTrend, setHeroSkuPriceTrend] = useState<HeroSkuPriceTrendData | null>(null);
  const [loading, setLoading] = useState(true);
  const [selectedFilters, setSelectedFilters] = useState<Filters>(loadStoredFilters);
  const [draftFilters, setDraftFilters] = useState<Filters>(loadStoredFilters);
  const [dateBounds, setDateBounds] = useState<{ min: string; max: string } | null>(null);

  // Cascading filter options
  useEffect(() => {
    const { markets, cities, retailers } = draftFilters;
    getFilters({ markets, cities, retailers })
      .then((res) => {
        const data: FiltersResponse = res.data ?? res;
        setApiFilters(data);
        const range = data.date_range;
        if (range?.min && range?.max) {
          const min = range.min > MIN_SELECTABLE_DATE ? range.min : MIN_SELECTABLE_DATE;
          setDateBounds(min <= range.max ? { min, max: range.max } : null);
        } else {
          setDateBounds(null);
        }
      })
      .catch(() => setApiFilters(null));
  }, [draftFilters]);

  // Re-clamp any already-picked date range if bounds shift (e.g. after a Market change)
  useEffect(() => {
    if (!dateBounds) return;
    setDraftFilters((p) => {
      const nextStart = p.startDate && p.startDate < dateBounds.min ? dateBounds.min : p.startDate && p.startDate > dateBounds.max ? dateBounds.max : p.startDate;
      const nextEnd = p.endDate && p.endDate > dateBounds.max ? dateBounds.max : p.endDate && p.endDate < dateBounds.min ? dateBounds.min : p.endDate;
      if (nextStart === p.startDate && nextEnd === p.endDate) return p;
      return { ...p, startDate: nextStart, endDate: nextEnd };
    });
  }, [dateBounds]);

  // Hero SKU price trend data
  useEffect(() => {
    let cancelled = false;
    getHeroSkuPriceTrend(selectedFilters)
      .then((res) => { if (!cancelled) { setHeroSkuPriceTrend(res.data ?? res); setLoading(false); } })
      .catch(() => { if (!cancelled) { setHeroSkuPriceTrend(null); setLoading(false); } });
    return () => { cancelled = true; };
  }, [selectedFilters]);

  // Persist filters
  useEffect(() => {
    try { localStorage.setItem(STORAGE_KEY, JSON.stringify(selectedFilters)); } catch {}
  }, [selectedFilters]);

  const applyFilters = () => { setSelectedFilters({ ...draftFilters }); };
  const resetFilters = () => {
    setDraftFilters(DEFAULT_FILTERS);
    setSelectedFilters(DEFAULT_FILTERS);
    try { localStorage.removeItem(STORAGE_KEY); } catch {}
  };

  const buildOptions = (items: string[], label: string) => [
    { label, value: "" }, ...items.map((item) => ({ label: item, value: item })),
  ];

  /* =========================
     CHART DATA
  ========================= */

  const effWeeks = heroSkuPriceTrend?.weeks ?? [];

  const CAN33_EXCLUDED_BRANDS = ["tiger", "birra moretti"];
  const can33Skus = (heroSkuPriceTrend?.skus ?? []).filter((s) => {
    if (s.pack_type?.toLowerCase() !== "can" || Number(s.pack) !== 24 || s.sub_type?.toLowerCase() !== "regular") return false;
    const brand = s.sku_label.split("·")[0].trim().toLowerCase();
    const packSize = s.pack_size?.toLowerCase();
    if (brand === "budweiser") return packSize === "35.5cl";
    return packSize === "33cl" && !CAN33_EXCLUDED_BRANDS.includes(brand);
  });
  const can33Data = effWeeks.map((date, i) => {
    const obj: Record<string, any> = {
      date: new Date(date).toLocaleDateString("en-GB", { day: "2-digit", month: "short" }),
    };
    can33Skus.forEach((sku, si) => { obj[`s${si}`] = sku.eff_price?.[i] ?? null; });
    return obj;
  });
  const can33Lines = can33Skus.map((sku, si) => ({
    key: `s${si}`,
    color: getPricingBrandColor(sku.sku_label, si),
    label: getPricingBrandLabel(sku.sku_label),
  }));

  const CAN50_EXCLUDED_BRANDS = ["birra moretti"];
  const can50Skus = (heroSkuPriceTrend?.skus ?? []).filter((s) => {
    if (s.pack_type?.toLowerCase() !== "can" || Number(s.pack) !== 24 || s.sub_type?.toLowerCase() !== "regular") return false;
    const brand = s.sku_label.split("·")[0].trim().toLowerCase();
    const packSize = s.pack_size?.toLowerCase();
    if (brand === "budweiser") return packSize === "47.3cl";
    return packSize === "50cl" && !CAN50_EXCLUDED_BRANDS.includes(brand);
  });
  const can50Data = effWeeks.map((date, i) => {
    const obj: Record<string, any> = {
      date: new Date(date).toLocaleDateString("en-GB", { day: "2-digit", month: "short" }),
    };
    can50Skus.forEach((sku, si) => { obj[`s${si}`] = sku.eff_price?.[i] ?? null; });
    return obj;
  });
  const can50Lines = can50Skus.map((sku, si) => ({
    key: `s${si}`,
    color: getPricingBrandColor(sku.sku_label, si),
    label: getPricingBrandLabel(sku.sku_label),
  }));

  const GLASS_BRANDS = ["heineken", "corona", "stella"];
  const glassSkus = (heroSkuPriceTrend?.skus ?? []).filter(
    (s) => s.pack_type?.toLowerCase() === "glass" && Number(s.pack) === 24 && s.sub_type?.toLowerCase() === "regular" && ["33cl", "35.5cl"].includes(s.pack_size?.toLowerCase()) && GLASS_BRANDS.includes(s.sku_label.split("·")[0].trim().toLowerCase())
  );
  const glassData = effWeeks.map((date, i) => {
    const obj: Record<string, any> = {
      date: new Date(date).toLocaleDateString("en-GB", { day: "2-digit", month: "short" }),
    };
    glassSkus.forEach((sku, si) => { obj[`s${si}`] = sku.eff_price?.[i] ?? null; });
    return obj;
  });
  const glassLines = glassSkus.map((sku, si) => ({
    key: `s${si}`,
    color: getPricingBrandColor(sku.sku_label, si),
    label: getPricingBrandLabel(sku.sku_label),
  }));

  const GLASS_SP_BRANDS = ["birra moretti", "peroni"];
  const glassSPSkus = (heroSkuPriceTrend?.skus ?? []).filter(
    (s) => s.pack_type?.toLowerCase() === "glass" && s.pack_size?.toLowerCase() === "33cl" && Number(s.pack) === 24 && s.sub_type?.toLowerCase() === "regular" && GLASS_SP_BRANDS.includes(s.sku_label.split("·")[0].trim().toLowerCase())
  );
  const glassSPData = effWeeks.map((date, i) => {
    const obj: Record<string, any> = {
      date: new Date(date).toLocaleDateString("en-GB", { day: "2-digit", month: "short" }),
    };
    glassSPSkus.forEach((sku, si) => { obj[`s${si}`] = sku.eff_price?.[i] ?? null; });
    return obj;
  });
  const glassSPLines = glassSPSkus.map((sku, si) => ({
    key: `s${si}`,
    color: getPricingBrandColor(sku.sku_label, si),
    label: getPricingBrandLabel(sku.sku_label),
  }));

  const canSPSkus = (heroSkuPriceTrend?.skus ?? []).filter((s) => {
    if (s.pack_type?.toLowerCase() !== "can" || Number(s.pack) !== 24 || s.sub_type?.toLowerCase() !== "regular") return false;
    const brand = s.sku_label.split("·")[0].trim().toLowerCase();
    const packSize = s.pack_size?.toLowerCase();
    if (brand === "peroni") return packSize === "35.5cl";
    return brand === "birra moretti" && packSize === "33cl";
  });
  const canSPData = effWeeks.map((date, i) => {
    const obj: Record<string, any> = {
      date: new Date(date).toLocaleDateString("en-GB", { day: "2-digit", month: "short" }),
    };
    canSPSkus.forEach((sku, si) => { obj[`s${si}`] = sku.eff_price?.[i] ?? null; });
    return obj;
  });
  const canSPLines = canSPSkus.map((sku, si) => ({
    key: `s${si}`,
    color: getPricingBrandColor(sku.sku_label, si),
    label: getPricingBrandLabel(sku.sku_label),
  }));

  const STRONG_CAN_BRANDS = ["kingfisher", "red horse", "haywards"];
  const STRONG_CAN_SUB_TYPES = ["strong", "red strong"];
  const strongCanRawSkus = (heroSkuPriceTrend?.skus ?? []).filter(
    (s) => s.pack_type?.toLowerCase() === "can" && s.pack_size?.toLowerCase() === "50cl" && Number(s.pack) === 24 && STRONG_CAN_SUB_TYPES.includes(s.sub_type?.toLowerCase()) && STRONG_CAN_BRANDS.includes(s.sku_label.split("·")[0].trim().toLowerCase())
  );
  const strongCanSkus = STRONG_CAN_BRANDS.map((brand) => {
    const brandSkus = strongCanRawSkus.filter((s) => s.sku_label.split("·")[0].trim().toLowerCase() === brand);
    if (brandSkus.length === 0) return null;
    const primary = brandSkus.find((s) => s.sub_type?.toLowerCase() === "strong") ?? brandSkus[0];
    const merged_eff_price = effWeeks.map((_, i) => {
      const strongVal = brandSkus.find((s) => s.sub_type?.toLowerCase() === "strong")?.eff_price?.[i] ?? null;
      if (strongVal !== null) return strongVal;
      return brandSkus.find((s) => s.sub_type?.toLowerCase() === "red strong")?.eff_price?.[i] ?? null;
    });
    return { ...primary, eff_price: merged_eff_price };
  }).filter((s): s is SkuPriceTrend => s !== null);
  const strongCanData = effWeeks.map((date, i) => {
    const obj: Record<string, any> = {
      date: new Date(date).toLocaleDateString("en-GB", { day: "2-digit", month: "short" }),
    };
    strongCanSkus.forEach((sku, si) => { obj[`s${si}`] = sku.eff_price?.[i] ?? null; });
    return obj;
  });
  const strongCanLines = strongCanSkus.map((sku, si) => ({
    key: `s${si}`,
    color: getPricingBrandColor(sku.sku_label, si),
    label: getPricingBrandLabel(sku.sku_label),
  }));

  const latestWeek = dateBounds?.max ?? effWeeks[effWeeks.length - 1];

  return (
    <div className="min-h-screen bg-transparent">
      <style>{`
        @keyframes hsg-shimmer { 0%{background-position:200% 0} 100%{background-position:-200% 0} }
        .hsg-shimmer { background: linear-gradient(90deg,#e2e8f0 25%,#f1f5f9 50%,#e2e8f0 75%); background-size:200% 100%; animation: hsg-shimmer 1.4s infinite; border-radius: 6px; }
      `}</style>
      <DashboardTopbar
        title="Beer & Cider Pricing Analysis"
        lastUpdated={latestWeek}
        lastUpdatedLoading={loading}
      />

      <div className="p-8">
        {/* FILTER PANEL */}
        <div className="hero-sku-filters rounded-2xl bg-[var(--card-bg)] p-3 shadow-xl border border-[var(--card-bd)] mb-6">
          <div className="hero-sku-filter">
            <FilterSelect label="Market" value={draftFilters.markets?.[0] ?? ""} onChange={(v) => setDraftFilters((p) => ({ ...p, markets: v ? [v] : [], cities: [], retailers: [] }))} options={buildOptions(apiFilters?.markets ?? [], "All Markets")} />
          </div>
          <div className="hero-sku-filter">
            <FilterSelect label="City" value={draftFilters.cities?.[0] ?? ""} onChange={(v) => setDraftFilters((p) => ({ ...p, cities: v ? [v] : [], retailers: [] }))} options={buildOptions(apiFilters?.cities ?? [], "All Cities")} />
          </div>
          <div className="hero-sku-filter">
            <FilterSelect label="Retailer" value={draftFilters.retailers?.[0] ?? ""} onChange={(v) => setDraftFilters((p) => ({ ...p, retailers: v ? [v] : [] }))} options={buildOptions(apiFilters?.["all-retailers"] ?? [], "All Retailers")} />
          </div>
          {dateBounds && (
            <div className="hero-sku-filter hero-sku-daterange">
              <FilterDateRange
                label="Date Range"
                startDate={draftFilters.startDate ?? dateBounds.min}
                endDate={draftFilters.endDate ?? dateBounds.max}
                min={dateBounds.min}
                max={dateBounds.max}
                onChange={(s, e) => setDraftFilters((p) => ({ ...p, startDate: s, endDate: e }))}
              />
            </div>
          )}
          <div className="hero-sku-currency" style={{ display: "flex", flexDirection: "column", gap: 3 }}>
            <span style={{ fontSize: 10, fontWeight: 600, color: "var(--muted-tx)", letterSpacing: "0.05em", textTransform: "uppercase" }}>Currency</span>
            <CurrencySwitch value={draftFilters.local ?? false} onChange={(v) => setDraftFilters((p) => ({ ...p, local: v }))} />
          </div>
          <div className="pricing-filter-actions">
            <button onClick={resetFilters} className="h-9 px-3 text-xs rounded-xl transition" style={{ background: "var(--card-bg-2)", color: "var(--muted-tx)", border: "1px solid var(--card-bd)" }}>Reset</button>
            <button onClick={applyFilters} disabled={loading} className="h-9 min-w-[72px] px-4 text-xs font-semibold rounded-xl bg-blue-600 text-white border border-blue-600 hover:bg-blue-700 shadow-sm transition disabled:opacity-60 disabled:cursor-not-allowed pricing-apply-button">Apply</button>
          </div>
        </div>

        {/* LOADING SKELETON */}
        {loading && (
          <div className="rounded-2xl bg-[var(--card-bg-2)] border border-[var(--card-bd)] p-6 shadow-lg">
            <div className="hsg-shimmer" style={{ height: 24, width: 260, margin: "0 auto 8px" }} />
            <div className="hsg-shimmer" style={{ height: 14, width: 320, margin: "0 auto 24px" }} />
            <div className="grid grid-cols-1 lg:grid-cols-2 gap-6">
              {[1, 2, 3, 4, 5].map((n) => (
                <div key={n}>
                  <div className="hsg-shimmer" style={{ height: 12, width: 200, marginBottom: 10 }} />
                  <div className="hsg-shimmer" style={{ height: 280, width: "100%" }} />
                </div>
              ))}
            </div>
          </div>
        )}

        {/* EFFECTIVE PRICE TRENDING */}
        {!loading && (can33Skus.length > 0 || can50Skus.length > 0 || glassSkus.length > 0 || glassSPSkus.length > 0 || canSPSkus.length > 0 || strongCanSkus.length > 0) && (
          <div className="rounded-2xl bg-[var(--card-bg-2)] border border-[var(--card-bd)] p-6 shadow-lg">
            <p className="text-lg font-semibold text-white mb-1 text-center">Effective Price Trending</p>
            <p className="text-sm text-[#7A7A73] mb-6 text-center">
              {selectedFilters.startDate || selectedFilters.endDate
                ? `Effective price per SKU from ${selectedFilters.startDate ?? dateBounds?.min} to ${selectedFilters.endDate ?? dateBounds?.max}`
                : `Effective price per SKU over the last ${effWeeks.length} weeks`}
            </p>

            <div className="grid grid-cols-1 lg:grid-cols-2 gap-6">
              {can33Skus.length > 0 && (
                <div>
                  <p className="text-sm font-bold text-white mb-2" style={{ textTransform: "uppercase", letterSpacing: "0.04em" }}>
                    CAN | 33CL | 24 PACK | REGULAR
                  </p>
                  <MultiLineChartCard title="" data={can33Data} xKey="date" lines={can33Lines} decimals={2} />
                </div>
              )}

              {can50Skus.length > 0 && (
                <div>
                  <p className="text-sm font-bold text-white mb-2" style={{ textTransform: "uppercase", letterSpacing: "0.04em" }}>
                    CAN | 50CL | 24 PACK | REGULAR
                  </p>
                  <MultiLineChartCard title="" data={can50Data} xKey="date" lines={can50Lines} decimals={2} />
                </div>
              )}

              {glassSkus.length > 0 && (
                <div>
                  <p className="text-sm font-bold text-white mb-2" style={{ textTransform: "uppercase", letterSpacing: "0.04em" }}>
                    GLASS | 33CL/35.5CL | 24 PACK | REGULAR
                  </p>
                  <MultiLineChartCard title="" data={glassData} xKey="date" lines={glassLines} decimals={2} />
                </div>
              )}

              {strongCanSkus.length > 0 && (
                <div>
                  <p className="text-sm font-bold text-white mb-2" style={{ textTransform: "uppercase", letterSpacing: "0.04em" }}>
                    CAN | 50CL | 24 PACK | STRONG
                  </p>
                  <MultiLineChartCard title="" data={strongCanData} xKey="date" lines={strongCanLines} decimals={2} />
                </div>
              )}

              {glassSPSkus.length > 0 && (
                <div>
                  <p className="text-sm font-bold text-white mb-2" style={{ textTransform: "uppercase", letterSpacing: "0.04em" }}>
                    GLASS | 33CL | 24 PACK | REGULAR | SUPER PREMIUM
                  </p>
                  <MultiLineChartCard title="" data={glassSPData} xKey="date" lines={glassSPLines} decimals={2} />
                </div>
              )}

              {canSPSkus.length > 0 && (
                <div>
                  <p className="text-sm font-bold text-white mb-2" style={{ textTransform: "uppercase", letterSpacing: "0.04em" }}>
                    CAN | 33CL | 24 PACK | REGULAR | SUPER PREMIUM
                  </p>
                  <MultiLineChartCard title="" data={canSPData} xKey="date" lines={canSPLines} decimals={2} />
                </div>
              )}
            </div>
          </div>
        )}
      </div>
    </div>
  );
}
