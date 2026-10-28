import logging

from fastapi import APIRouter, BackgroundTasks, HTTPException, status

from services.data_scraping_service.app.models.instagram_posts import (
    InstagramPostJobCreated,
    InstagramPostJobStatus,
    InstagramPostScrapeRequest,
    InstagramPostScrapeResponse,
)
from services.data_scraping_service.app.services.instagram import (
    InstagramScrapeError,
    ScraperConfigurationError,
)
from services.data_scraping_service.app.services.instagram_posts import (
    persist_posts,
    scrape_instagram_posts,
    upload_post_images,
)
from services.data_scraping_service.app.services.post_jobs import (
    create_post_job,
    get_post_job,
    run_post_job,
)


logger = logging.getLogger(__name__)
router = APIRouter(prefix="/instagram", tags=["Instagram Scraping"])


@router.post(
    "/posts/jobs",
    response_model=InstagramPostJobCreated,
    status_code=status.HTTP_202_ACCEPTED,
)
async def start_post_job(
    request: InstagramPostScrapeRequest,
    background_tasks: BackgroundTasks,
) -> InstagramPostJobCreated:
    job = await create_post_job(request)
    background_tasks.add_task(run_post_job, job["job_id"], request)
    return InstagramPostJobCreated(
        job_id=job["job_id"],
        total=job["total"],
        progress_url=f"/api/v1/data-scraping/instagram/posts/jobs/{job['job_id']}",
    )


@router.get("/posts/jobs/{job_id}", response_model=InstagramPostJobStatus)
async def post_job_status(job_id: str) -> InstagramPostJobStatus:
    job = await get_post_job(job_id)
    if not job:
        raise HTTPException(status_code=404, detail="Scraping job not found")
    return InstagramPostJobStatus.model_validate(job)


@router.post("/posts", response_model=InstagramPostScrapeResponse)
async def scrape_posts(request: InstagramPostScrapeRequest) -> InstagramPostScrapeResponse:
    try:
        posts = await scrape_instagram_posts(request)
        if request.upload_images_to_s3:
            await upload_post_images(posts)
        if request.save_to_database:
            await persist_posts(posts)
    except ScraperConfigurationError as exc:
        raise HTTPException(status_code=503, detail=str(exc)) from exc
    except InstagramScrapeError as exc:
        raise HTTPException(status_code=502, detail=str(exc)) from exc
    except Exception as exc:
        logger.exception("Instagram post processing failed")
        raise HTTPException(status_code=500, detail="Instagram post processing failed") from exc

    return InstagramPostScrapeResponse(
        requested_usernames=len(request.usernames),
        scraped_posts=len(posts),
        saved_to_database=request.save_to_database,
        upload_images_to_s3=request.upload_images_to_s3,
        images_uploaded=sum(post.image_upload_status == "uploaded" for post in posts),
        images_skipped=sum(post.image_upload_status == "skipped" for post in posts),
        images_failed=sum(post.image_upload_status == "failed" for post in posts),
        posts=posts,
    )
