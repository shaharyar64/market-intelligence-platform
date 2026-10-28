import asyncio
from datetime import UTC, datetime
from typing import Any
from urllib.parse import urlparse

import httpx
from sqlalchemy import text

from services.data_scraping_service.app.core.config import get_settings
from services.data_scraping_service.app.models.tiktok import (
    TikTokProfile,
    TikTokProfileScrapeRequest,
)
from services.data_scraping_service.app.services.instagram import (
    InstagramScrapeError,
    ScraperConfigurationError,
)


def _username_from_url(url: str) -> str:
    return next(
        part[1:]
        for part in urlparse(url).path.split("/")
        if part.startswith("@")
    )


def normalize_profile(item: dict[str, Any], request: TikTokProfileScrapeRequest) -> TikTokProfile:
    return TikTokProfile(
        id=str(item["id"]) if item.get("id") is not None else None,
        url=item.get("url"),
        username=item.get("username"),
        nickname=item.get("nickname"),
        bio=item.get("bio"),
        bio_url=item.get("bioUrl"),
        followers=item.get("followers") or 0,
        following=item.get("following") or 0,
        likes=item.get("likes") or 0,
        videos=item.get("videos") or 0,
        is_verified=item.get("verified") or False,
        profile_category=item.get("profileCategory"),
        avatar=item.get("avatar"),
        country=request.country,
        industry=request.industry,
        project=request.project,
        last_updated=datetime.now(UTC),
    )


async def scrape_tiktok_profile(
    profile_url: str,
    request: TikTokProfileScrapeRequest,
) -> TikTokProfile:
    settings = get_settings()
    if not settings.APIFY_KEY:
        raise ScraperConfigurationError("APIFY_KEY is not configured")
    actor_id = settings.APIFY_TIKTOK_PROFILE_ACTOR_ID.replace("/", "~")
    url = f"{settings.APIFY_API_URL.rstrip('/')}/acts/{actor_id}/run-sync-get-dataset-items"
    try:
        async with httpx.AsyncClient(timeout=settings.APIFY_REQUEST_TIMEOUT + 10) as client:
            response = await client.post(
                url,
                params={
                    "token": settings.APIFY_KEY,
                    "timeout": settings.APIFY_REQUEST_TIMEOUT,
                    "clean": "true",
                },
                json={
                    "startUrls": [profile_url],
                    "maxItems": request.max_items,
                    "getFollowers": request.get_followers,
                    "getFollowing": request.get_following,
                },
            )
            response.raise_for_status()
    except httpx.TimeoutException as exc:
        raise InstagramScrapeError(f"TikTok profile scrape timed out for {profile_url}") from exc
    except httpx.HTTPStatusError as exc:
        raise InstagramScrapeError(
            f"Apify returned HTTP {exc.response.status_code} for {profile_url}"
        ) from exc
    except httpx.RequestError as exc:
        raise InstagramScrapeError(f"Could not reach Apify for {profile_url}") from exc

    items = response.json()
    if not isinstance(items, list):
        raise InstagramScrapeError("Apify returned an unexpected TikTok response")
    expected = _username_from_url(profile_url).lower()
    item = next(
        (entry for entry in items if str(entry.get("username", "")).lower() == expected),
        None,
    )
    if item is None:
        raise InstagramScrapeError(f"TikTok profile was not found for @{expected}")
    return normalize_profile(item, request)


async def scrape_tiktok_profiles(request: TikTokProfileScrapeRequest) -> list[TikTokProfile]:
    semaphore = asyncio.Semaphore(4)

    async def scrape(url: str) -> TikTokProfile:
        async with semaphore:
            return await scrape_tiktok_profile(url, request)

    return await asyncio.gather(*(scrape(url) for url in request.profiles))


def _persist_profiles_sync(profiles: list[TikTokProfile]) -> None:
    from shared.database import Database

    table = get_settings().TIKTOK_PROFILE_TABLE
    update_statement = text(f"""
        UPDATE {table}
        SET id = :id, name = :name, bio = :bio, bio_url = :bio_url,
            followers = :followers, following = :following, likes = :likes,
            videos = :videos, verified = :verified, category = :category,
            country = :country, industry = :industry
        WHERE username = :username AND project = :project
    """)
    insert_statement = text(f"""
        INSERT INTO {table}
            (id, username, name, bio, bio_url, followers, following, likes,
             videos, verified, category, country, industry, project)
        SELECT
            :id, :username, :name, :bio, :bio_url, :followers, :following, :likes,
            :videos, :verified, :category, :country, :industry, :project
        WHERE NOT EXISTS (
            SELECT 1 FROM {table} WHERE username = :username AND project = :project
        )
    """)
    rows = [
        {
            "id": profile.id,
            "username": profile.username,
            "name": profile.nickname or profile.username,
            "bio": profile.bio,
            "bio_url": profile.bio_url,
            "followers": profile.followers,
            "following": profile.following,
            "likes": profile.likes,
            "videos": profile.videos,
            "verified": profile.is_verified,
            "category": profile.profile_category,
            "country": profile.country,
            "industry": profile.industry,
            "project": profile.project,
        }
        for profile in profiles
    ]
    if rows:
        with Database("raw_data").get_engine().begin() as connection:
            connection.execute(update_statement, rows)
            connection.execute(insert_statement, rows)


async def persist_tiktok_profiles(profiles: list[TikTokProfile]) -> None:
    if profiles:
        await asyncio.to_thread(_persist_profiles_sync, profiles)
