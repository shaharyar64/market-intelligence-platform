"use client";

import { useState } from "react";
import { FileText, Loader2, Trash2 } from "lucide-react";

import { deleteDocument, type KnowledgeDocument } from "@/lib/knowledgeBase";
import { friendlyError } from "@/lib/foodIntelligence";

const STATUS_LABEL: Record<KnowledgeDocument["status"], string> = {
  processing: "Processing", ready: "Ready", failed: "Failed",
};
const STATUS_TOKEN: Record<KnowledgeDocument["status"], string> = {
  processing: "var(--fi-mainstream-tx)", ready: "var(--fi-growth-tx)", failed: "var(--fi-danger-tx)",
};

function formatAdded(iso: string): string {
  const date = new Date(iso);
  if (Number.isNaN(date.getTime())) return "";
  return date.toLocaleDateString(undefined, { day: "numeric", month: "short", year: "numeric" });
}

function StatusCell({ doc }: { doc: KnowledgeDocument }) {
  return (
    <span className="inline-flex items-center gap-1.5 text-xs font-semibold"
      style={{ color: STATUS_TOKEN[doc.status] }}>
      {doc.status === "processing"
        ? <Loader2 size={12} aria-hidden="true" className="animate-spin" />
        : <span aria-hidden="true" className="size-1.5 rounded-full"
            style={{ background: STATUS_TOKEN[doc.status] }} />}
      {STATUS_LABEL[doc.status]}
    </span>
  );
}

