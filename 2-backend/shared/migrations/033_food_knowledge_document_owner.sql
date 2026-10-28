-- Who may delete a Knowledge Base document.
--
-- uploaded_by is a display email resolved at upload time and can fall back to
-- another identifier, so it is not safe to authorize on. The uploader's Cognito
-- sub is stable. Rows uploaded before this column existed stay NULL, and the API
-- treats a NULL owner as deletable by nobody.

ALTER TABLE food_intel.knowledge_documents ADD COLUMN IF NOT EXISTS uploaded_by_sub text;
