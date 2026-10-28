import type { FactorId, TestType } from "@/lib/ideaTesting";

export type FactorMeta = {
  id: FactorId; label: string; short: string; question: string; color: string;
};

export const FACTORS: FactorMeta[] = [
  { id: "clutter", label: "Clutter Break", short: "Uniqueness", color: "var(--fi-growth)",
    question: "How unique does the consumer find the messages being communicated?" },
  { id: "connect", label: "Connect", short: "Emotion & Relevance", color: "var(--chart-1)",
    question: "What feelings does it generate? How attractive and relevant is it?" },
  { id: "clarity", label: "Clarity", short: "Comprehension", color: "var(--chart-5)",
    question: "How clearly is the idea being communicated?" },
  { id: "competitive", label: "Competitive Edge", short: "Differentiation", color: "var(--chart-3)",
    question: "What advantage does this create versus existing alternatives?" },
  { id: "credibility", label: "Credibility", short: "Believability", color: "var(--chart-2)",
    question: "How convincing and believable are the claims?" },
  { id: "conversion", label: "Conversion", short: "Behaviour Change", color: "var(--chart-4)",
    question: "How likely is this to influence behaviour, preference or trial?" },
];

export function scoreTone(score: number): string {
  if (score <= 40) return "var(--fi-danger-tx)";
  if (score <= 60) return "var(--fi-mainstream-tx)";
  return "var(--fi-growth-tx)";
}

export const FACTOR_MAP: Record<FactorId, FactorMeta> = Object.fromEntries(
  FACTORS.map((f) => [f.id, f]),
) as Record<FactorId, FactorMeta>;

export type TestTypeMeta = { id: TestType; label: string; tagline: string; description: string };

export const TEST_TYPES: TestTypeMeta[] = [
  { id: "quick-idea", label: "Quick Ideas", tagline: "Early-stage thought starters",
    description: "Pressure-test raw ideas and thought starters before you invest." },
  { id: "advertising", label: "Advertising Concept", tagline: "Campaign & communication routes",
    description: "Evaluate campaign routes and messaging against the real-estate market." },
  { id: "innovation", label: "Innovation Concept", tagline: "New products & propositions",
    description: "Validate product, project or proposition innovation." },
];
