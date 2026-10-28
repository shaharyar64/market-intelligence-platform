"use client";

import React, { useEffect, useState } from "react";
import DashboardTopbar from "@/components/layout/DashboardTopbar";
import { getHeroSkuTracker, getFilters, getKPIs, Filters } from "@/lib/pricingAnalysis";
import FilterSelect from "@/components/filters/FilterSelect";
import LastUpdatedCard from "@/components/pricing/LastUpdatedCard";
import * as XLSX from "xlsx";
import { Download } from "lucide-react";

/* =========================
   TYPES
========================= */

interface SkuRow {
  category: string;
  segment: string;
  brand: string;
  brand_display: string;
  sku_label: string;
  pack_type: string;
  pack_size: string;
  pack: number;
  sub_type: string;
  eff_price: number | null;
  regular_price: number | null;
  promo_price: number | null;
  delta_eff_pct: number | null;
  top10_pct: number | null;
  first_page_pct: number | null;
  delta_top10_pt: number | null;
  delta_first_page_pt: number | null;
  price_flag: "red" | "amber" | "promo" | "ok" | null;
  vis_flag: "red" | "ok" | null;
  has_pricing_data: boolean;
  has_visibility_data: boolean;
  pricing_currency: string;
}

interface Section { section: string; label: string; rows: SkuRow[] }
interface TrackerData { week_date: string; prev_week_date: string; pricing_currency: string; sections: Section[] }
interface FiltersResponse { markets: string[]; cities: string[]; sub_types: string[]; comp: string[]; brands: string[]; types: string[]; quantity: string[]; skus: number[]; dates: string[]; "all-retailers"?: string[] }

/* =========================
   FILTER PERSISTENCE
========================= */

const DEFAULT_FILTERS: Filters = { markets: [], cities: [], retailers: [], segments: [], local: false };
const HERO_STORAGE_KEY = "pricing_hero_sku_filters";
const loadStoredFilters = (): Filters => {
  if (typeof window === "undefined") return DEFAULT_FILTERS;
  try { const s = localStorage.getItem(HERO_STORAGE_KEY); return s ? { ...DEFAULT_FILTERS, ...JSON.parse(s) } : DEFAULT_FILTERS; }
  catch { return DEFAULT_FILTERS; }
};

/* =========================
   LAYOUT CONSTANTS  (mirrors pricing/sales)
========================= */

// Segment, Brand, Type, Size, PK, Sub
const FIXED_WIDTHS  = [130, 150, 62, 64, 40, 88] as const;
const FIXED_OFFSETS = [0,   130, 280, 342, 406, 446] as const;
const FIXED_TOTAL   = 534;
const FIXED_COUNT   = FIXED_WIDTHS.length;

const HEADER_H = 34;

function stickyCol(i: number, bg: string, zIndex = 2): React.CSSProperties {
  return {
    position: "sticky",
    left: FIXED_OFFSETS[i],
    width: FIXED_WIDTHS[i],
    maxWidth: FIXED_WIDTHS[i],
    background: bg,
    zIndex,
    boxShadow: i === FIXED_COUNT - 1 ? "6px 0 12px -6px rgba(15,23,42,0.18)" : undefined,
  };
}

function stickySpan(bg: string, zIndex = 2): React.CSSProperties {
  return {
    position: "sticky", left: 0,
    minWidth: FIXED_TOTAL, width: FIXED_TOTAL, maxWidth: FIXED_TOTAL,
    background: bg, zIndex,
    boxShadow: "6px 0 12px -6px rgba(15,23,42,0.18)",
  };
}

const TRUNCATE: React.CSSProperties = { overflow: "hidden", textOverflow: "ellipsis", whiteSpace: "nowrap" };

/* =========================
   CURRENCY SWITCH
========================= */

const CurrencySwitch = ({ value, onChange }: { value: boolean; onChange: (v: boolean) => void }) => (
  <div style={{ background: "var(--card-bg-2)", border: "1px solid var(--card-bd)", boxShadow: "0 2px 10px rgba(15,23,42,0.08)", width: "fit-content" }} className="inline-flex items-center gap-0.5 rounded-full p-0.5">
    <button type="button" onClick={() => onChange(true)}  style={{ color: value  ? "#ffffff" : "var(--muted-tx)", background: value  ? "#2563eb" : "transparent" }} className="h-6 rounded-full px-2.5 text-[11px] font-semibold leading-none transition-colors">Local</button>
    <button type="button" onClick={() => onChange(false)} style={{ color: !value ? "#ffffff" : "var(--muted-tx)", background: !value ? "#2563eb" : "transparent" }} className="h-6 rounded-full px-2.5 text-[11px] font-semibold leading-none transition-colors">USD</button>
  </div>
);

