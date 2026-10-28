import logging
import threading
from concurrent.futures import ThreadPoolExecutor
from datetime import datetime, timezone

from services.trends_real_estate_service.app.core.config import get_settings
from services.trends_real_estate_service.app.db import analysis_store, postgres
from services.trends_real_estate_service.app.enrichment.adapters import normalize_post
from services.trends_real_estate_service.app.enrichment.agent import (
    all_nodes_failed,
    analyze_post,
    retryable_failures,
)
from services.trends_real_estate_service.app.services import s3_media

settings = get_settings()
logger = logging.getLogger(__name__)


def _with_retry(fn, label: str, attempts: int = 3):
    """Run a startup read again if the connection drops.

    From outside the VPC the RDS link drops the odd query mid-transfer ("SSL
    SYSCALL error: EOF", a statement timeout on a 6ms query). A per-post failure
    only costs that post, but this read gates the whole platform, so one blip
    used to abort the run before a single post was enriched.
    """
    import time
    for attempt in range(1, attempts + 1):
        try:
            return fn()
        except Exception as exc:
            if attempt == attempts:
                raise
            logger.warning("%s failed (attempt %s/%s), retrying: %s",
                           label, attempt, attempts, str(exc).splitlines()[0])
            time.sleep(5 * attempt)


def _enrich_platform(platform: str, projects: list[str], limit: int | None, force: bool,
                     workers: int = 6, since: str | None = None) -> dict:
    """Enrich a platform's posts, running posts concurrently.

    Each post fans out to seven LLM nodes internally, but the posts themselves
    used to run one after another — end to end that measured about one post per
    minute, so a 1,000-post run would have taken most of a day for work that is
    almost entirely spent waiting on the network. Both stores hand out pooled
    SQLAlchemy connections, so the worker count is capped below the smaller
    pool (10 + 5 overflow).
    """
    stats = {"fetched": 0, "skipped_existing": 0, "skipped_unmapped": 0,
             "skipped_excluded": 0, "retried_partial": 0, "enriched": 0, "errors": 0}
    rows = postgres.fetch_posts(platform, projects, limit=limit, since=since)
    stats["fetched"] = len(rows)
    # Accounts kept off trends (a motorsport event, a charity) are not worth
    # seven LLM calls a post: nothing downstream reads their analysis.
    excluded = {a.lower() for a in settings.TREND_EXCLUDE_AUTHORS}
    # One query for the whole platform instead of one per post. It also carries
    # each row's _failed_nodes, so a post stored with failures can be picked up
    # again rather than counting as done forever.
    state = {} if force else _with_retry(lambda: analysis_store.fetch_enrichment_state(platform),
                                         f"[{platform}] enrichment state")
    logger.info(f"[{platform}] fetched {len(rows)} posts, {len(state)} already stored, {workers} workers")
    lock = threading.Lock()

    def bump(key: str) -> int:
        with lock:
            stats[key] += 1
            return stats[key]

    def process(row: dict) -> None:
        try:
            normalized = normalize_post(platform, row)
            if (normalized.get("account_username") or "").lower() in excluded:
                bump("skipped_excluded")
                return
            if not normalized["brand"]:
                bump("skipped_unmapped")
                return
            stored = state.get(normalized["post_id"]) if not force else None
            image_key = None
            if stored is not None:
                # Stored already - but only skip if nothing worth retrying is
                # outstanding. Resolving the image first is what lets us tell a
                # vision node that can succeed from one that never will.
                image_key = s3_media.resolve_image_key(platform, normalized["post_id"])
                outstanding = retryable_failures(
                    stored, bool((normalized.get("text") or "").strip()), bool(image_key))
                if not outstanding:
                    bump("skipped_existing")
                    return
                bump("retried_partial")
                logger.info("[%s] re-running %s for %s", platform,
                            ",".join(outstanding), normalized["post_id"])
            if image_key is None:
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
        except Exception:
            bump("errors")
            logger.exception("[%s] failed on post %s", platform, row.get("post_id"))

    with ThreadPoolExecutor(max_workers=workers) as pool:
        list(pool.map(process, rows))

    return stats


def run_enrichment(platforms=None, projects=None, limit=None, force=False, workers: int = 6,
                   since: str | None = None) -> dict:
    platforms = platforms or settings.ENRICH_PLATFORMS
    projects = projects or settings.ENRICH_PROJECTS
    logger.info(f"Enrichment start — platforms={platforms} projects={projects} limit={limit} "
                f"force={force} since={since}")

    totals = {}
    for platform in platforms:
        totals[platform] = _enrich_platform(platform, projects, limit, force, workers=workers,
                                            since=since)
    logger.info(f"Enrichment done — {totals}")
    return totals
