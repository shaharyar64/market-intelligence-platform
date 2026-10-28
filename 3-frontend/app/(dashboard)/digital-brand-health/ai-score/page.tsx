"use client";

import { useEffect, useMemo, useState } from "react";
import DashboardTopbar from "@/components/layout/DashboardTopbar";
import {
  AI_ASSISTANTS,
  BankPerceptionDrilldown,
} from "@/components/digitalBrandHealth/BankPerceptionAnalytics";
import BankCategoryHeatmap from "@/components/digitalBrandHealth/BankCategoryHeatmap";
import { AxisTick, getBarChartDimensions } from "@/components/digitalBrandHealth/ChartAxisTick";
import CitationAnalysis from "@/components/digitalBrandHealth/CitationAnalysis";
import ExportExcelButton from "@/components/ui/ExportExcelButton";
import { bankPerceptions } from "@/lib/bankingPerceptionData";
import {
  getAiScoreAudienceAffinity,
  getAiScoreBrandProjection,
  getAiScoreCitations,
  getAiScoreOverall,
  getAiScorePerceptionBanks,
  getAiScoreProducts,
  getAiScoreServices,
  getDigitalDiscoverabilityOverall,
  getDigitalDiscoverabilityProducts,
  getDigitalDiscoverabilityServices,
  type AiScoreAudienceAffinityResponse,
  type AiScoreBrandProjectionItem,
  type AiScoreBrandProjectionResponse,
  type AiScoreOverallItem,
  type AiScoreResponse,
} from "@/lib/digitalBrandHealth";
import { getBankColor } from "@/lib/bankColors";
import {
  Bar,
  BarChart,
  CartesianGrid,
  Cell,
  LabelList,
  ReferenceLine,
  ResponsiveContainer,
  Tooltip,
  XAxis,
  YAxis,
} from "recharts";
import {
  BrainCircuit,
  Database,
  Gauge,
  Link2,
  Percent,
  Smartphone,
  TrendingUp,
} from "lucide-react";

type MainTab = "overview" | "digital-discoverability" | "perception" | "citations";

const LLM_MAP: Record<string, string> = {
  "All Assistants": "Overall",
  ChatGPT: "ChatGPT",
  Gemini: "Gemini",
  Claude: "Claude",
  Grok: "Grok",
};

type ChartRow = {
  name: string;
  score: number;
};

function formatScore(value: number | null) {
  return value === null ? "-" : value.toFixed(2);
}

function toChartRows(items: { bank: string; score: number }[] = []): ChartRow[] {
  return items.map((item) => ({
    name: item.bank,
    score: Number(item.score.toFixed(2)),
  }));
}

function ScoreChart({
  data,
  loading = false,
}: {
  data: ChartRow[];
  loading?: boolean;
}) {
  if (loading) {
    return (
      <div className="mt-6 h-[360px] animate-pulse rounded-2xl border border-[var(--card-bd)] bg-[var(--card-bg)] p-5 shadow-sm" />
    );
  }

  if (!data.length) {
    return (
      <div className="mt-6 flex h-[360px] items-center justify-center rounded-2xl border border-[var(--card-bd)] bg-[var(--card-bg)] p-5 text-sm text-[var(--muted-tx)] shadow-sm">
        No data available
      </div>
    );
  }

  const average = data.reduce((sum, item) => sum + item.score, 0) / data.length;
  const { chartWidth, axisHeight, chartHeight } = getBarChartDimensions(
    data.map((item) => item.name)
  );

  return (
    <div className="mt-6 overflow-x-auto rounded-2xl border border-[var(--card-bd)] bg-[var(--card-bg)] p-5 shadow-sm">
      <div style={{ width: chartWidth, minWidth: "100%", height: chartHeight }}>
        <ResponsiveContainer
          width="100%"
          height="100%"
          initialDimension={{ width: chartWidth, height: chartHeight }}
        >
          <BarChart data={data} margin={{ top: 28, right: 96, left: 0, bottom: 8 }}>
            <CartesianGrid strokeDasharray="3 3" strokeOpacity={0.08} vertical={false} />
            <XAxis
              dataKey="name"
              interval={0}
              height={axisHeight}
              tick={<AxisTick />}
              tickLine={false}
              axisLine={{ stroke: "var(--card-bd)" }}
            />
            <YAxis
              domain={[0, 100]}
              tick={{ fill: "var(--muted-tx)", fontSize: 12, fontWeight: 600 }}
              tickLine={false}
              axisLine={false}
            />
            <Tooltip
              formatter={(value) => [`${value}`, "AI Score"]}
              contentStyle={{
                background: "var(--tooltip-bg)",
                border: "1px solid var(--tooltip-bd)",
                borderRadius: 12,
                color: "var(--tooltip-tx)",
              }}
              labelStyle={{ color: "var(--tooltip-tx)" }}
              itemStyle={{ color: "var(--tooltip-tx)" }}
              cursor={{ fill: "rgba(84,170,236,0.08)" }}
            />
            <ReferenceLine
              y={average}
              stroke="var(--muted-tx)"
              strokeDasharray="4 4"
              strokeWidth={1.5}
              ifOverflow="extendDomain"
              label={{
                value: `Average ${average.toFixed(1)}`,
                position: "right",
                fill: "var(--muted-tx)",
                fontSize: 12,
                fontWeight: 700,
              }}
            />
            <Bar dataKey="score" radius={[8, 8, 0, 0]} maxBarSize={40}>
              {data.map((item, index) => (
                <Cell key={index} fill={getBankColor(item.name, index)} />
              ))}
              <LabelList
                dataKey="score"
                position="top"
                formatter={(value) =>
                  typeof value === "number" ? value.toFixed(2) : `${value ?? ""}`
                }
                style={{
                  fill: "var(--muted-tx)",
                  fontSize: 13,
                  fontWeight: 700,
                }}
              />
            </Bar>
          </BarChart>
        </ResponsiveContainer>
      </div>
    </div>
  );
}

