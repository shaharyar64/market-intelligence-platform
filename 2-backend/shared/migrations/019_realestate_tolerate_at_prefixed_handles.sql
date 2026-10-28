-- Make the account joins tolerant of an @-prefixed handle.
--
-- The influencer scrape landed 1,481 posts across 16 accounts, but wrote the
-- handle as '@alessia_sheglova' while public.instagram_profile stores
-- 'alessia_sheglova'. The join never matched, so every one of those posts was
-- invisible and realestate_intel.influencer_posts read as empty - which looked
-- exactly like "the scrape has not run yet".
--
-- Measured before changing anything: the @ prefix is on exactly those 1,481
-- rows and nothing else, all 56,395 other instagram_posts rows are clean, no
-- profile table stores an @, and no @-prefixed account appears on a developer
-- list. Stripping it therefore recovers the influencer pool and moves the brand
-- pool by zero - 6,694 Instagram brand posts either way.
--
-- Applied to every platform rather than just Instagram, so the next scrape that
-- formats a handle this way fails loudly on a count rather than silently on a
-- join. The emitted author_username is normalised too, so it matches
-- realestate_intel.brand.username and the registry lookup keeps working.
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
       lower(ltrim(p.username, '@')) AS author_username,
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
  JOIN ig ON ig.username = lower(ltrim(p.username, '@'))
UNION ALL
SELECT 'tiktok'::text,
       p.id,
       'brand'::text,
       p.post_url,
       lower(ltrim(p.username, '@')),
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
  JOIN tt ON tt.username = lower(ltrim(p.username, '@'))
UNION ALL
SELECT 'twitter'::text,
       p.id,
       'brand'::text,
       'https://twitter.com/' || ltrim(p.username, '@') || '/status/' || p.id,
       lower(ltrim(p.username, '@')),
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
  FROM (SELECT DISTINCT ON (id) * FROM public.twitter_posts
         ORDER BY id, last_updated DESC NULLS LAST, username) p
  JOIN tw ON tw.username = lower(ltrim(p.username, '@'))
UNION ALL
SELECT 'linkedin'::text,
       p.id::text,
       'brand'::text,
       p.post_url,
       ltrim(p.universal_name, '@'),
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
  JOIN li ON li.universal_name = ltrim(p.universal_name, '@');

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
       lower(ltrim(p.username, '@')) AS author_username,
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
  JOIN ig ON ig.username = lower(ltrim(p.username, '@'));
