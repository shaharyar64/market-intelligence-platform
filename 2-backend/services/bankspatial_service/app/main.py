from fastapi import FastAPI
from services.bankspatial_service.app.api.v1.health import router as health_router
from services.bankspatial_service.app.api.v1.overview import router as overview_router
from services.bankspatial_service.app.api.v1.maps import router as maps_router
from services.bankspatial_service.app.api.v1.review import router as review_router

app = FastAPI(
    title="Bank Spatial Service",
    version="1.0.0",
    docs_url="/docs",
)

app.include_router(health_router, prefix="/api/v1")
app.include_router(overview_router, prefix="/api/v1")
app.include_router(maps_router, prefix="/api/v1")
app.include_router(review_router, prefix="/api/v1")
