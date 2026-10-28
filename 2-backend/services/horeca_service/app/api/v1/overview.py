from typing import List, Optional
from fastapi import APIRouter, Query

from services.horeca_service.app.services.overview import (
    fetch_kpis,
    fetch_horeca_split,
    fetch_rating_distribution,
    fetch_popular_times,
    fetch_filters
)

router = APIRouter(
    prefix="/overview",
    tags=["horeca overview"]
)


def build_filters(
    cuisine: Optional[List[str]] = None,
    horeca_type: Optional[List[str]] = None,
    price_range: Optional[List[str]] = None,
    min_rating: Optional[float] = None,
    max_rating: Optional[float] = None,
):
    return {
        "cuisine": cuisine,
        "horeca_type": horeca_type,
        "price_range": price_range,
        "rating": {
            "min": min_rating,
            "max": max_rating
        }
    }


@router.get("/health")
async def health():
    return {"status": "ok"}


@router.get("/kpis")
async def get_kpis(
    cuisine: Optional[List[str]] = Query(None),
    horeca_type: Optional[List[str]] = Query(None),
    price_range: Optional[List[str]] = Query(None),
    min_rating: Optional[float] = Query(None),
    max_rating: Optional[float] = Query(None),
):
    filters = build_filters(cuisine, horeca_type, price_range, min_rating, max_rating)
    return await fetch_kpis(filters)


@router.get("/horeca-split")
async def get_horeca_split(
    cuisine: Optional[List[str]] = Query(None),
    horeca_type: Optional[List[str]] = Query(None),
    price_range: Optional[List[str]] = Query(None),
    min_rating: Optional[float] = Query(None),
    max_rating: Optional[float] = Query(None),
):
    filters = build_filters(cuisine, horeca_type, price_range, min_rating, max_rating)
    return await fetch_horeca_split(filters)


@router.get("/rating-distribution")
async def get_rating_distribution(
    cuisine: Optional[List[str]] = Query(None),
    horeca_type: Optional[List[str]] = Query(None),
    price_range: Optional[List[str]] = Query(None),
    min_rating: Optional[float] = Query(None),
    max_rating: Optional[float] = Query(None),
):
    filters = build_filters(cuisine, horeca_type, price_range, min_rating, max_rating)
    return await fetch_rating_distribution(filters)


# -------------------------
# Popular Times
# -------------------------
@router.get("/popular-times")
async def get_popular_times(
    cuisine: Optional[List[str]] = Query(None),
    horeca_type: Optional[List[str]] = Query(None),
    price_range: Optional[List[str]] = Query(None),
    min_rating: Optional[float] = Query(None),
    max_rating: Optional[float] = Query(None),
):
    filters = build_filters(
        cuisine, horeca_type, price_range, min_rating, max_rating
    )
    return await fetch_popular_times(filters)



@router.get("/filters")
async def get_restaurant_filters():
    return await fetch_filters()
