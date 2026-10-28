"use client";

import { useState } from "react";
import { Calendar, Search, X } from "lucide-react";
import { countActiveFilters } from "@/lib/dashboardUi";

interface FilterOption {
  label: string;
  value: string;
}

export type DashboardFilterValues = {
  search: string;
  selected: string;
  startDate: string;
  endDate: string;
};

interface DashboardFiltersProps {
  title?: string;
  selectOptions?: FilterOption[];
  onApply?: (filters: DashboardFilterValues) => void;
}

export default function DashboardFilters({
  title = "Filters",
  selectOptions = [],
  onApply,
}: DashboardFiltersProps) {
  const [search, setSearch] = useState("");
  const [selected, setSelected] = useState("");
  const [startDate, setStartDate] = useState("");
  const [endDate, setEndDate] = useState("");

  function handleApply() {
    onApply?.({
      search,
      selected,
      startDate,
      endDate,
    });
  }

  function handleReset() {
    setSearch("");
    setSelected("");
    setStartDate("");
    setEndDate("");
    onApply?.({ search: "", selected: "", startDate: "", endDate: "" });
  }

  const activeFilterCount = countActiveFilters({ search, selected, startDate, endDate });

  return (
    <section
      aria-label={title}
      className="dashboard-filter-panel relative rounded-2xl border p-4 sm:p-6"
      style={{ background: "var(--card-bg)", borderColor: "var(--card-bd)", boxShadow: "var(--card-shadow)" }}
    >
      
      {/* Header */}
      <div className="flex items-center justify-between mb-6">
        <div className="flex items-center gap-2">
          <h3 style={{ color: "var(--title-tx)" }} className="text-sm font-semibold">{title}</h3>
          {activeFilterCount > 0 && (
            <span className="rounded-full px-2 py-0.5 text-xs font-semibold" style={{ background: "var(--accent-soft)", color: "var(--accent-tx)" }}>
              {activeFilterCount} active
            </span>
          )}
        </div>

        <button
          onClick={handleReset}
          type="button"
          disabled={activeFilterCount === 0}
          className="flex items-center gap-1 text-xs transition-colors disabled:cursor-not-allowed disabled:opacity-50"
          style={{ color: "var(--muted-tx)" }}
        >
          <X size={14} aria-hidden="true" />
          Reset
        </button>
      </div>

      {/* Filters Grid */}
      <div className="grid grid-cols-1 gap-4 md:grid-cols-2 xl:grid-cols-4">

        {/* Search */}
        <div className="relative">
          <Search
            size={16}
            className="absolute left-3 top-1/2 -translate-y-1/2 text-slate-400"
          />
          <input
            type="text"
            placeholder="Search..."
            value={search}
            onChange={(e) => setSearch(e.target.value)}
            aria-label="Search filters"
            className="w-full rounded-xl border px-9 py-2 text-sm transition-colors"
            style={{ background: "var(--select-bg)", borderColor: "var(--card-bd)", color: "var(--select-fg)" }}
          />
        </div>

        {/* Dropdown */}
        <select
          value={selected}
          onChange={(e) => setSelected(e.target.value)}
          aria-label="Filter option"
          className="rounded-xl border px-4 py-2 text-sm transition-colors"
          style={{ background: "var(--select-bg)", borderColor: "var(--card-bd)", color: "var(--select-fg)" }}
        >
          <option value="">Select Option</option>
          {selectOptions.map((opt) => (
            <option key={opt.value} value={opt.value}>
              {opt.label}
            </option>
          ))}
        </select>

        {/* Start Date */}
        <div className="relative">
          <Calendar
            size={16}
            className="absolute left-3 top-1/2 -translate-y-1/2 text-slate-400"
          />
          <input
            type="date"
            value={startDate}
            onChange={(e) => setStartDate(e.target.value)}
            aria-label="Start date"
            className="w-full rounded-xl border py-2 pl-9 pr-4 text-sm transition-colors"
            style={{ background: "var(--select-bg)", borderColor: "var(--card-bd)", color: "var(--select-fg)" }}
          />
        </div>

        {/* End Date */}
        <input
          type="date"
          value={endDate}
          onChange={(e) => setEndDate(e.target.value)}
          aria-label="End date"
          className="rounded-xl border px-4 py-2 text-sm transition-colors"
          style={{ background: "var(--select-bg)", borderColor: "var(--card-bd)", color: "var(--select-fg)" }}
        />
      </div>

      {/* Apply Button */}
      <div className="flex justify-end mt-6">
        <button
          type="button"
          onClick={handleApply}
          className="px-6 py-2 rounded-xl bg-gradient-to-r from-blue-500 to-cyan-500 text-white text-sm font-medium shadow-md hover:opacity-90 transition"
        >
          Apply Filters
        </button>
      </div>
    </section>
  );
}
