-- Brings food_intel.trends in line with production, where these changes were
-- applied by hand. A no-op on production; on a fresh database it makes the
-- table one the trend pipeline and the assistant's create_trend can write to.

ALTER TABLE food_intel.trends ADD COLUMN IF NOT EXISTS origin text NOT NULL DEFAULT 'pipeline';

ALTER TABLE food_intel.trends ADD COLUMN IF NOT EXISTS created_by text;

ALTER TABLE food_intel.trends ADD COLUMN IF NOT EXISTS source_query text;

ALTER TABLE food_intel.trends DROP COLUMN IF EXISTS sentiment;

CREATE INDEX IF NOT EXISTS trends_origin_idx ON food_intel.trends USING btree (origin);
