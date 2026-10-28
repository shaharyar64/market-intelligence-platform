from unittest.mock import patch, MagicMock


def test_functional_visual_node_writes_categories(mock_settings):
    from services.food_intelligence_service.app.enrichment.nodes import vision_nodes
    from services.food_intelligence_service.app.enrichment.schema import FunctionalVisualOutput, FunctionalVisualItem

    fake_result = FunctionalVisualOutput(functional_visual=[
        FunctionalVisualItem(category="product", confidence=0.95, visual_evidence="glass jar, label visible"),
    ])
    mock_llm = MagicMock()
    mock_llm.invoke.return_value = fake_result

    with patch("services.food_intelligence_service.app.enrichment.nodes.vision_nodes.ChatOpenAI") as MockChat:
        MockChat.return_value.with_structured_output.return_value = mock_llm
        result = vision_nodes.functional_visual_node({"image_url": "https://signed-url"})

    assert result["functional_visual"].functional_visual[0].category == "product"


def test_functional_visual_node_skips_when_no_image(mock_settings):
    from services.food_intelligence_service.app.enrichment.nodes import vision_nodes

    with patch("services.food_intelligence_service.app.enrichment.nodes.vision_nodes.ChatOpenAI") as MockChat:
        result = vision_nodes.functional_visual_node({"image_url": None})

    MockChat.assert_not_called()
    assert result["functional_visual"] is None


def test_functional_visual_node_returns_none_after_exhausting_retries(mock_settings):
    from services.food_intelligence_service.app.enrichment.nodes import vision_nodes

    mock_llm = MagicMock()
    mock_llm.invoke.side_effect = RuntimeError("model unavailable")

    with patch("services.food_intelligence_service.app.enrichment.nodes.vision_nodes.ChatOpenAI") as MockChat, \
         patch("services.food_intelligence_service.app.enrichment.retry.time.sleep"):
        MockChat.return_value.with_structured_output.return_value = mock_llm
        result = vision_nodes.functional_visual_node({"image_url": "https://signed-url"})

    assert result["functional_visual"] is None
    assert mock_llm.invoke.call_count == 3


def test_semiotic_visual_node_writes_scores(mock_settings):
    from services.food_intelligence_service.app.enrichment.nodes import vision_nodes
    from services.food_intelligence_service.app.enrichment.schema import SemioticVisualOutput

    fake_result = SemioticVisualOutput(premium=0.8, healthy=0.7, natural=None, modern=None,
                                       traditional=None, sophisticated=None, indulgent=None)
    mock_llm = MagicMock()
    mock_llm.invoke.return_value = fake_result

    with patch("services.food_intelligence_service.app.enrichment.nodes.vision_nodes.ChatOpenAI") as MockChat:
        MockChat.return_value.with_structured_output.return_value = mock_llm
        result = vision_nodes.semiotic_visual_node({"image_url": "https://signed-url"})

    assert result["semiotic_visual"].scores["premium"] == 0.8


def test_semiotic_visual_node_skips_when_no_image(mock_settings):
    from services.food_intelligence_service.app.enrichment.nodes import vision_nodes

    with patch("services.food_intelligence_service.app.enrichment.nodes.vision_nodes.ChatOpenAI") as MockChat:
        result = vision_nodes.semiotic_visual_node({"image_url": None})

    MockChat.assert_not_called()
    assert result["semiotic_visual"] is None
