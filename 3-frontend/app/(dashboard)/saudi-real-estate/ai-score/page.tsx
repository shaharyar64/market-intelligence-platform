"use client";

import { useEffect, useMemo, useState } from "react";
import DashboardTopbar from "@/components/layout/DashboardTopbar";
import {
  AI_ASSISTANTS,
  BankPerceptionDrilldown,
} from "@/components/digitalBrandHealth/BankPerceptionAnalytics";
import BankCategoryHeatmap from "@/components/digitalBrandHealth/BankCategoryHeatmap";
import ExportExcelButton from "@/components/ui/ExportExcelButton";
import {
  entityName,
  getAiScoreAudienceAffinity,
  getAiScoreBrandProjection,
  getAiScoreCitations,
  getAiScoreMarketPositioning,
  getAiScoreOverall,
  getAiScorePerceptionBanks,
  getAiScoreProducts,
  getAiScoreServices,
  type AiScoreAudienceAffinityResponse,
  type AiScoreBrandProjectionItem,
  type AiScoreBrandProjectionResponse,
  type AiScoreCitationItem,
  type AiScoreOverallItem,
  type AiScoreResponse,
  type EntityNamed,
} from "@/lib/saudiRealEstate";
import { getBankColor } from "@/lib/bankColors";
import { normalizeBankKey } from "@/lib/bankNames";
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
  ExternalLink,
  FileText,
  Gauge,
  Layers,
  Link2,
  Percent,
  ShieldCheck,
  TrendingUp,
} from "lucide-react";

type MainTab = "overview" | "perception" | "citations";

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

function entityLabel(item: EntityNamed): string {
  return entityName(item);
}

function toChartRows(items: (EntityNamed & { score: number })[] = []): ChartRow[] {
  return items
    .filter((item) => entityName(item).length > 0)
    .map((item) => ({
      name: entityLabel(item),
      score: Number(item.score.toFixed(2)),
    }));
}

