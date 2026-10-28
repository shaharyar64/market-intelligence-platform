"use client";

import { useState } from "react";
import {
  PolarAngleAxis,
  PolarGrid,
  PolarRadiusAxis,
  Radar,
  RadarChart,
  ResponsiveContainer,
  Tooltip,
} from "recharts";
import type { BankPerception } from "@/lib/bankingPerceptionData";
import type { AiScoreAudienceAffinityItem } from "@/lib/uaeBankBrandHealth";
import { normalizeBankKey } from "@/lib/bankNames";

export const AI_ASSISTANTS = ["All Assistants", "ChatGPT", "Gemini", "Claude", "Grok"];

function shortLabel(value: string, max = 24) {
  return value.length > max ? `${value.slice(0, max - 1)}...` : value;
}

function NotAvailable() {
  return <p className="text-sm italic text-[var(--muted-tx)]">Not yet available.</p>;
}

function findPerception(perceptions: BankPerception[], bankName: string) {
  const normalized = normalizeBankKey(bankName);
  return perceptions.find((bank) => normalizeBankKey(bank.bank_name) === normalized);
}

type AudienceRadarPoint = {
  segment: string;
  score: number;
  rationale?: string;
};

function AudienceFitTooltip({
  active,
  payload,
}: {
  active?: boolean;
  payload?: Array<{ payload: AudienceRadarPoint }>;
}) {
  if (!active || !payload?.length) return null;

  const point = payload[0].payload;

  return (
    <div
      className="max-w-xs rounded-xl border px-3 py-2 shadow-xl"
      style={{
        background: "var(--tooltip-bg)",
        borderColor: "var(--tooltip-bd)",
        color: "var(--tooltip-tx)",
      }}
    >
      <p className="text-sm font-bold">
        {point.segment} · {point.score.toFixed(1)}
      </p>
      {point.rationale && (
        <p className="mt-1 text-xs leading-5 opacity-90">{point.rationale}</p>
      )}
    </div>
  );
}

