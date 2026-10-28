import asyncio
import json
import re
from datetime import UTC, datetime, time, timedelta
from email.utils import parsedate_to_datetime
from typing import Any, Iterator

import httpx
from sqlalchemy import text

from services.data_scraping_service.app.core.config import get_settings
from services.data_scraping_service.app.models.twitter_keywords import (
    TwitterKeywordPost,
    TwitterKeywordScrapeRequest,
)
from services.data_scraping_service.app.services.instagram import ScraperConfigurationError
from services.data_scraping_service.app.services.twitter import TwitterScrapeError


COUNTRY_FILTER_TERMS = {
    "IND": [
        "india", "bharat", "indian", "mumbai", "delhi", "new delhi", "ncr",
        "gurgaon", "gurugram", "noida", "bangalore", "bengaluru", "chennai",
        "hyderabad", "pune", "kolkata", "ahmedabad", "jaipur", "kerala",
        "maharashtra", "karnataka", "tamil nadu", "telangana", "gujarat",
    ],
    "UAE": [
        "uae", "united arab emirates", "emirati", "dubai", "abu dhabi",
        "sharjah", "ajman", "ras al khaimah", "fujairah", "umm al quwain",
        "al ain",
    ],
    "SAU": [
        "saudi", "saudi arabia", "ksa", "riyadh", "jeddah", "dammam",
        "mecca", "makkah", "medina", "madinah", "khobar", "الرياض", "السعودية",
    ],
    "USA": [
        "usa", "united states", "u.s.", "american", "new york", "los angeles",
        "chicago", "houston", "washington dc", "san francisco", "california", "texas",
    ],
    "GBR": [
        "uk", "united kingdom", "britain", "great britain", "british", "england",
        "scotland", "wales", "northern ireland", "london", "manchester", "birmingham",
        "glasgow", "edinburgh",
    ],
}
COUNTRY_ALIASES = {
    "IN": "IND", "INDIA": "IND",
    "AE": "UAE", "UNITED ARAB EMIRATES": "UAE",
    "SA": "SAU", "KSA": "SAU", "SAUDI ARABIA": "SAU",
    "US": "USA", "UNITED STATES": "USA",
    "UK": "GBR", "GB": "GBR", "UNITED KINGDOM": "GBR",
}


def normalize_search_term(term: str) -> str:
    advanced_tokens = (
        " from:", " to:", " since_time:", " until_time:",
        " min_faves:", " filter:", " lang:", " OR ",
    )
    if term.startswith('"') or any(token in f" {term} " for token in advanced_tokens):
        return term
    if term.startswith("#") or " " not in term:
        return term
    return f'"{term}"'


def iter_windows(request: TwitterKeywordScrapeRequest) -> Iterator[tuple[datetime, datetime]]:
    cursor = datetime.combine(request.start_date, time.min, tzinfo=UTC)
    final_end = datetime.combine(request.end_date + timedelta(days=1), time.min, tzinfo=UTC)
    while cursor < final_end:
        window_end = min(cursor + timedelta(days=request.window_days), final_end)
        yield cursor, window_end
        cursor = window_end


def build_query(
    keyword: str,
    start: datetime,
    end: datetime,
    request: TwitterKeywordScrapeRequest,
) -> str:
    parts = [
        normalize_search_term(keyword),
        f"since_time:{int(start.timestamp())}",
        f"until_time:{int(end.timestamp())}",
    ]
    if request.lang:
        parts.append(f"lang:{request.lang}")
    if request.location_query:
        parts.append(request.location_query)
    if request.exclude_retweets:
        parts.append("-filter:retweets")
    if request.exclude_replies:
        parts.append("-filter:replies")
    return " ".join(parts)


def _country_pattern(request: TwitterKeywordScrapeRequest) -> re.Pattern | None:
    if not request.filter_by_country:
        return None
    country = COUNTRY_ALIASES.get(request.country or "", request.country or "")
    terms = request.country_filter_terms or COUNTRY_FILTER_TERMS.get(country)
    if not terms:
        raise TwitterScrapeError(
            f"No built-in filter terms for {request.country}; provide country_filter_terms"
        )
    escaped = "|".join(re.escape(term) for term in terms if term.strip())
    if not escaped:
        raise TwitterScrapeError("country_filter_terms cannot be empty")
    return re.compile(rf"(?<!\w)({escaped})(?!\w)", re.IGNORECASE)


