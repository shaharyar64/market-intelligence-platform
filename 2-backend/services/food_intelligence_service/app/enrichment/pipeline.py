import logging
import threading
from concurrent.futures import ThreadPoolExecutor
from datetime import datetime, timezone

from services.food_intelligence_service.app.core.config import get_settings
from services.food_intelligence_service.app.db import postgres, analysis_store
from services.food_intelligence_service.app.enrichment.adapters import normalize_post
from services.food_intelligence_service.app.enrichment.agent import all_nodes_failed, analyze_post
from services.food_intelligence_service.app.services import s3_media

settings = get_settings()
logger = logging.getLogger(__name__)


def _enrich_platform(platform: str, projects: list[str], limit: int | None, force: bool,
                     workers: int = 6) -> dict:
    """Enrich a platform's posts, running posts concurrently.

    Each post fans out to seven LLM nodes internally, but the posts themselves
    used to run one after another — end to end that measured about one post per
    minute, so a 1,000-post run would have taken most of a day for work that is
    almost entirely spent waiting on the network. Both stores hand out pooled
    SQLAlchemy connections, so the worker count is capped below the smaller
    pool (10 + 5 overflow).
    """
    stats = {"fetched": 0, "skipped_existing": 0, "skipped_unmapped": 0, "enriched": 0, "errors": 0}
    rows = postgres.fetch_posts(platform, projects, limit=limit)
    stats["fetched"] = len(rows)
    logger.info(f"[{platform}] fetched {len(rows)} posts, {workers} workers")
    lock = threading.Lock()

    def bump(key: str) -> int:
        with lock:
            stats[key] += 1
            return stats[key]

    def process(row: dict) -> None:
        try:
            normalized = normalize_post(platform, row)
            if not normalized["brand"]:
                bump("skipped_unmapped")
                return
            if not force and analysis_store.post_already_enriched(normalized["post_id"], platform):
                bump("skipped_existing")
                return

            image_key = s3_media.resolve_image_key(platform, normalized["post_id"])
            analysis = analyze_post(normalized, image_key=image_key)
            if all_nodes_failed(analysis):
                # Almost always a rate limit. Leaving the row unwritten is what
                # lets the next run pick the post up again.
                bump("errors")
                logger.warning("[%s] every node failed for %s; not stored",
                               platform, normalized["post_id"])
                return
            engagement = normalized["engagement"]
            analysis_store.upsert_post_analysis({
                "platform": platform,
                "post_id": normalized["post_id"],
                "brand_key": normalized["brand"]["key"],
                "brand_name": normalized["brand"]["name"],
                "account_type": normalized["brand"]["account_type"],
                "account_username": normalized["account_username"],
                "caption": normalized["text"],
                "language": analysis.get("language"),
                "engagement": {k: engagement[k] for k in
                               ("likes", "comments", "views", "shares", "bookmarks")},
                "engagement_total": engagement["total"],
                "analysis": analysis,
                "image_key": image_key,
                "posted_at": normalized["posted_at"],
                "processed_at": datetime.now(timezone.utc).isoformat(),
                "post_url": normalized.get("post_url"),
            })
            done = bump("enriched")
            if done % 25 == 0:
                logger.info(f"[{platform}] enriched {done} so far…")
        except Exception as e:
            bump("errors")
            logger.exception(f"[{platform}] failed on post {row.get('post_id')}: {e}")

    with ThreadPoolExecutor(max_workers=workers) as pool:
        list(pool.map(process, rows))

    return stats


def run_enrichment(platforms=None, projects=None, limit=None, force=False, workers: int = 6) -> dict:
    platforms = platforms or settings.ENRICH_PLATFORMS
    projects = projects or settings.ENRICH_PROJECTS
    logger.info(f"Enrichment start — platforms={platforms} projects={projects} limit={limit} force={force}")

    totals = {}
    for platform in platforms:
        totals[platform] = _enrich_platform(platform, projects, limit, force, workers=workers)
    logger.info(f"Enrichment done — {totals}")
    return totals
