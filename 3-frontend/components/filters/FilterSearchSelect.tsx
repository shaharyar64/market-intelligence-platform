"use client";

import { useState, useMemo, useRef, useEffect, useId } from "react";
import { ChevronDown } from "lucide-react";

interface Option { label: string; value: string; }
interface Props { label: string; value: string; options: Option[]; onChange: (value: string) => void; }

export default function FilterSearchSelect({ label, value, options = [], onChange }: Props) {
  const [open, setOpen] = useState(false);
  const [query, setQuery] = useState("");
  const ref = useRef<HTMLDivElement | null>(null);
  const listboxId = useId();

  const filteredOptions = useMemo(
    () => (query ? options.filter((o) => o.label.toLowerCase().includes(query.toLowerCase())) : options),
    [query, options]
  );

  useEffect(() => {
    const handler = (e: MouseEvent) => {
      if (ref.current && !ref.current.contains(e.target as Node)) setOpen(false);
    };
    document.addEventListener("mousedown", handler);
    const onKeyDown = (event: KeyboardEvent) => { if (event.key === "Escape") setOpen(false); };
    document.addEventListener("keydown", onKeyDown);
    return () => {
      document.removeEventListener("mousedown", handler);
      document.removeEventListener("keydown", onKeyDown);
    };
  }, []);

  const selectedLabel = options.find((o) => o.value === value)?.label || label;

  return (
    <div ref={ref} className="relative w-full">
      <label style={{ color: "var(--muted-tx)" }} className="block text-xs font-medium mb-1">
        {label}
      </label>

      <button
        type="button"
        onClick={() => { setOpen(!open); setQuery(""); }}
        aria-expanded={open}
        aria-controls={open ? listboxId : undefined}
        aria-haspopup="listbox"
        style={{ background: "var(--card-bg-2)", borderColor: "var(--card-bd)", color: "var(--title-tx)" }}
        className="w-full flex items-center justify-between rounded-xl border px-4 py-3 text-sm hover:border-blue-500 transition-colors"
      >
        <span className="truncate">{selectedLabel}</span>
        <ChevronDown size={15} style={{ color: "var(--muted-tx)" }} className={`shrink-0 transition-transform duration-200 ${open ? "rotate-180" : ""}`} />
      </button>

      {open && (
        <div
          style={{
            background: "var(--dropdown-bg)",
            border: "1px solid var(--dropdown-bd)",
            boxShadow: "0 8px 32px rgba(0,0,0,0.15)",
          }}
          id={listboxId}
          role="listbox"
          aria-label={label}
          className="absolute z-[9999] mt-1 w-full rounded-xl overflow-hidden max-h-60 overflow-y-auto"
        >
          <div style={{ borderBottom: "1px solid var(--dropdown-bd)" }} className="p-2">
            <input
              autoFocus
              value={query}
              onChange={(e) => setQuery(e.target.value)}
              placeholder="Search..."
              style={{ background: "var(--dropdown-bg-2)", color: "var(--title-tx)" }}
              className="w-full px-3 py-2 text-sm rounded-lg outline-none placeholder:text-[var(--muted-tx)]"
            />
          </div>
          {filteredOptions.length === 0 ? (
            <div style={{ color: "var(--muted-tx)", background: "var(--dropdown-bg)" }} className="px-4 py-3 text-sm">
              No results
            </div>
          ) : (
            filteredOptions.map((option) => (
              <button
                key={option.value}
                type="button"
                onClick={() => { onChange(option.value); setOpen(false); setQuery(""); }}
                role="option"
                aria-selected={option.value === value}
                style={{ color: "var(--body-tx)", background: "var(--dropdown-bg)" }}
                className="w-full text-left px-4 py-2.5 text-sm hover:bg-blue-600 hover:text-white transition-colors"
              >
                {option.label}
              </button>
            ))
          )}
        </div>
      )}
    </div>
  );
}
