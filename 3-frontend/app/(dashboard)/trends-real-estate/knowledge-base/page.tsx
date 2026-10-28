"use client";

import { useEffect, useState } from "react";
import Link from "next/link";
import { ArrowLeft } from "lucide-react";

import DocumentList from "@/components/knowledgeBase/DocumentList";
import UploadDocumentForm, { type UploadedDocument } from "@/components/knowledgeBase/UploadDocumentForm";
import DashboardTopbar from "@/components/layout/DashboardTopbar";
import { Skel } from "@/components/ui/RealEstateTrendsPanels";
import { listDocuments, type KnowledgeDocument } from "@/lib/knowledgeBase";
import { friendlyError } from "@/lib/foodIntelligence";
import { getMe } from "@/lib/user";

const POLL_INTERVAL_MS = 4000;

export default function KnowledgeBasePage() {
  const [documents, setDocuments] = useState<KnowledgeDocument[] | null>(null);
  const [listError, setListError] = useState<string | null>(null);
  const [isAdmin, setIsAdmin] = useState(false);
  const [email, setEmail] = useState("");

  function refresh() {
    listDocuments()
      .then((r) => {
        setDocuments(r.documents);
        setListError(null);
      })
      .catch((e) => setListError(friendlyError(e)));
  }

  // The upload response already carries the new document, so show it straight away
  // instead of making the uploader wait on a second round trip to see their own file.
  function handleUploaded(created: UploadedDocument) {
    setDocuments((prev) => [
      {
        document_id: created.document_id,
        title: created.title,
        status: created.status,
        chunk_count: null,
        uploaded_by: email,
        created_at: new Date().toISOString(),
        error_message: null,
      },
      ...(prev ?? []),
    ]);
    refresh();
  }

  useEffect(() => {
    refresh();
    getMe()
      .then((u) => { setIsAdmin(u.role?.toUpperCase() === "ADMIN"); setEmail(u.email); })
      .catch(() => setIsAdmin(false));
  }, []);

  useEffect(() => {
    if (!documents || !documents.some((d) => d.status === "processing")) return;
    const timer = setTimeout(refresh, POLL_INTERVAL_MS);
    return () => clearTimeout(timer);
  }, [documents]);

  const readyCount = documents?.filter((d) => d.status === "ready").length ?? 0;

  return (
    <div className="w-full">
      <DashboardTopbar title="Knowledge Base" accessory={null} />

      <div className="mx-auto w-full max-w-[1500px] p-6 sm:p-8">
        <header className="mb-8">
          <Link
            href="/trends-real-estate/idea-testing"
            style={{ color: "var(--muted-tx)" }}
            className="inline-flex items-center gap-1.5 rounded-full py-1 pr-2 text-sm font-medium transition-colors hover:text-[var(--title-tx)]"
          >
            <ArrowLeft size={14} aria-hidden="true" />
            Idea Testing
          </Link>
          <h2 style={{ color: "var(--title-tx)" }}
            className="mt-4 text-2xl font-bold tracking-tight text-balance sm:text-3xl">
            Proprietary research library
          </h2>
          <p style={{ color: "var(--muted-tx)" }} className="mt-2 max-w-2xl text-sm sm:text-base">
            Documents uploaded here are cited by Idea Testing alongside the real posts and trends
            already collected for this market.
            {readyCount > 0 && ` ${readyCount} document${readyCount === 1 ? "" : "s"} currently in use.`}
          </p>
        </header>

        {/* The list column stretches to the row height so it stays level with the upload
            panel whether the library is empty or full, and the panel keeps its own height
            so it can stick while a long list scrolls past. */}
        <div className={isAdmin ? "grid gap-6 xl:grid-cols-[minmax(0,1fr)_22rem]" : ""}>
          <div className="flex min-w-0 flex-col gap-3">
            {listError && (
              <p role="alert" style={{ color: "var(--fi-danger-tx)" }} className="text-sm">
                {listError}
              </p>
            )}
            {documents === null
              ? !listError && <Skel className="min-h-64 flex-1 rounded-2xl" />
              : <DocumentList documents={documents} canManage={isAdmin} onDeleted={refresh} />}
          </div>

          {isAdmin && (
            <aside className="self-start xl:sticky xl:top-24">
              <UploadDocumentForm onUploaded={handleUploaded} />
            </aside>
          )}
        </div>
      </div>
    </div>
  );
}
