"use client";

import { useEffect, useMemo, useState } from "react";
import { ExternalLink, Search, X } from "lucide-react";
import ExportExcelButton from "@/components/ui/ExportExcelButton";
import { getAiScoreCitations, type AiScoreCitationItem } from "@/lib/bankBrandHealth";

export type ExplorerFilters = { search: string; bank: string; section: string; category: string };
export const EMPTY_FILTERS: ExplorerFilters = { search: "", bank: "", section: "", category: "" };

const PAGE_SIZE = 15;
const fieldClass =
  "h-10 w-full rounded-xl border border-[var(--card-bd)] bg-[var(--select-bg)] px-3 text-sm text-[var(--select-fg)] outline-none focus:border-[var(--accent-from)]";

type Source = {
  url: string;
  title: string;
  domain: string;
  category: string;
  banks: string[];
  sections: string[];
  assistants: string[];
  count: number;
};

const domainOf = (url: string) => {
  try {
    return new URL(url).hostname.replace(/^www\./, "");
  } catch {
    return url;
  }
};
// Titles are sometimes junk: a bare index ("3") or the bare domain/URL echoed back.
const isRealTitle = (t?: string | null) => !!t && !/^\d+$/.test(t.trim()) && !/^(https?:\/\/)?(www\.)?[^\s/]+\.[a-z]{2,}\/?$/i.test(t.trim());
const uniq = (v: (string | null | undefined)[]) => Array.from(new Set(v.filter(Boolean) as string[])).sort();

function Select({ label, value, options, onChange }: { label: string; value: string; options: string[]; onChange: (v: string) => void }) {
  return (
    <label className="flex flex-col gap-1.5">
      <span className="text-xs font-bold uppercase tracking-[0.1em] text-[var(--muted-tx)]">{label}</span>
      <select value={value} onChange={(e) => onChange(e.target.value)} className={fieldClass}>
        <option value="">All</option>
        {options.map((o) => (
          <option key={o} value={o}>{o}</option>
        ))}
      </select>
    </label>
  );
}

