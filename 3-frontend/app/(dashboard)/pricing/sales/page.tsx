"use client";

import React, { useEffect, useState } from "react";
import * as XLSX from "xlsx";
import DashboardTopbar from "@/components/layout/DashboardTopbar";
import { getBrandSales, getFilters, Filters } from "@/lib/pricingAnalysis";
import FilterSelect from "@/components/filters/FilterSelect";
import FilterSearchSelect from "@/components/filters/FilterSearchSelect";
import FilterMultiSelect from "@/components/filters/FilterMultiSelect";

/* =========================
   TYPES
========================= */

interface PricingData {
  regular_price: number | null;
  regular_price_diff_vs_previous_week: number | null;
  promo_price: number | null;
  promo_price_diff_vs_previous_week: number | null;
  promo_pct: number | null;
  promo_pct_diff_vs_previous_week: number | null;
  has_data?: boolean;
}

interface BrandRow {
  brand: string;
  pack_type: string;
  pack_size: string;
  pack: number;
  sub_type?: string | null;
  pricing_currency: string;
  retailers: Record<string, PricingData>;
  regions: Record<string, PricingData>;
  brand_group: string;
}

interface BrandSalesData {
  source_table: string;
  latest_data_point_used_date: string;
  previous_week_data_point_used_date: string;
  retailers: string[];
  regions: string[];
  rows: BrandRow[];
}

/* =========================
   CONFIG
========================= */

const REGION_HEADER_COLOR: Record<string, string> = {
  "Dubai": "#93c5fd",
  "Abu Dhabi": "#93c5fd",
  "Other Emirates": "#c4b5fd",
  "Bahrain": "#93c5fd",
};
const REGION_SUBHEADER_COLOR: Record<string, string> = {
  "Dubai": "#dbeafe",
  "Abu Dhabi": "#dbeafe",
  "Other Emirates": "#ede9fe",
  "Bahrain": "#dbeafe",
};
const REGION_LABEL: Record<string, string> = {
  "Dubai": "DUBAI",
  "Abu Dhabi": "ABU DHABI",
  "Other Emirates": "OTHER EMIRATES",
  "Bahrain": "BAHRAIN",
};
const RETAILER_HEADER_COLOR = "#86efac";
const RETAILER_SUBHEADER_COLOR = "#dcfce7";
const RETAILER_LABELS: Record<string, string> = {
  africanandeastern: "African & Eastern",
  africaneasternonline: "A&E Online",
  bdutyfree: "B Duty Free",
  bmmishops: "BMM I Shops",
  citydrinks: "City Drinks",
  dubaidutyfree: "Dubai Duty Free",
  gbiexpress: "GBI Express",
  gmp: "GMP",
  highspiritsuae: "High Spirits UAE",
  jmkcellars: "JMK Cellars",
  mmihomedelivery: "MMI Home Delivery",
  nhsc: "NHSC",
  royalspirit: "Royal Spirit",
  spinneysauh: "Spinneys AUH",
  supercellar: "Super Cellar",
  thebottlestore: "The Bottle Store",
  unisatgt: "Unisat GT",
  windmillgt: "Windmill GT",
};

const REGION_SUB_COLS = ["Regular", "Δ", "Promo", "Δ", "% Promo", "Δ"];
const RETAILER_SUB_COLS = ["Regular", "Δ", "Promo", "Δ", "% Promo"];
const REGION_ORDER = ["Dubai", "Abu Dhabi", "Other Emirates", "Bahrain"];
const RETAILER_ORDER: { region: string; aliases: string[] }[] = [
  { region: "Dubai", aliases: ["mmihomedelivery", "mmi"] },
  { region: "Dubai", aliases: ["africaneasternonline"] },
  { region: "Dubai", aliases: ["dubaidutyfree"] },
  { region: "Abu Dhabi", aliases: ["spinneysauh"] },
  { region: "Abu Dhabi", aliases: ["thebottlestore", "bottlestore"] },
  { region: "Abu Dhabi", aliases: ["africaneasternonline"] },
  { region: "Abu Dhabi", aliases: ["citydrinks"] },
  { region: "Abu Dhabi", aliases: ["centaurusint", "centaurus", "centaurusinternational"] },
  { region: "Other Emirates", aliases: ["mmihomedelivery", "mmi"] },
  { region: "Other Emirates", aliases: ["africaneasternonline"] },
  { region: "Other Emirates", aliases: ["supercellar"] },
  { region: "Other Emirates", aliases: ["unisatgt"] },
  { region: "Bahrain", aliases: ["bmmishops", "bmmi"] },
  { region: "Bahrain", aliases: ["africanandeastern", "africaneastern"] },
  { region: "Bahrain", aliases: ["bdutyfree", "bahraindutyfree"] },
  { region: "Bahrain", aliases: ["gbiexpress"] },
  { region: "Bahrain", aliases: ["nhsc"] },
];
const FIXED_COL_WIDTHS = [112, 58, 56, 34, 96] as const;
const STICKY_LEFT_OFFSETS = [0, 112, 170, 226, 260] as const;
const STICKY_TOTAL_WIDTH = 356;
const FIXED_COL_COUNT = FIXED_COL_WIDTHS.length;
const STICKY_HEADER_TOP = 0;
const STICKY_HEADER_ROW_HEIGHT = 32;
const STICKY_HEADER_SECOND_ROW_TOP = STICKY_HEADER_TOP + STICKY_HEADER_ROW_HEIGHT;
const TRUNCATE_CELL: React.CSSProperties = {
  overflow: "hidden",
  textOverflow: "ellipsis",
  whiteSpace: "nowrap",
};
const WRAP_CELL: React.CSSProperties = {
  overflow: "hidden",
  overflowWrap: "break-word",
  whiteSpace: "normal",
  lineHeight: 1.2,
};

/* =========================
   COLOR HELPERS
========================= */

function diffBg(diff: number): string {
  if (diff > 0) return "#dcfce7";
  if (diff < 0) return "#fee2e2";
  return "#fef9c3";
}
function diffFg(diff: number): string {
  if (diff > 0) return "#166534";
  if (diff < 0) return "#991b1b";
  return "#713f12";
}
function priceBg(diff: number): string {
  if (diff > 0) return "#f0fdf4";
  if (diff < 0) return "#fff1f2";
  return "#fefce8";
}

