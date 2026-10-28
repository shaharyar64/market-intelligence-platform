from unittest.mock import patch

import pytest
from fastapi.testclient import TestClient

from services.trends_real_estate_service.app.api import deps
from services.trends_real_estate_service.app.main import app

client = TestClient(app)
_MODULE = "services.trends_real_estate_service.app.api.v1.knowledge"

_ADMIN_USER = {"username": "8f3c1a2e-uuid-sub", "sub": "8f3c1a2e-uuid-sub",
              "cognito:groups": ["Admins"]}
_REGULAR_USER = {"username": "user@example.com", "cognito:groups": []}


def _as(user):
    app.dependency_overrides[deps.get_current_user] = lambda: user
    return client


@pytest.fixture(autouse=True)
def _restore_overrides():
    saved = dict(app.dependency_overrides)
    yield
    app.dependency_overrides.clear()
    app.dependency_overrides.update(saved)


def test_post_document_requires_admin():
    _as(_REGULAR_USER)
    response = client.post("/api/v1/knowledge/documents", data={"title": "T"},
                           files={"file": ("brief.pdf", b"%PDF-1.4...", "application/pdf")})
    assert response.status_code == 403


def test_post_document_saves_and_schedules_ingestion():
    _as(_ADMIN_USER)
    with patch(f"{_MODULE}.store.save_document") as save, \
         patch(f"{_MODULE}.service.ingest_document") as ingest:
        response = client.post(
            "/api/v1/knowledge/documents", data={"title": "Q3 Outlook"},
            files={"file": ("brief.pdf", b"%PDF-1.4...", "application/pdf")})
    assert response.status_code == 200
    body = response.json()
    assert body["status"] == "processing"
    assert "document_id" in body
    save.assert_called_once()
    ingest.assert_called_once()  # scheduled as a background task


def test_post_document_uses_resolved_email_as_uploaded_by():
    _as(_ADMIN_USER)
    with patch(f"{_MODULE}.store.save_document") as save, \
         patch(f"{_MODULE}.service.ingest_document"), \
         patch(f"{_MODULE}.resolve_email", return_value="admin@example.com") as resolve:
        response = client.post(
            "/api/v1/knowledge/documents", data={"title": "Q3 Outlook"},
            files={"file": ("brief.pdf", b"%PDF-1.4...", "application/pdf")})
    assert response.status_code == 200
    resolve.assert_called_once_with(_ADMIN_USER["sub"])
    _, args, _ = save.mock_calls[0]
    assert args[2] == "admin@example.com"


def test_post_document_falls_back_to_username_when_resolve_email_fails():
    _as(_ADMIN_USER)
    with patch(f"{_MODULE}.store.save_document") as save, \
         patch(f"{_MODULE}.service.ingest_document"), \
         patch(f"{_MODULE}.resolve_email", return_value=None) as resolve:
        response = client.post(
            "/api/v1/knowledge/documents", data={"title": "Q3 Outlook"},
            files={"file": ("brief.pdf", b"%PDF-1.4...", "application/pdf")})
    assert response.status_code == 200
    resolve.assert_called_once_with(_ADMIN_USER["sub"])
    _, args, _ = save.mock_calls[0]
    assert args[2] == _ADMIN_USER["username"]


def test_post_document_rejects_non_pdf():
    _as(_ADMIN_USER)
    response = client.post(
        "/api/v1/knowledge/documents", data={"title": "T"},
        files={"file": ("card.png", b"\x89PNG...", "image/png")})
    assert response.status_code == 400


def test_get_documents_lists_active_documents():
    rows = [{"document_id": "d1", "title": "T", "status": "ready", "chunk_count": 3,
            "uploaded_by": "admin@example.com", "created_at": "2026-09-17T00:00:00Z"}]
    _as(_REGULAR_USER)
    with patch(f"{_MODULE}.store.list_active_documents", return_value=rows):
        response = client.get("/api/v1/knowledge/documents")
    assert response.status_code == 200
    assert response.json()["documents"][0]["document_id"] == "d1"


def test_delete_document_requires_admin():
    _as(_REGULAR_USER)
    response = client.delete("/api/v1/knowledge/documents/d1")
    assert response.status_code == 403


def test_delete_document_calls_service():
    _as(_ADMIN_USER)
    with patch(f"{_MODULE}.store.get_document", return_value={"document_id": "d1"}), \
         patch(f"{_MODULE}.service.delete_document") as delete:
        response = client.delete("/api/v1/knowledge/documents/d1")
    assert response.status_code == 200
    delete.assert_called_once_with("d1")


def test_delete_document_returns_404_when_missing():
    _as(_ADMIN_USER)
    with patch(f"{_MODULE}.store.get_document", return_value=None):
        response = client.delete("/api/v1/knowledge/documents/does-not-exist")
    assert response.status_code == 404
