from typing import Literal

from fastapi import APIRouter, Query

from services.ceer_campaign_service.app.services import campaign


router = APIRouter(prefix="/campaign", tags=["CEER Campaign"])


@router.get("/overview")
def overview():
    return campaign.get_overview()


@router.get("/before-after")
def before_after():
    return campaign.get_before_after_metrics()


@router.get("/launch-impact")
def launch_impact():
    return campaign.get_launch_impact()


@router.get("/launch-themes")
def launch_themes():
    return campaign.get_launch_themes()


@router.get("/sentiment")
def sentiment():
    return campaign.get_sentiment()


@router.get("/themes")
def themes(
    content_type: Literal["post", "audience_comment"] = Query(default="audience_comment"),
):
    return campaign.get_themes(content_type)


@router.get("/search-interest")
def search_interest(
    keyword: str | None = Query(default=None, description="A CEER Trends keyword. Defaults to the five strongest terms."),
    country: str | None = Query(default=None, description="Optional country code."),
):
    return {"data": campaign.get_search_interest(keyword, country)}


@router.get("/search-regions")
def search_regions(
    keyword: str | None = Query(default=None, description="A CEER Trends keyword. Defaults to the strongest term per region."),
    country: str | None = Query(default=None, description="Optional country code."),
):
    return {"data": campaign.get_search_regions(keyword, country)}


@router.get("/content-performance")
def content_performance():
    return campaign.get_content_performance()


@router.get("/top-posts")
def top_posts(
    limit: int = Query(default=6, ge=1, le=12),
    platform: Literal["all", "instagram", "linkedin", "tiktok", "twitter"] = "all",
    sort: Literal["views", "engagement"] = "views",
):
    return campaign.get_top_posts(limit, platform, sort)


@router.get("/posts")
def posts(
    mode: Literal["top", "all"] = "top",
    limit: int = Query(default=12, ge=1, le=100),
    offset: int = Query(default=0, ge=0),
    platform: Literal["all", "instagram", "linkedin", "tiktok", "twitter"] = "all",
    period: Literal["all", "before", "launch_day", "after"] = "all",
    theme: str = "all",
):
    return campaign.get_posts_feed(mode, limit, offset, platform, period, theme)


@router.get("/comments")
def comments(
    mode: Literal["top", "all"] = "top",
    limit: int = Query(default=12, ge=1, le=50),
    offset: int = Query(default=0, ge=0),
    platform: Literal["all", "instagram", "linkedin", "tiktok", "twitter", "youtube"] = "all",
    period: Literal["all", "before", "launch_day", "after"] = "all",
):
    return campaign.get_comments_feed(mode, limit, offset, platform, period)


@router.get("/activity")
def activity():
    return campaign.get_activity()


@router.get("/community-pulse")
def community_pulse():
    return campaign.get_community_pulse()


@router.get("/audience-themes")
def audience_themes():
    return campaign.get_all_audience_themes()


@router.get("/competitor-mentions")
def competitor_mentions():
    return campaign.get_competitor_mentions()
