from unittest.mock import patch

from services.trends_real_estate_service.app.knowledge import service


def _fake_pdf_text(data, max_chars=None):
    return "Sentence one. Sentence two. Sentence three."


def test_ingest_document_saves_chunks_and_marks_ready():
    embed_query = lambda text: [0.01] * 1024  # noqa: E731
    with patch(f"{service.__name__}.extract_pdf_text", side_effect=_fake_pdf_text), \
         patch.object(service.store, "save_chunks") as save_chunks, \
         patch.object(service.store, "update_document_status") as update_status:
        service.ingest_document("d1", b"%PDF-1.4...", embed_query)
    save_chunks.assert_called_once()
    call_document_id, call_chunks, call_model = save_chunks.call_args[0]
    assert call_document_id == "d1"
    assert len(call_chunks) == 1  # short text, one chunk
    assert call_chunks[0][0] == "Sentence one. Sentence two. Sentence three."
    update_status.assert_called_once_with(
        "d1", "ready", char_count=len("Sentence one. Sentence two. Sentence three."), chunk_count=1)


def test_ingest_document_marks_failed_when_the_pdf_cannot_be_read():
    embed_query = lambda text: [0.01] * 1024  # noqa: E731
    with patch(f"{service.__name__}.extract_pdf_text", side_effect=ValueError("Stream has ended unexpectedly")), \
         patch.object(service.store, "update_document_status") as update_status, \
         patch.object(service.store, "save_chunks") as save_chunks:
        service.ingest_document("d2", b"%PDF-1.4...", embed_query)
    save_chunks.assert_not_called()
    update_status.assert_called_once_with("d2", "failed", error_message=service._UNREADABLE_MESSAGE)


def test_ingest_document_explains_that_a_scanned_pdf_has_no_text_layer():
    embed_query = lambda text: [0.01] * 1024  # noqa: E731
    with patch(f"{service.__name__}.extract_pdf_text", return_value="   "), \
         patch.object(service.store, "update_document_status") as update_status, \
         patch.object(service.store, "save_chunks") as save_chunks:
        service.ingest_document("d3", b"%PDF-1.4...", embed_query)
    save_chunks.assert_not_called()
    update_status.assert_called_once_with("d3", "failed", error_message=service._NO_TEXT_MESSAGE)
    # The message has to tell the user what to do about it, not just that it failed.
    assert "scanned" in service._NO_TEXT_MESSAGE.lower()


def test_ingest_document_marks_failed_when_embedding_raises():
    embed_query = lambda text: (_ for _ in ()).throw(RuntimeError("rate limited"))
    with patch(f"{service.__name__}.extract_pdf_text", side_effect=_fake_pdf_text), \
         patch.object(service.store, "update_document_status") as update_status, \
         patch.object(service.store, "save_chunks") as save_chunks:
        service.ingest_document("d4", b"%PDF-1.4...", embed_query)
    save_chunks.assert_not_called()
    update_status.assert_called_once_with("d4", "failed", error_message="rate limited")


def test_ingest_document_uses_a_larger_char_cap_than_idea_testing():
    # The whole reason extract_pdf_text takes max_chars as a parameter (Task 2)
    # is so a full report isn't cut at idea_testing's 50,000-char concept-card
    # limit. Confirm this call site actually asks for more.
    embed_query = lambda text: [0.01] * 1024  # noqa: E731
    with patch(f"{service.__name__}.extract_pdf_text", side_effect=_fake_pdf_text) as extract, \
         patch.object(service.store, "save_chunks"), \
         patch.object(service.store, "update_document_status"):
        service.ingest_document("d5", b"%PDF-1.4...", embed_query)
    _, kwargs = extract.call_args
    assert kwargs["max_chars"] > 50_000


def test_delete_document_delegates_to_store():
    with patch.object(service.store, "delete_document") as delete:
        service.delete_document("d6")
    delete.assert_called_once_with("d6")