def _country_match_source(
    tweet: dict[str, Any],
    pattern: re.Pattern | None,
) -> str | None:
    if pattern is None:
        return None
    author = tweet.get("author") or {}
    for source, value in {
        "author_location": author.get("location"),
        "author_description": author.get("description"),
        "tweet_text": tweet.get("text"),
    }.items():
        if value and pattern.search(str(value)):
            return source
    return None


def _tweet_datetime(value: Any) -> datetime | None:
    if not value:
        return None
    if isinstance(value, datetime):
        return value.astimezone(UTC) if value.tzinfo else value.replace(tzinfo=UTC)
    for parser in (
        parsedate_to_datetime,
        lambda item: datetime.fromisoformat(item.replace("Z", "+00:00")),
    ):
        try:
            result = parser(str(value))
            return result.astimezone(UTC) if result.tzinfo else result.replace(tzinfo=UTC)
        except Exception:
            pass
    return None


def normalize_tweet(
    tweet: dict[str, Any],
    keyword: str,
    query: str,
    start: datetime,
    end: datetime,
    request: TwitterKeywordScrapeRequest,
    country_pattern: re.Pattern | None = None,
) -> TwitterKeywordPost | None:
    post_id = str(tweet.get("id") or "")
    if not post_id:
        return None
    author = tweet.get("author") or {}
    entities = tweet.get("entities") or {}
    hashtags = [item.get("text") for item in entities.get("hashtags", []) if isinstance(item, dict) and item.get("text")]
    mentions = [
        item.get("screen_name") or item.get("userName") or item.get("name")
        for item in entities.get("user_mentions", []) if isinstance(item, dict)
    ]
    urls = [
        item.get("expanded_url") or item.get("url")
        for item in entities.get("urls", []) if isinstance(item, dict)
    ]
    return TwitterKeywordPost(
        id=post_id,
        keyword=keyword,
        search_query=query,
        username=author.get("userName"),
        author_name=author.get("name"),
        author_id=str(author["id"]) if author.get("id") is not None else None,
        author_location=author.get("location"),
        country_match_source=_country_match_source(tweet, country_pattern),
        text=tweet.get("text"),
        url=tweet.get("url"),
        uploaded_at=_tweet_datetime(tweet.get("createdAt")),
        views=tweet.get("viewCount") or 0,
        replies=tweet.get("replyCount") or 0,
        retweet=tweet.get("retweetCount") or 0,
        likes=tweet.get("likeCount") or 0,
        quotes=tweet.get("quoteCount") or 0,
        bookmarks=tweet.get("bookmarkCount") or 0,
        lang=tweet.get("lang"),
        is_reply=tweet.get("isReply"),
        conversation_id=str(tweet["conversationId"]) if tweet.get("conversationId") is not None else None,
        hashtags=json.dumps(hashtags, ensure_ascii=False),
        mentions=json.dumps([item for item in mentions if item], ensure_ascii=False),
        expanded_urls=json.dumps([item for item in urls if item], ensure_ascii=False),
        window_start=start.date(),
        window_end=(end - timedelta(seconds=1)).date(),
        last_updated=datetime.now(UTC),
        project=request.project,
        country=request.country,
        industry=request.industry,
    )


async def _advanced_search_page(
    client: httpx.AsyncClient,
    query: str,
    cursor: str,
    query_type: str,
) -> dict[str, Any]:
    settings = get_settings()
    for attempt in range(4):
        try:
            response = await client.get(
                settings.TWITTER_KEYWORD_API_URL,
                headers={"X-API-Key": settings.TWITTER_API_KEY},
                params={"query": query, "queryType": query_type, "cursor": cursor},
            )
            if response.status_code not in {429, 500, 502, 503, 504}:
                response.raise_for_status()
                payload = response.json()
                if not isinstance(payload, dict):
                    raise TwitterScrapeError("Twitter keyword search returned invalid data")
                return payload
        except (httpx.RequestError, httpx.HTTPStatusError) as exc:
            if attempt == 3:
                raise TwitterScrapeError("Twitter keyword search request failed") from exc
        if attempt < 3:
            await asyncio.sleep(2 ** (attempt + 1))
    raise TwitterScrapeError("Twitter keyword search request failed")