function BrandProjectionCard({
  projection,
  loading,
  bankName,
}: {
  projection: AiScoreBrandProjectionItem | null;
  loading: boolean;
  bankName: string;
}) {
  return (
    <section className="rounded-2xl border border-[var(--card-bd)] bg-[var(--card-bg-2)] p-6 shadow-lg">
      <h2 className="text-lg font-semibold text-[var(--title-tx)]">Brand Projection</h2>
      <p className="mt-2 text-sm text-[var(--muted-tx)]">
        How {bankName || "this bank"}&apos;s personality and positioning come across in AI
        responses.
      </p>

      {loading ? (
        <div className="mt-5 h-[200px] animate-pulse rounded-2xl bg-[var(--card-bg)]" />
      ) : !projection ? (
        <div className="mt-5 flex h-[120px] items-center justify-center rounded-2xl border border-[var(--card-bd)] bg-[var(--card-bg)] text-sm text-[var(--muted-tx)]">
          Not yet available for this bank.
        </div>
      ) : (
        <div className="mt-5 space-y-4">
          <div className="rounded-2xl border border-[var(--card-bd)] bg-blue-500/10 p-4">
            <p className="text-sm leading-6 text-[var(--title-tx)]">{projection.personality}</p>
          </div>

          <div className="grid grid-cols-1 gap-4 lg:grid-cols-2">
            <div className="rounded-2xl border border-[var(--card-bd)] bg-[var(--card-bg)] p-4">
              <p className="text-xs font-bold uppercase tracking-[0.14em] text-[var(--muted-tx)]">
                Strengths
              </p>
              <ol className="mt-2 space-y-1 text-sm text-[var(--title-tx)]">
                {projection.strengths.map((item, index) => (
                  <li key={item}>
                    {index + 1}. {item}
                  </li>
                ))}
              </ol>
            </div>

            <div className="rounded-2xl border border-[var(--card-bd)] bg-[var(--card-bg)] p-4">
              <p className="text-xs font-bold uppercase tracking-[0.14em] text-[var(--muted-tx)]">
                Positioning Opportunities
              </p>
              <ol className="mt-2 space-y-1 text-sm text-[var(--title-tx)]">
                {projection.positioning_opportunities.map((item, index) => (
                  <li key={item}>
                    {index + 1}. {item}
                  </li>
                ))}
              </ol>
            </div>
          </div>
        </div>
      )}
    </section>
  );
}

