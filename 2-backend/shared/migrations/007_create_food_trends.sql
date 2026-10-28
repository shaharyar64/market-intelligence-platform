-- Trend pipeline storage: pgvector embeddings + a single jsonb-heavy trends table.
-- Lives in food_intel alongside post_analysis (same jsonb-payload house style).

CREATE EXTENSION IF NOT EXISTS vector;

CREATE TABLE IF NOT EXISTS food_intel.post_embedding (
  platform    text NOT NULL,
  post_id     text NOT NULL,
  model       text NOT NULL,               -- e.g. 'text-embedding-3-large@1024'
  embedding   vector(1024) NOT NULL,
  created_at  timestamptz NOT NULL DEFAULT now(),
  PRIMARY KEY (platform, post_id, model)
);

-- Semantic search for the AI assistant (and future cross-run trend stitching).
CREATE INDEX IF NOT EXISTS ix_post_embedding_hnsw
  ON food_intel.post_embedding USING hnsw (embedding vector_cosine_ops);

CREATE TABLE IF NOT EXISTS food_intel.trends (
  trend_id         text PRIMARY KEY,
  run_id           text NOT NULL,
  level            text NOT NULL CHECK (level IN ('micro','umbrella')),
  parent_trend_id  text,

  -- scalars: what gets filtered / sorted in SQL
  name             text NOT NULL,
  quadrant         text NOT NULL CHECK (quadrant IN ('breakthrough','slow-burner','mainstream','watchlist')),
  volume_index     real NOT NULL,
  growth_index     real NOT NULL,
  sentiment        real NOT NULL,          -- share of positive posts, 0..1
  post_count       int  NOT NULL,
  unique_authors   int  NOT NULL,

  -- detail rides in jsonb (see spec 2026-08-07-trend-generation-pilot-design.md)
  narrative        jsonb NOT NULL,
  metrics          jsonb NOT NULL,
  timeline         jsonb NOT NULL,
  example_posts    jsonb NOT NULL,
  member_posts     jsonb NOT NULL,

  created_at       timestamptz NOT NULL DEFAULT now()
);

-- Run-level provenance lives in the pipeline run cache, not on every trend row.
ALTER TABLE food_intel.trends DROP COLUMN IF EXISTS run_info;

CREATE INDEX IF NOT EXISTS ix_trends_run ON food_intel.trends (run_id, level, quadrant);