function promoHighlightStyle(kind: "min" | "max" | null): React.CSSProperties | undefined {
  if (kind === "min") {
    return {
      background: "#0f766e",
      color: "#ffffff",
      fontWeight: 700,
      textShadow: "0 1px 1px rgba(0,0,0,0.12)",
      boxShadow: "inset 0 0 0 1px rgba(255,255,255,0.18)",
    };
  }

  if (kind === "max") {
    return {
      background: "#be185d",
      color: "#ffffff",
      fontWeight: 700,
      textShadow: "0 1px 1px rgba(0,0,0,0.14)",
      boxShadow: "inset 0 0 0 1px rgba(255,255,255,0.16)",
    };
  }

  return undefined;
}

/* =========================
   HELPERS
========================= */

const nv = (v: number | string | null | undefined) => { const n = Number(v); return isNaN(n) ? 0 : n; };

function getISOWeek(date: Date): number {
  const d = new Date(Date.UTC(date.getFullYear(), date.getMonth(), date.getDate()));
  const day = d.getUTCDay() || 7;
  d.setUTCDate(d.getUTCDate() + 4 - day);
  const yearStart = new Date(Date.UTC(d.getUTCFullYear(), 0, 1));
  return Math.ceil(((d.getTime() - yearStart.getTime()) / 86400000 + 1) / 7);
}

function formatPeriodLabel(latest: string, prev: string): string {
  if (!latest || !prev) return "";
  const d = new Date(latest);
  const p = new Date(prev);
  const MONTHS = ["Jan","Feb","Mar","Apr","May","Jun","Jul","Aug","Sep","Oct","Nov","Dec"];
  return `${d.getFullYear()} – Week ${getISOWeek(d)} (${MONTHS[p.getMonth()]} ${p.getDate()}–${d.getDate()})`;
}

function capitalizeBrand(brand: string): string {
  return brand.split(/[\s_]+/).map((w) => w.charAt(0).toUpperCase() + w.slice(1)).join(" ");
}

function formatPackSize(size: string): string {
  return size.toLowerCase().replace(".0cl", "cl");
}

function formatRetailerLabel(retailer: string): string {
  const [, base = retailer, suffix = ""] = retailer.match(/^([^(]+?)(\s*\(.*\))?$/) ?? [];
  const trimmedBase = base.trim();
  const trimmedSuffix = suffix.trim();
  const label = RETAILER_LABELS[trimmedBase] ?? capitalizeBrand(trimmedBase);
  return trimmedSuffix ? `${label} ${trimmedSuffix}` : label;
}

function getRetailerBase(retailer: string): string {
  return retailer.split("(")[0].trim();
}

function normalizeRetailerKey(value: string): string {
  return value.toLowerCase().replace(/[^a-z0-9]/g, "");
}

function getRetailerRegion(retailer: string): string | null {
  return retailer.match(/\(([^)]+)\)/)?.[1]?.trim() ?? null;
}

function normalizeRetailerRegion(region: string | null): string | null {
  if (!region) return null;
  const normalized = normalizeRetailerKey(region);
  if (normalized === "d" || normalized === "dubai") return "Dubai";
  if (normalized === "ad" || normalized === "abudhabi") return "Abu Dhabi";
  if (normalized === "ne" || normalized === "otheremirates") return "Other Emirates";
  if (normalized === "bh" || normalized === "bahrain") return "Bahrain";
  return region;
}

function getRetailerOrderIndex(retailer: string, activeRegions: string[]): number {
  const base = normalizeRetailerKey(getRetailerBase(retailer));
  const region = normalizeRetailerRegion(getRetailerRegion(retailer));
  const exactRegionIndex = RETAILER_ORDER.findIndex(
    (entry) => entry.region === region && entry.aliases.includes(base)
  );
  if (exactRegionIndex !== -1) return exactRegionIndex;

  const activeRegionSet = new Set(activeRegions);
  const activeRegionIndex = RETAILER_ORDER.findIndex(
    (entry) => activeRegionSet.has(entry.region) && entry.aliases.includes(base)
  );
  if (activeRegionIndex !== -1) return activeRegionIndex;

  const fallbackIndex = RETAILER_ORDER.findIndex((entry) => entry.aliases.includes(base));
  return fallbackIndex === -1 ? Number.MAX_SAFE_INTEGER : fallbackIndex;
}

function resolveRetailerColumns(apiRetailers: string[], rows: BrandRow[], regions: string[]): string[] {
  const rowRetailers = Array.from(new Set(rows.flatMap((row) => Object.keys(row.retailers ?? {}))));
  const sourceOrder = new Map(
    [...apiRetailers, ...rowRetailers].map((retailer, index) => [retailer, index])
  );

  const ordered: string[] = [];
  const used = new Set<string>();
  const add = (retailer: string) => {
    if (!used.has(retailer)) {
      used.add(retailer);
      ordered.push(retailer);
    }
  };

  apiRetailers.forEach((apiRetailer) => {
    rowRetailers
      .filter((rowRetailer) => rowRetailer === apiRetailer || getRetailerBase(rowRetailer) === apiRetailer)
      .forEach(add);
  });
  rowRetailers.forEach(add);

  return ordered.sort((a, b) => {
    const ai = getRetailerOrderIndex(a, regions);
    const bi = getRetailerOrderIndex(b, regions);
    if (ai !== bi) return ai - bi;
    return (sourceOrder.get(a) ?? 9999) - (sourceOrder.get(b) ?? 9999);
  });
}

function getPromoHighlightKind(
  value: number | string | null | undefined,
  minPromo: number | null,
  maxPromo: number | null
): "min" | "max" | null {
  const n = Number(value);
  if (!value || isNaN(n) || n <= 0 || minPromo == null || maxPromo == null || minPromo === maxPromo) {
    return null;
  }

  if (n === minPromo) return "min";
  if (n === maxPromo) return "max";
  return null;
}

function getRowPromoRange(row: BrandRow, regions: string[], retailers: string[]) {
  const values = [
    ...regions.map((r) => { const v = Number(row.regions[r]?.regular_price); return isNaN(v) ? null : v; }),
    ...retailers.map((r) => { const v = Number(row.retailers[r]?.regular_price); return isNaN(v) ? null : v; }),
  ].filter((v): v is number => v != null && v > 0);

  if (values.length < 2) return { minPromo: null, maxPromo: null };
  return { minPromo: Math.min(...values), maxPromo: Math.max(...values) };
}

/* =========================
   CELL COMPONENTS
========================= */

const CELL_BASE: React.CSSProperties = {
  padding: "4px 5px",
  textAlign: "center",
  borderRight: "1px solid #f0f0f0",
  fontSize: 12,
  minWidth: 48,
};