export default function AIScorePage() {
  const [activeTab, setActiveTab] = useState<MainTab>("overview");
  const [selectedAssistant, setSelectedAssistant] = useState(AI_ASSISTANTS[0]);
  const [selectedDigitalAssistant, setSelectedDigitalAssistant] = useState(AI_ASSISTANTS[0]);
  const [selectedPerceptionAssistant, setSelectedPerceptionAssistant] = useState(AI_ASSISTANTS[0]);
  const [selectedCitationAssistant, setSelectedCitationAssistant] = useState("All Assistants");
  const [overviewData, setOverviewData] = useState<AiScoreResponse>({});
  const [productData, setProductData] = useState<AiScoreResponse>({});
  const [overallScores, setOverallScores] = useState<AiScoreOverallItem[]>([]);
  const [digitalOverviewData, setDigitalOverviewData] = useState<AiScoreResponse>({});
  const [digitalProductData, setDigitalProductData] = useState<AiScoreResponse>({});
  const [digitalOverallScores, setDigitalOverallScores] = useState<AiScoreOverallItem[]>([]);
  const [audienceAffinity, setAudienceAffinity] = useState<AiScoreAudienceAffinityResponse>({});
  const [brandProjection, setBrandProjection] = useState<AiScoreBrandProjectionResponse>({});
  const [citationAssistantOptions, setCitationAssistantOptions] = useState<string[]>([
    "All Assistants",
  ]);
  const [bankOptions, setBankOptions] = useState<string[]>([]);
  const [perceptionSelectedBank, setPerceptionSelectedBank] = useState("");
  const [overviewLoading, setOverviewLoading] = useState(true);
  const [productLoading, setProductLoading] = useState(true);
  const [overallLoading, setOverallLoading] = useState(true);
  const [digitalOverviewLoading, setDigitalOverviewLoading] = useState(true);
  const [digitalProductLoading, setDigitalProductLoading] = useState(true);
  const [digitalOverallLoading, setDigitalOverallLoading] = useState(true);
  const [audienceAffinityLoading, setAudienceAffinityLoading] = useState(true);
  const [brandProjectionLoading, setBrandProjectionLoading] = useState(true);
  const [error, setError] = useState("");

  useEffect(() => {
    let active = true;

    getAiScoreServices(LLM_MAP[selectedAssistant] ?? "Overall")
      .then((res) => {
        if (!active) return;

        setOverviewData(res ?? {});
        setError((current) =>
          current === "Unable to load overview AI score data." ? "" : current
        );
      })
      .catch(() => {
        if (!active) return;

        setOverviewData({});
        setError("Unable to load overview AI score data.");
      })
      .finally(() => {
        if (active) setOverviewLoading(false);
      });

    return () => {
      active = false;
    };
  }, [selectedAssistant]);

  useEffect(() => {
    let active = true;

    getAiScoreProducts(LLM_MAP[selectedAssistant] ?? "Overall")
      .then((res) => {
        if (!active) return;

        setProductData(res ?? {});
        setError((current) =>
          current === "Unable to load product AI score data." ? "" : current
        );
      })
      .catch(() => {
        if (!active) return;

        setProductData({});
        setError("Unable to load product AI score data.");
      })
      .finally(() => {
        if (active) setProductLoading(false);
      });

    return () => {
      active = false;
    };
  }, [selectedAssistant]);

  useEffect(() => {
    let active = true;

    getAiScoreOverall(LLM_MAP[selectedAssistant] ?? "Overall")
      .then((res) => {
        if (!active) return;
        setOverallScores(res ?? []);
      })
      .catch(() => {
        if (!active) return;
        setOverallScores([]);
      })
      .finally(() => {
        if (active) setOverallLoading(false);
      });

    return () => {
      active = false;
    };
  }, [selectedAssistant]);

  useEffect(() => {
    let active = true;

    getDigitalDiscoverabilityServices(LLM_MAP[selectedDigitalAssistant] ?? "Overall")
      .then((res) => {
        if (!active) return;
        setDigitalOverviewData(res ?? {});
      })
      .catch(() => {
        if (!active) return;
        setDigitalOverviewData({});
      })
      .finally(() => {
        if (active) setDigitalOverviewLoading(false);
      });

    return () => {
      active = false;
    };
  }, [selectedDigitalAssistant]);

  useEffect(() => {
    let active = true;

    getDigitalDiscoverabilityProducts(LLM_MAP[selectedDigitalAssistant] ?? "Overall")
      .then((res) => {
        if (!active) return;
        setDigitalProductData(res ?? {});
      })
      .catch(() => {
        if (!active) return;
        setDigitalProductData({});
      })
      .finally(() => {
        if (active) setDigitalProductLoading(false);
      });

    return () => {
      active = false;
    };
  }, [selectedDigitalAssistant]);

  useEffect(() => {
    let active = true;

    getDigitalDiscoverabilityOverall(LLM_MAP[selectedDigitalAssistant] ?? "Overall")
      .then((res) => {
        if (!active) return;
        setDigitalOverallScores(res ?? []);
      })
      .catch(() => {
        if (!active) return;
        setDigitalOverallScores([]);
      })
      .finally(() => {
        if (active) setDigitalOverallLoading(false);
      });

    return () => {
      active = false;
    };
  }, [selectedDigitalAssistant]);

  useEffect(() => {
    if (!perceptionSelectedBank) return;
    let active = true;

    getAiScoreAudienceAffinity(
      LLM_MAP[selectedPerceptionAssistant] ?? "Overall",
      perceptionSelectedBank
    )
      .then((res) => {
        if (!active) return;
        setAudienceAffinity(res ?? {});
      })
      .catch(() => {
        if (!active) return;
        setAudienceAffinity({});
      })
      .finally(() => {
        if (active) setAudienceAffinityLoading(false);
      });

    return () => {
      active = false;
    };
  }, [perceptionSelectedBank, selectedPerceptionAssistant]);

  useEffect(() => {
    if (!perceptionSelectedBank) return;
    let active = true;

    getAiScoreBrandProjection(
      LLM_MAP[selectedPerceptionAssistant] ?? "Overall",
      perceptionSelectedBank
    )
      .then((res) => {
        if (!active) return;
        setBrandProjection(res ?? {});
      })
      .catch(() => {
        if (!active) return;
        setBrandProjection({});
      })
      .finally(() => {
        if (active) setBrandProjectionLoading(false);
      });

    return () => {
      active = false;
    };
  }, [perceptionSelectedBank, selectedPerceptionAssistant]);

  useEffect(() => {
    let active = true;

    getAiScoreCitations()
      .then((res) => {
        if (!active) return;
        // kpi.assistants is the full cross-model assistant list for the dropdown.
        if (res.kpi) setCitationAssistantOptions(["All Assistants", ...(res.kpi.assistants ?? [])]);
      })
      .catch(() => {});

    return () => {
      active = false;
    };
  }, []);

  useEffect(() => {
    let active = true;

    getAiScorePerceptionBanks()
      .then((res) => {
        if (!active) return;
        const banks = (res.banks ?? []).filter(Boolean);
        setBankOptions(banks);
        setPerceptionSelectedBank((current) => current || banks[0] || "");
      })
      .catch(() => {
        if (!active) return;
        setBankOptions([]);
      });

    return () => {
      active = false;
    };
  }, []);

  const overviewCategories = useMemo(() => Object.keys(overviewData), [overviewData]);

  const overviewChartData = useMemo(() => toChartRows(overallScores), [overallScores]);

  const digitalOverviewChartData = useMemo(
    () => toChartRows(digitalOverallScores),
    [digitalOverallScores]
  );

  const summary = useMemo(() => {
    const topBank = overallScores[0] ?? null;
    const average =
      overallScores.length > 0
        ? overallScores.reduce((sum, item) => sum + item.score, 0) / overallScores.length
        : null;

    return {
      banksTracked: overallScores.length,
      topBankName: topBank?.bank ?? null,
      topScore: topBank?.score ?? null,
      average,
      categoryCount: overviewCategories.length,
    };
  }, [overallScores, overviewCategories]);

  const selectedAudienceAffinity = useMemo(
    () => audienceAffinity[perceptionSelectedBank] ?? [],
    [audienceAffinity, perceptionSelectedBank]
  );

  const selectedBrandProjection = useMemo(
    () => brandProjection[perceptionSelectedBank] ?? null,
    [brandProjection, perceptionSelectedBank]
  );

  return (
    <div className="min-h-screen">
      <DashboardTopbar title="BrandIQ" />

      <main className="p-8">
        <section className="mb-6 overflow-hidden rounded-2xl bg-gradient-to-r from-[#1f6feb] via-[#0f766e] to-[#7c3aed] p-6 text-white shadow-lg">
          <div className="grid gap-5 lg:grid-cols-[1.35fr_1fr_1fr_1fr] lg:items-center">
            <div className="flex flex-col justify-center">
              <div className="mb-3 flex h-10 w-10 items-center justify-center rounded-xl bg-white/18">
                <Gauge className="h-5 w-5" />
              </div>
              <h1 className="text-2xl font-bold">AI Score Overview</h1>
              <p className="mt-3 max-w-md text-sm leading-6 text-white/90">
                Represents the brand&apos;s visibility across large language models
                (LLMs), indicating how strongly and accurately it appears in
                AI-generated responses. It includes the overall visibility score
                and performance across specific associations and product-related
                searches.
              </p>
            </div>

            <div className="flex min-h-[126px] flex-col items-center justify-center rounded-lg bg-white/18 px-6 py-4 text-center shadow-sm backdrop-blur-md">
              <div className="mx-auto mb-2 flex h-9 w-9 items-center justify-center rounded-xl bg-sky-500">
                <Database className="h-5 w-5" />
              </div>
              <p className="text-2xl font-bold leading-none">{summary.banksTracked || "-"}</p>
              <p className="mt-1 text-sm text-white/85">Banks Tracked</p>
            </div>

            <div className="flex min-h-[126px] flex-col items-center justify-center rounded-lg bg-white/18 px-6 py-4 text-center shadow-sm backdrop-blur-md">
              <div className="mx-auto mb-2 flex h-9 w-9 items-center justify-center rounded-xl bg-fuchsia-500">
                <TrendingUp className="h-5 w-5" />
              </div>
              <p className="max-w-full truncate text-lg font-bold leading-none">
                {summary.topBankName ?? "-"}
              </p>
              <p className="mt-1 text-sm text-white/85">
                Leading Bank{summary.topScore !== null ? ` · ${formatScore(summary.topScore)}` : ""}
              </p>
            </div>

            <div className="flex min-h-[126px] flex-col items-center justify-center rounded-lg bg-white/18 px-6 py-4 text-center shadow-sm backdrop-blur-md">
              <div className="mx-auto mb-2 flex h-9 w-9 items-center justify-center rounded-xl bg-orange-500">
                <Percent className="h-5 w-5" />
              </div>
              <p className="text-2xl font-bold leading-none">{formatScore(summary.average)}</p>
              <p className="mt-1 text-sm text-white/85">Category Average</p>
            </div>
          </div>
        </section>

        {error && (
          <div className="mb-6 rounded-lg border border-red-500/30 bg-red-500/10 px-4 py-3 text-sm font-medium text-red-500">
            {error}
          </div>
        )}

        <div className="mb-6 inline-flex rounded-full border border-[var(--card-bd)] bg-[var(--card-bg)] p-1 shadow-sm">
          {[
            { label: "Discoverability", value: "overview" as const, icon: Gauge },
            {
              label: "Digital Discoverability",
              value: "digital-discoverability" as const,
              icon: Smartphone,
            },
            { label: "Perception", value: "perception" as const, icon: BrainCircuit },
            { label: "Citations", value: "citations" as const, icon: Link2 },
          ].map((tab) => {
            const active = activeTab === tab.value;
            const Icon = tab.icon;

            return (
              <button
                key={tab.value}
                type="button"
                onClick={() => setActiveTab(tab.value)}
                className="flex h-10 items-center gap-2 rounded-full px-4 text-sm font-semibold transition"
                style={{
                  background: active ? "#2563eb" : "transparent",
                  color: active ? "#ffffff" : "var(--muted-tx)",
                }}
              >
                <Icon className="h-4 w-4" />
                {tab.label}
              </button>
            );
          })}
        </div>

        {activeTab === "overview" && (
          <div className="space-y-6">
            <section className="rounded-2xl border border-[var(--card-bd)] bg-[var(--card-bg-2)] p-6 shadow-lg">
              <div className="flex flex-col gap-4 lg:flex-row lg:items-start lg:justify-between">
                <div>
                  <h3 className="text-base font-semibold text-[var(--title-tx)]">
                    Discoverability AI Score
                  </h3>
                  <p className="mt-1 text-sm text-[var(--muted-tx)]">
                    Compare AI discoverability scores by bank on a 100-point scale.
                  </p>
                </div>

                <div className="flex flex-wrap items-start gap-3">
                  <ExportExcelButton
                    rows={overviewChartData.map((item) => ({ ...item }))}
                    filename="ai_score_discoverability_overview"
                    sheetName="Discoverability AI Score"
                    disabled={overallLoading}
                  />
                  <label className="min-w-[180px] text-xs font-semibold text-[var(--muted-tx)]">
                    AI Assistant
                    <select
                      value={selectedAssistant}
                      onChange={(event) => {
                        setOverallLoading(true);
                        setOverviewLoading(true);
                        setProductLoading(true);
                        setSelectedAssistant(event.target.value);
                      }}
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

              <ScoreChart data={overviewChartData} loading={overallLoading} />

              <BankCategoryHeatmap
                title="Theme Heatmap"
                description="Every bank's AI visibility score by theme, on a consistent 0–100 scale."
                data={overviewData}
                excludeKeys={["overall"]}
                scaleMax={100}
                loading={overviewLoading}
                filenamePrefix="ai_score_theme_heatmap"
              />

              <BankCategoryHeatmap
                title="Product Heatmap"
                description="Every bank's AI visibility score by product, on the same 0–100 scale as the theme heatmap."
                data={productData}
                excludeKeys={["overall"]}
                scaleMax={100}
                loading={productLoading}
                filenamePrefix="ai_score_product_heatmap"
              />
            </section>
          </div>
        )}

        {activeTab === "digital-discoverability" && (
          <div className="space-y-6">
            <section className="rounded-2xl border border-[var(--card-bd)] bg-[var(--card-bg-2)] p-6 shadow-lg">
              <div className="flex flex-col gap-4 lg:flex-row lg:items-start lg:justify-between">
                <div>
                  <h3 className="text-base font-semibold text-[var(--title-tx)]">
                    Digital Discoverability AI Score
                  </h3>
                  <p className="mt-1 text-sm text-[var(--muted-tx)]">
                    Compare AI discoverability scores for digital-only banks on a 100-point scale.
                  </p>
                </div>

                <div className="flex flex-wrap items-start gap-3">
                  <ExportExcelButton
                    rows={digitalOverviewChartData.map((item) => ({ ...item }))}
                    filename="ai_score_digital_discoverability_overview"
                    sheetName="Digital Discoverability AI Score"
                    disabled={digitalOverallLoading}
                  />
                  <label className="min-w-[180px] text-xs font-semibold text-[var(--muted-tx)]">
                    AI Assistant
                    <select
                      value={selectedDigitalAssistant}
                      onChange={(event) => {
                        setDigitalOverallLoading(true);
                        setDigitalOverviewLoading(true);
                        setDigitalProductLoading(true);
                        setSelectedDigitalAssistant(event.target.value);
                      }}
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

              <ScoreChart data={digitalOverviewChartData} loading={digitalOverallLoading} />

              <BankCategoryHeatmap
                title="Theme Heatmap"
                description="Every digital bank's AI visibility score by theme, on a consistent 0–100 scale."
                data={digitalOverviewData}
                excludeKeys={["overall"]}
                scaleMax={100}
                loading={digitalOverviewLoading}
                filenamePrefix="ai_score_digital_theme_heatmap"
              />

              <BankCategoryHeatmap
                title="Product Heatmap"
                description="Every digital bank's AI visibility score by product, on the same 0–100 scale as the theme heatmap."
                data={digitalProductData}
                excludeKeys={["overall"]}
                scaleMax={100}
                loading={digitalProductLoading}
                filenamePrefix="ai_score_digital_product_heatmap"
              />
            </section>
          </div>
        )}

        {activeTab === "perception" && (
          <div className="space-y-6">
            <BankPerceptionDrilldown
              perceptions={bankPerceptions}
              bankOptions={bankOptions}
              selectedBank={perceptionSelectedBank}
              onSelectedBankChange={(bank) => {
                setAudienceAffinityLoading(true);
                setBrandProjectionLoading(true);
                setPerceptionSelectedBank(bank);
              }}
              selectedAssistant={selectedPerceptionAssistant}
              onSelectedAssistantChange={(assistant) => {
                setAudienceAffinityLoading(true);
                setBrandProjectionLoading(true);
                setSelectedPerceptionAssistant(assistant);
              }}
              audienceAffinity={selectedAudienceAffinity}
              audienceAffinityLoading={audienceAffinityLoading}
            />

            <BrandProjectionCard
              projection={selectedBrandProjection}
              loading={brandProjectionLoading}
              bankName={perceptionSelectedBank}
            />
          </div>
        )}

        {activeTab === "citations" && (
          <div className="space-y-6">
            <label className="block max-w-xs text-xs font-semibold text-[var(--muted-tx)]">
              AI Assistant
              <select
                value={selectedCitationAssistant}
                onChange={(event) => setSelectedCitationAssistant(event.target.value)}
                className="mt-2 h-11 w-full rounded-xl border border-[var(--card-bd)] bg-[var(--card-bg)] px-3 text-sm font-semibold text-[var(--title-tx)] outline-none"
              >
                {citationAssistantOptions.map((assistant) => (
                  <option key={assistant} value={assistant}>
                    {assistant}
                  </option>
                ))}
              </select>
            </label>
            <CitationAnalysis
              assistant={selectedCitationAssistant === "All Assistants" ? undefined : selectedCitationAssistant}
            />
          </div>
        )}
      </main>
    </div>
  );
}
