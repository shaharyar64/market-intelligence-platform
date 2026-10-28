"""Scratch-Postgres fixtures for the SQL tests.

These lived in test_views.py and were imported by test_trend_posts.py, which
made `seeded` both a module-level name and a fixture parameter in the same file
- a redefinition ruff flags and a papered-over `# noqa: F401`. In a conftest
pytest injects them by name, so neither module imports the other.
"""
import os
from pathlib import Path

import pytest
from sqlalchemy import create_engine, text
from sqlalchemy.engine import make_url

TEST_POSTGRES_DSN = os.environ.get("TEST_POSTGRES_DSN")

pytestmark = pytest.mark.skipif(
    not TEST_POSTGRES_DSN,
    reason="Set TEST_POSTGRES_DSN to a scratch Postgres database to run the SQL tests.",
)

_MIGRATION = (Path(__file__).resolve().parents[4]
              / "shared" / "migrations" / "011_create_realestate_intel_schema.sql")

_SCRATCH_MARKERS = ("scratch", "test", "tmp")

# Minimal stand-ins for the production public tables. Column types match
# production exactly, because three of them need casts the view must get
# right: linkedin_posts.id is integer, and both linkedin_posts.uploaded_at
# and twitter_posts.uploaded_at are date, not timestamptz.
_STUBS = {
    "instagram_profile": "username text, followers bigint, country text, industry text, project text",
    "tiktok_profiles": "username varchar, followers bigint, country varchar, industry varchar, project varchar",
    "twitter_profiles": "username text, followers bigint, country text, industry text, project text",
    "linkedin_profiles": "universal_name text, company_name text, follower_count integer, country text, industry text, project varchar",
    "instagram_posts": "id text, username text, uploaded_at timestamptz, caption text, views bigint, comments bigint, likes bigint",
    "tiktok_posts": "id text, title text, views bigint, likes bigint, comments bigint, shares bigint, bookmarks bigint, uploaded_at_formatted timestamptz, post_url text, username text",
    "twitter_posts": "id text, username text, text text, uploaded_at date, views bigint, replies bigint, retweet bigint, likes bigint, last_updated date",
    "linkedin_posts": "id integer, post_text text, post_url text, likes integer, shares integer, comments integer, uploaded_at date, universal_name text",
    "community_posts": ("platform text, post_id text, source text, post_url text, author_username text, "
                        "caption text, hashtags text[], search_keywords text[], likes bigint, comments bigint, "
                        "views bigint, shares bigint, engagement_total bigint, media_keys text[], "
                        "country text, posted_at timestamptz"),
}


def _assert_scratch_database(dsn: str) -> None:
    name = make_url(dsn).database or ""
    if not any(marker in name.lower() for marker in _SCRATCH_MARKERS):
        raise RuntimeError(
            f"Refusing to run: TEST_POSTGRES_DSN points at database {name!r}, which does not look "
            f"like a scratch database. These tests DROP the realestate_intel schema and the public "
            f"stub tables. Point TEST_POSTGRES_DSN at a throwaway database whose name contains one "
            f"of {_SCRATCH_MARKERS}."
        )


def _apply(conn, path: Path) -> None:
    sql = path.read_text(encoding="utf-8")
    for statement in [s.strip() for s in sql.split(";") if s.strip()]:
        conn.execute(text(statement))


@pytest.fixture(scope="module")
def scratch_engine():
    _assert_scratch_database(TEST_POSTGRES_DSN)
    engine = create_engine(TEST_POSTGRES_DSN, pool_pre_ping=True)
    with engine.begin() as conn:
        conn.execute(text("DROP SCHEMA IF EXISTS realestate_intel CASCADE"))
        for table in _STUBS:
            conn.execute(text(f"DROP TABLE IF EXISTS public.{table} CASCADE"))
        for table, columns in _STUBS.items():
            conn.execute(text(f"CREATE TABLE public.{table} ({columns})"))
        _apply(conn, _MIGRATION)
    yield engine
    with engine.begin() as conn:
        conn.execute(text("DROP SCHEMA IF EXISTS realestate_intel CASCADE"))
        for table in _STUBS:
            conn.execute(text(f"DROP TABLE IF EXISTS public.{table} CASCADE"))
    engine.dispose()


