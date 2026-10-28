ALTER TABLE food_intel.post_analysis
  ADD COLUMN IF NOT EXISTS node_status jsonb NOT NULL DEFAULT '{}'::jsonb;

UPDATE food_intel.post_analysis
SET node_status = COALESCE(analysis->'node_status', '{}'::jsonb)
WHERE analysis ? 'node_status';

UPDATE food_intel.post_analysis
SET analysis = analysis - 'node_status'
WHERE analysis ? 'node_status';