/* =========================
   COLOUR HELPERS
========================= */

function diffBg(v: number) { return v > 0 ? "#dcfce7" : v < 0 ? "#fee2e2" : "#fef9c3"; }
function diffFg(v: number) { return v > 0 ? "#166534" : v < 0 ? "#991b1b" : "#713f12"; }

const SEGMENT_COLORS: Record<string, { dot: string; text: string; bg: string }> = {
  mainstream:      { dot: "#3b82f6", text: "#1d4ed8", bg: "#eff6ff" },
  premium:         { dot: "#8b5cf6", text: "#6d28d9", bg: "#f5f3ff" },
  strong:          { dot: "#f59e0b", text: "#92400e", bg: "#fffbeb" },
  "super premium": { dot: "#ec4899", text: "#9d174d", bg: "#fdf2f8" },
};
function segColor(seg: string) { return SEGMENT_COLORS[seg.toLowerCase()] ?? { dot: "#94a3b8", text: "#475569", bg: "#f8fafc" }; }

const SECTION_CFG: Record<string, { bg: string; color: string; border: string }> = {
  our_portfolio:   { bg: "#eff6ff", color: "#1e40af", border: "#bfdbfe" },
  key_competitors: { bg: "#f0fdf4", color: "#166534", border: "#bbf7d0" },
};
const FALLBACK_SECTION = { bg: "#f8fafc", color: "#334155", border: "#e2e8f0" };

/* =========================
   CELL COMPONENTS
========================= */

const DASH = <span style={{ color: "#cbd5e1" }}>—</span>;

function DeltaPct({ v }: { v: number | null }) {
  if (v === null || v === undefined || v === 0) return DASH;
  const pos = v > 0;
  return <span style={{ fontWeight: 700, fontSize: 11, color: pos ? "#16a34a" : "#dc2626" }}>{pos ? "+" : "−"}{Math.abs(v).toFixed(1)}%</span>;
}

function DeltaPt({ v }: { v: number | null }) {
  if (v === null || v === undefined || v === 0) return DASH;
  const pos = v > 0;
  return <span style={{ fontWeight: 700, fontSize: 11, color: pos ? "#16a34a" : "#dc2626" }}>{pos ? "+" : "−"}{Math.abs(v)}pt</span>;
}

function PriceFlag({ flag }: { flag: SkuRow["price_flag"] }) {
  if (!flag || flag === "promo") return DASH;
  const m: Record<string, { bg: string; fg: string; bd: string; label: string }> = {
    red:   { bg: "#fee2e2", fg: "#991b1b", bd: "#fca5a5", label: "Red" },
    amber: { bg: "#fef3c7", fg: "#92400e", bd: "#fcd34d", label: "Amber" },
    ok:    { bg: "#dcfce7", fg: "#166534", bd: "#86efac", label: "OK" },
  };
  const s = m[flag]; if (!s) return DASH;
  return <span style={{ display: "inline-block", padding: "1px 7px", borderRadius: 99, fontSize: 10, fontWeight: 700, background: s.bg, color: s.fg, border: `1px solid ${s.bd}` }}>{s.label}</span>;
}

function VisFlag({ flag }: { flag: SkuRow["vis_flag"] }) {
  if (!flag) return DASH;
  const m: Record<string, { bg: string; fg: string; bd: string; label: string }> = {
    red: { bg: "#fee2e2", fg: "#991b1b", bd: "#fca5a5", label: "Red" },
    ok:  { bg: "#dcfce7", fg: "#166534", bd: "#86efac", label: "OK" },
  };
  const s = m[flag]; if (!s) return DASH;
  return <span style={{ display: "inline-block", padding: "1px 7px", borderRadius: 99, fontSize: 10, fontWeight: 700, background: s.bg, color: s.fg, border: `1px solid ${s.bd}` }}>{s.label}</span>;
}

const CELL: React.CSSProperties = { padding: "9px 12px", textAlign: "center", borderRight: "1px solid #f0f0f0", fontSize: 12, minWidth: 80 };

/* =========================
   PAGE
========================= */

