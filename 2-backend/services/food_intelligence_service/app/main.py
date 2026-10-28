import logging
from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from services.food_intelligence_service.app.core.config import get_settings
from services.food_intelligence_service.app.api.v1 import health, brands, visual, trends, assistant
from services.food_intelligence_service.app.api.v1 import personas, idea_testing, knowledge
from services.food_intelligence_service.app.db import analysis_store

settings = get_settings()
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


@asynccontextmanager
async def lifespan(app: FastAPI):
    try:
        analysis_store.run_query("SELECT 1")
        logger.info("Postgres (food_intel) reachable")
    except Exception as e:
        logger.warning(f"Postgres not reachable at startup, read endpoints will error until it is: {e}")
    try:
        from services.food_intelligence_service.app.assistant import session
        session.ensure_table()
    except Exception as e:
        logger.warning(f"assistant_conversations table not ready, chat history will not persist: {e}")
    yield
    logger.info("Shutting down Food Intelligence service")


app = FastAPI(
    title=settings.PROJECT_NAME,
    description="Food Intelligence — Brand Intelligence over enriched social posts",
    version="1.0.0",
    docs_url="/docs",
    redoc_url="/redoc",
    lifespan=lifespan,
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Mounted so the gateway's /api/v1/food-intelligence/{path} maps to /api/v1/{path} here.
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
    return {"service": "food_intelligence", "status": "ok"}
