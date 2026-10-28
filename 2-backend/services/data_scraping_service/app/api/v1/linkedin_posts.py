import logging
from fastapi import APIRouter,BackgroundTasks,HTTPException,status
from services.data_scraping_service.app.models.linkedin_posts import LinkedInPostJobCreated,LinkedInPostJobStatus,LinkedInPostScrapeRequest,LinkedInPostScrapeResponse
from services.data_scraping_service.app.services.instagram import InstagramScrapeError,ScraperConfigurationError
from services.data_scraping_service.app.services.linkedin_post_jobs import create_job,get_job,run_job
from services.data_scraping_service.app.services.linkedin_posts import persist_linkedin_posts,scrape_linkedin_posts
logger=logging.getLogger(__name__);router=APIRouter(prefix="/linkedin",tags=["LinkedIn Scraping"])
@router.post("/posts/jobs",response_model=LinkedInPostJobCreated,status_code=status.HTTP_202_ACCEPTED)
async def start_job(request:LinkedInPostScrapeRequest,background_tasks:BackgroundTasks):
    job=await create_job(request);background_tasks.add_task(run_job,job["job_id"],request)
    return LinkedInPostJobCreated(job_id=job["job_id"],total=job["total"],progress_url=f"/api/v1/data-scraping/linkedin/posts/jobs/{job['job_id']}")
@router.get("/posts/jobs/{job_id}",response_model=LinkedInPostJobStatus)
async def job_status(job_id:str):
    job=await get_job(job_id)
    if not job:raise HTTPException(status_code=404,detail="Scraping job not found")
    return LinkedInPostJobStatus.model_validate(job)
@router.post("/posts",response_model=LinkedInPostScrapeResponse)
async def scrape_posts(request:LinkedInPostScrapeRequest):
    try:
        posts=await scrape_linkedin_posts(request)
        if request.save_to_database:await persist_linkedin_posts(posts)
    except ScraperConfigurationError as exc:raise HTTPException(status_code=503,detail=str(exc)) from exc
    except InstagramScrapeError as exc:raise HTTPException(status_code=502,detail=str(exc)) from exc
    except Exception as exc:
        logger.exception("LinkedIn post processing failed");raise HTTPException(status_code=500,detail="LinkedIn post processing failed") from exc
    return LinkedInPostScrapeResponse(requested_companies=len(request.target_urls),scraped_posts=len(posts),saved_to_database=request.save_to_database,posts=posts)
