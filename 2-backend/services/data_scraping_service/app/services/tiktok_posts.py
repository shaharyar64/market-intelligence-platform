import asyncio
import json
from datetime import UTC, datetime
from typing import Any

import httpx
from sqlalchemy import text

from services.data_scraping_service.app.core.config import get_settings
from services.data_scraping_service.app.models.tiktok_posts import (
    TikTokPost,
    TikTokPostScrapeRequest,
)
from services.data_scraping_service.app.services.instagram import (
    InstagramScrapeError,
    ScraperConfigurationError,
)


CUSTOM_MAP_FUNCTION = "(object) => { return { ...object } }"


def _uploaded_at(item: dict[str, Any]) -> datetime | None:
    value = item.get("createTimeISO")
    if value:
        try:
            return datetime.fromisoformat(str(value).replace("Z", "+00:00"))
        except ValueError:
            pass
    timestamp = item.get("createTime")
    if timestamp is not None:
        try:
            return datetime.fromtimestamp(float(timestamp), tz=UTC)
        except (TypeError, ValueError, OSError):
            pass
    return None


def normalize_post(item: dict[str, Any], request: TikTokPostScrapeRequest) -> TikTokPost | None:
    post_id = item.get("id")
    if not post_id or item.get("error"):
        return None
    uploaded_at = _uploaded_at(item)
    if request.start_date and request.end_date:
        if uploaded_at is None or not request.start_date <= uploaded_at.date() <= request.end_date:
            return None
    author = item.get("authorMeta") or {}
    video = item.get("videoMeta") or {}
    music = item.get("musicMeta") or {}
    hashtags = [
        tag.get("name") or tag.get("title")
        for tag in (item.get("hashtags") or [])
        if isinstance(tag, dict) and (tag.get("name") or tag.get("title"))
    ]
    return TikTokPost(
        id=str(post_id),
        text=item.get("text"),
        text_language=item.get("textLanguage"),
        uploaded_at=uploaded_at,
        web_video_url=item.get("webVideoUrl"),
        location_created=item.get("locationCreated"),
        is_ad=item.get("isAd") or False,
        author_id=str(author["id"]) if author.get("id") is not None else None,
        username=author.get("name"),
        nickname=author.get("nickName"),
        author_verified=author.get("verified") or False,
        author_followers=author.get("fans") or 0,
        views=item.get("playCount") or 0,
        likes=item.get("diggCount") or 0,
        comments=item.get("commentCount") or 0,
        shares=item.get("shareCount") or 0,
        saves=item.get("collectCount") or 0,
        reposts=item.get("repostCount") or 0,
        duration=video.get("duration"),
        cover_url=video.get("coverUrl") or video.get("originalCoverUrl"),
        music_name=music.get("musicName"),
        hashtags=json.dumps(hashtags, ensure_ascii=False),
        is_slideshow=item.get("isSlideshow") or False,
        is_pinned=item.get("isPinned") or False,
        is_sponsored=item.get("isSponsored") or False,
        input_url=item.get("input") or item.get("submittedVideoUrl"),
        country=request.country,
        industry=request.industry,
        project=request.project,
        last_updated=datetime.now(UTC),
    )


async def scrape_posts_for_url(
    start_url: str,
    request: TikTokPostScrapeRequest,
) -> list[TikTokPost]:
    settings = get_settings()
    if not settings.APIFY_KEY:
        raise ScraperConfigurationError("APIFY_KEY is not configured")
    actor_id = settings.APIFY_TIKTOK_POSTS_ACTOR_ID.replace("/", "~")
    actor_url = f"{settings.APIFY_API_URL.rstrip('/')}/acts/{actor_id}/run-sync-get-dataset-items"
    actor_input = {
        "customMapFunction": CUSTOM_MAP_FUNCTION,
        "includeSearchKeywords": False,
        "maxItems": request.max_items,
        "startUrls": [start_url],
    }
    try:
        async with httpx.AsyncClient(timeout=settings.APIFY_REQUEST_TIMEOUT + 10) as client:
            response = await client.post(
                actor_url,
                params={
                    "token": settings.APIFY_KEY,
                    "timeout": settings.APIFY_REQUEST_TIMEOUT,
                    "clean": "true",
                },
                json=actor_input,
            )
            response.raise_for_status()
    except httpx.TimeoutException as exc:
        raise InstagramScrapeError(f"TikTok posts scrape timed out for {start_url}") from exc
    except httpx.HTTPStatusError as exc:
        raise InstagramScrapeError(
            f"Apify returned HTTP {exc.response.status_code} for {start_url}"
        ) from exc
    except httpx.RequestError as exc:
        raise InstagramScrapeError(f"Could not reach Apify for {start_url}") from exc
    items = response.json()
    if not isinstance(items, list):
        raise InstagramScrapeError("Apify returned an unexpected TikTok posts response")
    errors = [item.get("error") for item in items if item.get("error")]
    posts = [post for item in items if (post := normalize_post(item, request))]
    if errors and not posts:
        raise InstagramScrapeError(f"TikTok scrape failed for {start_url}: {errors[0]}")
    return posts


async def scrape_tiktok_posts(request: TikTokPostScrapeRequest) -> list[TikTokPost]:
    semaphore = asyncio.Semaphore(2)

    async def scrape(url: str) -> list[TikTokPost]:
        async with semaphore:
            return await scrape_posts_for_url(url, request)

    batches = await asyncio.gather(*(scrape(url) for url in request.start_urls))
    unique = {post.id: post for batch in batches for post in batch}
    return list(unique.values())


def _persist_posts_sync(posts: list[TikTokPost]) -> None:
    from shared.database import Database

    table = get_settings().TIKTOK_POSTS_TABLE
    columns = (
        "id", "text", "text_language", "uploaded_at", "web_video_url",
        "location_created", "is_ad", "author_id", "username", "nickname",
        "author_verified", "author_followers", "views", "likes", "comments",
        "shares", "saves", "reposts", "duration", "cover_url", "music_name",
        "hashtags", "is_slideshow", "is_pinned", "is_sponsored", "input_url",
        "country", "industry", "project", "last_updated",
    )
    column_sql = ", ".join(columns)
    value_sql = ", ".join(f":{column}" for column in columns)
    statement = text(
        f"""
        INSERT INTO {table} ({column_sql})
        SELECT {value_sql}
        WHERE NOT EXISTS (SELECT 1 FROM {table} WHERE id = :id)
        """
    )
    rows = [
        {
            **post.model_dump(),
            "uploaded_at": post.uploaded_at.replace(tzinfo=None) if post.uploaded_at else None,
            "last_updated": post.last_updated.replace(tzinfo=None),
        }
        for post in posts
    ]
    if rows:
        with Database("raw_data").get_engine().begin() as connection:
            connection.execute(statement, rows)


async def persist_tiktok_posts(posts: list[TikTokPost]) -> None:
    if posts:
        await asyncio.to_thread(_persist_posts_sync, posts)
