import logging
from fastapi import APIRouter, BackgroundTasks, HTTPException, status

from services.data_scraping_service.app.models.linkedin import LinkedInProfileJobCreated, LinkedInProfileJobStatus, LinkedInProfileScrapeRequest, LinkedInProfileScrapeResponse
from services.data_scraping_service.app.services.instagram import InstagramScrapeError, ScraperConfigurationError
from services.data_scraping_service.app.services.linkedin import persist_linkedin_profiles, scrape_linkedin_profiles
from services.data_scraping_service.app.services.linkedin_jobs import create_linkedin_job, get_linkedin_job, run_linkedin_job

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/linkedin", tags=["LinkedIn Scraping"])

@router.post("/profiles/jobs", response_model=LinkedInProfileJobCreated, status_code=status.HTTP_202_ACCEPTED)
async def start_job(request: LinkedInProfileScrapeRequest, background_tasks: BackgroundTasks):
    job = await create_linkedin_job(request)
    background_tasks.add_task(run_linkedin_job, job["job_id"], request)
    return LinkedInProfileJobCreated(job_id=job["job_id"], total=job["total"], progress_url=f"/api/v1/data-scraping/linkedin/profiles/jobs/{job['job_id']}")

@router.get("/profiles/jobs/{job_id}", response_model=LinkedInProfileJobStatus)
async def job_status(job_id: str):
    job = await get_linkedin_job(job_id)
    if not job:
        raise HTTPException(status_code=404, detail="Scraping job not found")
    return LinkedInProfileJobStatus.model_validate(job)

@router.post("/profiles", response_model=LinkedInProfileScrapeResponse)
async def scrape_profiles(request: LinkedInProfileScrapeRequest):
    try:
        profiles = await scrape_linkedin_profiles(request)
        if request.save_to_database:
            await persist_linkedin_profiles(profiles)
    except ScraperConfigurationError as exc:
        raise HTTPException(status_code=503, detail=str(exc)) from exc
    except InstagramScrapeError as exc:
        raise HTTPException(status_code=502, detail=str(exc)) from exc
    except Exception as exc:
        logger.exception("LinkedIn profile processing failed")
        raise HTTPException(status_code=500, detail="LinkedIn profile processing failed") from exc
    return LinkedInProfileScrapeResponse(requested=len(request.profile_urls), scraped=len(profiles), saved_to_database=request.save_to_database, profiles=profiles)
