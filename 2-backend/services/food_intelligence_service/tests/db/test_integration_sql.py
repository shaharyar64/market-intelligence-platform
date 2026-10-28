import os
from datetime import datetime, timezone
from pathlib import Path
from unittest.mock import patch

import pytest
from sqlalchemy import create_engine, text
from sqlalchemy.engine import make_url

TEST_POSTGRES_DSN = os.environ.get("TEST_POSTGRES_DSN")

pytestmark = pytest.mark.skipif(
    not TEST_POSTGRES_DSN,
    reason="Set TEST_POSTGRES_DSN to a scratch Postgres database to run the SQL integration tests.",
)

_MIGRATIONS_DIR = Path(__file__).resolve().parents[4] / "shared" / "migrations"
_MIGRATIONS = [
    _MIGRATIONS_DIR / "002_create_food_intel_schema.sql",
    _MIGRATIONS_DIR / "003_drop_food_intel_derived_tables.sql",
    _MIGRATIONS_DIR / "004_drop_food_intel_brand_profile.sql",
    _MIGRATIONS_DIR / "005_move_node_status_out_of_analysis.sql",
    _MIGRATIONS_DIR / "006_drop_node_status_column.sql",
    _MIGRATIONS_DIR / "007_replace_provenance_with_processed_at.sql",
    _MIGRATIONS_DIR / "008_consolidate_engagement_into_jsonb.sql",
    _MIGRATIONS_DIR / "009_rename_image_ref_to_image_key.sql",
]

_PROFILE_STUBS = {
    "instagram_profile": "username text, followers bigint, country text, industry text, is_verified boolean",
    "tiktok_profiles": "username text, followers bigint, country text, industry text, verified boolean",
}

_SEEDED_USERNAMES = ("nadadairy", "almaraidairy")

_NOW = datetime.now(timezone.utc).isoformat()


def _row(post_id: str, *, brand_key: str = "nada", platform: str = "instagram",
         functional: list | None = None,
         visual: dict | None = None, engagement_total: int = 61) -> dict:
    return {
        "platform": platform, "post_id": post_id,
        "brand_key": brand_key, "brand_name": brand_key.title(),
        "account_type": "brand", "account_username": f"{brand_key}dairy",
        "caption": "protein rich kefir", "language": "en",
        "engagement": {"likes": 47, "comments": 14, "views": 0, "shares": 0, "bookmarks": 0},
        "engagement_total": engagement_total,
        "analysis": {
            "description": "A caption about kefir.",
            "language": "en",
            "keywords": ["#kefir"],
            "semiotic": {"text": "warm", "visual": visual if visual is not None else {"premium": 0.8, "healthy": 0.6}},
            "themes": [{"label": "High protein", "confidence": 1.0, "evidence": ["protein"]}],
            "product_focus": [{"product": "kefir", "confidence": 1.0, "evidence": ["kefir"]}],
            "functional_visual": functional if functional is not None else [
                {"category": "product", "confidence": 0.9, "visual_evidence": "jar in frame"},
            ],
        },
        "image_key": f"media/{platform}/{post_id}.jpg",
        "posted_at": _NOW, "processed_at": _NOW,
        "post_url": f"https://example.test/{post_id}",
    }


_SCRATCH_MARKERS = ("scratch", "test", "tmp")


def _assert_scratch_database(dsn: str) -> None:
    name = make_url(dsn).database or ""
    if not any(marker in name.lower() for marker in _SCRATCH_MARKERS):
        raise RuntimeError(
            f"Refusing to run: TEST_POSTGRES_DSN points at database {name!r}, which does not look "
            f"like a scratch database. These tests DROP the food_intel schema. Point TEST_POSTGRES_DSN "
            f"at a throwaway database whose name contains one of {_SCRATCH_MARKERS}."
        )