function stickyColStyle(index: number, background: string, zIndex = 2): React.CSSProperties {
  return {
    position: "sticky",
    left: STICKY_LEFT_OFFSETS[index],
    width: FIXED_COL_WIDTHS[index],
    maxWidth: FIXED_COL_WIDTHS[index],
    background,
    zIndex,
    boxShadow: index === FIXED_COL_COUNT - 1 ? "10px 0 14px -14px rgba(15, 23, 42, 0.35)" : undefined,
  };
}

function stickyGroupCellStyle(background: string, zIndex = 2): React.CSSProperties {
  return {
    position: "sticky",
    left: 0,
    background,
    zIndex,
    minWidth: STICKY_TOTAL_WIDTH,
    width: STICKY_TOTAL_WIDTH,
    maxWidth: STICKY_TOTAL_WIDTH,
    boxShadow: "10px 0 14px -14px rgba(15, 23, 42, 0.35)",
  };
}

function DiffPill({ diff, isPct = false }: { diff: number; isPct?: boolean }) {
  const abs = Math.abs(diff);
  const num = abs % 1 === 0 ? String(abs) : abs.toFixed(2);
  const label = diff === 0 ? "0" : `${diff > 0 ? "+" : "-"}${num}${isPct ? "%" : ""}`;
  return (
    <span
      style={{
        display: "inline-block",
        padding: "2px 7px",
        borderRadius: 99,
        background: diffBg(diff),
        color: diffFg(diff),
        fontWeight: 700,
        fontSize: 11,
      }}
    >
      {label}
    </span>
  );
}

function RegionCells({
  data,
  isLast,
  promoHighlight,
}: {
  data: PricingData | undefined;
  isLast: boolean;
  promoHighlight?: "min" | "max" | null;
}) {
  const dash = <span style={{ color: "#d1d5db" }}>–</span>;
  const sep = isLast ? undefined : "2px solid #e2e8f0";

  if (!data) {
    return (
      <>
        {REGION_SUB_COLS.map((_, i) => (
          <td key={i} style={{ ...CELL_BASE, borderRight: i === REGION_SUB_COLS.length - 1 ? sep : CELL_BASE.borderRight }}>
            {dash}
          </td>
        ))}
      </>
    );
  }

  const hasRegular    = nv(data.regular_price) > 0;
  const hasPromoPrice = nv(data.promo_price) > 0 && nv(data.promo_price) !== nv(data.regular_price);
  const hasPromoDiff  = nv(data.promo_price) > 0 && nv(data.promo_price_diff_vs_previous_week) !== 0;
  const rd   = nv(data.regular_price_diff_vs_previous_week);
  const hasRegularDiff = hasRegular && rd !== 0;
  const pd   = nv(data.promo_price_diff_vs_previous_week);
  const pctd = nv(data.promo_pct_diff_vs_previous_week);

  return (
    <>
      <td style={{ ...CELL_BASE, background: hasRegular ? priceBg(rd) : undefined, color: "#1e293b" }}>
        {hasRegular ? nv(data.regular_price).toFixed(2) : dash}
      </td>
      <td style={{ ...CELL_BASE, background: hasRegularDiff ? diffBg(rd) : undefined }}>
        {hasRegularDiff ? <DiffPill diff={rd} /> : dash}
      </td>
      <td style={{ ...CELL_BASE, background: hasPromoPrice ? priceBg(pd) : undefined, color: "#1e293b" }}>
        {hasPromoPrice ? nv(data.promo_price).toFixed(2) : dash}
      </td>
      <td style={{ ...CELL_BASE, background: hasPromoDiff ? diffBg(pd) : undefined }}>
        {hasPromoDiff ? <DiffPill diff={pd} /> : dash}
      </td>
      <td style={{ ...CELL_BASE, background: hasPromoPrice ? priceBg(pctd) : undefined, color: "#1e293b" }}>
        {hasPromoPrice ? `${nv(data.promo_pct).toFixed(0)}%` : dash}
      </td>
      <td style={{ ...CELL_BASE, background: (hasPromoPrice && pctd !== 0) ? diffBg(pctd) : undefined, borderRight: sep }}>
        {(hasPromoPrice && pctd !== 0) ? <DiffPill diff={pctd} isPct /> : dash}
      </td>
    </>
  );
}

function RetailerCells({
  data,
  isLast,
  promoHighlight,
}: {
  data: PricingData | undefined;
  isLast: boolean;
  promoHighlight?: "min" | "max" | null;
}) {
  const dash = <span style={{ color: "#d1d5db" }}>–</span>;
  const sep = isLast ? undefined : "2px solid #e2e8f0";

  if (!data) {
    return (
      <>
        {RETAILER_SUB_COLS.map((_, i) => (
          <td key={i} style={{ ...CELL_BASE, borderRight: i === RETAILER_SUB_COLS.length - 1 ? sep : CELL_BASE.borderRight }}>
            {dash}
          </td>
        ))}
      </>
    );
  }

  const hasRegular    = nv(data.regular_price) > 0;
  const hasPromoPrice = nv(data.promo_price) > 0 && nv(data.promo_price) !== nv(data.regular_price);
  const hasPromoDiff  = nv(data.promo_price) > 0 && nv(data.promo_price_diff_vs_previous_week) !== 0;
  const rd = nv(data.regular_price_diff_vs_previous_week);
  const pd = nv(data.promo_price_diff_vs_previous_week);

  const reg = nv(data.regular_price);
  const prm = nv(data.promo_price);
  const promoPct = hasRegular && hasPromoPrice ? ((reg - prm) / reg) * 100 : null;

  return (
    <>
      <td style={{ ...CELL_BASE, background: hasRegular ? priceBg(rd) : undefined, color: "#1e293b", ...promoHighlightStyle(hasRegular ? (promoHighlight ?? null) : null) }}>
        {hasRegular ? reg.toFixed(2) : dash}
      </td>
      <td style={{ ...CELL_BASE, background: hasRegular && rd !== 0 ? diffBg(rd) : undefined }}>
        {hasRegular && rd !== 0 ? <DiffPill diff={rd} /> : dash}
      </td>
      <td style={{ ...CELL_BASE, background: hasPromoPrice ? priceBg(pd) : undefined, color: "#1e293b" }}>
        {hasPromoPrice ? prm.toFixed(2) : dash}
      </td>
      <td style={{ ...CELL_BASE, background: hasPromoDiff ? diffBg(pd) : undefined }}>
        {hasPromoDiff ? <DiffPill diff={pd} /> : dash}
      </td>
      <td style={{ ...CELL_BASE, color: "#1e293b", borderRight: sep }}>
        {promoPct !== null ? `${promoPct.toFixed(1)}%` : dash}
      </td>
    </>
  );
}

/* =========================
   EXPORT
========================= */

