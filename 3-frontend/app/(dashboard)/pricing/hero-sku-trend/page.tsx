"use client";

import React, { useEffect, useLayoutEffect, useRef, useState } from "react";
import DashboardTopbar from "@/components/layout/DashboardTopbar";
import { getHeroSkuTrend, getFilters, Filters } from "@/lib/pricingAnalysis";
import FilterSelect from "@/components/filters/FilterSelect";
import LastUpdatedCard from "@/components/pricing/LastUpdatedCard";
import * as XLSX from "xlsx";
import { Download } from "lucide-react";

/* =========================
   TYPES
========================= */

interface TrendRow {
  category: string;
  segment: string;
  brand: string;
  brand_display: string;
  sku_label: string;
  pack_type: string;
  pack_size: string;
  pack: number;
  sub_type: string;
  pricing: (number | null)[];
  pricing_deltas: (number | null)[];
  top10_pct: (number | null)[];
  top10_deltas: (number | null)[];
  first_page_pct: (number | null)[];
  first_page_deltas: (number | null)[];
  pricing_currency: string;
}

interface TrendSection { section: string; label: string; rows: TrendRow[] }
interface TrendData { weeks: string[]; pricing_currency: string; sections: TrendSection[] }
interface FiltersResponse { markets: string[]; cities: string[]; sub_types: string[]; comp: string[]; brands: string[]; types: string[]; quantity: string[]; skus: number[]; dates: string[]; "all-retailers"?: string[] }

/* =========================
   FILTER PERSISTENCE  (shared key with hero-sku-tracker)
========================= */

const DEFAULT_FILTERS: Filters = { markets: [], cities: [], retailers: [], segments: [], local: false };
const HERO_STORAGE_KEY = "pricing_hero_sku_filters";
const loadStoredFilters = (): Filters => {
  if (typeof window === "undefined") return DEFAULT_FILTERS;
  try { const s = localStorage.getItem(HERO_STORAGE_KEY); return s ? { ...DEFAULT_FILTERS, ...JSON.parse(s) } : DEFAULT_FILTERS; }
  catch { return DEFAULT_FILTERS; }
};

/* =========================
   LAYOUT CONSTANTS
========================= */

// Sticky left: Segment, Brand, Type, Size, PK, Sub
const FIXED_MIN_WIDTHS = [80, 90, 40, 40, 26, 50] as const;
const FIXED_COUNT      = 6;

const WEEK_W = 72;
const GRP_H  = 26;
const COL_H  = 32;

// stickyCol uses dynamic lefts measured after render; lefts default to 0 until measured
function stickyCol(i: number, bg: string, lefts: number[], zIndex = 2): React.CSSProperties {
  return {
    position: "sticky",
    left: lefts[i] ?? 0,
    minWidth: FIXED_MIN_WIDTHS[i],
    whiteSpace: "nowrap",
    background: bg,
    zIndex,
    boxShadow: i === FIXED_COUNT - 1 ? "6px 0 12px -6px rgba(15,23,42,0.18)" : undefined,
  };
}

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
   CELL HELPERS
========================= */

const DASH = <span style={{ color: "#cbd5e1" }}>—</span>;
const CELL: React.CSSProperties = { padding: "8px 6px", textAlign: "center", borderRight: "1px solid #d1d5db", fontSize: 12, whiteSpace: "nowrap" };

function WeekVal({ v }: { v: number | null | undefined }) {
  if (v == null) return DASH;
  return <span style={{ fontVariantNumeric: "tabular-nums" }}>{Math.round(v)}</span>;
}

function WeekPct({ v }: { v: number | null | undefined }) {
  if (v == null) return DASH;
  return <span style={{ fontVariantNumeric: "tabular-nums" }}>{Math.round(v)}%</span>;
}