export default function HeroSkuTrackerPage() {
  const topScrollRef = React.useRef<HTMLDivElement>(null);
  const tableWrapRef = React.useRef<HTMLDivElement>(null);
  const tableRef     = React.useRef<HTMLTableElement>(null);
  const [tableInnerWidth, setTableInnerWidth] = useState(0);
  const onTopScroll   = () => { if (tableWrapRef.current && topScrollRef.current) tableWrapRef.current.scrollLeft = topScrollRef.current.scrollLeft; };
  const onTableScroll = () => { if (topScrollRef.current && tableWrapRef.current) topScrollRef.current.scrollLeft = tableWrapRef.current.scrollLeft; };

  const [trackerData, setTrackerData] = useState<TrackerData | null>(null);
  const [kpis, setKpis] = useState<any>(null);
  const [loading, setLoading] = useState(true);
  const [apiFilters, setApiFilters] = useState<FiltersResponse | null>(null);
  const [selectedFilters, setSelectedFilters] = useState<Filters>(loadStoredFilters);
  const [draftFilters, setDraftFilters] = useState<Filters>(loadStoredFilters);

  useEffect(() => {
    const { markets, cities } = draftFilters;
    getFilters({ markets, cities, retailers: draftFilters.retailers }).then((res) => setApiFilters(res.data ?? res)).catch(() => setApiFilters(null));
  }, [draftFilters]);

  useEffect(() => {
    setLoading(true);
    Promise.all([
      getHeroSkuTracker(selectedFilters).then((res) => setTrackerData(res.data ?? res)).catch(() => setTrackerData(null)),
      getKPIs(selectedFilters).then((res) => setKpis(res.data ?? res)).catch(() => setKpis(null)),
    ]).finally(() => setLoading(false));
  }, [selectedFilters]);

  useEffect(() => {
    try { localStorage.setItem(HERO_STORAGE_KEY, JSON.stringify(selectedFilters)); } catch {}
  }, [selectedFilters]);

  useEffect(() => {
    if (tableRef.current) setTableInnerWidth(tableRef.current.scrollWidth);
  }, [trackerData, loading]);

  useEffect(() => {
    if (tableWrapRef.current) tableWrapRef.current.scrollLeft = 0;
    if (topScrollRef.current) topScrollRef.current.scrollLeft = 0;
  }, [trackerData]);

  const applyFilters = () => { setLoading(true); setSelectedFilters({ ...draftFilters }); };
  const resetFilters = () => {
    setDraftFilters(DEFAULT_FILTERS); setSelectedFilters(DEFAULT_FILTERS);
    try { localStorage.removeItem(HERO_STORAGE_KEY); } catch {}
  };

  const SEGMENT_ORDER = ["premium", "mainstream", "super premium", "strong"];
  const segmentOptions = React.useMemo(() => {
    const all = trackerData?.sections.flatMap((s) => s.rows.map((r) => r.segment)) ?? [];
    return [...new Set(all)].sort((a, b) => {
      const ai = SEGMENT_ORDER.indexOf(a.toLowerCase());
      const bi = SEGMENT_ORDER.indexOf(b.toLowerCase());
      return (ai === -1 ? 99 : ai) - (bi === -1 ? 99 : bi);
    });
  }, [trackerData]);

  const buildOptions = (items: string[], label: string) => [
    { label, value: "" }, ...items.map((item) => ({ label: item, value: item })),
  ];
  const fmtDate = (d: string) => new Date(d).toLocaleDateString("en-GB", { day: "numeric", month: "short", year: "numeric" });
  const currency = trackerData?.pricing_currency ?? "USD";

  const selectedSegment = selectedFilters.segments?.[0] ?? "";

  const biggestPriceMove = kpis?.biggest_price_move ?? null;
  const biggestVisMove   = kpis?.biggest_visibility_move ?? null;

  const [exporting, setExporting] = useState(false);
  const handleExport = () => {
    if (!trackerData) return;
    setExporting(true);
    try {
      const sortedSections = trackerData.sections.map((section) => ({
        ...section,
        rows: [...section.rows].sort((a, b) => {
          const ai = SEGMENT_ORDER.indexOf(a.segment.toLowerCase());
          const bi = SEGMENT_ORDER.indexOf(b.segment.toLowerCase());
          return (ai === -1 ? 99 : ai) - (bi === -1 ? 99 : bi);
        }),
      }));
      const rows = sortedSections.flatMap((section) =>
        section.rows.map((r) => ({
          Section:      section.label,
          Segment:      r.segment,
          Brand:        r.brand_display,
          SKU:          r.sku_label,
          Type:         r.pack_type,
          Size:         r.pack_size,
          PK:           r.pack,
          Sub:          r.sub_type,
          [`Eff Price (${trackerData.pricing_currency})`]: r.eff_price ?? "",
          "Δ Eff %":    r.delta_eff_pct ?? "",
          "Top 10%":    r.top10_pct ?? "",
          "1st Page%":  r.first_page_pct ?? "",
          "Δ Top-10 pt":      r.delta_top10_pt ?? "",
          "Δ 1st Page pt":    r.delta_first_page_pt ?? "",
          "Price Flag": r.price_flag ?? "",
          "Vis Flag":   r.vis_flag ?? "",
        }))
      );
      const ws = XLSX.utils.json_to_sheet(rows);
      ws["!cols"] = Object.keys(rows[0] ?? {}).map(() => ({ wch: 18 }));
      const wb = XLSX.utils.book_new();
      XLSX.utils.book_append_sheet(wb, ws, "Hero SKU Tracker");
      XLSX.writeFile(wb, `hero_sku_tracker_${trackerData.week_date}.xlsx`);
    } finally {
      setExporting(false);
    }
  };

  return (
    <div className="w-full bg-transparent" style={{ minHeight: "100%" }}>
      <style>{`
        @keyframes hsku-shimmer { 0%{background-position:200% 0} 100%{background-position:-200% 0} }
        .vis-scroll::-webkit-scrollbar { height: 8px; }
        .vis-scroll::-webkit-scrollbar-track { background: #e2e8f0; border-radius: 4px; }
        .vis-scroll::-webkit-scrollbar-thumb { background: #94a3b8; border-radius: 4px; }
        .hsku-row:hover > td { filter: brightness(0.97); }
      `}</style>

      <DashboardTopbar title="Beer & Cider Pricing Analysis" lastUpdated={trackerData?.week_date} lastUpdatedLoading={loading} />

      <div className="p-8">

        {/* Filters */}
        <div className="hero-sku-filters rounded-2xl bg-[var(--card-bg)] p-4 shadow-xl border border-[var(--card-bd)] mb-6">
          <div className="hero-sku-filter"><FilterSelect label="Market"   value={draftFilters.markets?.[0]   ?? ""} onChange={(v) => setDraftFilters((p) => ({ ...p, markets: v ? [v] : [], cities: [], retailers: [] }))} options={buildOptions(apiFilters?.markets ?? [], "All Markets")} /></div>
          <div className="hero-sku-filter"><FilterSelect label="City"     value={draftFilters.cities?.[0]    ?? ""} onChange={(v) => setDraftFilters((p) => ({ ...p, cities:   v ? [v] : [], retailers: [] }))}                  options={buildOptions(apiFilters?.cities  ?? [], "All Cities")}   /></div>
          <div className="hero-sku-filter"><FilterSelect label="Retailer" value={draftFilters.retailers?.[0] ?? ""} onChange={(v) => setDraftFilters((p) => ({ ...p, retailers: v ? [v] : [] }))}                                options={buildOptions(apiFilters?.["all-retailers"] ?? [], "All Retailers")} /></div>
          <div className="hero-sku-filter"><FilterSelect label="Segment"  value={draftFilters.segments?.[0]  ?? ""} onChange={(v) => setDraftFilters((p) => ({ ...p, segments: v ? [v] : [] }))}                                 options={buildOptions(segmentOptions, "All Segments")} /></div>
          <div className="hero-sku-currency" style={{ display: "flex", flexDirection: "column", gap: 4 }}>
            <span style={{ fontSize: 11, fontWeight: 600, color: "var(--muted-tx)", letterSpacing: "0.05em", textTransform: "uppercase" }}>Currency</span>
            <CurrencySwitch value={draftFilters.local ?? false} onChange={(v) => setDraftFilters((p) => ({ ...p, local: v }))} />
          </div>
          <div className="pricing-filter-actions">
            <button onClick={resetFilters} className="h-[42px] px-4 text-sm rounded-xl transition" style={{ background: "var(--card-bg-2)", color: "var(--muted-tx)", border: "1px solid var(--card-bd)" }}>Reset</button>
            <button onClick={applyFilters} disabled={loading} className="h-[42px] min-w-[84px] px-5 text-sm font-semibold rounded-xl bg-blue-600 text-white border border-blue-600 hover:bg-blue-700 shadow-sm transition disabled:opacity-60 disabled:cursor-not-allowed pricing-apply-button">Apply</button>
          </div>
        </div>

        {/* KPI cards */}
        <div className="grid grid-cols-1 sm:grid-cols-2 gap-4 mb-6">
          {/* Biggest Price Move */}
          <div style={{ background: "var(--card-bg)", border: "1px solid var(--card-bd)", borderRadius: 16, padding: "20px 24px", boxShadow: "0 1px 6px rgba(15,23,42,0.06)" }}>
            {loading ? (
              <>
                <div style={{ height: 12, width: 140, borderRadius: 4, background: "var(--card-bd)", marginBottom: 14 }} className="animate-pulse" />
                <div style={{ height: 22, width: 260, borderRadius: 4, background: "var(--card-bd)" }} className="animate-pulse" />
              </>
            ) : (
              <>
                <div style={{ fontSize: 12, fontWeight: 600, color: "var(--muted-tx)", textTransform: "uppercase", letterSpacing: "0.06em", marginBottom: 10 }}>Biggest price move</div>
                {biggestPriceMove ? (
                  <div style={{ fontSize: 17, fontWeight: 700, color: "var(--title-tx)" }}>
                    {typeof biggestPriceMove === "string" ? biggestPriceMove : (
                      <>
                        {`${biggestPriceMove.sku_label ?? biggestPriceMove.brand_display}`}&nbsp;
                        <span style={{ color: (biggestPriceMove.delta_eff_pct ?? biggestPriceMove.delta) < 0 ? "#dc2626" : "#16a34a" }}>
                          {(biggestPriceMove.delta_eff_pct ?? biggestPriceMove.delta) > 0 ? "+" : "−"}{Math.abs(biggestPriceMove.delta_eff_pct ?? biggestPriceMove.delta).toFixed(1)}%
                        </span>
                        {biggestPriceMove.price_flag === "promo" && <span style={{ fontWeight: 400, color: "var(--muted-tx)", fontSize: 13 }}> (promo deepened)</span>}
                        {biggestPriceMove.price_flag === "red" && <span style={{ fontWeight: 400, color: "#dc2626", fontSize: 13 }}> (regular price drop)</span>}
                      </>
                    )}
                  </div>
                ) : <div style={{ fontSize: 15, color: "var(--muted-tx)" }}>—</div>}
              </>
            )}
          </div>

          {/* Biggest Visibility Move */}
          <div style={{ background: "var(--card-bg)", border: "1px solid var(--card-bd)", borderRadius: 16, padding: "20px 24px", boxShadow: "0 1px 6px rgba(15,23,42,0.06)" }}>
            {loading ? (
              <>
                <div style={{ height: 12, width: 160, borderRadius: 4, background: "var(--card-bd)", marginBottom: 14 }} className="animate-pulse" />
                <div style={{ height: 22, width: 240, borderRadius: 4, background: "var(--card-bd)" }} className="animate-pulse" />
              </>
            ) : (
              <>
                <div style={{ fontSize: 12, fontWeight: 600, color: "var(--muted-tx)", textTransform: "uppercase", letterSpacing: "0.06em", marginBottom: 10 }}>Biggest visibility move</div>
                {biggestVisMove ? (
                  <div style={{ fontSize: 17, fontWeight: 700, color: "var(--title-tx)" }}>
                    {typeof biggestVisMove === "string" ? biggestVisMove : (
                      <>
                        {`${biggestVisMove.sku_label ?? biggestVisMove.brand_display}`}&nbsp;
                        <span style={{ color: (biggestVisMove.delta_top10_pt ?? biggestVisMove.delta) < 0 ? "#dc2626" : "#16a34a" }}>
                          {(biggestVisMove.delta_top10_pt ?? biggestVisMove.delta) > 0 ? "+" : "−"}{Math.abs(biggestVisMove.delta_top10_pt ?? biggestVisMove.delta)}pt Top-10
                        </span>
                        {biggestVisMove.vis_flag === "red" && <span style={{ fontWeight: 400, color: "#dc2626", fontSize: 13 }}> (dropped out)</span>}
                      </>
                    )}
                  </div>
                ) : <div style={{ fontSize: 15, color: "var(--muted-tx)" }}>—</div>}
              </>
            )}
          </div>
        </div>

        {/* Table card */}
        <div style={{ borderRadius: 14, border: "1px solid #e2e8f0", boxShadow: "0 2px 12px rgba(15,23,42,0.08)", overflow: "hidden", background: "white" }}>

          {/* Card header */}
          <div style={{ padding: "12px 18px", background: "white", borderBottom: "1px solid #e2e8f0", display: "flex", alignItems: "center", justifyContent: "space-between", flexWrap: "wrap", gap: 8 }}>
            <div>
              <div style={{ fontWeight: 700, fontSize: 15, color: "#0f172a" }}>Hero SKU Tracker</div>
              {trackerData && (
                <div style={{ fontSize: 12, color: "#64748b", marginTop: 2 }}>
                  Week of <strong style={{ color: "#334155" }}>{fmtDate(trackerData.week_date)}</strong>
                  {trackerData.prev_week_date && <> vs <strong style={{ color: "#334155" }}>{fmtDate(trackerData.prev_week_date)}</strong></>}
                  &nbsp;·&nbsp;{currency}
                </div>
              )}
            </div>
            <div style={{ display: "flex", alignItems: "center", gap: 16, flexWrap: "wrap" }}>
            {/* Flag legend */}
            <div style={{ display: "flex", gap: 10, flexWrap: "wrap" }}>
              {([["#fee2e2","#991b1b","Red"],["#fef3c7","#92400e","Amber"],["#dcfce7","#166534","OK"]] as const).map(([bg,fg,label]) => (
                <span key={label} style={{ display: "inline-flex", alignItems: "center", gap: 5, fontSize: 11 }}>
                  <span style={{ width: 9, height: 9, borderRadius: 99, background: bg, border: `1px solid ${fg}44`, display: "inline-block" }} />
                  <span style={{ color: fg, fontWeight: 600 }}>{label}</span>
                </span>
              ))}
              <span style={{ color: "#94a3b8", fontSize: 11 }}>· Δ = vs prev week</span>
            </div>
            <button onClick={handleExport} disabled={exporting || !trackerData}
              style={{ display: "inline-flex", alignItems: "center", gap: 6, padding: "6px 14px", borderRadius: 8, fontSize: 12, fontWeight: 600, background: "#eff6ff", color: "#1d4ed8", border: "1px solid #bfdbfe", cursor: exporting || !trackerData ? "not-allowed" : "pointer", opacity: exporting || !trackerData ? 0.6 : 1 }}>
              <Download size={13} /> {exporting ? "Exporting…" : "Download Excel"}
            </button>
            </div>
          </div>

          {/* Top scroll mirror */}
          <div ref={topScrollRef} onScroll={onTopScroll} className="vis-scroll"
            style={{ overflowX: "scroll", overflowY: "hidden", height: 10, background: "#f1f5f9", flexShrink: 0 }}>
            <div style={{ width: tableInnerWidth || 9999, height: 1 }} />
          </div>

          {/* Table scroll */}
          <div ref={tableWrapRef} onScroll={onTableScroll} className="vis-scroll"
            style={{ width: "100%", overflowX: "auto", overflowY: "auto", maxHeight: "calc(100vh - 340px)" }}>
            <table ref={tableRef} style={{ borderCollapse: "collapse", fontSize: 12, whiteSpace: "nowrap", background: "white", width: "max-content", minWidth: "100%" }}>

              <thead>
                <tr style={{ background: "#f8fafc" }}>
                  {/* Fixed sticky headers */}
                  {(["Segment","Brand","Type","Size","PK","Sub"] as const).map((label, i) => (
                    <th key={label} style={{
                      padding: "9px 10px", textAlign: "left",
                      color: "#64748b", fontWeight: 700, fontSize: 10,
                      letterSpacing: "0.06em", textTransform: "uppercase",
                      borderBottom: "2px solid #e2e8f0",
                      borderRight: i === FIXED_COUNT - 1 ? "2px solid #cbd5e1" : "1px solid #e2e8f0",
                      minWidth: FIXED_WIDTHS[i], width: FIXED_WIDTHS[i],
                      position: "sticky", top: 0, zIndex: 9,
                      ...stickyCol(i, "#f8fafc", 9),
                    }}>{label}</th>
                  ))}
                  {/* Data headers */}
                  {[
                    { label: `Eff price (${currency})`, align: "center" },
                    { label: "Δ Eff",         align: "center"  },
                    { label: "T10% · 1st pg%", align: "center" },
                    { label: "Δ Top-10",       align: "center" },
                    { label: "Δ 1st page",     align: "center" },
                    { label: "Price flag",     align: "center" },
                    { label: "Vis flag",       align: "center" },
                  ].map(({ label, align }) => (
                    <th key={label} style={{
                      ...CELL, padding: "9px 12px",
                      textAlign: align as React.CSSProperties["textAlign"],
                      color: "#64748b", fontWeight: 700, fontSize: 10,
                      letterSpacing: "0.06em", textTransform: "uppercase",
                      borderBottom: "2px solid #e2e8f0",
                      position: "sticky", top: 0, zIndex: 1, background: "#f8fafc",
                    }}>{label}</th>
                  ))}
                </tr>
              </thead>

              <tbody>
                {loading ? (
                  Array.from({ length: 12 }).map((_, i) => (
                    <tr key={i} style={{ borderBottom: "1px solid #f1f5f9" }}>
                      {Array.from({ length: FIXED_COUNT + 7 }).map((_, j) => (
                        <td key={j} style={{ padding: "8px 10px" }}>
                          <div style={{ height: 11, borderRadius: 3, width: j < FIXED_COUNT ? "70%" : "55%", background: "linear-gradient(90deg,#e2e8f0 25%,#f1f5f9 50%,#e2e8f0 75%)", backgroundSize: "200% 100%", animation: "hsku-shimmer 1.4s infinite" }} />
                        </td>
                      ))}
                    </tr>
                  ))
                ) : !trackerData || trackerData.sections.length === 0 ? (
                  <tr><td colSpan={FIXED_COUNT + 7} style={{ padding: 56, textAlign: "center", color: "#94a3b8" }}>No data available</td></tr>
                ) : (
                  trackerData.sections.map((section) => {
                    const scfg = SECTION_CFG[section.section] ?? FALLBACK_SECTION;

                    /* filter by segment, then group by brand */
                    const filtered = section.rows
                      .filter((r) => !selectedSegment || r.segment.toLowerCase() === selectedSegment.toLowerCase())
                      .sort((a, b) => {
                        const ai = SEGMENT_ORDER.indexOf(a.segment.toLowerCase());
                        const bi = SEGMENT_ORDER.indexOf(b.segment.toLowerCase());
                        return (ai === -1 ? 99 : ai) - (bi === -1 ? 99 : bi);
                      });
                    const groups: SkuRow[][] = [];
                    filtered.forEach((row) => {
                      const last = groups[groups.length - 1];
                      if (last && last[0].brand === row.brand) last.push(row);
                      else groups.push([row]);
                    });

                    if (groups.length === 0) return null;

                    return (
                      <React.Fragment key={section.section}>
                        {/* Section band */}
                        <tr>
                          <td colSpan={FIXED_COUNT + 7} style={{
                            padding: "8px 16px",
                            background: scfg.bg,
                            borderTop: `2px solid ${scfg.border}`,
                            borderBottom: `2px solid ${scfg.border}`,
                            ...stickySpan(scfg.bg, 3),
                          }}>
                            <span style={{ fontWeight: 800, fontSize: 10, letterSpacing: "0.08em", textTransform: "uppercase", color: scfg.color }}>
                              {section.label}
                            </span>
                          </td>
                        </tr>

                        {groups.map((group, gi) => {
                          const isLastGroup = gi === groups.length - 1;
                          return (
                            <React.Fragment key={group[0].brand}>
                              {group.map((row, ri) => {
                                const isFirst    = ri === 0;
                                const isLastInGroup = ri === group.length - 1;
                                const seg = segColor(row.segment);
                                const rowBg = "white";

                                return (
                                  <tr key={`${row.brand}-${row.sku_label}-${ri}`} className="hsku-row"
                                    style={{ borderBottom: isLastInGroup && !isLastGroup ? "2px solid #e2e8f0" : "1px solid #f1f5f9", background: rowBg }}>

                                    {/* Segment — only on first row */}
                                    <td style={{ padding: "9px 10px", borderRight: "1px solid #f0f0f0", ...TRUNCATE, ...stickyCol(0, rowBg) }}>
                                      {isFirst ? (
                                        <span style={{ display: "inline-flex", alignItems: "center", gap: 4, padding: "1px 6px", borderRadius: 99, fontSize: 10, fontWeight: 700, background: seg.bg, color: seg.text }}>
                                          <span style={{ width: 5, height: 5, borderRadius: "50%", background: seg.dot, display: "inline-block", flexShrink: 0 }} />
                                          {row.segment}
                                        </span>
                                      ) : null}
                                    </td>

                                    {/* Brand — only on first row */}
                                    <td style={{ padding: "9px 10px", fontWeight: isFirst ? 700 : 400, color: isFirst ? "#0f172a" : "transparent", borderRight: "1px solid #f0f0f0", ...TRUNCATE, ...stickyCol(1, rowBg) }}>
                                      {isFirst ? row.brand_display : ""}
                                    </td>

                                    {/* Type */}
                                    <td style={{ padding: "9px 10px", color: "#475569", borderRight: "1px solid #f0f0f0", ...TRUNCATE, ...stickyCol(2, rowBg) }}>
                                      {row.pack_type}
                                    </td>

                                    {/* Size */}
                                    <td style={{ padding: "9px 10px", color: "#3b82f6", fontWeight: 600, borderRight: "1px solid #f0f0f0", ...TRUNCATE, ...stickyCol(3, rowBg) }}>
                                      {row.pack_size}
                                    </td>

                                    {/* PK */}
                                    <td style={{ padding: "9px 10px", color: "#475569", textAlign: "center", borderRight: "1px solid #f0f0f0", ...stickyCol(4, rowBg) }}>
                                      {row.pack}
                                    </td>

                                    {/* Sub */}
                                    <td style={{ padding: "9px 10px", color: "#475569", borderRight: "2px solid #cbd5e1", ...TRUNCATE, ...stickyCol(5, rowBg) }}>
                                      {row.sub_type ? row.sub_type.charAt(0).toUpperCase() + row.sub_type.slice(1) : "—"}
                                    </td>

                                    {/* Eff price */}
                                    <td style={{ ...CELL, textAlign: "center", fontWeight: 600, color: "#0f172a", background: row.has_pricing_data && row.eff_price != null ? "#f0fdf4" : undefined }}>
                                      {row.has_pricing_data && row.eff_price != null ? Math.round(row.eff_price) : DASH}
                                    </td>

                                    {/* Δ Eff */}
                                    <td style={{ ...CELL, textAlign: "center", background: row.has_pricing_data && row.delta_eff_pct != null && row.delta_eff_pct !== 0 ? diffBg(row.delta_eff_pct) : undefined }}>
                                      {row.has_pricing_data ? <DeltaPct v={row.delta_eff_pct} /> : DASH}
                                    </td>

                                    {/* T10% · 1st pg% */}
                                    <td style={{ ...CELL, textAlign: "center", fontVariantNumeric: "tabular-nums", fontWeight: 600 }}>
                                      {row.has_visibility_data && (row.top10_pct != null || row.first_page_pct != null)
                                        ? <span>{row.top10_pct ?? "—"}<span style={{ color: "#cbd5e1", margin: "0 2px" }}>·</span>{row.first_page_pct ?? "—"}</span>
                                        : DASH}
                                    </td>

                                    {/* Δ Top-10 */}
                                    <td style={{ ...CELL, textAlign: "center", background: row.has_visibility_data && row.delta_top10_pt != null && row.delta_top10_pt !== 0 ? diffBg(row.delta_top10_pt) : undefined }}>
                                      {row.has_visibility_data ? <DeltaPt v={row.delta_top10_pt} /> : DASH}
                                    </td>

                                    {/* Δ 1st page */}
                                    <td style={{ ...CELL, textAlign: "center", background: row.has_visibility_data && row.delta_first_page_pt != null && row.delta_first_page_pt !== 0 ? diffBg(row.delta_first_page_pt) : undefined }}>
                                      {row.has_visibility_data ? <DeltaPt v={row.delta_first_page_pt} /> : DASH}
                                    </td>

                                    {/* Price flag */}
                                    <td style={{ ...CELL, textAlign: "center" }}>
                                      {row.has_pricing_data ? <PriceFlag flag={row.price_flag} /> : DASH}
                                    </td>

                                    {/* Vis flag */}
                                    <td style={{ ...CELL, textAlign: "center" }}>
                                      {row.has_visibility_data ? <VisFlag flag={row.vis_flag} /> : DASH}
                                    </td>
                                  </tr>
                                );
                              })}
                            </React.Fragment>
                          );
                        })}
                      </React.Fragment>
                    );
                  })
                )}
              </tbody>
            </table>
          </div>
        </div>
      </div>
    </div>
  );
}
