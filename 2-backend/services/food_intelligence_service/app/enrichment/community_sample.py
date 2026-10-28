"""Enrich a representative sample of consumer posts.

The tracked brands and influencers are enriched exhaustively - there are only
~5.7k of their posts between them. Consumers are a different scale: 354,912 food
posts, which at seven LLM nodes each would cost thousands of dollars to analyse
in full and say very little more than a sample does. So this reads a stratified
sample, and every screen built on it should say so.

Stratified by trend rather than drawn flat. A flat sample of a corpus this
skewed would be dominated by whichever topics the scraper happened to collect
most of, and the question these panels answer - what do consumers talk about
where brands do and do not show up - is a per-trend question. Allocation is
proportional to each trend's size, with a floor so a small trend still returns
enough posts to say anything, and a cap so a large one cannot swamp the sample.

Consumer posts carry no account identity by design: brand_key is the constant
'community' rather than an account, because the cohort is the subject here and
no individual poster is.
"""
import argparse
import json
import logging
import math
import threading
from concurrent.futures import ThreadPoolExecutor

from services.food_intelligence_service.app.core.config import get_settings
from services.food_intelligence_service.app.db import analysis_store
from services.food_intelligence_service.app.enrichment.agent import all_nodes_failed, analyze_post
from services.food_intelligence_service.app.trends import store

logger = logging.getLogger("enrichment.community")

COHORT_KEY = "community"
COHORT_NAME = "Consumers"

MIN_PER_TREND = 8
MAX_PER_TREND = 60


def _allocate(sizes: dict, target: int) -> dict:
    """Posts to sample per trend: proportional, bounded at both ends."""
    total = sum(sizes.values()) or 1
    plan = {}
    for tid, n in sizes.items():
        share = math.ceil(target * n / total)
        plan[tid] = max(MIN_PER_TREND, min(MAX_PER_TREND, min(share, n)))
    return plan


def select(target: int) -> list:
    """The sample, as rows ready to enrich.

    Ordered by engagement within each trend: a post nobody engaged with is weak
    evidence of what a cohort responds to, and the sample is small enough that
    spending it on the visible end of the corpus is the better trade. Posts
    without an image are skipped, since half of what the analysis reads is the
    picture.
    """
    with store.get_conn() as conn, conn.cursor() as cur:
        # Pipeline trends only. Ad-hoc trends a user asked the assistant to
        # build overlap the discovered ones and would tilt a sample that is
        # meant to represent the corpus, not anyone's questions about it.
        cur.execute("""SELECT trend_id, member_posts FROM food_intel.trends
                       WHERE run_id = (SELECT run_id FROM food_intel.trends
                                       WHERE origin = 'pipeline' AND country IS NULL
                                       ORDER BY created_at DESC LIMIT 1)
                         AND level = 'micro' AND origin = 'pipeline'""")
        trends = cur.fetchall()

    members = {}
    for tid, mp in trends:
        mp = mp if isinstance(mp, list) else json.loads(mp)
        members[tid] = [(m["platform"], m["post_id"]) for m in mp]
    plan = _allocate({t: len(v) for t, v in members.items()}, target)

    rows = []
    seen = set()
    with store.get_conn() as conn, conn.cursor() as cur:
        for tid, ids in members.items():
            if not ids:
                continue
            cur.execute("""
                SELECT p.platform, p.post_id, p.caption, p.author_username, p.post_url,
                       p.posted_at, p.likes, p.comments, p.views, p.engagement_total,
                       p.media_keys[1]
                FROM food_intel.trend_posts p
                WHERE (p.platform, p.post_id) IN %s
                  AND p.source = 'community' AND p.is_food IS TRUE
                  AND p.caption IS NOT NULL AND p.caption <> ''
                  AND p.media_keys IS NOT NULL
                ORDER BY p.engagement_total DESC NULLS LAST
                LIMIT %s
            """, (tuple(ids), plan[tid]))
            for r in cur.fetchall():
                key = (r[0], r[1])
                if key in seen:
                    continue
                seen.add(key)
                rows.append({
                    "platform": r[0], "post_id": r[1], "caption": r[2] or "",
                    "author_username": r[3], "post_url": r[4], "posted_at": r[5],
                    "likes": r[6] or 0, "comments": r[7] or 0, "views": r[8] or 0,
                    "engagement_total": r[9] or 0, "media_key": r[10],
                    "trend_id": tid,
                })
    return rows


