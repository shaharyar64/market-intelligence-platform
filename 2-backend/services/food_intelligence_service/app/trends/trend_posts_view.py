"""Give the pipeline one read surface without moving anyone's data.

Each corpus stays in the table that owns it. `public.community_posts` holds the
community scrape, dumped once from the other database so it never has to be
re-scraped; the tracked brand and influencer accounts live in
`public.instagram_posts`, keyed to their lists by `public.instagram_profile`.
Loading the tracked accounts into community_posts is what the old
`--source Brand` migration did, and it is what put 16,887 keyword hits into the
brand column in the first place: once a post is in the community table, the only
thing saying it is a brand post is a text field nobody can verify.

So the pipeline reads `food_intel.trend_posts`, a view that unions the sources
and derives `source` from the tracked lists — a fact, checkable at query time,
rather than a label copied in at load time.

Two pieces of state cannot live in either source table:

  food_intel.post_food   the food classifier's verdict. It is computed by this
                         pipeline, so it does not belong in the community dump
                         or in the brand crawl's table. Keyed like
                         food_intel.post_embedding, which already works this way.
  media                  the tracked accounts' images were never migrated to
                         the trends bucket, but the crawl that fetched them left
                         them in the raw bucket, where 99.6% of their food posts
                         still have one. The view emits a bucket-qualified key
                         pointing there, so the cards render without copying a
                         single object.

Deduplication is by author, not by id: a post written by a tracked account is a
brand or influencer post however we happened to find it, so the community branch
excludes tracked authors and the tracked branch is the sole source for them.
"""
import argparse
import logging

from services.food_intelligence_service.app.trends import store

logger = logging.getLogger("etl.trend_posts_view")

FOOD_PROJECTS = ("food_trends_brands", "food_trends_influencers")
JUNK_CAPTIONS = ("nan", "none", "null", "undefined")

POST_FOOD = """
CREATE TABLE IF NOT EXISTS food_intel.post_food (
    platform  text NOT NULL,
    post_id   text NOT NULL,
    is_food   boolean,
    scored_at timestamptz NOT NULL DEFAULT now(),
    PRIMARY KEY (platform, post_id)
)
"""

SEED_POST_FOOD = """
INSERT INTO food_intel.post_food (platform, post_id, is_food)
SELECT platform, post_id, is_food
  FROM public.community_posts
 WHERE is_food IS NOT NULL
ON CONFLICT (platform, post_id) DO NOTHING
"""

# One place derives "who wrote this": the view below, and any query that needs
# to filter by source without paying for the full union — notably the
# assistant's vector search, where a source filter over 0.3% of the corpus
# cannot be satisfied by an approximate-nearest-neighbour pool.
# Needs `mp`, one element of trends.member_posts; yields mcc.member_country.
MEMBER_COUNTRY_JOIN = """
    LEFT JOIN public.community_posts mc
      ON mc.platform = mp->>'platform' AND mc.post_id = mp->>'post_id'
    LEFT JOIN public.instagram_posts mi
      ON mp->>'platform' = 'instagram' AND mi.id = mp->>'post_id'
    LEFT JOIN public.instagram_profile mpr
      ON mpr.username = mi.username
     AND mpr.project IN ('food_trends_brands', 'food_trends_influencers')
    CROSS JOIN LATERAL (SELECT COALESCE(mc.country, CASE upper(btrim(mpr.country))
            WHEN 'KSA' THEN 'SA' WHEN 'UAE' THEN 'AE'
            WHEN 'IND' THEN 'IN' WHEN 'MYS' THEN 'MY' END) AS member_country) mcc"""

POST_SOURCE = f"""
CREATE OR REPLACE VIEW food_intel.post_source AS
SELECT 'instagram'::text AS platform,
       ip.id             AS post_id,
       CASE pr.project WHEN 'food_trends_brands' THEN 'brand' ELSE 'influencer' END AS source
  FROM public.instagram_posts ip
  JOIN public.instagram_profile pr ON pr.username = ip.username
 WHERE pr.project IN {FOOD_PROJECTS}
"""

