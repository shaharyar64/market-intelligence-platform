from datetime import datetime
from unittest.mock import patch


def test_list_brands_groups_by_brand_key(mock_settings):
    from services.food_intelligence_service.app.services import brand_service

    fake_rows = [{"brand_key": "nada", "name": "Nada", "account_type": "brand",
                  "post_count": 5, "platforms": ["instagram"]}]
    with patch.object(brand_service.analysis_store, "run_query", return_value=fake_rows):
        result = brand_service.list_brands()

    assert result == {"brands": [{"key": "nada", "name": "Nada", "account_type": "brand",
                                  "post_count": 5, "platforms": ["instagram"]}]}


def test_get_themes_filters_by_min_posts(mock_settings):
    from services.food_intelligence_service.app.services import brand_service

    fake_rows = [
        {"label": "High protein", "post_count": 4, "engagement": 100, "avg_confidence": 0.95,
         "evidence": ["a", "b"], "post_ids": ["p1", "p2"]},
    ]
    with patch.object(brand_service.analysis_store, "run_query", return_value=fake_rows) as run_query:
        result = brand_service.get_themes("nada", min_posts=3, limit=25)

    assert result["themes"][0] == {
        "label": "High protein", "post_count": 4, "engagement": 100,
        "avg_confidence": 0.95, "evidence": ["a", "b"], "example_post_ids": ["p1", "p2"],
    }
    assert result["min_posts"] == 3

    sql, params = run_query.call_args.args
    assert "post_theme" not in sql
    assert "jsonb_array_elements(pa.analysis->'themes')" in sql
    assert params == {"key": "nada", "min_posts": 3, "limit": 25}


def test_get_products_aggregates_product_focus_from_jsonb(mock_settings):
    from services.food_intelligence_service.app.services import brand_service

    fake_rows = [
        {"label": "kefir", "post_count": 2, "engagement": 40, "avg_confidence": 0.9,
         "evidence": ["kefir"], "post_ids": ["p1", "p2"]},
    ]
    with patch.object(brand_service.analysis_store, "run_query", return_value=fake_rows) as run_query:
        result = brand_service.get_products("nada", min_posts=1, limit=25)

    assert result["products"][0]["product"] == "kefir"
    assert result["products"][0]["post_count"] == 2
    assert result["products"][0]["example_post_ids"] == ["p1", "p2"]

    sql = run_query.call_args.args[0]
    assert "post_product" not in sql
    assert "jsonb_array_elements(pa.analysis->'product_focus')" in sql
    assert "elem->>'product'" in sql


def test_get_top_content_maps_engagement_and_owner(mock_settings):
    from services.food_intelligence_service.app.services import brand_service

    fake_rows = [{
        "post_id": "p1", "platform": "instagram", "post_url": "https://x", "owner_username": "nadadairy",
        "owner_name": "Nada", "posted_at": datetime(2026, 7, 23), "caption": "hi",
        "engagement": {"likes": 1, "comments": 2, "views": 0, "shares": 0, "bookmarks": 0},
        "engagement_total": 3,
        "themes": ["High protein"], "products": ["kefir"],
    }]
    with patch.object(brand_service.analysis_store, "run_query", return_value=fake_rows):
        result = brand_service.get_top_content("nada", limit=10)

    item = result["items"][0]
    assert item["owner"] == {"username": "nadadairy", "name": "Nada"}
    assert item["engagement"]["total"] == 3
    assert item["engagement"]["likes"] == 1
    assert item["engagement"]["comments"] == 2
    assert item["themes"] == ["High protein"]


def test_get_functional_visual_aggregates_via_jsonb(mock_settings):
    from services.food_intelligence_service.app.services import brand_service

    fake_rows = [{"category": "product", "post_count": 8, "total_posts": 10}]
    with patch.object(brand_service.analysis_store, "run_query", return_value=fake_rows):
        result = brand_service.get_functional_visual("nada")

    assert result["categories"][0]["category"] == "product"
    assert result["categories"][0]["pct"] == 80.0


def test_get_semiotic_returns_axis_scores(mock_settings):
    from services.food_intelligence_service.app.services import brand_service

    fake_rows = [{"axis": "premium", "avg_score": 0.8}, {"axis": "healthy", "avg_score": 0.7}]
    with patch.object(brand_service.analysis_store, "run_query", return_value=fake_rows):
        result = brand_service.get_semiotic("nada")

    assert result["axes"]["premium"] == 80.0
    assert result["axes"]["healthy"] == 70.0


def test_get_overview_includes_top_visual_territories(mock_settings):
    from services.food_intelligence_service.app.services import brand_service

    overview_rows = [{"name": "Nada", "account_type": "brand", "platforms": ["instagram"],
                      "post_count": 5, "total_engagement": 50,
                      "first_post_date": None, "last_post_date": None,
                      "theme_count": 3, "product_count": 3,
                      "axes": {"premium": 90.0, "healthy": 80.0, "modern": 30.0},
                      "accounts": [], "followers_total": 0}]

    seen_sql = []

    def fake_run_query(sql, params=None):
        seen_sql.append(sql)
        return overview_rows

    with patch.object(brand_service.analysis_store, "run_query", side_effect=fake_run_query):
        result = brand_service.get_overview("nada")

    assert result["visual_territories"] == ["premium", "healthy"]
    assert result["theme_count"] == 3
    assert result["product_count"] == 3

    assert len(seen_sql) == 1
    joined = seen_sql[0]
    assert "post_theme" not in joined
    assert "post_product" not in joined
    assert "jsonb_array_elements(pa.analysis->'themes')" in joined
    assert "jsonb_array_elements(pa.analysis->'product_focus')" in joined


def test_get_overview_reads_followers_and_verified_from_live_profiles(mock_settings):
    from services.food_intelligence_service.app.services import brand_service

    overview_rows = [{"name": "Nada", "account_type": "brand", "platforms": ["instagram", "tiktok"],
                      "post_count": 4, "total_engagement": 40,
                      "first_post_date": None, "last_post_date": None,
                      "theme_count": 0, "product_count": 0, "axes": {},
                      "accounts": [
                          {"platform": "instagram", "account_username": "nadadairy",
                           "followers": 1000, "is_verified": True},
                          {"platform": "tiktok", "account_username": "nadadairy",
                           "followers": None, "is_verified": None},
                      ],
                      "followers_total": 1000}]

    with patch.object(brand_service.analysis_store, "run_query", return_value=overview_rows):
        result = brand_service.get_overview("nada")

    assert result["followers_total"] == 1000
    assert result["accounts"] == [
        {"platform": "instagram", "account_username": "nadadairy", "followers": 1000, "is_verified": True},
        {"platform": "tiktok", "account_username": "nadadairy", "followers": 0, "is_verified": False},
    ]
