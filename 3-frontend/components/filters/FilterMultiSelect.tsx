"use client";

import { useEffect, useMemo, useRef, useState } from "react";
import { Check, ChevronDown, X } from "lucide-react";

interface Option {
  label: string;
  value: string;
}

interface Props {
  label: string;
  values: string[];
  options: Option[];
  onChange: (values: string[]) => void;
  allLabel?: string;
  maxValues?: number;
}

export default function FilterMultiSelect({
  label,
  values,
  options = [],
  onChange,
  allLabel = `All ${label}s`,
  maxValues,
}: Props) {
  const [open, setOpen] = useState(false);
  const [query, setQuery] = useState("");
  const ref = useRef<HTMLDivElement | null>(null);
  const selectedValues = useMemo(() => new Set(values.filter(Boolean)), [values]);

  const realOptions = useMemo(() => options.filter((option) => option.value), [options]);
  const filteredOptions = useMemo(() => {
    const normalizedQuery = query.trim().toLowerCase();
    const matchingOptions = normalizedQuery
      ? realOptions.filter((option) => option.label.toLowerCase().includes(normalizedQuery))
      : realOptions;

    return [...matchingOptions].sort((a, b) => {
      const aSelected = selectedValues.has(a.value);
      const bSelected = selectedValues.has(b.value);

      if (aSelected !== bSelected) return aSelected ? -1 : 1;

      const aSelectedIndex = values.indexOf(a.value);
      const bSelectedIndex = values.indexOf(b.value);
      if (aSelected && bSelected && aSelectedIndex !== bSelectedIndex) {
        return aSelectedIndex - bSelectedIndex;
      }

      return 0;
    });
  }, [query, realOptions, selectedValues, values]);

  useEffect(() => {
    const handler = (event: MouseEvent) => {
      if (ref.current && !ref.current.contains(event.target as Node)) setOpen(false);
    };
    document.addEventListener("mousedown", handler);
    return () => document.removeEventListener("mousedown", handler);
  }, []);

  const selectedLabel = useMemo(() => {
    if (!selectedValues.size) return allLabel;
    const selectedLabels = realOptions
      .filter((option) => selectedValues.has(option.value))
      .map((option) => option.label);

    // Fall back to raw values when options haven't loaded yet
    const labels = selectedLabels.length > 0 ? selectedLabels : Array.from(selectedValues);

    if (labels.length <= 2) return labels.join(", ");
    return `${labels.length} selected`;
  }, [allLabel, realOptions, selectedValues]);

  const toggleValue = (value: string) => {
    const next = new Set(selectedValues);
    if (next.has(value)) {
      next.delete(value);
    } else {
      if (maxValues && next.size >= maxValues) return;
      next.add(value);
    }
    onChange(Array.from(next));
  };

  const clearSelection = () => {
    onChange([]);
    setQuery("");
  };

  return (
    <div ref={ref} className="relative w-full">
      <label style={{ color: "var(--muted-tx)" }} className="block text-xs font-medium mb-1">
        {label}
      </label>

      <button
        type="button"
        onClick={() => {
          setOpen((prev) => !prev);
          setQuery("");
        }}
        style={{ background: "var(--card-bg-2)", borderColor: "var(--card-bd)", color: "var(--title-tx)" }}
        className="w-full flex items-center justify-between rounded-xl border px-4 py-3 text-sm hover:border-blue-500 transition-colors"
      >
        <span className="truncate">{selectedLabel}</span>
        <span className="ml-2 flex shrink-0 items-center gap-1">
          {selectedValues.size > 0 && (
            <span
              style={{ background: "rgba(37, 99, 235, 0.12)", color: "#2563eb" }}
              className="rounded-full px-1.5 py-0.5 text-[10px] font-semibold leading-none"
            >
              {selectedValues.size}
            </span>
          )}
          <ChevronDown size={15} style={{ color: "var(--muted-tx)" }} className={`transition-transform duration-200 ${open ? "rotate-180" : ""}`} />
        </span>
      </button>

      {open && (
        <div
          style={{
            background: "var(--dropdown-bg)",
            border: "1px solid var(--dropdown-bd)",
            boxShadow: "0 8px 32px rgba(0,0,0,0.15)",
          }}
          className="absolute z-[9999] mt-1 w-full rounded-xl overflow-hidden"
        >
          <div style={{ borderBottom: "1px solid var(--dropdown-bd)" }} className="p-2">
            <div className="flex items-center gap-2">
              <input
                autoFocus
                value={query}
                onChange={(event) => setQuery(event.target.value)}
                placeholder="Search..."
                style={{ background: "var(--dropdown-bg-2)", color: "var(--title-tx)" }}
                className="min-w-0 flex-1 px-3 py-2 text-sm rounded-lg outline-none placeholder:text-[var(--muted-tx)]"
              />
              {selectedValues.size > 0 && (
                <button
                  type="button"
                  onClick={clearSelection}
                  title="Clear selected brands"
                  style={{ color: "var(--muted-tx)", border: "1px solid var(--dropdown-bd)" }}
                  className="flex h-9 w-9 shrink-0 items-center justify-center rounded-lg transition hover:border-red-300 hover:text-red-500"
                >
                  <X size={14} />
                </button>
              )}
            </div>
          </div>

          <button
            type="button"
            onClick={clearSelection}
            style={{ color: "var(--body-tx)", background: "var(--dropdown-bg)" }}
            className="flex w-full items-center justify-between px-4 py-2.5 text-left text-sm transition-colors hover:bg-blue-600 hover:text-white"
          >
            <span>{allLabel}</span>
            {!selectedValues.size && <Check size={14} />}
          </button>

          <div className="max-h-60 overflow-y-auto">
            {filteredOptions.length === 0 ? (
              <div style={{ color: "var(--muted-tx)", background: "var(--dropdown-bg)" }} className="px-4 py-3 text-sm">
                No results
              </div>
            ) : (
              filteredOptions.map((option) => {
                const selected = selectedValues.has(option.value);
                const limitReached = !!maxValues && selectedValues.size >= maxValues && !selected;
                return (
                  <button
                    key={option.value}
                    type="button"
                    onClick={() => toggleValue(option.value)}
                    disabled={limitReached}
                    style={{ color: "var(--body-tx)", background: "var(--dropdown-bg)", opacity: limitReached ? 0.4 : 1, cursor: limitReached ? "not-allowed" : "pointer" }}
                    className="flex w-full items-center justify-between gap-3 px-4 py-2.5 text-left text-sm transition-colors hover:bg-blue-600 hover:text-white disabled:hover:bg-transparent disabled:hover:text-[var(--body-tx)]"
                  >
                    <span className="truncate">{option.label}</span>
                    <span
                      style={{
                        borderColor: selected ? "#2563eb" : "var(--dropdown-bd)",
                        background: selected ? "#2563eb" : "transparent",
                        color: "white",
                      }}
                      className="flex h-4 w-4 shrink-0 items-center justify-center rounded border"
                    >
                      {selected && <Check size={11} />}
                    </span>
                  </button>
                );
              })
            )}
          </div>
        </div>
      )}
    </div>
  );
}