function buildExcel(
  data: BrandSalesData,
  brandGroups: BrandRow[][],
  periodLabel: string
) {
  const regions = [...data.regions].sort(
    (a, b) => (REGION_ORDER.indexOf(a) + 1 || 999) - (REGION_ORDER.indexOf(b) + 1 || 999)
  );
  const retailers = resolveRetailerColumns(data.retailers ?? [], data.rows ?? [], regions);

  // ── header row 1 ──
  const h1: (string | null)[] = [
    "Price, " + (brandGroups[0]?.[0]?.pricing_currency ?? ""),
    ...Array(FIXED_COL_COUNT - 1).fill(null),
  ];
  const merges: XLSX.Range[] = [{ s: { r: 0, c: 0 }, e: { r: 0, c: FIXED_COL_COUNT - 1 } }];
  let col = FIXED_COL_COUNT;

  regions.forEach((region) => {
    h1.push(REGION_LABEL[region] ?? region);
    for (let i = 1; i < REGION_SUB_COLS.length; i++) h1.push(null);
    merges.push({ s: { r: 0, c: col }, e: { r: 0, c: col + REGION_SUB_COLS.length - 1 } });
    col += REGION_SUB_COLS.length;
  });
  retailers.forEach((retailer) => {
    h1.push(formatRetailerLabel(retailer));
    for (let i = 1; i < RETAILER_SUB_COLS.length; i++) h1.push(null);
    merges.push({ s: { r: 0, c: col }, e: { r: 0, c: col + RETAILER_SUB_COLS.length - 1 } });
    col += RETAILER_SUB_COLS.length;
  });

  // ── header row 2 ──
  const h2: string[] = ["BRAND", "PACK TYPE", "PACK SIZE", "PACK", "SUB TYPE"];
  regions.forEach(() => REGION_SUB_COLS.forEach((s) => h2.push(s)));
  retailers.forEach(() => RETAILER_SUB_COLS.forEach((s) => h2.push(s)));

  const wsData: (string | number | null)[][] = [h1, h2];

  brandGroups.forEach((group) => {
    group.forEach((row, ri) => {
      const r: (string | number | null)[] = [
        ri === 0 ? capitalizeBrand(row.brand) : "",
        row.pack_type,
        formatPackSize(row.pack_size),
        row.pack,
        row.sub_type ?? "",
      ];

      regions.forEach((region) => {
        const d = row.regions[region];
        if (!d) {
          REGION_SUB_COLS.forEach(() => r.push("–"));
        } else {
          const reg = nv(d.regular_price);
          const prm = nv(d.promo_price);
          const hasPromo = prm > 0 && prm !== reg;
          r.push(reg > 0 ? reg : "–");
          r.push(nv(d.regular_price_diff_vs_previous_week) !== 0 ? nv(d.regular_price_diff_vs_previous_week) : "–");
          r.push(hasPromo ? prm : "–");
          r.push(nv(d.promo_price_diff_vs_previous_week) !== 0 ? nv(d.promo_price_diff_vs_previous_week) : "–");
          r.push(hasPromo ? `${nv(d.promo_pct).toFixed(0)}%` : "–");
          r.push(nv(d.promo_pct_diff_vs_previous_week) !== 0 ? nv(d.promo_pct_diff_vs_previous_week) : "–");
        }
      });

      retailers.forEach((retailer) => {
        const d = row.retailers[retailer];
        if (!d) {
          RETAILER_SUB_COLS.forEach(() => r.push("–"));
        } else {
          const reg = nv(d.regular_price);
          const prm = nv(d.promo_price);
          const hasPromo = prm > 0 && prm !== reg;
          const promoPct = reg > 0 && hasPromo ? ((reg - prm) / reg) * 100 : null;
          r.push(reg > 0 ? reg : "–");
          r.push(nv(d.regular_price_diff_vs_previous_week) !== 0 ? nv(d.regular_price_diff_vs_previous_week) : "–");
          r.push(hasPromo ? prm : "–");
          r.push(nv(d.promo_price_diff_vs_previous_week) !== 0 ? nv(d.promo_price_diff_vs_previous_week) : "–");
          r.push(promoPct !== null ? `${promoPct.toFixed(1)}%` : "–");
        }
      });

      wsData.push(r);
    });
    // blank separator row between brand groups
    wsData.push(Array(h2.length).fill(null));
  });

  const ws = XLSX.utils.aoa_to_sheet(wsData);
  ws["!merges"] = merges;
  ws["!cols"] = h2.map((_, i) => ({ wch: i < FIXED_COL_COUNT ? 16 : 10 }));

  const wb = XLSX.utils.book_new();
  XLSX.utils.book_append_sheet(wb, ws, "Pricing Analysis");
  const ld = new Date(data.latest_data_point_used_date);
  const pd = new Date(data.previous_week_data_point_used_date);
  const FILE_MONTHS = ["Jan","Feb","Mar","Apr","May","Jun","Jul","Aug","Sep","Oct","Nov","Dec"];
  const fileName = !isNaN(ld.getTime())
    ? `pricing_analysis_${ld.getFullYear()}_W${getISOWeek(ld)}_${FILE_MONTHS[ld.getMonth()]}_${pd.getDate()}-${ld.getDate()}.xlsx`
    : `pricing_analysis_${periodLabel.replace(/\s+/g, "_")}.xlsx`;
  XLSX.writeFile(wb, fileName);
}

/* =========================
   PAGE
========================= */

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

/* =========================
   PAGE
========================= */

interface ApiFiltersResponse {
  markets: string[];
  "all-retailers": string[];
  sub_types: string[];
  dates: string[];
  cities: string[];
  brands: string[];
}

const DEFAULT_SELECTED_FILTERS: Filters = {
  markets: [],
  retailers: [],
  subTypes: [],
  cities: [],
  brands: [],
  local: true,
  date: undefined,
};
const EMPTY_TABLE_FILTERS = { packType: "", packSize: "", pack: "" };

const SALES_FILTERS_STORAGE_KEY = "pricing_sales_filters";

const loadStoredSalesFilters = (): { selectedFilters: Filters; tableFilters: typeof EMPTY_TABLE_FILTERS } => {
  if (typeof window === "undefined") return { selectedFilters: DEFAULT_SELECTED_FILTERS, tableFilters: EMPTY_TABLE_FILTERS };
  try {
    const stored = localStorage.getItem(SALES_FILTERS_STORAGE_KEY);
    if (!stored) return { selectedFilters: DEFAULT_SELECTED_FILTERS, tableFilters: EMPTY_TABLE_FILTERS };
    const parsed = JSON.parse(stored);
    return {
      selectedFilters: { ...DEFAULT_SELECTED_FILTERS, ...parsed.selectedFilters },
      tableFilters: { ...EMPTY_TABLE_FILTERS, ...parsed.tableFilters },
    };
  } catch {
    return { selectedFilters: DEFAULT_SELECTED_FILTERS, tableFilters: EMPTY_TABLE_FILTERS };
  }
};

