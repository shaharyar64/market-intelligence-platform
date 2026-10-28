import logging

from fastapi import APIRouter, BackgroundTasks, HTTPException, status

from services.data_scraping_service.app.models.tiktok_posts import (
    TikTokPostJobCreated,
    TikTokPostJobStatus,
    TikTokPostScrapeRequest,
    TikTokPostScrapeResponse,
)
from services.data_scraping_service.app.services.instagram import (
    InstagramScrapeError,
    ScraperConfigurationError,
)
from services.data_scraping_service.app.services.tiktok_post_jobs import (
    create_tiktok_post_job,
    get_tiktok_post_job,
    run_tiktok_post_job,
)
from services.data_scraping_service.app.services.tiktok_posts import (
    persist_tiktok_posts,
    scrape_tiktok_posts,
)


logger = logging.getLogger(__name__)
router = APIRouter(prefix="/tiktok", tags=["TikTok Scraping"])


@router.post(
    "/posts/jobs",
    response_model=TikTokPostJobCreated,
    status_code=status.HTTP_202_ACCEPTED,
)
async def start_post_job(
    request: TikTokPostScrapeRequest,
    background_tasks: BackgroundTasks,
) -> TikTokPostJobCreated:
    job = await create_tiktok_post_job(request)
    background_tasks.add_task(run_tiktok_post_job, job["job_id"], request)
    return TikTokPostJobCreated(
        job_id=job["job_id"],
        total=job["total"],
        progress_url=f"/api/v1/data-scraping/tiktok/posts/jobs/{job['job_id']}",
    )


@router.get("/posts/jobs/{job_id}", response_model=TikTokPostJobStatus)
async def post_job_status(job_id: str) -> TikTokPostJobStatus:
    job = await get_tiktok_post_job(job_id)
    if not job:
        raise HTTPException(status_code=404, detail="Scraping job not found")
    return TikTokPostJobStatus.model_validate(job)


@router.post("/posts", response_model=TikTokPostScrapeResponse)
async def scrape_posts(request: TikTokPostScrapeRequest) -> TikTokPostScrapeResponse:
    try:
        posts = await scrape_tiktok_posts(request)
        if request.save_to_database:
            await persist_tiktok_posts(posts)
    except ScraperConfigurationError as exc:
        raise HTTPException(status_code=503, detail=str(exc)) from exc
    except InstagramScrapeError as exc:
        raise HTTPException(status_code=502, detail=str(exc)) from exc
    except Exception as exc:
        logger.exception("TikTok post processing failed")
        raise HTTPException(status_code=500, detail="TikTok post processing failed") from exc
    return TikTokPostScrapeResponse(
        requested_urls=len(request.start_urls),
        scraped_posts=len(posts),
        saved_to_database=request.save_to_database,
        posts=posts,
    )
