from fastapi import APIRouter, Query
from typing import Optional
from services.ev_service.app.services.trend_trajectory import (
    fetch_themes_quadrants,
)



router = APIRouter(
    prefix="/trend-trajectory",
    tags=["EV Trend Trajectory"]
)

@router.get("/themes/quadrants")
async def get_themes_quadrants(
    country: Optional[str] = Query(
        default="Overall",
        description="Country filter (e.g. IN, US, AE, Overall)"
    )
):
    return await fetch_themes_quadrants(country)


