from typing import List, Optional
from fastapi import APIRouter, Query

from services.horeca_service.app.services.deep_dive import (
    fetch_restaurants,
    fetch_menu,
    fetch_review_topics,
    fetch_top_rated_restaurants,
    fetch_review_kpis,
    fetch_review_sentiment_distribution,
    fetch_restaurant_names,
    fetch_restaurant_details
)

router = APIRouter(
    prefix="/deep-dive",
    tags=["horeca maps"]
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
# Restaurants
# -------------------------
@router.get("/restaurants")
async def get_restaurants(
    page: int = Query(1, ge=1),
    page_size: int = Query(25, ge=1, le=50),
    cuisine: Optional[List[str]] = Query(None),
    horeca_type: Optional[List[str]] = Query(None),
    price_range: Optional[List[str]] = Query(None),
    min_rating: Optional[float] = Query(None),
    max_rating: Optional[float] = Query(None),
):
    filters = build_filters(
        cuisine, horeca_type, price_range, min_rating, max_rating
    )
    return await fetch_restaurants(page, page_size, filters)



# -------------------------
# Menu
# -------------------------
@router.get("/menu")
async def get_menu(
    page: int = Query(1, ge=1),
    page_size: int = Query(25, ge=1, le=50),
    cuisine: Optional[List[str]] = Query(None),
    horeca_type: Optional[List[str]] = Query(None),
    price_range: Optional[List[str]] = Query(None),
    min_rating: Optional[float] = Query(None),
    max_rating: Optional[float] = Query(None),
):
    filters = build_filters(
        cuisine, horeca_type, price_range, min_rating, max_rating
    )
    return await fetch_menu(page, page_size, filters)


# -------------------------
# Review Topics
# -------------------------
@router.get("/review-topics")
async def get_review_topics(
    cuisine: Optional[List[str]] = Query(None),
    horeca_type: Optional[List[str]] = Query(None),
    price_range: Optional[List[str]] = Query(None),
    min_rating: Optional[float] = Query(None),
    max_rating: Optional[float] = Query(None),
):
    filters = build_filters(
        cuisine, horeca_type, price_range, min_rating, max_rating
    )
    return await fetch_review_topics(filters)


# -------------------------
# Top Rated Restaurants
# -------------------------
@router.get("/top-rated-restaurants")
async def get_top_rated_restaurants(
    cuisine: Optional[List[str]] = Query(None),
    horeca_type: Optional[List[str]] = Query(None),
    price_range: Optional[List[str]] = Query(None),
    min_rating: Optional[float] = Query(None),
    max_rating: Optional[float] = Query(None),
):
    filters = build_filters(
        cuisine, horeca_type, price_range, min_rating, max_rating
    )
    return await fetch_top_rated_restaurants(filters)


# -------------------------
# Review KPIs
# -------------------------
@router.get("/review-kpis")
async def get_review_kpis(
    cuisine: Optional[List[str]] = Query(None),
    horeca_type: Optional[List[str]] = Query(None),
    price_range: Optional[List[str]] = Query(None),
    min_rating: Optional[float] = Query(None),
    max_rating: Optional[float] = Query(None),
):
    filters = build_filters(
        cuisine, horeca_type, price_range, min_rating, max_rating
    )
    return await fetch_review_kpis(filters)


# -------------------------
# Review Sentiment Distribution
# -------------------------
@router.get("/review-sentiment-distribution")
async def get_review_sentiment_distribution(
    cuisine: Optional[List[str]] = Query(None),
    horeca_type: Optional[List[str]] = Query(None),
    price_range: Optional[List[str]] = Query(None),
    min_rating: Optional[float] = Query(None),
    max_rating: Optional[float] = Query(None),
):
    filters = build_filters(
        cuisine, horeca_type, price_range, min_rating, max_rating
    )
    return await fetch_review_sentiment_distribution(filters)


# -------------------------
# Restaurant Names
# -------------------------
@router.get("/restaurant-names")
async def get_restaurant_names():
    return await fetch_restaurant_names()



# -------------------------
# Restaurant Details
# -------------------------
@router.get("/restaurant-details")
async def get_restaurant_details(
    place_id: str,
    cuisine: Optional[List[str]] = Query(None),
    horeca_type: Optional[List[str]] = Query(None),
    price_range: Optional[List[str]] = Query(None),
    min_rating: Optional[float] = Query(None),
    max_rating: Optional[float] = Query(None),
):
    filters = build_filters(
        cuisine, horeca_type, price_range, min_rating, max_rating
    )
    return await fetch_restaurant_details(place_id, filters)



