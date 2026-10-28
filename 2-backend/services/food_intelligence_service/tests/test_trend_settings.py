from services.food_intelligence_service.app.core.config import get_settings


def test_tracked_sources_are_brand_and_influencer():
    s = get_settings()
    assert s.TREND_TRACKED_SOURCES == ["brand", "influencer"]


def test_document_source_defaults_to_caption_for_food():
    """Food must not default to analysis the way real estate does: only 7,604 of
    food's 408,308 posts are analysed, so a community run in analysis mode would
    cluster almost nothing and the existing all-* runs would break."""
    s = get_settings()
    assert s.TREND_DOCUMENT_SOURCE == "caption"


def test_exclude_authors_defaults_to_empty():
    s = get_settings()
    assert s.TREND_EXCLUDE_AUTHORS == []
