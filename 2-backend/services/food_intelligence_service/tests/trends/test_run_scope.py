import json
from unittest.mock import MagicMock

from services.food_intelligence_service.app.trends import run as run_mod
from services.food_intelligence_service.app.trends import store


def _client_naming(name: str):
    client = MagicMock()
    payload = {"name": name, "summary": "s", "related_themes": [],
               "product_entities": [], "is_coherent": True, "confidence": 0.9}
    client.chat.completions.create.return_value.choices = [
        MagicMock(message=MagicMock(content=json.dumps(payload)))
    ]
    return client


def _few_author_cluster_state():
    members = [
        {"platform": "ig", "post_id": str(i), "caption": "c", "hashtags": [],
         "author_username": f"a{i % 3}", "engagement_total": 0}
        for i in range(60)
    ]
    state = {
        "cluster": {
            "labels": {f"{m['platform']}:{m['post_id']}": 0 for m in members},
            "centrality": {f"{m['platform']}:{m['post_id']}": 0.5 for m in members},
            "keywords": {"0": ["k"]},
        },
    }
    return members, state


def test_tracked_run_names_a_cluster_with_few_authors():
    posts, state = _few_author_cluster_state()
    stats = run_mod.stage_name(posts, state, _client_naming("Trend"), "m",
                               min_posts=50, min_authors=0, run_id="r1")
    assert stats == {"named": 1, "skipped_small": 0, "skipped_incoherent": 0}


def test_non_tracked_run_skips_a_cluster_with_few_authors():
    posts, state = _few_author_cluster_state()
    stats = run_mod.stage_name(posts, state, _client_naming("Trend"), "m",
                               min_posts=50, min_authors=30, run_id="r1")
    assert stats == {"named": 0, "skipped_small": 1, "skipped_incoherent": 0}


def test_run_key_prefers_country_then_tracked_then_cohort():
    assert run_mod.resolve_run_key(cohort="all", tracked=True, country="SA") == "sa"
    assert run_mod.resolve_run_key(cohort="all", tracked=True, country=None) == "tracked"
    assert run_mod.resolve_run_key(cohort="all", tracked=False, country=None) == "all"


def test_build_scope_for_a_country_run_is_tracked_and_market_scoped():
    scope = run_mod.build_scope(tracked=True, country="SA",
                                tracked_sources=["brand", "influencer"],
                                exclude_authors=["spam"])
    assert scope == {"sources": ["brand", "influencer"], "country": "SA",
                     "exclude_authors": ["spam"]}


def test_build_scope_is_empty_for_a_plain_cohort_run():
    assert run_mod.build_scope(tracked=False, country=None,
                               tracked_sources=["brand", "influencer"],
                               exclude_authors=[]) == {}


def test_country_is_written_onto_every_trend_row():
    rows = [{"trend_id": "t1"}, {"trend_id": "t2"}]
    run_mod.stamp_country(rows, "SA")
    assert [r["country"] for r in rows] == ["SA", "SA"]


def test_stamp_country_writes_none_for_an_all_markets_run():
    rows = [{"trend_id": "t1"}]
    run_mod.stamp_country(rows, None)
    assert rows[0]["country"] is None


def test_trend_columns_include_country():
    """upsert_trends builds its INSERT from TREND_COLUMNS and reads each row with
    r.get(c), so country must be listed or it is silently never written."""
    assert "country" in store.TREND_COLUMNS
