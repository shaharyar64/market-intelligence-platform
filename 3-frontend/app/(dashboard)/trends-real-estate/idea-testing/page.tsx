"use client";

import { Suspense, useEffect, useRef, useState, type ReactNode } from "react";
import Link from "next/link";
import { usePathname, useRouter, useSearchParams } from "next/navigation";
import { AnimatePresence, motion, MotionConfig, type Variants } from "framer-motion";
import { BookOpen } from "lucide-react";

import ComparisonView from "@/components/ideaTesting/ComparisonView";
import HistoryList from "@/components/ideaTesting/HistoryList";
import ResultsView from "@/components/ideaTesting/ResultsView";
import StepConcept from "@/components/ideaTesting/StepConcept";
import StepHeader from "@/components/ideaTesting/StepHeader";
import StepMode from "@/components/ideaTesting/StepMode";
import StepTestType from "@/components/ideaTesting/StepTestType";
import WizardStepper, { type WizardStepId } from "@/components/ideaTesting/WizardStepper";
import DashboardTopbar from "@/components/layout/DashboardTopbar";
import { InlineError, Skel } from "@/components/ui/RealEstateTrendsPanels";
import MarketSelect, { useMarket } from "@/components/ui/MarketSelect";
import {
  assessConcepts, getAssessment, getComparison, getHistory,
  type AssessResponse, type ConceptMode, type HistoryItem, type TestType,
} from "@/lib/ideaTesting";
import { TEST_TYPES } from "@/lib/ideaTestingFramework";
import { friendlyError } from "@/lib/foodIntelligence";

type Phase = WizardStepId | "assessing" | "loading" | "results" | "error";

const PHASE_ORDER: Record<Phase, number> = {
  type: 0, mode: 1, concept: 2, assessing: 3, loading: 3, results: 4, error: 4,
};

const EASE_OUT: [number, number, number, number] = [0.16, 1, 0.3, 1];

const stepVariants: Variants = {
  enter: (direction: number) => ({ opacity: 0, x: 24 * direction }),
  center: { opacity: 1, x: 0, transition: { duration: 0.3, ease: EASE_OUT } },
  exit: (direction: number) => ({
    opacity: 0, x: -24 * direction, transition: { duration: 0.15, ease: [0.4, 0, 1, 1] },
  }),
};

function isWizardStep(phase: Phase): phase is WizardStepId {
  return phase === "type" || phase === "mode" || phase === "concept";
}

function KnowledgeBaseLink() {
  return (
    <Link
      href="/trends-real-estate/knowledge-base"
      className="flex min-h-11 items-center gap-1.5 whitespace-nowrap rounded-full px-3.5 py-1.5 text-xs font-semibold transition-colors"
      style={{
        background: "var(--card-bg-2)",
        color: "var(--body-tx)",
        border: "1px solid var(--card-bd)",
      }}
    >
      <BookOpen size={13} aria-hidden="true" />
      Knowledge Base
    </Link>
  );
}

