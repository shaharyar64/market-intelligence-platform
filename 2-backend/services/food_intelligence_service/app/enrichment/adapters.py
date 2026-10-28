"""Per-platform column map + normalization.

The four platforms diverge in table/column names (see the schema audit). This
config is the single source of truth for those differences so the rest of the
service is platform-agnostic. Phase 1 wires Instagram + TikTok; LinkedIn/Twitter
slot in by adding entries here.
"""
from datetime import datetime, timezone

from services.food_intelligence_service.app.registry.brands import account_to_identity

PLATFORM_CONFIG: dict[str, dict] = {
    "instagram": {
        "posts_table": "instagram_posts",
        "profile_table": "instagram_profile",
        "profile_join_key": "username",
        # instagram_posts has no URL column — build it from the post id (shortcode)
        "post_url_template": "https://www.instagram.com/p/{post_id}",
        "columns": {
            "post_id": "id",
            "account_username": "username",
            "text": "caption",
            "posted_at": "uploaded_at",
            "likes": "likes",
            "comments": "comments",
            "views": "views",
            # instagram_posts has no shares/bookmarks
        },
        "profile_columns": {
            "username": "username",
            "name": "full_name",
            "followers": "followers",
            "country": "country",
            "industry": "industry",
            "is_verified": "is_verified",
        },
    },
    "tiktok": {
        "posts_table": "tiktok_posts",
        "profile_table": "tiktok_profiles",
        "profile_join_key": "username",
        # tiktok_posts has a real post_url column; keep a template as a fallback
        "post_url_template": "https://www.tiktok.com/@{account_username}/video/{post_id}",
        "columns": {
            "post_id": "id",
            "account_username": "username",
            "text": "title",
            "posted_at": "uploaded_at_formatted",
            "likes": "likes",
            "comments": "comments",
            "views": "views",
            "shares": "shares",
            "bookmarks": "bookmarks",
            "post_url": "post_url",
        },
        "profile_columns": {
            "username": "username",
            "name": "name",
            "followers": "followers",
            "country": "country",
            "industry": "industry",
            "is_verified": "verified",
        },
    },
}


def _to_int(value) -> int:
    try:
        return int(value) if value is not None else 0
    except (TypeError, ValueError):
        return 0


def _to_iso(value) -> str | None:
    if value is None:
        return None
    if isinstance(value, datetime):
        if value.tzinfo is None:
            value = value.replace(tzinfo=timezone.utc)
        return value.astimezone(timezone.utc).isoformat()
    return str(value)


def _build_post_url(platform: str, row: dict, post_id: str, account_username: str | None) -> str | None:
    """Prefer a real URL column from the source table (e.g. tiktok_posts.post_url);
    otherwise construct it from the platform URL pattern + post id
    (e.g. Instagram -> https://www.instagram.com/p/{post_id})."""
    real = row.get("post_url")
    if real:
        return str(real)
    template = PLATFORM_CONFIG.get(platform, {}).get("post_url_template")
    if template:
        return template.format(post_id=post_id, account_username=account_username or "")
    return None


def normalize_post(platform: str, row: dict) -> dict:
    """Turn a raw DB row into the common shape the agent + the analysis row expect.

    Returns a dict with brand identity resolved via the registry. If the account
    isn't in the registry, brand is None and the caller should skip/log it.
    """
    likes = _to_int(row.get("likes"))
    comments = _to_int(row.get("comments"))
    views = _to_int(row.get("views"))
    shares = _to_int(row.get("shares"))
    bookmarks = _to_int(row.get("bookmarks"))

    post_id = str(row["post_id"])
    account_username = row.get("account_username")
    brand = account_to_identity(platform, account_username)

    return {
        "post_id": post_id,
        "platform": platform,
        "account_username": account_username,
        # account_type comes from the registry now: the same pipeline enriches
        # tracked brands and tracked influencers, and the consumers downstream
        # need to tell them apart.
        "brand": brand,
        "owner": {
            "username": account_username,
            "name": brand["name"] if brand else None,
        },
        "post_url": _build_post_url(platform, row, post_id, account_username),
        "text": (row.get("text") or "").strip(),
        "posted_at": _to_iso(row.get("posted_at")),
        "engagement": {
            "likes": likes,
            "comments": comments,
            "views": views,
            "shares": shares,
            "bookmarks": bookmarks,
            # normalized cross-platform engagement (used for ranking/rollups)
            "total": likes + comments + shares + bookmarks,
        },
    }
