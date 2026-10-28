from datetime import date
from fastapi import APIRouter, HTTPException, Depends, Query
from typing import Dict, Any, List, Optional
from services.saudi_real_estate_service.app.api.deps import get_current_user

from services.saudi_real_estate_service.app.services.social_data import (
    fetch_social_overview,
    fetch_post_distribution,
    fetch_post_volume_last6months,
    fetch_volume_trend,
    fetch_engagement_trend,
    fetch_bank_volume_growth,
    fetch_bank_followers,
    fetch_banks_and_platforms,
    fetch_avg_sentiment_by_topic,
    fetch_avg_sentiment_by_bank,
    fetch_top_topics_by_sentiment,
    fetch_top_banks_by_sentiment,
    fetch_top_5_associations,
    fetch_association_distribution,
    fetch_top_5_associations_over_time
)

from services.saudi_real_estate_service.app.models.social_data import (
    SocialOverviewResponse,
    PostDistributionResponse,
    PostVolumeLast6MonthsResponse,
    VolumeTrendResponse,
    EngagementTrendResponse,
    BankVolumeGrowthResponse,
    BankFollowersResponse,
    BankPlatformFiltersResponse,
    AvgSentimentTopicResponse,
    AvgSentimentBankResponse,
    TopTopicsResponse,
    TopBanksResponse,
    TopAssociationsResponse,
    AssociationsDistributionResponse,
    AssociationsTrendResponse
)

router = APIRouter(prefix="/social-data", tags=["Social Data"])

SD_DATE_DESC = "Defaults to 2025-01-01 if not provided."
SD_END_DATE_DESC = "Defaults to no upper bound if not provided."


# ✅ 0. SOCIAL OVERVIEW
@router.get("/overview", response_model=SocialOverviewResponse)
async def social_overview(
    bank: Optional[str] = None,
    platform: Optional[str] = None,
    start_date: Optional[date] = Query(None, description=SD_DATE_DESC),
    end_date: Optional[date] = Query(None, description=SD_END_DATE_DESC),
    current_user: Dict[str, Any] = Depends(get_current_user)
):
    try:
        data = await fetch_social_overview(bank, platform, start_date, end_date)
        return data
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


# ✅ 1. Posts Distribution (Pie Chart)
@router.get("/posts-distribution", response_model=PostDistributionResponse)
async def posts_distribution(
    bank: Optional[str] = None,
    platform: Optional[str] = None,
    start_date: Optional[date] = Query(None, description=SD_DATE_DESC),
    end_date: Optional[date] = Query(None, description=SD_END_DATE_DESC),
    current_user: Dict[str, Any] = Depends(get_current_user)
):
    try:
        data = await fetch_post_distribution(bank, platform, start_date, end_date)
        return {"distribution": data}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))



# ✅ 2. Volume of posts — Last 6 months (Bar Chart)
@router.get("/posts-volume-last6months", response_model=PostVolumeLast6MonthsResponse)
async def posts_volume_last6(
    bank: Optional[str] = None,
    platform: Optional[str] = None,
    current_user: Dict[str, Any] = Depends(get_current_user)
):
    try:
        data = await fetch_post_volume_last6months(bank, platform)
        return {"data": data}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


# ✅ 3. Volume Trend Over Time (Line Chart)
@router.get("/volume-trend", response_model=VolumeTrendResponse)
async def volume_trend(
    frequency: str = Query("1m", enum=["1m", "3m", "6m", "1y"]),
    bank: Optional[str] = None,
    platform: Optional[str] = None,
    start_date: Optional[date] = Query(None, description=SD_DATE_DESC),
    end_date: Optional[date] = Query(None, description=SD_END_DATE_DESC),
    current_user: Dict[str, Any] = Depends(get_current_user)
):
    try:
        data = await fetch_volume_trend(frequency, bank, platform, start_date, end_date)
        return {"trend": data}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


# ✅ 4. Engagement Trend Over Time (Line Chart)
@router.get("/engagement-trend", response_model=EngagementTrendResponse)
async def engagement_trend(
    frequency: str = Query("1m", enum=["1m", "3m", "6m", "1y"]),
    bank: Optional[str] = None,
    platform: Optional[str] = None,
    start_date: Optional[date] = Query(None, description=SD_DATE_DESC),
    end_date: Optional[date] = Query(None, description=SD_END_DATE_DESC),
    current_user: Dict[str, Any] = Depends(get_current_user)
):
    try:
        data = await fetch_engagement_trend(frequency, bank, platform, start_date, end_date)
        return {"trend": data}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


# ✅ 4b. Bank Volume Growth ("Fastest Growing" KPI card)
@router.get("/top-growing", response_model=BankVolumeGrowthResponse)
async def bank_volume_growth(
    platform: Optional[str] = None,
    bank: Optional[List[str]] = Query(None, description="Up to 5 bank names. When provided, returns exactly these banks (ignores `limit`)."),
    limit: Optional[int] = Query(None, ge=1, description="Max rows to return, ordered by growth desc. Omit (and omit `bank`) to return every bank, including negative growers."),
    start_date: Optional[date] = Query(None, description=SD_DATE_DESC),
    end_date: Optional[date] = Query(None, description=SD_END_DATE_DESC),
    current_user: Dict[str, Any] = Depends(get_current_user)
):
    if bank and len(bank) > 5:
        raise HTTPException(status_code=400, detail="You can specify at most 5 banks.")
    try:
        data = await fetch_bank_volume_growth(start_date, end_date, platform, bank, limit)
        return {"data": data}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


