from unittest.mock import patch


def test_description_node_writes_description(mock_settings):
    from services.food_intelligence_service.app.enrichment.nodes import text_nodes
    from services.food_intelligence_service.app.enrichment.schema import DescriptionOutput

    with patch("services.food_intelligence_service.app.enrichment.node_factory.invoke_with_retry",
               return_value=DescriptionOutput(description="A caption about kefir.", language="en")):
        result = text_nodes.description_node({"caption": "test caption"})

    assert result["description"].description == "A caption about kefir."
    assert result["description"].language == "en"


def test_keywords_node_writes_keywords(mock_settings):
    from services.food_intelligence_service.app.enrichment.nodes import text_nodes
    from services.food_intelligence_service.app.enrichment.schema import KeywordsOutput

    with patch("services.food_intelligence_service.app.enrichment.node_factory.invoke_with_retry",
               return_value=KeywordsOutput(keywords=["#kefir"])):
        result = text_nodes.keywords_node({"caption": "test caption"})

    assert result["keywords"].keywords == ["#kefir"]


def test_description_node_returns_none_after_exhausting_retries(mock_settings):
    from services.food_intelligence_service.app.enrichment.nodes import text_nodes
    from services.food_intelligence_service.app.enrichment.retry import NodeFailed

    def always_fails(*args, **kwargs):
        raise NodeFailed("description", "boom")

    with patch("services.food_intelligence_service.app.enrichment.node_factory.invoke_with_retry",
               side_effect=always_fails):
        result = text_nodes.description_node({"caption": "test caption"})

    assert result["description"] is None


def test_description_node_skips_empty_caption_without_calling_the_llm(mock_settings):
    from services.food_intelligence_service.app.enrichment.nodes import text_nodes

    with patch("services.food_intelligence_service.app.enrichment.node_factory.invoke_with_retry") as mock_invoke:
        result = text_nodes.description_node({"caption": "   "})

    mock_invoke.assert_not_called()
    assert result["description"] is None


def test_semiotic_text_node_writes_semiotic_text(mock_settings):
    from services.food_intelligence_service.app.enrichment.nodes import text_nodes
    from services.food_intelligence_service.app.enrichment.schema import SemioticTextOutput

    with patch("services.food_intelligence_service.app.enrichment.node_factory.invoke_with_retry",
               return_value=SemioticTextOutput(semiotic_text="Warm, family-oriented tone.")):
        result = text_nodes.semiotic_text_node({"caption": "test caption"})

    assert result["semiotic_text"].semiotic_text == "Warm, family-oriented tone."
