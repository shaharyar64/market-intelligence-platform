"use client";

import { useEffect, useMemo, useState, type ReactNode } from "react";
import {
  Bar,
  BarChart,
  CartesianGrid,
  Cell,
  LabelList,
  Legend,
  ResponsiveContainer,
  Tooltip,
  XAxis,
  YAxis,
} from "recharts";
import { ExternalLink, FileText, Globe, Layers, Link2, Store } from "lucide-react";
import CitationExplorer, { EMPTY_FILTERS, type ExplorerFilters } from "@/components/digitalBrandHealth/CitationExplorer";
import BankCategoryHeatmap from "@/components/digitalBrandHealth/BankCategoryHeatmap";
import { AxisTick, getBarChartDimensions } from "@/components/digitalBrandHealth/ChartAxisTick";
import ExportExcelButton from "@/components/ui/ExportExcelButton";
import { getCitationAnalysis, type CitationAnalysisResponse } from "@/lib/digitalBrandHealth";
import { FALLBACK_COLORS as SERIES_COLORS, getBankColor } from "@/lib/bankColors";

const KIND_LABELS: Record<string, string> = {
  own_site: "Own site",
  other_bank_site: "Other bank's site",
  third_party: "Third party",
};
const KIND_KEYS = ["own_site", "other_bank_site", "third_party"];

const tooltipProps = {
  contentStyle: {
    background: "var(--tooltip-bg)",
    border: "1px solid var(--tooltip-bd)",
    borderRadius: 12,
    color: "var(--tooltip-tx)",
  },
  labelStyle: { color: "var(--tooltip-tx)" },
  itemStyle: { color: "var(--tooltip-tx)" },
  cursor: { fill: "rgba(84,170,236,0.08)" },
};
const tickStyle = { fill: "var(--muted-tx)", fontSize: 12, fontWeight: 600 };

type Row = Record<string, number | string>;

// Long rows -> one row per bank with a zero-filled column per series key.
function pivot(
  rows: Array<{ bank: string; citations: number } & Record<string, unknown>>,
  key: string,
  fixedKeys?: string[],
  pct = false
) {
  const banks = new Map<string, Row>();
  const keys = new Set<string>(fixedKeys);
  rows.forEach((r) => {
    const k = String(r[key]);
    keys.add(k);
    const row = banks.get(r.bank) ?? { bank: r.bank };
    row[k] = ((row[k] as number) ?? 0) + r.citations;
    banks.set(r.bank, row);
  });
  const keyList = Array.from(keys);
  const data = Array.from(banks.values()).map((row) => {
    keyList.forEach((k) => (row[k] = (row[k] as number) ?? 0));
    if (pct) {
      const total = keyList.reduce((sum, k) => sum + (row[k] as number), 0) || 1;
      keyList.forEach((k) => (row[k] = ((row[k] as number) / total) * 100));
    }
    return row;
  });
  return { data, keys: keyList };
}

function Card({
  title,
  description,
  exportRows,
  filename,
  actions,
  children,
}: {
  title: string;
  description: string;
  exportRows: Row[];
  filename: string;
  actions?: ReactNode;
  children: ReactNode;
}) {
  return (
    <section className="rounded-2xl border border-[var(--card-bd)] bg-[var(--card-bg-2)] p-6 shadow-lg">
      <div className="mb-5 flex flex-col gap-3 sm:flex-row sm:items-start sm:justify-between">
        <div>
          <h2 className="text-lg font-semibold text-[var(--title-tx)]">{title}</h2>
          <p className="mt-1 text-sm text-[var(--muted-tx)]">{description}</p>
        </div>
        <div className="flex flex-wrap items-center gap-3">
          {actions}
          <ExportExcelButton rows={exportRows} filename={filename} sheetName={title} />
        </div>
      </div>
      <div className="overflow-x-auto rounded-2xl border border-[var(--card-bd)] bg-[var(--card-bg)] p-5 shadow-sm">
        {children}
      </div>
    </section>
  );
}