function InlineDelta({ v, type }: { v: number | null | undefined; type: "pct" | "pt" }) {
  if (v == null) return null;
  if (v === 0) return <span style={{ marginLeft: 4, fontSize: 10, color: "#94a3b8" }}>—</span>;
  const pos = v > 0;
  const label = type === "pct"
    ? `${pos ? "+" : ""}${Math.round(v)}%`
    : `${pos ? "+" : ""}${Math.round(v)}pt`;
  return <span style={{ marginLeft: 4, fontSize: 10, fontWeight: 700, color: pos ? "#16a34a" : "#dc2626" }}>{label}</span>;
}

function fmtWeek(d: string) {
  return new Date(d).toLocaleDateString("en-GB", { day: "2-digit", month: "short" });
}

/* =========================
   PAGE
========================= */

export default function HeroSkuTrendPage() {
  const topScrollRef     = useRef<HTMLDivElement>(null);
  const tableWrapRef     = useRef<HTMLDivElement>(null);
  const tableRef         = useRef<HTMLTableElement>(null);
  const fixedHeaderRefs  = useRef<(HTMLTableCellElement | null)[]>(Array(FIXED_COUNT).fill(null));
  const [tableInnerWidth, setTableInnerWidth] = useState(0);
  const [dynLefts, setDynLefts] = useState<number[]>(Array(FIXED_COUNT).fill(0));
  const [dynTotal, setDynTotal] = useState(0);
  const onTopScroll   = () => { if (tableWrapRef.current && topScrollRef.current) tableWrapRef.current.scrollLeft = topScrollRef.current.scrollLeft; };
  const onTableScroll = () => { if (topScrollRef.current && tableWrapRef.current) topScrollRef.current.scrollLeft = tableWrapRef.current.scrollLeft; };

  const [trendData, setTrendData]     = useState<TrendData | null>(null);
  const [loading, setLoading]         = useState(true);
  const [apiFilters, setApiFilters]   = useState<FiltersResponse | null>(null);
  const [selectedFilters, setSelectedFilters] = useState<Filters>(loadStoredFilters);
  const [draftFilters, setDraftFilters]       = useState<Filters>(loadStoredFilters);

  useEffect(() => {
    const { markets, cities } = draftFilters;
    getFilters({ markets, cities, retailers: draftFilters.retailers }).then((res) => setApiFilters(res.data ?? res)).catch(() => setApiFilters(null));
  }, [draftFilters]);

  useEffect(() => {
    setLoading(true);
    getHeroSkuTrend(selectedFilters)
      .then((res) => setTrendData(res.data ?? res))
      .catch(() => setTrendData(null))
      .finally(() => setLoading(false));
  }, [selectedFilters]);

  useEffect(() => {
    try { localStorage.setItem(HERO_STORAGE_KEY, JSON.stringify(selectedFilters)); } catch {}
  }, [selectedFilters]);

  useEffect(() => {
    if (tableRef.current) setTableInnerWidth(tableRef.current.scrollWidth);
  }, [trendData, loading]);

  useLayoutEffect(() => {
    const lefts: number[] = [];
    let acc = 0;
    for (let i = 0; i < FIXED_COUNT; i++) {
      lefts.push(acc);
      acc += fixedHeaderRefs.current[i]?.offsetWidth ?? 0;
    }
    setDynLefts(lefts);
    setDynTotal(acc);
  }, [trendData, loading]);

  useEffect(() => {
    if (tableWrapRef.current) tableWrapRef.current.scrollLeft = 0;
    if (topScrollRef.current) topScrollRef.current.scrollLeft = 0;
  }, [trendData]);

  const applyFilters = () => { setLoading(true); setSelectedFilters({ ...draftFilters }); };
  const resetFilters = () => {
    setDraftFilters(DEFAULT_FILTERS); setSelectedFilters(DEFAULT_FILTERS);
    try { localStorage.removeItem(HERO_STORAGE_KEY); } catch {}
  };

  const buildOptions = (items: string[], label: string) => [
    { label, value: "" }, ...items.map((item) => ({ label: item, value: item })),
  ];

  const [exporting, setExporting] = useState(false);
  const handleExport = () => {
    if (!trendData) return;
    setExporting(true);
    try {
      const wkLabels = trendData.weeks.map((w, i) => `W${i + 1} (${fmtWeek(w)})`);
      const SEGMENT_ORDER_EXPORT = ["premium", "mainstream", "super premium", "strong"];
      const sortedSections = trendData.sections.map((section) => ({
        ...section,
        rows: [...section.rows].sort((a, b) => {
          const ai = SEGMENT_ORDER_EXPORT.indexOf(a.segment.toLowerCase());
          const bi = SEGMENT_ORDER_EXPORT.indexOf(b.segment.toLowerCase());
          return (ai === -1 ? 99 : ai) - (bi === -1 ? 99 : bi);
        }),
      }));
      const rows = sortedSections.flatMap((section) =>
        section.rows.map((r) => {
          const obj: Record<string, any> = {
            Section:  section.label,
            Segment:  r.segment,
            Brand:    r.brand_display,
            SKU:      r.sku_label,
            Type:     r.pack_type,
            Size:     r.pack_size,
            PK:       r.pack,
            Sub:      r.sub_type,
          };
          wkLabels.forEach((lbl, i) => { obj[`Price ${lbl}`] = r.pricing?.[i] ?? ""; });
          obj["Δ Price %"] = r.pricing_deltas?.[r.pricing_deltas.length - 1] ?? "";
          wkLabels.forEach((lbl, i) => { obj[`Top10% ${lbl}`] = r.top10_pct?.[i] ?? ""; });
          obj["Δ Top-10 pt"] = r.top10_deltas?.[r.top10_deltas.length - 1] ?? "";
          wkLabels.forEach((lbl, i) => { obj[`1stPage% ${lbl}`] = r.first_page_pct?.[i] ?? ""; });
          obj["Δ 1st Page pt"] = r.first_page_deltas?.[r.first_page_deltas.length - 1] ?? "";
          return obj;
        })
      );
      const ws = XLSX.utils.json_to_sheet(rows);
      ws["!cols"] = Object.keys(rows[0] ?? {}).map(() => ({ wch: 16 }));
      const wb = XLSX.utils.book_new();
      XLSX.utils.book_append_sheet(wb, ws, "Hero SKU Trend");
      XLSX.writeFile(wb, `hero_sku_trend_${trendData.weeks.at(-1) ?? "export"}.xlsx`);
    } finally {
      setExporting(false);
    }
  };

  const SEGMENT_ORDER = ["premium", "mainstream", "super premium", "strong"];
  const segmentOptions = React.useMemo(() => {
    const all = trendData?.sections.flatMap((s) => s.rows.map((r) => r.segment)) ?? [];
    return [...new Set(all)].sort((a, b) => {
      const ai = SEGMENT_ORDER.indexOf(a.toLowerCase());
      const bi = SEGMENT_ORDER.indexOf(b.toLowerCase());
      return (ai === -1 ? 99 : ai) - (bi === -1 ? 99 : bi);
    });
  }, [trendData]);

  const selectedSegment = selectedFilters.segments?.[0] ?? "";

  const weeks = trendData?.weeks ?? [];
  const currency = trendData?.pricing_currency ?? "USD";
  const latestWeek = weeks[weeks.length - 1];

  // Total cols: 6 fixed + 9 pricing + 9 top10 + 9 first_page = 33
  const TOTAL_COLS = FIXED_COUNT + 9 + 9 + 9;

  // Section band spanning
  const sectionBgStyle = (cfg: typeof FALLBACK_SECTION): React.CSSProperties => ({
    position: "sticky", left: 0,
    minWidth: dynTotal || 380, width: dynTotal || 380,
    background: cfg.bg, zIndex: 2,
    boxShadow: "6px 0 12px -6px rgba(15,23,42,0.18)",
  });

  return (
    <div className="w-full bg-transparent" style={{ minHeight: "100%" }}>
      <style>{`
        @keyframes hskut-shimmer { 0%{background-position:200% 0} 100%{background-position:-200% 0} }
        .vis-scroll::-webkit-scrollbar { height: 8px; }
        .vis-scroll::-webkit-scrollbar-track { background: #e2e8f0; border-radius: 4px; }
        .vis-scroll::-webkit-scrollbar-thumb { background: #94a3b8; border-radius: 4px; }
        .hskut-row:hover > td { filter: brightness(0.97); }
      `}</style>

      <DashboardTopbar title="Beer & Cider Pricing Analysis" lastUpdated={latestWeek} lastUpdatedLoading={loading} />

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

        {/* Table card */}
        <div style={{ borderRadius: 14, border: "1px solid #e2e8f0", boxShadow: "0 2px 12px rgba(15,23,42,0.08)", overflow: "hidden", background: "white" }}>

          {/* Card header */}
          <div style={{ padding: "12px 18px", background: "white", borderBottom: "1px solid #e2e8f0", display: "flex", alignItems: "center", justifyContent: "space-between", flexWrap: "wrap", gap: 8 }}>
            <div>
              <div style={{ fontWeight: 700, fontSize: 15, color: "#0f172a" }}>Hero SKU Trend — 9-Week History</div>
              {latestWeek && (
                <div style={{ fontSize: 12, color: "#64748b", marginTop: 2 }}>
                  Latest week: <strong style={{ color: "#334155" }}>{fmtWeek(latestWeek)}</strong>
                  &nbsp;·&nbsp;{currency}
                </div>
              )}
            </div>
            <div style={{ display: "flex", gap: 16, alignItems: "center", flexWrap: "wrap" }}>
              <span style={{ display: "inline-flex", alignItems: "center", gap: 6, fontSize: 11, color: "#64748b" }}>
                <span style={{ width: 8, height: 8, borderRadius: "50%", background: "#16a34a", display: "inline-block" }} /> W9 = latest week · Δ shown per cell vs prior week
              </span>
              <button onClick={handleExport} disabled={exporting || !trendData}
                style={{ display: "inline-flex", alignItems: "center", gap: 6, padding: "6px 14px", borderRadius: 8, fontSize: 12, fontWeight: 600, background: "#eff6ff", color: "#1d4ed8", border: "1px solid #bfdbfe", cursor: exporting || !trendData ? "not-allowed" : "pointer", opacity: exporting || !trendData ? 0.6 : 1 }}>
                <Download size={13} /> {exporting ? "Exporting…" : "Download Excel"}
              </button>
            </div>
          </div>

          {/* Top scroll mirror */}
          <div ref={topScrollRef} onScroll={onTopScroll} className="vis-scroll"
            style={{ overflowX: "scroll", overflowY: "hidden", height: 10, background: "#f1f5f9", flexShrink: 0 }}>
            <div style={{ width: tableInnerWidth || 9999, height: 1 }} />
          </div>

          {/* Table */}
          <div ref={tableWrapRef} onScroll={onTableScroll} className="vis-scroll"
            style={{ width: "100%", overflowX: "auto", overflowY: "auto", maxHeight: "calc(100vh - 300px)" }}>
            <table ref={tableRef} style={{ borderCollapse: "collapse", fontSize: 12, whiteSpace: "nowrap", background: "white", width: "max-content", minWidth: "100%" }}>

              <thead>
                {/* ── Row 1: group labels ── */}
                <tr style={{ background: "#f1f5f9" }}>
                  {/* Sticky fixed span */}
                  <th colSpan={FIXED_COUNT} style={{
                    position: "sticky", left: 0, zIndex: 9,
                    minWidth: dynTotal || 380,
                    background: "#f1f5f9",
                    borderBottom: "1px solid #e2e8f0",
                    height: GRP_H, top: 0,
                    boxShadow: "6px 0 12px -6px rgba(15,23,42,0.18)",
                  }} />
                  {/* PRICING group */}
                  <th colSpan={9} style={{
                    top: 0, position: "sticky", zIndex: 1,
                    background: "#eff6ff", color: "#1e40af",
                    fontWeight: 800, fontSize: 10, letterSpacing: "0.08em", textTransform: "uppercase",
                    textAlign: "center", padding: "4px 8px",
                    borderBottom: "2px solid #bfdbfe",
                    borderLeft: "2px solid #bfdbfe", borderRight: "2px solid #bfdbfe",
                    height: GRP_H,
                  }}>
                    Pricing ({currency})
                  </th>
                  {/* TOP 10% group */}
                  <th colSpan={10} style={{
                    top: 0, position: "sticky", zIndex: 1,
                    background: "#f0fdf4", color: "#166534",
                    fontWeight: 800, fontSize: 10, letterSpacing: "0.08em", textTransform: "uppercase",
                    textAlign: "center", padding: "4px 8px",
                    borderBottom: "2px solid #bbf7d0",
                    borderLeft: "2px solid #bbf7d0", borderRight: "2px solid #bbf7d0",
                    height: GRP_H,
                  }}>
                    Top 10%
                  </th>
                  {/* 1ST PAGE% group */}
                  <th colSpan={10} style={{
                    top: 0, position: "sticky", zIndex: 1,
                    background: "#fdf4ff", color: "#7e22ce",
                    fontWeight: 800, fontSize: 10, letterSpacing: "0.08em", textTransform: "uppercase",
                    textAlign: "center", padding: "4px 8px",
                    borderBottom: "2px solid #e9d5ff",
                    borderLeft: "2px solid #e9d5ff",
                    height: GRP_H,
                  }}>
                    1st Page%
                  </th>
                </tr>

                {/* ── Row 2: column labels ── */}
                <tr style={{ background: "#f8fafc" }}>
                  {(["Segment","Brand","Type","Size","PK","Sub"] as const).map((label, i) => (
                    <th key={label} ref={(el) => { fixedHeaderRefs.current[i] = el; }} style={{
                      padding: "7px 10px", textAlign: "left",
                      color: "#64748b", fontWeight: 700, fontSize: 10, letterSpacing: "0.06em", textTransform: "uppercase",
                      borderBottom: "2px solid #e2e8f0",
                      borderRight: i === FIXED_COUNT - 1 ? "2px solid #cbd5e1" : "1px solid #e2e8f0",
                      top: GRP_H, position: "sticky", zIndex: 9,
                      ...stickyCol(i, "#f8fafc", dynLefts, 9),
                    }}>{label}</th>
                  ))}
                  {/* Pricing W1-W9 */}
                  {Array.from({ length: 9 }, (_, i) => (
                    <th key={`pw${i}`} style={{
                      ...CELL, padding: "7px 8px",
                      color: "#1e40af", fontWeight: 700, fontSize: 10, letterSpacing: "0.05em", textTransform: "uppercase",
                      borderBottom: "2px solid #e2e8f0",
                      borderLeft: i === 0 ? "2px solid #bfdbfe" : undefined,
                      borderRight: i === 8 ? "2px solid #bfdbfe" : undefined,
                      top: GRP_H, position: "sticky", zIndex: 1, background: "#f8fafc",
                      minWidth: WEEK_W, width: WEEK_W,
                    }}>
                      <div>W{i + 1}</div>
                      {weeks[i] && <div style={{ fontSize: 9, fontWeight: 500, color: "#94a3b8", marginTop: 1 }}>{fmtWeek(weeks[i])}</div>}
                    </th>
                  ))}
                  {/* Top10 W1-W9 */}
                  {Array.from({ length: 9 }, (_, i) => (
                    <th key={`t${i}`} style={{
                      ...CELL, padding: "7px 8px",
                      color: "#166534", fontWeight: 700, fontSize: 10, letterSpacing: "0.05em", textTransform: "uppercase",
                      borderBottom: "2px solid #e2e8f0",
                      borderLeft: i === 0 ? "2px solid #bbf7d0" : undefined,
                      borderRight: i === 8 ? "2px solid #bbf7d0" : undefined,
                      top: GRP_H, position: "sticky", zIndex: 1, background: "#f8fafc",
                      minWidth: WEEK_W, width: WEEK_W,
                    }}>
                      <div>W{i + 1}</div>
                      {weeks[i] && <div style={{ fontSize: 9, fontWeight: 500, color: "#94a3b8", marginTop: 1 }}>{fmtWeek(weeks[i])}</div>}
                    </th>
                  ))}
                  {/* 1st Page W1-W9 */}
                  {Array.from({ length: 9 }, (_, i) => (
                    <th key={`fp${i}`} style={{
                      ...CELL, padding: "7px 8px",
                      color: "#7e22ce", fontWeight: 700, fontSize: 10, letterSpacing: "0.05em", textTransform: "uppercase",
                      borderBottom: "2px solid #e2e8f0",
                      borderLeft: i === 0 ? "2px solid #e9d5ff" : undefined,
                      top: GRP_H, position: "sticky", zIndex: 1, background: "#f8fafc",
                      minWidth: WEEK_W, width: WEEK_W,
                    }}>
                      <div>W{i + 1}</div>
                      {weeks[i] && <div style={{ fontSize: 9, fontWeight: 500, color: "#94a3b8", marginTop: 1 }}>{fmtWeek(weeks[i])}</div>}
                    </th>
                  ))}
                </tr>
              </thead>

              <tbody>
                {loading ? (
                  Array.from({ length: 14 }).map((_, i) => (
                    <tr key={i} style={{ borderBottom: "1px solid #f1f5f9" }}>
                      {Array.from({ length: TOTAL_COLS }).map((_, j) => (
                        <td key={j} style={{ padding: "2px 6px" }}>
                          <div style={{ height: 11, borderRadius: 3, width: j < FIXED_COUNT ? "75%" : "55%", background: "linear-gradient(90deg,#e2e8f0 25%,#f1f5f9 50%,#e2e8f0 75%)", backgroundSize: "200% 100%", animation: "hskut-shimmer 1.4s infinite" }} />
                        </td>
                      ))}
                    </tr>
                  ))
                ) : !trendData || trendData.sections.length === 0 ? (
                  <tr><td colSpan={TOTAL_COLS} style={{ padding: 56, textAlign: "center", color: "#94a3b8" }}>No data available</td></tr>
                ) : (
                  trendData.sections.map((section) => {
                    const scfg = SECTION_CFG[section.section] ?? FALLBACK_SECTION;

                    // Filter by segment then group by brand
                    const filtered = section.rows
                      .filter((r) => !selectedSegment || r.segment.toLowerCase() === selectedSegment.toLowerCase())
                      .sort((a, b) => {
                        const ai = SEGMENT_ORDER.indexOf(a.segment.toLowerCase());
                        const bi = SEGMENT_ORDER.indexOf(b.segment.toLowerCase());
                        return (ai === -1 ? 99 : ai) - (bi === -1 ? 99 : bi);
                      });
                    const groups: TrendRow[][] = [];
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
                          <td colSpan={TOTAL_COLS} style={{
                            padding: "4px 16px",
                            background: scfg.bg,
                            borderTop: `2px solid ${scfg.border}`,
                            borderBottom: `2px solid ${scfg.border}`,
                            ...sectionBgStyle(scfg),
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
                                const isFirst       = ri === 0;
                                const isLastInGroup = ri === group.length - 1;
                                const seg           = segColor(row.segment);
                                const rowBg         = "white";

                                return (
                                  <tr key={`${row.brand}-${row.sku_label}-${ri}`} className="hskut-row"
                                    style={{ borderBottom: isLastInGroup && !isLastGroup ? "2px solid #e2e8f0" : "1px solid #f1f5f9", background: rowBg }}>

                                    {/* Segment */}
                                    <td style={{ padding: "2px 6px", borderRight: "1px solid #f0f0f0", ...stickyCol(0, rowBg, dynLefts) }}>
                                      {isFirst ? (
                                        <span style={{ display: "inline-flex", alignItems: "center", gap: 4, padding: "1px 6px", borderRadius: 99, fontSize: 10, fontWeight: 700, background: seg.bg, color: seg.text }}>
                                          <span style={{ width: 5, height: 5, borderRadius: "50%", background: seg.dot, display: "inline-block", flexShrink: 0 }} />
                                          {row.segment}
                                        </span>
                                      ) : null}
                                    </td>
                                    {/* Brand */}
                                    <td style={{ padding: "2px 6px", fontWeight: isFirst ? 700 : 400, color: isFirst ? "#0f172a" : "transparent", borderRight: "1px solid #f0f0f0", ...stickyCol(1, rowBg, dynLefts) }}>
                                      {isFirst ? row.brand_display : ""}
                                    </td>
                                    {/* Type */}
                                    <td style={{ padding: "2px 6px", color: "#475569", borderRight: "1px solid #f0f0f0", ...stickyCol(2, rowBg, dynLefts) }}>
                                      {row.pack_type}
                                    </td>
                                    {/* Size */}
                                    <td style={{ padding: "2px 6px", color: "#3b82f6", fontWeight: 600, borderRight: "1px solid #f0f0f0", ...stickyCol(3, rowBg, dynLefts) }}>
                                      {row.pack_size}
                                    </td>
                                    {/* PK */}
                                    <td style={{ padding: "2px 6px", color: "#475569", textAlign: "center", borderRight: "1px solid #f0f0f0", ...stickyCol(4, rowBg, dynLefts) }}>
                                      {row.pack}
                                    </td>
                                    {/* Sub */}
                                    <td style={{ padding: "2px 6px", color: "#475569", borderRight: "2px solid #cbd5e1", ...stickyCol(5, rowBg, dynLefts) }}>
                                      {row.sub_type ? row.sub_type.charAt(0).toUpperCase() + row.sub_type.slice(1) : "—"}
                                    </td>

                                    {/* Pricing W1–W9 (value + delta stacked) */}
                                    {Array.from({ length: 9 }, (_, i) => (
                                      <td key={`p${i}`} style={{ ...CELL, ...(i === 0 ? { borderLeft: "2px solid #bfdbfe" } : {}), ...(i === 8 ? { borderRight: "2px solid #bfdbfe" } : {}) }}>
                                        <WeekVal v={row.pricing?.[i]} />
                                        <InlineDelta v={row.pricing_deltas?.[i]} type="pct" />
                                      </td>
                                    ))}

                                    {/* Top10 W1–W9 (value + delta stacked) */}
                                    {Array.from({ length: 9 }, (_, i) => (
                                      <td key={`t${i}`} style={{ ...CELL, ...(i === 0 ? { borderLeft: "2px solid #bbf7d0" } : {}), ...(i === 8 ? { borderRight: "2px solid #bbf7d0" } : {}) }}>
                                        <WeekPct v={row.top10_pct?.[i]} />
                                        <InlineDelta v={row.top10_deltas?.[i]} type="pt" />
                                      </td>
                                    ))}

                                    {/* 1st Page W1–W9 (value + delta stacked) */}
                                    {Array.from({ length: 9 }, (_, i) => (
                                      <td key={`fp${i}`} style={{ ...CELL, ...(i === 0 ? { borderLeft: "2px solid #e9d5ff" } : {}) }}>
                                        <WeekPct v={row.first_page_pct?.[i]} />
                                        <InlineDelta v={row.first_page_deltas?.[i]} type="pt" />
                                      </td>
                                    ))}
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