export default function DocumentList({
  documents, canManage, onDeleted,
}: {
  documents: KnowledgeDocument[];
  canManage: boolean;
  onDeleted: () => void;
}) {
  const [deletingId, setDeletingId] = useState<string | null>(null);
  const [confirmingId, setConfirmingId] = useState<string | null>(null);
  const [error, setError] = useState<string | null>(null);

  async function handleDelete(documentId: string) {
    setDeletingId(documentId);
    setConfirmingId(null);
    setError(null);
    try {
      await deleteDocument(documentId);
      onDeleted();
    } catch (e) {
      setError(friendlyError(e));
    } finally {
      setDeletingId(null);
    }
  }

  if (documents.length === 0) {
    return (
      <div className="chart-card flex min-h-64 flex-1 flex-col items-center justify-center gap-3 rounded-2xl px-6 py-16 text-center">
        <FileText size={24} aria-hidden="true" style={{ color: "var(--muted-tx)" }} />
        <p style={{ color: "var(--title-tx)" }} className="text-sm font-medium">
          No documents yet
        </p>
        <p style={{ color: "var(--muted-tx)" }} className="max-w-xs text-xs">
          Upload a research report or market study and Idea Testing will cite it alongside the
          posts and trends it already reads.
        </p>
      </div>
    );
  }

  const processingCount = documents.filter((d) => d.status === "processing").length;

  return (
    <div className="flex flex-1 flex-col gap-3">
      {error && (
        <p role="alert" style={{ color: "var(--fi-danger-tx)" }} className="text-sm">{error}</p>
      )}

      {/* Polling swaps status in place, so announce the change rather than letting it pass silently. */}
      <span aria-live="polite" className="sr-only">
        {processingCount > 0
          ? `${processingCount} document${processingCount === 1 ? "" : "s"} still processing`
          : "All documents processed"}
      </span>

      <div className="chart-card min-h-64 flex-1 overflow-hidden rounded-2xl">
        <table className="w-full border-collapse text-left">
          <caption className="sr-only">Knowledge base documents</caption>
          <thead>
            <tr style={{ borderBottom: "1px solid var(--card-bd)" }}>
              <th scope="col" style={{ color: "var(--muted-tx)" }}
                className="px-5 py-3 text-xs font-semibold">Document</th>
              <th scope="col" style={{ color: "var(--muted-tx)" }}
                className="hidden px-5 py-3 text-xs font-semibold sm:table-cell">Status</th>
              <th scope="col" style={{ color: "var(--muted-tx)" }}
                className="hidden px-5 py-3 text-right text-xs font-semibold lg:table-cell">Chunks</th>
              <th scope="col" style={{ color: "var(--muted-tx)" }}
                className="hidden px-5 py-3 text-xs font-semibold lg:table-cell">Added</th>
              <th scope="col" style={{ color: "var(--muted-tx)" }}
                className="hidden px-5 py-3 text-xs font-semibold md:table-cell">Uploaded by</th>
              {canManage && (
                <th scope="col" style={{ color: "var(--muted-tx)" }}
                  className="px-5 py-3 text-right text-xs font-semibold">Actions</th>
              )}
            </tr>
          </thead>
          <tbody>
            {documents.map((doc, i) => {
              const confirming = confirmingId === doc.document_id;
              const deleting = deletingId === doc.document_id;
              return (
                <tr key={doc.document_id}
                  style={i > 0 ? { borderTop: "1px solid var(--card-bd)" } : undefined}>
                  <td className="px-5 py-3 align-top">
                    <span style={{ color: "var(--title-tx)" }}
                      className="block text-sm font-medium">{doc.title}</span>
                    {/* Without the reason, a failed upload is a dead end the uploader cannot act on. */}
                    {doc.status === "failed" && doc.error_message && (
                      <span style={{ color: "var(--fi-danger-tx)" }}
                        className="mt-1 block max-w-prose text-xs">{doc.error_message}</span>
                    )}
                    <span style={{ color: "var(--muted-tx)" }}
                      className="mt-1 block text-xs sm:hidden">
                      {STATUS_LABEL[doc.status]}
                      {doc.chunk_count != null ? ` · ${doc.chunk_count} chunks` : ""}
                    </span>
                  </td>
                  <td className="hidden px-5 py-3 align-top sm:table-cell">
                    <StatusCell doc={doc} />
                  </td>
                  <td style={{ color: "var(--body-tx)", fontVariantNumeric: "tabular-nums" }}
                    className="hidden px-5 py-3 text-right align-top text-sm lg:table-cell">
                    {doc.chunk_count ?? "--"}
                  </td>
                  <td style={{ color: "var(--body-tx)", fontVariantNumeric: "tabular-nums" }}
                    className="hidden whitespace-nowrap px-5 py-3 align-top text-sm lg:table-cell">
                    {formatAdded(doc.created_at)}
                  </td>
                  <td style={{ color: "var(--body-tx)" }}
                    className="hidden max-w-[16rem] truncate px-5 py-3 align-top text-sm md:table-cell">
                    {doc.uploaded_by}
                  </td>
                  {canManage && (
                    <td className="px-5 py-3 text-right align-top">
                      {confirming ? (
                        <span className="inline-flex items-center gap-1">
                          <button type="button" onClick={() => handleDelete(doc.document_id)}
                            style={{ color: "var(--fi-danger-tx)" }}
                            className="inline-flex min-h-11 items-center rounded-lg px-2 text-xs font-semibold">
                            Delete
                          </button>
                          <button type="button" onClick={() => setConfirmingId(null)}
                            style={{ color: "var(--muted-tx)" }}
                            className="inline-flex min-h-11 items-center rounded-lg px-2 text-xs font-medium">
                            Cancel
                          </button>
                        </span>
                      ) : (
                        <button
                          type="button"
                          onClick={() => setConfirmingId(doc.document_id)}
                          disabled={deleting}
                          aria-label={`Delete ${doc.title}`}
                          style={{ color: "var(--muted-tx)" }}
                          className="inline-flex size-11 items-center justify-center rounded-lg transition-colors hover:text-[var(--fi-danger-tx)] disabled:opacity-50"
                        >
                          {deleting
                            ? <Loader2 size={16} aria-hidden="true" className="animate-spin" />
                            : <Trash2 size={16} aria-hidden="true" />}
                        </button>
                      )}
                    </td>
                  )}
                </tr>
              );
            })}
          </tbody>
        </table>
      </div>
    </div>
  );
}