@pytest.fixture(scope="module")
def scratch_engine():
    _assert_scratch_database(TEST_POSTGRES_DSN)
    engine = create_engine(TEST_POSTGRES_DSN, pool_pre_ping=True)
    created_stubs = []
    with engine.begin() as conn:
        conn.execute(text("DROP SCHEMA IF EXISTS food_intel CASCADE"))
        for migration in _MIGRATIONS:
            sql = migration.read_text(encoding="utf-8")
            for statement in [s.strip() for s in sql.split(";") if s.strip()]:
                conn.execute(text(statement))
        for table, columns in _PROFILE_STUBS.items():
            if conn.execute(text("SELECT to_regclass(:n)"), {"n": f"public.{table}"}).scalar() is None:
                conn.execute(text(f"CREATE TABLE public.{table} ({columns})"))
                created_stubs.append(table)
    yield engine
    with engine.begin() as conn:
        conn.execute(text("DROP SCHEMA IF EXISTS food_intel CASCADE"))
        for table in created_stubs:
            conn.execute(text(f"DROP TABLE IF EXISTS public.{table}"))
    engine.dispose()


def _seed_profile(engine, table: str, verified_col: str, username: str,
                  followers: int = 1000, industry: str = "Dairy") -> None:
    with engine.begin() as conn:
        conn.execute(
            text(f"INSERT INTO public.{table} (username, followers, country, industry, {verified_col}) "
                 f"VALUES (:u, :f, 'SA', :i, true)"),
            {"u": username, "f": followers, "i": industry},
        )


@pytest.fixture()
def store(scratch_engine):
    from services.food_intelligence_service.app.db import analysis_store

    with patch.object(analysis_store, "engine", return_value=scratch_engine):
        with scratch_engine.begin() as conn:
            conn.execute(text("TRUNCATE food_intel.post_analysis"))
            for table in _PROFILE_STUBS:
                conn.execute(text(f"DELETE FROM public.{table} WHERE username = ANY(:u)"),
                             {"u": list(_SEEDED_USERNAMES)})
        yield analysis_store


def test_upsert_post_analysis_round_trips_all_bind_parameters(store):
    store.upsert_post_analysis(_row("p1"))

    rows = store.run_query("SELECT * FROM food_intel.post_analysis WHERE post_id = :p", {"p": "p1"})
    assert len(rows) == 1
    stored = rows[0]
    assert stored["brand_key"] == "nada"
    assert stored["language"] == "en"
    assert stored["engagement_total"] == 61
    assert stored["image_key"] == "media/instagram/p1.jpg"
    assert stored["post_url"] == "https://example.test/p1"
    assert stored["posted_at"] is not None and stored["processed_at"] is not None
    assert stored["analysis"]["semiotic"]["visual"]["premium"] == 0.8

    assert stored["analysis"]["themes"] == [
        {"label": "High protein", "confidence": 1.0, "evidence": ["protein"]}]
    assert stored["analysis"]["product_focus"] == [
        {"product": "kefir", "confidence": 1.0, "evidence": ["kefir"]}]


def test_the_derived_child_tables_no_longer_exist(store):
    absent = store.run_query(
        "SELECT to_regclass('food_intel.post_theme') AS t, to_regclass('food_intel.post_product') AS p")
    assert absent[0]["t"] is None
    assert absent[0]["p"] is None


def test_only_post_analysis_remains_in_the_schema(store):
    tables = store.run_query(
        "SELECT table_name FROM information_schema.tables WHERE table_schema = 'food_intel'")
    assert {t["table_name"] for t in tables} == {"post_analysis"}


def test_upsert_post_analysis_is_idempotent_on_conflict(store):
    store.upsert_post_analysis(_row("p1"))
    updated = _row("p1", engagement_total=999)
    updated["caption"] = "second pass"
    store.upsert_post_analysis(updated)

    rows = store.run_query("SELECT caption, engagement_total FROM food_intel.post_analysis WHERE post_id = :p",
                           {"p": "p1"})
    assert len(rows) == 1
    assert rows[0]["caption"] == "second pass"
    assert rows[0]["engagement_total"] == 999

    stored = store.run_query("SELECT analysis FROM food_intel.post_analysis WHERE post_id = :p", {"p": "p1"})
    assert len(stored[0]["analysis"]["themes"]) == 1


def test_post_already_enriched_reflects_whether_the_row_exists(store):
    store.upsert_post_analysis(_row("p1"))
    assert store.post_already_enriched("p1", "instagram") is True
    assert store.post_already_enriched("p2", "instagram") is False
    assert store.post_already_enriched("p1", "tiktok") is False


