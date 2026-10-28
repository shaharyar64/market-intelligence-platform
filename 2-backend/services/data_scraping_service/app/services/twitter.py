import asyncio
from datetime import UTC, datetime
from typing import Any

import httpx
from sqlalchemy import text

from services.data_scraping_service.app.core.config import get_settings
from services.data_scraping_service.app.models.twitter import (
    TwitterProfile,
    TwitterProfileScrapeRequest,
)
from services.data_scraping_service.app.services.instagram import ScraperConfigurationError


class TwitterScrapeError(RuntimeError):
    pass


async def scrape_twitter_profile(
    username: str,
    request: TwitterProfileScrapeRequest,
) -> TwitterProfile:
    settings = get_settings()
    if not settings.TWITTER_API_KEY:
        raise ScraperConfigurationError("TWITTER_API_KEY is not configured")
    try:
        async with httpx.AsyncClient(timeout=60) as client:
            response = await client.get(
                settings.TWITTER_PROFILE_API_URL,
                headers={"X-API-Key": settings.TWITTER_API_KEY},
                params={"userName": username},
            )
            response.raise_for_status()
    except httpx.TimeoutException as exc:
        raise TwitterScrapeError(f"Twitter profile scrape timed out for {username}") from exc
    except httpx.HTTPStatusError as exc:
        raise TwitterScrapeError(
            f"Twitter API returned HTTP {exc.response.status_code} for {username}"
        ) from exc
    except httpx.RequestError as exc:
        raise TwitterScrapeError(f"Could not reach Twitter API for {username}") from exc

    payload: dict[str, Any] = response.json()
    if payload.get("status") != "success" or not isinstance(payload.get("data"), dict):
        raise TwitterScrapeError(f"Twitter profile was not found for {username}")
    data = payload["data"]
    return TwitterProfile(
        id=str(data["id"]) if data.get("id") is not None else None,
        username=data.get("userName"),
        full_name=data.get("name"),
        bio=data.get("description"),
        followers=data.get("followers") or 0,
        following=data.get("following") or 0,
        posts=data.get("statusesCount") or 0,
        is_verified=data.get("isVerified") or False,
        is_blue_verified=data.get("isBlueVerified") or False,
        verified_type=data.get("verifiedType"),
        created_at=data.get("createdAt"),
        last_updated=datetime.now(UTC),
        country=request.country,
        industry=request.industry,
        project=request.project,
    )


async def scrape_twitter_profiles(request: TwitterProfileScrapeRequest) -> list[TwitterProfile]:
    semaphore = asyncio.Semaphore(4)

    async def scrape(username: str) -> TwitterProfile:
        async with semaphore:
            return await scrape_twitter_profile(username, request)

    return await asyncio.gather(*(scrape(username) for username in request.usernames))


def _persist_twitter_profiles_sync(profiles: list[TwitterProfile]) -> None:
    from shared.database import Database

    table = get_settings().TWITTER_PROFILE_TABLE
    statement = text(
        f"""
        INSERT INTO {table}
            (id, username, full_name, bio, followers, following, posts,
             is_verified, is_blue_verified, verified_type, created_at,
             last_updated, country, industry, project)
        VALUES
            (:id, :username, :full_name, :bio, :followers, :following, :posts,
             :is_verified, :is_blue_verified, :verified_type, :created_at,
             :last_updated, :country, :industry, :project)
        """
    )
    rows = [
        {
            **profile.model_dump(),
            "id": int(profile.id) if profile.id else None,
            "created_at": profile.created_at.replace(tzinfo=None) if profile.created_at else None,
            "last_updated": profile.last_updated.replace(tzinfo=None),
        }
        for profile in profiles
    ]
    if rows:
        with Database("raw_data").get_engine().begin() as connection:
            connection.execute(statement, rows)


async def persist_twitter_profiles(profiles: list[TwitterProfile]) -> None:
    if profiles:
        await asyncio.to_thread(_persist_twitter_profiles_sync, profiles)
