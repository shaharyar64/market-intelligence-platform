"use client";

import { useCallback, useEffect, useRef, useState } from "react";
import { usePathname, useRouter, useSearchParams } from "next/navigation";
import { Check, ChevronDown } from "lucide-react";

import { MARKETS, parseMarket, type Market } from "@/lib/realEstateTrends";

/**
 * The market lives in the URL (?market=AE | SA) so a shared link, a refresh and
 * the overview-to-explorer hop all keep it. Omitted means all markets.
 *
 * Changing market drops ?trend: trend ids belong to one run, and the trend a
 * reader had open does not exist in the other market's run.
 */
export function useMarket(): [Market | null, (next: Market | null) => void] {
  const searchParams = useSearchParams();
  const router = useRouter();
  const pathname = usePathname();
  const market = parseMarket(searchParams.get("market"));
  const setMarket = useCallback((next: Market | null) => {
    const qs = new URLSearchParams(searchParams.toString());
    if (next) qs.set("market", next); else qs.delete("market");
    qs.delete("trend");
    const s = qs.toString();
    router.replace(s ? `${pathname}?${s}` : pathname, { scroll: false });
  }, [searchParams, router, pathname]);
  return [market, setMarket];
}

/**
 * Market filter, drawn like the Explorer's other filter dropdowns ("Posts
 * from") so it reads as one more filter in the row rather than a page-level
 * switch. A dropdown rather than pills: it stays one pill wide however many
 * markets are added, and "All markets" no longer wraps.
 */
export default function MarketSelect({ market, onChange, markets = MARKETS }: {
  market: Market | null; onChange: (m: Market | null) => void;
  markets?: { value: Market | null; label: string }[];
}) {
  const [open, setOpen] = useState(false);
  const rootRef = useRef<HTMLDivElement>(null);

  useEffect(() => {
    if (!open) return;
    const onDown = (e: MouseEvent) => {
      if (!rootRef.current?.contains(e.target as Node)) setOpen(false);
    };
    const onKey = (e: KeyboardEvent) => { if (e.key === "Escape") setOpen(false); };
    document.addEventListener("mousedown", onDown);
    document.addEventListener("keydown", onKey);
    return () => {
      document.removeEventListener("mousedown", onDown);
      document.removeEventListener("keydown", onKey);
    };
  }, [open]);

  const active = market !== null;
  const current = markets.find((m) => m.value === market) ?? markets[0];

  return (
    <div ref={rootRef} className="relative">
      <button type="button" onClick={() => setOpen((o) => !o)}
        aria-haspopup="listbox" aria-expanded={open}
        className="flex min-h-11 items-center gap-1.5 whitespace-nowrap rounded-full px-3.5 py-1.5 text-xs font-semibold transition-colors"
        style={{
          background: active ? "var(--fi-solid)" : "var(--card-bg-2)",
          color: active ? "var(--fi-solid-tx)" : "var(--body-tx)",
          border: `1px solid ${active ? "var(--fi-solid)" : "var(--card-bd)"}`,
        }}>
        <span style={{ opacity: 0.75 }}>Market</span>
        {current.label}
        <ChevronDown size={13} aria-hidden="true"
          style={{ transform: open ? "rotate(180deg)" : undefined, transition: "transform 150ms" }} />
      </button>

      {open && (
        <div role="listbox" aria-label="Market"
          className="absolute left-0 top-full z-30 mt-2 min-w-[11rem] rounded-xl p-1.5 shadow-xl"
          style={{ background: "var(--dropdown-bg)", border: "1px solid var(--card-bd)" }}>
          {markets.map((m, i) => {
            const on = m.value === market;
            return (
              <div key={m.label}>
                {i === 1 && <div className="my-1 h-px" style={{ background: "var(--card-bd)" }} aria-hidden="true" />}
                <button type="button" role="option" aria-selected={on}
                  onClick={() => { onChange(m.value); setOpen(false); }}
                  className="flex min-h-11 w-full items-center justify-between gap-3 rounded-lg px-3 py-2 text-left text-xs font-medium transition-colors hover:bg-[var(--dropdown-bg-2)]"
                  style={{ color: "var(--body-tx)" }}>
                  {m.label}
                  {on && <Check size={13} aria-hidden="true" style={{ color: "var(--accent-tx)" }} />}
                </button>
              </div>
            );
          })}
        </div>
      )}
    </div>
  );
}
