-- Drop the relevance gate.
--
-- Every one of its 59,020 rows was TRUE, set by provenance in migration 018
-- rather than measured by a classifier, so the gate admitted everything it was
-- asked about. What it actually did was withhold any post it had not seen,
-- which made it a hidden dependency on a loader nobody runs - a post arriving
-- tomorrow would be invisible to trends and to the assistant until something
-- remembered to score it.
--
-- The corpus is already bounded at collection. Community rows reach us only
-- through 'real_estate' = ANY(search_keywords), applied at scrape time, and
-- brand and influencer rows come from account lists we curate. Off-topic posts
-- are caught downstream by the naming prompt's domain gate, which refuses to
-- name a cluster that does not share a property theme.
--
-- The view is dropped and recreated rather than replaced. CREATE OR REPLACE
-- VIEW cannot remove a column, and is_relevant is going away, so the view has
-- to go first anyway - it depends on the table being dropped.
DROP VIEW IF EXISTS realestate_intel.trend_posts;

CREATE VIEW realestate_intel.trend_posts AS
WITH all_sources AS (
    SELECT b.*, 'brand'::text AS cohort, 1 AS precedence
      FROM realestate_intel.brand_posts b
    UNION ALL
    SELECT i.*, 'influencer'::text, 2
      FROM realestate_intel.influencer_posts i
    UNION ALL
    SELECT c.*, 'community'::text, 3
      FROM realestate_intel.community_posts c
)
SELECT DISTINCT ON (platform, post_id)
       platform, post_id, source, post_url, author_username, caption,
       hashtags, likes, comments, views, engagement_total, media_keys,
       country, posted_at, cohort
  FROM all_sources
 ORDER BY platform, post_id, precedence;

DROP TABLE IF EXISTS realestate_intel.post_relevance;
