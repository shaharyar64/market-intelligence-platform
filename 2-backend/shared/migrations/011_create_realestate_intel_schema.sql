CREATE SCHEMA IF NOT EXISTS realestate_intel;

CREATE TABLE IF NOT EXISTS realestate_intel.post_geo (
  platform   text NOT NULL,
  post_id    text NOT NULL,
  country    text,
  method     text NOT NULL,
  updated_at timestamptz DEFAULT now(),
  PRIMARY KEY (platform, post_id)
);

CREATE OR REPLACE VIEW realestate_intel.brand_posts AS
WITH ig AS (
  SELECT DISTINCT ON (lower(username)) lower(username) AS username, country
    FROM public.instagram_profile
   WHERE project IN ('realestate_dbh', 'realestate_trends')
   ORDER BY lower(username), project
), tt AS (
  SELECT DISTINCT ON (lower(username)) lower(username) AS username, country
    FROM public.tiktok_profiles
   WHERE project IN ('realestate_dbh', 'realestate_trends')
   ORDER BY lower(username), project
), tw AS (
  SELECT DISTINCT ON (lower(username)) lower(username) AS username, country
    FROM public.twitter_profiles
   WHERE project IN ('realestate_dbh', 'realestate_trends')
   ORDER BY lower(username), project
), li AS (
  SELECT DISTINCT ON (universal_name) universal_name, country
    FROM public.linkedin_profiles
   WHERE project IN ('realestate_dbh', 'realestate_trends')
   ORDER BY universal_name, project
)
SELECT 'instagram'::text AS platform,
       p.id AS post_id,
       'brand'::text AS source,
       'https://www.instagram.com/p/' || p.id AS post_url,
       lower(p.username) AS author_username,
       btrim(p.caption) AS caption,
       ARRAY(SELECT DISTINCT lower(m.m[1])
               FROM regexp_matches(COALESCE(p.caption, ''), '#([A-Za-z0-9_]+)', 'g') m(m)) AS hashtags,
       COALESCE(p.likes, 0)::bigint AS likes,
       COALESCE(p.comments, 0)::bigint AS comments,
       COALESCE(p.views, 0)::bigint AS views,
       (COALESCE(p.likes, 0) + COALESCE(p.comments, 0))::bigint AS engagement_total,
       ARRAY['media/instagram/' || p.id || '.jpg']::text[] AS media_keys,
       CASE upper(btrim(ig.country)) WHEN 'KSA' THEN 'SA' WHEN 'UAE' THEN 'AE' ELSE NULL END AS country,
       p.uploaded_at AS posted_at
  FROM public.instagram_posts p
  JOIN ig ON ig.username = lower(p.username)
UNION ALL
SELECT 'tiktok'::text,
       p.id,
       'brand'::text,
       p.post_url,
       lower(p.username),
       btrim(p.title),
       ARRAY(SELECT DISTINCT lower(m.m[1])
               FROM regexp_matches(COALESCE(p.title, ''), '#([A-Za-z0-9_]+)', 'g') m(m)),
       COALESCE(p.likes, 0)::bigint,
       COALESCE(p.comments, 0)::bigint,
       COALESCE(p.views, 0)::bigint,
       (COALESCE(p.likes, 0) + COALESCE(p.comments, 0) + COALESCE(p.shares, 0))::bigint,
       NULL::text[],
       CASE upper(btrim(tt.country)) WHEN 'KSA' THEN 'SA' WHEN 'UAE' THEN 'AE' ELSE NULL END,
       p.uploaded_at_formatted
  FROM public.tiktok_posts p
  JOIN tt ON tt.username = lower(p.username)
UNION ALL
SELECT 'twitter'::text,
       p.id,
       'brand'::text,
       'https://twitter.com/' || p.username || '/status/' || p.id,
       lower(p.username),
       btrim(p.text),
       ARRAY(SELECT DISTINCT lower(m.m[1])
               FROM regexp_matches(COALESCE(p.text, ''), '#([A-Za-z0-9_]+)', 'g') m(m)),
       COALESCE(p.likes, 0)::bigint,
       COALESCE(p.replies, 0)::bigint,
       COALESCE(p.views, 0)::bigint,
       (COALESCE(p.likes, 0) + COALESCE(p.replies, 0) + COALESCE(p.retweet, 0))::bigint,
       NULL::text[],
       CASE upper(btrim(tw.country)) WHEN 'KSA' THEN 'SA' WHEN 'UAE' THEN 'AE' ELSE NULL END,
       p.uploaded_at::timestamptz
  FROM (SELECT DISTINCT ON (id) * FROM public.twitter_posts ORDER BY id, last_updated DESC NULLS LAST, username) p
  JOIN tw ON tw.username = lower(p.username)
UNION ALL
SELECT 'linkedin'::text,
       p.id::text,
       'brand'::text,
       p.post_url,
       p.universal_name,
       btrim(p.post_text),
       ARRAY(SELECT DISTINCT lower(m.m[1])
               FROM regexp_matches(COALESCE(p.post_text, ''), '#([A-Za-z0-9_]+)', 'g') m(m)),
       COALESCE(p.likes, 0)::bigint,
       COALESCE(p.comments, 0)::bigint,
       0::bigint,
       (COALESCE(p.likes, 0) + COALESCE(p.comments, 0) + COALESCE(p.shares, 0))::bigint,
       NULL::text[],
       CASE upper(btrim(li.country)) WHEN 'KSA' THEN 'SA' WHEN 'UAE' THEN 'AE' ELSE NULL END,
       p.uploaded_at::timestamptz
  FROM public.linkedin_posts p
  JOIN li ON li.universal_name = p.universal_name;

CREATE OR REPLACE VIEW realestate_intel.influencer_posts AS
WITH ig AS (
  SELECT DISTINCT ON (lower(username)) lower(username) AS username, country
    FROM public.instagram_profile
   WHERE project = 'realestate_trends_influencers'
   ORDER BY lower(username), project
)
SELECT 'instagram'::text AS platform,
       p.id AS post_id,
       'influencer'::text AS source,
       'https://www.instagram.com/p/' || p.id AS post_url,
       lower(p.username) AS author_username,
       btrim(p.caption) AS caption,
       ARRAY(SELECT DISTINCT lower(m.m[1])
               FROM regexp_matches(COALESCE(p.caption, ''), '#([A-Za-z0-9_]+)', 'g') m(m)) AS hashtags,
       COALESCE(p.likes, 0)::bigint AS likes,
       COALESCE(p.comments, 0)::bigint AS comments,
       COALESCE(p.views, 0)::bigint AS views,
       (COALESCE(p.likes, 0) + COALESCE(p.comments, 0))::bigint AS engagement_total,
       ARRAY['media/instagram/' || p.id || '.jpg']::text[] AS media_keys,
       CASE upper(btrim(ig.country)) WHEN 'KSA' THEN 'SA' WHEN 'UAE' THEN 'AE' ELSE NULL END AS country,
       p.uploaded_at AS posted_at
  FROM public.instagram_posts p
  JOIN ig ON ig.username = lower(p.username);

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
       g.country,
       cp.posted_at
  FROM public.community_posts cp
  LEFT JOIN realestate_intel.post_geo g
         ON g.platform = cp.platform AND g.post_id = cp.post_id
 WHERE 'real_estate' = ANY (cp.search_keywords);
