def test_grounded_keeps_only_items_with_verbatim_evidence(mock_settings):
    from services.food_intelligence_service.app.enrichment.node_factory import grounded
    from services.food_intelligence_service.app.enrichment.schema import ThemeItem

    items = [
        ThemeItem(label="High protein", confidence=1.0, evidence=["قوي بالبروتين"]),
        ThemeItem(label="Fake theme", confidence=0.9, evidence=["not in caption"]),
    ]
    caption_norm = "خفيف بالإحساس، قوي بالبروتين"
    kept, dropped = grounded(items, caption_norm.lower())
    assert len(kept) == 1
    assert kept[0].label == "High protein"
    assert dropped == 1
