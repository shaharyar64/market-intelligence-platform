from fastapi import FastAPI
from services.horeca_service.app.api.v1.overview import router as overview_router
from services.horeca_service.app.api.v1.health import router as health_router
from services.horeca_service.app.api.v1.maps import router as maps_router
from services.horeca_service.app.api.v1.deep_dive import router as deep_router
from services.horeca_service.app.api.v1.rice_analysis import router as rice_router

app = FastAPI(
    title="Sales Dashboard Service",
    version="1.0.0",
    docs_url="/docs",
)

app.include_router(health_router, prefix="/api/v1")
app.include_router(overview_router, prefix="/api/v1")
app.include_router(maps_router, prefix="/api/v1")
app.include_router(deep_router, prefix="/api/v1")
app.include_router(rice_router, prefix="/api/v1")
