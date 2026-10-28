import httpx
from fastapi import FastAPI, Request, Depends
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import Response
from contextlib import asynccontextmanager
from sqlalchemy import text

from gateway.app.core.config import get_settings
from gateway.app.db.session import get_engine, get_db_conn
from gateway.app.utils.proxy import forward_request
from gateway.app.core.dependencies import get_current_user
from gateway.app.core.authorization import authorize_service_access
from shared.logger import get_logger
from shared.exceptions import register_exception_handlers
from shared.redis import connect_redis, disconnect_redis

from gateway.app.api import auth, admin

settings = get_settings()
logger = get_logger("uvicorn.error")


# =================================================
# LIFESPAN
# =================================================
@asynccontextmanager
async def lifespan(fastapi_app: FastAPI):
    engine = get_engine()

    if engine:
        try:
            async with engine.connect() as conn:
                await conn.execute(text("SELECT 1"))
            logger.info("✅ Database connection established")
        except Exception as exc:
            logger.error(f"❌ Database connection failed: {exc}")

    if settings.REDIS_HOST:
        await connect_redis(settings.REDIS_HOST, settings.REDIS_PASSWORD)

    yield

    if engine:
        await engine.dispose()
        logger.info("🛑 Database connection closed")

    await disconnect_redis()


app = FastAPI(
    title=settings.PROJECT_NAME,
    lifespan=lifespan,
)


# =================================================
# MIDDLEWARE
# =================================================
app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.cors_origins,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


# =================================================
# EXCEPTIONS
# =================================================
register_exception_handlers(app)


# =================================================
# SERVICE CONFIG
# =================================================

# 👉 URL mapping (proxy)
SERVICE_MAP = {
    "horeca": settings.HORECA_SERVICE_URL,
    "ev": settings.EV_SERVICE_URL,
    "bank-spatial": settings.BANK_SPATIAL_SERVICE_URL,
    "beer": settings.BEER_CIDER_SERVICE_URL,
    "digital-brand-health": settings.DIGITAL_BRAND_HEALTH_SERVICE_URL,
    "digital_brand_health": settings.DIGITAL_BRAND_HEALTH_SERVICE_URL,
    "digital": settings.DIGITAL_BRAND_HEALTH_SERVICE_URL,
    "data-scraping": settings.DATA_SCRAPING_SERVICE_URL,
    "data_scraping": settings.DATA_SCRAPING_SERVICE_URL,
    "scraping": settings.DATA_SCRAPING_SERVICE_URL,
    "real-estate": settings.REAL_ESTATE_SERVICE_URL,
    "real_estate": settings.REAL_ESTATE_SERVICE_URL,
    "food-intelligence": settings.FOOD_INTELLIGENCE_SERVICE_URL,
    "food_intelligence": settings.FOOD_INTELLIGENCE_SERVICE_URL,
    "saudi-real-estate": settings.SAUDI_REAL_ESTATE_SERVICE_URL,
    "saudi_real_estate": settings.SAUDI_REAL_ESTATE_SERVICE_URL,
    "trends-real-estate": settings.TRENDS_REAL_ESTATE_SERVICE_URL,
    "trends_real_estate": settings.TRENDS_REAL_ESTATE_SERVICE_URL,
    "bank-brand-health": settings.BANK_BRAND_HEALTH_SERVICE_URL,
    "bank_brand_health": settings.BANK_BRAND_HEALTH_SERVICE_URL,
    "uae-bank-brand-health": settings.UAE_BANK_BRAND_HEALTH_SERVICE_URL,
    "uae_bank_brand_health": settings.UAE_BANK_BRAND_HEALTH_SERVICE_URL,
    "ceer-campaign": settings.CEER_CAMPAIGN_SERVICE_URL,
    "ceer_campaign": settings.CEER_CAMPAIGN_SERVICE_URL,
}

