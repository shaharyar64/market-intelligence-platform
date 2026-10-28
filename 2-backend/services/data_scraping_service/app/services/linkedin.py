import asyncio
from datetime import UTC, datetime
from typing import Any

import httpx
from sqlalchemy import text

from services.data_scraping_service.app.core.config import get_settings
from services.data_scraping_service.app.models.linkedin import (
    LinkedInProfile,
    LinkedInProfileScrapeRequest,
)
from services.data_scraping_service.app.services.instagram import InstagramScrapeError, ScraperConfigurationError


def normalize_profile(item: dict[str, Any], request: LinkedInProfileScrapeRequest) -> LinkedInProfile:
    headquarters = item.get("headquarter") or {}
    founded = item.get("foundedOn") or {}
    return LinkedInProfile(
        url=item.get("url"), company_name=item.get("companyName"),
        website_url=item.get("websiteUrl"), industry=item.get("industry"),
        employee_count=item.get("employeeCount") or 0,
        follower_count=item.get("followerCount") or 0,
        universal_name=item.get("universalName"), tagline=item.get("tagline"),
        hashtag=item.get("hashtag"),
        country=request.country or headquarters.get("country"),
        city=headquarters.get("city"), postal_code=headquarters.get("postalCode"),
        founded_on=founded.get("year"), description=item.get("description"),
        project=request.project, last_updated=datetime.now(UTC),
    )


async def scrape_linkedin_profile(url: str, request: LinkedInProfileScrapeRequest) -> LinkedInProfile:
    settings = get_settings()
    if not settings.APIFY_KEY:
        raise ScraperConfigurationError("APIFY_KEY is not configured")
    actor_id = settings.APIFY_LINKEDIN_PROFILE_ACTOR_ID.replace("/", "~")
    endpoint = f"{settings.APIFY_API_URL.rstrip('/')}/acts/{actor_id}/run-sync-get-dataset-items"
    try:
        async with httpx.AsyncClient(timeout=settings.APIFY_REQUEST_TIMEOUT + 10) as client:
            response = await client.post(endpoint, params={
                "token": settings.APIFY_KEY, "timeout": settings.APIFY_REQUEST_TIMEOUT, "clean": "true"
            }, json={"profileUrls": [url]})
            response.raise_for_status()
    except httpx.TimeoutException as exc:
        raise InstagramScrapeError(f"LinkedIn profile scrape timed out for {url}") from exc
    except httpx.HTTPStatusError as exc:
        raise InstagramScrapeError(f"Apify returned HTTP {exc.response.status_code} for {url}") from exc
    except httpx.RequestError as exc:
        raise InstagramScrapeError(f"Could not reach Apify for {url}") from exc
    items = response.json()
    if not isinstance(items, list) or not items:
        raise InstagramScrapeError(f"LinkedIn company profile was not found for {url}")
    return normalize_profile(items[0], request)


async def scrape_linkedin_profiles(request: LinkedInProfileScrapeRequest) -> list[LinkedInProfile]:
    semaphore = asyncio.Semaphore(4)
    async def scrape(url: str):
        async with semaphore:
            return await scrape_linkedin_profile(url, request)
    return await asyncio.gather(*(scrape(url) for url in request.profile_urls))


def _persist_sync(profiles: list[LinkedInProfile]) -> None:
    from shared.database import Database
    table = get_settings().LINKEDIN_PROFILE_TABLE
    columns = ("url", "company_name", "website_url", "industry", "employee_count", "follower_count", "universal_name", "tagline", "hashtag", "country", "city", "postal_code", "founded_on", "description", "project", "last_updated")
    statement = text(f"INSERT INTO {table} ({', '.join(columns)}) VALUES ({', '.join(':'+c for c in columns)})")
    rows = [{**profile.model_dump(), "last_updated": profile.last_updated.replace(tzinfo=None)} for profile in profiles]
    if rows:
        with Database("raw_data").get_engine().begin() as connection:
            connection.execute(statement, rows)


async def persist_linkedin_profiles(profiles: list[LinkedInProfile]) -> None:
    if profiles:
        await asyncio.to_thread(_persist_sync, profiles)
