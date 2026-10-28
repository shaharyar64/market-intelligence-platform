"use client";

import { useEffect, useState, useRef, useCallback } from "react";
import DashboardTopbar from "@/components/layout/DashboardTopbar";
import {
  getFilters,
  getRetailers,
  getExport,
} from "@/lib/pricingAnalysis";
import FilterSelect from "@/components/filters/FilterSelect";
import FilterMultiSelect from "@/components/filters/FilterMultiSelect";
import * as XLSX from "xlsx";

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
  dates: string[];
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
  date?: string;
}

interface PricingRow {
  date: string | null;
  market: string | null;
  region: string | null;
  retailer: string | null;
  segment: string | null;
  sub_type: string | null;
  comp: string | null;
  brand: string | null;
  type: string | null;
  quantity: string | null;
  units: number | null;
  pack_format: string | null;
  original_price_local: number | null;
  original_price_usd: number | null;
  discounted_price_local: number | null;
  discounted_price_usd: number | null;
  currency: string | null;
  discount_percentage: number | null;
  availability: string | null;
  features_in_top10: string | null;
  features_on_first_page: string | null;
  link: string | null;
  image_link: string | null;
}

const DEFAULT_SELECTED_FILTERS: SelectedFilters = {
  markets: [],
  cities: [],
  retailers: [],
  subTypes: [],
  comp: [],
  brands: [],
  date: undefined,
  types: [],
  quantity: [],
  skus: [],
  local: false,
};

const FILTERS_STORAGE_KEY = "pricing_explore_filters";

const loadStoredFilters = (): SelectedFilters => {
  if (typeof window === "undefined") return DEFAULT_SELECTED_FILTERS;
  try {
    const stored = localStorage.getItem(FILTERS_STORAGE_KEY);
    return stored ? { ...DEFAULT_SELECTED_FILTERS, ...JSON.parse(stored) } : DEFAULT_SELECTED_FILTERS;
  } catch {
    return DEFAULT_SELECTED_FILTERS;
  }
};

/* =========================
   TABLE CONSTANTS
========================= */

const PER_PAGE = 50;

const COLUMNS: { key: string; label: string; minWidth?: number }[] = [
  { key: "image",                  label: "Image",           minWidth: 64  },
  { key: "date",                   label: "Date",            minWidth: 110 },
  { key: "market",                 label: "Market",          minWidth: 90  },
  { key: "region",                 label: "Region",          minWidth: 110 },
  { key: "retailer",               label: "Retailer",        minWidth: 110 },
  { key: "segment",                label: "Segment",         minWidth: 150 },
  { key: "sub_type",               label: "Sub Type",        minWidth: 110 },
  { key: "brand",                  label: "Brand",           minWidth: 110 },
  { key: "type",                   label: "Type",            minWidth: 80  },
  { key: "quantity",               label: "Quantity",        minWidth: 90  },
  { key: "units",                  label: "Units",           minWidth: 70  },
  { key: "pack_format",            label: "Pack Format",     minWidth: 110 },
  { key: "original_price_local",   label: "Orig. (Local)",   minWidth: 110 },
  { key: "original_price_usd",     label: "Orig. (USD)",     minWidth: 100 },
  { key: "discounted_price_local", label: "Disc. (Local)",   minWidth: 110 },
  { key: "discounted_price_usd",   label: "Disc. (USD)",     minWidth: 100 },
  { key: "currency",               label: "Currency",        minWidth: 85  },
  { key: "discount_percentage",    label: "Discount %",      minWidth: 95  },
  { key: "availability",           label: "Availability",    minWidth: 100 },
  { key: "features_in_top10",      label: "Top 10",          minWidth: 100 },
  { key: "features_on_first_page", label: "First Page",      minWidth: 100 },
  { key: "action",                 label: "Link",            minWidth: 80  },
];

const TABLE_MIN_WIDTH = COLUMNS.reduce((sum, col) => sum + (col.minWidth ?? 100), 0);

/* =========================
   TABLE SUB-COMPONENTS
========================= */

