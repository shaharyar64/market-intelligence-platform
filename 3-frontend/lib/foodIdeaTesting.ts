import { apiFetch } from "@/lib/apiClient";

const BASE = "/api/v1/food-intelligence/idea-testing";

export type FactorId =
  | "clutter" | "connect" | "clarity" | "competitive" | "credibility" | "conversion";
export type TestType = "quick-idea" | "advertising" | "innovation";
export type ConceptMode = "single" | "multiple";
export type Market = "AE" | "SA";

export type ConceptExtraction = {
  need: string;
  proposition: string;
  claims: string[];
  category: string;
  audience: string;
  cues: string[];
};

export type Citation = {
  evidence_type: "post" | "trend" | "document";
  platform?: string | null;
  post_id?: string | null;
  trend_id?: string | null;
  document_id?: string | null;
  document_title?: string | null;
  document_deleted?: boolean;
  post_url?: string | null;
  quote: string;
};

export type CriterionScore = {
  criterion_id: string;
  label: string;
  rating: number;
};

export type FactorScore = {
  factor_id: FactorId;
  score: number;
  verdict: string;
  finding: string;
  citations: Citation[];
  criteria?: CriterionScore[];
};

export type FoodRelation = "food" | "food_adjacent" | "not_food";

export type ConfidenceBreakdown = {
  relevance: number;
  volume: number;
  spread: number;
  recency: number;
  quality: number;
};

export type Assessment = {
  assessment_id: string;
  concept_id: string;
  title: string;
  test_type: TestType;
  headline: string;
  summary: string;
  factor_scores: FactorScore[];
  overall_score: number;
  confidence_score: number;
  confidence_breakdown: ConfidenceBreakdown;
  confidence_label: string;
  confidence_explanation: string;
  recommendations: string[];
  trends_run_id: string | null;
  country: Market | null;
  cached: boolean;
  food_relation?: FoodRelation | null;
};

export type FactorLeader = { factor_id: FactorId; assessment_id: string };
export type Comparison = {
  comparison_id: string;
  winner_assessment_id: string;
  factor_leaders: FactorLeader[];
  verdict: string;
  narrative: string;
};

export type AssessResponse = { assessments: Assessment[]; comparison: Comparison | null };

export type HistoryAssessmentItem = {
  kind: "assessment";
  assessment_id: string;
  title: string;
  test_type: TestType;
  overall_score: number;
  created_at: string;
};
export type HistoryComparisonItem = {
  kind: "comparison";
  comparison_id: string;
  titles: string[];
  scores: number[];
  verdict: string;
  created_at: string;
};
export type HistoryItem = HistoryAssessmentItem | HistoryComparisonItem;

async function getJson<T>(endpoint: string, init: RequestInit = {}): Promise<T> {
  const res = await apiFetch(endpoint, init);
  if (!res.ok) {
    const detail = await res.text().catch(() => "");
    throw new Error(`${res.status} ${detail || res.statusText}`);
  }
  return res.json() as Promise<T>;
}

export function createConceptFromText(title: string, rawText: string) {
  const form = new FormData();
  form.set("title", title);
  form.set("raw_text", rawText);
  return getJson<{ concept_id: string; extracted: ConceptExtraction }>(
    `${BASE}/concepts`, { method: "POST", body: form },
  );
}

export function createConceptFromFile(title: string, file: File, notes?: string) {
  const form = new FormData();
  form.set("title", title);
  form.set("file", file);
  if (notes?.trim()) form.set("raw_text", notes.trim());
  return getJson<{ concept_id: string; extracted: ConceptExtraction }>(
    `${BASE}/concepts`, { method: "POST", body: form },
  );
}

export function assessConcepts(
  conceptIds: string[],
  mode: ConceptMode,
  testType: TestType,
  country?: Market | null,
) {
  return getJson<AssessResponse>(`${BASE}/assess`, {
    method: "POST",
    body: JSON.stringify({
      concept_ids: conceptIds, mode, test_type: testType, country: country ?? null,
    }),
  });
}

export function getAssessment(assessmentId: string) {
  return getJson<Assessment>(`${BASE}/assessments/${encodeURIComponent(assessmentId)}`);
}

export function getComparison(comparisonId: string) {
  return getJson<AssessResponse>(`${BASE}/comparisons/${encodeURIComponent(comparisonId)}`);
}

export function getHistory() {
  return getJson<{ items: HistoryItem[] }>(`${BASE}/history`);
}
