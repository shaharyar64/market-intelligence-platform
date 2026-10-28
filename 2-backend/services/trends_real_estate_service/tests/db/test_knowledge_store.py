import os
from pathlib import Path

import pytest
from sqlalchemy import create_engine, text
from sqlalchemy.engine import make_url

TEST_POSTGRES_DSN = os.environ.get("TEST_POSTGRES_DSN")
pytestmark = pytest.mark.skipif(
    not TEST_POSTGRES_DSN,
    reason="Set TEST_POSTGRES_DSN to a scratch Postgres database (with pgvector) to run this test.",
)

_MIGRATION = (Path(__file__).resolve().parents[4]
              / "shared" / "migrations" / "029_create_realestate_intel_knowledge_base.sql")
_SCRATCH_MARKERS = ("scratch", "test", "tmp")


def _assert_scratch_database(dsn: str) -> None:
    name = make_url(dsn).database or ""
    if not any(marker in name.lower() for marker in _SCRATCH_MARKERS):
        raise RuntimeError(
            f"Refusing to run: TEST_POSTGRES_DSN points at database {name!r}, which does not look "
            f"like a scratch database. Point it at a throwaway database whose name contains one of "
            f"{_SCRATCH_MARKERS}."
        )


@pytest.fixture(scope="module")
def scratch_engine():
    _assert_scratch_database(TEST_POSTGRES_DSN)
    engine = create_engine(TEST_POSTGRES_DSN, pool_pre_ping=True)
    with engine.begin() as conn:
        conn.execute(text("DROP TABLE IF EXISTS realestate_intel.knowledge_chunks CASCADE"))
        conn.execute(text("DROP TABLE IF EXISTS realestate_intel.knowledge_documents CASCADE"))
        sql = _MIGRATION.read_text(encoding="utf-8")
        for statement in [s.strip() for s in sql.split(";") if s.strip()]:
            conn.execute(text(statement))
    yield engine
    engine.dispose()


def _columns(engine, table: str) -> set[str]:
    with engine.begin() as conn:
        rows = conn.execute(text(
            "SELECT column_name FROM information_schema.columns "
            "WHERE table_schema = 'realestate_intel' AND table_name = :t"), {"t": table})
        return {r[0] for r in rows}


def test_knowledge_documents_has_the_expected_columns(scratch_engine):
    assert _columns(scratch_engine, "knowledge_documents") == {
        "document_id", "title", "uploaded_by", "file_s3_key", "status", "error_message",
        "char_count", "chunk_count", "created_at", "deleted_at",
    }


def test_knowledge_chunks_has_the_expected_columns(scratch_engine):
    assert _columns(scratch_engine, "knowledge_chunks") == {
        "chunk_id", "document_id", "chunk_index", "chunk_text", "model", "embedding", "created_at",
    }


def test_knowledge_chunks_embedding_has_an_hnsw_index(scratch_engine):
    with scratch_engine.begin() as conn:
        rows = conn.execute(text(
            "SELECT indexdef FROM pg_indexes WHERE schemaname = 'realestate_intel' "
            "AND tablename = 'knowledge_chunks' AND indexname = 'knowledge_chunks_embedding_hnsw'"
        )).fetchall()
    assert len(rows) == 1
    assert "hnsw" in rows[0][0].lower()


def test_status_check_constraint_rejects_an_invalid_value(scratch_engine):
    with scratch_engine.begin() as conn:
        with pytest.raises(Exception):
            conn.execute(text(
                "INSERT INTO realestate_intel.knowledge_documents "
                "(document_id, title, uploaded_by, status) "
                "VALUES ('d1', 'T', 'user1', 'not-a-real-status')"))


def test_save_and_get_document_round_trips(scratch_engine, monkeypatch):
    from services.trends_real_estate_service.app.knowledge import store
    monkeypatch.setattr(store, "get_conn", scratch_engine.connect)
    store.save_document("kd1", "Q3 2026 Market Outlook", "admin@example.com")
    doc = store.get_document("kd1")
    assert doc["title"] == "Q3 2026 Market Outlook"
    assert doc["status"] == "processing"
    assert doc["file_s3_key"] is None
    assert doc["deleted_at"] is None


def test_update_document_status_sets_ready_fields(scratch_engine, monkeypatch):
    from services.trends_real_estate_service.app.knowledge import store
    monkeypatch.setattr(store, "get_conn", scratch_engine.connect)
    store.save_document("kd2", "T", "admin@example.com")
    store.update_document_status("kd2", "ready", char_count=1200, chunk_count=3)
    doc = store.get_document("kd2")
    assert doc["status"] == "ready"
    assert doc["char_count"] == 1200
    assert doc["chunk_count"] == 3


