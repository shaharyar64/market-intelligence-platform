-- Empty clones of the food_intel tables the copied service queries.
-- Created so every endpoint returns an empty result instead of erroring
-- while the enrichment and trend pipelines are still being planned.

CREATE TABLE IF NOT EXISTS realestate_intel.post_analysis (
  platform text NOT NULL,
  post_id text NOT NULL,
  brand_key text NOT NULL,
  brand_name text NOT NULL,
  account_type text NOT NULL,
  account_username text NOT NULL,
  caption text,
  language text,
  engagement_total integer DEFAULT 0,
  analysis jsonb NOT NULL,
  image_key text,
  posted_at timestamp with time zone,
  processed_at timestamp with time zone,
  post_url text,
  engagement jsonb DEFAULT '{}'::jsonb NOT NULL,
  PRIMARY KEY (platform, post_id)
);

CREATE TABLE IF NOT EXISTS realestate_intel.trends (
  trend_id text NOT NULL,
  run_id text NOT NULL,
  level text NOT NULL,
  parent_trend_id text,
  name text NOT NULL,
  quadrant text NOT NULL,
  volume_index real NOT NULL,
  growth_index real NOT NULL,
  post_count integer NOT NULL,
  unique_authors integer NOT NULL,
  narrative jsonb NOT NULL,
  metrics jsonb NOT NULL,
  timeline jsonb NOT NULL,
  example_posts jsonb NOT NULL,
  member_posts jsonb NOT NULL,
  created_at timestamp with time zone DEFAULT now() NOT NULL,
  origin text DEFAULT 'pipeline'::text NOT NULL,
  created_by text,
  source_query text,
  PRIMARY KEY (trend_id)
);

CREATE TABLE IF NOT EXISTS realestate_intel.assistant_conversations (
  conversation_id text NOT NULL,
  user_sub text NOT NULL,
  title text DEFAULT 'New chat'::text NOT NULL,
  transcript jsonb DEFAULT '[]'::jsonb NOT NULL,
  persona text,
  created_at timestamp with time zone DEFAULT now() NOT NULL,
  updated_at timestamp with time zone DEFAULT now() NOT NULL,
  PRIMARY KEY (conversation_id)
);

CREATE TABLE IF NOT EXISTS realestate_intel.personas (
  persona_id text NOT NULL,
  name text NOT NULL,
  tagline text,
  definition text NOT NULL,
  motivations text[] DEFAULT '{}'::text[] NOT NULL,
  priorities text[] DEFAULT '{}'::text[] NOT NULL,
  behaviors text[] DEFAULT '{}'::text[] NOT NULL,
  centroid vector(1024),
  model text,
  radius real,
  stats jsonb DEFAULT '{}'::jsonb NOT NULL,
  origin text DEFAULT 'seed'::text NOT NULL,
  created_by text,
  created_at timestamp with time zone DEFAULT now() NOT NULL,
  refreshed_at timestamp with time zone,
  PRIMARY KEY (persona_id)
);

CREATE TABLE IF NOT EXISTS realestate_intel.persona_post (
  persona_id text NOT NULL,
  platform text NOT NULL,
  post_id text NOT NULL,
  distance real NOT NULL,
  PRIMARY KEY (persona_id, platform, post_id)
);

CREATE TABLE IF NOT EXISTS realestate_intel.post_embedding (
  platform text NOT NULL,
  post_id text NOT NULL,
  model text NOT NULL,
  embedding vector(1024) NOT NULL,
  created_at timestamp with time zone DEFAULT now() NOT NULL,
  PRIMARY KEY (platform, post_id, model)
);

CREATE TABLE IF NOT EXISTS realestate_intel.product_alias (
  raw text NOT NULL,
  canonical text NOT NULL,
  kind text NOT NULL,
  scored_at timestamp with time zone DEFAULT now() NOT NULL,
  PRIMARY KEY (raw)
);

CREATE TABLE IF NOT EXISTS realestate_intel.trend_embedding (
  run_id text NOT NULL,
  trend_id text NOT NULL,
  model text NOT NULL,
  embedding vector NOT NULL,
  PRIMARY KEY (run_id, trend_id, model)
);

CREATE TABLE IF NOT EXISTS realestate_intel.post_language (
  platform text NOT NULL,
  post_id text NOT NULL,
  script text,
  language text,
  in_scope boolean,
  scored_at timestamp with time zone DEFAULT now() NOT NULL,
  reason text,
  PRIMARY KEY (platform, post_id)
);