def test_fetch_brand_profiles_returns_one_row_per_account(store, scratch_engine):
    _seed_profile(scratch_engine, "instagram_profile", "is_verified", "nadadairy", followers=1000)
    store.upsert_post_analysis(_row("p1"))
    store.upsert_post_analysis(_row("p2"))

    profiles = store.fetch_brand_profiles("nada")
    assert len(profiles) == 1
    assert profiles[0]["followers"] == 1000


def test_fetch_brand_profiles_reflects_rescraped_follower_counts(store, scratch_engine):
    _seed_profile(scratch_engine, "instagram_profile", "is_verified", "nadadairy", followers=1000)
    store.upsert_post_analysis(_row("p1"))
    assert store.fetch_brand_profiles("nada")[0]["followers"] == 1000

    with scratch_engine.begin() as conn:
        conn.execute(text("UPDATE public.instagram_profile SET followers = 2000 WHERE username = 'nadadairy'"))

    profile = store.fetch_brand_profiles("nada")[0]
    assert profile["followers"] == 2000
    assert profile["industry"] == "Dairy"
    assert profile["is_verified"] is True


def test_fetch_brand_profiles_returns_nulls_when_the_source_profile_is_missing(store):
    store.upsert_post_analysis(_row("p1", platform="tiktok"))

    profile = store.fetch_brand_profiles("nada")[0]
    assert profile["account_username"] == "nadadairy"
    assert profile["followers"] is None
    assert profile["industry"] is None
    assert profile["is_verified"] is None


def test_fetch_brand_profiles_reads_tiktok_from_the_tiktok_profiles_table(store, scratch_engine):
    _seed_profile(scratch_engine, "tiktok_profiles", "verified", "nadadairy", followers=555)
    store.upsert_post_analysis(_row("p1", platform="tiktok"))

    profile = store.fetch_brand_profiles("nada")[0]
    assert profile["followers"] == 555
    assert profile["is_verified"] is True


def test_brand_service_read_queries_execute(store, scratch_engine):
    from services.food_intelligence_service.app.services import brand_service

    store.upsert_post_analysis(_row("p1"))
    store.upsert_post_analysis(_row("p2"))
    _seed_profile(scratch_engine, "instagram_profile", "is_verified", "nadadairy", followers=1000)

    brands = brand_service.list_brands()
    assert [b["key"] for b in brands["brands"]] == ["nada"]

    overview = brand_service.get_overview("nada")
    assert overview["post_count"] == 2
    assert overview["theme_count"] == 1
    assert overview["product_count"] == 1
    assert overview["followers_total"] == 1000
    assert overview["visual_territories"] == ["premium", "healthy"]

    assert brand_service.get_overview("does-not-exist") is None

    themes = brand_service.get_themes("nada", min_posts=1, limit=10)
    assert themes["themes"][0]["label"] == "High protein"
    assert themes["themes"][0]["post_count"] == 2
    assert themes["themes"][0]["evidence"] == ["protein"]

    products = brand_service.get_products("nada", min_posts=1, limit=10)
    assert products["products"][0]["product"] == "kefir"

    assert brand_service.get_themes("nada", min_posts=5, limit=10)["themes"] == []

    top = brand_service.get_top_content("nada", limit=5)
    assert {i["post_id"] for i in top["items"]} == {"p1", "p2"}
    assert top["items"][0]["themes"] == ["High protein"]
    assert top["items"][0]["products"] == ["kefir"]

    filtered = brand_service.get_top_content("nada", limit=5, platform="tiktok")
    assert filtered["items"] == []


def test_get_functional_visual_cte_and_scalar_subquery(store):
    from services.food_intelligence_service.app.services import brand_service

    store.upsert_post_analysis(_row("p1"))
    store.upsert_post_analysis(_row("p2", functional=[
        {"category": "product", "confidence": 0.8, "visual_evidence": "bottle"},
        {"category": "in_home", "confidence": 0.5, "visual_evidence": "kitchen counter"},
    ]))

    result = brand_service.get_functional_visual("nada")
    by_category = {c["category"]: c for c in result["categories"]}
    assert by_category["product"]["post_count"] == 2
    assert by_category["product"]["pct"] == 100.0
    assert by_category["in_home"]["post_count"] == 1
    assert by_category["in_home"]["pct"] == 50.0


