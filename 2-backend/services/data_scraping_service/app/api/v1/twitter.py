import logging

from fastapi import APIRouter, BackgroundTasks, HTTPException, status

from services.data_scraping_service.app.models.twitter import (
    TwitterProfileJobCreated,
    TwitterProfileJobStatus,
    TwitterProfileScrapeRequest,
    TwitterProfileScrapeResponse,
)
from services.data_scraping_service.app.services.instagram import ScraperConfigurationError
from services.data_scraping_service.app.services.twitter import (
    TwitterScrapeError,
    persist_twitter_profiles,
    scrape_twitter_profiles,
)
from services.data_scraping_service.app.services.twitter_jobs import (
    create_twitter_profile_job,
    get_twitter_profile_job,
    run_twitter_profile_job,
)


logger = logging.getLogger(__name__)
router = APIRouter(prefix="/twitter", tags=["Twitter Scraping"])


@router.post(
    "/profiles/jobs",
    response_model=TwitterProfileJobCreated,
    status_code=status.HTTP_202_ACCEPTED,
)
async def start_profile_job(
    request: TwitterProfileScrapeRequest,
    background_tasks: BackgroundTasks,
) -> TwitterProfileJobCreated:
    job = await create_twitter_profile_job(request)
    background_tasks.add_task(run_twitter_profile_job, job["job_id"], request)
    return TwitterProfileJobCreated(
        job_id=job["job_id"],
        total=job["total"],
        progress_url=f"/api/v1/data-scraping/twitter/profiles/jobs/{job['job_id']}",
    )


@router.get("/profiles/jobs/{job_id}", response_model=TwitterProfileJobStatus)
async def profile_job_status(job_id: str) -> TwitterProfileJobStatus:
    job = await get_twitter_profile_job(job_id)
    if not job:
        raise HTTPException(status_code=404, detail="Scraping job not found")
    return TwitterProfileJobStatus.model_validate(job)


@router.post("/profiles", response_model=TwitterProfileScrapeResponse)
async def scrape_profiles(request: TwitterProfileScrapeRequest) -> TwitterProfileScrapeResponse:
    try:
        profiles = await scrape_twitter_profiles(request)
        if request.save_to_database:
            await persist_twitter_profiles(profiles)
    except ScraperConfigurationError as exc:
        raise HTTPException(status_code=503, detail=str(exc)) from exc
    except TwitterScrapeError as exc:
        raise HTTPException(status_code=502, detail=str(exc)) from exc
    except Exception as exc:
        logger.exception("Twitter profile processing failed")
        raise HTTPException(status_code=500, detail="Twitter profile processing failed") from exc

    return TwitterProfileScrapeResponse(
        requested=len(request.usernames),
        scraped=len(profiles),
        saved_to_database=request.save_to_database,
        profiles=profiles,
    )
