import asyncio, json
from uuid import uuid4
from services.data_scraping_service.app.core.config import get_settings
from services.data_scraping_service.app.services.linkedin_posts import persist_linkedin_posts, scrape_posts_for_company
from shared.redis import ensure_redis

_jobs, _lock, _PREFIX = {}, asyncio.Lock(), "data-scraping:linkedin-post-job:"
async def _save(job):
    async with _lock: _jobs[job["job_id"]] = job
    redis = await ensure_redis()
    if redis: await redis.set(f"{_PREFIX}{job['job_id']}", json.dumps(job), ex=get_settings().SCRAPING_JOB_TTL_SECONDS)
async def create_job(request):
    job={"job_id":str(uuid4()),"status":"queued","total":len(request.target_urls),"completed":0,"successful":0,"failed":0,"progress_percent":0.0,"current_target_url":None,"scraped_posts":0,"saved_to_database":request.save_to_database,"posts":[],"errors":[]}
    await _save(job); return job
async def get_job(job_id):
    redis=await ensure_redis()
    if redis:
        raw=await redis.get(f"{_PREFIX}{job_id}")
        if raw:return json.loads(raw)
    async with _lock:return _jobs.get(job_id)
async def run_job(job_id,request):
    job=await get_job(job_id)
    if not job:return
    job["status"]="running";await _save(job)
    for url in request.target_urls:
        job["current_target_url"]=url;await _save(job)
        try:
            posts=await scrape_posts_for_company(url,request)
            if request.save_to_database:await persist_linkedin_posts(posts)
            job["posts"].extend(json.loads(p.model_dump_json()) for p in posts);job["scraped_posts"]+=len(posts);job["successful"]+=1
        except Exception as exc:
            job["failed"]+=1;job["errors"].append({"target_url":url,"message":str(exc)})
        finally:
            job["completed"]+=1;job["progress_percent"]=round(job["completed"]/job["total"]*100,2);await _save(job)
    job["current_target_url"]=None;job["status"]="completed_with_errors" if job["failed"] else "completed";await _save(job)
