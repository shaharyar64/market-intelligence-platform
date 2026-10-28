import os
from contextlib import asynccontextmanager
from fastapi import FastAPI
from dotenv import load_dotenv

load_dotenv()

from services.beer_cider_pricing_service.app.api.v1.beer import router as beer_router
from services.beer_cider_pricing_service.app.api.v1.health import router as health_router
from services.beer_cider_pricing_service.app.services.beer import _default_table_columns, _get_trend_date_column
from shared.redis import connect_redis, disconnect_redis
import asyncio


@asynccontextmanager
async def lifespan(fastapi_app: FastAPI):
    redis_host = os.getenv("REDIS_HOST")
    redis_password = os.getenv("REDIS_PASSWORD")
    if redis_host:
        await connect_redis(redis_host, redis_password)
    # warm schema caches so first API request doesn't pay the penalty
    await asyncio.to_thread(_default_table_columns)
    await asyncio.to_thread(_get_trend_date_column)
    yield
    await disconnect_redis()


app = FastAPI(
    title="Beer Cider Pricing Service",
    version="1.0.0",
    docs_url="/docs",
    lifespan=lifespan,
)

app.include_router(health_router, prefix="/api/v1")
app.include_router(beer_router, prefix="/api/v1")
