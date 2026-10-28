from pathlib import Path

import pytest
from sqlalchemy import text

from services.trends_real_estate_service.tests.db.conftest import (
    CONTRACT,
    TEST_POSTGRES_DSN,
    _apply,
)

pytestmark = pytest.mark.skipif(
    not TEST_POSTGRES_DSN,
    reason="Set TEST_POSTGRES_DSN to a scratch Postgres database to run the SQL tests.",
)

_MIGRATION = (Path(__file__).resolve().parents[4]
              / "shared" / "migrations" / "012_create_realestate_intel_trend_posts.sql")


@pytest.fixture()
def with_trend_posts(seeded):
    with seeded.begin() as conn:
        _apply(conn, _MIGRATION)
    return seeded


def test_trend_posts_exposes_the_column_contract(with_trend_posts):
    with with_trend_posts.connect() as conn:
        columns = list(conn.execute(
            text("SELECT * FROM realestate_intel.trend_posts LIMIT 0")).keys())
    assert columns == CONTRACT


def test_trend_posts_has_no_duplicate_post_keys(with_trend_posts):
    with with_trend_posts.connect() as conn:
        dupes = conn.execute(text(
            "SELECT count(*) FROM (SELECT platform, post_id FROM realestate_intel.trend_posts "
            "GROUP BY 1, 2 HAVING count(*) > 1) d")).scalar()
    assert dupes == 0


def test_brand_row_wins_over_community_row_for_the_same_post(with_trend_posts):
    """'ig1' is in both the brand tables and the community scrape."""
    with with_trend_posts.connect() as conn:
        source = conn.execute(text(
            "SELECT source FROM realestate_intel.trend_posts WHERE post_id = 'ig1'")).scalar()
    assert source == "brand"


def test_trend_posts_unions_every_source(with_trend_posts):
    with with_trend_posts.connect() as conn:
        rows = dict(conn.execute(text(
            "SELECT source, count(*) FROM realestate_intel.trend_posts GROUP BY 1")).all())
    # 5 brand posts (ig1, ig2, tt1, tw1, linkedin 42), 1 community-only (c1),
    # 0 influencer. 'ig1' is deduped to the brand side.
    assert rows == {"brand": 5, "community": 1}


def test_trend_posts_total_is_union_minus_collisions(with_trend_posts):
    with with_trend_posts.connect() as conn:
        total = conn.execute(text("SELECT count(*) FROM realestate_intel.trend_posts")).scalar()
        brand = conn.execute(text("SELECT count(*) FROM realestate_intel.brand_posts")).scalar()
        community = conn.execute(text("SELECT count(*) FROM realestate_intel.community_posts")).scalar()
    assert total == brand + community - 1  # one collision: ig1


def test_trend_posts_migration_is_idempotent(with_trend_posts):
    with with_trend_posts.begin() as conn:
        _apply(conn, _MIGRATION)
        _apply(conn, _MIGRATION)
        exists = conn.execute(text(
            "SELECT count(*) FROM information_schema.views "
            "WHERE table_schema = 'realestate_intel' AND table_name = 'trend_posts'")).scalar()
    assert exists == 1
