from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from services.real_estate_service.app.core.config import get_settings
from services.real_estate_service.app.api.v1 import (
    auth, 
    users, 
    health,
    ai_score, 
    sponsership, 
    search_data,
    reviews_data, 
    search_products,
    social_data,
    exclusive_summary,
    filters

)
from services.real_estate_service.app.utils.database import db
import logging
from contextlib import asynccontextmanager

settings = get_settings()

# Setup logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# Lifespan handler for startup/shutdown logic
@asynccontextmanager
async def lifespan(app: FastAPI):
    # Startup
    try:
        uri = db.get_uri() 
        logger.info("✅ Database connected successfully")
    except Exception as e:
        logger.error(f"❌ Failed to connect to database: {e}")
    
    yield  # The app runs while inside this block
    
    # Shutdown
    logger.info("🛑 Shutting down application...")

# FastAPI app instance
app = FastAPI(
    title=settings.PROJECT_NAME,
    description="FastAPI application with AWS Cognito authentication",
    version="1.0.0",
    docs_url="/docs",
    redoc_url="/redoc",
    lifespan=lifespan,  # 👈 New preferred pattern
)

# Middleware
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Routers
app.include_router(auth.router, prefix=settings.API_V1_PREFIX)
app.include_router(users.router, prefix=settings.API_V1_PREFIX)
app.include_router(health.router, prefix=settings.API_V1_PREFIX)
app.include_router(ai_score.router, prefix=settings.API_V1_PREFIX)
app.include_router(search_data.router, prefix=settings.API_V1_PREFIX)
app.include_router(sponsership.router, prefix=settings.API_V1_PREFIX)
app.include_router(reviews_data.router, prefix=settings.API_V1_PREFIX)
app.include_router(search_products.router, prefix=settings.API_V1_PREFIX)
app.include_router(social_data.router, prefix=settings.API_V1_PREFIX)
app.include_router(exclusive_summary.router, prefix=settings.API_V1_PREFIX)
app.include_router(filters.router, prefix=settings.API_V1_PREFIX)


# Health endpoints
@app.get("/", tags=["Health"])
async def root():
    return {"message": "Real Estate Digital Brand Health", "version": "1.0.0", "docs": "/docs"}

@app.get("/health", tags=["Health"])
async def health_check():
    return {"status": "healthy"}

# Uvicorn entrypoint
if __name__ == "__main__":
    import uvicorn
    uvicorn.run(
        "services.real_estate_service.app.main:app",
        host="0.0.0.0",
        port=8007,
        reload=settings.DEBUG,
    )
