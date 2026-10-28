-- Per-country trend runs.
--
-- A run is now scoped to one market or to all of them. NULL keeps its old
-- meaning - every market in one run - so each existing row stays exactly what
-- it was, and every reader that asks for "the latest run" keeps getting an
-- all-markets run by filtering on country IS NULL.
--
-- The column is on the trend rather than only in the run id so the API can pick
-- the newest run for a market with an index lookup, and so a user-generated
-- trend inherits its run's market without parsing an id.
--
-- Values are ISO 3166-1 alpha-2, the codes brand_posts and influencer_posts
-- already emit: 'AE' or 'SA'.

ALTER TABLE realestate_intel.trends ADD COLUMN IF NOT EXISTS country text;

CREATE INDEX IF NOT EXISTS trends_by_country_created
    ON realestate_intel.trends (country, created_at DESC);
