from unittest.mock import patch

from fastapi.testclient import TestClient

from services.trends_real_estate_service.app.api import deps
from services.trends_real_estate_service.app.idea_testing.schema import ConceptExtraction
from services.trends_real_estate_service.app.idea_testing.service import ConceptNotFoundError
from services.trends_real_estate_service.app.main import app

client = TestClient(app)
app.dependency_overrides[deps.get_current_user] = lambda: {"username": "test-user", "sub": "test-user"}

_MODULE = "services.trends_real_estate_service.app.api.v1.idea_testing"


def test_post_concept_from_text_returns_extracted_fields():
    stub = ConceptExtraction(need="n", proposition="p", claims=[], category="cat",
                             audience="a", cues=[])
    with patch(f"{_MODULE}.extract_concept", return_value=stub), \
         patch(f"{_MODULE}.store.save_concept"):
        response = client.post("/api/v1/idea-testing/concepts",
                               data={"title": "Milestone plan", "raw_text": "A payment plan..."})
    assert response.status_code == 200
    body = response.json()
    assert body["extracted"]["category"] == "cat"
    assert "concept_id" in body


def test_post_concept_requires_text_or_file():
    response = client.post("/api/v1/idea-testing/concepts", data={"title": "No input"})
    assert response.status_code == 400


def test_post_concept_from_file_saves_a_null_file_s3_key():
    stub = ConceptExtraction(need="n", proposition="p", claims=[], category="cat",
                             audience="a", cues=[])
    with patch(f"{_MODULE}.extract_concept", return_value=stub), \
         patch(f"{_MODULE}.store.save_concept") as save:
        response = client.post(
            "/api/v1/idea-testing/concepts",
            data={"title": "Concept card"},
            files={"file": ("card.png", b"\x89PNG...", "image/png")})
    assert response.status_code == 200
    assert save.call_args[0][5] is None


def test_post_concept_from_file_passes_optional_notes_to_extraction_and_storage():
    stub = ConceptExtraction(need="n", proposition="p", claims=[], category="cat",
                             audience="a", cues=[])
    with patch(f"{_MODULE}.extract_concept", return_value=stub) as extract, \
         patch(f"{_MODULE}.store.save_concept") as save:
        response = client.post(
            "/api/v1/idea-testing/concepts",
            data={"title": "Brochure", "raw_text": "Handover in Q4 2027."},
            files={"file": ("card.pdf", b"%PDF-1.4...", "application/pdf")})
    assert response.status_code == 200
    assert extract.call_args[0][0] == "Handover in Q4 2027."
    assert extract.call_args[0][3] == b"%PDF-1.4..."
    assert save.call_args[0][4] == "Handover in Q4 2027."


def test_post_concept_returns_400_when_the_file_cannot_be_parsed():
    with patch(f"{_MODULE}.extract_concept", side_effect=ValueError("unreadable")):
        response = client.post(
            "/api/v1/idea-testing/concepts",
            data={"title": "Corrupt card"},
            files={"file": ("card.png", b"not-a-real-image", "image/png")})
    assert response.status_code == 400


def test_post_concept_returns_400_for_a_pdf_with_no_extractable_text():
    with patch(f"{_MODULE}.extract_concept", side_effect=ValueError("empty pdf text")):
        response = client.post(
            "/api/v1/idea-testing/concepts",
            data={"title": "Scanned PDF"},
            files={"file": ("card.pdf", b"%PDF-1.4...", "application/pdf")})
    assert response.status_code == 400


def test_post_concept_rejects_a_file_over_the_size_cap():
    with patch(f"{_MODULE}._MAX_UPLOAD_BYTES", 10), \
         patch(f"{_MODULE}.extract_concept") as extract:
        response = client.post(
            "/api/v1/idea-testing/concepts",
            data={"title": "Big file"},
            files={"file": ("card.png", b"x" * 100, "image/png")})
    assert response.status_code == 400
    extract.assert_not_called()


def test_post_assess_rejects_more_than_three_concepts():
    response = client.post("/api/v1/idea-testing/assess", json={
        "concept_ids": ["c1", "c2", "c3", "c4"], "mode": "multiple", "test_type": "quick-idea"})
    assert response.status_code == 422  # Pydantic max_length on concept_ids


