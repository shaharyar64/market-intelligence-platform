"use client";

import { motion } from "framer-motion";
import { RotateCcw } from "lucide-react";

import ConfidenceMeter from "./ConfidenceMeter";
import FactorAccordion from "./FactorAccordion";
import FactorProfile from "./FactorProfile";
import ScoreMethod from "./ScoreMethod";
import ScoreRing from "./ScoreRing";
import type { Assessment } from "@/lib/foodIdeaTesting";
import { scoreTone } from "@/lib/foodIdeaTestingFramework";

export default function ResultsView({
  assessment, onRestart,
}: {
  assessment: Assessment;
  onRestart?: () => void;
}) {
  return (
    <div className="grid gap-6 lg:grid-cols-[minmax(0,1fr)_minmax(320px,380px)]">
      <motion.header
        initial={{ opacity: 0, y: 10 }}
        animate={{ opacity: 1, y: 0 }}
        transition={{ duration: 0.4, ease: [0.16, 1, 0.3, 1] }}
        className="min-w-0 lg:col-start-1"
      >
        <div className="flex items-center gap-5">
          <ScoreRing score={assessment.overall_score} />
          <div className="min-w-0">
            <h2 style={{ color: "var(--title-tx)" }} className="text-2xl font-bold tracking-tight text-balance sm:text-3xl">
              {assessment.title}
            </h2>
            <p style={{ color: scoreTone(assessment.overall_score) }} className="mt-1 text-sm font-semibold">
              {assessment.headline}
            </p>
          </div>
        </div>
        <p style={{ color: "var(--body-tx)" }} className="mt-5 max-w-3xl text-sm leading-relaxed">
          {assessment.summary}
        </p>
        {assessment.food_relation === "food_adjacent" && (
          <p
            role="note"
            className="mt-4 max-w-3xl rounded-xl px-4 py-3 text-sm leading-relaxed"
            style={{ background: "var(--card-bg-2)", border: "1px solid var(--card-bd)", color: "var(--body-tx)" }}
          >
            This concept is food-related rather than a food or beverage product, so the food posts
            and trends behind these scores describe its market only indirectly.
          </p>
        )}
      </motion.header>

      <aside className="min-w-0 space-y-4 lg:sticky lg:top-24 lg:col-start-2 lg:row-span-3 lg:row-start-1 lg:self-start">
        <section className="chart-card rounded-2xl p-5">
          <h3 style={{ color: "var(--muted-tx)" }} className="mb-3 text-[11px] font-semibold uppercase tracking-wide">
            InsightFactor profile
          </h3>
          <FactorProfile factors={assessment.factor_scores} />
        </section>
        <ScoreMethod factors={assessment.factor_scores} overall={assessment.overall_score} />
        <ConfidenceMeter
          score={assessment.confidence_score}
          label={assessment.confidence_label}
          explanation={assessment.confidence_explanation}
          breakdown={assessment.confidence_breakdown}
        />
      </aside>

      <div className="min-w-0 lg:col-start-1">
        <FactorAccordion factors={assessment.factor_scores} />
      </div>

      <div className="min-w-0 space-y-6 lg:col-start-1">
        <section className="chart-card rounded-2xl p-5">
          <h3 style={{ color: "var(--title-tx)" }} className="text-sm font-semibold">Recommendations</h3>
          <ol className="mt-3 space-y-2 text-sm leading-relaxed" style={{ color: "var(--body-tx)" }}>
            {assessment.recommendations.map((r, i) => (
              <li key={i} className="flex gap-3">
                <span
                  style={{ background: "var(--card-bg-2)", color: "var(--title-tx)" }}
                  className="flex size-6 shrink-0 items-center justify-center rounded-full text-xs font-semibold tabular-nums"
                >
                  {i + 1}
                </span>
                <span className="pt-0.5">{r}</span>
              </li>
            ))}
          </ol>
        </section>

        {onRestart && (
          <button
            type="button"
            onClick={onRestart}
            style={{ border: "1px solid var(--card-bd)", background: "var(--card-bg)", color: "var(--title-tx)" }}
            className="inline-flex items-center gap-1.5 rounded-full px-4 py-2 text-sm font-semibold transition-colors hover:border-[var(--fi-solid)] hover:text-[var(--fi-solid)]"
          >
            <RotateCcw size={14} aria-hidden="true" />
            Test another concept
          </button>
        )}
      </div>
    </div>
  );
}
