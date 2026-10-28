from typing import Any, Dict, Optional

from fastapi import APIRouter, Depends, HTTPException, Query
from fastapi.concurrency import run_in_threadpool

from services.food_intelligence_service.app.api.deps import get_current_user
from services.food_intelligence_service.app.core.config import get_settings
from services.food_intelligence_service.app.services import brand_service
from services.food_intelligence_service.app.models.brand import (
    BrandListResponse,
    BrandOverview,
    ThemesResponse,
    ProductsResponse,
    TopContentResponse,
    FunctionalVisualResponse,
    SemioticResponse,
)

settings = get_settings()
router = APIRouter(prefix="/brands", tags=["Brand Intelligence"])


@router.get("", response_model=BrandListResponse)
async def list_brands(
    account_type: Optional[str] = Query(
        "brand", pattern="^(brand|influencer|all)$",
        description="'all' includes the tracked influencers, whose posts are "
                    "enriched by the same pipeline."),
    current_user: Dict[str, Any] = Depends(get_current_user),
):
    """Account selector — brands, influencers, or both, that have enriched data."""
    try:
        return await run_in_threadpool(
            brand_service.list_brands, None if account_type == "all" else account_type)
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/{key}/overview", response_model=BrandOverview)
async def brand_overview(key: str, current_user: Dict[str, Any] = Depends(get_current_user)):
    """Headline stats for a selected brand (across its platform accounts)."""
    try:
        result = await run_in_threadpool(brand_service.get_overview, key)
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))
    if result is None:
        raise HTTPException(status_code=404, detail=f"No enriched data for brand '{key}'")
    return result


@router.get("/{key}/themes", response_model=ThemesResponse)
async def brand_themes(
    key: str,
    min_posts: Optional[int] = Query(None, ge=1, description="Evidence threshold (defaults to service config)"),
    limit: int = Query(25, ge=1, le=100),
    current_user: Dict[str, Any] = Depends(get_current_user),
):
    """Communication themes the brand consistently posts about, evidence-backed."""
    threshold = min_posts or settings.EVIDENCE_MIN_POSTS
    try:
        return await run_in_threadpool(brand_service.get_themes, key, threshold, limit)
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/{key}/products", response_model=ProductsResponse)
async def brand_products(
    key: str,
    min_posts: Optional[int] = Query(None, ge=1),
    limit: int = Query(25, ge=1, le=100),
    current_user: Dict[str, Any] = Depends(get_current_user),
):
    """Most-discussed products for the brand, evidence-backed."""
    threshold = min_posts or settings.EVIDENCE_MIN_POSTS
    try:
        return await run_in_threadpool(brand_service.get_products, key, threshold, limit)
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/{key}/top-content", response_model=TopContentResponse)
async def brand_top_content(
    key: str,
    limit: int = Query(10, ge=1, le=50),
    platform: Optional[str] = Query(None, description="Filter to one platform, e.g. 'instagram'"),
    current_user: Dict[str, Any] = Depends(get_current_user),
):
    """Top performing content for the brand by engagement."""
    try:
        return await run_in_threadpool(brand_service.get_top_content, key, limit, platform)
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/{key}/functional-visual", response_model=FunctionalVisualResponse)
async def brand_functional_visual(key: str, current_user: Dict[str, Any] = Depends(get_current_user)):
    try:
        return await run_in_threadpool(brand_service.get_functional_visual, key)
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/{key}/semiotic", response_model=SemioticResponse)
async def brand_semiotic(key: str, current_user: Dict[str, Any] = Depends(get_current_user)):
    try:
        return await run_in_threadpool(brand_service.get_semiotic, key)
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/{key}/trend-participation")
async def brand_trend_participation(
    key: str,
    limit: int = Query(8, ge=1, le=20),
    current_user: Dict[str, Any] = Depends(get_current_user),
):
    """Trends this brand's own posts were assigned to in the latest run."""
    try:
        return await run_in_threadpool(brand_service.get_trend_participation, key, limit)
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/{key}/trend-opportunities")
async def brand_trend_opportunities(
    key: str,
    limit: int = Query(8, ge=1, le=20),
    min_competitors: int = Query(1, ge=1, le=10),
    current_user: Dict[str, Any] = Depends(get_current_user),
):
    """Trends this brand is absent from that its competitors already occupy."""
    try:
        return await run_in_threadpool(
            brand_service.get_trend_opportunities, key, limit, min_competitors)
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))