# ✅ 5. Bank Followers (Bar Chart)
@router.get("/bank-followers", response_model=BankFollowersResponse)
async def bank_followers(
    platform: Optional[str] = None,
    start_date: Optional[date] = Query(None, description=SD_DATE_DESC),
    end_date: Optional[date] = Query(None, description=SD_END_DATE_DESC),
    current_user: Dict[str, Any] = Depends(get_current_user)
):
    try:
        data = await fetch_bank_followers(platform, start_date, end_date)
        return {"followers": data}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))



@router.get("/filters", response_model=BankPlatformFiltersResponse)
async def get_banks_and_platforms(
    current_user: Dict[str, Any] = Depends(get_current_user)
):
    try:
        data = await fetch_banks_and_platforms()
        return {"data": data}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))



# Sentiment Analysis APIs


# ✅ Average Sentiment by Topic
@router.get("/sentiment/avg-by-topic", response_model=AvgSentimentTopicResponse)
async def avg_by_topic(
    bank: Optional[str] = None,
    start_date: Optional[date] = Query(None, description=SD_DATE_DESC),
    end_date: Optional[date] = Query(None, description=SD_END_DATE_DESC),
    current_user: Dict[str, Any] = Depends(get_current_user)
):
    try:
        return {"data": await fetch_avg_sentiment_by_topic(start_date, end_date, bank)}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

# ✅ Average Sentiment by Bank
@router.get("/sentiment/avg-by-bank", response_model=AvgSentimentBankResponse)
async def avg_by_bank(
    bank: Optional[str] = None,
    start_date: Optional[date] = Query(None, description=SD_DATE_DESC),
    end_date: Optional[date] = Query(None, description=SD_END_DATE_DESC),
    current_user: Dict[str, Any] = Depends(get_current_user)
):
    try:
        return {"data": await fetch_avg_sentiment_by_bank(start_date, end_date, bank)}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

# ✅ Top Topics by Sentiment
@router.get("/sentiment/top-topics", response_model=TopTopicsResponse)
async def top_topics(
    limit: int = 10,
    bank: Optional[str] = None,
    start_date: Optional[date] = Query(None, description=SD_DATE_DESC),
    end_date: Optional[date] = Query(None, description=SD_END_DATE_DESC),
    current_user: Dict[str, Any] = Depends(get_current_user)
):
    try:
        return {"data": await fetch_top_topics_by_sentiment(limit, start_date, end_date, bank)}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

# ✅ Top Banks by Sentiment
@router.get("/sentiment/top-banks", response_model=TopBanksResponse)
async def top_banks(
    limit: int = 10,
    bank: Optional[str] = None,
    start_date: Optional[date] = Query(None, description=SD_DATE_DESC),
    end_date: Optional[date] = Query(None, description=SD_END_DATE_DESC),
    current_user: Dict[str, Any] = Depends(get_current_user)
):
    try:
        return {"data": await fetch_top_banks_by_sentiment(limit, start_date, end_date, bank)}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))



# Associations


ASSOC_DATE_DESC = "Defaults to 2025-01-01 if not provided."
ASSOC_END_DATE_DESC = "Defaults to no upper bound if not provided."
ASSOCIATIONS_DESC = "Up to 5 association names. Defaults to top 5 associations if not provided."


# ✅ Top 5 Associations
@router.get("/associations/top5", response_model=TopAssociationsResponse)
async def top_5_associations(
    platform: str = None,
    bank: Optional[str] = None,
    start_date: Optional[date] = Query(None, description=ASSOC_DATE_DESC),
    end_date: Optional[date] = Query(None, description=ASSOC_END_DATE_DESC),
    associations: Optional[List[str]] = Query(None, description=ASSOCIATIONS_DESC),
    current_user: Dict[str, Any] = Depends(get_current_user)
):
    if associations and len(associations) > 5:
        raise HTTPException(status_code=400, detail="You can specify at most 5 associations.")
    try:
        data = await fetch_top_5_associations(platform, start_date, end_date, associations, bank)
        return {"data": data}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


# ✅ Associations Distribution
@router.get("/associations/distribution", response_model=AssociationsDistributionResponse)
async def associations_distribution(
    platform: str = None,
    bank: Optional[str] = None,
    start_date: Optional[date] = Query(None, description=ASSOC_DATE_DESC),
    end_date: Optional[date] = Query(None, description=ASSOC_END_DATE_DESC),
    associations: Optional[List[str]] = Query(None, description=ASSOCIATIONS_DESC),
    current_user: Dict[str, Any] = Depends(get_current_user)
):
    if associations and len(associations) > 5:
        raise HTTPException(status_code=400, detail="You can specify at most 5 associations.")
    try:
        data = await fetch_association_distribution(platform, start_date, end_date, associations, bank)
        return {"data": data}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

# ✅ Associations Over Time
@router.get("/associations/top5-over-time", response_model=AssociationsTrendResponse)
async def associations_over_time(
    platform: str = None,
    bank: Optional[str] = None,
    frequency: str = "1m",  # 1m, 3m, 6m, 1y
    start_date: Optional[date] = Query(None, description=ASSOC_DATE_DESC),
    end_date: Optional[date] = Query(None, description=ASSOC_END_DATE_DESC),
    associations: Optional[List[str]] = Query(None, description=ASSOCIATIONS_DESC),
    current_user: Dict[str, Any] = Depends(get_current_user)
):
    if associations and len(associations) > 5:
        raise HTTPException(status_code=400, detail="You can specify at most 5 associations.")
    try:
        data = await fetch_top_5_associations_over_time(platform, frequency, start_date, end_date, associations, bank)
        return {"data": data}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))