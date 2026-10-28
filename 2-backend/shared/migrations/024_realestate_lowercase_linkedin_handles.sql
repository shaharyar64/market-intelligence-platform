-- Lowercase LinkedIn handles in brand_posts, matching the other three platforms.
--
-- The Instagram, TikTok and Twitter arms all emit lower(ltrim(username, '@')) as
-- author_username. The LinkedIn arm emitted universal_name raw and joined its
-- profile CTE case-sensitively. Two consequences, both silent rather than loud:
--
--   * brand_service joins post_analysis.account_username to author_username by
--     string equality, and the enrichment path already lowercases. An uppercase
--     handle would drop that developer's LinkedIn posts out of trend
--     participation, returning a smaller plausible number instead of an error.
--   * fetch_posts matches profiles case-insensitively while this view did not, so
--     enrichment could write a row for a post the view excludes.
--
-- No handle in the corpus has uppercase today, so this rewrites no current row.
-- It closes the asymmetry before one arrives.

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
  SELECT DISTINCT ON (lower(universal_name)) lower(universal_name) AS universal_name, country
    FROM public.linkedin_profiles
   WHERE project IN ('realestate_dbh', 'realestate_trends')
   ORDER BY lower(universal_name), project
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
       lower(ltrim(p.universal_name, '@')),
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
  JOIN li ON li.universal_name = lower(ltrim(p.universal_name, '@'));

