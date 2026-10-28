from datetime import date
from fastapi import APIRouter, HTTPException, Depends, Query
from services.uae_bank_brand_health.app.services.reviews_data import (
    fetch_reviews_per_bank,
    fetch_top_rated_banks,
    fetch_rated_banks,
    fetch_avg_rating_by_topic,
    fetch_avg_sentiment_by_bank,
    fetch_review_topics_distribution
)
from services.uae_bank_brand_health.app.models.reviews_data import (
    ReviewsPerBankItem,
    TopRatedBanksItem,
    RatedBanksResponse,
    AvgRatingByTopicItem,
    AvgSentimentByBankItem,
    ReviewTopicsDistributionItem

)
from services.uae_bank_brand_health.app.api.deps import get_current_user
from typing import Dict, Any, List, Optional

router = APIRouter(prefix="/reviews", tags=["Reviews Data"])

DATE_DESC = "Defaults to 2025-01-01 if not provided."
END_DATE_DESC = "Defaults to no upper bound if not provided."


@router.get("/per-bank", response_model=List[ReviewsPerBankItem])
async def get_reviews_per_bank(
    start_date: Optional[date] = Query(None, description=DATE_DESC),
    end_date: Optional[date] = Query(None, description=END_DATE_DESC),
    current_user: Dict[str, Any] = Depends(get_current_user)
):
    try:
        return await fetch_reviews_per_bank(start_date, end_date)
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/top-rated", response_model=List[TopRatedBanksItem])
async def get_top_rated_banks(
    start_date: Optional[date] = Query(None, description=DATE_DESC),
    end_date: Optional[date] = Query(None, description=END_DATE_DESC),
    current_user: Dict[str, Any] = Depends(get_current_user)
):
    try:
        return await fetch_top_rated_banks(start_date, end_date)
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/rated-banks", response_model=RatedBanksResponse)
async def get_rated_banks(
    rating: int,
    start_date: Optional[date] = Query(None, description=DATE_DESC),
    end_date: Optional[date] = Query(None, description=END_DATE_DESC),
    current_user: Dict[str, Any] = Depends(get_current_user)
):
    try:
        data = await fetch_rated_banks(rating, start_date, end_date)
        return RatedBanksResponse(items=data)
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/avg-sentiment-by-bank", response_model=List[AvgSentimentByBankItem])
async def get_avg_sentiment_by_bank(
    start_date: Optional[date] = Query(None, description=DATE_DESC),
    end_date: Optional[date] = Query(None, description=END_DATE_DESC),
    current_user: Dict[str, Any] = Depends(get_current_user)
):
    try:
        return await fetch_avg_sentiment_by_bank(start_date, end_date)
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/review-topics-distribution", response_model=List[ReviewTopicsDistributionItem])
async def get_review_topics_distribution(
    bank: Optional[str] = None,
    start_date: Optional[date] = Query(None, description=DATE_DESC),
    end_date: Optional[date] = Query(None, description=END_DATE_DESC),
    current_user: Dict[str, Any] = Depends(get_current_user)
):
    try:
        return await fetch_review_topics_distribution(bank, start_date, end_date)
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/avg-rating-by-topic", response_model=List[AvgRatingByTopicItem])
async def get_avg_rating_by_topic(
    bank: Optional[str] = None,
    start_date: Optional[date] = Query(None, description=DATE_DESC),
    end_date: Optional[date] = Query(None, description=END_DATE_DESC),
    current_user: Dict[str, Any] = Depends(get_current_user)
):
    try:
        return await fetch_avg_rating_by_topic(bank, start_date, end_date)
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))
