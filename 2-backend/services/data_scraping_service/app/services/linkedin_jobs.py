import asyncio
import json
from typing import Any
from uuid import uuid4

from services.data_scraping_service.app.core.config import get_settings
from services.data_scraping_service.app.models.linkedin import LinkedInProfileScrapeRequest
from services.data_scraping_service.app.services.linkedin import persist_linkedin_profiles, scrape_linkedin_profile
from shared.redis import ensure_redis

_jobs: dict[str, dict[str, Any]] = {}
_lock = asyncio.Lock()
_PREFIX = "data-scraping:linkedin-profile-job:"

async def _save(job):
    async with _lock:
        _jobs[job["job_id"]] = job
    redis = await ensure_redis()
    if redis:
        await redis.set(f"{_PREFIX}{job['job_id']}", json.dumps(job), ex=get_settings().SCRAPING_JOB_TTL_SECONDS)

async def create_linkedin_job(request):
    job = {"job_id": str(uuid4()), "status": "queued", "total": len(request.profile_urls),
           "completed": 0, "successful": 0, "failed": 0, "progress_percent": 0.0,
           "current_profile_url": None, "saved_to_database": request.save_to_database,
           "profiles": [], "errors": []}
    await _save(job)
    return job

async def get_linkedin_job(job_id):
    redis = await ensure_redis()
    if redis:
        raw = await redis.get(f"{_PREFIX}{job_id}")
        if raw:
            return json.loads(raw)
    async with _lock:
        return _jobs.get(job_id)

async def run_linkedin_job(job_id, request):
    job = await get_linkedin_job(job_id)
    if not job:
        return
    job["status"] = "running"
    await _save(job)
    for url in request.profile_urls:
        job["current_profile_url"] = url
        await _save(job)
        try:
            profile = await scrape_linkedin_profile(url, request)
            if request.save_to_database:
                await persist_linkedin_profiles([profile])
            job["profiles"].append(json.loads(profile.model_dump_json()))
            job["successful"] += 1
        except Exception as exc:
            job["failed"] += 1
            job["errors"].append({"profile_url": url, "message": str(exc)})
        finally:
            job["completed"] += 1
            job["progress_percent"] = round(job["completed"] / job["total"] * 100, 2)
            await _save(job)
    job["current_profile_url"] = None
    job["status"] = "completed_with_errors" if job["failed"] else "completed"
    await _save(job)
