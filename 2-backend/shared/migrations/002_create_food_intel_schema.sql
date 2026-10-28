CREATE SCHEMA IF NOT EXISTS food_intel;

CREATE TABLE IF NOT EXISTS food_intel.post_analysis (
  platform          text        NOT NULL,
  post_id           text        NOT NULL,
  brand_key         text        NOT NULL,
  brand_name        text        NOT NULL,
  account_type      text        NOT NULL,
  account_username  text        NOT NULL,

  caption           text,
  language          text,

  likes             int DEFAULT 0,
  comments          int DEFAULT 0,
  views             int DEFAULT 0,
  shares            int DEFAULT 0,
  bookmarks         int DEFAULT 0,
  engagement_total  int DEFAULT 0,

  analysis          jsonb       NOT NULL,
  image_ref         text,

  posted_at         timestamptz,
  fetched_at        timestamptz,
  post_url          text,

  provenance        jsonb,
  prompt_version    text,
  schema_version    int DEFAULT 2,

  PRIMARY KEY (platform, post_id)
);

CREATE INDEX IF NOT EXISTS ix_post_analysis_brand_posted
  ON food_intel.post_analysis (brand_key, posted_at DESC);
CREATE INDEX IF NOT EXISTS ix_post_analysis_brand_engagement
  ON food_intel.post_analysis (brand_key, engagement_total DESC);
CREATE INDEX IF NOT EXISTS ix_post_analysis_gin
  ON food_intel.post_analysis USING gin (analysis jsonb_path_ops);

CREATE TABLE IF NOT EXISTS food_intel.post_theme (
  platform    text NOT NULL,
  post_id     text NOT NULL,
  label       text NOT NULL,
  confidence  real,
  evidence    text[] DEFAULT '{}',
  FOREIGN KEY (platform, post_id) REFERENCES food_intel.post_analysis(platform, post_id) ON DELETE CASCADE
);
CREATE INDEX IF NOT EXISTS ix_post_theme_post ON food_intel.post_theme (platform, post_id);
CREATE INDEX IF NOT EXISTS ix_post_theme_label ON food_intel.post_theme (label);

CREATE TABLE IF NOT EXISTS food_intel.post_product (
  platform    text NOT NULL,
  post_id     text NOT NULL,
  product     text NOT NULL,
  confidence  real,
  evidence    text[] DEFAULT '{}',
  FOREIGN KEY (platform, post_id) REFERENCES food_intel.post_analysis(platform, post_id) ON DELETE CASCADE
);
CREATE INDEX IF NOT EXISTS ix_post_product_post ON food_intel.post_product (platform, post_id);
CREATE INDEX IF NOT EXISTS ix_post_product_product ON food_intel.post_product (product);

CREATE TABLE IF NOT EXISTS food_intel.brand_profile (
  brand_key         text NOT NULL,
  brand_name        text NOT NULL,
  platform          text NOT NULL,
  account_username  text NOT NULL,
  followers         int DEFAULT 0,
  country           text,
  industry          text,
  is_verified       boolean DEFAULT false,
  updated_at        timestamptz DEFAULT now(),
  PRIMARY KEY (brand_key, platform)
);