export function BankPerceptionDrilldown({
  perceptions,
  bankOptions,
  selectedBank: controlledSelectedBank,
  onSelectedBankChange,
  selectedAssistant: controlledSelectedAssistant,
  onSelectedAssistantChange,
  audienceAffinity = [],
  audienceAffinityLoading = false,
  entityLabel = "Bank",
}: {
  perceptions: BankPerception[];
  bankOptions: string[];
  selectedBank?: string;
  onSelectedBankChange?: (bank: string) => void;
  selectedAssistant?: string;
  onSelectedAssistantChange?: (assistant: string) => void;
  audienceAffinity?: AiScoreAudienceAffinityItem[];
  audienceAffinityLoading?: boolean;
  entityLabel?: string;
}) {
  const options = bankOptions.length > 0 ? bankOptions : perceptions.map((bank) => bank.bank_name);
  const [internalSelectedBank, setInternalSelectedBank] = useState(options[0] ?? "");
  const selectedBank = controlledSelectedBank ?? internalSelectedBank;
  const setSelectedBank = onSelectedBankChange ?? setInternalSelectedBank;
  const [internalSelectedAssistant, setInternalSelectedAssistant] = useState(AI_ASSISTANTS[0]);
  const selectedAssistant = controlledSelectedAssistant ?? internalSelectedAssistant;
  const setSelectedAssistant = onSelectedAssistantChange ?? setInternalSelectedAssistant;
  const resolvedSelection = options.includes(selectedBank) ? selectedBank : options[0] ?? "";
  const matchedBank = findPerception(perceptions, resolvedSelection);
  const activeBank: BankPerception = matchedBank ?? {
    bank_name: resolvedSelection,
    summarised_perception: "",
    strengths: [],
    weaknesses: [],
    customer_segments: [],
  };

  if (!resolvedSelection) return null;

  const audienceRadarData: AudienceRadarPoint[] = [...audienceAffinity]
    .sort((a, b) => b.score - a.score)
    .map((item) => ({
      segment: item.customer_segment,
      score: item.score,
      rationale: item.rationale,
    }));
  const topAudienceGroups = audienceRadarData.slice(0, 2);
  const audienceInsight =
    topAudienceGroups.length >= 2
      ? `${activeBank.bank_name} shows strongest alignment with ${topAudienceGroups[0].segment} and ${topAudienceGroups[1].segment}.`
      : null;

  return (
    <section className="rounded-2xl border border-[var(--card-bd)] bg-[var(--card-bg-2)] p-6 shadow-lg">
      <div className="flex flex-col gap-4 lg:flex-row lg:items-start lg:justify-between">
        <div>
          <h2 className="text-lg font-semibold text-[var(--title-tx)]">
            AI Perception
          </h2>
          <p className="mt-2 text-sm text-[var(--muted-tx)]">
            Select a {entityLabel.toLowerCase()} to read how AI assistants describe it.
          </p>
        </div>

        <div className="flex flex-wrap gap-3">
          <label className="min-w-[220px] text-xs font-semibold text-[var(--muted-tx)]">
            {entityLabel}
            <select
              value={selectedBank}
              onChange={(event) => setSelectedBank(event.target.value)}
              className="mt-2 h-11 w-full rounded-xl border border-[var(--card-bd)] bg-[var(--card-bg)] px-3 text-sm font-semibold text-[var(--title-tx)] outline-none"
            >
              {options.map((bank) => (
                <option key={bank} value={bank}>
                  {bank}
                </option>
              ))}
            </select>
          </label>

          <label className="min-w-[180px] text-xs font-semibold text-[var(--muted-tx)]">
            AI Assistant
            <select
              value={selectedAssistant}
              onChange={(event) => setSelectedAssistant(event.target.value)}
              className="mt-2 h-11 w-full rounded-xl border border-[var(--card-bd)] bg-[var(--card-bg)] px-3 text-sm font-semibold text-[var(--title-tx)] outline-none"
            >
              {AI_ASSISTANTS.map((assistant) => (
                <option key={assistant} value={assistant}>
                  {assistant}
                </option>
              ))}
            </select>
          </label>
        </div>
      </div>

      <div className="mt-5 rounded-2xl border border-[var(--card-bd)] bg-blue-500/10 p-4">
        <h3 className="text-lg font-bold text-[var(--title-tx)]">{activeBank.bank_name}</h3>
        {activeBank.summarised_perception ? (
          <p className="mt-2 text-sm leading-6 text-[var(--muted-tx)]">
            {activeBank.summarised_perception}
          </p>
        ) : (
          <div className="mt-2">
            <NotAvailable />
          </div>
        )}
      </div>

      <div className="mt-4">
        <div className="rounded-2xl border border-[var(--card-bd)] bg-[var(--card-bg)] p-4">
          <p className="text-xs font-bold text-[var(--title-tx)]">Audience Fit</p>
          <p className="mt-1 text-xs text-[var(--muted-tx)]">
            How well {activeBank.bank_name} resonates with different consumer profiles.
          </p>

          {audienceAffinityLoading ? (
            <div className="mt-3 h-[320px] animate-pulse rounded-2xl bg-[var(--card-bg-2)]" />
          ) : audienceRadarData.length > 0 ? (
            <>
              <div className="mt-3 h-[320px]">
                <ResponsiveContainer width="100%" height="100%">
                  <RadarChart data={audienceRadarData} outerRadius="72%">
                    <PolarGrid stroke="var(--card-bd)" />
                    <PolarAngleAxis
                      dataKey="segment"
                      tick={{ fill: "var(--muted-tx)", fontSize: 11, fontWeight: 700 }}
                      tickFormatter={(value) => shortLabel(String(value))}
                    />
                    <PolarRadiusAxis
                      angle={90}
                      domain={[0, 100]}
                      tick={{ fill: "var(--muted-tx)", fontSize: 10, fontWeight: 700 }}
                    />
                    <Radar
                      name="Relevance"
                      dataKey="score"
                      stroke="#2563eb"
                      fill="#2563eb"
                      fillOpacity={0.24}
                      strokeWidth={2}
                    />
                    <Tooltip content={<AudienceFitTooltip />} />
                  </RadarChart>
                </ResponsiveContainer>
              </div>

              {audienceInsight && (
                <div className="mt-3 rounded-xl bg-blue-500/10 p-3">
                  <p className="text-xs font-bold uppercase tracking-[0.14em] text-blue-600">
                    Insight
                  </p>
                  <p className="mt-1 text-sm text-[var(--title-tx)]">{audienceInsight}</p>
                </div>
              )}
            </>
          ) : (
            <div className="mt-3">
              <NotAvailable />
            </div>
          )}
        </div>
      </div>
    </section>
  );
}
