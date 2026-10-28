from unittest.mock import patch, MagicMock


def test_themes_node_drops_ungrounded_items_and_retries_once(mock_settings):
    from services.food_intelligence_service.app.enrichment.nodes import grounded_nodes
    from services.food_intelligence_service.app.enrichment.schema import ThemesOutput, ThemeItem

    first_call = ThemesOutput(themes=[
        ThemeItem(label="High protein", confidence=1.0, evidence=["قوي بالبروتين"]),
        ThemeItem(label="Fake", confidence=0.9, evidence=["not in caption"]),
    ])
    second_call = ThemesOutput(themes=[
        ThemeItem(label="High protein", confidence=1.0, evidence=["قوي بالبروتين"]),
    ])

    mock_llm = MagicMock()
    mock_llm.invoke.side_effect = [first_call, second_call]

    with patch("services.food_intelligence_service.app.enrichment.nodes.grounded_nodes.ChatOpenAI") as MockChat:
        MockChat.return_value.with_structured_output.return_value = mock_llm
        result = grounded_nodes.themes_node({"caption": "خفيف بالإحساس، قوي بالبروتين"})

    assert len(result["themes"].themes) == 1
    assert result["themes"].themes[0].label == "High protein"
    assert mock_llm.invoke.call_count == 2


def test_themes_node_does_not_retry_when_all_grounded(mock_settings):
    from services.food_intelligence_service.app.enrichment.nodes import grounded_nodes
    from services.food_intelligence_service.app.enrichment.schema import ThemesOutput, ThemeItem

    clean_call = ThemesOutput(themes=[ThemeItem(label="High protein", confidence=1.0, evidence=["protein"])])
    mock_llm = MagicMock()
    mock_llm.invoke.return_value = clean_call

    with patch("services.food_intelligence_service.app.enrichment.nodes.grounded_nodes.ChatOpenAI") as MockChat:
        MockChat.return_value.with_structured_output.return_value = mock_llm
        result = grounded_nodes.themes_node({"caption": "protein rich"})

    assert mock_llm.invoke.call_count == 1
    assert result["themes"].themes[0].label == "High protein"


def test_themes_node_skips_empty_caption_without_calling_the_llm(mock_settings):
    from services.food_intelligence_service.app.enrichment.nodes import grounded_nodes

    with patch("services.food_intelligence_service.app.enrichment.nodes.grounded_nodes.ChatOpenAI") as MockChat:
        result = grounded_nodes.themes_node({"caption": ""})

    MockChat.assert_not_called()
    assert result["themes"] is None


def test_product_focus_node_drops_ungrounded_items(mock_settings):
    from services.food_intelligence_service.app.enrichment.nodes import grounded_nodes
    from services.food_intelligence_service.app.enrichment.schema import ProductFocusOutput, ProductItem

    first_call = ProductFocusOutput(product_focus=[
        ProductItem(product="Greek kefir", confidence=1.0, evidence=["كفير يوناني"]),
        ProductItem(product="Fake product", confidence=0.9, evidence=["not present"]),
    ])
    second_call = ProductFocusOutput(product_focus=[
        ProductItem(product="Greek kefir", confidence=1.0, evidence=["كفير يوناني"]),
    ])
    mock_llm = MagicMock()
    mock_llm.invoke.side_effect = [first_call, second_call]

    with patch("services.food_intelligence_service.app.enrichment.nodes.grounded_nodes.ChatOpenAI") as MockChat:
        MockChat.return_value.with_structured_output.return_value = mock_llm
        result = grounded_nodes.product_focus_node({"caption": "ندى كفير يوناني"})

    assert len(result["product_focus"].product_focus) == 1
    assert result["product_focus"].product_focus[0].product == "Greek kefir"
