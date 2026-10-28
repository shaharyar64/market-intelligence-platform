from typing import Any

from fastapi import APIRouter, Depends, HTTPException, Query
from fastapi.concurrency import run_in_threadpool

from services.trends_real_estate_service.app.api.deps import get_current_user
from services.trends_real_estate_service.app.api.errors import internal_error
from services.trends_real_estate_service.app.services import visual_service

router = APIRouter(prefix="/visual", tags=["Visual Intelligence"])


@router.get("/cohorts")
async def cohorts(current_user: dict[str, Any] = Depends(get_current_user)):
    """The three cohorts and how much analysed material each has — the tabs."""
    try:
        return await run_in_threadpool(visual_service.cohort_counts)
    except Exception:
        raise internal_error("cohorts") from None


@router.get("/cohort/{account_type}")
async def cohort_analysis(
    account_type: str,
    key: list[str] | None = Query(None, description="Narrow to these accounts; repeat for several"),
    min_posts: int = Query(2, ge=1, le=50),
    limit: int = Query(15, ge=1, le=50),
    current_user: dict[str, Any] = Depends(get_current_user),
):
    """Themes, offerings and language for a cohort, or one account inside it.

    Consumers come back with sampled=true: their posts are analysed from a
    stratified sample rather than in full, and the screen has to say so.
    """
    try:
        return await run_in_threadpool(
            visual_service.get_cohort_analysis, account_type, key, min_posts, limit)
    except ValueError as e:
        raise HTTPException(status_code=404, detail=str(e)) from e
    except Exception:
        raise internal_error("cohort_analysis") from None


@router.get("/gallery")
async def gallery(
    limit: int = Query(12, ge=1, le=50),
    key: list[str] | None = Query(None, description="Narrow to these accounts; repeat for several"),
    account_type: str | None = Query(None, pattern="^(brand|influencer|community)$"),
    current_user: dict[str, Any] = Depends(get_current_user),
):
    """Recent imagery for a cohort, or for a chosen set of accounts inside it."""
    try:
        return await run_in_threadpool(
            visual_service.get_gallery, limit, key, account_type)
    except Exception:
        raise internal_error("gallery") from None


@router.get("/territories")
async def territory_growth(
    limit: int = Query(8, ge=1, le=20),
    account_type: str | None = Query(None, pattern="^(brand|influencer|community)$"),
    key: list[str] | None = Query(None),
    current_user: dict[str, Any] = Depends(get_current_user),
):
    """Which visual territories are gaining share of the conversation.

    Measured over the tracked accounts only, where every post is analysed; the
    consumer sample is drawn by engagement rather than by date and cannot carry
    a time series.
    """
    try:
        return await run_in_threadpool(
            visual_service.get_territory_growth, limit, account_type, key)
    except Exception:
        raise internal_error("territory_growth") from None


@router.get("/brand-territories")
async def brand_territories(
    limit: int = Query(8, ge=1, le=50),
    account_type: str = Query("brand", pattern="^(brand|influencer|community)$"),
    current_user: dict[str, Any] = Depends(get_current_user),
):
    try:
        return await run_in_threadpool(
            visual_service.get_brand_territories, limit, account_type)
    except Exception:
        raise internal_error("brand_territories") from None
