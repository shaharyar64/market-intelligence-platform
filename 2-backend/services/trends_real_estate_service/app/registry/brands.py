"""Canonical developer registry.

Unlike the food service, which hand-writes its brand list because nothing in
the database links a brand's Instagram account to its TikTok one, real estate
already has that mapping: realestate_dbh.social_data carries
brand_name -> username -> platform for 23 brands. It covers 23 of the 48
brand accounts; the rest are resolved from the profile's display name and
reported for human confirmation rather than guessed silently.
"""
import logging
import re
import unicodedata

from services.trends_real_estate_service.app.db import store

logger = logging.getLogger("registry.brands")


def slugify(name: str) -> str:
    """A stable ASCII key for a brand name.

    Names in this dataset are routinely bilingual ("Binghatti  بن غاطي"), so
    non-ASCII is stripped rather than transliterated. A name with no ASCII at
    all yields "", and the caller falls back to the username.

    Stripping non-Latin script or punctuation routinely leaves a stray
    single-character token behind (e.g. "ROSHN Group l مجموعة روشن" -> "roshn
    group l"). Those tokens are dropped, unless doing so would empty the slug
    entirely — a name that is nothing but single-character tokens ("A -- B")
    keeps them rather than collapsing to "".
    """
    ascii_only = unicodedata.normalize("NFKD", name).encode("ascii", "ignore").decode()
    tokens = [t for t in re.split(r"[^a-z0-9]+", ascii_only.lower()) if t]
    kept = [t for t in tokens if len(t) > 1]
    return "_".join(kept or tokens)


_SOCIAL_DATA_SQL = """
    SELECT brand_name, platform, username, COALESCE(followers, 0) AS followers
      FROM realestate_dbh.social_data
     WHERE username IS NOT NULL
"""

_BRAND_ACCOUNTS_SQL = """
    SELECT DISTINCT platform, author_username
      FROM realestate_intel.brand_posts
"""

_PROFILE_NAMES_SQL = """
    SELECT 'instagram' AS platform, lower(username) AS username,
           full_name AS display_name, COALESCE(followers, 0) AS followers, project
      FROM public.instagram_profile
     WHERE project IN ('realestate_dbh', 'realestate_trends')
    UNION ALL
    SELECT 'tiktok', lower(username), name, COALESCE(followers, 0), project
      FROM public.tiktok_profiles
     WHERE project IN ('realestate_dbh', 'realestate_trends')
    UNION ALL
    SELECT 'twitter', lower(username), full_name, COALESCE(followers, 0), project
      FROM public.twitter_profiles
     WHERE project IN ('realestate_dbh', 'realestate_trends')
    UNION ALL
    SELECT 'linkedin', universal_name, company_name, COALESCE(follower_count, 0), project
      FROM public.linkedin_profiles
     WHERE project IN ('realestate_dbh', 'realestate_trends')
"""


def _existing_keys() -> dict[str, str]:
    """username -> the brand_key it is already stored under, if any.

    Read before the rebuild so a group that already exists keeps its key. Only
    the username is used as the lookup, matching how groups are formed.
    """
    try:
        rows = store.run_query(
            "SELECT username, brand_key FROM realestate_intel.brand")
    except Exception:
        logger.exception("could not read existing brand keys - rebuilding from scratch")
        return {}
    return {r["username"]: r["brand_key"] for r in rows if r.get("username")}


def _write_rows(rows: list[dict]) -> None:
    from sqlalchemy import text

    if not rows:
        return
    with store.engine().begin() as conn:
        conn.execute(text("TRUNCATE realestate_intel.brand"))
        conn.execute(
            text("INSERT INTO realestate_intel.brand "
                 "(brand_key, brand_name, platform, username, followers, source_project, resolution) "
                 "VALUES (:brand_key, :brand_name, :platform, :username, :followers, "
                 ":source_project, :resolution)"),
            rows,
        )