function BankBars({
  data,
  keys,
  labels,
  percent,
  onSelect,
}: {
  data: Row[];
  keys: string[];
  labels?: Record<string, string>;
  percent?: boolean;
  onSelect?: (bank: string, key: string) => void;
}) {
  const { chartWidth, axisHeight, chartHeight } = getBarChartDimensions(data.map((r) => String(r.bank)));
  return (
    <div style={{ width: chartWidth, minWidth: "100%", height: chartHeight }}>
      <ResponsiveContainer width="100%" height="100%" initialDimension={{ width: chartWidth, height: chartHeight }}>
        <BarChart data={data} margin={{ top: 30, right: 24, left: 4, bottom: 8 }}>
          <CartesianGrid strokeDasharray="3 3" strokeOpacity={0.08} vertical={false} />
          <XAxis
            dataKey="bank"
            interval={0}
            height={axisHeight}
            tick={<AxisTick />}
            tickLine={false}
            axisLine={{ stroke: "var(--card-bd)" }}
          />
          <YAxis
            domain={percent ? [0, 100] : undefined}
            ticks={percent ? [0, 25, 50, 75, 100] : undefined}
            tickFormatter={percent ? (v) => `${Math.round(Number(v))}%` : undefined}
            tick={tickStyle}
            tickLine={false}
            axisLine={false}
          />
          <Tooltip {...tooltipProps} formatter={(v) => (percent ? `${Number(v).toFixed(1)}%` : `${v}`)} />
          <Legend verticalAlign="top" wrapperStyle={{ color: "var(--muted-tx)", fontSize: 12, fontWeight: 600 }} />
          {keys.map((k, i) => (
            <Bar
              key={k}
              dataKey={k}
              name={labels?.[k] ?? k}
              stackId="a"
              fill={SERIES_COLORS[i % SERIES_COLORS.length]}
              maxBarSize={40}
              cursor={onSelect ? "pointer" : undefined}
              onClick={onSelect && ((d) => onSelect(String(d.payload?.bank), k))}
              radius={i === keys.length - 1 ? [8, 8, 0, 0] : 0}
            />
          ))}
        </BarChart>
      </ResponsiveContainer>
    </div>
  );
}

function CitationAnalysisSkeleton() {
  return (
    <div className="space-y-6">
      <section className="grid grid-cols-1 gap-4 sm:grid-cols-2 xl:grid-cols-5">
        {Array.from({ length: 5 }, (_, i) => (
          <div key={i} className="h-[148px] animate-pulse rounded-2xl border border-[var(--card-bd)] bg-[var(--card-bg-2)] shadow-sm" />
        ))}
      </section>
      {Array.from({ length: 3 }, (_, i) => (
        <div key={i} className="h-[440px] animate-pulse rounded-2xl border border-[var(--card-bd)] bg-[var(--card-bg-2)] shadow-lg" />
      ))}
    </div>
  );
}

function Pills<T extends string>({ items, value, onChange }: { items: [T, string][]; value: T; onChange: (v: T) => void }) {
  return (
    <div className="inline-flex rounded-full border border-[var(--card-bd)] bg-[var(--card-bg)] p-1">
      {items.map(([v, label]) => (
        <button
          key={v}
          type="button"
          onClick={() => onChange(v)}
          className={`h-8 rounded-full px-4 text-xs font-bold transition ${
            value === v ? "bg-[var(--accent-soft)] text-[var(--accent-tx)]" : "text-[var(--muted-tx)] hover:text-[var(--title-tx)]"
          }`}
        >
          {label}
        </button>
      ))}
    </div>
  );
}

export default function CitationAnalysis({ assistant }: { assistant?: string }) {
  const [tab, setTab] = useState<"analysis" | "explorer">("analysis");
  const [filters, setFilters] = useState<ExplorerFilters>(EMPTY_FILTERS);
  // Chart click-throughs open the Explorer pre-filtered.
  const explore = (patch: Partial<ExplorerFilters>) => {
    setFilters({ ...EMPTY_FILTERS, ...patch });
    setTab("explorer");
  };

  return (
    <div className="space-y-6">
      <Pills
        items={[["analysis", "Citation Analysis"], ["explorer", "Citation Explorer"]]}
        value={tab}
        onChange={setTab}
      />
      {tab === "analysis" ? (
        <Analysis assistant={assistant} explore={explore} />
      ) : (
        <CitationExplorer assistant={assistant} filters={filters} onFilters={setFilters} />
      )}
    </div>
  );
}

