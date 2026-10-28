import { apiFetch } from "@/lib/apiClient";

const BASE = "/api/v1/trends-real-estate/knowledge";

export type DocumentStatus = "processing" | "ready" | "failed";

export type KnowledgeDocument = {
  document_id: string;
  title: string;
  status: DocumentStatus;
  chunk_count: number | null;
  uploaded_by: string;
  created_at: string;
  error_message: string | null;
};

async function getJson<T>(endpoint: string, init: RequestInit = {}): Promise<T> {
  const res = await apiFetch(endpoint, init);
  if (!res.ok) {
    const detail = await res.text().catch(() => "");
    throw new Error(`${res.status} ${detail || res.statusText}`);
  }
  return res.json() as Promise<T>;
}

export function listDocuments() {
  return getJson<{ documents: KnowledgeDocument[] }>(`${BASE}/documents`);
}

export function uploadDocument(title: string, file: File) {
  const form = new FormData();
  form.set("title", title);
  form.set("file", file);
  return getJson<{ document_id: string; status: DocumentStatus }>(
    `${BASE}/documents`, { method: "POST", body: form },
  );
}

export function deleteDocument(documentId: string) {
  return getJson<{ deleted: boolean }>(
    `${BASE}/documents/${encodeURIComponent(documentId)}`, { method: "DELETE" },
  );
}
