CREATE SCHEMA IF NOT EXISTS food_intel;

CREATE TABLE IF NOT EXISTS food_intel.idea_concepts (
  concept_id   text PRIMARY KEY,
  created_by   text NOT NULL,
  title        text NOT NULL,
  input_format text NOT NULL CHECK (input_format IN ('text', 'image', 'pdf')),
  raw_text     text,
  file_s3_key  text,
  extracted    jsonb NOT NULL,
  created_at   timestamptz NOT NULL DEFAULT now()
);

CREATE INDEX IF NOT EXISTS idea_concepts_created_by_idx
  ON food_intel.idea_concepts (created_by, created_at DESC);

CREATE TABLE IF NOT EXISTS food_intel.idea_assessments (
  assessment_id        text PRIMARY KEY,
  concept_id           text NOT NULL REFERENCES food_intel.idea_concepts (concept_id),
  test_type            text NOT NULL CHECK (test_type IN ('quick-idea', 'advertising', 'innovation')),
  headline             text NOT NULL,
  summary              text NOT NULL,
  factor_scores        jsonb NOT NULL,
  overall_score        integer NOT NULL CHECK (overall_score BETWEEN 0 AND 100),
  confidence_score     integer NOT NULL CHECK (confidence_score BETWEEN 0 AND 100),
  confidence_breakdown jsonb NOT NULL,
  recommendations      jsonb NOT NULL,
  trends_run_id        text,
  country              text,
  model                text NOT NULL,
  framework_version    text NOT NULL,
  cache_key            text NOT NULL UNIQUE,
  created_at           timestamptz NOT NULL DEFAULT now()
);

CREATE INDEX IF NOT EXISTS idea_assessments_concept_idx
  ON food_intel.idea_assessments (concept_id);

CREATE TABLE IF NOT EXISTS food_intel.idea_comparisons (
  comparison_id        text PRIMARY KEY,
  assessment_ids       text[] NOT NULL,
  winner_assessment_id text NOT NULL,
  factor_leaders       jsonb NOT NULL,
  verdict              text NOT NULL,
  narrative            text NOT NULL,
  created_at           timestamptz NOT NULL DEFAULT now()
);
