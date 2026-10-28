from typing import Any

from fastapi import APIRouter, Depends, HTTPException, Query
from fastapi.concurrency import run_in_threadpool

from services.trends_real_estate_service.app.api.deps import get_current_user
from services.trends_real_estate_service.app.api.errors import internal_error
from services.trends_real_estate_service.app.core.config import get_settings
from services.trends_real_estate_service.app.models.brand import (
    BrandListResponse,
    BrandOverview,
    FunctionalVisualResponse,
    OfferingsResponse,
    SemioticResponse,
    ThemesResponse,
    TopContentResponse,
)
from services.trends_real_estate_service.app.services import brand_service

settings = get_settings()
router = APIRouter(prefix="/brands", tags=["Brand Intelligence"])


@router.get("", response_model=BrandListResponse)
async def list_brands(
    account_type: str | None = Query(
        "brand", pattern="^(brand|influencer|all)$",
        description="'all' includes the tracked influencers, whose posts are "
                    "enriched by the same pipeline."),
    current_user: dict[str, Any] = Depends(get_current_user),
):
    """Account selector — brands, influencers, or both, that have enriched data."""
    try:
        return await run_in_threadpool(
            brand_service.list_brands, None if account_type == "all" else account_type)
    except Exception:
        raise internal_error("list_brands") from None


@router.get("/{key}/overview", response_model=BrandOverview)
async def brand_overview(key: str, current_user: dict[str, Any] = Depends(get_current_user)):
    """Headline stats for a selected brand (across its platform accounts)."""
    try:
        result = await run_in_threadpool(brand_service.get_overview, key)
    except Exception:
        raise internal_error("brand_overview") from None
    if result is None:
        raise HTTPException(status_code=404, detail=f"No enriched data for brand '{key}'")
    return result


@router.get("/{key}/themes", response_model=ThemesResponse)
async def brand_themes(
    key: str,
    min_posts: int | None = Query(None, ge=1, description="Evidence threshold (defaults to service config)"),
    limit: int = Query(25, ge=1, le=100),
    current_user: dict[str, Any] = Depends(get_current_user),
):
    """Communication themes the brand consistently posts about, evidence-backed."""
    threshold = min_posts or settings.EVIDENCE_MIN_POSTS
    try:
        return await run_in_threadpool(brand_service.get_themes, key, threshold, limit)
    except Exception:
        raise internal_error("brand_themes") from None


@router.get("/{key}/offerings", response_model=OfferingsResponse)
async def brand_offerings(
    key: str,
    min_posts: int | None = Query(None, ge=1),
    limit: int = Query(25, ge=1, le=100),
    current_user: dict[str, Any] = Depends(get_current_user),
):
    """Most-discussed offerings for the brand, evidence-backed."""
    threshold = min_posts or settings.EVIDENCE_MIN_POSTS
    try:
        return await run_in_threadpool(brand_service.get_offerings, key, threshold, limit)
    except Exception:
        raise internal_error("brand_offerings") from None


@router.get("/{key}/top-content", response_model=TopContentResponse)
async def brand_top_content(
    key: str,
    limit: int = Query(10, ge=1, le=50),
    platform: str | None = Query(None, description="Filter to one platform, e.g. 'instagram'"),
    current_user: dict[str, Any] = Depends(get_current_user),
):
    """Top performing content for the brand by engagement."""
    try:
        return await run_in_threadpool(brand_service.get_top_content, key, limit, platform)
    except Exception:
        raise internal_error("brand_top_content") from None


@router.get("/{key}/functional-visual", response_model=FunctionalVisualResponse)
async def brand_functional_visual(key: str, current_user: dict[str, Any] = Depends(get_current_user)):
    try:
        return await run_in_threadpool(brand_service.get_functional_visual, key)
    except Exception:
        raise internal_error("brand_functional_visual") from None


@router.get("/{key}/semiotic", response_model=SemioticResponse)
async def brand_semiotic(key: str, current_user: dict[str, Any] = Depends(get_current_user)):
    try:
        return await run_in_threadpool(brand_service.get_semiotic, key)
    except Exception:
        raise internal_error("brand_semiotic") from None


@router.get("/{key}/trend-participation")
async def brand_trend_participation(
    key: str,
    limit: int = Query(8, ge=1, le=20),
    current_user: dict[str, Any] = Depends(get_current_user),
):
    """Trends this brand's own posts were assigned to in the latest run."""
    try:
        return await run_in_threadpool(brand_service.get_trend_participation, key, limit)
    except Exception:
        raise internal_error("brand_trend_participation") from None


@router.get("/{key}/trend-opportunities")
async def brand_trend_opportunities(
    key: str,
    limit: int = Query(8, ge=1, le=20),
    min_competitors: int = Query(1, ge=1, le=10),
    current_user: dict[str, Any] = Depends(get_current_user),
):
    """Trends this brand is absent from that its competitors already occupy."""
    try:
        return await run_in_threadpool(
            brand_service.get_trend_opportunities, key, limit, min_competitors)
    except Exception:
        raise internal_error("brand_trend_opportunities") from None
