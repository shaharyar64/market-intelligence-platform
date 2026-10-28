CREATE TABLE IF NOT EXISTS realestate_intel.theme_demand (
  theme        text NOT NULL,
  sub_theme    text NOT NULL,
  country      text,
  avg_volume   double precision,
  avg_growth   double precision,
  quadrant     text,
  period_start date,
  period_end   date,
  updated_at   timestamptz DEFAULT now()
);

CREATE INDEX IF NOT EXISTS ix_re_theme_demand_theme ON realestate_intel.theme_demand (theme, country);
