CREATE TABLE IF NOT EXISTS realestate_intel.taxonomy (
  theme      text NOT NULL,
  sub_theme  text NOT NULL,
  source     text NOT NULL,
  aliases    text[] DEFAULT '{}',
  updated_at timestamptz DEFAULT now(),
  PRIMARY KEY (theme, sub_theme)
);

CREATE INDEX IF NOT EXISTS ix_re_taxonomy_theme ON realestate_intel.taxonomy (theme);
