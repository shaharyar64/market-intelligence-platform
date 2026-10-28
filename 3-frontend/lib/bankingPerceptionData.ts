import perceptionsJson from "../public/data/banking/bank_perceptions_structured.json";

export type ScoredLabel = {
  score: number;
};

export type BankStrength = ScoredLabel & {
  strength: string;
};

export type BankWeakness = ScoredLabel & {
  weakness: string;
};

export type CustomerSegment = {
  segment: string;
  relevance_score: number;
};

export type BankPerception = {
  bank_name: string;
  summarised_perception: string;
  strengths: BankStrength[];
  weaknesses: BankWeakness[];
  customer_segments: CustomerSegment[];
  perceived_brand_role?: string;
  narrative_tone?: string[];
  perception_opportunity?: string;
  established_associations?: string[];
  less_established_associations?: string[];
};

export const bankPerceptions = perceptionsJson as BankPerception[];
