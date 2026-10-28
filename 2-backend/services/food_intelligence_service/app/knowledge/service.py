"""Orchestrates Knowledge Base document ingestion: extract -> chunk ->
embed -> save. Runs as a FastAPI background task (see api/v1/knowledge.py)
so a large PDF's embedding calls never block the upload request.
"""
from services.food_intelligence_service.app.core.config import get_settings
from services.food_intelligence_service.app.knowledge import store
from services.food_intelligence_service.app.knowledge.chunking import chunk_text
from services.food_intelligence_service.app.services.pdf_text import extract_pdf_text
from services.food_intelligence_service.app.trends.store import model_tag

# A full research report is not a short concept card -- idea_testing's
# 50,000-char cap exists for a different kind of document. This is deliberately
# larger, not shared with idea_testing/extraction.py's _MAX_PDF_CHARS.
_MAX_DOCUMENT_CHARS = 200_000

_NO_TEXT_MESSAGE = (
    "No text could be read from this PDF. Scanned or image-only PDFs are not supported yet, "
    "so try a PDF whose text can be selected in a PDF viewer."
)
_UNREADABLE_MESSAGE = "This PDF could not be read. It may be corrupted or password protected."


def ingest_document(document_id: str, pdf_bytes: bytes, embed_query) -> None:
    try:
        text = extract_pdf_text(pdf_bytes, max_chars=_MAX_DOCUMENT_CHARS)
    except Exception:
        store.update_document_status(document_id, "failed", error_message=_UNREADABLE_MESSAGE)
        return
    if not text.strip():
        store.update_document_status(document_id, "failed", error_message=_NO_TEXT_MESSAGE)
        return

    try:
        pieces = chunk_text(text)
        settings = get_settings()
        model = model_tag(settings.TREND_EMBED_MODEL, settings.TREND_EMBED_DIM)
        chunks = [(piece, embed_query(piece)) for piece in pieces]
    except Exception as exc:
        store.update_document_status(document_id, "failed", error_message=str(exc))
        return

    try:
        store.save_chunks(document_id, chunks, model)
        store.update_document_status(document_id, "ready", char_count=len(text), chunk_count=len(chunks))
    except Exception as exc:
        store.update_document_status(document_id, "failed", error_message=str(exc))
        return


def delete_document(document_id: str) -> None:
    store.delete_document(document_id)
