from services.trends_real_estate_service.app.knowledge.schema import KnowledgeDocumentOut


def test_knowledge_document_out_round_trips_expected_fields():
    doc = KnowledgeDocumentOut(
        document_id="d1", title="Q3 2026 Market Outlook", status="ready",
        chunk_count=12, uploaded_by="admin@example.com", created_at="2026-09-17T00:00:00Z")
    dumped = doc.model_dump()
    assert dumped["document_id"] == "d1"
    assert dumped["status"] == "ready"
    assert dumped["chunk_count"] == 12
