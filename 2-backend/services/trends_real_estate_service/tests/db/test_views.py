"""The realestate_intel views, exercised against a scratch Postgres.

Fixtures (scratch_engine, seeded, _apply, TEST_POSTGRES_DSN) come from
conftest.py in this directory.
"""
import pytest
from sqlalchemy import text

from services.trends_real_estate_service.tests.db.conftest import (
    _MIGRATION,
    CONTRACT,
    TEST_POSTGRES_DSN,
    _apply,
)

pytestmark = pytest.mark.skipif(
    not TEST_POSTGRES_DSN,
    reason="Set TEST_POSTGRES_DSN to a scratch Postgres database to run the SQL tests.",
)

@pytest.mark.parametrize("view", ["brand_posts", "influencer_posts", "community_posts"])
def test_view_exposes_the_column_contract_in_order(seeded, view):
    with seeded.connect() as conn:
        columns = list(conn.execute(
            text(f"SELECT * FROM realestate_intel.{view} LIMIT 0")).keys())
    assert columns == CONTRACT


def test_brand_posts_does_not_double_count_dual_project_accounts(seeded):
    """'aldar' is registered under both brand projects but has one post."""
    with seeded.connect() as conn:
        count = conn.execute(text(
            "SELECT count(*) FROM realestate_intel.brand_posts WHERE post_id = 'ig1'")).scalar()
    assert count == 1


def test_brand_posts_spans_four_platforms(seeded):
    with seeded.connect() as conn:
        rows = dict(conn.execute(text(
            "SELECT platform, count(*) FROM realestate_intel.brand_posts GROUP BY 1")).all())
    assert rows == {"instagram": 2, "linkedin": 1, "twitter": 2, "tiktok": 1}


def test_brand_posts_excludes_accounts_from_other_projects(seeded):
    with seeded.connect() as conn:
        authors = [r[0] for r in conn.execute(text(
            "SELECT DISTINCT author_username FROM realestate_intel.brand_posts")).all()]
    assert "randomperson" not in authors


def test_brand_posts_maps_country_to_iso2(seeded):
    with seeded.connect() as conn:
        rows = dict(conn.execute(text(
            "SELECT author_username, country FROM realestate_intel.brand_posts "
            "WHERE platform = 'instagram'")).all())
    assert rows == {"aldar": "AE", "roshnksa": "SA"}


def test_brand_posts_casts_linkedin_integer_id_and_date(seeded):
    with seeded.connect() as conn:
        row = conn.execute(text(
            "SELECT post_id, posted_at FROM realestate_intel.brand_posts "
            "WHERE platform = 'linkedin'")).one()
    assert row[0] == "42"
    assert row[1].year == 2025


def test_brand_posts_computes_engagement_per_platform(seeded):
    with seeded.connect() as conn:
        rows = dict(conn.execute(text(
            "SELECT platform, engagement_total FROM realestate_intel.brand_posts "
            "WHERE post_id IN ('tt1', 'tw1', '42')")).all())
    # tiktok likes+comments+shares = 6+1+2, twitter likes+replies+retweet = 3+1+2,
    # linkedin likes+comments+shares = 4+2+1
    assert rows == {"tiktok": 9, "twitter": 6, "linkedin": 7}


def test_brand_posts_extracts_hashtags_from_caption(seeded):
    with seeded.connect() as conn:
        tags = conn.execute(text(
            "SELECT hashtags FROM realestate_intel.brand_posts WHERE post_id = 'ig1'")).scalar()
    assert sorted(tags) == ["dubai", "luxury"]


def test_brand_posts_builds_instagram_media_key(seeded):
    with seeded.connect() as conn:
        keys = conn.execute(text(
            "SELECT media_keys FROM realestate_intel.brand_posts WHERE post_id = 'ig1'")).scalar()
    assert keys == ["media/instagram/ig1.jpg"]


def test_brand_posts_has_no_media_for_linkedin(seeded):
    with seeded.connect() as conn:
        keys = conn.execute(text(
            "SELECT media_keys FROM realestate_intel.brand_posts WHERE platform = 'linkedin'")).scalar()
    assert keys is None


def test_brand_posts_twitter_dedup_prefers_the_freshest_scrape(seeded):
    """'tw2' is stored twice under two username castings (the production
    424-id duplication case), with different engagement metrics and
    last_updated dates. The DISTINCT ON tie-break must pick the row with the
    later last_updated, not whichever username string sorts first."""
    with seeded.connect() as conn:
        row = conn.execute(text(
            "SELECT likes, views, comments, engagement_total, author_username "
            "FROM realestate_intel.brand_posts WHERE post_id = 'tw2'")).one()
    assert row.likes == 88
    assert row.views == 999
    assert row.comments == 40
    assert row.engagement_total == 88 + 40 + 15


def test_influencer_posts_is_empty_but_resolves(seeded):
    """The 28 influencer profiles are registered; their posts are not scraped
    yet. The view must resolve and return nothing rather than error."""
    with seeded.connect() as conn:
        count = conn.execute(text(
            "SELECT count(*) FROM realestate_intel.influencer_posts")).scalar()
    assert count == 0


def test_community_posts_filters_on_the_real_estate_keyword(seeded):
    with seeded.connect() as conn:
        ids = sorted(r[0] for r in conn.execute(text(
            "SELECT post_id FROM realestate_intel.community_posts")).all())
    assert ids == ["c1", "ig1"]


def test_community_posts_keeps_brand_authored_history(seeded):
    """Brand-authored community posts are NOT excluded: the brand tables only
    reach back to 2025-01, so a username-level exclusion would delete years of
    developer history that has no replacement."""
    with seeded.connect() as conn:
        authors = [r[0] for r in conn.execute(text(
            "SELECT author_username FROM realestate_intel.community_posts")).all()]
    assert "aldar" in authors


def test_community_posts_country_comes_from_post_geo(seeded):
    """post_geo is empty at this point, so country is NULL. Task 7 fills it."""
    with seeded.connect() as conn:
        countries = [r[0] for r in conn.execute(text(
            "SELECT country FROM realestate_intel.community_posts")).all()]
    assert len(countries) == 2
    assert all(c is None for c in countries)


def test_migration_is_idempotent(scratch_engine):
    with scratch_engine.begin() as conn:
        _apply(conn, _MIGRATION)
        _apply(conn, _MIGRATION)
        count = conn.execute(text(
            "SELECT count(*) FROM information_schema.views WHERE table_schema = 'realestate_intel'")).scalar()
    assert count == 3