function VerticalAxisTick({
  x,
  y,
  payload,
}: {
  x?: number;
  y?: number;
  payload?: { value: string };
}) {
  return (
    <g transform={`translate(${x ?? 0},${y ?? 0})`}>
      <text
        x={0}
        y={0}
        dy={8}
        textAnchor="end"
        transform="rotate(-90)"
        fill="var(--muted-tx)"
        fontSize={11}
        fontWeight={600}
      >
        {payload?.value}
      </text>
    </g>
  );
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
      <div className="h-[480px] animate-pulse rounded-xl bg-[var(--card-bg-2)]" />
    );
  }

  if (!data.length) {
    return (
      <div className="flex h-[480px] items-center justify-center rounded-xl border border-[var(--card-bd)] bg-[var(--card-bg)] text-sm text-[var(--muted-tx)]">
        No data available
      </div>
    );
  }

  const average = data.reduce((sum, item) => sum + item.score, 0) / data.length;
  const chartWidth = Math.max(data.length * 56, 640);
  const longestName = data.reduce((max, item) => Math.max(max, item.name.length), 0);
  const axisHeight = Math.min(260, Math.max(70, Math.round(longestName * 6.4) + 20));
  const chartHeight = 340 + axisHeight;

  return (
    <div className="overflow-x-auto" style={{ height: chartHeight }}>
      <div style={{ width: chartWidth, minWidth: "100%", height: "100%" }}>
        <ResponsiveContainer width="100%" height="100%">
          <BarChart data={data} margin={{ top: 28, right: 24, left: 0, bottom: 8 }}>
            <CartesianGrid strokeDasharray="3 3" strokeOpacity={0.08} vertical={false} />
            <XAxis
              dataKey="name"
              interval={0}
              height={axisHeight}
              tick={<VerticalAxisTick />}
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
                position: "insideTopRight",
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
                  typeof value === "number" ? value.toFixed(1) : `${value ?? ""}`
                }
                style={{
                  fill: "var(--muted-tx)",
                  fontSize: 11,
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
        How {bankName || "this developer"}&apos;s personality and positioning come across in AI
        responses.
      </p>

      {loading ? (
        <div className="mt-5 h-[200px] animate-pulse rounded-2xl bg-[var(--card-bg)]" />
      ) : !projection ? (
        <div className="mt-5 flex h-[120px] items-center justify-center rounded-2xl border border-[var(--card-bd)] bg-[var(--card-bg)] text-sm text-[var(--muted-tx)]">
          Not yet available for this developer.
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

type CitationSourceRow = {
  rank: number;
  title: string;
  url: string;
  domain: string;
  citationAppearances: number;
  platforms: string[];
  details: string[];
  models: string[];
};

function getCitationAssistant(item: AiScoreCitationItem) {
  const value = item.llm ?? item.platform;
  return typeof value === "string" ? value.trim() : "";
}

function CitationSourcesTable({
  sources,
  loading,
}: {
  sources: CitationSourceRow[];
  loading: boolean;
}) {
  return (
    <div className="overflow-x-auto rounded-2xl border border-[var(--card-bd)] bg-[var(--card-bg)]">
      <div className="min-w-[860px]">
        <div className="grid grid-cols-[56px_1.8fr_1fr_0.9fr_48px] gap-4 bg-[var(--card-bg-2)] px-4 py-3 text-xs font-bold uppercase tracking-[0.1em] text-[var(--muted-tx)]">
          <div>Rank</div>
          <div>Source page</div>
          <div>Citation appearances</div>
          <div>AI assistants</div>
          <div>Link</div>
        </div>

        {loading ? (
          <div className="space-y-2 p-4">
            {Array.from({ length: 6 }).map((_, index) => (
              <div key={index} className="h-12 animate-pulse rounded-lg bg-[var(--card-bg-2)]" />
            ))}
          </div>
        ) : sources.length === 0 ? (
          <div className="px-4 py-6 text-sm text-[var(--muted-tx)]">
            No sources cited by this assistant.
          </div>
        ) : (
          sources.map((source) => (
            <div
              key={source.url}
              className="grid grid-cols-[56px_1.8fr_1fr_0.9fr_48px] items-start gap-4 border-t border-[var(--card-bd)] px-4 py-3 text-sm"
            >
              <div className="font-bold text-blue-600">{source.rank}</div>
              <div className="min-w-0">
                <p
                  className="line-clamp-2 font-semibold leading-snug text-[var(--title-tx)]"
                  title={source.title}
                >
                  {source.title}
                </p>
                {source.domain !== source.title ? (
                  <p className="mt-0.5 truncate text-xs text-[var(--muted-tx)]">{source.domain}</p>
                ) : null}
                {source.details.length ? (
                  <p className="mt-1 line-clamp-2 text-xs text-[var(--muted-tx)]">
                    {source.details.join(" · ")}
                  </p>
                ) : null}
              </div>
              <div className="font-bold text-[var(--title-tx)]">{source.citationAppearances}</div>
              <div className="min-w-0 text-[var(--muted-tx)]">
                <div className="truncate">{source.platforms.join(" · ") || "Not specified"}</div>
                {source.models.length ? (
                  <div className="mt-1 truncate text-xs">{source.models.join(" · ")}</div>
                ) : null}
              </div>
              <div>
                <a
                  href={source.url}
                  target="_blank"
                  rel="noopener noreferrer"
                  title={source.url}
                  className="inline-flex h-8 w-8 items-center justify-center rounded-lg border border-[var(--card-bd)] text-[var(--muted-tx)] transition hover:border-blue-500 hover:text-blue-600"
                >
                  <ExternalLink className="h-4 w-4" />
                </a>
              </div>
            </div>
          ))
        )}
      </div>
    </div>
  );
}

export default function AIScorePage() {
  const [activeTab, setActiveTab] = useState<MainTab>("overview");
  const [selectedAssistant, setSelectedAssistant] = useState(AI_ASSISTANTS[0]);
  const [selectedPerceptionAssistant, setSelectedPerceptionAssistant] = useState(AI_ASSISTANTS[0]);
  const [selectedCitationAssistant, setSelectedCitationAssistant] = useState("All Assistants");
  const [showAllCitedSources, setShowAllCitedSources] = useState(false);
  const [overviewData, setOverviewData] = useState<AiScoreResponse>({});
  const [productData, setProductData] = useState<AiScoreResponse>({});
  const [marketPositioningData, setMarketPositioningData] = useState<AiScoreResponse>({});
  const [overallScores, setOverallScores] = useState<AiScoreOverallItem[]>([]);
  const [audienceAffinity, setAudienceAffinity] = useState<AiScoreAudienceAffinityResponse>({});
  const [brandProjection, setBrandProjection] = useState<AiScoreBrandProjectionResponse>({});
  const [citations, setCitations] = useState<AiScoreCitationItem[]>([]);
  const [bankOptions, setBankOptions] = useState<string[]>([]);
  const [perceptionSelectedBank, setPerceptionSelectedBank] = useState("");
  const [overviewLoading, setOverviewLoading] = useState(true);
  const [productLoading, setProductLoading] = useState(true);
  const [marketPositioningLoading, setMarketPositioningLoading] = useState(true);
  const [overallLoading, setOverallLoading] = useState(true);
  const [audienceAffinityLoading, setAudienceAffinityLoading] = useState(true);
  const [brandProjectionLoading, setBrandProjectionLoading] = useState(true);
  const [citationsLoading, setCitationsLoading] = useState(true);
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

    getAiScoreMarketPositioning(LLM_MAP[selectedAssistant] ?? "Overall")
      .then((res) => {
        if (!active) return;

        setMarketPositioningData(res ?? {});
        setError((current) =>
          current === "Unable to load market positioning AI score data." ? "" : current
        );
      })
      .catch(() => {
        if (!active) return;

        setMarketPositioningData({});
        setError("Unable to load market positioning AI score data.");
      })
      .finally(() => {
        if (active) setMarketPositioningLoading(false);
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

    const llm = selectedCitationAssistant === "All Assistants" ? undefined : selectedCitationAssistant;

    getAiScoreCitations(llm)
      .then((res) => {
        if (!active) return;
        setCitations(res ?? []);
      })
      .catch(() => {
        if (!active) return;
        setCitations([]);
      })
      .finally(() => {
        if (active) setCitationsLoading(false);
      });

    return () => {
      active = false;
    };
  }, [selectedCitationAssistant]);

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

  const overviewHeatmapData = overviewData;
  const productHeatmapData = productData;
  const marketPositioningHeatmapData = marketPositioningData;

  const summary = useMemo(() => {
    const topBank = overallScores[0] ?? null;
    const average =
      overallScores.length > 0
        ? overallScores.reduce((sum, item) => sum + item.score, 0) / overallScores.length
        : null;

    const topBankName = topBank ? entityLabel(topBank) : "";

    return {
      banksTracked: overallScores.length,
      topBankName: topBankName || null,
      topScore: topBank?.score ?? null,
      average,
      categoryCount: overviewCategories.length,
    };
  }, [overallScores, overviewCategories]);

  const audienceAffinityKeyMap = useMemo(() => {
    const map = new Map<string, string>();
    Object.keys(audienceAffinity).forEach((bank) => map.set(normalizeBankKey(bank), bank));
    return map;
  }, [audienceAffinity]);

  const selectedAudienceAffinity = useMemo(() => {
    const key = audienceAffinityKeyMap.get(normalizeBankKey(perceptionSelectedBank));
    return key ? audienceAffinity[key] ?? [] : [];
  }, [audienceAffinityKeyMap, audienceAffinity, perceptionSelectedBank]);

  const brandProjectionKeyMap = useMemo(() => {
    const map = new Map<string, string>();
    Object.keys(brandProjection).forEach((bank) => map.set(normalizeBankKey(bank), bank));
    return map;
  }, [brandProjection]);

  const selectedBrandProjection = useMemo(() => {
    const key = brandProjectionKeyMap.get(normalizeBankKey(perceptionSelectedBank));
    return key ? brandProjection[key] ?? null : null;
  }, [brandProjectionKeyMap, brandProjection, perceptionSelectedBank]);

  const citationStats = useMemo(() => {
    const uniqueUrls = new Set<string>();
    const platforms = new Set<string>();
    const platformsByUrl = new Map<string, Set<string>>();

    citations.forEach((item) => {
      const key = item.url.trim().toLowerCase().replace(/\/$/, "");
      uniqueUrls.add(key);
      const platform = getCitationAssistant(item);
      if (!platform) return;
      platforms.add(platform);

      const set = platformsByUrl.get(key) ?? new Set<string>();
      set.add(platform);
      platformsByUrl.set(key, set);
    });

    const citedByAllAssistants =
      platforms.size > 0
        ? Array.from(platformsByUrl.values()).filter((set) => set.size >= platforms.size).length
        : 0;

    return {
      uniqueSources: uniqueUrls.size,
      totalCitationAppearances: citations.length,
      citedByAllAssistants,
      platformCount: platforms.size,
    };
  }, [citations]);

  const groupedCitationSources = useMemo(() => {
    const bySource = new Map<
      string,
      {
        title: string;
        url: string;
        count: number;
        platforms: Set<string>;
        details: Set<string>;
        models: Set<string>;
      }
    >();

    citations.forEach((item) => {
      const key = item.url.trim().toLowerCase().replace(/\/$/, "");
      const existing = bySource.get(key) ?? {
        title: item.title,
        url: item.url,
        count: 0,
        platforms: new Set<string>(),
        details: new Set<string>(),
        models: new Set<string>(),
      };
      existing.count += 1;
      const platform = getCitationAssistant(item);
      if (platform) existing.platforms.add(platform);
      [entityName(item), item.location, item.analysis_section, item.prompt].forEach((detail) => {
        if (typeof detail === "string" && detail.trim()) existing.details.add(detail.trim());
      });
      if (typeof item.model === "string" && item.model.trim()) {
        existing.models.add(item.model.trim());
      }
      bySource.set(key, existing);
    });

    return Array.from(bySource.values())
      .sort((a, b) => b.count - a.count)
      .map((item, index) => {
        let domain = item.url;
        try {
          domain = new URL(item.url).hostname.replace(/^www\./, "");
        } catch {
          // keep raw url as a fallback if it doesn't parse
        }

        // Some source titles are extraction artifacts — a listicle's rank
        // digit ("1", "2") captured instead of the real page title. Fall
        // back to the domain rather than showing a bare number.
        const title = /^\d+$/.test(item.title.trim()) ? domain : item.title;

        return {
          rank: index + 1,
          title,
          url: item.url,
          domain,
          citationAppearances: item.count,
          platforms: Array.from(item.platforms).filter(Boolean).map(
            (platform) =>
              AI_ASSISTANTS.find(
                (assistant) => assistant.toLowerCase() === platform.toLowerCase()
              ) ?? platform
          ),
          details: Array.from(item.details),
          models: Array.from(item.models),
        };
      });
  }, [citations]);

  const topCitedSources = useMemo(
    () => groupedCitationSources.slice(0, 10),
    [groupedCitationSources]
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
              <p className="mt-1 text-sm text-white/85">Developers Tracked</p>
            </div>

            <div className="flex min-h-[126px] flex-col items-center justify-center rounded-lg bg-white/18 px-6 py-4 text-center shadow-sm backdrop-blur-md">
              <div className="mx-auto mb-2 flex h-9 w-9 items-center justify-center rounded-xl bg-fuchsia-500">
                <TrendingUp className="h-5 w-5" />
              </div>
              <p className="max-w-full truncate text-lg font-bold leading-none">
                {summary.topBankName ?? "-"}
              </p>
              <p className="mt-1 text-sm text-white/85">
                Leading Developer{summary.topScore !== null ? ` · ${formatScore(summary.topScore)}` : ""}
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
                    Compare AI discoverability scores by developer on a 100-point scale.
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
                        setMarketPositioningLoading(true);
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

              <div className="mt-5 rounded-2xl border border-[var(--card-bd)] bg-[var(--card-bg)] p-5 shadow-sm">
                <ScoreChart data={overviewChartData} loading={overallLoading} />
              </div>

              <BankCategoryHeatmap
                title="Theme Heatmap"
                description="Every developer's AI visibility score by theme, on a consistent 0–100 scale."
                data={overviewHeatmapData}
                excludeKeys={["overall"]}
                scaleMax={100}
                loading={overviewLoading}
                filenamePrefix="ai_score_theme_heatmap"
                rowLabel="Developer"
              />

              <BankCategoryHeatmap
                title="Product Heatmap"
                description="Every developer's AI visibility score by product, on the same 0–100 scale as the theme heatmap."
                data={productHeatmapData}
                excludeKeys={["overall"]}
                scaleMax={100}
                loading={productLoading}
                filenamePrefix="ai_score_product_heatmap"
                rowLabel="Developer"
              />

              <BankCategoryHeatmap
                title="Market Positioning Heatmap"
                description="Every developer's AI visibility score by market position, from Affordable to Ultra Luxury, on the same 0–100 scale."
                data={marketPositioningHeatmapData}
                excludeKeys={["overall"]}
                scaleMax={100}
                loading={marketPositioningLoading}
                filenamePrefix="ai_score_market_positioning_heatmap"
                rowLabel="Developer"
              />
            </section>
          </div>
        )}

        {activeTab === "perception" && (
          <div className="space-y-6">
            <BankPerceptionDrilldown
              perceptions={[]}
              bankOptions={bankOptions}
              entityLabel="Developer"
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
            <div className="flex flex-wrap gap-3">
              <label className="min-w-[180px] max-w-xs text-xs font-semibold text-[var(--muted-tx)]">
                AI Assistant
                <select
                  value={selectedCitationAssistant}
                  onChange={(event) => {
                    setCitationsLoading(true);
                    setSelectedCitationAssistant(event.target.value);
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

            <section className="grid grid-cols-1 gap-4 sm:grid-cols-2 xl:grid-cols-4">
              <div className="rounded-2xl border border-[var(--card-bd)] bg-[var(--card-bg-2)] p-5 shadow-sm">
                <div className="mb-3 flex h-9 w-9 items-center justify-center rounded-xl bg-blue-500/15 text-blue-600">
                  <FileText className="h-5 w-5" />
                </div>
                <p className="text-2xl font-bold text-[var(--title-tx)]">
                  {citationsLoading ? "-" : citationStats.uniqueSources}
                </p>
                <p className="mt-1 text-xs font-bold uppercase tracking-[0.1em] text-[var(--muted-tx)]">
                  Unique Sources
                </p>
                <p className="mt-1 text-sm text-[var(--muted-tx)]">
                  Different URLs in the full bibliography.
                </p>
              </div>

              <div className="rounded-2xl border border-[var(--card-bd)] bg-[var(--card-bg-2)] p-5 shadow-sm">
                <div className="mb-3 flex h-9 w-9 items-center justify-center rounded-xl bg-emerald-500/15 text-emerald-600">
                  <Layers className="h-5 w-5" />
                </div>
                <p className="text-2xl font-bold text-[var(--title-tx)]">
                  {citationsLoading ? "-" : citationStats.totalCitationAppearances}
                </p>
                <p className="mt-1 text-xs font-bold uppercase tracking-[0.1em] text-[var(--muted-tx)]">
                  Total Citation Appearances
                </p>
                <p className="mt-1 text-sm text-[var(--muted-tx)]">
                  Times sources appeared across separate AI responses.
                </p>
              </div>

              <div className="rounded-2xl border border-[var(--card-bd)] bg-[var(--card-bg-2)] p-5 shadow-sm">
                <div className="mb-3 flex h-9 w-9 items-center justify-center rounded-xl bg-orange-500/15 text-orange-600">
                  <ShieldCheck className="h-5 w-5" />
                </div>
                <p className="text-2xl font-bold text-[var(--title-tx)]">
                  {citationsLoading ? "-" : citationStats.citedByAllAssistants}
                </p>
                <p className="mt-1 text-xs font-bold uppercase tracking-[0.1em] text-[var(--muted-tx)]">
                  Cited by All {citationStats.platformCount || ""} Assistants
                </p>
                <p className="mt-1 text-sm text-[var(--muted-tx)]">
                  Sources returned by every AI assistant tracked.
                </p>
              </div>

              <div className="rounded-2xl border border-[var(--card-bd)] bg-[var(--card-bg-2)] p-5 shadow-sm">
                <p className="text-xs font-bold uppercase tracking-[0.1em] text-[var(--muted-tx)]">
                  What the counts mean
                </p>
                <p className="mt-2 text-sm leading-6 text-[var(--title-tx)]">
                  The same URL is counted once per individual AI response, even if it appears more
                  than once in that answer.
                </p>
              </div>
            </section>

            <section className="rounded-2xl border border-[var(--card-bd)] bg-[var(--card-bg-2)] p-6 shadow-lg">
              <div className="mb-5 flex flex-col gap-3 sm:flex-row sm:items-start sm:justify-between">
                <div>
                  <h2 className="text-lg font-semibold text-[var(--title-tx)]">
                    {showAllCitedSources
                      ? "All Citation Sources"
                      : "Top 10 cited sources"}
                  </h2>
                  {showAllCitedSources && (
                    <p className="mt-2 text-sm text-[var(--muted-tx)]">
                      Every unique source cited across all AI responses (
                      {groupedCitationSources.length} total).
                    </p>
                  )}
                </div>
                <button
                  type="button"
                  onClick={() => setShowAllCitedSources((current) => !current)}
                  className="text-sm font-semibold text-blue-600 hover:underline"
                >
                  {showAllCitedSources ? "← Show top 10" : "View all sources →"}
                </button>
              </div>

              <div className={showAllCitedSources ? "max-h-[600px] overflow-y-auto" : undefined}>
                <CitationSourcesTable
                  sources={showAllCitedSources ? groupedCitationSources : topCitedSources}
                  loading={citationsLoading}
                />
              </div>
            </section>

            <div className="rounded-2xl border border-[var(--card-bd)] bg-blue-500/10 p-4 text-sm text-[var(--title-tx)]">
              <span className="font-bold">Ranking rule: </span>
              Order sources by citation appearances: the number of separate AI responses containing
              the normalized URL. Ties can share the same rank.
            </div>
          </div>
        )}
      </main>
    </div>
  );
}
