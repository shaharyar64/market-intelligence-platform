ALTER TABLE food_intel.post_analysis
  RENAME COLUMN fetched_at TO processed_at;

UPDATE food_intel.post_analysis
SET processed_at = COALESCE(
    (provenance->>'processed_at')::timestamptz,
    processed_at
)
WHERE provenance ? 'processed_at';

ALTER TABLE food_intel.post_analysis
  DROP COLUMN IF EXISTS provenance,
  DROP COLUMN IF EXISTS prompt_version,
  DROP COLUMN IF EXISTS schema_version;
