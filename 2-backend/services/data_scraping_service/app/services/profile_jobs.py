import asyncio
import json
from typing import Any
from uuid import uuid4

from services.data_scraping_service.app.core.config import get_settings
from services.data_scraping_service.app.models.instagram import InstagramProfileScrapeRequest
from services.data_scraping_service.app.services.instagram import (
    persist_profiles,
    scrape_instagram_profiles,
)
from shared.redis import ensure_redis


_jobs: dict[str, dict[str, Any]] = {}
_jobs_lock = asyncio.Lock()
_KEY_PREFIX = "data-scraping:instagram-profile-job:"


async def _save_job(job: dict[str, Any]) -> None:
    async with _jobs_lock:
        _jobs[job["job_id"]] = job
    redis = await ensure_redis()
    if redis:
        await redis.set(
            f"{_KEY_PREFIX}{job['job_id']}",
            json.dumps(job),
            ex=get_settings().SCRAPING_JOB_TTL_SECONDS,
        )


async def create_profile_job(request: InstagramProfileScrapeRequest) -> dict[str, Any]:
    job = {
        "job_id": str(uuid4()),
        "status": "queued",
        "total": len(request.usernames),
        "completed": 0,
        "successful": 0,
        "failed": 0,
        "progress_percent": 0.0,
        "current_username": None,
        "save_to_database": request.save_to_database,
        "profiles": [],
        "errors": [],
    }
    await _save_job(job)
    return job


async def get_profile_job(job_id: str) -> dict[str, Any] | None:
    redis = await ensure_redis()
    if redis:
        raw = await redis.get(f"{_KEY_PREFIX}{job_id}")
        if raw:
            return json.loads(raw)
    async with _jobs_lock:
        return _jobs.get(job_id)


async def run_profile_job(job_id: str, request: InstagramProfileScrapeRequest) -> None:
    job = await get_profile_job(job_id)
    if not job:
        return
    job["status"] = "running"
    await _save_job(job)

    for username in request.usernames:
        job["current_username"] = username
        await _save_job(job)
        single_request = request.model_copy(update={"usernames": [username]})
        try:
            profiles = await scrape_instagram_profiles(single_request)
            if request.save_to_database:
                await persist_profiles(profiles)
            job["profiles"].extend(
                json.loads(profile.model_dump_json()) for profile in profiles
            )
            job["successful"] += 1
        except Exception as exc:
            job["failed"] += 1
            job["errors"].append({"username": username, "message": str(exc)})
        finally:
            job["completed"] += 1
            job["progress_percent"] = round(job["completed"] / job["total"] * 100, 2)
            await _save_job(job)

    job["current_username"] = None
    job["status"] = "completed_with_errors" if job["failed"] else "completed"
    await _save_job(job)
