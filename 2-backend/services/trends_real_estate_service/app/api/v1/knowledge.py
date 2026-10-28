import uuid
from typing import Any

from fastapi import APIRouter, BackgroundTasks, Depends, File, Form, HTTPException, UploadFile

from services.trends_real_estate_service.app.api.deps import get_current_user
from services.trends_real_estate_service.app.api.errors import internal_error
from services.trends_real_estate_service.app.assistant.agent import embed_query
from services.trends_real_estate_service.app.knowledge import service, store
from services.trends_real_estate_service.app.knowledge.schema import KnowledgeDocumentOut
from services.trends_real_estate_service.app.services.user_directory import resolve_email

router = APIRouter(prefix="/knowledge", tags=["Knowledge Base"])

_MAX_UPLOAD_BYTES = 15 * 1024 * 1024


def _require_admin(current_user: dict[str, Any] = Depends(get_current_user)) -> dict[str, Any]:
    if "Admins" not in (current_user.get("cognito:groups") or []):
        raise HTTPException(status_code=403, detail="Admin access required.")
    return current_user


@router.post("/documents")
async def create_document(
    background_tasks: BackgroundTasks,
    title: str = Form(...),
    file: UploadFile = File(...),
    current_user: dict[str, Any] = Depends(_require_admin),
):
    if file.content_type != "application/pdf":
        raise HTTPException(status_code=400, detail="Only PDF documents are supported.")
    data = await file.read()
    if len(data) > _MAX_UPLOAD_BYTES:
        raise HTTPException(status_code=400, detail="File too large.")

    document_id = uuid.uuid4().hex
    try:
        uploaded_by = resolve_email(current_user.get("sub", "")) or current_user["username"]
        store.save_document(document_id, title, uploaded_by)
    except Exception:
        raise internal_error("knowledge_create_document") from None

    background_tasks.add_task(service.ingest_document, document_id, data, embed_query)
    return {"document_id": document_id, "status": "processing"}


@router.get("/documents")
async def list_documents(current_user: dict[str, Any] = Depends(get_current_user)):
    try:
        documents = store.list_active_documents()
    except Exception:
        raise internal_error("knowledge_list_documents") from None
    return {"documents": [KnowledgeDocumentOut(**row) for row in documents]}


@router.delete("/documents/{document_id}")
async def delete_document(document_id: str,
                          current_user: dict[str, Any] = Depends(_require_admin)):
    try:
        existing = store.get_document(document_id)
    except Exception:
        raise internal_error("knowledge_delete_document_lookup") from None
    if existing is None or existing.get("deleted_at") is not None:
        raise HTTPException(status_code=404, detail="Document not found.")
    try:
        service.delete_document(document_id)
    except Exception:
        raise internal_error("knowledge_delete_document") from None
    return {"deleted": True}