# 👉 URL → DB name mapping
SERVICE_NAME_MAP = {
    "horeca": "Horeca Spatial Intelligence",
    "ev": "EV Intelligence",
    "bank-spatial": "Banking Spatial Intelligence",
    "beer": "Pricing Analysis",
    "digital-brand-health": "Digital Brand Health",
    "digital_brand_health": "Digital Brand Health",
    "digital": "Digital Brand Health",
    "data-scraping": "Data Scraping",
    "data_scraping": "Data Scraping",
    "scraping": "Data Scraping",
    "real-estate": "Real Estate Digital Brand Health",
    "real_estate": "Real Estate Digital Brand Health",
    "food-intelligence": "Food Intelligence",
    "food_intelligence": "Food Intelligence",
    "saudi-real-estate": "Saudi Real Estate Intelligence",
    "saudi_real_estate": "Saudi Real Estate Intelligence",
    "trends-real-estate": "Real Estate Trends",
    "trends_real_estate": "Real Estate Trends",
    "bank-brand-health": "Bank Brand Health",
    "bank_brand_health": "Bank Brand Health",
    "uae-bank-brand-health": "UAE Bank Brand Health",
    "uae_bank_brand_health": "UAE Bank Brand Health",
    "ceer-campaign": "CEER Campaign",
    "ceer_campaign": "CEER Campaign",
}


# =================================================
# ROUTERS
# =================================================
app.include_router(auth.router)
app.include_router(admin.router, prefix="/api/v1")


# =================================================
# ROOT & HEALTH (PUBLIC)
# =================================================
@app.get("/")
async def root():
    return {"message": "Analytics Platform Dashboards Backend", "status": "ok"}


@app.get("/health")
async def health_check():
    return {"status": "ok"}


# =================================================
# PROXY (PROTECTED)
# =================================================
@app.api_route(
    "/api/v1/{service}/{path:path}",
    methods=["GET", "POST", "PUT", "PATCH", "DELETE"],
)
async def proxy(
    service: str,
    path: str,
    request: Request,
    user: dict = Depends(get_current_user),
):
    # ❌ invalid service
    if service not in SERVICE_MAP:
        return Response(content="Unknown service", status_code=404)

    # ✅ map URL → DB service name
    service_name = SERVICE_NAME_MAP.get(service)
    if not service_name:
        return Response(content="Service mapping not found", status_code=400)

    async with get_db_conn() as conn:

        # =================================================
        # STEP 1: Get DB user using Cognito sub
        # =================================================
        user_result = await conn.execute(
            text("""
                SELECT id
                FROM users
                WHERE cognito_sub = :sub
                AND is_active = TRUE
            """),
            {"sub": user["sub"]},
        )
        user_row = user_result.fetchone()

        if not user_row:
            return Response(content="User not found", status_code=401)

        user_id = user_row.id

        # =================================================
        # STEP 2: Fetch allowed services
        # =================================================
        result = await conn.execute(
            text("""
                SELECT s.name
                FROM user_services us
                JOIN services s ON s.id = us.service_id
                WHERE us.user_id = :user_id
                AND s.is_active = TRUE
            """),
            {"user_id": user_id},
        )

        allowed_services = {row[0] for row in result.fetchall()}

    # =================================================
    # STEP 3: Authorization check
    # =================================================
    authorize_service_access(
        user=user,
        service_name=service_name,
        allowed_services=allowed_services,
    )

    # =================================================
    # STEP 4: Forward request
    # =================================================
    return await forward_request(
        service_url=SERVICE_MAP[service],
        path=f"api/v1/{path}",
        request=request,
    )


# =================================================
# HEALTH CHECK (PUBLIC)
# =================================================
@app.get("/services/health")
async def health():
    result = {}

    async with httpx.AsyncClient(timeout=3) as client:
        for service, url in SERVICE_MAP.items():
            try:
                r = await client.get(f"{url}/api/v1/health")
                result[service] = "Healthy" if r.status_code == 200 else "Unhealthy"
            except Exception as e:
                result[service] = "Unreachable"
                logger.error(f"❌ Service {service} is unreachable: {e}")

    return result
