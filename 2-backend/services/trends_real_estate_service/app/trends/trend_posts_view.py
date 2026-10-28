"""Give the trend pipeline one read surface, built from the sources we chose.

The three base views in migration 011 already encode every decision about what
this service reads: which projects count as a tracked developer, which count as
an influencer, which platforms are in, and how the per-platform engagement
figures are computed. This module does not re-derive any of that. It unions
those three and adds the two columns the pipeline needs on top:

Cohort is decided by AUTHOR, not by which scrape found the post. A post written
by a tracked developer is a brand post however we came across it, and 16,468 of
41,263 community rows were authored by tracked developers - DAMAC, Aldar, Azizi,
Meraas. The interpretation prompt reads source mix as the finding, so those rows
made it report developers' own marketing as "genuine market interest".

They are RELABELLED, not dropped. The two branches read different source tables:
community_posts comes from the keyword scrape, brand_posts from the account
scrape, and only 465 of those 16,468 posts exist in both. Excluding them removed
15,242 real posts from the corpus - the same mistake in the other direction.

A relabelled post takes its author's COUNTRY along with the cohort. The keyword
scrape carries no country at all, so without this the 16.9k relabelled posts
had none, and every country filter - the assistant's post search, its counts,
the per-market trend runs - silently lost them. Every tracked profile has one,
mapped to ISO the same way brand_posts maps it ('KSA' -> SA, 'UAE' -> AE).

  cohort       which pool a row came from - 'brand', 'influencer' or
               'community'. The pipeline filters on it, and 'all' means no
               filter at all.

Deduplication is by (platform, post_id) with brand > influencer > community, so
a post the community scrape also happened to catch is counted once, on the
developer's own authoritative feed.

NOTE ON PROVENANCE. The food service's version of this file rebuilt the union
from scratch against public.instagram_posts alone, and additionally ran a DELETE
and an UPDATE against public.community_posts to undo a historical migration of
its own. Neither belongs here: that table is shared with the food service and is
read-only to us, and an Instagram-only union would silently drop every Saudi
developer and all 9,582 TikTok, X and LinkedIn brand posts.
"""
import argparse
import logging

from services.trends_real_estate_service.app.trends import store

logger = logging.getLogger("etl.trend_posts_view")

# One place derives "who wrote this", for the assistant's vector search: a
# source filter over a small slice of the corpus cannot be satisfied by an
# approximate-nearest-neighbour pool, so the pool itself is restricted through
# this view rather than the rows being filtered after the fact.
POST_SOURCE = """
CREATE OR REPLACE VIEW realestate_intel.post_source AS
SELECT platform, post_id, source FROM realestate_intel.brand_posts
UNION ALL
SELECT platform, post_id, source FROM realestate_intel.influencer_posts
"""

VIEW = """
CREATE OR REPLACE VIEW realestate_intel.trend_posts AS
WITH tracked AS (
    SELECT username, min(cohort) AS cohort,
           min(CASE upper(btrim(country)) WHEN 'KSA' THEN 'SA'
                                          WHEN 'UAE' THEN 'AE' END) AS country
      FROM (
        SELECT lower(ltrim(username, '@')) AS username,
               CASE WHEN project = 'realestate_trends_influencers'
                    THEN 'influencer' ELSE 'brand' END AS cohort,
               country
          FROM public.instagram_profile
         WHERE project = ANY(ARRAY['realestate_dbh', 'realestate_trends',
                                   'realestate_trends_influencers'])
        UNION ALL
        SELECT lower(ltrim(username::text, '@')),
               CASE WHEN project::text = 'realestate_trends_influencers'
                    THEN 'influencer' ELSE 'brand' END,
               country::text
          FROM public.tiktok_profiles
         WHERE project::text = ANY(ARRAY['realestate_dbh', 'realestate_trends',
                                         'realestate_trends_influencers'])
        UNION ALL
        SELECT lower(ltrim(username, '@')),
               CASE WHEN project = 'realestate_trends_influencers'
                    THEN 'influencer' ELSE 'brand' END,
               country
          FROM public.twitter_profiles
         WHERE project = ANY(ARRAY['realestate_dbh', 'realestate_trends',
                                   'realestate_trends_influencers'])
        UNION ALL
        SELECT lower(ltrim(universal_name, '@')),
               CASE WHEN project::text = 'realestate_trends_influencers'
                    THEN 'influencer' ELSE 'brand' END,
               country
          FROM public.linkedin_profiles
         WHERE project::text = ANY(ARRAY['realestate_dbh', 'realestate_trends',
                                         'realestate_trends_influencers'])
    ) p GROUP BY username
), all_sources AS (
    SELECT b.*, 'brand'::text AS cohort, 1 AS precedence
      FROM realestate_intel.brand_posts b
    UNION ALL
    SELECT i.*, 'influencer'::text, 2
      FROM realestate_intel.influencer_posts i
    UNION ALL
    SELECT c.platform, c.post_id,
           COALESCE(t.cohort, c.source), c.post_url, c.author_username, c.caption,
           c.hashtags, c.likes, c.comments, c.views, c.engagement_total,
           c.media_keys, COALESCE(c.country, t.country), c.posted_at,
           COALESCE(t.cohort, 'community'), 3
      FROM realestate_intel.community_posts c
      LEFT JOIN tracked t ON t.username = lower(c.author_username)
), deduped AS (
    SELECT DISTINCT ON (platform, post_id)
           platform, post_id, source, post_url, author_username, caption,
           hashtags, likes, comments, views, engagement_total, media_keys,
           country, posted_at, cohort
      FROM all_sources
     ORDER BY platform, post_id, precedence
)
SELECT * FROM deduped
"""


def _exec(sql: str, label: str) -> int:
    with store.get_conn() as conn, conn.cursor() as cur:
        cur.execute("SET LOCAL statement_timeout = '0'")
        cur.execute(sql)
        n = cur.rowcount
    logger.info("%s: %s rows", label, n)
    return n


def build() -> dict:
    _exec(VIEW, "trend_posts view created")
    _exec(POST_SOURCE, "post_source view created")
    with store.get_conn() as conn, conn.cursor() as cur:
        cur.execute("""SELECT cohort, count(*)
                       FROM realestate_intel.trend_posts GROUP BY 1 ORDER BY 2 DESC""")
        mix = {r[0]: {"posts": r[1]} for r in cur.fetchall()}
    return {"mix": mix}


def main():
    logging.basicConfig(level=logging.INFO,
                        format="%(asctime)s %(levelname)s %(name)s %(message)s")
    argparse.ArgumentParser(description=__doc__).parse_args()
    result = build()
    for cohort, counts in result["mix"].items():
        logger.info("  %-11s %7s posts", cohort, counts["posts"])


if __name__ == "__main__":
    main()
