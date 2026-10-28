"use client";

import { motion } from "framer-motion";
import { AlertTriangle, RotateCcw, Trophy } from "lucide-react";

import ResultHero, { HeroStat } from "./ResultHero";
import ResultsView from "./ResultsView";
import { FACTORS, FACTOR_MAP } from "@/lib/foodIdeaTestingFramework";
import type { Assessment, Comparison } from "@/lib/foodIdeaTesting";

function joinList(items: string[]): string {
  if (items.length <= 1) return items.join("");
  return `${items.slice(0, -1).join(", ")} and ${items[items.length - 1]}`;
}

export default function ComparisonView({
  assessments, comparison, onRestart,
}: {
  assessments: Assessment[];
  comparison: Comparison;
  onRestart: () => void;
}) {
  const winnerIndex = assessments.findIndex((a) => a.assessment_id === comparison.winner_assessment_id);
  const winner = assessments[winnerIndex] ?? assessments[0];
  const runnerUpScore = Math.max(
    ...assessments.filter((a) => a !== winner).map((a) => a.overall_score),
  );
  const lead = winner.overall_score - runnerUpScore;
  const wonFactors = comparison.factor_leaders
    .filter((l) => l.assessment_id === winner.assessment_id)
    .map((l) => FACTOR_MAP[l.factor_id].label);
  const lowConfidence = assessments.filter((a) => a.confidence_score <= 40);

  const verdict =
    (lead > 0
      ? `${winner.title} leads by ${lead} ${lead === 1 ? "point" : "points"} overall`
      : `${winner.title} ties for the highest overall score`) +
    (wonFactors.length > 0
      ? ` and wins ${wonFactors.length} of ${FACTORS.length} factors: ${joinList(wonFactors)}.`
      : ".");

  return (
    <div className="space-y-8">
      <ResultHero
        pill={<><Trophy size={12} aria-hidden="true" />Winner of {assessments.length} concepts</>}
        title={winner.title}
        description={comparison.narrative}
        stats={
          <>
            <HeroStat value={winner.overall_score} label="Overall /100" />
            <HeroStat value={lead > 0 ? `+${lead}` : "0"} label="Lead" />
            <HeroStat value={`${winner.confidence_score}%`} label="Confidence" />
          </>
        }
        verdict={verdict}
        footer={
          lowConfidence.length > 0 && (
            <p
              style={{ background: "var(--fi-mainstream-soft)", border: "1px solid var(--fi-mainstream-soft-bd)", color: "var(--fi-mainstream-tx)" }}
              className="mt-3 flex items-start gap-1.5 rounded-lg px-3 py-2 text-xs"
            >
              <AlertTriangle size={13} aria-hidden="true" className="mt-px shrink-0" />
              <span>
                {joinList(lowConfidence.map((a) => `${a.title} (${a.confidence_score}%)`))}{" "}
                {lowConfidence.length === 1 ? "has" : "have"} low confidence, so read{" "}
                {lowConfidence.length === 1 ? "its" : "their"} scores as directional before
                picking a winner.
              </span>
            </p>
          )
        }
      />

      <motion.div
        initial={{ opacity: 0, y: 10 }}
        animate={{ opacity: 1, y: 0 }}
        transition={{ duration: 0.4, delay: 0.05, ease: [0.16, 1, 0.3, 1] }}
        className="chart-card overflow-x-auto rounded-2xl p-5"
      >
        <table className="w-full text-sm" style={{ color: "var(--title-tx)" }}>
          <thead>
            <tr style={{ color: "var(--muted-tx)", borderBottom: "1px solid var(--card-bd)" }} className="text-left text-xs uppercase">
              <th scope="col" className="py-2 pr-4 font-medium">Factor</th>
              {assessments.map((a, i) => (
                <th scope="col" key={`${a.assessment_id}-${i}`} className="py-2 pr-4 font-medium">
                  <span className="flex items-center gap-1.5 normal-case" style={{ color: "var(--title-tx)" }}>
                    {a.title}
                    {i === winnerIndex && (
                      <span
                        style={{ background: "var(--fi-solid)", color: "var(--fi-solid-tx)" }}
                        className="rounded-full px-2 py-0.5 text-[10px] font-semibold uppercase tracking-wide"
                      >
                        Winner
                      </span>
                    )}
                  </span>
                </th>
              ))}
            </tr>
          </thead>
          <tbody>
            {comparison.factor_leaders.map(({ factor_id, assessment_id: leaderId }) => {
              const leaderIndex = assessments.findIndex((a) => a.assessment_id === leaderId);
              return (
                <tr key={factor_id} style={{ borderTop: "1px solid var(--card-bd)" }}>
                  <th scope="row" className="py-2 pr-4 text-left font-medium">{FACTOR_MAP[factor_id].label}</th>
                  {assessments.map((a, i) => {
                    const score = a.factor_scores.find((f) => f.factor_id === factor_id)?.score ?? 0;
                    const isLeader = i === leaderIndex;
                    return (
                      <td key={`${a.assessment_id}-${i}`} className="py-2 pr-4">
                        <span
                          style={{
                            color: isLeader ? "var(--fi-solid)" : "var(--title-tx)",
                            fontWeight: isLeader ? 700 : 400,
                          }}
                        >
                          {score}
                        </span>
                      </td>
                    );
                  })}
                </tr>
              );
            })}
            <tr style={{ borderTop: "1px solid var(--card-bd)" }}>
              <th scope="row" className="py-2 pr-4 text-left font-semibold">Overall</th>
              {assessments.map((a, i) => (
                <td key={`${a.assessment_id}-${i}`} className="py-2 pr-4 font-semibold">{a.overall_score}</td>
              ))}
            </tr>
            <tr style={{ borderTop: "1px solid var(--card-bd)" }}>
              <th scope="row" className="py-2 pr-4 text-left font-medium">Confidence</th>
              {assessments.map((a, i) => {
                const low = a.confidence_score <= 40;
                return (
                  <td key={`${a.assessment_id}-${i}`} className="py-2 pr-4">
                    <span className="tabular-nums">{a.confidence_score}%</span>
                    <span
                      style={{ color: low ? "var(--fi-mainstream-tx)" : "var(--muted-tx)" }}
                      className="ml-2 inline-flex items-center gap-1 text-xs"
                    >
                      {low && <AlertTriangle size={12} aria-hidden="true" />}
                      {a.confidence_label}
                    </span>
                  </td>
                );
              })}
            </tr>
          </tbody>
        </table>
      </motion.div>

      <div className="space-y-10">
        {assessments.map((a, i) => (
          <div
            key={`${a.assessment_id}-${i}`}
            className={i > 0 ? "border-t pt-10" : ""}
            style={i > 0 ? { borderColor: "var(--card-bd)" } : undefined}
          >
            <ResultsView assessment={a} />
          </div>
        ))}
      </div>

      <button
        type="button"
        onClick={onRestart}
        style={{ border: "1px solid var(--card-bd)", background: "var(--card-bg)", color: "var(--title-tx)" }}
        className="inline-flex items-center gap-1.5 rounded-full px-4 py-2 text-sm font-semibold transition-colors hover:border-[var(--fi-solid)] hover:text-[var(--fi-solid)]"
      >
        <RotateCcw size={14} aria-hidden="true" />
        Test another concept
      </button>
    </div>
  );
}
