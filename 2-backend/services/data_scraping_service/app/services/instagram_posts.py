import asyncio
from datetime import UTC, datetime, time, timedelta
from typing import Any

import httpx
from sqlalchemy import text

from services.data_scraping_service.app.core.config import get_settings
from services.data_scraping_service.app.models.instagram_posts import (
    InstagramPost,
    InstagramPostScrapeRequest,
)
from services.data_scraping_service.app.services.instagram import (
    InstagramScrapeError,
    ScraperConfigurationError,
)
from services.data_scraping_service.app.services.media import upload_post_thumbnail


TERMINAL_RUN_STATUSES = {"SUCCEEDED", "FAILED", "ABORTED", "TIMED-OUT"}


def _data(payload: dict[str, Any]) -> dict[str, Any]:
    data = payload.get("data", payload)
    if not isinstance(data, dict):
        raise InstagramScrapeError("Apify returned an unexpected response")
    return data


async def scrape_posts_for_username(
    username: str,
    request: InstagramPostScrapeRequest,
) -> list[InstagramPost]:
    settings = get_settings()
    if not settings.APIFY_KEY:
        raise ScraperConfigurationError("APIFY_KEY is not configured")

    actor_id = settings.APIFY_INSTAGRAM_POSTS_ACTOR_ID.replace("/", "~")
    base = settings.APIFY_API_URL.rstrip("/")
    params = {"token": settings.APIFY_KEY}
    run_input = {
        "username": username,
        "scrape_type": "posts",
        "max_items": request.max_items_per_username,
        "output_mode": "clean",
        "cursor": "",
    }
    start = datetime.combine(request.start_date, time.min, tzinfo=UTC)
    end = datetime.combine(request.end_date + timedelta(days=1), time.min, tzinfo=UTC)

    try:
        async with httpx.AsyncClient(timeout=60) as client:
            started = await client.post(f"{base}/acts/{actor_id}/runs", params=params, json=run_input)
            started.raise_for_status()
            run = _data(started.json())
            run_id = run.get("id")
            dataset_id = run.get("defaultDatasetId")
            if not run_id or not dataset_id:
                raise InstagramScrapeError("Apify did not return run and dataset IDs")

            offset = 0
            posts: dict[str, InstagramPost] = {}
            should_stop = False
            while True:
                items_response = await client.get(
                    f"{base}/datasets/{dataset_id}/items",
                    params={**params, "offset": offset, "limit": 1000, "clean": "true"},
                )
                items_response.raise_for_status()
                items = items_response.json()
                if not isinstance(items, list):
                    raise InstagramScrapeError("Apify returned unexpected dataset items")
                offset += len(items)

                for item in items:
                    taken_at = item.get("taken_at")
                    post_id = item.get("shortcode")
                    if taken_at is None or not post_id:
                        continue
                    uploaded_at = datetime.fromtimestamp(taken_at, tz=UTC)
                    if uploaded_at < start:
                        should_stop = True
                        continue
                    if uploaded_at >= end:
                        continue
                    caption = item.get("caption") or ""
                    hashtags = item.get("hashtags") or []
                    posts[post_id] = InstagramPost(
                        id=post_id,
                        username=username,
                        uploaded_at=uploaded_at,
                        caption=f"{caption} {' '.join(hashtags)}".strip().lower(),
                        views=item.get("play_count") or item.get("ig_play_count") or 0,
                        comments=item.get("comment_count") or 0,
                        likes=item.get("like_count") or 0,
                        last_updated=datetime.now(UTC),
                        thumbnail_url=item.get("thumbnail_url"),
                    )

                run_response = await client.get(f"{base}/actor-runs/{run_id}", params=params)
                run_response.raise_for_status()
                run_status = _data(run_response.json()).get("status")
                if should_stop:
                    if run_status not in TERMINAL_RUN_STATUSES:
                        await client.post(f"{base}/actor-runs/{run_id}/abort", params=params)
                    break
                if run_status in TERMINAL_RUN_STATUSES and not items:
                    if run_status not in {"SUCCEEDED", "ABORTED"}:
                        raise InstagramScrapeError(f"Apify run ended with status {run_status}")
                    break
                if not items:
                    await asyncio.sleep(1)
            return list(posts.values())
    except httpx.TimeoutException as exc:
        raise InstagramScrapeError(f"Instagram posts scrape timed out for {username}") from exc
    except httpx.HTTPStatusError as exc:
        raise InstagramScrapeError(
            f"Apify returned HTTP {exc.response.status_code} while scraping {username}"
        ) from exc
    except httpx.RequestError as exc:
        raise InstagramScrapeError(f"Could not reach Apify while scraping {username}") from exc


async def scrape_instagram_posts(request: InstagramPostScrapeRequest) -> list[InstagramPost]:
    semaphore = asyncio.Semaphore(4)

    async def scrape(username: str) -> list[InstagramPost]:
        async with semaphore:
            return await scrape_posts_for_username(username, request)

    batches = await asyncio.gather(*(scrape(username) for username in request.usernames))
    unique = {post.id: post for batch in batches for post in batch}
    return list(unique.values())


async def upload_post_images(posts: list[InstagramPost]) -> None:
    semaphore = asyncio.Semaphore(12)

    async def upload(post: InstagramPost) -> None:
        if not post.thumbnail_url:
            post.image_upload_status = "skipped"
            return
        async with semaphore:
            key, result = await asyncio.to_thread(upload_post_thumbnail, post.thumbnail_url, post.id)
            post.s3_key = key
            post.image_upload_status = result

    await asyncio.gather(*(upload(post) for post in posts))


def _persist_posts_sync(posts: list[InstagramPost]) -> None:
    from shared.database import Database

    table = get_settings().INSTAGRAM_POSTS_TABLE
    statement = text(
        f"""
        INSERT INTO {table}
            (id, username, uploaded_at, caption, views, comments, likes, last_updated)
        VALUES
            (:id, :username, :uploaded_at, :caption, :views, :comments, :likes, :last_updated)
        ON CONFLICT (id) DO NOTHING
        """
    )
    fields = {"id", "username", "uploaded_at", "caption", "views", "comments", "likes", "last_updated"}
    rows = [post.model_dump(include=fields) for post in posts]
    if rows:
        with Database("raw_data").get_engine().begin() as connection:
            connection.execute(statement, rows)


async def persist_posts(posts: list[InstagramPost]) -> None:
    if posts:
        await asyncio.to_thread(_persist_posts_sync, posts)