@pytest.fixture()
def seeded(scratch_engine):
    with scratch_engine.begin() as conn:
        for table in _STUBS:
            conn.execute(text(f"TRUNCATE public.{table}"))

        # 'aldar' is deliberately registered under BOTH brand projects, the
        # duplicate-profile case from the spec. It has exactly one post, so a
        # view that joins profiles naively will report two.
        conn.execute(text(
            "INSERT INTO public.instagram_profile (username, followers, country, industry, project) VALUES "
            "('aldar', 100, 'UAE', 'Realestate', 'realestate_dbh'),"
            "('aldar', 100, 'UAE', 'Real Estate', 'realestate_trends'),"
            "('roshnksa', 50, 'KSA', 'Real Estate', 'realestate_trends'),"
            "('hamdy_s', 900, 'KSA', 'Real Estate', 'realestate_trends_influencers'),"
            "('randomperson', 5, 'UAE', 'Other', 'realestate_dbh')"))
        conn.execute(text(
            "INSERT INTO public.instagram_posts (id, username, uploaded_at, caption, views, comments, likes) VALUES "
            "('ig1', 'aldar', '2025-06-01T00:00:00Z', 'Waterfront living #luxury #dubai', 10, 2, 5),"
            "('ig2', 'roshnksa', '2025-06-02T00:00:00Z', 'New community in Riyadh', 20, 3, 7),"
            "('ig3', 'randomperson', '2025-06-03T00:00:00Z', 'unrelated', 1, 1, 1)"))

        conn.execute(text(
            "INSERT INTO public.linkedin_profiles (universal_name, company_name, follower_count, country, industry, project) "
            "VALUES ('emaar-properties', 'Emaar', 1000, 'UAE', 'Real Estate', 'realestate_dbh')"))
        conn.execute(text(
            "INSERT INTO public.linkedin_posts (id, post_text, post_url, likes, shares, comments, uploaded_at, universal_name) "
            "VALUES (42, 'Quarterly results', 'https://li.test/42', 4, 1, 2, DATE '2025-08-01', 'emaar-properties')"))

        conn.execute(text(
            "INSERT INTO public.twitter_profiles (username, followers, country, industry, project) "
            "VALUES ('damacofficial', 700, 'UAE', 'Realestate', 'realestate_dbh')"))
        conn.execute(text(
            "INSERT INTO public.twitter_posts (id, username, text, uploaded_at, views, replies, retweet, likes, last_updated) "
            "VALUES ('tw1', 'damacofficial', 'Launch day', DATE '2025-05-01', 9, 1, 2, 3, DATE '2025-05-02')"))
        conn.execute(text(
            # Duplicate tweet id under two username castings (the production
            # 424-id duplication case), with DIFFERENT engagement metrics and
            # last_updated dates. The fresher row (tw2b, last_updated 2025-07-01)
            # must win the DISTINCT ON tie-break, not whichever username sorts
            # first.
            "INSERT INTO public.twitter_posts (id, username, text, uploaded_at, views, replies, retweet, likes, last_updated) VALUES "
            "('tw2', 'damacofficial', 'Stale scrape', DATE '2025-05-01', 100, 10, 5, 20, DATE '2025-05-01'),"
            "('tw2', 'DAMACOfficial', 'Fresh scrape', DATE '2025-05-01', 999, 40, 15, 88, DATE '2025-07-01')"))

        conn.execute(text(
            "INSERT INTO public.tiktok_profiles (username, followers, country, industry, project) "
            "VALUES ('binghatti', 300, 'UAE', 'Realestate', 'realestate_dbh')"))
        conn.execute(text(
            "INSERT INTO public.tiktok_posts (id, title, views, likes, comments, shares, bookmarks, "
            "uploaded_at_formatted, post_url, username) "
            "VALUES ('tt1', 'Tower tour', 50, 6, 1, 2, 0, '2025-04-01T00:00:00Z', 'https://tt.test/1', 'binghatti')"))

        conn.execute(text(
            "INSERT INTO public.community_posts (platform, post_id, source, post_url, author_username, caption, "
            "hashtags, search_keywords, likes, comments, views, shares, engagement_total, media_keys, country, posted_at) VALUES "
            "('instagram', 'c1', 'community', 'https://ig.test/c1', 'someagent', 'Villa tour', "
            " ARRAY['villa'], ARRAY['real_estate'], 3, 1, 8, 0, 4, ARRAY['community/instagram/c1/0.jpg'], NULL, '2024-02-01T00:00:00Z'),"
            "('instagram', 'c2', 'community', 'https://ig.test/c2', 'foodblogger', 'Lunch', "
            " ARRAY['food'], ARRAY['Food'], 2, 0, 5, 0, 2, ARRAY['community/instagram/c2/0.jpg'], NULL, '2024-02-02T00:00:00Z'),"
            "('instagram', 'ig1', 'community', 'https://ig.test/ig1', 'aldar', 'Waterfront living', "
            " ARRAY['luxury'], ARRAY['real_estate'], 3, 1, 8, 0, 4, ARRAY['community/instagram/ig1/0.jpg'], NULL, '2025-06-01T00:00:00Z')"))
    return scratch_engine


# The column contract both view test modules assert against.
CONTRACT = ["platform", "post_id", "source", "post_url", "author_username", "caption",
            "hashtags", "likes", "comments", "views", "engagement_total", "media_keys",
            "country", "posted_at"]
