from fastapi import FastAPI

from services.ceer_campaign_service.app.api.v1.campaign import router as campaign_router
from services.ceer_campaign_service.app.api.v1.health import router as health_router


app = FastAPI(title="CEER Campaign Service", version="1.0.0", docs_url="/docs")
app.include_router(health_router, prefix="/api/v1")
app.include_router(campaign_router, prefix="/api/v1")