def test_post_assess_returns_the_service_result():
    with patch(f"{_MODULE}.trend_service.latest_run_id", return_value="run-1"), \
         patch(f"{_MODULE}.assess_and_compare",
              return_value={"assessments": [{"assessment_id": "a1", "overall_score": 70}],
                           "comparison": None}):
        response = client.post("/api/v1/idea-testing/assess", json={
            "concept_ids": ["c1"], "mode": "single", "test_type": "quick-idea"})
    assert response.status_code == 200
    assert response.json()["assessments"][0]["assessment_id"] == "a1"


def test_post_assess_returns_404_when_the_concept_does_not_exist():
    with patch(f"{_MODULE}.trend_service.latest_run_id", return_value="run-1"), \
         patch(f"{_MODULE}.assess_and_compare",
              side_effect=ConceptNotFoundError("No concept with id 'nope'.")):
        response = client.post("/api/v1/idea-testing/assess", json={
            "concept_ids": ["nope"], "mode": "single", "test_type": "quick-idea"})
    assert response.status_code == 404


def test_post_assess_does_not_leak_a_pydantic_validation_error_as_422():
    # A ValidationError raised deep in the pipeline (e.g. a malformed stored
    # `extracted` blob) is a ValueError subclass. It must not be caught by a
    # broad `except ValueError` and turned into a 422 that echoes internal
    # detail -- it should fall through to the generic internal_error 500.
    from pydantic import ValidationError
    try:
        ConceptExtraction()
    except ValidationError as e:
        validation_error = e
    with patch(f"{_MODULE}.trend_service.latest_run_id", return_value="run-1"), \
         patch(f"{_MODULE}.assess_and_compare", side_effect=validation_error):
        response = client.post("/api/v1/idea-testing/assess", json={
            "concept_ids": ["c1"], "mode": "single", "test_type": "quick-idea"})
    assert response.status_code == 500
    assert "need" not in response.text  # no leaked Pydantic field detail


def test_get_assessment_returns_404_when_missing():
    with patch(f"{_MODULE}.store.get_assessment", return_value=None):
        response = client.get("/api/v1/idea-testing/assessments/does-not-exist")
    assert response.status_code == 404


def test_get_assessment_returns_the_stored_row():
    with patch(f"{_MODULE}.store.get_assessment",
              return_value={"assessment_id": "a1", "concept_id": "c1", "overall_score": 70}), \
         patch(f"{_MODULE}.store.get_concept",
              return_value={"concept_id": "c1", "created_by": "test-user"}):
        response = client.get("/api/v1/idea-testing/assessments/a1")
    assert response.status_code == 200
    assert response.json()["assessment_id"] == "a1"


def test_get_assessment_response_never_includes_the_cache_key():
    with patch(f"{_MODULE}.store.get_assessment",
              return_value={"assessment_id": "a1", "concept_id": "c1", "overall_score": 70,
                           "cache_key": "should-not-leak"}), \
         patch(f"{_MODULE}.store.get_concept",
              return_value={"concept_id": "c1", "created_by": "test-user"}):
        response = client.get("/api/v1/idea-testing/assessments/a1")
    assert response.status_code == 200
    assert "cache_key" not in response.json()


def test_get_assessment_returns_404_when_owned_by_a_different_user():
    with patch(f"{_MODULE}.store.get_assessment",
              return_value={"assessment_id": "a1", "concept_id": "c1", "overall_score": 70}), \
         patch(f"{_MODULE}.store.get_concept",
              return_value={"concept_id": "c1", "created_by": "someone-else"}):
        response = client.get("/api/v1/idea-testing/assessments/a1")
    assert response.status_code == 404


def test_every_route_requires_auth():
    app.dependency_overrides.pop(deps.get_current_user, None)
    try:
        response = client.get("/api/v1/idea-testing/assessments/a1")
        assert response.status_code in (401, 403)
    finally:
        app.dependency_overrides[deps.get_current_user] = lambda: {"username": "test-user",
                                                                    "sub": "test-user"}
