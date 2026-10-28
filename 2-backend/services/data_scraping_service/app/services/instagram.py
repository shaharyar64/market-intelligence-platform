import asyncio
from datetime import UTC, datetime
from typing import Any

import httpx
from sqlalchemy import text

from services.data_scraping_service.app.core.config import get_settings
from services.data_scraping_service.app.models.instagram import (
    InstagramProfile,
    InstagramProfileScrapeRequest,
)


class ScraperConfigurationError(RuntimeError):
    pass


class InstagramScrapeError(RuntimeError):
    pass


def normalize_profile(
    item: dict[str, Any],
    request: InstagramProfileScrapeRequest,
) -> InstagramProfile:
    return InstagramProfile(
        id=str(item["id"]) if item.get("id") is not None else None,
        username=item.get("username"),
        full_name=item.get("fullName"),
        followers=item.get("followersCount") or 0,
        following=item.get("followsCount") or 0,
        posts=item.get("postsCount") or 0,
        category=item.get("businessCategoryName"),
        is_verified=item.get("verified", False),
        bio=item.get("biography"),
        external_url=item.get("externalUrl") or item.get("external_url"),
        last_updated=datetime.now(UTC),
        country=request.country,
        industry=request.industry,
        project=request.project,
    )


async def scrape_instagram_profiles(
    request: InstagramProfileScrapeRequest,
) -> list[InstagramProfile]:
    settings = get_settings()
    if not settings.APIFY_KEY:
        raise ScraperConfigurationError("APIFY_KEY is not configured")

    actor_id = settings.APIFY_INSTAGRAM_PROFILE_ACTOR_ID.replace("/", "~")
    url = (
        f"{settings.APIFY_API_URL.rstrip('/')}/acts/{actor_id}"
        "/run-sync-get-dataset-items"
    )
    params = {
        "token": settings.APIFY_KEY,
        "timeout": settings.APIFY_REQUEST_TIMEOUT,
        "clean": "true",
    }
    run_input = {
        "usernames": request.usernames,
        "includeAboutSection": request.include_about_section,
    }

    try:
        async with httpx.AsyncClient(timeout=settings.APIFY_REQUEST_TIMEOUT + 10) as client:
            response = await client.post(url, params=params, json=run_input)
            response.raise_for_status()
    except httpx.TimeoutException as exc:
        raise InstagramScrapeError("Instagram scrape timed out") from exc
    except httpx.HTTPStatusError as exc:
        detail = exc.response.text[:500]
        raise InstagramScrapeError(
            f"Apify returned HTTP {exc.response.status_code}: {detail}"
        ) from exc
    except httpx.RequestError as exc:
        raise InstagramScrapeError(f"Could not reach Apify: {exc}") from exc

    items = response.json()
    if not isinstance(items, list):
        raise InstagramScrapeError("Apify returned an unexpected response")
    return [normalize_profile(item, request) for item in items]


def _persist_profiles_sync(profiles: list[InstagramProfile]) -> None:
    # Import lazily so scraping without persistence does not initialize AWS/DB clients.
    from shared.database import Database

    settings = get_settings()
    database = Database("raw_data")
    update_statement = text(
        f"""
        UPDATE {settings.INSTAGRAM_PROFILE_TABLE}
        SET id = :id, full_name = :full_name, followers = :followers,
            following = :following, posts = :posts, category = :category,
            is_verified = :is_verified, bio = :bio, external_url = :external_url,
            last_updated = :last_updated, country = :country, industry = :industry
        WHERE username = :username
          AND project IS NOT DISTINCT FROM :project
        """
    )
    insert_statement = text(
        f"""
        INSERT INTO {settings.INSTAGRAM_PROFILE_TABLE}
            (id, username, full_name, followers, following, posts, category,
             is_verified, bio, external_url, last_updated, country, industry, project)
        VALUES
            (:id, :username, :full_name, :followers, :following, :posts, :category,
             :is_verified, :bio, :external_url, :last_updated, :country, :industry, :project)
        ON CONFLICT DO NOTHING
        """
    )
    rows = [
        {
            **profile.model_dump(),
            "id": int(profile.id) if profile.id is not None else None,
            "last_updated": profile.last_updated.replace(tzinfo=None),
        }
        for profile in profiles
    ]
    with database.get_engine().begin() as connection:
        connection.execute(update_statement, rows)
        connection.execute(insert_statement, rows)


async def persist_profiles(profiles: list[InstagramProfile]) -> None:
    if profiles:
        await asyncio.to_thread(_persist_profiles_sync, profiles)
