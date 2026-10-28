CREATE TABLE IF NOT EXISTS realestate_intel.brand (
  brand_key      text NOT NULL,
  brand_name     text NOT NULL,
  platform       text NOT NULL,
  username       text NOT NULL,
  followers      bigint DEFAULT 0,
  source_project text,
  resolution     text NOT NULL,
  updated_at     timestamptz DEFAULT now(),
  PRIMARY KEY (platform, username)
);

CREATE INDEX IF NOT EXISTS ix_re_brand_key ON realestate_intel.brand (brand_key);
