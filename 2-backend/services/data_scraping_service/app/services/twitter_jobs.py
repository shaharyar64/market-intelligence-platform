import asyncio
import json
from typing import Any
from uuid import uuid4

from services.data_scraping_service.app.core.config import get_settings
from services.data_scraping_service.app.models.twitter import TwitterProfileScrapeRequest
from services.data_scraping_service.app.services.twitter import (
    persist_twitter_profiles,
    scrape_twitter_profile,
)
from shared.redis import ensure_redis


_jobs: dict[str, dict[str, Any]] = {}
_lock = asyncio.Lock()
_KEY_PREFIX = "data-scraping:twitter-profile-job:"


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


async def create_twitter_profile_job(request: TwitterProfileScrapeRequest) -> dict[str, Any]:
    job = {
        "job_id": str(uuid4()),
        "status": "queued",
        "total": len(request.usernames),
        "completed": 0,
        "successful": 0,
        "failed": 0,
        "progress_percent": 0.0,
        "current_username": None,
        "saved_to_database": request.save_to_database,
        "profiles": [],
        "errors": [],
    }
    await _save(job)
    return job


async def get_twitter_profile_job(job_id: str) -> dict[str, Any] | None:
    redis = await ensure_redis()
    if redis:
        raw = await redis.get(f"{_KEY_PREFIX}{job_id}")
        if raw:
            return json.loads(raw)
    async with _lock:
        return _jobs.get(job_id)


async def run_twitter_profile_job(
    job_id: str,
    request: TwitterProfileScrapeRequest,
) -> None:
    job = await get_twitter_profile_job(job_id)
    if not job:
        return
    job["status"] = "running"
    await _save(job)

    for username in request.usernames:
        job["current_username"] = username
        await _save(job)
        try:
            profile = await scrape_twitter_profile(username, request)
            if request.save_to_database:
                await persist_twitter_profiles([profile])
            job["profiles"].append(json.loads(profile.model_dump_json()))
            job["successful"] += 1
        except Exception as exc:
            job["failed"] += 1
            job["errors"].append({"username": username, "message": str(exc)})
        finally:
            job["completed"] += 1
            job["progress_percent"] = round(job["completed"] / job["total"] * 100, 2)
            await _save(job)

    job["current_username"] = None
    job["status"] = "completed_with_errors" if job["failed"] else "completed"
    await _save(job)