function IdeaTestingPageContent() {
  const [market, setMarket] = useMarket();
  const router = useRouter();
  const pathname = usePathname();
  const searchParams = useSearchParams();
  const assessmentIdParam = searchParams.get("assessment");
  const comparisonIdParam = searchParams.get("comparison");

  const [phase, setPhase] = useState<Phase>(
    assessmentIdParam || comparisonIdParam ? "loading" : "type",
  );
  const [direction, setDirection] = useState(1);
  const phaseRef = useRef(phase);
  useEffect(() => { phaseRef.current = phase; }, [phase]);
  const [testType, setTestType] = useState<TestType | null>(null);
  const [mode, setMode] = useState<ConceptMode | null>(null);
  const [result, setResult] = useState<AssessResponse | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [conceptIds, setConceptIds] = useState<string[] | null>(null);
  const [history, setHistory] = useState<HistoryItem[]>([]);
  const [historyLoading, setHistoryLoading] = useState(true);

  useEffect(() => {
    getHistory().then((r) => setHistory(r.items)).catch(() => {}).finally(() => setHistoryLoading(false));
  }, []);

  function go(next: Phase) {
    setDirection(PHASE_ORDER[next] >= PHASE_ORDER[phaseRef.current] ? 1 : -1);
    phaseRef.current = next;
    setPhase(next);
  }

  function setResultUrl(id: string, kind: "assessment" | "comparison") {
    const qs = new URLSearchParams(searchParams.toString());
    qs.delete("assessment");
    qs.delete("comparison");
    qs.set(kind, id);
    router.replace(`${pathname}?${qs.toString()}`, { scroll: false });
  }

  function openHistoryItem(id: string, kind: "assessment" | "comparison") {
    const qs = new URLSearchParams(searchParams.toString());
    qs.delete("assessment");
    qs.delete("comparison");
    qs.set(kind, id);
    router.push(`${pathname}?${qs.toString()}`, { scroll: false });
  }

  function clearResultUrl() {
    const qs = new URLSearchParams(searchParams.toString());
    qs.delete("assessment");
    qs.delete("comparison");
    const qsStr = qs.toString();
    router.replace(qsStr ? `${pathname}?${qsStr}` : pathname, { scroll: false });
  }

  async function runAssessment(ids: string[]) {
    if (!testType || !mode) return;
    go("assessing");
    setError(null);
    try {
      const response = await assessConcepts(ids, mode, testType, market);
      setResult(response);
      go("results");
      if (response.comparison) {
        loadedResultUrl.current = `c:${response.comparison.comparison_id}`;
        setResultUrl(response.comparison.comparison_id, "comparison");
      } else {
        loadedResultUrl.current = `a:${response.assessments[0].assessment_id}`;
        setResultUrl(response.assessments[0].assessment_id, "assessment");
      }
      getHistory().then((r) => setHistory(r.items)).catch(() => {});
    } catch (e) {
      setError(friendlyError(e));
      go("error");
    }
  }

  function handleConceptsReady(ids: string[]) {
    setConceptIds(ids);
    void runAssessment(ids);
  }

  function resetWizard() {
    go("type");
    setTestType(null);
    setMode(null);
    setResult(null);
    setError(null);
    setConceptIds(null);
  }

  function restart() {
    resetWizard();
    clearResultUrl();
  }

  const loadedResultUrl = useRef<string | null>(null);
  useEffect(() => {
    const idKey = assessmentIdParam ? `a:${assessmentIdParam}` : comparisonIdParam ? `c:${comparisonIdParam}` : null;
    if (!idKey) {
      const p = phaseRef.current;
      if (loadedResultUrl.current && (p === "results" || p === "loading" || p === "error")) {
        resetWizard();
      }
      loadedResultUrl.current = null;
      return;
    }
    if (loadedResultUrl.current === idKey) return;
    loadedResultUrl.current = idKey;
    go("loading");
    setError(null);
    const load = assessmentIdParam
      ? getAssessment(assessmentIdParam).then((a) => ({ assessments: [a], comparison: null }))
      : getComparison(comparisonIdParam!);
    load
      .then((data) => {
        setResult(data);
        go("results");
      })
      .catch((e) => {
        setError(friendlyError(e));
        go("error");
      });
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [assessmentIdParam, comparisonIdParam]);

  function handleErrorRetry() {
    if (assessmentIdParam || comparisonIdParam) {
      restart();
      return;
    }
    if (conceptIds) {
      void runAssessment(conceptIds);
      return;
    }
    go("concept");
  }

  const testTypeLabel = TEST_TYPES.find((t) => t.id === testType)?.label;
  const modeLabel = mode === "multiple" ? "Compare up to 3" : mode === "single" ? "Single concept" : undefined;

  function renderBody(): ReactNode {
    switch (phase) {
      case "type":
        return (
          <div className="mx-auto w-full max-w-5xl">
            <StepHeader
              title="Pressure-test your concept"
              description="Score it against the InsightFactor 6C framework, grounded in the real posts and trends already collected for this market."
              action={<KnowledgeBaseLink />}
            />
            <StepTestType onSelect={(t) => { setTestType(t); go("mode"); }} />
            <HistoryList items={history} loading={historyLoading} onSelect={openHistoryItem} />
          </div>
        );
      case "mode":
        return (
          <div className="mx-auto w-full max-w-5xl">
            <StepHeader
              title="One concept or several?"
              description="Get a focused read on a single concept, or score up to three and see which one leads on each factor."
              onBack={() => go("type")}
              selections={testTypeLabel ? [testTypeLabel] : []}
              action={<KnowledgeBaseLink />}
            />
            <StepMode onSelect={(m) => { setMode(m); go("concept"); }} />
          </div>
        );
      case "concept":
        if (!testType || !mode) return null;
        return (
          <div className="mx-auto w-full max-w-5xl">
            <StepHeader
              title={mode === "multiple" ? "Add the concepts to compare" : "Add your concept"}
              description="Paste the concept text, or attach an image or PDF of the concept card. Every score cites the real posts and trends behind it."
              onBack={() => go("mode")}
              selections={[testTypeLabel, modeLabel].filter((s): s is string => Boolean(s))}
              action={<KnowledgeBaseLink />}
            />
            <StepConcept testType={testType} mode={mode} onSubmit={handleConceptsReady} />
          </div>
        );
      case "assessing":
      case "loading":
        return (
          <div className="flex min-h-[calc(100vh-7rem)] items-center justify-center sm:min-h-[calc(100vh-8rem)]">
            <div className="chart-card flex w-full max-w-md flex-col items-center gap-4 rounded-2xl px-6 py-16 text-center">
              <span
                className="size-10 animate-spin rounded-full border-2 border-transparent"
                style={{ borderTopColor: "var(--fi-solid)", borderRightColor: "var(--fi-solid)" }}
                aria-hidden="true"
              />
              <p style={{ color: "var(--title-tx)" }} className="text-sm font-medium" role="status">
                {phase === "loading"
                  ? "Loading your results…"
                  : "Scoring your concept against the Trends Real Estate corpus…"}
              </p>
              {phase === "assessing" && (
                <p style={{ color: "var(--muted-tx)" }} className="max-w-xs text-xs">
                  This retrieves real posts and trends, then applies the 6C framework. Roughly a
                  minute per concept, longer when comparing more than one.
                </p>
              )}
            </div>
          </div>
        );
      case "error":
        return <InlineError message={error ?? "Something went wrong."} onRetry={handleErrorRetry} />;
      case "results":
        if (!result) return null;
        return result.comparison
          ? <ComparisonView assessments={result.assessments} comparison={result.comparison} onRestart={restart} />
          : <ResultsView assessment={result.assessments[0]} onRestart={restart} />;
    }
  }

  return (
    <MotionConfig reducedMotion="user">
      <div className="w-full">
        <DashboardTopbar
          title="Idea Testing"
          accessory={<MarketSelect market={market} onChange={setMarket} />}
        />
        <div className="mx-auto w-full max-w-[1500px] p-6 sm:p-8">
          <AnimatePresence initial={false}>
            {isWizardStep(phase) && (
              <motion.div
                key="stepper"
                initial={{ opacity: 0 }}
                animate={{ opacity: 1, transition: { duration: 0.3 } }}
                exit={{ opacity: 0, transition: { duration: 0.15 } }}
                className="mx-auto mb-10 w-full max-w-5xl"
              >
                <WizardStepper current={phase} />
              </motion.div>
            )}
          </AnimatePresence>

          <AnimatePresence mode="wait" custom={direction}>
            <motion.div
              key={phase}
              custom={direction}
              variants={stepVariants}
              initial="enter"
              animate="center"
              exit="exit"
            >
              {renderBody()}
            </motion.div>
          </AnimatePresence>
        </div>
      </div>
    </MotionConfig>
  );
}

export default function IdeaTestingPage() {
  return (
    <Suspense fallback={
      <div className="w-full">
        <DashboardTopbar title="Idea Testing" accessory={null} />
        <div className="mx-auto w-full max-w-5xl p-6 sm:p-8">
          <Skel className="mb-10 h-7 rounded-full" />
          <Skel className="mb-8 h-20 rounded-2xl" />
          <Skel className="h-60 rounded-2xl" />
        </div>
      </div>
    }>
      <IdeaTestingPageContent />
    </Suspense>
  );
}
