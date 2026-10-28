from fastapi import APIRouter
from typing import Optional
from services.ev_service.app.services.overview import (
    fetch_kpis,
    fetch_last_6_months_posts,
    fetch_engagement_trend,
    fetch_posts_trend,
    fetch_total_posts_by_brand,
    fetch_top5_themes_by_volume,
    fetch_theme_distribution,
    fetch_themes_multiline,
    fetch_growing_themes_bar,
    fetch_growing_themes_multiline,
    fetch_top5_sub_themes_by_volume,
    fetch_sub_theme_distribution,
    fetch_sub_themes_multiline,
    fetch_growing_sub_themes_bar,
    fetch_growing_sub_themes_multiline
)



router = APIRouter(
    prefix="/overview",
    tags=["EV Overview"]
)


@router.get("/kpis")
async def get_kpis(country: str | None = None):
    return await fetch_kpis(country)


@router.get("/last-6-months-posts")
async def get_last_6_months_posts(country: str | None = None):
    return await fetch_last_6_months_posts(country)


@router.get("/engagement-trend")
async def get_engagement_trend(country: str | None = None):
    return await fetch_engagement_trend(country)


@router.get("/posts-trend")
async def get_posts_trend(country: str | None = None):
    return await fetch_posts_trend(country)


@router.get("/total-posts-by-brand")
async def get_total_posts_by_brand(country: str | None = None):
    return await fetch_total_posts_by_brand(country)



# =========================
# THEMES ENDPOINTS
# =========================

@router.get("/themes/top5-themes-by-volume")
async def get_top5_themes_by_volume(
    country: Optional[str] = None,
    theme: Optional[str] = None
):
    return await fetch_top5_themes_by_volume(country, theme)


@router.get("/themes/distribution")
async def get_theme_distribution(
    country: Optional[str] = None,
    theme: Optional[str] = None
):
    return await fetch_theme_distribution(country, theme)


@router.get("/themes/multiline")
async def get_themes_multiline(
    country: Optional[str] = None,
    theme: Optional[str] = None
):
    return await fetch_themes_multiline(country, theme)


@router.get("/themes/growing-bar")
async def get_growing_themes_bar(
    country: Optional[str] = None,
    theme: Optional[str] = None
):
    return await fetch_growing_themes_bar(country, theme)


@router.get("/themes/growing-multiline")
async def get_growing_themes_multiline(
    country: Optional[str] = None,
    theme: Optional[str] = None
):
    return await fetch_growing_themes_multiline(country, theme)


# =========================
# SUB-THEMES ENDPOINTS
# =========================

@router.get("/sub-themes/top5-sub-themes-by-volume")
async def get_top5_sub_themes_by_volume(
    country: Optional[str] = None
):
    return await fetch_top5_sub_themes_by_volume(country)


@router.get("/sub-themes/distribution")
async def get_sub_theme_distribution(
    country: Optional[str] = None
):
    return await fetch_sub_theme_distribution(country)


@router.get("/sub-themes/multiline")
async def get_sub_themes_multiline(
    country: Optional[str] = None
):
    return await fetch_sub_themes_multiline(country)


@router.get("/sub-themes/growing-bar")
async def get_growing_sub_themes_bar(
    country: Optional[str] = None
):
    return await fetch_growing_sub_themes_bar(country)


@router.get("/sub-themes/growing-multiline")
async def get_growing_sub_themes_multiline(
    country: Optional[str] = None
):
    return await fetch_growing_sub_themes_multiline(country)