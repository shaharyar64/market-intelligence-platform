"use client";

import DashboardTopbar from "@/components/layout/DashboardTopbar";
import { AlertCircle } from "lucide-react";

export default function PackFormatPage() {
  return (
    <div className="min-h-screen bg-transparent">
      <DashboardTopbar title="Pack Format Analysis" />
      <div className="p-8 flex items-center justify-center min-h-[calc(100vh-80px)]">
        <div className="rounded-2xl bg-[var(--card-bg-2)] border border-[var(--card-bd)] p-12 shadow-lg max-w-md text-center">
          <AlertCircle size={48} className="mx-auto mb-4" style={{ color: "var(--muted-tx)" }} />
          <h2 className="text-xl font-semibold mb-2" style={{ color: "var(--title-tx)" }}>
            Page Disabled
          </h2>
          <p style={{ color: "var(--body-tx)" }}>
            The Pack & Format analysis page is currently disabled.
          </p>
        </div>
      </div>
    </div>
  );
}
