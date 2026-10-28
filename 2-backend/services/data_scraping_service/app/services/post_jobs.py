import asyncio
import json
from typing import Any
from uuid import uuid4

from services.data_scraping_service.app.core.config import get_settings
from services.data_scraping_service.app.models.instagram_posts import InstagramPostScrapeRequest
from services.data_scraping_service.app.services.instagram_posts import (
    persist_posts,
    scrape_posts_for_username,
    upload_post_images,
)
from shared.redis import ensure_redis


_jobs: dict[str, dict[str, Any]] = {}
_lock = asyncio.Lock()
_KEY_PREFIX = "data-scraping:instagram-post-job:"


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


async def create_post_job(request: InstagramPostScrapeRequest) -> dict[str, Any]:
    job = {
        "job_id": str(uuid4()),
        "status": "queued",
        "total": len(request.usernames),
        "completed": 0,
        "successful": 0,
        "failed": 0,
        "progress_percent": 0.0,
        "current_username": None,
        "scraped_posts": 0,
        "saved_to_database": request.save_to_database,
        "upload_images_to_s3": request.upload_images_to_s3,
        "images_uploaded": 0,
        "images_skipped": 0,
        "images_failed": 0,
        "posts": [],
        "errors": [],
    }
    await _save(job)
    return job


async def get_post_job(job_id: str) -> dict[str, Any] | None:
    redis = await ensure_redis()
    if redis:
        raw = await redis.get(f"{_KEY_PREFIX}{job_id}")
        if raw:
            return json.loads(raw)
    async with _lock:
        return _jobs.get(job_id)


async def run_post_job(job_id: str, request: InstagramPostScrapeRequest) -> None:
    job = await get_post_job(job_id)
    if not job:
        return
    job["status"] = "running"
    await _save(job)

    for username in request.usernames:
        job["current_username"] = username
        await _save(job)
        try:
            posts = await scrape_posts_for_username(username, request)
            if request.upload_images_to_s3:
                await upload_post_images(posts)
            if request.save_to_database:
                await persist_posts(posts)
            job["posts"].extend(json.loads(post.model_dump_json()) for post in posts)
            job["scraped_posts"] += len(posts)
            job["images_uploaded"] += sum(p.image_upload_status == "uploaded" for p in posts)
            job["images_skipped"] += sum(p.image_upload_status == "skipped" for p in posts)
            job["images_failed"] += sum(p.image_upload_status == "failed" for p in posts)
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