function StatusBadge({ value }: { value: string | null }) {
  if (!value || value === "null") {
    return <span style={{ color: "var(--ptbl-muted-text)", fontStyle: "italic" }}>—</span>;
  }
  const v = value.toLowerCase();
  const styles: React.CSSProperties =
    v === "yes"
      ? { background: "rgba(34, 197, 94, 0.14)", color: "#16a34a", border: "1px solid rgba(34, 197, 94, 0.22)" }
      : v === "no"
      ? { background: "rgba(239, 68, 68, 0.12)", color: "#dc2626", border: "1px solid rgba(239, 68, 68, 0.18)" }
      : { background: "var(--ptbl-chip-neutral-bg)", color: "var(--ptbl-muted-text)", border: "1px solid var(--ptbl-chip-neutral-border)" };
  return (
    <span style={{ display: "inline-block", padding: "2px 9px", borderRadius: 99, fontSize: 11, fontWeight: 600, letterSpacing: "0.02em", ...styles }}>
      {value}
    </span>
  );
}

function SkeletonRows() {
  return (
    <>
      {Array.from({ length: 8 }).map((_, i) => (
        <tr key={i} style={{ borderBottom: "1px solid var(--ptbl-table-border)" }}>
          {COLUMNS.map((col) => (
            <td key={col.key} style={{ padding: "9px 14px", verticalAlign: "middle" }}>
              <div
                style={{
                  width: col.key === "image" ? 40 : "70%",
                  height: col.key === "image" ? 40 : 14,
                  borderRadius: 4,
                  background: "linear-gradient(90deg, var(--ptbl-skeleton-base) 25%, var(--ptbl-skeleton-highlight) 50%, var(--ptbl-skeleton-base) 75%)",
                  backgroundSize: "200% 100%",
                  animation: "ptbl-shimmer 1.4s infinite",
                }}
              />
            </td>
          ))}
        </tr>
      ))}
    </>
  );
}

/* =========================
   PAGE
========================= */