export default function CitationExplorer({
  assistant,
  filters,
  onFilters,
}: {
  assistant?: string;
  filters: ExplorerFilters;
  onFilters: (f: ExplorerFilters) => void;
}) {
  const key = assistant ?? "";
  const [result, setResult] = useState<{ key: string; rows: AiScoreCitationItem[] | null } | null>(null);
  const [sort, setSort] = useState<"count" | "title">("count");
  const [page, setPage] = useState(0);
  const loading = result?.key !== key;
  const rows = loading ? null : result.rows;

  useEffect(() => {
    let active = true;
    getAiScoreCitations(assistant)
      .then((res) => active && setResult({ key, rows: res.citations }))
      .catch(() => active && setResult({ key, rows: null }));
    return () => {
      active = false;
    };
  }, [assistant, key]);

  const set = (patch: Partial<ExplorerFilters>) => {
    onFilters({ ...filters, ...patch });
    setPage(0);
  };

  const banks = useMemo(() => uniq((rows ?? []).map((r) => r.bank)), [rows]);
  const categories = useMemo(() => uniq((rows ?? []).map((r) => r.category)), [rows]);
  const sections = useMemo(() => uniq((rows ?? []).map((r) => r.analysis_section)), [rows]);

  const sources = useMemo(() => {
    const q = filters.search.trim().toLowerCase();
    const map = new Map<string, Source & { b: Set<string>; s: Set<string>; a: Set<string> }>();
    (rows ?? []).forEach((r) => {
      if (filters.bank && r.bank !== filters.bank) return;
      if (filters.category && r.category !== filters.category) return;
      if (filters.section && r.analysis_section !== filters.section) return;
      const domain = domainOf(r.url);
      if (q && !`${r.title} ${domain} ${r.url}`.toLowerCase().includes(q)) return;
      const s = map.get(r.url) ?? { url: r.url, title: "", domain, category: r.category ?? "", banks: [], sections: [], assistants: [], count: 0, b: new Set(), s: new Set(), a: new Set() };
      if (!s.title && isRealTitle(r.title)) s.title = r.title.trim();
      s.count += 1;
      if (r.bank) s.b.add(r.bank);
      if (r.analysis_section) s.s.add(r.analysis_section);
      if (r.llm) s.a.add(r.llm);
      map.set(r.url, s);
    });
    const list = Array.from(map.values()).map((s) => ({ ...s, banks: [...s.b].sort(), sections: [...s.s].sort(), assistants: [...s.a].sort() }));
    return list.sort((x, y) => (sort === "count" ? y.count - x.count || x.title.localeCompare(y.title) : x.title.localeCompare(y.title)));
  }, [rows, filters, sort]);

  if (loading) return <div className="h-[440px] animate-pulse rounded-2xl border border-[var(--card-bd)] bg-[var(--card-bg-2)] shadow-lg" />;
  if (!rows) {
    return (
      <div className="flex h-[200px] items-center justify-center rounded-2xl border border-[var(--card-bd)] bg-[var(--card-bg)] text-sm text-[var(--muted-tx)] shadow-sm">
        Citation records are not available right now.
      </div>
    );
  }

  const appearances = sources.reduce((n, s) => n + s.count, 0);
  const pages = Math.max(1, Math.ceil(sources.length / PAGE_SIZE));
  const current = Math.min(page, pages - 1);
  const visible = sources.slice(current * PAGE_SIZE, (current + 1) * PAGE_SIZE);
  const chips = (Object.entries(filters) as [keyof ExplorerFilters, string][]).filter(([, v]) => v);
  const chipLabel = { search: "Search", bank: "Bank", section: "Section", category: "Category" };

  return (
    <section className="rounded-2xl border border-[var(--card-bd)] bg-[var(--card-bg-2)] p-6 shadow-lg">
      <div className="mb-5 flex flex-col gap-3 sm:flex-row sm:items-start sm:justify-between">
        <div>
          <h2 className="text-lg font-semibold text-[var(--title-tx)]">Citation Explorer</h2>
          <p className="mt-1 text-sm text-[var(--muted-tx)]">
            {sources.length.toLocaleString()} sources · {appearances.toLocaleString()} appearances
          </p>
        </div>
        <ExportExcelButton
          filename="citation_explorer"
          sheetName="Citation Explorer"
          rows={sources.map((s) => ({
            title: s.title || s.domain,
            url: s.url,
            domain: s.domain,
            category: s.category,
            appearances: s.count,
            banks: s.banks.join("; "),
            sections: s.sections.join("; "),
            assistants: s.assistants.join("; "),
          }))}
        />
      </div>

      <div className="grid gap-3 sm:grid-cols-2 lg:grid-cols-5">
        <label className="flex flex-col gap-1.5">
          <span className="text-xs font-bold uppercase tracking-[0.1em] text-[var(--muted-tx)]">Search</span>
          <span className="relative">
            <Search className="pointer-events-none absolute left-3 top-1/2 h-4 w-4 -translate-y-1/2 text-[var(--muted-tx)]" />
            <input
              type="search"
              value={filters.search}
              onChange={(e) => set({ search: e.target.value })}
              placeholder="Title or domain"
              className={`${fieldClass} pl-9`}
            />
          </span>
        </label>
        <Select label="Bank" value={filters.bank} options={banks} onChange={(bank) => set({ bank })} />
        <Select label="Source category" value={filters.category} options={categories} onChange={(category) => set({ category })} />
        <Select label="Analysis section" value={filters.section} options={sections} onChange={(section) => set({ section })} />
        <label className="flex flex-col gap-1.5">
          <span className="text-xs font-bold uppercase tracking-[0.1em] text-[var(--muted-tx)]">Sort by</span>
          <select value={sort} onChange={(e) => setSort(e.target.value as "count" | "title")} className={fieldClass}>
            <option value="count">Most appearances</option>
            <option value="title">Title A–Z</option>
          </select>
        </label>
      </div>

      {chips.length > 0 && (
        <div className="mt-4 flex flex-wrap items-center gap-2">
          {chips.map(([k, v]) => (
            <button
              key={k}
              type="button"
              onClick={() => set({ [k]: "" })}
              className="inline-flex items-center gap-1.5 rounded-full border border-[var(--accent-soft-bd)] bg-[var(--accent-soft)] px-3 py-1 text-xs font-semibold text-[var(--accent-tx)]"
            >
              {chipLabel[k]}: {v}
              <X className="h-3 w-3" />
            </button>
          ))}
          <button type="button" onClick={() => set(EMPTY_FILTERS)} className="text-xs font-semibold text-[var(--muted-tx)] underline">
            Clear all
          </button>
        </div>
      )}

      <div className="mt-5 overflow-x-auto rounded-2xl border border-[var(--card-bd)] bg-[var(--card-bg)] shadow-sm">
        <table className="w-full min-w-[860px] text-left text-sm">
          <thead>
            <tr className="border-b border-[var(--card-bd)] text-xs font-bold uppercase tracking-[0.1em] text-[var(--muted-tx)]">
              {["Source", "Category", "Banks", "Sections", "Appearances", "Assistants"].map((h) => (
                <th key={h} className="px-4 py-3">{h}</th>
              ))}
            </tr>
          </thead>
          <tbody>
            {visible.map((s) => (
              <tr key={s.url} className="border-b border-[var(--card-bd)] align-top last:border-0">
                <td className="max-w-[340px] px-4 py-3">
                  <a href={s.url} target="_blank" rel="noopener noreferrer" className="inline-flex items-start gap-1.5 font-semibold text-[var(--title-tx)] hover:text-[var(--accent-tx)]">
                    <span className="line-clamp-2">{s.title || s.domain}</span>
                    <ExternalLink className="mt-0.5 h-3.5 w-3.5 shrink-0" />
                  </a>
                  <p className="mt-0.5 truncate text-xs text-[var(--muted-tx)]">{s.domain}</p>
                </td>
                <td className="px-4 py-3 text-[var(--body-tx)]">{s.category || "—"}</td>
                <td className="px-4 py-3 text-[var(--body-tx)]">{s.banks.join(", ") || "—"}</td>
                <td className="px-4 py-3 text-[var(--body-tx)]">{s.sections.join(", ") || "—"}</td>
                <td className="px-4 py-3 font-bold text-[var(--title-tx)]">{s.count}</td>
                <td className="px-4 py-3 text-[var(--body-tx)]">{s.assistants.join(", ") || "—"}</td>
              </tr>
            ))}
            {!visible.length && (
              <tr>
                <td colSpan={6} className="px-4 py-10 text-center text-[var(--muted-tx)]">No citation records match these filters.</td>
              </tr>
            )}
          </tbody>
        </table>
      </div>

      <div className="mt-4 flex items-center justify-between text-sm text-[var(--muted-tx)]">
        <span>Page {current + 1} of {pages}</span>
        <div className="flex gap-2">
          {[
            ["Previous", current - 1, current === 0],
            ["Next", current + 1, current >= pages - 1],
          ].map(([label, to, off]) => (
            <button
              key={label as string}
              type="button"
              disabled={off as boolean}
              onClick={() => setPage(to as number)}
              className="h-9 rounded-full border border-[var(--card-bd)] bg-[var(--card-bg)] px-4 font-semibold text-[var(--title-tx)] disabled:cursor-not-allowed disabled:opacity-50"
            >
              {label as string}
            </button>
          ))}
        </div>
      </div>
    </section>
  );
}
