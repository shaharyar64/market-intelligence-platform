import logging

from fastapi import APIRouter, BackgroundTasks, HTTPException, status

from services.data_scraping_service.app.models.twitter_keywords import (
    TwitterKeywordJobCreated,
    TwitterKeywordJobStatus,
    TwitterKeywordScrapeRequest,
    TwitterKeywordScrapeResponse,
)
from services.data_scraping_service.app.services.instagram import ScraperConfigurationError
from services.data_scraping_service.app.services.twitter import TwitterScrapeError
from services.data_scraping_service.app.services.twitter_keyword_jobs import (
    create_keyword_job,
    get_keyword_job,
    run_keyword_job,
)
from services.data_scraping_service.app.services.twitter_keywords import (
    persist_keyword_posts,
    scrape_keywords,
)


logger = logging.getLogger(__name__)
router = APIRouter(prefix="/twitter", tags=["Twitter Scraping"])


@router.post(
    "/keywords/jobs",
    response_model=TwitterKeywordJobCreated,
    status_code=status.HTTP_202_ACCEPTED,
)
async def start_keyword_job(
    request: TwitterKeywordScrapeRequest,
    background_tasks: BackgroundTasks,
) -> TwitterKeywordJobCreated:
    job = await create_keyword_job(request)
    background_tasks.add_task(run_keyword_job, job["job_id"], request)
    return TwitterKeywordJobCreated(
        job_id=job["job_id"],
        total=job["total"],
        progress_url=f"/api/v1/data-scraping/twitter/keywords/jobs/{job['job_id']}",
    )


@router.get("/keywords/jobs/{job_id}", response_model=TwitterKeywordJobStatus)
async def keyword_job_status(job_id: str) -> TwitterKeywordJobStatus:
    job = await get_keyword_job(job_id)
    if not job:
        raise HTTPException(status_code=404, detail="Scraping job not found")
    return TwitterKeywordJobStatus.model_validate(job)


@router.post("/keywords", response_model=TwitterKeywordScrapeResponse)
async def scrape_keyword_posts(
    request: TwitterKeywordScrapeRequest,
) -> TwitterKeywordScrapeResponse:
    try:
        posts = await scrape_keywords(request)
        if request.save_to_database:
            await persist_keyword_posts(posts)
    except ScraperConfigurationError as exc:
        raise HTTPException(status_code=503, detail=str(exc)) from exc
    except TwitterScrapeError as exc:
        raise HTTPException(status_code=502, detail=str(exc)) from exc
    except Exception as exc:
        logger.exception("Twitter keyword processing failed")
        raise HTTPException(status_code=500, detail="Twitter keyword processing failed") from exc
    return TwitterKeywordScrapeResponse(
        requested_keywords=len(request.keywords),
        scraped_posts=len(posts),
        saved_to_database=request.save_to_database,
        posts=posts,
    )
