"""Postgres persistence for the Knowledge Base. Uses the same pooled
get_conn() every other store in this service uses, imported by name so
tests can monkeypatch it to a scratch connection.
"""
from services.food_intelligence_service.app.trends.store import get_conn


def save_document(document_id: str, title: str, uploaded_by: str, uploaded_by_sub: str) -> None:
    with get_conn() as conn, conn.cursor() as cur:
        cur.execute(
            """INSERT INTO food_intel.knowledge_documents
               (document_id, title, uploaded_by, uploaded_by_sub, status)
               VALUES (%(id)s, %(title)s, %(uploaded_by)s, %(uploaded_by_sub)s, 'processing')""",
            {"id": document_id, "title": title, "uploaded_by": uploaded_by,
             "uploaded_by_sub": uploaded_by_sub})


def _row(cur) -> dict | None:
    row = cur.fetchone()
    if row is None:
        return None
    cols = [d[0] for d in cur.description]
    return dict(zip(cols, row, strict=True))


def get_document(document_id: str) -> dict | None:
    with get_conn() as conn, conn.cursor() as cur:
        cur.execute(
            "SELECT * FROM food_intel.knowledge_documents WHERE document_id = %(id)s",
            {"id": document_id})
        return _row(cur)


def list_active_documents(limit: int = 50) -> list[dict]:
    with get_conn() as conn, conn.cursor() as cur:
        cur.execute(
            """SELECT * FROM food_intel.knowledge_documents
               WHERE deleted_at IS NULL ORDER BY created_at DESC LIMIT %(limit)s""",
            {"limit": limit})
        cols = [d[0] for d in cur.description]
        return [dict(zip(cols, row, strict=True)) for row in cur.fetchall()]


def update_document_status(document_id: str, status: str, *, char_count: int | None = None,
                           chunk_count: int | None = None, error_message: str | None = None) -> None:
    with get_conn() as conn, conn.cursor() as cur:
        cur.execute(
            """UPDATE food_intel.knowledge_documents
               SET status = %(status)s, char_count = %(char_count)s,
                   chunk_count = %(chunk_count)s, error_message = %(error_message)s
               WHERE document_id = %(id)s""",
            {"id": document_id, "status": status, "char_count": char_count,
             "chunk_count": chunk_count, "error_message": error_message})


def save_chunks(document_id: str, chunks: list[tuple[str, list[float]]], model: str) -> None:
    with get_conn() as conn, conn.cursor() as cur:
        for index, (chunk_text, embedding) in enumerate(chunks):
            cur.execute(
                """INSERT INTO food_intel.knowledge_chunks
                   (chunk_id, document_id, chunk_index, chunk_text, model, embedding)
                   VALUES (%(chunk_id)s, %(document_id)s, %(index)s, %(text)s, %(model)s,
                           %(embedding)s::vector)""",
                {"chunk_id": f"{document_id}-{index}", "document_id": document_id,
                 "index": index, "text": chunk_text, "model": model,
                 "embedding": "[" + ",".join(f"{v:.6f}" for v in embedding) + "]"})


def delete_document(document_id: str) -> None:
    with get_conn() as conn, conn.cursor() as cur:
        cur.execute(
            "DELETE FROM food_intel.knowledge_chunks WHERE document_id = %(id)s",
            {"id": document_id})
        cur.execute(
            "UPDATE food_intel.knowledge_documents SET deleted_at = now() "
            "WHERE document_id = %(id)s",
            {"id": document_id})


def search_knowledge_chunks(query_vector: list[float], model: str, limit: int = 3) -> list[dict]:
    vec = "[" + ",".join(f"{v:.6f}" for v in query_vector) + "]"
    with get_conn() as conn, conn.cursor() as cur:
        cur.execute(
            """SELECT c.chunk_id, c.document_id, c.chunk_text,
                      (c.embedding <=> %(vec)s::vector) AS distance
               FROM food_intel.knowledge_chunks c
               JOIN food_intel.knowledge_documents d ON d.document_id = c.document_id
               WHERE d.deleted_at IS NULL AND d.status = 'ready' AND c.model = %(model)s
               ORDER BY c.embedding <=> %(vec)s::vector
               LIMIT %(limit)s""",
            {"vec": vec, "model": model, "limit": limit})
        cols = [d[0] for d in cur.description]
        return [dict(zip(cols, row, strict=True)) for row in cur.fetchall()]


def knowledge_version() -> str:
    with get_conn() as conn, conn.cursor() as cur:
        cur.execute("""SELECT md5(coalesce(string_agg(document_id, ',' ORDER BY document_id), ''))
                       FROM food_intel.knowledge_documents
                       WHERE deleted_at IS NULL AND status = 'ready'""")
        return cur.fetchone()[0]


def document_status(document_ids: set[str]) -> dict[str, dict]:
    if not document_ids:
        return {}
    with get_conn() as conn, conn.cursor() as cur:
        cur.execute(
            """SELECT document_id, title, deleted_at FROM food_intel.knowledge_documents
               WHERE document_id = ANY(%(ids)s)""",
            {"ids": list(document_ids)})
        return {row[0]: {"title": row[1], "deleted_at": row[2]} for row in cur.fetchall()}
