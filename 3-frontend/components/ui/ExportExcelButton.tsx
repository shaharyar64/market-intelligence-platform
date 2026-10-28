"use client";

import * as XLSX from "xlsx";
import { FileSpreadsheet } from "lucide-react";

type ExportRow = Record<string, unknown>;

type Props = {
  rows: ExportRow[];
  filename: string;
  sheetName?: string;
  disabled?: boolean;
};

function safeFileName(value: string) {
  return value
    .trim()
    .toLowerCase()
    .replace(/[^a-z0-9]+/g, "_")
    .replace(/^_+|_+$/g, "");
}

function flattenValue(value: unknown): string | number | boolean | null {
  if (value === null || value === undefined) return null;
  if (typeof value === "string" || typeof value === "number" || typeof value === "boolean") {
    return value;
  }
  return JSON.stringify(value);
}

function normalizeRows(rows: ExportRow[]) {
  return rows.map((row) =>
    Object.fromEntries(
      Object.entries(row).map(([key, value]) => [key, flattenValue(value)])
    )
  );
}

export default function ExportExcelButton({
  rows,
  filename,
  sheetName = "Data",
  disabled = false,
}: Props) {
  const handleExport = () => {
    if (!rows.length) return;

    const worksheet = XLSX.utils.json_to_sheet(normalizeRows(rows));
    const workbook = XLSX.utils.book_new();
    XLSX.utils.book_append_sheet(workbook, worksheet, sheetName.slice(0, 31));
    XLSX.writeFile(workbook, `${safeFileName(filename) || "export"}.xlsx`);
  };

  return (
    <button
      type="button"
      onClick={handleExport}
      disabled={disabled || rows.length === 0}
      aria-label="Export Excel"
      className="inline-flex h-9 w-9 items-center justify-center rounded-full border border-emerald-500/30 bg-emerald-500 text-white shadow-sm shadow-emerald-500/20 transition hover:border-emerald-600 hover:bg-emerald-600 disabled:cursor-not-allowed disabled:border-emerald-500/20 disabled:bg-emerald-500/45 disabled:opacity-60"
      style={{ color: "#ffffff" }}
      title="Export Excel"
    >
      <FileSpreadsheet className="h-4 w-4" />
    </button>
  );
}