def load_registry() -> dict:
    """Populate realestate_intel.brand and report how each row was resolved.

    A username is grouped across every platform it appears under in
    brand_posts *before* a brand_key is assigned, so the same account never
    fragments into different brands just because each platform's own display
    name is formatted differently (e.g. Instagram's "ROSHN Group l مجموعة
    روشن" vs Twitter's "ROSHN l روشن" vs LinkedIn's "ROSHN Group" must all
    become one brand_key, not three).

    Within a username group: if any (platform, username) in the group is
    curated in realestate_dbh.social_data, that curated brand_name wins for
    every row in the group — ties among multiple curated rows in one group
    are broken deterministically by platform name. Otherwise the group's
    brand_name is the profile display name (across the group's platforms)
    whose slugify() is longest, tie-broken alphabetically by the name itself,
    which prefers the most informative spelling ("ROSHN Group" over "ROSHN").
    If no display name yields a non-empty slug, the username itself is used
    as both name and key — nothing is dropped, so the account still appears
    in brand rollups.

    `resolution` reflects where the group's NAME came from, so a platform's
    own row can be 'social_data' even when that platform's own account was
    not the curated one — the group's name was.
    """
    curated = {
        (r["platform"], (r["username"] or "").lower()): r
        for r in store.run_query(_SOCIAL_DATA_SQL)
    }
    profiles = {
        (r["platform"], (r["username"] or "").lower()): r
        for r in store.run_query(_PROFILE_NAMES_SQL)
    }

    groups: dict[str, list[tuple[str, str]]] = {}
    for account in store.run_query(_BRAND_ACCOUNTS_SQL):
        key = (account["platform"], (account["author_username"] or "").lower())
        groups.setdefault(key[1], []).append(key)

    existing_keys = _existing_keys()
    rows: list[dict] = []
    auto_resolved: list[dict] = []
    unresolved: list[dict] = []
    for username, group_accounts in groups.items():
        curated_hits = sorted(
            (curated[k] for k in group_accounts if k in curated),
            key=lambda r: r["platform"],
        )
        if curated_hits:
            name = curated_hits[0]["brand_name"]
            resolution = "social_data"
        else:
            display_names = [
                display_name
                for k in group_accounts
                for display_name in [(profiles.get(k, {}).get("display_name") or "").strip()]
                if display_name
            ]
            name = (min(display_names, key=lambda n: (-len(slugify(n)), n))
                    if display_names else username)
            resolution = "auto"

        # A key already in use for this username group wins over a freshly
        # derived one. brand_key is derived from whichever current display name
        # has the longest slug, and post_analysis stores it as a copy that
        # nothing reconciles - so a scraper renaming a profile, or a platform
        # dropping out of the project list, would mint a different key and
        # silently detach every row already enriched under the old one.
        derived = slugify(name) or username
        brand_key = existing_keys.get(username) or derived
        group_is_unresolved = resolution == "auto" and slugify(name) == ""

        for key in group_accounts:
            profile = profiles.get(key, {})
            curated_row = curated.get(key)
            row = {
                "brand_key": brand_key,
                "brand_name": name,
                "platform": key[0],
                "username": key[1],
                "followers": (curated_row or profile).get("followers", 0) or 0,
                "source_project": profile.get("project"),
                "resolution": resolution,
            }
            rows.append(row)
            if resolution == "auto":
                (unresolved if group_is_unresolved else auto_resolved).append(row)

    _write_rows(rows)
    return {"seeded": sum(1 for r in rows if r["resolution"] == "social_data"),
            "auto_resolved": auto_resolved,
            "unresolved": unresolved}


def account_to_brand_key(platform: str, username: str) -> str | None:
    rows = store.run_query(
        "SELECT brand_key FROM realestate_intel.brand "
        "WHERE platform = :p AND username = lower(:u)",
        {"p": platform, "u": username},
    )
    return rows[0]["brand_key"] if rows else None


# ── the identity API the enrichment and trends modules expect ────────────
# food_intelligence_service resolves these from a hand-written BRANDS list
# because nothing in its database links a brand's Instagram account to its
# TikTok one. Real estate does not have that problem: realestate_intel.brand
# already holds the cross-platform mapping, so these read from the table
# rather than from a literal. Same contract, different source of truth.

_INFLUENCER_SQL = """
    SELECT DISTINCT lower(username) AS username
      FROM public.instagram_profile
     WHERE project = :project
"""


def account_to_identity(platform: str, username: str | None) -> dict | None:
    """The account behind a post: a tracked developer, a tracked influencer,
    or None.

    Developers win a name collision, since a developer's own account is the
    stronger claim on it.
    """
    if not username:
        return None

    rows = store.run_query(
        "SELECT brand_key, brand_name FROM realestate_intel.brand "
        "WHERE platform = :p AND username = lower(:u)",
        {"p": platform, "u": username},
    )
    if rows:
        return {"key": rows[0]["brand_key"], "name": rows[0]["brand_name"],
                "account_type": "brand"}

    if platform != "instagram":
        return None

    from services.trends_real_estate_service.app.core.config import get_settings

    influencers = {
        r["username"]
        for r in store.run_query(_INFLUENCER_SQL,
                                 {"project": get_settings().INFLUENCER_PROJECT})
    }
    key = username.lower()
    if key in influencers:
        return {"key": key, "name": username, "account_type": "influencer"}
    return None


def list_brands() -> list[dict]:
    """One entry per canonical developer, with the accounts it spans."""
    rows = store.run_query("""
        SELECT brand_key, min(brand_name) AS brand_name,
               array_agg(DISTINCT platform ORDER BY platform) AS platforms
          FROM realestate_intel.brand
         GROUP BY brand_key
         ORDER BY 2
    """)
    return [{"key": r["brand_key"], "name": r["brand_name"],
             "platforms": r["platforms"]} for r in rows]
