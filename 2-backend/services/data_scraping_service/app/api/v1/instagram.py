import logging

from fastapi import APIRouter, BackgroundTasks, HTTPException, status

from services.data_scraping_service.app.models.instagram import (
    InstagramProfileScrapeRequest,
    InstagramProfileScrapeResponse,
    InstagramProfileJobCreated,
    InstagramProfileJobStatus,
)
from services.data_scraping_service.app.services.profile_jobs import (
    create_profile_job,
    get_profile_job,
    run_profile_job,
)
from services.data_scraping_service.app.services.instagram import (
    InstagramScrapeError,
    ScraperConfigurationError,
    persist_profiles,
    scrape_instagram_profiles,
)


logger = logging.getLogger(__name__)
router = APIRouter(prefix="/instagram", tags=["Instagram Scraping"])


@router.post(
    "/profiles/jobs",
    response_model=InstagramProfileJobCreated,
    status_code=status.HTTP_202_ACCEPTED,
)
async def start_profile_job(
    request: InstagramProfileScrapeRequest,
    background_tasks: BackgroundTasks,
) -> InstagramProfileJobCreated:
    job = await create_profile_job(request)
    background_tasks.add_task(run_profile_job, job["job_id"], request)
    return InstagramProfileJobCreated(
        job_id=job["job_id"],
        total=job["total"],
        progress_url=f"/api/v1/data-scraping/instagram/profiles/jobs/{job['job_id']}",
    )


@router.get("/profiles/jobs/{job_id}", response_model=InstagramProfileJobStatus)
async def profile_job_status(job_id: str) -> InstagramProfileJobStatus:
    job = await get_profile_job(job_id)
    if not job:
        raise HTTPException(status_code=404, detail="Scraping job not found")
    return InstagramProfileJobStatus.model_validate(job)


@router.post(
    "/profiles",
    response_model=InstagramProfileScrapeResponse,
    status_code=status.HTTP_200_OK,
)
async def scrape_profiles(
    request: InstagramProfileScrapeRequest,
) -> InstagramProfileScrapeResponse:
    try:
        profiles = await scrape_instagram_profiles(request)
        if request.save_to_database:
            await persist_profiles(profiles)
    except ScraperConfigurationError as exc:
        raise HTTPException(status_code=503, detail=str(exc)) from exc
    except InstagramScrapeError as exc:
        raise HTTPException(status_code=502, detail=str(exc)) from exc
    except Exception as exc:
        logger.exception("Instagram profile persistence failed")
        raise HTTPException(
            status_code=500,
            detail="Profiles were scraped but could not be saved",
        ) from exc

    return InstagramProfileScrapeResponse(
        requested=len(request.usernames),
        scraped=len(profiles),
        saved_to_database=request.save_to_database,
        profiles=profiles,
    )