export default function PricingAnalysisExploreNew() {
  const topScrollRef = React.useRef<HTMLDivElement>(null);
  const tableWrapRef = React.useRef<HTMLDivElement>(null);
  const tableRef     = React.useRef<HTMLTableElement>(null);
  const [tableInnerWidth, setTableInnerWidth] = useState(0);

  const onTopScroll   = () => { if (tableWrapRef.current && topScrollRef.current) tableWrapRef.current.scrollLeft = topScrollRef.current.scrollLeft; };
  const onTableScroll = () => { if (topScrollRef.current && tableWrapRef.current) topScrollRef.current.scrollLeft = tableWrapRef.current.scrollLeft; };

  const [data, setData] = useState<BrandSalesData | null>(null);
  const [loading, setLoading] = useState(true);
  const [apiFilters, setApiFilters] = useState<ApiFiltersResponse | null>(null);
  const [brandOptions, setBrandOptions] = useState<string[]>([]);
  const [selectedFilters, setSelectedFilters] = useState<Filters>(() => loadStoredSalesFilters().selectedFilters);
  const [draftSelectedFilters, setDraftSelectedFilters] = useState<Filters>(() => loadStoredSalesFilters().selectedFilters);

  const dateInitialized = React.useRef(false);
  const brandScopeRef = React.useRef("");

  useEffect(() => {
    const { markets, cities, retailers, brands, subTypes } = draftSelectedFilters;
    const brandScopeKey = JSON.stringify({ markets, cities, retailers, subTypes });
    getFilters({ markets, cities, retailers, brands, subTypes })
      .then((res) => {
        const data = res.data ?? res;
        setApiFilters(data);
        setBrandOptions((prev) => {
          const nextBrands = data?.brands ?? [];
          if (brandScopeRef.current !== brandScopeKey) {
            brandScopeRef.current = brandScopeKey;
            return nextBrands;
          }
          return Array.from(new Set([...prev, ...nextBrands]));
        });
        if (!dateInitialized.current && data?.dates?.length) {
          dateInitialized.current = true;
          setSelectedFilters((prev) => ({ ...prev, date: prev.date ?? data.dates[0] }));
          setDraftSelectedFilters((prev) => ({ ...prev, date: prev.date ?? data.dates[0] }));
        }
      })
      .catch(() => setApiFilters(null));
  }, [draftSelectedFilters]);

  useEffect(() => {
    getBrandSales(selectedFilters)
      .then((res: Record<string, BrandSalesData>) => setData(res.data ?? res))
      .catch(() => setData(null))
      .finally(() => setLoading(false));
  }, [selectedFilters]);

  const updateDraftFilters = (updater: (prev: Filters) => Filters) => {
    setDraftSelectedFilters(updater);
  };

  const applyFilters = () => {
    setLoading(true);
    setSelectedFilters({ ...draftSelectedFilters });
    setFilters({ ...draftFilters });
  };

  const resetFilters = () => {
    const resetSelected = { ...DEFAULT_SELECTED_FILTERS, date: apiFilters?.dates?.[0] };
    setDraftSelectedFilters(resetSelected);
    setSelectedFilters(resetSelected);
    setDraftFilters(EMPTY_TABLE_FILTERS);
    setFilters(EMPTY_TABLE_FILTERS);
    try {
      localStorage.removeItem(SALES_FILTERS_STORAGE_KEY);
    } catch {}
  };

  const regions = [...(data?.regions ?? [])].sort(
    (a, b) => {
      const ai = REGION_ORDER.indexOf(a);
      const bi = REGION_ORDER.indexOf(b);
      return (ai === -1 ? 999 : ai) - (bi === -1 ? 999 : bi);
    }
  );
  const rows      = data?.rows      ?? [];
  const retailers = resolveRetailerColumns(data?.retailers ?? [], rows, regions);

  // ── column filters ───────────────────────────────────────────────
  const [filters, setFilters] = useState(() => loadStoredSalesFilters().tableFilters);
  const [draftFilters, setDraftFilters] = useState(() => loadStoredSalesFilters().tableFilters);

  // Persist applied filters so they survive page reloads/navigation
  useEffect(() => {
    try {
      localStorage.setItem(SALES_FILTERS_STORAGE_KEY, JSON.stringify({ selectedFilters, tableFilters: filters }));
    } catch {}
  }, [selectedFilters, filters]);

  const uniq = {
    packTypes: [...new Set(rows.map(r => r.pack_type))].sort(),
    packSizes: [...new Set(rows.map(r => r.pack_size))].sort((a, b) => parseFloat(a) - parseFloat(b)),
    packs:     [...new Set(rows.map(r => String(r.pack)))].sort((a, b) => Number(a) - Number(b)),
  };

  const brandGroups: BrandRow[][] = [];
  rows.forEach((row) => {
    const last = brandGroups[brandGroups.length - 1];
    if (last && last[0].brand === row.brand) last.push(row);
    else brandGroups.push([row]);
  });

  const filteredGroups = brandGroups
    .map(group => group.filter(row =>
      (!filters.packType || row.pack_type === filters.packType) &&
      (!filters.packSize || row.pack_size === filters.packSize) &&
      (!filters.pack     || String(row.pack) === filters.pack)
    ))
    .filter(group => group.length > 0);

  const periodLabel = data
    ? formatPeriodLabel(data.latest_data_point_used_date, data.previous_week_data_point_used_date)
    : "Loading…";

  useEffect(() => {
    if (tableRef.current) setTableInnerWidth(tableRef.current.scrollWidth);
  }, [data, filteredGroups]);

  /* ---- shared th styles ---- */
  const fixedTh = (i: number): React.CSSProperties => ({
    padding: "5px 6px",
    textAlign: "left",
    background: "#f8fafc",
    color: "#64748b",
    fontWeight: 600,
    fontSize: 10,
    letterSpacing: "0.06em",
    borderBottom: "2px solid #e2e8f0",
    borderRight: i === FIXED_COL_COUNT - 1 ? "2px solid #cbd5e1" : "1px solid #e2e8f0",
    minWidth: FIXED_COL_WIDTHS[i],
    width: FIXED_COL_WIDTHS[i],
    maxWidth: FIXED_COL_WIDTHS[i],
    top: STICKY_HEADER_SECOND_ROW_TOP,
    ...stickyColStyle(i, "#f8fafc", 9),
  });

  const headerRow1Style = (background: string, zIndex = 7): React.CSSProperties => ({
    position: "sticky",
    top: STICKY_HEADER_TOP,
    zIndex,
    background,
  });

  const headerRow2Style = (background: string, zIndex = 6): React.CSSProperties => ({
    position: "sticky",
    top: STICKY_HEADER_SECOND_ROW_TOP,
    zIndex,
    background,
  });

  return (
    <div className="w-full bg-transparent" style={{ minHeight: "100%" }}>
      <DashboardTopbar
        title="Beer & Cider Pricing Analysis"
        accessory={
          <CurrencySwitch
            value={draftSelectedFilters.local ?? false}
            onChange={(val) => updateDraftFilters((prev) => ({ ...prev, local: val }))}
          />
        }
      />
      <style>{`
        @keyframes bst-spin { to { transform: rotate(360deg); } }
        @keyframes bst-shimmer { 0%{background-position:200% 0} 100%{background-position:-200% 0} }
        .bst-shimmer { background: linear-gradient(90deg,#e2e8f0 25%,#f1f5f9 50%,#e2e8f0 75%); background-size:200% 100%; animation: bst-shimmer 1.4s infinite; border-radius: 4px; }
        .bst-row:hover > td { filter: brightness(0.96); }
        .bst-scroll::-webkit-scrollbar { height: 10px; }
        .bst-scroll::-webkit-scrollbar-track { background: #e2e8f0; border-radius: 5px; }
        .bst-scroll::-webkit-scrollbar-thumb { background: #94a3b8; border-radius: 5px; }
        .bst-scroll::-webkit-scrollbar-thumb:hover { background: #64748b; }
        .export-btn:hover:not(:disabled) { background: #166534 !important; }
        .pricing-page-shell { padding: 20px 24px !important; }
        .pricing-controls-row { margin-bottom: 14px !important; }
        .pricing-legend { gap: 8px !important; font-size: 10px !important; }
        .pricing-legend-swatch { width: 8px !important; height: 8px !important; }
        .pricing-filter-actions {
          display: flex;
          align-items: flex-end;
          gap: 8px;
          flex: 0 0 auto;
          align-self: flex-end;
        }
      `}</style>


      <div
        className="pricing-page-shell p-8"
        style={{ height: "calc(100vh - 64px)", display: "flex", flexDirection: "column", minHeight: 0 }}
      >

        {/* Title + controls row */}
        <div className="pricing-controls-row flex items-start justify-end gap-4 mb-6">
          <div className="flex items-center gap-3 shrink-0">
            {/* Color legend */}
            <div className="pricing-legend flex items-center gap-3" style={{ fontSize: 11, color: "#64748b" }}>
              {[
                { bg: "#dcfce7", fg: "#166534", label: "Increase" },
                { bg: "#fef9c3", fg: "#713f12", label: "Same" },
                { bg: "#fee2e2", fg: "#991b1b", label: "Decrease" },
                { bg: "#0f766e", fg: "#0f766e", label: "Lowest Price" },
                { bg: "#be185d", fg: "#be185d", label: "Highest Price" },
              ].map(({ bg, fg, label }) => (
                <span key={label} className="flex items-center gap-1">
                  <span className="pricing-legend-swatch" style={{ display: "inline-block", width: 10, height: 10, borderRadius: 2, background: bg, border: `1px solid ${fg}33` }} />
                  <span style={{ color: fg, fontWeight: 600 }}>{label}</span>
                </span>
              ))}
              <span style={{ color: "#475569", fontWeight: 700, paddingLeft: 4 }}>Δ = Diff vs Previous Week</span>
            </div>

            {/* Export button */}
            <button
              className="export-btn"
              disabled={loading || !data}
              onClick={() => data && buildExcel(data, filteredGroups, periodLabel)}
              style={{
                display: "inline-flex",
                alignItems: "center",
                gap: 5,
                padding: "6px 12px",
                background: "#16a34a",
                color: "white",
                border: "none",
                borderRadius: 9,
                fontSize: 11,
                fontWeight: 600,
                cursor: loading || !data ? "not-allowed" : "pointer",
                opacity: loading || !data ? 0.5 : 1,
                transition: "background 0.15s",
                whiteSpace: "nowrap",
              }}
            >
              <svg width="12" height="12" viewBox="0 0 16 16" fill="currentColor">
                <path d="M2 14h12v-1.5H2V14zm10-8H9V2H7v4H4l4 4 4-4z" />
              </svg>
              Export Excel
            </button>

          </div>
        </div>

        {/* Column filters */}
        <div className="pricing-compact-filters pricing-table-filters chart-card rounded-xl p-4 mb-4 flex items-end gap-3 flex-wrap">

            {/* Market */}
            <div className="pricing-filter-field" style={{ "--filter-w": "112px" } as React.CSSProperties}>
              <FilterSelect
                label="Market"
                value={draftSelectedFilters.markets?.[0] ?? ""}
                onChange={(val) => updateDraftFilters((prev) => ({ ...prev, markets: val ? [val] : [], subTypes: [] }))}
                options={[
                  { label: "All Markets", value: "" },
                  ...(apiFilters?.markets ?? []).map((m) => ({ label: m, value: m })),
                ]}
              />
            </div>

            {/* City */}
            <div className="pricing-filter-field" style={{ "--filter-w": "112px" } as React.CSSProperties}>
              <FilterSelect
                label="City"
                value={draftSelectedFilters.cities?.[0] ?? ""}
                onChange={(val) => updateDraftFilters((prev) => ({ ...prev, cities: val ? [val] : [] }))}
                options={[
                  { label: "All Cities", value: "" },
                  ...(apiFilters?.cities ?? []).map((c) => ({ label: c, value: c })),
                ]}
              />
            </div>

            {/* Retailer */}
            <div className="pricing-filter-field" style={{ "--filter-w": "126px" } as React.CSSProperties}>
              <FilterSelect
                label="Retailer"
                value={draftSelectedFilters.retailers?.[0] ?? ""}
                onChange={(val) => updateDraftFilters((prev) => ({ ...prev, retailers: val ? [val] : [] }))}
                options={[
                  { label: "All Retailers", value: "" },
                  ...(apiFilters?.["all-retailers"] ?? []).map((r) => ({ label: capitalizeBrand(r), value: r })),
                ]}
              />
            </div>

            {/* Brand */}
            <div className="pricing-filter-field" style={{ "--filter-w": "190px" } as React.CSSProperties}>
              <FilterMultiSelect
                label="Brand"
                values={draftSelectedFilters.brands ?? []}
                onChange={(values) => updateDraftFilters((prev) => ({ ...prev, brands: values }))}
                options={[
                  { label: "All Brands", value: "" },
                  ...brandOptions.map((b) => ({ label: capitalizeBrand(b), value: b })),
                ]}
                allLabel="All Brands"
              />
            </div>

            {/* Sub Type */}
            <div className="pricing-filter-field" style={{ "--filter-w": "108px" } as React.CSSProperties}>
              <FilterSelect
                label="Sub Type"
                value={draftSelectedFilters.subTypes?.[0] ?? ""}
                onChange={(val) => updateDraftFilters((prev) => ({ ...prev, subTypes: val ? [val] : [] }))}
                options={[
                  { label: "All Sub Types", value: "" },
                  ...(apiFilters?.sub_types ?? []).map((s) => ({ label: s, value: s })),
                ]}
              />
            </div>

            {/* Pack Type */}
            <div className="pricing-filter-field" style={{ "--filter-w": "106px" } as React.CSSProperties}>
              <FilterSearchSelect
                label="Pack Type"
                value={draftFilters.packType}
                options={[
                  { label: "All Pack Types", value: "" },
                  ...uniq.packTypes.map(p => ({ label: p.charAt(0).toUpperCase() + p.slice(1), value: p })),
                ]}
                onChange={(val) => setDraftFilters(prev => ({ ...prev, packType: val }))}
              />
            </div>

            {/* Pack Size */}
            <div className="pricing-filter-field" style={{ "--filter-w": "106px" } as React.CSSProperties}>
              <FilterSearchSelect
                label="Pack Size"
                value={draftFilters.packSize}
                options={[
                  { label: "All Pack Sizes", value: "" },
                  ...uniq.packSizes.map(p => ({ label: formatPackSize(p), value: p })),
                ]}
                onChange={(val) => setDraftFilters(prev => ({ ...prev, packSize: val }))}
              />
            </div>

            {/* Pack */}
            <div className="pricing-filter-field" style={{ "--filter-w": "76px" } as React.CSSProperties}>
              <FilterSearchSelect
                label="Pack"
                value={draftFilters.pack}
                options={[
                  { label: "All Packs", value: "" },
                  ...uniq.packs.map(p => ({ label: p, value: p })),
                ]}
                onChange={(val) => setDraftFilters(prev => ({ ...prev, pack: val }))}
              />
            </div>

            {/* Historic Date */}
            <div className="pricing-filter-field" style={{ "--filter-w": "118px" } as React.CSSProperties}>
              <FilterSelect
                label="Historic Date"
                value={draftSelectedFilters.date ?? ""}
                onChange={(val) => updateDraftFilters((prev) => ({ ...prev, date: val || undefined }))}
                options={(apiFilters?.dates ?? []).map((d) => ({
                  label: new Date(d).toLocaleDateString("en-GB", { day: "2-digit", month: "short", year: "numeric" }),
                  value: d,
                }))}
              />
            </div>

            <div className="pricing-filter-actions">
              <button
                onClick={resetFilters}
                style={{ color: "var(--muted-tx)", border: "1px solid var(--card-bd)", padding: "6px 11px", borderRadius: 8, fontSize: 11, cursor: "pointer", background: "transparent", whiteSpace: "nowrap" }}
                className="hover:border-red-400 transition-colors"
              >Reset</button>
              <button
                onClick={applyFilters}
                disabled={loading}
                style={{ color: "white", border: "1px solid #2563eb", padding: "6px 13px", borderRadius: 8, fontSize: 11, fontWeight: 700, cursor: loading ? "not-allowed" : "pointer", background: "#2563eb", opacity: loading ? 0.6 : 1, whiteSpace: "nowrap" }}
                className="pricing-apply-button transition-colors hover:bg-blue-700"
              >
                Apply
              </button>
            </div>
          </div>

        {/* Table */}
        <div style={{ borderRadius: 12, border: "1px solid #e2e8f0", boxShadow: "0 2px 10px rgba(0,0,0,0.07)", overflow: "hidden", flex: "1 1 auto", minHeight: 0, display: "flex", flexDirection: "column" }}>
          {/* Top scrollbar mirror */}
          <div
            ref={topScrollRef}
            onScroll={onTopScroll}
            className="bst-scroll"
            style={{ overflowX: "scroll", overflowY: "hidden", height: 10, background: "#f1f5f9", flexShrink: 0 }}
          >
            <div style={{ width: tableInnerWidth || 9999, height: 1 }} />
          </div>
          {/* Table scroll container */}
          <div
            ref={tableWrapRef}
            onScroll={onTableScroll}
            className="bst-scroll"
            style={{ width: "100%", overflow: "auto", flex: "1 1 auto", minHeight: 0 }}
          >
          {loading ? (
            <table style={{ borderCollapse: "collapse", width: "100%", background: "white" }}>
              <tbody>
                {Array.from({ length: 12 }).map((_, ri) => (
                  <tr key={ri} style={{ borderBottom: "1px solid #f1f5f9" }}>
                    {Array.from({ length: 8 }).map((_, ci) => (
                      <td key={ci} style={{ padding: "10px 12px" }}>
                        <div className="bst-shimmer" style={{ height: 12, width: ci === 0 ? "80%" : ci === 1 ? "60%" : "50%" }} />
                      </td>
                    ))}
                  </tr>
                ))}
              </tbody>
            </table>
          ) : !data || rows.length === 0 ? (
            <div style={{ padding: 60, textAlign: "center", color: "#94a3b8", background: "white", fontSize: 14 }}>
              No data available
            </div>
          ) : (
            <table ref={tableRef} style={{ borderCollapse: "collapse", fontSize: 13, whiteSpace: "nowrap", background: "white", width: "max-content", minWidth: "100%" }}>
              <thead>
                {/* Row 1 */}
                <tr>
                  <th
                    colSpan={FIXED_COL_COUNT}
                    style={{
                      background: "#f1f5f9",
                      borderBottom: "0",
                      borderRight: "2px solid #cbd5e1",
                      top: STICKY_HEADER_TOP,
                      ...stickyGroupCellStyle("#f1f5f9", 10),
                    }}
                  />

                  {regions.map((region, ri) => (
                    <th
                      key={region}
                      colSpan={REGION_SUB_COLS.length}
                      style={{
                        ...headerRow1Style(REGION_HEADER_COLOR[region] ?? "#93c5fd"),
                        padding: "8px 9px",
                        textAlign: "center",
                        color: "#0f172a",
                        fontWeight: 700,
                        fontSize: 11,
                        letterSpacing: "0.05em",
                        borderBottom: "0",
                        borderRight: ri < regions.length - 1 || retailers.length > 0 ? "2px solid #60a5fa" : undefined,
                      }}
                    >
                      {REGION_LABEL[region] ?? region}
                    </th>
                  ))}

                  {retailers.map((retailer, ri) => (
                    <th
                      key={retailer}
                      colSpan={RETAILER_SUB_COLS.length}
                      style={{
                        ...headerRow1Style(RETAILER_HEADER_COLOR),
                        padding: "8px 9px",
                        textAlign: "center",
                        color: "#0f172a",
                        fontWeight: 700,
                        fontSize: 11,
                        letterSpacing: "0.05em",
                        borderBottom: "0",
                        borderRight: ri < retailers.length - 1 ? "2px solid #4ade80" : undefined,
                      }}
                    >
                      {formatRetailerLabel(retailer)}
                    </th>
                  ))}
                </tr>

                {/* Row 2 */}
                <tr>
                  {(["BRAND", "TYPE", "SIZE", "PK", "SUB"] as const).map((label, i) => (
                    <th key={label} style={fixedTh(i)}>{label}</th>
                  ))}

                  {regions.map((region, ri) =>
                    REGION_SUB_COLS.map((sub, si) => (
                      <th
                        key={`${region}-${si}`}
                        style={{
                          ...headerRow2Style(REGION_SUBHEADER_COLOR[region] ?? "#dbeafe"),
                          padding: "5px 5px",
                          textAlign: "center",
                          color: "#334155",
                          fontWeight: 500,
                          fontSize: 10,
                          letterSpacing: "0.02em",
                          borderBottom: "2px solid #93c5fd",
                          borderRight:
                            si === REGION_SUB_COLS.length - 1
                              ? ri < regions.length - 1 || retailers.length > 0
                                ? "2px solid #60a5fa"
                                : undefined
                              : "1px solid #dbeafe",
                          minWidth: 48,
                        }}
                      >
                        {sub}
                      </th>
                    ))
                  )}

                  {retailers.map((retailer, ri) =>
                    RETAILER_SUB_COLS.map((sub, si) => (
                      <th
                        key={`${retailer}-${si}`}
                        style={{
                          ...headerRow2Style(RETAILER_SUBHEADER_COLOR),
                          padding: "5px 5px",
                          textAlign: "center",
                          color: "#334155",
                          fontWeight: 500,
                          fontSize: 10,
                          letterSpacing: "0.02em",
                          borderBottom: "2px solid #86efac",
                          borderRight:
                            si === RETAILER_SUB_COLS.length - 1
                              ? ri < retailers.length - 1
                                ? "2px solid #4ade80"
                                : undefined
                              : "1px solid #dcfce7",
                          minWidth: 48,
                        }}
                      >
                        {sub}
                      </th>
                    ))
                  )}
                </tr>
              </thead>

              <tbody>
                {filteredGroups.map((group) =>
                  group.map((row, ri) => {
                    const isFirst = ri === 0;
                    const isLast = ri === group.length - 1;
                    const { minPromo, maxPromo } = getRowPromoRange(row, regions, retailers);
                    return (
                      <tr
                        key={`${row.brand}-${row.pack_type}-${row.pack_size}-${row.pack}-${row.sub_type ?? ""}`}
                        className="bst-row"
                        style={{ borderBottom: isLast ? "2px solid #e2e8f0" : "1px solid #f1f5f9" }}
                      >
                        <td
                          style={{
                            padding: "5px 6px",
                            color: "#1e293b",
                            fontWeight: isFirst ? 600 : 400,
                            borderRight: "1px solid #f0f0f0",
                            minWidth: FIXED_COL_WIDTHS[0],
                            ...WRAP_CELL,
                            background: "white",
                            ...stickyColStyle(0, "white"),
                          }}
                          title={isFirst ? capitalizeBrand(row.brand) : undefined}
                        >
                          {isFirst ? capitalizeBrand(row.brand) : ""}
                        </td>
                        <td
                          style={{
                            padding: "5px 6px",
                            color: "#475569",
                            borderRight: "1px solid #f0f0f0",
                            minWidth: FIXED_COL_WIDTHS[1],
                            ...TRUNCATE_CELL,
                            background: "white",
                            ...stickyColStyle(1, "white"),
                          }}
                        >
                          {row.pack_type ? row.pack_type.charAt(0).toUpperCase() + row.pack_type.slice(1) : ""}
                        </td>
                        <td
                          style={{
                            padding: "5px 6px",
                            color: "#3b82f6",
                            fontWeight: 600,
                            borderRight: "1px solid #f0f0f0",
                            minWidth: FIXED_COL_WIDTHS[2],
                            ...TRUNCATE_CELL,
                            background: "white",
                            ...stickyColStyle(2, "white"),
                          }}
                        >
                          {formatPackSize(row.pack_size)}
                        </td>
                        <td
                          style={{
                            padding: "5px 6px",
                            color: "#475569",
                            borderRight: "1px solid #f0f0f0",
                            textAlign: "center",
                            minWidth: FIXED_COL_WIDTHS[3],
                            background: "white",
                            ...stickyColStyle(3, "white"),
                          }}
                        >
                          {row.pack}
                        </td>
                        <td
                          style={{
                            padding: "5px 6px",
                            color: row.sub_type ? "#475569" : "#cbd5e1",
                            borderRight: "2px solid #cbd5e1",
                            minWidth: FIXED_COL_WIDTHS[4],
                            ...WRAP_CELL,
                            background: "white",
                            ...stickyColStyle(4, "white"),
                          }}
                          title={row.sub_type ? row.sub_type.charAt(0).toUpperCase() + row.sub_type.slice(1) : undefined}
                        >
                          {row.sub_type ? row.sub_type.charAt(0).toUpperCase() + row.sub_type.slice(1) : "–"}
                        </td>

                        {regions.map((region, ri) => (
                          <React.Fragment key={region}>
                            <RegionCells
                              data={row.regions[region]}
                              isLast={ri === regions.length - 1 && retailers.length === 0}
                            />
                          </React.Fragment>
                        ))}

                        {retailers.map((retailer, ri) => (
                          <React.Fragment key={retailer}>
                            <RetailerCells
                              data={row.retailers[retailer]}
                              isLast={ri === retailers.length - 1}
                              promoHighlight={getPromoHighlightKind(row.retailers[retailer]?.regular_price, minPromo, maxPromo)}
                            />
                          </React.Fragment>
                        ))}
                      </tr>
                    );
                  })
                )}
              </tbody>
            </table>
          )}
          </div>
        </div>
      </div>
    </div>
  );
}