export default function PricingAnalysisSegmentDeepDive() {

  const [filters, setFilters]     = useState<FiltersResponse | null>(null);
  const [retailers, setRetailers] = useState<string[]>([]);
  const [rows, setRows]           = useState<PricingRow[]>([]);
  const [total, setTotal]         = useState(0);
  const [page, setPage]           = useState(0);
  const [loading, setLoading]     = useState(true);
  const [exporting, setExporting] = useState(false);
  const [exportProgress, setExportProgress] = useState({ fetched: 0, total: 0 });

  // Tracks the latest fetch so stale responses from rapid filter changes are discarded
  const fetchIdRef = useRef(0);
  const topScrollRef = useRef<HTMLDivElement | null>(null);
  const tableScrollRef = useRef<HTMLDivElement | null>(null);
  const syncingScrollRef = useRef(false);
  const [scrollContentWidth, setScrollContentWidth] = useState(TABLE_MIN_WIDTH);

  const [selectedFilters, setSelectedFilters] = useState<SelectedFilters>(loadStoredFilters);
  const [draftSelectedFilters, setDraftSelectedFilters] = useState<SelectedFilters>(loadStoredFilters);

  const syncHorizontalScroll = (source: "top" | "table") => {
    if (syncingScrollRef.current) return;
    const from = source === "top" ? topScrollRef.current : tableScrollRef.current;
    const to = source === "top" ? tableScrollRef.current : topScrollRef.current;
    if (!from || !to) return;

    syncingScrollRef.current = true;
    to.scrollLeft = from.scrollLeft;
    requestAnimationFrame(() => {
      syncingScrollRef.current = false;
    });
  };

  useEffect(() => {
    const updateScrollWidth = () => {
      const nextWidth = Math.max(TABLE_MIN_WIDTH, tableScrollRef.current?.scrollWidth ?? 0);
      setScrollContentWidth(nextWidth);
    };

    updateScrollWidth();
    const resizeObserver = typeof ResizeObserver !== "undefined" ? new ResizeObserver(updateScrollWidth) : null;
    if (tableScrollRef.current) resizeObserver?.observe(tableScrollRef.current);
    window.addEventListener("resize", updateScrollWidth);

    return () => {
      resizeObserver?.disconnect();
      window.removeEventListener("resize", updateScrollWidth);
    };
  }, [rows.length, loading]);

  /* =========================
     API CALLS
  ========================= */

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

  // Fetches only PER_PAGE rows for the current page — fast
  const fetchPage = useCallback(async (
    currentFilters: SelectedFilters,
    currentPage: number
  ) => {
    const fetchId = ++fetchIdRef.current;
    setLoading(true);
    try {
      const res = await getExport(currentFilters, currentPage + 1, PER_PAGE);
      if (!res.ok) throw new Error("Failed to fetch");
      const json = await res.json();

      // Discard if a newer fetch has started
      if (fetchId !== fetchIdRef.current) return;

      if (Array.isArray(json)) {
        // plain array fallback
        setRows(json);
        setTotal(json.length < PER_PAGE ? currentPage * PER_PAGE + json.length : -1);
      } else {
        // { data: { rows, total_count, page, limit }, success }
        const inner = json.data ?? json;
        const data: PricingRow[] = inner.rows ?? inner.data ?? inner.items ?? inner.results ?? [];
        const knownTotal: number | null = inner.total_count ?? inner.total ?? inner.count ?? null;
        setRows(data);
        setTotal(knownTotal !== null ? knownTotal : (
          data.length < PER_PAGE
            ? currentPage * PER_PAGE + data.length
            : (currentPage + 1) * PER_PAGE + 1
        ));
      }
    } catch {
      if (fetchId === fetchIdRef.current) {
        setRows([]);
        setTotal(0);
      }
    } finally {
      if (fetchId === fetchIdRef.current) setLoading(false);
    }
  }, []);

  // When filters change — reset to page 0 and fetch
  useEffect(() => {
    setPage(0);
    fetchPage(selectedFilters, 0);
  // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [selectedFilters]);

  // Persist applied filters so they survive page reloads/navigation
  useEffect(() => {
    try {
      localStorage.setItem(FILTERS_STORAGE_KEY, JSON.stringify(selectedFilters));
    } catch {}
  }, [selectedFilters]);

  // When page changes — fetch new page
  useEffect(() => {
    fetchPage(selectedFilters, page);
  // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [page]);

  /* =========================
     HANDLERS
  ========================= */

  const handleChange = (key: keyof SelectedFilters, value: string) => {
    setDraftSelectedFilters((prev) => {
      const updated = { ...prev, [key]: value ? [value] : [] } as SelectedFilters;

      // Cascading reset
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

  const resetFilters = () => {
    setDraftSelectedFilters(DEFAULT_SELECTED_FILTERS);
    setSelectedFilters(DEFAULT_SELECTED_FILTERS);
    try {
      localStorage.removeItem(FILTERS_STORAGE_KEY);
    } catch {}
  };

  const applyFilters = () => {
    setLoading(true);
    setSelectedFilters({ ...draftSelectedFilters });
  };

  const toTitleCase = (str: string) =>
    str.replace(/\w\S*/g, (w) => w.charAt(0).toUpperCase() + w.slice(1).toLowerCase());

  const buildOptions = (items: string[], label: string, titleCase = false) => [
    { label, value: "" },
    ...items.map((item) => ({ label: titleCase ? toTitleCase(item) : item, value: item })),
  ];

  /* =========================
     TABLE LOGIC
  ========================= */

  const totalPages = Math.max(1, Math.ceil(total / PER_PAGE));
  // We know it's the last page when the API returned fewer rows than requested
  const isLastPage = rows.length < PER_PAGE;

  const goPage = (p: number) => {
    if (p < 0 || p === page) return;
    if (isLastPage && p > page) return; // can't go past last page
    setPage(p);
  };

  const EXPORT_BATCH = 50;
  const PARALLEL = 10; // concurrent requests at a time

  const handleExport = async () => {
    setExporting(true);
    setExportProgress({ fetched: 0, total: 0 });
    try {
      // ── Step 1: fetch page 1 to get first batch + detect if there's more ──
      const firstRes = await getExport(selectedFilters, 1, EXPORT_BATCH);
      if (!firstRes.ok) throw new Error("Export failed");
      const firstJson = await firstRes.json();
      const firstRows: PricingRow[] = Array.isArray(firstJson)
        ? firstJson
        : (firstJson.data?.rows ?? firstJson.data ?? []);

      // Grab total_count from first response for accurate progress bar
      const knownTotal: number = firstJson.data?.total_count ?? firstJson.total_count ?? 0;

      // If first page already has fewer rows than batch, we're done
      if (firstRows.length < EXPORT_BATCH) {
        writeExcel(firstRows);
        return;
      }

      const allRows: PricingRow[] = [...firstRows];

      // Use total_count from API for accurate progress — fall back to table total or estimate
      const estimatedTotal = knownTotal > 0 ? knownTotal : total > 0 ? total : EXPORT_BATCH * 20;
      setExportProgress({ fetched: allRows.length, total: estimatedTotal });

      let nextPage = 2;
      let done = false;

      // ── Step 2: fetch PARALLEL pages at a time until exhausted ──
      while (!done) {
        const pages = Array.from({ length: PARALLEL }, (_, i) => nextPage + i);
        nextPage += PARALLEL;

        const results = await Promise.all(
          pages.map((p) =>
            getExport(selectedFilters, p, EXPORT_BATCH)
              .then((r) => r.json())
              .then((json) => {
                if (Array.isArray(json)) return json as PricingRow[];
                return (json.data?.rows ?? json.data ?? []) as PricingRow[];
              })
              .catch(() => [] as PricingRow[])
          )
        );

        for (const pageRows of results) {
          allRows.push(...pageRows);
          if (pageRows.length < EXPORT_BATCH) {
            done = true;
            break;
          }
        }

        // Update progress with actual fetched vs known estimated total
        setExportProgress({ fetched: allRows.length, total: estimatedTotal });
      }

      // Final — set fetched = total so bar completes to 100%
      setExportProgress({ fetched: estimatedTotal, total: estimatedTotal });

      writeExcel(allRows);
    } catch (err) {
      console.error("Export failed:", err);
    } finally {
      setExporting(false);
      setExportProgress({ fetched: 0, total: 0 });
    }
  };

  const writeExcel = (allRows: PricingRow[]) => {
    const exportCols = COLUMNS.filter((c) => c.key !== "image");
    const wsData = [
      exportCols.map((c) => c.label),
      ...allRows.map((row) =>
        exportCols.map((c) => (c.key === "action" ? row.link : row[c.key as keyof PricingRow]) ?? "")
      ),
    ];
    const ws = XLSX.utils.aoa_to_sheet(wsData);
    ws["!cols"] = exportCols.map(() => ({ wch: 18 }));
    const wb = XLSX.utils.book_new();
    XLSX.utils.book_append_sheet(wb, ws, "Pricing Analysis");
    XLSX.writeFile(wb, "pricing_analysis.xlsx");
  };

  const renderCell = (colKey: string, row: PricingRow) => {
    if (colKey === "image") {
      return row.image_link ? (
        // eslint-disable-next-line @next/next/no-img-element
        <img
          src={row.image_link}
          alt={row.brand ?? "product"}
          style={{ width: 40, height: 40, objectFit: "contain", borderRadius: 8, border: "1px solid var(--ptbl-image-border)", background: "var(--ptbl-image-bg)", display: "block" }}
          onError={(e) => { (e.currentTarget as HTMLImageElement).style.display = "none"; }}
        />
      ) : (
        <div style={{ width: 40, height: 40, borderRadius: 8, background: "var(--ptbl-image-bg)", border: "1px solid var(--ptbl-image-border)" }} />
      );
    }

    if (colKey === "action") {
      return row.link ? (
        <a
          href={row.link}
          target="_blank"
          rel="noopener noreferrer"
          className="ptbl-view-btn"
          style={{ display: "inline-block", padding: "4px 10px", borderRadius: 7, border: "1px solid var(--ptbl-action-border)", color: "var(--ptbl-action-text)", fontSize: 11, fontWeight: 600, textDecoration: "none", transition: "background 0.12s, color 0.12s, border-color 0.12s" }}
        >
          View ↗
        </a>
      ) : (
        <span style={{ color: "var(--ptbl-muted-text)", fontStyle: "italic" }}>—</span>
      );
    }

    const val = row[colKey as keyof PricingRow];

    if (colKey === "availability" || colKey === "features_in_top10" || colKey === "features_on_first_page") {
      return <StatusBadge value={val as string | null} />;
    }
    if (colKey === "discount_percentage") {
      return val != null
        ? <span>{(val as number).toFixed(1)}%</span>
        : <span style={{ color: "var(--ptbl-muted-text)", fontStyle: "italic" }}>—</span>;
    }
    if (["original_price_local", "original_price_usd", "discounted_price_local", "discounted_price_usd"].includes(colKey)) {
      return val != null
        ? <span>{(val as number).toLocaleString(undefined, { minimumFractionDigits: 0, maximumFractionDigits: 2 })}</span>
        : <span style={{ color: "var(--ptbl-muted-text)", fontStyle: "italic" }}>—</span>;
    }
    if (val == null || val === "") return <span style={{ color: "var(--ptbl-muted-text)", fontStyle: "italic" }}>—</span>;
    return <span>{String(val)}</span>;
  };

  /* =========================
     UI
  ========================= */

  return (
    <div className="ptbl-theme w-full bg-transparent" style={{ minHeight: "100%" }}>
      <DashboardTopbar title="Beer & Cider Pricing Analysis" />
      <style>{`
        .ptbl-theme {
          --ptbl-scrollbar-track: rgba(148, 163, 184, 0.12);
          --ptbl-scrollbar-thumb: rgba(100, 116, 139, 0.5);
          --ptbl-row-hover: rgba(59, 130, 246, 0.08);
          --ptbl-table-border: rgba(148, 163, 184, 0.26);
          --ptbl-header-bg: #0f172a;
          --ptbl-header-text: #94a3b8;
          --ptbl-cell-text: var(--body-tx);
          --ptbl-muted-text: var(--muted-tx);
          --ptbl-chip-neutral-bg: rgba(148, 163, 184, 0.12);
          --ptbl-chip-neutral-border: rgba(148, 163, 184, 0.24);
          --ptbl-action-border: rgba(100, 116, 139, 0.32);
          --ptbl-action-text: var(--body-tx);
          --ptbl-action-hover-bg: rgba(148, 163, 184, 0.12);
          --ptbl-action-hover-text: var(--title-tx);
          --ptbl-pagination-border: rgba(100, 116, 139, 0.32);
          --ptbl-pagination-hover-bg: rgba(148, 163, 184, 0.12);
          --ptbl-export-bg: rgba(34, 197, 94, 0.12);
          --ptbl-export-border: rgba(34, 197, 94, 0.2);
          --ptbl-export-text: #16a34a;
          --ptbl-progress-track: rgba(148, 163, 184, 0.18);
          --ptbl-image-bg: rgba(255, 255, 255, 0.84);
          --ptbl-image-border: rgba(148, 163, 184, 0.35);
          --ptbl-skeleton-base: rgba(148, 163, 184, 0.14);
          --ptbl-skeleton-highlight: rgba(148, 163, 184, 0.24);
        }
        .dark .ptbl-theme {
          --ptbl-scrollbar-track: #0f172a;
          --ptbl-scrollbar-thumb: #334155;
          --ptbl-row-hover: #0f1f35;
          --ptbl-table-border: #1e293b;
          --ptbl-header-bg: #0d1525;
          --ptbl-header-text: #64748b;
          --ptbl-cell-text: #cbd5e1;
          --ptbl-muted-text: #64748b;
          --ptbl-chip-neutral-bg: #1e293b;
          --ptbl-chip-neutral-border: #334155;
          --ptbl-action-border: #334155;
          --ptbl-action-text: #94a3b8;
          --ptbl-action-hover-bg: #1e293b;
          --ptbl-action-hover-text: #e2e8f0;
          --ptbl-pagination-border: #1e293b;
          --ptbl-pagination-hover-bg: #1e293b;
          --ptbl-export-bg: #22c55e14;
          --ptbl-export-border: #4ade8030;
          --ptbl-export-text: #4ade80;
          --ptbl-progress-track: #1e293b;
          --ptbl-image-bg: #0d1525;
          --ptbl-image-border: #1e293b;
          --ptbl-skeleton-base: #1e293b;
          --ptbl-skeleton-highlight: #263548;
        }
        @keyframes ptbl-shimmer {
          0%   { background-position: 200% 0; }
          100% { background-position: -200% 0; }
        }
        .ptbl-scroll::-webkit-scrollbar { height: 6px; }
        .ptbl-scroll::-webkit-scrollbar-track { background: var(--ptbl-scrollbar-track); }
        .ptbl-scroll::-webkit-scrollbar-thumb { background: var(--ptbl-scrollbar-thumb); border-radius: 3px; }
        .ptbl-table-scroll { scrollbar-width: none; }
        .ptbl-table-scroll::-webkit-scrollbar { height: 0; }
        .ptbl-tr:hover { background: var(--ptbl-row-hover) !important; }
        .ptbl-view-btn:hover { background: var(--ptbl-action-hover-bg) !important; color: var(--ptbl-action-hover-text) !important; border-color: var(--ptbl-action-border) !important; }
        .ptbl-pag-btn:hover:not(:disabled) { background: var(--ptbl-pagination-hover-bg); color: var(--title-tx); border-color: var(--ptbl-pagination-border); }
        .ptbl-export-btn:hover:not(:disabled) { background: rgba(34, 197, 94, 0.18) !important; border-color: rgba(34, 197, 94, 0.28) !important; }
        @keyframes ptbl-spin { to { transform: rotate(360deg); } }
      `}</style>


      <div className="p-8">


        {/* ── Filter Panel ── */}
        <div className="pricing-compact-filters pricing-standard-filters rounded-2xl bg-[var(--card-bg)] p-4 shadow-xl border border-[var(--card-bd)] mb-8 flex items-end gap-3 flex-wrap">
          {filters && (
            <>
              <FilterSelect label="Market"      value={draftSelectedFilters.markets[0] || ""}          onChange={(val) => handleChange("markets", val)}    options={buildOptions(filters.markets, "All Markets")} />
              <FilterSelect label="City"        value={draftSelectedFilters.cities[0] || ""}           onChange={(val) => handleChange("cities", val)}     options={buildOptions(filters.cities ?? [], "All Cities")} />
              <FilterSelect label="Retailer"    value={draftSelectedFilters.retailers[0] || ""}        onChange={(val) => handleChange("retailers", val)}  options={buildOptions((filters?.["all-retailers"] && filters["all-retailers"].length > 0) ? filters["all-retailers"] : retailers, "All Retailers", true)} />
              <FilterMultiSelect label="Brand"  values={draftSelectedFilters.brands}                   onChange={(values) => setDraftSelectedFilters((prev) => ({ ...prev, brands: values, comp: [] }))} options={buildOptions(filters.brands, "All Brands")} allLabel="All Brands" />
              <FilterSelect label="Sub Type"    value={draftSelectedFilters.subTypes[0] || ""}         onChange={(val) => handleChange("subTypes", val)}   options={buildOptions(filters.sub_types ?? [], "All Sub Types")} />
              <FilterSelect label="Competition" value={draftSelectedFilters.comp[0] || ""}             onChange={(val) => handleChange("comp", val)}       options={buildOptions(filters.comp, "All Competition")} />
              <FilterSelect label="Type"        value={draftSelectedFilters.types[0] || ""}            onChange={(val) => handleChange("types", val)}      options={buildOptions(filters.types, "All Types")} />
              <FilterSelect label="Quantity"    value={draftSelectedFilters.quantity[0] || ""}         onChange={(val) => handleChange("quantity", val)}   options={buildOptions(filters.quantity, "All Quantities")} />
              <FilterSelect label="SKU"         value={draftSelectedFilters.skus[0]?.toString() || ""} onChange={(val) => handleChange("skus", val)}       options={buildOptions(filters.skus.map(String), "All SKUs")} />
              <FilterSelect
                label="Historic Date"
                value={draftSelectedFilters.date ?? ""}
                onChange={(val) => setDraftSelectedFilters((prev) => ({ ...prev, date: val || undefined }))}
                options={[
                  { label: "All Dates", value: "" },
                  ...(filters.dates ?? []).map((d) => ({
                    label: new Date(d).toLocaleDateString("en-GB", { day: "2-digit", month: "short", year: "numeric" }),
                    value: d,
                  })),
                ]}
              />
              <div className="pricing-filter-row-break" aria-hidden="true" />
              <div className="pricing-filter-actions">
                <button
                  onClick={resetFilters}
                  className="transition"
                  style={{ height: 42, padding: "0 14px", fontSize: 13, borderRadius: 12, background: "var(--card-bg-2)", color: "var(--muted-tx)", border: "1px solid var(--card-bd)" }}
                >Reset</button>
                <button
                  onClick={applyFilters}
                  disabled={loading}
                  className="bg-blue-600 text-white border border-blue-600 transition hover:bg-blue-700 disabled:opacity-60 disabled:cursor-not-allowed pricing-apply-button"
                  style={{ height: 42, minWidth: 84, padding: "0 18px", fontSize: 13, fontWeight: 700, borderRadius: 12, boxShadow: "0 1px 8px rgba(15, 23, 42, 0.08)" }}
                >
                  Apply
                </button>
              </div>
            </>
          )}
        </div>

        {/* ── Data Table Panel ── */}
        <div className="rounded-2xl bg-[var(--card-bg)] p-6 shadow-xl border border-[var(--card-bd)]">

          {/* Toolbar */}
          <div style={{ display: "flex", alignItems: "center", justifyContent: "space-between", marginBottom: 14 }}>
            <span style={{ fontSize: 13, color: "var(--ptbl-muted-text)" }}>
              {loading ? "Loading…" : `${total.toLocaleString()} rows`}
            </span>
            {/* Export button + progress */}
            <div style={{ display: "flex", flexDirection: "column", alignItems: "flex-end", gap: 6 }}>
              <button
                className="ptbl-export-btn"
                onClick={handleExport}
                disabled={exporting || total === 0}
                style={{ display: "inline-flex", alignItems: "center", gap: 6, padding: "7px 16px", background: "var(--ptbl-export-bg)", color: "var(--ptbl-export-text)", border: "1px solid var(--ptbl-export-border)", borderRadius: 10, fontSize: 12, fontWeight: 600, cursor: exporting ? "not-allowed" : "pointer", letterSpacing: "0.02em", transition: "background 0.15s, border-color 0.15s", opacity: exporting || total === 0 ? 0.7 : 1 }}
              >
                {exporting ? (
                  <>
                    <svg width="13" height="13" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" style={{ animation: "ptbl-spin 1s linear infinite" }}>
                      <path d="M21 12a9 9 0 1 1-6.219-8.56" />
                    </svg>
                    Fetching {exportProgress.fetched} rows…
                  </>
                ) : (
                  <>
                    <svg width="13" height="13" viewBox="0 0 16 16" fill="currentColor">
                      <path d="M2 14h12v-1.5H2V14zm10-8H9V2H7v4H4l4 4 4-4z" />
                    </svg>
                    Export Excel
                  </>
                )}
              </button>
              {exporting && (
                <div style={{ width: 200, height: 3, background: "var(--ptbl-progress-track)", borderRadius: 99, overflow: "hidden" }}>
                  <div style={{
                    height: "100%",
                    background: "#4ade80",
                    borderRadius: 99,
                    width: exportProgress.total > 0
                      ? `${Math.min((exportProgress.fetched / exportProgress.total) * 100, 100)}%`
                      : "5%",
                    transition: "width 0.4s ease",
                  }} />
                </div>
              )}
            </div>
          </div>

          {/* Horizontally scrollable table */}
          <div
            ref={topScrollRef}
            onScroll={() => syncHorizontalScroll("top")}
            className="ptbl-scroll"
            style={{ width: "100%", overflowX: "auto", overflowY: "hidden", height: 10, marginBottom: 6 }}
          >
            <div style={{ width: scrollContentWidth, height: 1 }} />
          </div>
          <div
            ref={tableScrollRef}
            onScroll={() => syncHorizontalScroll("table")}
            className="ptbl-scroll ptbl-table-scroll"
            style={{ width: "100%", overflowX: "auto", borderRadius: 14, border: "1px solid var(--ptbl-table-border)", background: "rgba(255,255,255,0.02)" }}
          >
            <table style={{ borderCollapse: "collapse", width: "100%", minWidth: TABLE_MIN_WIDTH, fontSize: 13, whiteSpace: "nowrap" }}>
              <thead>
                <tr>
                  {COLUMNS.map((col) => (
                    <th
                      key={col.key}
                      style={{ background: "var(--ptbl-header-bg)", color: "var(--ptbl-header-text)", fontWeight: 600, fontSize: 11, letterSpacing: "0.06em", textTransform: "uppercase", padding: "11px 14px", textAlign: "left", borderBottom: "1px solid var(--ptbl-table-border)", position: "sticky", top: 0, zIndex: 1, minWidth: col.minWidth }}
                    >
                      {col.label}
                    </th>
                  ))}
                </tr>
              </thead>
              <tbody>
                {loading ? (
                  <SkeletonRows />
                ) : rows.length === 0 ? (
                  <tr>
                    <td colSpan={COLUMNS.length} style={{ padding: 40, textAlign: "center", color: "var(--ptbl-muted-text)" }}>
                      No data available
                    </td>
                  </tr>
                ) : (
                  rows.map((row, i) => (
                    <tr key={i} className="ptbl-tr" style={{ borderBottom: "1px solid var(--ptbl-table-border)", transition: "background 0.1s" }}>
                      {COLUMNS.map((col) => (
                        <td key={col.key} style={{ padding: "9px 14px", color: "var(--ptbl-cell-text)", verticalAlign: "middle" }}>
                          {renderCell(col.key, row)}
                        </td>
                      ))}
                    </tr>
                  ))
                )}
              </tbody>
            </table>
          </div>

          {/* Pagination */}
          {!loading && (
            <div style={{ display: "flex", alignItems: "center", gap: 6, marginTop: 14, flexWrap: "wrap" }}>
              <span style={{ fontSize: 12, color: "var(--ptbl-muted-text)", marginRight: "auto" }}>
                {rows.length > 0
                  ? `Showing ${page * PER_PAGE + 1}–${page * PER_PAGE + rows.length}${total > 0 ? ` of ${total.toLocaleString()}` : ""}`
                  : "No results"}
              </span>

              <button
                className="ptbl-pag-btn"
                onClick={() => goPage(page - 1)}
                disabled={page === 0}
                style={{ minWidth: 30, height: 30, padding: "0 6px", display: "inline-flex", alignItems: "center", justifyContent: "center", borderRadius: 8, border: "1px solid var(--ptbl-pagination-border)", background: "transparent", cursor: page === 0 ? "not-allowed" : "pointer", fontSize: 13, color: "var(--ptbl-muted-text)", transition: "background 0.1s, border-color 0.1s", opacity: page === 0 ? 0.3 : 1 }}
              >
                ‹
              </button>

              <span style={{ fontSize: 12, color: "var(--ptbl-muted-text)", padding: "0 8px" }}>
                Page {page + 1}{isLastPage && total > 0 ? ` of ${totalPages}` : ""}
              </span>

              <button
                className="ptbl-pag-btn"
                onClick={() => goPage(page + 1)}
                disabled={isLastPage}
                style={{ minWidth: 30, height: 30, padding: "0 6px", display: "inline-flex", alignItems: "center", justifyContent: "center", borderRadius: 8, border: "1px solid var(--ptbl-pagination-border)", background: "transparent", cursor: isLastPage ? "not-allowed" : "pointer", fontSize: 13, color: "var(--ptbl-muted-text)", transition: "background 0.1s, border-color 0.1s", opacity: isLastPage ? 0.3 : 1 }}
              >
                ›
              </button>
            </div>
          )}

        </div>
      </div>
    </div>
  );
}
