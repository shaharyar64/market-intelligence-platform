"use client";

import { useCallback, useEffect, useId, useMemo, useRef, useState } from "react";
import { AlertCircle, Bell, Check, ChevronDown, RotateCw, Search } from "lucide-react";

import type { BrandSummary } from "@/lib/foodIntelligence";

export function TopbarSearch() {
  return (
    <div className="hidden items-center gap-2 md:flex">
      <div className="relative">
        <Search size={14} className="pointer-events-none absolute left-3 top-1/2 -translate-y-1/2" style={{ color: "var(--muted-tx)" }} />
        <input
          disabled
          aria-hidden="true"
          tabIndex={-1}
          placeholder="Search trends, brands, personas"
          style={{ background: "var(--card-bg)", border: "1px solid var(--card-bd)", color: "var(--title-tx)", backdropFilter: "var(--blur)" }}
          className="w-64 cursor-not-allowed rounded-full py-2 pl-9 pr-4 text-sm opacity-60 placeholder:text-[var(--muted-tx)]"
        />
      </div>
      <button
        type="button"
        disabled
        aria-label="Notifications"
        title="Notifications (preview)"
        style={{ background: "var(--card-bg)", border: "1px solid var(--card-bd)", color: "var(--muted-tx)" }}
        className="flex h-10 w-10 cursor-not-allowed items-center justify-center rounded-full opacity-60"
      >
        <Bell size={16} aria-hidden="true" />
      </button>
    </div>
  );
}

export function Skel({ className = "", style }: { className?: string; style?: React.CSSProperties }) {
  return (
    <div
      aria-hidden="true"
      className={`animate-pulse rounded-lg ${className}`}
      style={{ background: "var(--card-bg-2)", ...style }}
    />
  );
}

export function BarRowsSkeleton({ rows = 8 }: { rows?: number }) {
  return (
    <div className="space-y-4">
      {Array.from({ length: rows }).map((_, i) => (
        <div key={i} className="space-y-1.5">
          <div className="flex items-center justify-between gap-3">
            <Skel className="h-3.5" style={{ width: `${38 + ((i * 13) % 34)}%` }} />
            <Skel className="h-3 w-8" />
          </div>
          <Skel className="h-2 w-full rounded-full" />
        </div>
      ))}
    </div>
  );
}

export function InlineBarsSkeleton({ rows = 5 }: { rows?: number }) {
  return (
    <div className="space-y-4">
      {Array.from({ length: rows }).map((_, i) => (
        <div key={i} className="flex items-center gap-3">
          <Skel className="h-3.5 w-28 shrink-0 xl:w-40" />
          <Skel className="h-3 flex-1 rounded-full" />
          <Skel className="h-3 w-8 shrink-0" />
        </div>
      ))}
    </div>
  );
}

export function ChartSkeleton({ height = 224 }: { height?: number }) {
  return <Skel className="w-full rounded-xl" style={{ height }} />;
}

export function CardGridSkeleton({
  count = 6,
  className = "grid grid-cols-1 gap-5 md:grid-cols-2 xl:grid-cols-3",
  height = 232,
}: { count?: number; className?: string; height?: number }) {
  return (
    <div className={className} aria-hidden="true">
      {Array.from({ length: count }).map((_, i) => (
        <div key={i} className="chart-card rounded-2xl p-5" style={{ height }}>
          <div className="flex items-start justify-between gap-3">
            <Skel className="h-4 w-1/2" />
            <Skel className="h-5 w-16 rounded-full" />
          </div>
          <Skel className="mt-4 h-12 w-full" />
          <Skel className="mt-4 h-3 w-full" />
          <Skel className="mt-2 h-3 w-4/5" />
        </div>
      ))}
    </div>
  );
}

export function LoadingAnnouncer({ label }: { label: string }) {
  return <span role="status" aria-live="polite" className="sr-only">{label}</span>;
}

export function EmptyNote({
  message,
  minHeight = 220,
  carded = false,
}: {
  message: string;
  minHeight?: number;
  carded?: boolean;
}) {
  const inner = (
    <div className="flex w-full items-center justify-center text-center" style={{ minHeight }}>
      <p style={{ color: "var(--muted-tx)" }} className="max-w-xs text-sm">{message}</p>
    </div>
  );
  return carded ? <div className="chart-card rounded-2xl p-6">{inner}</div> : inner;
}

