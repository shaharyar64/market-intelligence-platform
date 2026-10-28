import json
from unittest.mock import MagicMock, patch


def test_upsert_post_analysis_writes_only_the_post_analysis_row(mock_settings):
    from services.food_intelligence_service.app.db import analysis_store

    fake_conn = MagicMock()
    fake_engine = MagicMock()
    fake_engine.begin.return_value.__enter__.return_value = fake_conn

    row = {
        "platform": "instagram", "post_id": "abc123",
        "brand_key": "nada", "brand_name": "Nada",
        "account_type": "brand", "account_username": "nadadairy",
        "caption": "test caption", "language": "en",
        "likes": 1, "comments": 2, "views": 0, "shares": 0, "bookmarks": 0,
        "engagement_total": 3,
        "analysis": {
            "description": "...",
            "themes": [{"label": "High protein", "confidence": 1.0, "evidence": ["protein"]}],
            "product_focus": [{"product": "kefir", "confidence": 1.0, "evidence": ["kefir"]}],
            "semiotic": {"text": "", "visual": {}},
            "keywords": [],
            "functional_visual": [],
        },
        "image_key": None, "posted_at": None, "post_url": None,
        "processed_at": None,
    }

    with patch.object(analysis_store, "engine", return_value=fake_engine):
        analysis_store.upsert_post_analysis(row)

    assert fake_conn.execute.call_count == 1
    executed_sql = str(fake_conn.execute.call_args_list[0].args[0])
    assert "INSERT INTO food_intel.post_analysis" in executed_sql
    assert "post_theme" not in executed_sql
    assert "post_product" not in executed_sql

    payload = fake_conn.execute.call_args_list[0].args[1]
    stored_analysis = json.loads(payload["analysis"])
    assert stored_analysis["themes"] == [{"label": "High protein", "confidence": 1.0, "evidence": ["protein"]}]
    assert stored_analysis["product_focus"] == [{"product": "kefir", "confidence": 1.0, "evidence": ["kefir"]}]


def test_analysis_store_no_longer_writes_a_brand_profile_table(mock_settings):
    from services.food_intelligence_service.app.db import analysis_store

    assert not hasattr(analysis_store, "upsert_brand_profile")
    assert "food_intel.brand_profile" not in analysis_store.BRAND_ACCOUNTS_SQL


def test_fetch_brand_profiles_derives_accounts_from_post_analysis(mock_settings):
    from services.food_intelligence_service.app.db import analysis_store

    with patch.object(analysis_store, "run_query", return_value=[]) as run_query:
        analysis_store.fetch_brand_profiles("nada")

    sql = run_query.call_args.args[0]
    assert "food_intel.brand_profile" not in sql
    assert "food_intel.post_analysis" in sql


def test_fetch_brand_profiles_reads_followers_live_from_the_source_profile_tables(mock_settings):
    from services.food_intelligence_service.app.db import analysis_store

    with patch.object(analysis_store, "run_query", return_value=[]) as run_query:
        analysis_store.fetch_brand_profiles("nada")

    sql = run_query.call_args.args[0]
    assert "public.instagram_profile" in sql
    assert "public.tiktok_profiles" in sql
    assert "lp.username = bp.account_username" in sql
    for live in ("lp.followers", "lp.country", "lp.industry", "lp.is_verified"):
        assert live in sql


def test_post_already_enriched_true_when_row_exists(mock_settings):
    from services.food_intelligence_service.app.db import analysis_store

    fake_row = MagicMock()
    fake_row._mapping = {"?column?": 1}
    fake_conn = MagicMock()
    fake_conn.execute.return_value = [fake_row]
    fake_engine = MagicMock()
    fake_engine.connect.return_value.execution_options.return_value.__enter__.return_value = fake_conn

    with patch.object(analysis_store, "engine", return_value=fake_engine):
        assert analysis_store.post_already_enriched("abc123", "instagram") is True

    # Reads go out under AUTOCOMMIT: the implicit BEGIN/ROLLBACK that connect()
    # would otherwise wrap around a SELECT costs two extra round trips to an
    # out-of-region database, which is most of the latency on the visual pages.
    fake_engine.connect.return_value.execution_options.assert_called_once_with(
        isolation_level="AUTOCOMMIT")
