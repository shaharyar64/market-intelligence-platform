import logging
from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from services.trends_real_estate_service.app.api.v1 import (
    assistant,
    brands,
    health,
    idea_testing,
    knowledge,
    personas,
    trends,
    visual,
)
from services.trends_real_estate_service.app.assistant import session
from services.trends_real_estate_service.app.core.config import get_settings
from services.trends_real_estate_service.app.db import store

settings = get_settings()
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


@asynccontextmanager
async def lifespan(app: FastAPI):
    try:
        store.run_query("SELECT 1")
        logger.info("Postgres (realestate_intel) reachable")
    except Exception as e:
        logger.warning(f"Postgres not reachable at startup, read endpoints will error until it is: {e}")
    try:
        # The conversations table and its (user_sub, updated_at DESC) index. The
        # port dropped this call, so the table survives only because a migration
        # cloned it once - a fresh schema would start with no chat history at
        # all, and the sidebar swallows the resulting failure into an empty list.
        session.ensure_table()
    except Exception as e:
        logger.warning(f"assistant_conversations could not be ensured: {e}")
    yield
    logger.info("Shutting down Real Estate Intelligence service")


app = FastAPI(
    title=settings.PROJECT_NAME,
    description="Real Estate Intelligence — brand, influencer and community post intelligence",
    version="1.0.0",
    # The container publishes 8010 on the host, so these are reachable without
    # going through the gateway and without a token. The full schema of an
    # internal service is not something to hand out in production.
    docs_url=None if settings.is_production else "/docs",
    redoc_url=None if settings.is_production else "/redoc",
    openapi_url=None if settings.is_production else "/openapi.json",
    lifespan=lifespan,
)

app.add_middleware(
    CORSMiddleware,
    # The gateway is the front door and allows only these origins. Mirroring it
    # here matters because the container publishes 8010 on the host, so this
    # app is directly reachable - "*" with credentials made every browser on
    # that network a valid caller.
    allow_origins=settings.cors_allow_origins,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Mounted so the gateway's /api/v1/trends-real-estate/{path} maps to
# /api/v1/{path} here.
app.include_router(health.router, prefix=settings.API_V1_PREFIX)
app.include_router(brands.router, prefix=settings.API_V1_PREFIX)
app.include_router(visual.router, prefix=settings.API_V1_PREFIX)
app.include_router(trends.router, prefix=settings.API_V1_PREFIX)
app.include_router(assistant.router, prefix=settings.API_V1_PREFIX)
app.include_router(personas.router, prefix=settings.API_V1_PREFIX)
app.include_router(idea_testing.router, prefix=settings.API_V1_PREFIX)
app.include_router(knowledge.router, prefix=settings.API_V1_PREFIX)


@app.get("/")
async def root():
    return {"service": "trends_real_estate", "status": "ok"}
