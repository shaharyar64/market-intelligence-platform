-- Drop two more tables that were built before anything needed them.
--
-- offering_alias  0 rows. It canonicalised offering names through a hand-built
--                 alias map - food had 8,368 such rows. Ours was never
--                 populated, so the LEFT JOIN always missed and every caller
--                 already fell back to the raw normalised string. Removing it
--                 changes no result today.
--
-- post_geo        0 rows. It held a derived country for community posts,
--                 because public.community_posts.country is NULL on all of
--                 them and that table is shared and read-only to us. The
--                 backfill that would have filled it never completed, so the
--                 community_posts view has been reading NULL through a join
--                 that could never match.
--
-- community_posts now reads cp.country directly. That is still NULL for every
-- real-estate row, but it is honestly NULL rather than NULL arriving through
-- machinery that implies someone derived it. When country is worth having, it
-- gets built once, with a loader that runs.
CREATE OR REPLACE VIEW realestate_intel.community_posts AS
SELECT cp.platform,
       cp.post_id,
       'community'::text AS source,
       cp.post_url,
       lower(cp.author_username) AS author_username,
       btrim(cp.caption) AS caption,
       COALESCE(cp.hashtags, ARRAY[]::text[]) AS hashtags,
       COALESCE(cp.likes, 0)::bigint AS likes,
       COALESCE(cp.comments, 0)::bigint AS comments,
       COALESCE(cp.views, 0)::bigint AS views,
       COALESCE(cp.engagement_total, 0)::bigint AS engagement_total,
       cp.media_keys,
       cp.country,
       cp.posted_at
  FROM public.community_posts cp
 WHERE 'real_estate' = ANY (cp.search_keywords);

DROP TABLE IF EXISTS realestate_intel.offering_alias;

DROP TABLE IF EXISTS realestate_intel.post_geo;
