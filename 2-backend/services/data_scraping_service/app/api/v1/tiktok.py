import logging

from fastapi import APIRouter, BackgroundTasks, HTTPException, status

from services.data_scraping_service.app.models.tiktok import (
    TikTokProfileJobCreated,
    TikTokProfileJobStatus,
    TikTokProfileScrapeRequest,
    TikTokProfileScrapeResponse,
)
from services.data_scraping_service.app.services.instagram import (
    InstagramScrapeError,
    ScraperConfigurationError,
)
from services.data_scraping_service.app.services.tiktok import (
    persist_tiktok_profiles,
    scrape_tiktok_profiles,
)
from services.data_scraping_service.app.services.tiktok_jobs import (
    create_tiktok_profile_job,
    get_tiktok_profile_job,
    run_tiktok_profile_job,
)


logger = logging.getLogger(__name__)
router = APIRouter(prefix="/tiktok", tags=["TikTok Scraping"])


@router.post(
    "/profiles/jobs",
    response_model=TikTokProfileJobCreated,
    status_code=status.HTTP_202_ACCEPTED,
)
async def start_profile_job(
    request: TikTokProfileScrapeRequest,
    background_tasks: BackgroundTasks,
) -> TikTokProfileJobCreated:
    job = await create_tiktok_profile_job(request)
    background_tasks.add_task(run_tiktok_profile_job, job["job_id"], request)
    return TikTokProfileJobCreated(
        job_id=job["job_id"],
        total=job["total"],
        progress_url=f"/api/v1/data-scraping/tiktok/profiles/jobs/{job['job_id']}",
    )


@router.get("/profiles/jobs/{job_id}", response_model=TikTokProfileJobStatus)
async def profile_job_status(job_id: str) -> TikTokProfileJobStatus:
    job = await get_tiktok_profile_job(job_id)
    if not job:
        raise HTTPException(status_code=404, detail="Scraping job not found")
    return TikTokProfileJobStatus.model_validate(job)


@router.post("/profiles", response_model=TikTokProfileScrapeResponse)
async def scrape_profiles(request: TikTokProfileScrapeRequest) -> TikTokProfileScrapeResponse:
    try:
        profiles = await scrape_tiktok_profiles(request)
        if request.save_to_database:
            await persist_tiktok_profiles(profiles)
    except ScraperConfigurationError as exc:
        raise HTTPException(status_code=503, detail=str(exc)) from exc
    except InstagramScrapeError as exc:
        raise HTTPException(status_code=502, detail=str(exc)) from exc
    except Exception as exc:
        logger.exception("TikTok profile processing failed")
        raise HTTPException(status_code=500, detail="TikTok profile processing failed") from exc
    return TikTokProfileScrapeResponse(
        requested=len(request.profiles),
        scraped=len(profiles),
        saved_to_database=request.save_to_database,
        profiles=profiles,
    )
