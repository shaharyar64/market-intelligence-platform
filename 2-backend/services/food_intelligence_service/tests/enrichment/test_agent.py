from contextlib import ExitStack
from unittest.mock import patch


def test_analyze_post_assembles_all_five_text_nodes(mock_settings):
    from services.food_intelligence_service.app.enrichment import agent
    from services.food_intelligence_service.app.enrichment.schema import (
        DescriptionOutput, KeywordsOutput, SemioticTextOutput, ThemesOutput, ProductFocusOutput,
        ThemeItem, ProductItem,
    )

    with patch.object(agent, "description_node", return_value={"description": DescriptionOutput(description="d", language="en")}), \
         patch.object(agent, "keywords_node", return_value={"keywords": KeywordsOutput(keywords=["k"])}), \
         patch.object(agent, "semiotic_text_node", return_value={"semiotic_text": SemioticTextOutput(semiotic_text="s")}), \
         patch.object(agent, "themes_node", return_value={"themes": ThemesOutput(themes=[ThemeItem(label="High protein", confidence=1.0, evidence=["e"])])}), \
         patch.object(agent, "product_focus_node", return_value={"product_focus": ProductFocusOutput(product_focus=[ProductItem(product="kefir", confidence=1.0, evidence=["e"])])}):
        result = agent.analyze_post({"text": "caption", "brand": {"name": "Nada"}, "platform": "instagram"})

    assert result["description"] == "d"
    assert result["language"] == "en"
    assert result["keywords"] == ["k"]
    assert result["semiotic"]["text"] == "s"
    assert result["semiotic"]["visual"] == {}
    assert result["themes"][0]["label"] == "High protein"
    assert result["product_focus"][0]["product"] == "kefir"
    assert result["functional_visual"] == []


def test_analyze_post_handles_empty_caption_without_calling_any_node(mock_settings):
    from services.food_intelligence_service.app.enrichment import agent

    node_names = ("description_node", "keywords_node", "semiotic_text_node", "themes_node",
                  "product_focus_node", "functional_visual_node", "semiotic_visual_node")
    with ExitStack() as stack:
        mocks = [stack.enter_context(patch.object(agent, name)) for name in node_names]
        result = agent.analyze_post({"text": "", "brand": {"name": "Nada"}, "platform": "instagram"})

    for mock_node in mocks:
        mock_node.assert_not_called()
    assert result["description"] == ""
    assert result["language"] is None
    assert result["keywords"] == []
    assert result["semiotic"] == {"text": "", "visual": {}}
    assert result["themes"] == []
    assert result["product_focus"] == []
    assert result["functional_visual"] == []


def test_analyze_post_runs_vision_nodes_for_image_only_post(mock_settings):
    from services.food_intelligence_service.app.enrichment import agent
    from services.food_intelligence_service.app.enrichment.schema import (
        FunctionalVisualOutput, FunctionalVisualItem, SemioticVisualOutput,
    )

    with patch.object(agent, "functional_visual_node", return_value={
             "functional_visual": FunctionalVisualOutput(functional_visual=[
                 FunctionalVisualItem(category="prepared_food", confidence=0.9, visual_evidence="plated dish")])}), \
         patch.object(agent, "semiotic_visual_node", return_value={
             "semiotic_visual": SemioticVisualOutput(premium=None, healthy=None, natural=None, modern=None,
                                                  traditional=None, sophisticated=None, indulgent=0.7)}), \
         patch.object(agent, "presigned_url", return_value="https://signed-url") as mock_presign:
        result = agent.analyze_post(
            {"text": "   ", "brand": {"name": "Nada"}, "platform": "instagram"},
            image_key="media/instagram/x.jpg",
        )

    mock_presign.assert_called_once_with("media/instagram/x.jpg")
    assert result["functional_visual"][0]["category"] == "prepared_food"
    assert result["semiotic"]["visual"]["indulgent"] == 0.7
    assert result["semiotic"]["text"] == ""
    assert result["description"] == ""
    assert result["language"] is None
    assert result["keywords"] == []
    assert result["themes"] == []
    assert result["product_focus"] == []


def test_analyze_post_includes_vision_nodes_when_image_key_given(mock_settings):
    from services.food_intelligence_service.app.enrichment import agent
    from services.food_intelligence_service.app.enrichment.schema import (
        DescriptionOutput, KeywordsOutput, SemioticTextOutput, ThemesOutput, ProductFocusOutput,
        FunctionalVisualOutput, FunctionalVisualItem, SemioticVisualOutput,
    )

    with patch.object(agent, "description_node", return_value={"description": DescriptionOutput(description="d", language="en")}), \
         patch.object(agent, "keywords_node", return_value={"keywords": KeywordsOutput(keywords=[])}), \
         patch.object(agent, "semiotic_text_node", return_value={"semiotic_text": SemioticTextOutput(semiotic_text="")}), \
         patch.object(agent, "themes_node", return_value={"themes": ThemesOutput(themes=[])}), \
         patch.object(agent, "product_focus_node", return_value={"product_focus": ProductFocusOutput(product_focus=[])}), \
         patch.object(agent, "functional_visual_node", return_value={"functional_visual": FunctionalVisualOutput(functional_visual=[FunctionalVisualItem(category="product", confidence=0.9, visual_evidence="jar visible")])}), \
         patch.object(agent, "semiotic_visual_node", return_value={"semiotic_visual": SemioticVisualOutput(premium=0.8, healthy=None, natural=None, modern=None, traditional=None, sophisticated=None, indulgent=None)}), \
         patch.object(agent, "presigned_url", return_value="https://signed-url"):
        result = agent.analyze_post(
            {"text": "caption", "brand": {"name": "Nada"}, "platform": "instagram"},
            image_key="media/instagram/x.jpg",
        )

    assert result["functional_visual"][0]["category"] == "product"
    assert result["semiotic"]["visual"]["premium"] == 0.8
    assert result["language"] == "en"


def test_analyze_post_skips_vision_when_no_image_key(mock_settings):
    from services.food_intelligence_service.app.enrichment import agent
    from services.food_intelligence_service.app.enrichment.schema import (
        DescriptionOutput, KeywordsOutput, SemioticTextOutput, ThemesOutput, ProductFocusOutput,
    )
    with patch.object(agent, "description_node", return_value={"description": DescriptionOutput(description="d", language="en")}), \
         patch.object(agent, "keywords_node", return_value={"keywords": KeywordsOutput(keywords=[])}), \
         patch.object(agent, "semiotic_text_node", return_value={"semiotic_text": SemioticTextOutput(semiotic_text="")}), \
         patch.object(agent, "themes_node", return_value={"themes": ThemesOutput(themes=[])}), \
         patch.object(agent, "product_focus_node", return_value={"product_focus": ProductFocusOutput(product_focus=[])}), \
         patch.object(agent, "presigned_url") as mock_presign:
        result = agent.analyze_post({"text": "caption", "brand": {"name": "Nada"}, "platform": "instagram"}, image_key=None)

    mock_presign.assert_not_called()
    assert result["functional_visual"] == []
    assert result["semiotic"]["visual"] == {}
    assert result["description"] == "d"
