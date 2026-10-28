from typing import List, Optional
from fastapi import APIRouter, Query
from services.horeca_service.app.services.rice_analysis import (
    fetch_rice_kpis,
    fetch_rice_price_distribution,
    fetch_top_rice_dishes,
    fetch_rice_by_cuisine,
    fetch_rice_menu_mix
)


router = APIRouter(
    prefix="/rice",
    tags=["horeca rice analysis"]
)


# -------------------------
# Helper to build filters
# -------------------------
def build_filters(
    cuisine: Optional[List[str]] = Query(None),
    horeca_type: Optional[List[str]] = Query(None),
    price_range: Optional[List[str]] = Query(None),
    min_rating: Optional[float] = Query(None),
    max_rating: Optional[float] = Query(None),
):
    return {
        "cuisine": cuisine,
        "horeca_type": horeca_type,
        "price_range": price_range,
        "rating": {
            "min": min_rating,
            "max": max_rating,
        }
    }


# -------------------------
# RICE KPI ANALYSIS
# -------------------------
@router.get("/kpis")
async def get_rice_kpis(
    cuisine: Optional[List[str]] = Query(None),
    horeca_type: Optional[List[str]] = Query(None),
    price_range: Optional[List[str]] = Query(None),
    min_rating: Optional[float] = Query(None),
    max_rating: Optional[float] = Query(None),
):
    filters = build_filters(
        cuisine, horeca_type, price_range, min_rating, max_rating
    )
    return await fetch_rice_kpis(filters)


# -------------------------
# RICE PRICE DISTRIBUTION
# -------------------------
@router.get("/price-distribution")
async def get_rice_price_distribution(
    cuisine: Optional[List[str]] = Query(None),
    horeca_type: Optional[List[str]] = Query(None),
    price_range: Optional[List[str]] = Query(None),
    min_rating: Optional[float] = Query(None),
    max_rating: Optional[float] = Query(None),
):
    filters = build_filters(
        cuisine, horeca_type, price_range, min_rating, max_rating
    )
    return await fetch_rice_price_distribution(filters)



# -------------------------
# TOP RICE DISHES
# -------------------------
@router.get("/top-dishes")
async def get_top_rice_dishes(
    cuisine: Optional[List[str]] = Query(None),
    horeca_type: Optional[List[str]] = Query(None),
    price_range: Optional[List[str]] = Query(None),
    min_rating: Optional[float] = Query(None),
    max_rating: Optional[float] = Query(None),
):
    filters = build_filters(
        cuisine, horeca_type, price_range, min_rating, max_rating
    )
    return await fetch_top_rice_dishes(filters)


# -------------------------
# RICE BY CUISINE
# -------------------------
@router.get("/by-cuisine")
async def get_rice_by_cuisine(
    cuisine: Optional[List[str]] = Query(None),
    horeca_type: Optional[List[str]] = Query(None),
    price_range: Optional[List[str]] = Query(None),
    min_rating: Optional[float] = Query(None),
    max_rating: Optional[float] = Query(None),
):
    filters = build_filters(
        cuisine, horeca_type, price_range, min_rating, max_rating
    )
    return await fetch_rice_by_cuisine(filters)



# -------------------------
# RICE MENU MIX
# -------------------------
@router.get("/menu-mix")
async def get_rice_menu_mix(
    cuisine: Optional[List[str]] = Query(None),
    horeca_type: Optional[List[str]] = Query(None),
    price_range: Optional[List[str]] = Query(None),
    min_rating: Optional[float] = Query(None),
    max_rating: Optional[float] = Query(None),
):
    filters = build_filters(
        cuisine, horeca_type, price_range, min_rating, max_rating
    )
    return await fetch_rice_menu_mix(filters)