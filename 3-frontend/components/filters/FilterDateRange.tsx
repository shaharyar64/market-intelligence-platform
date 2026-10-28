"use client";

import { useEffect, useMemo, useRef, useState } from "react";
import dayjs, { Dayjs } from "dayjs";
import { Calendar, ChevronLeft, ChevronRight } from "lucide-react";

interface Props {
  label: string;
  startDate: string;
  endDate: string;
  min: string;
  max: string;
  onChange: (startDate: string, endDate: string) => void;
}

const WEEKDAYS = ["Su", "Mo", "Tu", "We", "Th", "Fr", "Sa"];
const fmt = (d: Dayjs) => d.format("YYYY-MM-DD");

export default function FilterDateRange({ label, startDate, endDate, min, max, onChange }: Props) {
  const [open, setOpen] = useState(false);
  const [viewMonth, setViewMonth] = useState<Dayjs>(() => dayjs(startDate || min));
  const [pendingStart, setPendingStart] = useState<string | null>(null);
  const [hoverDate, setHoverDate] = useState<string | null>(null);
  const ref = useRef<HTMLDivElement>(null);

  useEffect(() => {
    if (!open) return;
    const handler = (e: MouseEvent) => {
      if (ref.current && !ref.current.contains(e.target as Node)) {
        setOpen(false);
        setPendingStart(null);
      }
    };
    document.addEventListener("mousedown", handler);
    return () => document.removeEventListener("mousedown", handler);
  }, [open]);

  const openPicker = () => {
    setViewMonth(dayjs(startDate || min));
    setPendingStart(null);
    setOpen((v) => !v);
  };

  const minYM = min.slice(0, 7);
  const maxYM = max.slice(0, 7);
  const viewYM = viewMonth.format("YYYY-MM");
  const canPrev = viewYM > minYM;
  const canNext = viewYM < maxYM;

  const cells = useMemo(() => {
    const startOfMonth = viewMonth.startOf("month");
    const leadingBlanks = startOfMonth.day();
    const daysInMonth = viewMonth.daysInMonth();
    const list: (Dayjs | null)[] = [];
    for (let i = 0; i < leadingBlanks; i++) list.push(null);
    for (let d = 1; d <= daysInMonth; d++) list.push(startOfMonth.date(d));
    return list;
  }, [viewMonth]);

  const rangeStart = pendingStart ?? startDate;
  const rangeEndRaw = pendingStart ? hoverDate ?? pendingStart : endDate;
  const [lo, hi] = rangeStart && rangeEndRaw
    ? rangeStart < rangeEndRaw ? [rangeStart, rangeEndRaw] : [rangeEndRaw, rangeStart]
    : [null, null];

  const handleDayClick = (day: Dayjs) => {
    const iso = fmt(day);
    if (iso < min || iso > max) return;
    if (!pendingStart) {
      setPendingStart(iso);
      return;
    }
    const [s, e] = iso < pendingStart ? [iso, pendingStart] : [pendingStart, iso];
    onChange(s, e);
    setPendingStart(null);
    setOpen(false);
  };

  return (
    <div ref={ref} className="relative w-full">
      <label style={{ color: "var(--muted-tx)" }} className="block text-xs font-medium mb-1">
        {label}
      </label>

      <button
        type="button"
        onClick={openPicker}
        style={{ background: "var(--card-bg-2)", borderColor: "var(--card-bd)", color: "var(--title-tx)" }}
        className="w-full flex items-center gap-2 rounded-xl border px-4 py-3 text-sm hover:border-blue-500 transition-colors"
      >
        <Calendar size={14} style={{ color: "var(--muted-tx)" }} className="shrink-0" />
        <span className="truncate">
          {dayjs(startDate).format("DD MMM YYYY")} – {dayjs(endDate).format("DD MMM YYYY")}
        </span>
      </button>

      {open && (
        <div
          style={{ background: "var(--dropdown-bg)", border: "1px solid var(--dropdown-bd)", boxShadow: "0 8px 32px rgba(0,0,0,0.15)" }}
          className="absolute z-[9999] mt-1 w-[280px] rounded-xl overflow-hidden p-3"
        >
          <div className="flex items-center justify-between mb-2">
            <button
              type="button"
              disabled={!canPrev}
              onClick={() => setViewMonth((m) => m.subtract(1, "month"))}
              style={{ color: canPrev ? "var(--title-tx)" : "var(--muted-tx)" }}
              className="p-1 rounded-md hover:bg-black/5 disabled:opacity-30 disabled:cursor-not-allowed"
            >
              <ChevronLeft size={16} />
            </button>
            <span style={{ color: "var(--title-tx)" }} className="text-sm font-semibold">
              {viewMonth.format("MMMM YYYY")}
            </span>
            <button
              type="button"
              disabled={!canNext}
              onClick={() => setViewMonth((m) => m.add(1, "month"))}
              style={{ color: canNext ? "var(--title-tx)" : "var(--muted-tx)" }}
              className="p-1 rounded-md hover:bg-black/5 disabled:opacity-30 disabled:cursor-not-allowed"
            >
              <ChevronRight size={16} />
            </button>
          </div>

          <div className="grid grid-cols-7 gap-y-1 mb-1">
            {WEEKDAYS.map((d) => (
              <div key={d} style={{ color: "var(--muted-tx)" }} className="text-center text-[11px] font-medium">
                {d}
              </div>
            ))}
          </div>

          <div className="grid grid-cols-7 gap-y-1">
            {cells.map((day, i) => {
              if (!day) return <div key={i} />;
              const iso = fmt(day);
              const disabled = iso < min || iso > max;
              const isEdge = iso === startDate || iso === endDate || iso === pendingStart;
              const inRange = !!(lo && hi && iso >= lo && iso <= hi);

              return (
                <button
                  key={i}
                  type="button"
                  disabled={disabled}
                  onClick={() => handleDayClick(day)}
                  onMouseEnter={() => pendingStart && setHoverDate(iso)}
                  style={{
                    color: disabled ? "var(--muted-tx)" : isEdge ? "#ffffff" : "var(--title-tx)",
                    background: isEdge ? "#2563eb" : inRange ? "rgba(37,99,235,0.15)" : "transparent",
                    opacity: disabled ? 0.35 : 1,
                  }}
                  className="mx-auto flex h-7 w-7 items-center justify-center rounded-full text-xs transition-colors disabled:cursor-not-allowed hover:enabled:bg-blue-500/20"
                >
                  {day.date()}
                </button>
              );
            })}
          </div>
        </div>
      )}
    </div>
  );
}
