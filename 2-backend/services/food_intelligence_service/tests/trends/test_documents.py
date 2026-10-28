import json
from unittest.mock import MagicMock, patch

from services.food_intelligence_service.app.trends import documents


def test_document_tag_carries_the_analysis_variant():
    assert documents.document_tag().endswith("+analysis-v1")


def test_semantic_document_builds_every_section():
    analysis = {
        "description": "A creamy labneh bowl with olive oil.",
        "themes": [{"label": "Creamy texture"}, {"label": "High protein"}],
        "product_focus": [{"product": "labneh"}, {"product": "olive oil"}],
        "semiotic": {"text": "The tone is warm and homely.",
                     "visual": {"indulgent": 0.9, "rustic": 0.4}},
        "functional_visual": [{"visual_evidence": "a white bowl on a wooden table"}],
    }
    doc = documents.semantic_document(analysis)
    assert "Description:\nA creamy labneh bowl with olive oil." in doc
    assert "Themes:\nCreamy texture; High protein." in doc
    # Food's product_focus fills the same slot real estate fills with offering_focus.
    assert "Offering:\nlabneh; olive oil." in doc
    assert "Semantic Context:\nThe tone is warm and homely." in doc
    # Only visuals at or above 0.7 are named; rustic at 0.4 is dropped.
    assert "indulgent" in doc
    assert "rustic" not in doc
    assert "a white bowl on a wooden table" in doc


def test_semantic_document_accepts_a_json_string():
    doc = documents.semantic_document(json.dumps({"description": "Grilled kofta."}))
    assert "Grilled kofta." in doc


def test_semantic_document_returns_empty_for_missing_or_malformed_analysis():
    assert documents.semantic_document(None) == ""
    assert documents.semantic_document("not json at all") == ""
    assert documents.semantic_document([1, 2, 3]) == ""


def test_semantic_document_skips_absent_sections():
    doc = documents.semantic_document({"description": "Just a description."})
    assert doc == "Description:\nJust a description."


def _mock_embedding_client(captured_batches):
    def fake_create(**kwargs):
        captured_batches.append(kwargs["input"])
        return MagicMock(data=[MagicMock(embedding=[0.0]) for _ in kwargs["input"]])

    client = MagicMock()
    client.embeddings.create.side_effect = fake_create
    return client


def test_run_embedding_splits_batches_that_would_exceed_the_token_budget():
    posts = [{"platform": "instagram", "post_id": f"p{i}"} for i in range(6)]
    analyses = {("instagram", f"p{i}"): {"description": "word " * 40} for i in range(6)}
    captured_batches: list[list[str]] = []

    with patch.object(documents, "OpenAI", return_value=_mock_embedding_client(captured_batches)), \
         patch.object(documents, "TOKEN_BUDGET", 100), \
         patch.object(documents.store, "posts_missing_embedding", return_value=posts), \
         patch.object(documents.store, "fetch_analyses", return_value=analyses), \
         patch.object(documents.store, "upsert_post_embeddings", side_effect=lambda rows: len(rows)):
        result = documents.run_embedding()

    assert len(captured_batches) > 1
    for batch_inputs in captured_batches:
        assert sum(documents._token_count(text) for text in batch_inputs) <= 100
    assert result["embedded"] == 6


def test_run_embedding_sends_a_single_oversized_document_alone():
    posts = [{"platform": "instagram", "post_id": "big"}]
    analyses = {("instagram", "big"): {"description": "word " * 40}}
    captured_batches: list[list[str]] = []

    with patch.object(documents, "OpenAI", return_value=_mock_embedding_client(captured_batches)), \
         patch.object(documents, "TOKEN_BUDGET", 10), \
         patch.object(documents.store, "posts_missing_embedding", return_value=posts), \
         patch.object(documents.store, "fetch_analyses", return_value=analyses), \
         patch.object(documents.store, "upsert_post_embeddings", side_effect=lambda rows: len(rows)):
        result = documents.run_embedding()

    assert len(captured_batches) == 1
    assert len(captured_batches[0]) == 1
    assert result["embedded"] == 1