export function InlineError({ message, onRetry }: { message: string; onRetry?: () => void }) {
  return (
    <div
      role="alert"
      className="flex flex-wrap items-center gap-2 rounded-xl px-4 py-3 text-sm"
      style={{ background: "rgba(190,18,60,0.08)", border: "1px solid rgba(190,18,60,0.25)", color: "var(--fi-danger-tx)" }}
    >
      <AlertCircle size={16} aria-hidden="true" className="shrink-0" />
      <span className="min-w-0">{message}</span>
      {onRetry && (
        <button
          type="button"
          onClick={onRetry}
          style={{ border: "1px solid rgba(190,18,60,0.35)", color: "var(--fi-danger-tx)" }}
          className="ml-auto inline-flex shrink-0 items-center gap-1.5 rounded-full px-3 py-1.5 text-xs font-semibold"
        >
          <RotateCw size={12} aria-hidden="true" /> Try again
        </button>
      )}
    </div>
  );
}

export function PanelState({
  loading,
  error,
  isEmpty,
  emptyNote,
  emptyMinHeight = 220,
  skeleton,
  loadingLabel,
  onRetry,
  children,
}: {
  loading: boolean;
  error: string | null;
  isEmpty: boolean;
  emptyNote: string;
  emptyMinHeight?: number;
  skeleton: React.ReactNode;
  loadingLabel: string;
  onRetry?: () => void;
  children: React.ReactNode;
}) {
  if (loading) return <>{skeleton}<LoadingAnnouncer label={loadingLabel} /></>;
  if (error) return <InlineError message={error} onRetry={onRetry} />;
  if (isEmpty) return <EmptyNote message={emptyNote} minHeight={emptyMinHeight} />;
  return <>{children}</>;
}

export function radarTickFill(): string {
  if (typeof window === "undefined") return "#475569";
  return getComputedStyle(document.documentElement).getPropertyValue("--chart-tick").trim() || "#475569";
}

export function chartGridStroke(): string {
  if (typeof window === "undefined") return "rgba(71,85,105,0.22)";
  return getComputedStyle(document.documentElement).getPropertyValue("--chart-grid").trim() || "rgba(71,85,105,0.22)";
}

const BRAND_SELECT_FILTER_THRESHOLD = 8;

