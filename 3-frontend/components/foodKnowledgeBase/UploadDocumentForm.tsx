"use client";

import { useRef, useState } from "react";
import { UploadCloud, X } from "lucide-react";

import { uploadDocument, type DocumentStatus } from "@/lib/foodKnowledgeBase";
import { friendlyError } from "@/lib/foodIntelligence";

const MAX_FILE_BYTES = 15 * 1024 * 1024;

export type UploadedDocument = {
  document_id: string;
  status: DocumentStatus;
  title: string;
};

function formatSize(bytes: number): string {
  const mb = bytes / (1024 * 1024);
  return mb >= 1 ? `${mb.toFixed(1)} MB` : `${Math.round(bytes / 1024)} KB`;
}

export default function UploadDocumentForm(
  { onUploaded }: { onUploaded: (created: UploadedDocument) => void },
) {
  const [title, setTitle] = useState("");
  const [file, setFile] = useState<File | null>(null);
  const [dragging, setDragging] = useState(false);
  const [submitting, setSubmitting] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const inputRef = useRef<HTMLInputElement>(null);

  function clearFile() {
    setFile(null);
    if (inputRef.current) inputRef.current.value = "";
  }

  function acceptFile(candidate: File) {
    // Some drag sources hand over an empty MIME type, so fall back to the extension
    // rather than rejecting a real PDF the browser simply failed to label.
    const isPdf = candidate.type === "application/pdf"
      || (candidate.type === "" && candidate.name.toLowerCase().endsWith(".pdf"));
    if (!isPdf) {
      setError("That file is not a PDF. Only PDF documents can be added to the library.");
      return;
    }
    if (candidate.size > MAX_FILE_BYTES) {
      setError(`That PDF is ${formatSize(candidate.size)}. The limit is 15 MB.`);
      return;
    }
    setError(null);
    setFile(candidate);
  }

  async function handleSubmit(event: React.FormEvent) {
    event.preventDefault();
    if (!title.trim()) { setError("Give the document a title."); return; }
    if (!file) { setError("Attach a PDF."); return; }
    setSubmitting(true);
    setError(null);
    const submittedTitle = title.trim();
    try {
      const created = await uploadDocument(submittedTitle, file);
      setTitle("");
      clearFile();
      onUploaded({ ...created, title: submittedTitle });
    } catch (e) {
      setError(friendlyError(e));
    } finally {
      setSubmitting(false);
    }
  }

  return (
    <form onSubmit={handleSubmit} className="chart-card space-y-5 rounded-2xl p-5">
      <div>
        <h3 style={{ color: "var(--title-tx)" }} className="text-sm font-semibold">Add a document</h3>
        <p style={{ color: "var(--muted-tx)" }} className="mt-1 text-xs">
          Text-based PDFs only. Scanned pages cannot be read yet.
        </p>
      </div>

      <div className="space-y-1.5">
        <label htmlFor="kb-title" style={{ color: "var(--body-tx)" }}
          className="block text-xs font-medium">Title</label>
        <input
          id="kb-title"
          value={title}
          onChange={(e) => setTitle(e.target.value)}
          placeholder="Q3 2026 Market Outlook"
          style={{ background: "var(--card-bg)", border: "1px solid var(--card-bd)", color: "var(--title-tx)" }}
          className="w-full rounded-xl px-4 py-2.5 text-sm"
        />
      </div>

      <div className="space-y-1.5">
        <span style={{ color: "var(--body-tx)" }} className="block text-xs font-medium">File</span>
        {file ? (
          <div className="flex items-center justify-between gap-3 rounded-xl px-4 py-3"
            style={{ background: "var(--card-bg)", border: "1px solid var(--card-bd)" }}>
            <span className="min-w-0">
              <span style={{ color: "var(--title-tx)" }}
                className="block truncate text-sm font-medium">{file.name}</span>
              <span style={{ color: "var(--muted-tx)" }} className="text-xs">{formatSize(file.size)}</span>
            </span>
            <button type="button" onClick={clearFile} aria-label={`Remove ${file.name}`}
              style={{ color: "var(--muted-tx)" }}
              className="inline-flex size-11 shrink-0 items-center justify-center rounded-lg transition-colors hover:text-[var(--title-tx)]">
              <X size={16} aria-hidden="true" />
            </button>
          </div>
        ) : (
          <label
            htmlFor="kb-file"
            onDragOver={(e) => { e.preventDefault(); setDragging(true); }}
            onDragLeave={() => setDragging(false)}
            onDrop={(e) => {
              e.preventDefault(); setDragging(false);
              const f = e.dataTransfer.files?.[0]; if (f) acceptFile(f);
            }}
            className="flex min-h-32 cursor-pointer flex-col items-center justify-center gap-2 rounded-xl px-6 py-8 text-center transition-colors focus-within:ring-2 focus-within:ring-[var(--fi-solid)] focus-within:ring-offset-0"
            style={{
              background: dragging ? "var(--card-bg-2)" : "var(--card-bg)",
              border: `1.5px dashed ${dragging ? "var(--fi-solid)" : "var(--card-bd)"}`,
            }}
          >
            <UploadCloud size={22} aria-hidden="true"
              style={{ color: dragging ? "var(--fi-solid)" : "var(--muted-tx)" }} />
            <span style={{ color: "var(--title-tx)" }} className="text-sm font-medium">
              Drop a PDF here, or{" "}
              <span style={{ color: "var(--fi-solid)" }} className="underline underline-offset-2">browse</span>
            </span>
            <span style={{ color: "var(--muted-tx)" }} className="text-xs">PDF, up to 15 MB</span>
            <input ref={inputRef} id="kb-file" type="file" accept="application/pdf,.pdf"
              onChange={(e) => { const f = e.target.files?.[0]; if (f) acceptFile(f); }}
              className="sr-only" />
          </label>
        )}
      </div>

      {error && (
        <p role="alert" style={{ color: "var(--fi-danger-tx)" }} className="text-sm">{error}</p>
      )}

      <button
        type="submit"
        disabled={submitting}
        style={{ background: "var(--fi-solid)", color: "var(--fi-solid-tx)" }}
        className="inline-flex min-h-11 w-full items-center justify-center rounded-full px-5 text-sm font-semibold transition-opacity disabled:opacity-60"
      >
        {submitting ? "Uploading…" : "Upload document"}
      </button>
    </form>
  );
}
