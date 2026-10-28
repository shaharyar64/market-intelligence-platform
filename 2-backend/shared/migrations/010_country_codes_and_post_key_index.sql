UPDATE public.community_posts
   SET country = CASE lower(btrim(country))
       WHEN 'saudi arabia'         THEN 'SA'
       WHEN 'ksa'                  THEN 'SA'
       WHEN 'united arab emirates' THEN 'AE'
       WHEN 'uae'                  THEN 'AE'
       WHEN 'kuwait'               THEN 'KW'
       WHEN 'qatar'                THEN 'QA'
       WHEN 'oman'                 THEN 'OM'
       WHEN 'bahrain'              THEN 'BH'
       WHEN 'india'                THEN 'IN'
       WHEN 'ind'                  THEN 'IN'
       WHEN 'malaysia'             THEN 'MY'
       WHEN 'mys'                  THEN 'MY'
       ELSE country
   END
 WHERE country IS NOT NULL
   AND length(country) > 2;

DROP INDEX IF EXISTS public.community_posts_country_code_idx;

ALTER TABLE public.community_posts
  DROP COLUMN IF EXISTS country_code;

CREATE INDEX IF NOT EXISTS community_posts_country_idx
  ON public.community_posts (country)
  WHERE country IS NOT NULL;

CREATE INDEX IF NOT EXISTS community_posts_platform_post_idx
  ON public.community_posts (platform, post_id);

ANALYZE public.community_posts;