async def scrape_keyword(
    keyword: str,
    request: TwitterKeywordScrapeRequest,
) -> list[TwitterKeywordPost]:
    if not get_settings().TWITTER_API_KEY:
        raise ScraperConfigurationError("TWITTER_API_KEY is not configured")
    country_pattern = _country_pattern(request)
    posts: dict[tuple[str, str], TwitterKeywordPost] = {}
    async with httpx.AsyncClient(timeout=60) as client:
        for window_start, window_end in iter_windows(request):
            query = build_query(keyword, window_start, window_end, request)
            cursor = ""
            seen_cursors: set[str] = set()
            page_number = 0
            while True:
                page_number += 1
                payload = await _advanced_search_page(client, query, cursor, request.query_type)
                tweets = payload.get("tweets") or (payload.get("data") or {}).get("tweets") or []
                if not isinstance(tweets, list):
                    raise TwitterScrapeError(f"Twitter keyword search returned invalid tweets for {keyword}")
                for tweet in tweets:
                    match_source = _country_match_source(tweet, country_pattern)
                    if request.filter_by_country and not match_source:
                        continue
                    post = normalize_tweet(
                        tweet,
                        keyword,
                        query,
                        window_start,
                        window_end,
                        request,
                        country_pattern,
                    )
                    if post:
                        posts[(post.id, post.keyword)] = post
                has_next = bool(payload.get("has_next_page") or payload.get("hasNextPage"))
                next_cursor = payload.get("next_cursor") or payload.get("nextCursor") or ""
                if (
                    not has_next
                    or not next_cursor
                    or next_cursor in seen_cursors
                    or (
                        request.max_pages_per_window is not None
                        and page_number >= request.max_pages_per_window
                    )
                ):
                    break
                seen_cursors.add(next_cursor)
                cursor = next_cursor
                await asyncio.sleep(0.5)
            await asyncio.sleep(0.5)
    return list(posts.values())


async def scrape_keywords(request: TwitterKeywordScrapeRequest) -> list[TwitterKeywordPost]:
    # Keep keyword/window traffic modest to avoid API rate-limit bursts.
    semaphore = asyncio.Semaphore(2)

    async def scrape(keyword: str) -> list[TwitterKeywordPost]:
        async with semaphore:
            return await scrape_keyword(keyword, request)

    batches = await asyncio.gather(*(scrape(keyword) for keyword in request.keywords))
    unique = {(post.id, post.keyword): post for batch in batches for post in batch}
    return list(unique.values())


def _persist_keyword_posts_sync(posts: list[TwitterKeywordPost]) -> None:
    from shared.database import Database

    table = get_settings().TWITTER_KEYWORD_POSTS_TABLE
    columns = (
        "id", "keyword", "search_query", "username", "author_name", "author_id",
        "author_location", "country_match_source", "text", "url", "uploaded_at",
        "views", "replies", "retweet", "likes", "quotes", "bookmarks", "lang",
        "is_reply", "conversation_id", "hashtags", "mentions", "expanded_urls",
        "window_start", "window_end", "last_updated", "project", "country", "industry",
    )
    column_sql = ", ".join(columns)
    value_sql = ", ".join(f":{column}" for column in columns)
    statement = text(
        f"""
        INSERT INTO {table} ({column_sql})
        SELECT {value_sql}
        WHERE NOT EXISTS (
            SELECT 1 FROM {table}
            WHERE id = :id AND keyword = :keyword
        )
        """
    )
    rows = [post.model_dump() for post in posts]
    if rows:
        with Database("raw_data").get_engine().begin() as connection:
            connection.execute(statement, rows)


async def persist_keyword_posts(posts: list[TwitterKeywordPost]) -> None:
    if posts:
        await asyncio.to_thread(_persist_keyword_posts_sync, posts)