function Analysis({ assistant, explore }: { assistant?: string; explore: (patch: Partial<ExplorerFilters>) => void }) {
  const [share, setShare] = useState<"count" | "share">("count");
  // Result is tagged with the assistant it was fetched for, so a filter change shows the skeleton.
  const [result, setResult] = useState<{
    key: string;
    data: CitationAnalysisResponse | null;
  } | null>(null);
  const key = assistant ?? "";
  const loading = result?.key !== key;
  const data = loading ? null : result.data;
  const failed = !loading && !data;

  useEffect(() => {
    let active = true;
    getCitationAnalysis(assistant)
      .then((res) => active && setResult({ key, data: res }))
      .catch(() => active && setResult({ key, data: null }));
    return () => {
      active = false;
    };
  }, [assistant, key]);

  const byAssistant = useMemo(() => pivot(data?.by_bank_assistant ?? [], "llm", undefined, share === "share"), [data, share]);
  const bySection = useMemo(() => pivot(data?.by_bank_section ?? [], "analysis_section"), [data]);
  const catByAssistant = useMemo(
    () => pivot((data?.by_category_assistant ?? []).map((r) => ({ bank: r.llm, category: r.category, citations: r.citations })), "category", undefined, true),
    [data]
  );
  const catByBank = useMemo(() => pivot(data?.by_category_bank ?? [], "category", undefined, true), [data]);
  const mix = useMemo(() => pivot(data?.source_mix ?? [], "kind", KIND_KEYS, true), [data]);

  // Top 10 domains as heatmap columns, in the shape BankCategoryHeatmap expects.
  const heat = useMemo(() => {
    const rows = data?.domain_by_bank ?? [];
    const totals = new Map<string, number>();
    rows.forEach((r) => totals.set(r.domain, (totals.get(r.domain) ?? 0) + r.citations));
    const top = Array.from(totals.entries()).sort((a, b) => b[1] - a[1]).slice(0, 10).map(([d]) => d);
    const grid: Record<string, { bank: string; score: number }[]> = {};
    top.forEach((d) => (grid[d] = []));
    rows.forEach((r) => grid[r.domain]?.push({ bank: r.bank, score: r.citations }));
    return { grid, max: Math.max(1, ...rows.filter((r) => top.includes(r.domain)).map((r) => r.citations)) };
  }, [data]);

  if (loading) return <CitationAnalysisSkeleton />;
  if (failed || !data) {
    return (
      <div className="flex h-[200px] items-center justify-center rounded-2xl border border-[var(--card-bd)] bg-[var(--card-bg)] text-sm text-[var(--muted-tx)] shadow-sm">
        Citation analysis is not available right now.
      </div>
    );
  }

  const tiles = [
    { label: "Total Citations", value: data.kpi.total_citations, note: "All citation rows.", icon: Layers, tone: "bg-emerald-500/15 text-emerald-600" },
    { label: "Bank-Attributed", value: data.kpi.bank_citations, note: "Cited for a single bank.", icon: Store, tone: "bg-blue-500/15 text-blue-600" },
    { label: "Market-Level", value: data.kpi.market_level_citations, note: "Tagged “All Banks”.", icon: Globe, tone: "bg-amber-500/15 text-amber-600" },
    { label: "Unique Domains", value: data.kpi.unique_domains, note: "Distinct source sites.", icon: Link2, tone: "bg-violet-500/15 text-violet-600" },
    { label: "Unique URLs", value: data.kpi.unique_urls, note: "Distinct pages cited.", icon: FileText, tone: "bg-cyan-500/15 text-cyan-600" },
  ];

  const byBankDims = getBarChartDimensions(data.by_bank.map((r) => r.bank));
  const catMax = Math.max(1, ...data.by_category.map((c) => c.citations));
  const topMax = Math.max(1, ...data.top_domains.map((d) => d.citations));

  return (
    <div className="space-y-6">
      <section className="grid grid-cols-1 gap-4 sm:grid-cols-2 xl:grid-cols-5">
        {tiles.map(({ label, value, note, icon: Icon, tone }) => (
          <div key={label} className="rounded-2xl border border-[var(--card-bd)] bg-[var(--card-bg-2)] p-5 shadow-sm">
            <div className={`mb-3 flex h-9 w-9 items-center justify-center rounded-xl ${tone}`}>
              <Icon className="h-5 w-5" />
            </div>
            <p className="text-2xl font-bold text-[var(--title-tx)]">{value.toLocaleString()}</p>
            <p className="mt-1 text-xs font-bold uppercase tracking-[0.1em] text-[var(--muted-tx)]">{label}</p>
            <p className="mt-1 text-sm text-[var(--muted-tx)]">{note}</p>
          </div>
        ))}
      </section>

      <Card
        title="Source Category Distribution"
        description="Share of bank-attributed citations by source type. Select a category to explore its records."
        exportRows={data.by_category}
        filename="citation_source_categories"
      >
        <div className="space-y-3">
          {data.by_category.map((c, i) => (
            <button
              key={c.category}
              type="button"
              onClick={() => explore({ category: c.category })}
              className="flex w-full items-center gap-4 text-left"
            >
              <span className="w-48 shrink-0 text-sm font-semibold text-[var(--title-tx)]">{c.category}</span>
              <span className="h-3 flex-1 rounded-full bg-[var(--card-bd)]">
                <span className="block h-3 rounded-full" style={{ width: `${(c.citations / catMax) * 100}%`, background: SERIES_COLORS[i % SERIES_COLORS.length] }} />
              </span>
              <span className="w-28 shrink-0 text-right text-sm text-[var(--muted-tx)]">
                <b className="text-[var(--title-tx)]">{c.citations.toLocaleString()}</b> · {c.share_pct}%
              </span>
            </button>
          ))}
        </div>
      </Card>

      <Card
        title="Source Categories by AI Assistant"
        description="100% stacked share. Select a segment to open matching records."
        exportRows={data.by_category_assistant}
        filename="citation_categories_by_assistant"
      >
        <BankBars data={catByAssistant.data} keys={catByAssistant.keys} percent onSelect={(_, category) => explore({ category })} />
      </Card>

      <Card
        title="Source Categories by Bank"
        description="Which source types underpin each bank's citations. Select a segment to open matching records."
        exportRows={data.by_category_bank}
        filename="citation_categories_by_bank"
      >
        <BankBars data={catByBank.data} keys={catByBank.keys} percent onSelect={(bank, category) => explore({ bank, category })} />
      </Card>

      <Card
        title="Citations by Bank"
        description="Citations attributed to each bank, with share of all bank-attributed citations. Select a bar to explore its records."
        exportRows={data.by_bank}
        filename="citations_by_bank"
      >
        <div style={{ width: byBankDims.chartWidth, minWidth: "100%", height: byBankDims.chartHeight }}>
          <ResponsiveContainer width="100%" height="100%" initialDimension={{ width: byBankDims.chartWidth, height: byBankDims.chartHeight }}>
            <BarChart data={data.by_bank} margin={{ top: 30, right: 24, left: 4, bottom: 8 }}>
              <CartesianGrid strokeDasharray="3 3" strokeOpacity={0.08} vertical={false} />
              <XAxis dataKey="bank" interval={0} height={byBankDims.axisHeight} tick={<AxisTick />} tickLine={false} axisLine={{ stroke: "var(--card-bd)" }} />
              <YAxis tick={tickStyle} tickLine={false} axisLine={false} />
              <Tooltip
                {...tooltipProps}
                formatter={(v, _n, item) => [
                  `${v} (${item.payload.share_pct}%) · ${item.payload.unique_domains} domains · ${item.payload.unique_urls} URLs`,
                  "Citations",
                ]}
              />
              <Bar dataKey="citations" radius={[8, 8, 0, 0]} maxBarSize={40} cursor="pointer" onClick={(d) => explore({ bank: String(d.payload?.bank) })}>
                {data.by_bank.map((r, i) => (
                  <Cell key={r.bank} fill={getBankColor(r.bank, i)} />
                ))}
                <LabelList dataKey="citations" position="top" style={{ fill: "var(--muted-tx)", fontSize: 13, fontWeight: 700 }} />
              </Bar>
            </BarChart>
          </ResponsiveContainer>
        </div>
      </Card>

      <Card
        title="Citations by AI Assistant"
        description="How each assistant contributes to a bank's citations. Switch to Share for a 100% stacked view."
        exportRows={data.by_bank_assistant}
        filename="citations_by_bank_assistant"
        actions={<Pills items={[["count", "Count"], ["share", "Share"]]} value={share} onChange={setShare} />}
      >
        <BankBars data={byAssistant.data} keys={byAssistant.keys} percent={share === "share"} />
      </Card>

      <Card
        title="Citations by Analysis Section"
        description="Which part of the analysis each bank's citations come from."
        exportRows={data.by_bank_section}
        filename="citations_by_bank_section"
      >
        <BankBars data={bySection.data} keys={bySection.keys} />
      </Card>

      <Card
        title="Source Mix"
        description="Share of each bank's citations from its own site, another bank's site, or third parties."
        exportRows={data.source_mix}
        filename="citation_source_mix"
      >
        <BankBars data={mix.data} keys={KIND_KEYS} labels={KIND_LABELS} percent />
      </Card>

      <Card
        title="Top 10 Cited Domains"
        description="Most frequently cited source domains across all banks."
        exportRows={data.top_domains.map((d) => ({ ...d, assistants: d.assistants?.join("; "), sections: d.sections?.join("; ") }))}
        filename="top_cited_domains"
      >
        <div className="overflow-x-auto">
          <table className="w-full min-w-[820px] text-left text-sm">
            <thead>
              <tr className="border-b border-[var(--card-bd)] text-xs font-bold uppercase tracking-[0.1em] text-[var(--muted-tx)]">
                {["Rank", "Domain", "Assistants", "Sections", "Banks", "Citations", ""].map((h) => (
                  <th key={h} className="px-3 py-3">{h}</th>
                ))}
              </tr>
            </thead>
            <tbody>
              {data.top_domains.slice(0, 10).map((d, i) => (
                <tr key={d.domain} className="border-b border-[var(--card-bd)] last:border-0">
                  <td className="px-3 py-3 font-bold text-[var(--muted-tx)]">{i + 1}</td>
                  <td className="px-3 py-3 font-semibold text-[var(--title-tx)]">{d.domain}</td>
                  <td className="px-3 py-3 text-[var(--body-tx)]">{d.assistants?.join(", ") || "—"}</td>
                  <td className="px-3 py-3 text-[var(--body-tx)]">{d.sections?.join(", ") || "—"}</td>
                  <td className="px-3 py-3 text-[var(--body-tx)]">{d.banks}</td>
                  <td className="w-[34%] px-3 py-3">
                    <div className="flex items-center gap-3">
                      <div className="h-2 flex-1 rounded-full bg-[var(--card-bd)]">
                        <div className="h-2 rounded-full bg-[var(--accent-from)]" style={{ width: `${(d.citations / topMax) * 100}%` }} />
                      </div>
                      <span className="w-10 text-right font-bold text-[var(--title-tx)]">{d.citations}</span>
                    </div>
                  </td>
                  <td className="px-3 py-3 text-right">
                    <button type="button" onClick={() => explore({ search: d.domain })} className="inline-flex items-center gap-1 text-xs font-bold text-[var(--accent-tx)] hover:underline">
                      Explore <ExternalLink className="h-3 w-3" />
                    </button>
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      </Card>

      <BankCategoryHeatmap
        title="Top Domains by Bank"
        description="Citations from the 10 most-cited domains, per bank."
        data={heat.grid}
        excludeKeys={[]}
        scaleMax={heat.max}
        filenamePrefix="top_domains_by_bank"
      />
    </div>
  );
}
