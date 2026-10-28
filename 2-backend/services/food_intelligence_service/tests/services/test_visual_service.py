from unittest.mock import patch




def test_get_gallery_returns_presigned_urls(mock_settings):
    from services.food_intelligence_service.app.services import visual_service

    fake_rows = [{"post_id": "p1", "platform": "instagram", "image_key": "media/instagram/p1.jpg",
                   "caption": "hi", "brand_name": "Nada"}]
    with patch.object(visual_service.analysis_store, "run_query", return_value=fake_rows), \
         patch.object(visual_service.s3_media, "presigned_url", return_value="https://signed"):
        result = visual_service.get_gallery(limit=12)

    assert result["items"][0]["image_url"] == "https://signed"
    assert result["items"][0]["brand_name"] == "Nada"


def test_get_gallery_filters_by_cohort(mock_settings):
    """Each tab must show its own cohort.

    Without an account_type predicate the query is a global "newest images"
    lookup: influencers post most recently, so all three tabs came back with
    the same twelve influencer posts.
    """
    from services.food_intelligence_service.app.services import visual_service

    with patch.object(visual_service.analysis_store, "run_query", return_value=[]) as q, \
         patch.object(visual_service.s3_media, "presigned_url", return_value="https://signed"):
        result = visual_service.get_gallery(limit=12, account_type="brand")

    sql, params = q.call_args[0]
    assert "account_type" in sql
    assert params["account_type"] == "brand"
    assert result["account_type"] == "brand"


def test_get_gallery_takes_several_accounts(mock_settings):
    """The picker is a multi-select, so the gallery has to honour every key."""
    from services.food_intelligence_service.app.services import visual_service

    with patch.object(visual_service.analysis_store, "run_query", return_value=[]) as q, \
         patch.object(visual_service.s3_media, "presigned_url", return_value="https://signed"):
        visual_service.get_gallery(limit=12, keys=["nada", "brewdog"])

    sql, params = q.call_args[0]
    assert "ANY(:keys)" in sql
    assert params["keys"] == ["nada", "brewdog"]


def test_get_gallery_treats_no_selection_as_whole_cohort(mock_settings):
    """An empty selection means "All accounts", not "no accounts"."""
    from services.food_intelligence_service.app.services import visual_service

    with patch.object(visual_service.analysis_store, "run_query", return_value=[]) as q, \
         patch.object(visual_service.s3_media, "presigned_url", return_value="https://signed"):
        visual_service.get_gallery(limit=12, keys=[], account_type="community")

    _, params = q.call_args[0]
    assert params["keys"] is None
    assert params["account_type"] == "community"