def _already_enriched() -> set:
    with store.get_conn() as conn, conn.cursor() as cur:
        cur.execute("""SELECT platform, post_id FROM food_intel.post_analysis
                       WHERE account_type = 'community'""")
        return {(r[0], r[1]) for r in cur.fetchall()}


def run(target: int = 3000, workers: int = 8, force: bool = False) -> dict:
    rows = select(target)
    if not force:
        done = _already_enriched()
        rows = [r for r in rows if (r["platform"], r["post_id"]) not in done]
    stats = {"selected": len(rows), "enriched": 0, "errors": 0}
    if not rows:
        return stats
    logger.info("community sample: %s posts across %s trends, %s workers",
                len(rows), len({r["trend_id"] for r in rows}), workers)
    lock = threading.Lock()

    def process(row: dict) -> None:
        try:
            normalized = {
                "post_id": row["post_id"], "platform": row["platform"],
                "account_username": row["author_username"],
                "brand": {"key": COHORT_KEY, "name": COHORT_NAME,
                          "account_type": "community"},
                "text": (row["caption"] or "").strip(),
                "posted_at": row["posted_at"].isoformat() if row["posted_at"] else None,
                "post_url": row["post_url"],
            }
            key = row["media_key"]
            # Community media was migrated to the trends bucket; brand and
            # influencer media never left the raw one, so the key has to say
            # which bucket it means.
            if key and not key.startswith("s3://"):
                key = "s3://" + get_settings().TRENDS_MEDIA_S3_BUCKET + "/" + key
            analysis = analyze_post(normalized, image_key=key)
            if all_nodes_failed(analysis):
                with lock:
                    stats["errors"] += 1
                logger.warning("every node failed for %s; not stored", row["post_id"])
                return
            analysis_store.upsert_post_analysis({
                "platform": row["platform"], "post_id": row["post_id"],
                "brand_key": COHORT_KEY, "brand_name": COHORT_NAME,
                "account_type": "community",
                "account_username": row["author_username"],
                "caption": normalized["text"],
                "language": analysis.get("language"),
                "engagement": {"likes": row["likes"], "comments": row["comments"],
                               "views": row["views"], "shares": 0, "bookmarks": 0},
                "engagement_total": row["engagement_total"],
                "analysis": analysis, "image_key": key,
                "posted_at": normalized["posted_at"],
                "processed_at": None, "post_url": row["post_url"],
            })
            with lock:
                stats["enriched"] += 1
                if stats["enriched"] % 100 == 0:
                    logger.info("enriched %s / %s", stats["enriched"], len(rows))
        except Exception:
            with lock:
                stats["errors"] += 1
            logger.exception("community post %s failed", row.get("post_id"))

    with ThreadPoolExecutor(max_workers=workers) as pool:
        list(pool.map(process, rows))
    logger.info("community sample done: %s", stats)
    return stats


def main():
    logging.basicConfig(level=logging.INFO,
                        format="%(asctime)s %(levelname)s %(name)s %(message)s")
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--target", type=int, default=3000)
    ap.add_argument("--workers", type=int, default=8)
    ap.add_argument("--force", action="store_true")
    ap.add_argument("--dry-run", action="store_true")
    args = ap.parse_args()
    if args.dry_run:
        rows = select(args.target)
        per = {}
        for r in rows:
            per[r["trend_id"]] = per.get(r["trend_id"], 0) + 1
        print("would enrich %s posts across %s trends" % (len(rows), len(per)))
        if per:
            print("  per-trend: min %s, max %s" % (min(per.values()), max(per.values())))
        return
    run(target=args.target, workers=args.workers, force=args.force)


if __name__ == "__main__":
    main()
