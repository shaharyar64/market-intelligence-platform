import asyncio
from datetime import UTC, datetime
from typing import Any
from urllib.parse import urlparse

import httpx
from sqlalchemy import text

from services.data_scraping_service.app.core.config import get_settings
from services.data_scraping_service.app.models.linkedin_posts import LinkedInPost, LinkedInPostScrapeRequest
from services.data_scraping_service.app.services.instagram import InstagramScrapeError, ScraperConfigurationError


def _company_id(url: str) -> str | None:
    parts = [part for part in urlparse(url).path.split("/") if part]
    return parts[1] if len(parts) >= 2 and parts[0] == "company" else None


def normalize_post(item: dict[str, Any], target_url: str, request: LinkedInPostScrapeRequest) -> LinkedInPost | None:
    posted = item.get("postedAt") or {}
    value = posted.get("date")
    if not value and posted.get("timestamp") is not None:
        value = datetime.fromtimestamp(float(posted["timestamp"]) / 1000, tz=UTC).isoformat()
    try:
        uploaded = datetime.fromisoformat(str(value).replace("Z", "+00:00"))
    except (TypeError, ValueError, OSError):
        return None
    if not request.start_date <= uploaded.date() <= request.end_date:
        return None
    post_url = item.get("linkedinUrl") or item.get("shareLinkedinUrl")
    if not post_url:
        return None
    author = item.get("author") or {}
    engagement = item.get("engagement") or {}
    return LinkedInPost(
        post_text=item.get("content") or "",
        post_url=post_url,
        likes=engagement.get("likes") or 0,
        shares=engagement.get("shares") or 0,
        comments=engagement.get("comments") or 0,
        uploaded_at=uploaded,
        universal_name=author.get("universalName"),
        source_company=_company_id(target_url),
        last_updated=datetime.now(UTC),
    )


async def scrape_posts_for_company(target_url: str, request: LinkedInPostScrapeRequest) -> list[LinkedInPost]:
    settings = get_settings()
    if not settings.APIFY_KEY:
        raise ScraperConfigurationError("APIFY_KEY is not configured")
    actor_id = settings.APIFY_LINKEDIN_POSTS_ACTOR_ID.replace("/", "~")
    endpoint = f"{settings.APIFY_API_URL.rstrip('/')}/acts/{actor_id}/run-sync-get-dataset-items"
    actor_input = {
        "includeQuotePosts": False, "includeReposts": False,
        "maxComments": 0, "maxPosts": request.max_posts, "maxReactions": 0,
        "postNestedComments": False, "postNestedReactions": False,
        "postedLimit": "any", "postedLimitDate": request.start_date.isoformat(),
        "scrapeComments": False, "scrapeReactions": False,
        "targetUrls": [target_url],
    }
    try:
        async with httpx.AsyncClient(timeout=settings.APIFY_REQUEST_TIMEOUT + 10) as client:
            response = await client.post(endpoint, params={"token": settings.APIFY_KEY, "timeout": settings.APIFY_REQUEST_TIMEOUT, "clean": "true"}, json=actor_input)
            response.raise_for_status()
    except httpx.TimeoutException as exc:
        raise InstagramScrapeError(f"LinkedIn posts scrape timed out for {target_url}") from exc
    except httpx.HTTPStatusError as exc:
        raise InstagramScrapeError(f"Apify returned HTTP {exc.response.status_code} for {target_url}") from exc
    except httpx.RequestError as exc:
        raise InstagramScrapeError(f"Could not reach Apify for {target_url}") from exc
    items = response.json()
    if not isinstance(items, list):
        raise InstagramScrapeError("Apify returned an unexpected LinkedIn posts response")
    unique = {}
    for item in items:
        post = normalize_post(item, target_url, request)
        if post:
            unique[post.post_url] = post
    return list(unique.values())


async def scrape_linkedin_posts(request: LinkedInPostScrapeRequest) -> list[LinkedInPost]:
    semaphore = asyncio.Semaphore(3)
    async def scrape(url):
        async with semaphore:
            return await scrape_posts_for_company(url, request)
    batches = await asyncio.gather(*(scrape(url) for url in request.target_urls))
    return list({post.post_url: post for batch in batches for post in batch}.values())


def _persist_sync(posts: list[LinkedInPost]) -> None:
    from shared.database import Database
    table = get_settings().LINKEDIN_POSTS_TABLE
    columns = ("post_text", "post_url", "likes", "shares", "comments", "uploaded_at", "universal_name", "last_updated")
    statement = text(f"INSERT INTO {table} ({', '.join(columns)}) SELECT {', '.join(':'+c for c in columns)} WHERE NOT EXISTS (SELECT 1 FROM {table} WHERE post_url = :post_url)")
    rows = [{key: value for key, value in post.model_dump().items() if key in columns} for post in posts]
    if rows:
        with Database("raw_data").get_engine().begin() as connection:
            connection.execute(statement, rows)


async def persist_linkedin_posts(posts):
    if posts:
        await asyncio.to_thread(_persist_sync, posts)
