CREATE OR REPLACE VIEW realestate_intel.trend_posts AS
WITH all_sources AS (
  SELECT *, 1 AS precedence FROM realestate_intel.brand_posts
  UNION ALL
  SELECT *, 2 AS precedence FROM realestate_intel.influencer_posts
  UNION ALL
  SELECT *, 3 AS precedence FROM realestate_intel.community_posts
)
SELECT DISTINCT ON (platform, post_id)
       platform, post_id, source, post_url, author_username, caption,
       hashtags, likes, comments, views, engagement_total, media_keys,
       country, posted_at
  FROM all_sources
 ORDER BY platform, post_id, precedence;
