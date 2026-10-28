import logging

from fastapi import APIRouter, BackgroundTasks, HTTPException, status

from services.data_scraping_service.app.models.twitter_posts import (
    TwitterPostJobCreated,
    TwitterPostJobStatus,
    TwitterPostScrapeRequest,
    TwitterPostScrapeResponse,
)
from services.data_scraping_service.app.services.instagram import ScraperConfigurationError
from services.data_scraping_service.app.services.twitter import TwitterScrapeError
from services.data_scraping_service.app.services.twitter_post_jobs import (
    create_twitter_post_job,
    get_twitter_post_job,
    run_twitter_post_job,
)
from services.data_scraping_service.app.services.twitter_posts import (
    persist_twitter_posts,
    scrape_twitter_posts,
)


logger = logging.getLogger(__name__)
router = APIRouter(prefix="/twitter", tags=["Twitter Scraping"])


@router.post(
    "/posts/jobs",
    response_model=TwitterPostJobCreated,
    status_code=status.HTTP_202_ACCEPTED,
)
async def start_post_job(
    request: TwitterPostScrapeRequest,
    background_tasks: BackgroundTasks,
) -> TwitterPostJobCreated:
    job = await create_twitter_post_job(request)
    background_tasks.add_task(run_twitter_post_job, job["job_id"], request)
    return TwitterPostJobCreated(
        job_id=job["job_id"],
        total=job["total"],
        progress_url=f"/api/v1/data-scraping/twitter/posts/jobs/{job['job_id']}",
    )


@router.get("/posts/jobs/{job_id}", response_model=TwitterPostJobStatus)
async def post_job_status(job_id: str) -> TwitterPostJobStatus:
    job = await get_twitter_post_job(job_id)
    if not job:
        raise HTTPException(status_code=404, detail="Scraping job not found")
    return TwitterPostJobStatus.model_validate(job)


@router.post("/posts", response_model=TwitterPostScrapeResponse)
async def scrape_posts(request: TwitterPostScrapeRequest) -> TwitterPostScrapeResponse:
    try:
        posts = await scrape_twitter_posts(request)
        if request.save_to_database:
            await persist_twitter_posts(posts)
    except ScraperConfigurationError as exc:
        raise HTTPException(status_code=503, detail=str(exc)) from exc
    except TwitterScrapeError as exc:
        raise HTTPException(status_code=502, detail=str(exc)) from exc
    except Exception as exc:
        logger.exception("Twitter post processing failed")
        raise HTTPException(status_code=500, detail="Twitter post processing failed") from exc
    return TwitterPostScrapeResponse(
        requested_usernames=len(request.usernames),
        scraped_posts=len(posts),
        saved_to_database=request.save_to_database,
        posts=posts,
    )
