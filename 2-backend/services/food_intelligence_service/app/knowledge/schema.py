"""Pydantic models for the Knowledge Base API responses."""
from datetime import datetime
from typing import Literal

from pydantic import BaseModel


class KnowledgeDocumentOut(BaseModel):
    document_id: str
    title: str
    status: Literal["processing", "ready", "failed"]
    chunk_count: int | None = None
    uploaded_by: str
    created_at: datetime
    error_message: str | None = None
    can_delete: bool = False