def test_update_document_status_records_a_failure(scratch_engine, monkeypatch):
    from services.trends_real_estate_service.app.knowledge import store
    monkeypatch.setattr(store, "get_conn", scratch_engine.connect)
    store.save_document("kd3", "T", "admin@example.com")
    store.update_document_status("kd3", "failed", error_message="No extractable text.")
    doc = store.get_document("kd3")
    assert doc["status"] == "failed"
    assert doc["error_message"] == "No extractable text."


def test_list_active_documents_excludes_deleted(scratch_engine, monkeypatch):
    from services.trends_real_estate_service.app.knowledge import store
    monkeypatch.setattr(store, "get_conn", scratch_engine.connect)
    store.save_document("kd4", "Keep me", "admin@example.com")
    store.save_document("kd5", "Delete me", "admin@example.com")
    store.delete_document("kd5")
    titles = {d["title"] for d in store.list_active_documents()}
    assert "Keep me" in titles
    assert "Delete me" not in titles


def test_save_chunks_assigns_sequential_indexes(scratch_engine, monkeypatch):
    from services.trends_real_estate_service.app.knowledge import store
    monkeypatch.setattr(store, "get_conn", scratch_engine.connect)
    store.save_document("kd6", "T", "admin@example.com")
    vec = [0.01] * 1024
    store.save_chunks("kd6", [("chunk one", vec), ("chunk two", vec)], model="test-model")
    with scratch_engine.connect() as conn:
        from sqlalchemy import text
        rows = conn.execute(text(
            "SELECT chunk_index, chunk_text FROM realestate_intel.knowledge_chunks "
            "WHERE document_id = 'kd6' ORDER BY chunk_index")).fetchall()
    assert [r[0] for r in rows] == [0, 1]
    assert [r[1] for r in rows] == ["chunk one", "chunk two"]


def test_delete_document_removes_chunks_and_soft_deletes_the_document(scratch_engine, monkeypatch):
    from services.trends_real_estate_service.app.knowledge import store
    monkeypatch.setattr(store, "get_conn", scratch_engine.connect)
    store.save_document("kd7", "T", "admin@example.com")
    vec = [0.01] * 1024
    store.save_chunks("kd7", [("chunk", vec)], model="test-model")
    store.delete_document("kd7")
    with scratch_engine.connect() as conn:
        from sqlalchemy import text
        remaining_chunks = conn.execute(text(
            "SELECT count(*) FROM realestate_intel.knowledge_chunks WHERE document_id = 'kd7'"
        )).scalar()
    assert remaining_chunks == 0
    doc = store.get_document("kd7")
    assert doc["deleted_at"] is not None


def test_search_knowledge_chunks_excludes_deleted_documents(scratch_engine, monkeypatch):
    from services.trends_real_estate_service.app.knowledge import store
    monkeypatch.setattr(store, "get_conn", scratch_engine.connect)
    near = [0.9] + [0.0] * 1023
    far = [0.0] * 1023 + [0.9]

    store.save_document("kd8", "Active doc", "admin@example.com")
    store.save_chunks("kd8", [("relevant chunk", near)], model="test-model")

    store.save_document("kd9", "Deleted doc", "admin@example.com")
    store.save_chunks("kd9", [("also relevant chunk", near)], model="test-model")
    store.delete_document("kd9")

    results = store.search_knowledge_chunks(near, model="test-model", limit=5)
    document_ids = {r["document_id"] for r in results}
    assert "kd8" in document_ids
    assert "kd9" not in document_ids


def test_document_status_returns_title_and_deleted_at(scratch_engine, monkeypatch):
    from services.trends_real_estate_service.app.knowledge import store
    monkeypatch.setattr(store, "get_conn", scratch_engine.connect)
    store.save_document("kd10", "Active", "admin@example.com")
    store.save_document("kd11", "Gone", "admin@example.com")
    store.delete_document("kd11")

    status = store.document_status({"kd10", "kd11", "kd-missing"})
    assert status["kd10"]["title"] == "Active"
    assert status["kd10"]["deleted_at"] is None
    assert status["kd11"]["title"] == "Gone"
    assert status["kd11"]["deleted_at"] is not None
    assert "kd-missing" not in status
