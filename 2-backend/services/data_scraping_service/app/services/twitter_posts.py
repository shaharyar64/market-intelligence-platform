import asyncio
from datetime import datetime
from typing import Any

import httpx
from sqlalchemy import text

from services.data_scraping_service.app.core.config import get_settings
from services.data_scraping_service.app.models.twitter_posts import (
    TwitterPost,
    TwitterPostScrapeRequest,
)
from services.data_scraping_service.app.services.instagram import ScraperConfigurationError
from services.data_scraping_service.app.services.twitter import TwitterScrapeError


TWITTER_DATE_FORMAT = "%a %b %d %H:%M:%S %z %Y"


async def _fetch_page(
    client: httpx.AsyncClient,
    username: str,
    cursor: str | None,
) -> dict[str, Any]:
    settings = get_settings()
    params = {"userName": username}
    if cursor:
        params["cursor"] = cursor
    for attempt in range(4):
        try:
            response = await client.get(
                settings.TWITTER_POSTS_API_URL,
                headers={"X-API-Key": settings.TWITTER_API_KEY},
                params=params,
            )
            if response.status_code not in {429, 500, 502, 503, 504}:
                response.raise_for_status()
                payload = response.json()
                if payload.get("status") != "success":
                    raise TwitterScrapeError(
                        f"Twitter API error for {username}: {payload.get('msg', 'unknown error')}"
                    )
                return payload
        except (httpx.RequestError, httpx.HTTPStatusError) as exc:
            if attempt == 3:
                raise TwitterScrapeError(f"Twitter posts request failed for {username}") from exc
        if attempt < 3:
            await asyncio.sleep(2**attempt)
    raise TwitterScrapeError(f"Twitter posts request failed for {username}")


async def scrape_posts_for_username(
    username: str,
    request: TwitterPostScrapeRequest,
) -> list[TwitterPost]:
    if not get_settings().TWITTER_API_KEY:
        raise ScraperConfigurationError("TWITTER_API_KEY is not configured")

    posts: dict[str, TwitterPost] = {}
    cursor: str | None = None
    seen_cursors: set[str] = set()
    async with httpx.AsyncClient(timeout=httpx.Timeout(60, connect=10)) as client:
        while True:
            payload = await _fetch_page(client, username, cursor)
            tweets = payload.get("data", {}).get("tweets", [])
            if not isinstance(tweets, list):
                raise TwitterScrapeError(f"Twitter API returned invalid tweets for {username}")
            reached_start_boundary = False
            for tweet in tweets:
                try:
                    created_at = datetime.strptime(tweet["createdAt"], TWITTER_DATE_FORMAT)
                    created_date = created_at.date()
                    if created_date < request.start_date:
                        reached_start_boundary = True
                        continue
                    if created_date >= request.end_date:
                        continue
                    post_id = str(tweet["id"])
                    posts[post_id] = TwitterPost(
                        id=post_id,
                        username=username,
                        text=tweet.get("text") or "",
                        uploaded_at=created_date,
                        views=tweet.get("viewCount") or 0,
                        replies=tweet.get("replyCount") or 0,
                        retweet=tweet.get("retweetCount") or 0,
                        likes=tweet.get("likeCount") or 0,
                        last_updated=datetime.now().date(),
                    )
                except (KeyError, TypeError, ValueError):
                    continue
            if reached_start_boundary or not payload.get("has_next_page"):
                break
            next_cursor = payload.get("next_cursor")
            if not next_cursor or next_cursor in seen_cursors:
                break
            seen_cursors.add(next_cursor)
            cursor = next_cursor
    return list(posts.values())


async def scrape_twitter_posts(request: TwitterPostScrapeRequest) -> list[TwitterPost]:
    semaphore = asyncio.Semaphore(4)

    async def scrape(username: str) -> list[TwitterPost]:
        async with semaphore:
            return await scrape_posts_for_username(username, request)

    batches = await asyncio.gather(*(scrape(username) for username in request.usernames))
    unique = {(post.id, post.username): post for batch in batches for post in batch}
    return list(unique.values())


def _persist_twitter_posts_sync(posts: list[TwitterPost]) -> None:
    from shared.database import Database

    table = get_settings().TWITTER_POSTS_TABLE
    statement = text(
        f"""
        INSERT INTO {table}
            (id, username, text, uploaded_at, views, replies, retweet, likes, last_updated)
        SELECT
            :id, :username, :text, :uploaded_at, :views, :replies, :retweet, :likes, :last_updated
        WHERE NOT EXISTS (
            SELECT 1 FROM {table}
            WHERE id = :id AND username = :username
        )
        """
    )
    rows = [post.model_dump() for post in posts]
    if rows:
        with Database("raw_data").get_engine().begin() as connection:
            connection.execute(statement, rows)


async def persist_twitter_posts(posts: list[TwitterPost]) -> None:
    if posts:
        await asyncio.to_thread(_persist_twitter_posts_sync, posts)
