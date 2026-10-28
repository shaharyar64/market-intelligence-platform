"use client";

import { useId, useState } from "react";
import { AnimatePresence, motion } from "framer-motion";
import { ChevronDown, ExternalLink, Quote } from "lucide-react";

import { FACTORS, type FactorMeta } from "@/lib/ideaTestingFramework";
import type { Citation, FactorId, FactorScore } from "@/lib/ideaTesting";

const PLATFORM_NAMES: Record<string, string> = {
  instagram: "Instagram", tiktok: "TikTok", linkedin: "LinkedIn", twitter: "X", x: "X",
};

function sourceLabel(c: Citation): string {
  if (c.evidence_type === "document") return c.document_title || "Document";
  if (c.evidence_type === "trend") return "Trend";
  if (!c.platform) return "Social post";
  return `${PLATFORM_NAMES[c.platform] ?? c.platform[0].toUpperCase() + c.platform.slice(1)} post`;
}

function EvidenceCard({ citation, color }: { citation: Citation; color: string }) {
  const url = citation.post_url && /^https?:\/\//.test(citation.post_url) ? citation.post_url : null;
  const removed = citation.evidence_type === "document" && citation.document_deleted;
  const label = removed ? `Source removed: ${citation.document_title || "Document"}` : sourceLabel(citation);
  const chipClass = "inline-flex w-fit items-center gap-1.5 rounded-full px-2.5 py-0.5 text-[11px] font-semibold";
  const chipStyle = removed
    ? { background: "var(--fi-mainstream-soft)", border: "1px solid var(--fi-mainstream-soft-bd)", color: "var(--fi-mainstream-tx)" }
    : { border: "1px solid var(--card-bd)", color: "var(--body-tx)" };
  const dot = <span aria-hidden="true" className="size-1.5 rounded-full" style={{ background: color }} />;

  return (
    <figure
      className="flex flex-col rounded-xl p-4"
      style={{ background: "var(--card-bg-2)", border: "1px solid var(--card-bd)" }}
    >
      {url ? (
        <a
          href={url}
          target="_blank"
          rel="noopener noreferrer"
          aria-label={`Open ${label} in a new tab`}
          style={chipStyle}
          className={`${chipClass} transition-colors hover:border-[var(--fi-solid)] hover:text-[var(--title-tx)]`}
        >
          {dot}
          {label}
          <ExternalLink size={11} aria-hidden="true" />
        </a>
      ) : (
        <span style={chipStyle} className={chipClass}>
          {dot}
          {label}
        </span>
      )}
      <blockquote style={{ color: "var(--body-tx)" }} className="mt-3 flex gap-2 text-sm leading-relaxed">
        <Quote size={14} aria-hidden="true" className="mt-1 shrink-0" style={{ color: "var(--muted-tx)" }} />
        <span>{citation.quote}</span>
      </blockquote>
    </figure>
  );
}

function FactorRow({
  meta, factor, open, onToggle,
}: {
  meta: FactorMeta;
  factor: FactorScore;
  open: boolean;
  onToggle: () => void;
}) {
  const panelId = useId();
  const count = factor.citations.length;

  return (
    <div
      className="chart-card overflow-hidden rounded-2xl transition-colors duration-200"
      style={open ? { borderColor: `color-mix(in srgb, ${meta.color} 55%, transparent)` } : undefined}
    >
      <button
        type="button"
        onClick={onToggle}
        aria-expanded={open}
        aria-controls={panelId}
        className="flex w-full items-center gap-4 px-5 py-4 text-left"
      >
        <span aria-hidden="true" className="size-2.5 shrink-0 rounded-full" style={{ background: meta.color }} />
        <span className="min-w-0 flex-1">
          <span className="flex flex-wrap items-center gap-x-2.5 gap-y-1">
            <span style={{ color: "var(--title-tx)" }} className="text-sm font-semibold">{meta.label}</span>
            <span style={{ color: "var(--muted-tx)" }} className="text-xs">{factor.verdict}</span>
            {count > 0 && (
              <span
                className="inline-flex items-center gap-1 rounded-md px-1.5 py-0.5 text-[11px] tabular-nums"
                style={{ border: "1px solid var(--card-bd)", color: "var(--muted-tx)" }}
                aria-label={`${count} ${count === 1 ? "citation" : "citations"}`}
              >
                <Quote size={10} aria-hidden="true" />
                {count}
              </span>
            )}
          </span>
          <span className="mt-2.5 block h-1.5 w-full max-w-md overflow-hidden rounded-full" style={{ background: "var(--card-bd)" }}>
            <span
              className="block h-full rounded-full"
              style={{ width: `${Math.max(0, Math.min(100, factor.score))}%`, background: meta.color }}
            />
          </span>
        </span>
        <span style={{ color: "var(--title-tx)" }} className="text-lg font-bold tabular-nums">{factor.score}</span>
        <ChevronDown
          size={16}
          aria-hidden="true"
          className={`shrink-0 transition-transform duration-200 ${open ? "rotate-180" : ""}`}
          style={{ color: "var(--muted-tx)" }}
        />
      </button>

      <AnimatePresence initial={false}>
        {open && (
          <motion.div
            id={panelId}
            initial={{ height: 0, opacity: 0 }}
            animate={{ height: "auto", opacity: 1 }}
            exit={{ height: 0, opacity: 0 }}
            transition={{ duration: 0.25, ease: [0.16, 1, 0.3, 1] }}
            className="overflow-hidden"
          >
            <div className="border-t px-5 pb-5 pt-4" style={{ borderColor: "var(--card-bd)" }}>
              <p style={{ color: "var(--muted-tx)" }} className="text-sm italic">{meta.question}</p>
              <p style={{ color: "var(--body-tx)" }} className="mt-2 text-sm leading-relaxed">{factor.finding}</p>
              {count > 0 && (
                <>
                  <h4 style={{ color: "var(--muted-tx)" }} className="mt-5 text-[11px] font-semibold uppercase tracking-wide">
                    Evidence from your data
                  </h4>
                  <div className="mt-2.5 grid gap-3 sm:grid-cols-2">
                    {factor.citations.map((c, i) => (
                      <EvidenceCard key={`${c.post_id ?? c.trend_id ?? "c"}-${i}`} citation={c} color={meta.color} />
                    ))}
                  </div>
                </>
              )}
            </div>
          </motion.div>
        )}
      </AnimatePresence>
    </div>
  );
}

export default function FactorAccordion({ factors }: { factors: FactorScore[] }) {
  const rows = FACTORS
    .map((meta) => ({ meta, factor: factors.find((f) => f.factor_id === meta.id) }))
    .filter((r): r is { meta: FactorMeta; factor: FactorScore } => Boolean(r.factor));
  const [open, setOpen] = useState<Set<FactorId>>(() => new Set(rows[0] ? [rows[0].meta.id] : []));

  function toggle(id: FactorId) {
    setOpen((prev) => {
      const next = new Set(prev);
      if (next.has(id)) next.delete(id);
      else next.add(id);
      return next;
    });
  }

  return (
    <div className="space-y-3">
      {rows.map(({ meta, factor }) => (
        <FactorRow
          key={meta.id}
          meta={meta}
          factor={factor}
          open={open.has(meta.id)}
          onToggle={() => toggle(meta.id)}
        />
      ))}
    </div>
  );
}