export function BrandSelect({
  brands,
  value,
  onChange,
  loading = false,
  label = "Select a brand",
  placeholder = "Select a brand",
  multiple = false,
  values,
  onChangeMany,
}: {
  brands: BrandSummary[];
  value: string;
  onChange: (key: string) => void;
  loading?: boolean;
  label?: string;
  placeholder?: string;
  /** Compare several accounts at once. Single-select stays the default so the
   *  brand pages are unaffected. */
  multiple?: boolean;
  values?: string[];
  onChangeMany?: (keys: string[]) => void;
}) {
  const selected = multiple ? (values ?? []) : (value ? [value] : []);
  const isPicked = (key: string) => selected.includes(key);

  const pick = useCallback((key: string) => {
    if (!multiple) { onChange(key); return; }
    const next = (multiple ? (values ?? []) : []).includes(key)
      ? (values ?? []).filter((k) => k !== key)
      : [...(values ?? []), key];
    onChangeMany?.(next);
  }, [multiple, onChange, onChangeMany, values]);

  // Clearing the selection had no control: once you chose an account there was
  // no way back to the whole cohort short of reloading the page.
  const clear = () => { if (multiple) onChangeMany?.([]); else onChange(""); };
  const [open, setOpen] = useState(false);
  const [query, setQuery] = useState("");
  const [activeIndex, setActiveIndex] = useState(0);

  const rootRef = useRef<HTMLDivElement>(null);
  const triggerRef = useRef<HTMLButtonElement>(null);
  const listRef = useRef<HTMLUListElement>(null);
  const searchRef = useRef<HTMLInputElement>(null);
  const baseId = useId();
  const listId = `${baseId}-list`;
  const optionId = (i: number) => (i < 0 ? `${baseId}-opt-all` : `${baseId}-opt-${i}`);

  const showFilter = brands.length > BRAND_SELECT_FILTER_THRESHOLD;
  const disabled = loading || brands.length === 0;

  const options = useMemo(() => {
    const q = query.trim().toLowerCase();
    if (!q) return brands;
    return brands.filter((b) => b.name.toLowerCase().includes(q));
  }, [brands, query]);

  const close = useCallback((focusTrigger: boolean) => {
    setOpen(false);
    setQuery("");
    if (focusTrigger) triggerRef.current?.focus();
  }, []);

  const openMenu = useCallback(() => {
    if (disabled) return;
    const idx = brands.findIndex((b) => b.key === value);
    setQuery("");
    setActiveIndex(idx >= 0 ? idx : multiple ? -1 : 0);
    setOpen(true);
  }, [brands, disabled, value, multiple]);

  useEffect(() => {
    if (!open) return;
    const onPointerDown = (e: MouseEvent) => {
      if (rootRef.current && !rootRef.current.contains(e.target as Node)) close(false);
    };
    document.addEventListener("mousedown", onPointerDown);
    return () => document.removeEventListener("mousedown", onPointerDown);
  }, [open, close]);

  useEffect(() => {
    if (!open) return;
    if (showFilter) searchRef.current?.focus();
    else listRef.current?.focus();
  }, [open, showFilter]);

  useEffect(() => {
    if (!open) return;
    const node = listRef.current?.querySelector<HTMLElement>(`[data-index="${activeIndex}"]`);
    node?.scrollIntoView({ block: "nearest" });
  }, [open, activeIndex]);

  const handlePopoverKeyDown = (e: React.KeyboardEvent<HTMLDivElement>) => {
    if (e.key === "Escape") {
      e.preventDefault();
      close(true);
      return;
    }
    if (e.key === "Tab") {
      close(false);
      return;
    }
    if (options.length === 0) return;
    const wrap = (i: number) => (i < -1 ? options.length - 1 : i >= options.length ? -1 : i);
    if (e.key === "ArrowDown") {
      e.preventDefault();
      setActiveIndex((i) => wrap(i + 1));
      return;
    }
    if (e.key === "ArrowUp") {
      e.preventDefault();
      setActiveIndex((i) => wrap(i - 1));
      return;
    }
    if (e.key === "Home" && !showFilter) {
      e.preventDefault();
      setActiveIndex(-1);
      return;
    }
    if (e.key === "End" && !showFilter) {
      e.preventDefault();
      setActiveIndex(options.length - 1);
      return;
    }
    if (e.key === "Enter" || e.key === " ") {
      e.preventDefault();
      if (activeIndex === -1) { clear(); if (!multiple) close(true); return; }
      const opt = options[activeIndex];
      if (!opt) return;
      pick(opt.key);
      if (!multiple) close(true);
    }
  };

  const handleTriggerKeyDown = (e: React.KeyboardEvent<HTMLButtonElement>) => {
    if (open) return;
    if (e.key === "ArrowDown" || e.key === "ArrowUp") {
      e.preventDefault();
      openMenu();
    }
  };

  const triggerLabel = loading
    ? "Loading accounts"
    : brands.length === 0
      ? "No accounts available"
      : selected.length === 0
        ? placeholder
        : selected.length === 1
          ? (brands.find((b) => b.key === selected[0])?.name ?? placeholder)
          : `${selected.length} accounts`;

  return (
    <div ref={rootRef} className="relative w-full sm:w-72">
      <button
        ref={triggerRef}
        type="button"
        disabled={disabled}
        aria-haspopup="listbox"
        aria-expanded={open}
        aria-controls={open ? listId : undefined}
        aria-label={label}
        onClick={() => (open ? close(false) : openMenu())}
        onKeyDown={handleTriggerKeyDown}
        style={{
          background: "var(--card-bg)",
          border: "1px solid var(--card-bd)",
          color: "var(--title-tx)",
          backdropFilter: "var(--blur)",
        }}
        className="flex min-h-11 w-full items-center justify-between gap-2 rounded-xl px-4 py-2.5 text-sm font-semibold transition-colors disabled:cursor-not-allowed disabled:opacity-60"
      >
        <span className="flex min-w-0 items-center gap-2">
          {loading && (
            <Skel className="h-3.5 w-3.5 shrink-0 rounded-full" />
          )}
          <span dir="auto" className="truncate">{triggerLabel}</span>
        </span>
        <ChevronDown
          size={16}
          aria-hidden="true"
          className="shrink-0"
          style={{ color: "var(--muted-tx)", transform: open ? "rotate(180deg)" : undefined, transition: "transform 150ms" }}
        />
      </button>

      {open && (
        <div
          onKeyDown={handlePopoverKeyDown}
          style={{
            background: "var(--dropdown-bg)",
            border: "1px solid var(--dropdown-bd)",
            boxShadow: "var(--card-shadow)",
          }}
          className="absolute z-40 mt-2 w-full overflow-hidden rounded-xl p-1"
        >
          {showFilter && (
            <div className="relative p-1">
              <Search
                size={14}
                aria-hidden="true"
                className="pointer-events-none absolute left-3.5 top-1/2 -translate-y-1/2"
                style={{ color: "var(--muted-tx)" }}
              />
              <input
                ref={searchRef}
                type="text"
                value={query}
                onChange={(e) => { setQuery(e.target.value); setActiveIndex(0); }}
                aria-label="Filter brands by name"
                aria-controls={listId}
                aria-activedescendant={options.length ? optionId(activeIndex) : undefined}
                placeholder="Filter brands"
                style={{
                  background: "var(--dropdown-bg-2)",
                  border: "1px solid var(--dropdown-bd)",
                  color: "var(--title-tx)",
                }}
                className="w-full rounded-lg py-2 pl-8 pr-3 text-sm placeholder:text-[var(--muted-tx)]"
              />
            </div>
          )}

          {options.length === 0 ? (
            <p style={{ color: "var(--muted-tx)" }} className="px-3 py-4 text-center text-xs">
              No brands match that filter.
            </p>
          ) : (
            <ul
              ref={listRef}
              id={listId}
              role="listbox"
              tabIndex={-1}
              aria-label={label}
              aria-multiselectable={multiple || undefined}
              aria-activedescendant={optionId(activeIndex)}
              className="max-h-72 overflow-y-auto outline-none"
            >
              <li
                id={optionId(-1)}
                role="option"
                aria-selected={selected.length === 0}
                data-index={-1}
                onMouseEnter={() => setActiveIndex(-1)}
                onClick={() => { clear(); if (!multiple) close(true); }}
                style={{
                  background: activeIndex === -1 ? "var(--dropdown-bg-2)" : "transparent",
                  color: "var(--body-tx)",
                }}
                className="flex min-h-11 cursor-pointer items-center gap-2 rounded-lg px-3 py-2 text-sm"
              >
                <span className="flex w-4 shrink-0 justify-center">
                  {selected.length === 0 && (
                    <Check size={14} aria-hidden="true" style={{ color: "var(--accent-tx)" }} />
                  )}
                </span>
                <span className={`min-w-0 flex-1 truncate ${selected.length === 0 ? "font-semibold" : ""}`}>
                  All accounts
                </span>
              </li>
              {options.map((b, i) => {
                const isSelected = isPicked(b.key);
                const isActive = i === activeIndex;
                return (
                  <li
                    key={b.key}
                    id={optionId(i)}
                    role="option"
                    aria-selected={isSelected}
                    data-index={i}
                    onMouseEnter={() => setActiveIndex(i)}
                    // Multi-select stays open: picking three accounts should not
                    // mean opening the menu three times.
                    onClick={() => { pick(b.key); if (!multiple) close(true); }}
                    style={{
                      background: isActive ? "var(--dropdown-bg-2)" : "transparent",
                      color: "var(--body-tx)",
                    }}
                    className="flex min-h-11 cursor-pointer items-center gap-2 rounded-lg px-3 py-2 text-sm"
                  >
                    <span className="flex w-4 shrink-0 justify-center">
                      {isSelected && <Check size={14} aria-hidden="true" style={{ color: "var(--accent-tx)" }} />}
                    </span>
                    <span dir="auto" className={`min-w-0 flex-1 truncate ${isSelected ? "font-semibold" : ""}`}>
                      {b.name}
                    </span>
                  </li>
                );
              })}
            </ul>
          )}
        </div>
      )}
    </div>
  );
}
