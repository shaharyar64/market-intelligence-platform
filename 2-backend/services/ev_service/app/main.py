from fastapi import FastAPI
from services.ev_service.app.api.v1.health import router as health_router
from services.ev_service.app.api.v1.overview import router as overview_router
from services.ev_service.app.api.v1.trend_trajectory import router as trend_trajectory_router
from services.ev_service.app.api.v1.search_trends import router as search_trends_router
from services.ev_service.app.api.v1.cla import router as cla_router



app = FastAPI(
    title="Sales Dashboard Service",
    version="1.0.0",
    docs_url="/docs",
)


app.include_router(health_router, prefix="/api/v1")
app.include_router(overview_router, prefix="/api/v1")
app.include_router(trend_trajectory_router, prefix="/api/v1")
app.include_router(search_trends_router, prefix="/api/v1")
app.include_router(cla_router, prefix="/api/v1")