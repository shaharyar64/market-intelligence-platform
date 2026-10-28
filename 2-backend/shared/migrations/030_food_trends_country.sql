-- Per-country trend runs for food.
--
-- A run is scoped to one market or to all of them. NULL keeps its old meaning,
-- every market in one run, so each existing row stays exactly what it was and
-- every reader that asks for "the latest run" keeps getting an all-markets run
-- by filtering on country IS NULL.
--
-- The column is on the trend rather than only in the run id so the API can pick
-- the newest run for a market with an index lookup.
--
-- Values are ISO 3166-1 alpha-2: 'SA' or 'AE'.

ALTER TABLE food_intel.trends ADD COLUMN IF NOT EXISTS country text;

CREATE INDEX IF NOT EXISTS food_trends_by_country_created
    ON food_intel.trends (country, created_at DESC);
