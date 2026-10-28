import asyncio
import json
from typing import Any
from uuid import uuid4

from services.data_scraping_service.app.core.config import get_settings
from services.data_scraping_service.app.models.twitter_keywords import TwitterKeywordScrapeRequest
from services.data_scraping_service.app.services.twitter_keywords import (
    persist_keyword_posts,
    scrape_keyword,
)
from shared.redis import ensure_redis


_jobs: dict[str, dict[str, Any]] = {}
_lock = asyncio.Lock()
_KEY_PREFIX = "data-scraping:twitter-keyword-job:"


async def _save(job: dict[str, Any]) -> None:
    async with _lock:
        _jobs[job["job_id"]] = job
    redis = await ensure_redis()
    if redis:
        await redis.set(
            f"{_KEY_PREFIX}{job['job_id']}",
            json.dumps(job),
            ex=get_settings().SCRAPING_JOB_TTL_SECONDS,
        )


async def create_keyword_job(request: TwitterKeywordScrapeRequest) -> dict[str, Any]:
    job = {
        "job_id": str(uuid4()),
        "status": "queued",
        "total": len(request.keywords),
        "completed": 0,
        "successful": 0,
        "failed": 0,
        "progress_percent": 0.0,
        "current_keyword": None,
        "scraped_posts": 0,
        "saved_to_database": request.save_to_database,
        "posts": [],
        "errors": [],
    }
    await _save(job)
    return job


async def get_keyword_job(job_id: str) -> dict[str, Any] | None:
    redis = await ensure_redis()
    if redis:
        raw = await redis.get(f"{_KEY_PREFIX}{job_id}")
        if raw:
            return json.loads(raw)
    async with _lock:
        return _jobs.get(job_id)


async def run_keyword_job(job_id: str, request: TwitterKeywordScrapeRequest) -> None:
    job = await get_keyword_job(job_id)
    if not job:
        return
    job["status"] = "running"
    await _save(job)
    for keyword in request.keywords:
        job["current_keyword"] = keyword
        await _save(job)
        try:
            posts = await scrape_keyword(keyword, request)
            if request.save_to_database:
                await persist_keyword_posts(posts)
            job["posts"].extend(json.loads(post.model_dump_json()) for post in posts)
            job["scraped_posts"] += len(posts)
            job["successful"] += 1
        except Exception as exc:
            job["failed"] += 1
            job["errors"].append({"keyword": keyword, "message": str(exc)})
        finally:
            job["completed"] += 1
            job["progress_percent"] = round(job["completed"] / job["total"] * 100, 2)
            await _save(job)
    job["current_keyword"] = None
    job["status"] = "completed_with_errors" if job["failed"] else "completed"
    await _save(job)
