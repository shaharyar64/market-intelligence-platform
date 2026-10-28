from contextlib import asynccontextmanager
import asyncio
import logging

from fastapi import FastAPI

from services.data_scraping_service.app.api.v1.health import router as health_router
from services.data_scraping_service.app.api.v1.instagram import router as instagram_router
from services.data_scraping_service.app.api.v1.instagram_posts import router as posts_router
from services.data_scraping_service.app.api.v1.twitter import router as twitter_router
from services.data_scraping_service.app.api.v1.twitter_posts import router as twitter_posts_router
from services.data_scraping_service.app.api.v1.twitter_keywords import router as twitter_keywords_router
from services.data_scraping_service.app.api.v1.tiktok import router as tiktok_router
from services.data_scraping_service.app.api.v1.tiktok_posts import router as tiktok_posts_router
from services.data_scraping_service.app.api.v1.linkedin import router as linkedin_router
from services.data_scraping_service.app.api.v1.linkedin_posts import router as linkedin_posts_router
from services.data_scraping_service.app.api.v1.schedules import router as schedules_router
from services.data_scraping_service.app.core.config import get_settings
from shared.redis import connect_redis, disconnect_redis
from services.data_scraping_service.app.services.scheduler import (
    scheduler_table_exists,
    start_scheduler,
    stop_scheduler,
)


settings = get_settings()
logger = logging.getLogger(__name__)


@asynccontextmanager
async def lifespan(_: FastAPI):
    if settings.REDIS_HOST:
        await connect_redis(settings.REDIS_HOST, settings.REDIS_PASSWORD)
    try:
        if await asyncio.to_thread(scheduler_table_exists):
            start_scheduler()
        else:
            logger.warning(
                "Scheduler disabled: apply migration 002_create_scraping_schedules.sql and restart"
            )
    except Exception:
        logger.exception("Scheduler initialization failed; continuing without scheduler")
    yield
    await stop_scheduler()
    await disconnect_redis()


app = FastAPI(
    title=settings.PROJECT_NAME,
    version="1.0.0",
    docs_url="/docs",
    lifespan=lifespan,
)
app.include_router(health_router, prefix=settings.API_V1_PREFIX)
app.include_router(instagram_router, prefix=settings.API_V1_PREFIX)
app.include_router(posts_router, prefix=settings.API_V1_PREFIX)
app.include_router(twitter_router, prefix=settings.API_V1_PREFIX)
app.include_router(twitter_posts_router, prefix=settings.API_V1_PREFIX)
app.include_router(twitter_keywords_router, prefix=settings.API_V1_PREFIX)
app.include_router(tiktok_router, prefix=settings.API_V1_PREFIX)
app.include_router(tiktok_posts_router, prefix=settings.API_V1_PREFIX)
app.include_router(linkedin_router, prefix=settings.API_V1_PREFIX)
app.include_router(linkedin_posts_router, prefix=settings.API_V1_PREFIX)
app.include_router(schedules_router, prefix=settings.API_V1_PREFIX)


@app.get("/")
async def root() -> dict[str, str]:
    return {"message": settings.PROJECT_NAME, "docs": "/docs"}
