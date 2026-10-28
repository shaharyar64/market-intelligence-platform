-- Restore post_source.
--
-- Migration 020 dropped it as "read by nothing". That was true, but only
-- because the persona-removal edit had already deleted the branch that read
-- it - the assistant's vector search restricts its nearest-neighbour pool by
-- source through this view, and losing it silently downgraded that to a
-- post-ANN filter.
--
-- Why it has to be inside the pool: influencer posts are 1,481 of 59,596 rows
-- and brand posts 16,852. An unrestricted ANN returns its k nearest overall,
-- and a WHERE applied afterwards then finds few or none of the requested
-- source - so "what are influencers saying about waterfront" answers "no data"
-- against a corpus that has it.
CREATE OR REPLACE VIEW realestate_intel.post_source AS
SELECT platform, post_id, source FROM realestate_intel.brand_posts
UNION ALL
SELECT platform, post_id, source FROM realestate_intel.influencer_posts;
