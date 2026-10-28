from fastapi import APIRouter, HTTPException, Depends, Query
from services.saudi_real_estate_service.app.services.reviews_data import (
    fetch_reviews_per_bank, 
    fetch_top_rated_banks, 
    fetch_rated_banks,
    fetch_avg_rating_by_topic,
    fetch_avg_sentiment_by_bank,
    fetch_review_topics_distribution
)
from services.saudi_real_estate_service.app.models.reviews_data import (
    ReviewsPerBankItem,
    TopRatedBanksItem,
    RatedBanksResponse,
    AvgRatingByTopicItem,
    AvgSentimentByBankItem,
    ReviewTopicsDistributionItem

)
from services.saudi_real_estate_service.app.api.deps import get_current_user
from typing import Dict, Any, List, Optional

router = APIRouter(prefix="/reviews", tags=["Reviews Data"])

REGION_DESC = "Filter to developers operating in this region (see /filters/regions). Omit for all developers."


@router.get("/per-bank", response_model=List[ReviewsPerBankItem])
async def get_reviews_per_bank(
    region: Optional[str] = Query(default=None, description=REGION_DESC),
    current_user: Dict[str, Any] = Depends(get_current_user)
):
    try:
        return await fetch_reviews_per_bank(region)
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/top-rated", response_model=List[TopRatedBanksItem])
async def get_top_rated_banks(
    region: Optional[str] = Query(default=None, description=REGION_DESC),
    current_user: Dict[str, Any] = Depends(get_current_user)
):
    try:
        return await fetch_top_rated_banks(region)
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/rated-banks", response_model=RatedBanksResponse)
async def get_rated_banks(
    rating: int,
    region: Optional[str] = Query(default=None, description=REGION_DESC),
    current_user: Dict[str, Any] = Depends(get_current_user)
):
    try:
        data = await fetch_rated_banks(rating, region)
        return RatedBanksResponse(items=data)
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/avg-sentiment-by-bank", response_model=List[AvgSentimentByBankItem])
async def get_avg_sentiment_by_bank(
    region: Optional[str] = Query(default=None, description=REGION_DESC),
    current_user: Dict[str, Any] = Depends(get_current_user)
):
    try:
        return await fetch_avg_sentiment_by_bank(region)
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/review-topics-distribution", response_model=List[ReviewTopicsDistributionItem])
async def get_review_topics_distribution(
    bank: Optional[str] = None,
    current_user: Dict[str, Any] = Depends(get_current_user)
):
    try:
        return await fetch_review_topics_distribution(bank)
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/avg-rating-by-topic", response_model=List[AvgRatingByTopicItem])
async def get_avg_rating_by_topic(
    bank: Optional[str] = None,
    current_user: Dict[str, Any] = Depends(get_current_user)
):
    try:
        return await fetch_avg_rating_by_topic(bank)
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))