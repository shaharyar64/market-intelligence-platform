from fastapi import APIRouter, Query
from typing import Optional
from services.horeca_service.app.services.maps import (
    fetch_restaurants
)

router = APIRouter(
    prefix="/maps",
    tags=["horeca maps"]
)


@router.get("/restaurants")
async def get_restaurants(
    cuisine: Optional[str] = Query(None),
    horeca_type: Optional[str] = Query(None),
    price_range: Optional[str] = Query(None),
    rating_min: Optional[float] = Query(None),
    rating_max: Optional[float] = Query(None)
):
    return await fetch_restaurants(
        cuisine,
        horeca_type,
        price_range,
        rating_min,
        rating_max
    )
