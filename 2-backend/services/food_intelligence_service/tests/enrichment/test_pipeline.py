from unittest.mock import patch, MagicMock


def test_enrich_platform_writes_to_analysis_store_not_mongo(mock_settings):
    from services.food_intelligence_service.app.enrichment import pipeline

    fake_row = {
        "post_id": "p1", "account_username": "nadadairy", "platform": "instagram",
        "brand": {"key": "nada", "name": "Nada", "account_type": "brand"}, "text": "caption", "posted_at": None,
        "post_url": None, "owner": {"username": "nadadairy", "name": "Nada"},
        "engagement": {"likes": 1, "comments": 0, "views": 0, "shares": 0, "bookmarks": 0, "total": 1},
    }
    fake_analysis = {
        "description": "d", "language": "en", "keywords": [], "semiotic": {"text": "", "visual": {}},
        "themes": [], "product_focus": [], "functional_visual": [],
    }

    with patch.object(pipeline.postgres, "fetch_posts", return_value=[fake_row]), \
         patch.object(pipeline, "normalize_post", return_value=fake_row), \
         patch.object(pipeline, "analyze_post", return_value=fake_analysis), \
         patch.object(pipeline.s3_media, "resolve_image_key", return_value="media/instagram/p1.jpg"), \
         patch.object(pipeline.analysis_store, "post_already_enriched", return_value=False), \
         patch.object(pipeline.analysis_store, "upsert_post_analysis") as mock_upsert, \
         patch.object(pipeline.postgres, "fetch_profiles", return_value=[]):
        stats = pipeline.run_enrichment(platforms=["instagram"], projects=["food_trends_brands"], limit=1)

    assert stats["instagram"]["enriched"] == 1
    mock_upsert.assert_called_once()
    written_row = mock_upsert.call_args.args[0]
    assert written_row["language"] == "en"
    assert written_row["analysis"]["semiotic"]["text"] == ""
    assert written_row["processed_at"] is not None
    assert written_row["image_key"] == "media/instagram/p1.jpg"


def test_enrich_platform_skips_already_enriched_posts_without_force(mock_settings):
    from services.food_intelligence_service.app.enrichment import pipeline

    fake_row = {
        "post_id": "p1", "account_username": "nadadairy", "platform": "instagram",
        "brand": {"key": "nada", "name": "Nada", "account_type": "brand"}, "text": "caption", "posted_at": None,
        "post_url": None, "owner": {"username": "nadadairy", "name": "Nada"},
        "engagement": {"likes": 1, "comments": 0, "views": 0, "shares": 0, "bookmarks": 0, "total": 1},
    }

    with patch.object(pipeline.postgres, "fetch_posts", return_value=[fake_row]), \
         patch.object(pipeline, "normalize_post", return_value=fake_row), \
         patch.object(pipeline, "analyze_post") as mock_analyze, \
         patch.object(pipeline.analysis_store, "post_already_enriched", return_value=True), \
         patch.object(pipeline.analysis_store, "upsert_post_analysis") as mock_upsert, \
         patch.object(pipeline.postgres, "fetch_profiles", return_value=[]):
        stats = pipeline.run_enrichment(platforms=["instagram"], projects=["food_trends_brands"],
                                          limit=1, force=False)

    assert stats["instagram"]["skipped_existing"] == 1
    assert stats["instagram"]["enriched"] == 0
    mock_analyze.assert_not_called()
    mock_upsert.assert_not_called()


_UPSERT_BIND_KEYS = {
    "platform", "post_id", "brand_key", "brand_name", "account_type", "account_username",
    "caption", "language", "engagement", "engagement_total",
    "analysis", "image_key", "posted_at", "processed_at", "post_url",
}


def test_enriched_row_satisfies_every_upsert_bind_parameter(mock_settings):
    import re
    from services.food_intelligence_service.app.db import analysis_store
    from services.food_intelligence_service.app.enrichment import pipeline

    bound = set(re.findall(r":(\w+)", str(analysis_store._UPSERT_POST_ANALYSIS)))

    fake_row = {
        "post_id": "p1", "account_username": "nadadairy", "platform": "instagram",
        "brand": {"key": "nada", "name": "Nada", "account_type": "brand"}, "text": "caption", "posted_at": None,
        "post_url": None, "owner": {"username": "nadadairy", "name": "Nada"},
        "engagement": {"likes": 1, "comments": 0, "views": 0, "shares": 0, "bookmarks": 0, "total": 1},
    }

    with patch.object(pipeline.postgres, "fetch_posts", return_value=[fake_row]), \
         patch.object(pipeline, "normalize_post", return_value=fake_row), \
         patch.object(pipeline, "analyze_post", return_value={
             "description": "d", "language": "en", "keywords": [], "semiotic": {"text": "", "visual": {}},
             "themes": [], "product_focus": [], "functional_visual": [],
         }), \
         patch.object(pipeline.s3_media, "resolve_image_key", return_value=None), \
         patch.object(pipeline.analysis_store, "post_already_enriched", return_value=False), \
         patch.object(pipeline.analysis_store, "upsert_post_analysis") as mock_upsert:
        pipeline.run_enrichment(platforms=["instagram"], projects=["food_trends_brands"], limit=1)

    written_row = mock_upsert.call_args.args[0]
    assert bound == _UPSERT_BIND_KEYS
    assert bound - set(written_row) == set()