VIEW = """
CREATE OR REPLACE VIEW food_intel.trend_posts AS
SELECT cp.platform, cp.post_id, cp.source, cp.post_url, cp.author_username,
       cp.caption, cp.hashtags, cp.likes, cp.comments, cp.views,
       cp.engagement_total, cp.media_keys, cp.country, cp.posted_at, cp.cohort,
       pf.is_food
  FROM public.community_posts cp
  LEFT JOIN food_intel.post_food pf
         ON pf.platform = cp.platform AND pf.post_id = cp.post_id
 WHERE NOT EXISTS (SELECT 1 FROM (SELECT DISTINCT username,
               CASE project WHEN 'food_trends_brands' THEN 'brand' ELSE 'influencer' END AS source
          FROM public.instagram_profile
         WHERE project IN ('food_trends_brands', 'food_trends_influencers')) t WHERE t.username = cp.author_username)
UNION ALL
SELECT 'instagram'                                   AS platform,
       ip.id                                         AS post_id,
       t.source                                      AS source,
       'https://www.instagram.com/p/' || ip.id       AS post_url,
       ip.username                                   AS author_username,
       btrim(ip.caption)                             AS caption,
       ARRAY(SELECT DISTINCT lower(m[1])
               FROM regexp_matches(ip.caption, '#([A-Za-z0-9_]+)', 'g') AS m) AS hashtags,
       coalesce(ip.likes, 0)                         AS likes,
       coalesce(ip.comments, 0)                      AS comments,
       coalesce(ip.views, 0)                         AS views,
       coalesce(ip.likes, 0) + coalesce(ip.comments, 0) AS engagement_total,
       -- The account crawl left these pictures in the raw bucket. Nothing is
       -- copied: the key names its bucket and the presigner reads it there.
       -- A keyword-scraped duplicate that already reached the trends bucket
       -- keeps its own key and is presigned from there.
       coalesce(cpm.media_keys,
                ARRAY['s3://raw-data-bucket/media/instagram/' || ip.id || '.jpg'])
                                                     AS media_keys,
       -- The crawl records the account's country as KSA or UAE while the
       -- community dump spells it out, so both land on the same ISO code here.
       -- Left null, every tracked post was unplaceable: Almarai's 329 posts
       -- could not be counted as Saudi however the question was asked.
       CASE upper(btrim(pr.country))
            WHEN 'KSA' THEN 'SA' WHEN 'UAE' THEN 'AE'
            WHEN 'IND' THEN 'IN' WHEN 'MYS' THEN 'MY'
            ELSE NULL END                              AS country,
       ip.uploaded_at                                AS posted_at,
       'tracked'::text                               AS cohort,
       pf.is_food                                    AS is_food
  FROM public.instagram_posts ip
  JOIN (SELECT DISTINCT username,
               CASE project WHEN 'food_trends_brands' THEN 'brand' ELSE 'influencer' END AS source
          FROM public.instagram_profile
         WHERE project IN ('food_trends_brands', 'food_trends_influencers')) t ON t.username = ip.username
  LEFT JOIN public.instagram_profile pr ON pr.username = ip.username
  LEFT JOIN food_intel.post_food pf
         ON pf.platform = 'instagram' AND pf.post_id = ip.id
  LEFT JOIN public.community_posts cpm
         ON cpm.platform = 'instagram' AND cpm.post_id = ip.id
 WHERE ip.caption IS NOT NULL
   AND btrim(ip.caption) <> ''
   AND lower(btrim(ip.caption)) <> ALL (ARRAY['nan','none','null','undefined']::text[])
   AND ip.uploaded_at IS NOT NULL
"""


def _exec(sql: str, label: str) -> int:
    with store.get_conn() as conn, conn.cursor() as cur:
        cur.execute("SET LOCAL statement_timeout = '0'")
        cur.execute(sql)
        n = cur.rowcount
    logger.info("%s: %s rows", label, n)
    return n


def build() -> dict:
    _exec(POST_FOOD, "post_food table ready")
    _exec(POST_SOURCE, "post_source view created")
    seeded = _exec(SEED_POST_FOOD, "food verdicts filled in for unscored posts")
    _exec(VIEW, "trend_posts view created")
    with store.get_conn() as conn, conn.cursor() as cur:
        cur.execute("""SELECT source, count(*), count(*) FILTER (WHERE is_food) 
                       FROM food_intel.trend_posts GROUP BY 1 ORDER BY 2 DESC""")
        mix = {r[0]: {"posts": r[1], "food": r[2]} for r in cur.fetchall()}
    return {"seeded": seeded, "mix": mix}


def main():
    logging.basicConfig(level=logging.INFO,
                        format="%(asctime)s %(levelname)s %(name)s %(message)s")
    argparse.ArgumentParser(description=__doc__).parse_args()
    result = build()
    for source, counts in result["mix"].items():
        logger.info("  %-11s %7s posts  %7s food", source, counts["posts"], counts["food"])


if __name__ == "__main__":
    main()