def test_get_semiotic_averages_jsonb_each_text(store):
    from services.food_intelligence_service.app.services import brand_service

    store.upsert_post_analysis(_row("p1", visual={"premium": 1.0}))
    store.upsert_post_analysis(_row("p2", visual={"premium": 0.0}))

    assert brand_service.get_semiotic("nada")["axes"] == {"premium": 50.0}


def test_visual_service_functional_analysis_executes(store):
    from services.food_intelligence_service.app.services import visual_service

    store.upsert_post_analysis(_row("p1"))
    store.upsert_post_analysis(_row("p2", brand_key="almarai", functional=[
        {"category": "prepared_food", "confidence": 0.7, "visual_evidence": "plated dish"},
    ]))

    result = visual_service.get_functional_analysis()
    by_category = {c["category"]: c for c in result["categories"]}
    assert by_category["product"]["post_count"] == 1
    assert by_category["prepared_food"]["post_count"] == 1
    assert by_category["product"]["pct"] == 50.0


def test_get_semiotic_grouped_mixed_join_and_implicit_lateral(store, scratch_engine):
    from services.food_intelligence_service.app.services import visual_service

    store.upsert_post_analysis(_row("p1", visual={"premium": 1.0}))
    store.upsert_post_analysis(_row("p2", brand_key="almarai", visual={"premium": 0.4}))
    for brand_key in ("nada", "almarai"):
        _seed_profile(scratch_engine, "instagram_profile", "is_verified", f"{brand_key}dairy",
                      industry="Dairy")

    result = visual_service.get_semiotic_grouped("industry")
    assert result["group_by"] == "industry"
    assert result["groups"]["Dairy"]["premium"] == 70.0

    with pytest.raises(ValueError):
        visual_service.get_semiotic_grouped("country")


def test_get_gallery_orders_and_limits(store):
    from services.food_intelligence_service.app.services import visual_service

    store.upsert_post_analysis(_row("p1"))
    no_image = _row("p2")
    no_image["image_key"] = None
    store.upsert_post_analysis(no_image)

    with patch.object(visual_service.s3_media, "presigned_url", return_value="https://signed"):
        result = visual_service.get_gallery(limit=5)

    assert [i["post_id"] for i in result["items"]] == ["p1"]
    assert result["items"][0]["image_url"] == "https://signed"


def test_the_analysis_object_holds_exactly_the_assembled_fields(store):
    store.upsert_post_analysis(_row("p1"))

    row = store.run_query(
        "SELECT analysis FROM food_intel.post_analysis WHERE post_id = :p", {"p": "p1"})[0]
    assert set(row["analysis"]) == {
        "description", "language", "keywords", "semiotic", "themes", "product_focus", "functional_visual"}


def test_post_analysis_keeps_only_processed_at_for_provenance(store):
    columns = {c["column_name"] for c in store.run_query(
        "SELECT column_name FROM information_schema.columns "
        "WHERE table_schema = 'food_intel' AND table_name = 'post_analysis'")}
    assert "processed_at" in columns
    assert {"provenance", "prompt_version", "schema_version", "fetched_at"} & columns == set()


def test_engagement_metrics_live_in_one_jsonb_column(store):
    store.upsert_post_analysis(_row("p1"))

    row = store.run_query(
        "SELECT engagement, engagement_total FROM food_intel.post_analysis WHERE post_id = :p", {"p": "p1"})[0]
    assert row["engagement"] == {"likes": 47, "comments": 14, "views": 0, "shares": 0, "bookmarks": 0}
    assert row["engagement_total"] == 61

    columns = {c["column_name"] for c in store.run_query(
        "SELECT column_name FROM information_schema.columns "
        "WHERE table_schema = 'food_intel' AND table_name = 'post_analysis'")}
    assert {"likes", "comments", "views", "shares", "bookmarks"} & columns == set()
    assert "engagement_total" in columns
