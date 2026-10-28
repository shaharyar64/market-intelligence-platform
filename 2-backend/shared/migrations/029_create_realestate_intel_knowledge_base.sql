CREATE TABLE IF NOT EXISTS realestate_intel.knowledge_documents (
  document_id   text PRIMARY KEY,
  title         text NOT NULL,
  uploaded_by   text NOT NULL,
  file_s3_key   text,
  status        text NOT NULL CHECK (status IN ('processing', 'ready', 'failed')),
  error_message text,
  char_count    integer,
  chunk_count   integer,
  created_at    timestamptz NOT NULL DEFAULT now(),
  deleted_at    timestamptz
);

CREATE INDEX IF NOT EXISTS knowledge_documents_active_idx
  ON realestate_intel.knowledge_documents (created_at DESC)
  WHERE deleted_at IS NULL;

CREATE TABLE IF NOT EXISTS realestate_intel.knowledge_chunks (
  chunk_id      text PRIMARY KEY,
  document_id   text NOT NULL REFERENCES realestate_intel.knowledge_documents (document_id),
  chunk_index   integer NOT NULL,
  chunk_text    text NOT NULL,
  model         text NOT NULL,
  embedding     vector(1024) NOT NULL,
  created_at    timestamptz NOT NULL DEFAULT now()
);

CREATE INDEX IF NOT EXISTS knowledge_chunks_document_idx
  ON realestate_intel.knowledge_chunks (document_id);

CREATE INDEX IF NOT EXISTS knowledge_chunks_embedding_hnsw
  ON realestate_intel.knowledge_chunks USING hnsw (embedding vector_cosine_ops);
