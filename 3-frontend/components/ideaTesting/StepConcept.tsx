"use client";

import { useEffect, useRef, useState, type KeyboardEvent } from "react";
import { FileText, ImageIcon, Type, UploadCloud, X } from "lucide-react";
import type { LucideIcon } from "lucide-react";

import { createConceptFromFile, createConceptFromText } from "@/lib/ideaTesting";
import type { ConceptMode, TestType } from "@/lib/ideaTesting";
import { friendlyError } from "@/lib/foodIntelligence";

const MAX_CONCEPTS = 3;
const MAX_FILE_BYTES = 15 * 1024 * 1024;

type InputType = "text" | "image" | "pdf";

const INPUT_TYPES: { id: InputType; label: string; Icon: LucideIcon }[] = [
  { id: "text", label: "Text", Icon: Type },
  { id: "image", label: "Image card", Icon: ImageIcon },
  { id: "pdf", label: "PDF card", Icon: FileText },
];

const FILE_RULES: Record<"image" | "pdf", { accept: string; types: string[]; hint: string; noun: string }> = {
  image: {
    accept: "image/png,image/jpeg,image/webp",
    types: ["image/png", "image/jpeg", "image/webp"],
    hint: "PNG, JPG or WebP, up to 15 MB",
    noun: "an image",
  },
  pdf: { accept: "application/pdf", types: ["application/pdf"], hint: "PDF, up to 15 MB", noun: "a PDF" },
};

type FileKind = Exclude<InputType, "text">;

type PendingConcept = {
  id: string;
  title: string;
  inputType: InputType;
  text: string;
  image: File | null;
  pdf: File | null;
  notes: Record<FileKind, string>;
  fileError: string | null;
};

class ValidationError extends Error {}

function makeId(): string {
  return crypto.randomUUID?.() ?? `${Date.now()}-${Math.random().toString(36).slice(2)}`;
}

function newConcept(): PendingConcept {
  return {
    id: makeId(), title: "", inputType: "text", text: "", image: null, pdf: null,
    notes: { image: "", pdf: "" }, fileError: null,
  };
}

function formatBytes(bytes: number): string {
  if (bytes < 1024 * 1024) return `${Math.max(1, Math.round(bytes / 1024))} KB`;
  return `${(bytes / (1024 * 1024)).toFixed(1)} MB`;
}

function fileKind(file: File): FileKind | null {
  if (FILE_RULES.image.types.includes(file.type)) return "image";
  if (FILE_RULES.pdf.types.includes(file.type)) return "pdf";
  return null;
}

const fieldStyle = { background: "var(--card-bg)", border: "1px solid var(--card-bd)", color: "var(--title-tx)" };

function InputTypeTabs({
  conceptId, value, onChange,
}: {
  conceptId: string;
  value: InputType;
  onChange: (next: InputType) => void;
}) {
  const refs = useRef<Record<InputType, HTMLButtonElement | null>>({ text: null, image: null, pdf: null });

  function onKeyDown(e: KeyboardEvent<HTMLDivElement>) {
    const index = INPUT_TYPES.findIndex((t) => t.id === value);
    let next = index;
    if (e.key === "ArrowRight") next = (index + 1) % INPUT_TYPES.length;
    else if (e.key === "ArrowLeft") next = (index - 1 + INPUT_TYPES.length) % INPUT_TYPES.length;
    else if (e.key === "Home") next = 0;
    else if (e.key === "End") next = INPUT_TYPES.length - 1;
    else return;
    e.preventDefault();
    const id = INPUT_TYPES[next].id;
    onChange(id);
    refs.current[id]?.focus();
  }

  return (
    <div
      role="tablist"
      aria-label="Concept input type"
      onKeyDown={onKeyDown}
      className="grid w-full grid-cols-3 gap-1 rounded-xl p-1 sm:inline-flex sm:w-auto"
      style={{ background: "var(--card-bg-2)", border: "1px solid var(--card-bd)" }}
    >
      {INPUT_TYPES.map(({ id, label, Icon }) => {
        const selected = id === value;
        return (
          <button
            key={id}
            ref={(el) => { refs.current[id] = el; }}
            type="button"
            role="tab"
            id={`${conceptId}-tab-${id}`}
            aria-selected={selected}
            aria-controls={`${conceptId}-panel`}
            tabIndex={selected ? 0 : -1}
            onClick={() => onChange(id)}
            style={
              selected
                ? {
                  background: "var(--dropdown-bg)",
                  color: "var(--title-tx)",
                  boxShadow: "0 1px 3px rgba(0,0,0,0.18), inset 0 0 0 1px var(--card-bd)",
                }
                : { color: "var(--muted-tx)" }
            }
            className="inline-flex items-center justify-center gap-2 whitespace-nowrap rounded-lg px-2 py-1.5 text-sm font-medium transition-colors hover:text-[var(--title-tx)] sm:px-3"
          >
            <Icon size={15} aria-hidden="true" className="hidden shrink-0 sm:block" />
            {label}
          </button>
        );
      })}
    </div>
  );
}

function ImageThumb({ file }: { file: File }) {
  const [url, setUrl] = useState<string | null>(null);
  useEffect(() => {
    let cancelled = false;
    const reader = new FileReader();
    reader.onload = () => {
      if (!cancelled && typeof reader.result === "string") setUrl(reader.result);
    };
    reader.readAsDataURL(file);
    return () => {
      cancelled = true;
      reader.abort();
    };
  }, [file]);
  if (!url) return null;
  return (
    // eslint-disable-next-line @next/next/no-img-element
    <img src={url} alt="" className="size-12 shrink-0 rounded-lg object-cover" style={{ border: "1px solid var(--card-bd)" }} />
  );
}

function FileDropzone({
  conceptId, kind, file, fileError, onFile, onClear,
}: {
  conceptId: string;
  kind: FileKind;
  file: File | null;
  fileError: string | null;
  onFile: (file: File) => void;
  onClear: () => void;
}) {
  const rules = FILE_RULES[kind];
  const inputRef = useRef<HTMLInputElement>(null);
  const [dragging, setDragging] = useState(false);
  const inputId = `${conceptId}-file-${kind}`;

  function clear() {
    if (inputRef.current) inputRef.current.value = "";
    onClear();
  }

  if (file) {
    return (
      <div className="flex items-center gap-3 rounded-xl px-4 py-3" style={fieldStyle}>
        {kind === "image" ? (
          <ImageThumb file={file} />
        ) : (
          <span
            className="flex size-12 shrink-0 items-center justify-center rounded-lg"
            style={{ background: "var(--card-bg-2)", border: "1px solid var(--card-bd)", color: "var(--muted-tx)" }}
          >
            <FileText size={20} aria-hidden="true" />
          </span>
        )}
        <div className="min-w-0 flex-1">
          <p style={{ color: "var(--title-tx)" }} className="truncate text-sm font-medium">{file.name}</p>
          <p style={{ color: "var(--muted-tx)" }} className="text-xs">{formatBytes(file.size)}</p>
        </div>
        <button
          type="button"
          onClick={clear}
          aria-label={`Remove ${file.name}`}
          className="rounded-lg p-1.5 transition-colors hover:text-[var(--title-tx)]"
          style={{ color: "var(--muted-tx)" }}
        >
          <X size={16} aria-hidden="true" />
        </button>
      </div>
    );
  }

  return (
    <div>
      <label
        htmlFor={inputId}
        onDragOver={(e) => { e.preventDefault(); setDragging(true); }}
        onDragLeave={() => setDragging(false)}
        onDrop={(e) => {
          e.preventDefault();
          setDragging(false);
          const dropped = e.dataTransfer.files?.[0];
          if (dropped) onFile(dropped);
        }}
        className="flex min-h-40 cursor-pointer flex-col items-center justify-center gap-2 rounded-xl px-6 py-8 text-center transition-colors focus-within:outline focus-within:outline-2 focus-within:outline-offset-2 focus-within:outline-[var(--focus-ring)]"
        style={{
          background: dragging ? "var(--card-bg-2)" : "var(--card-bg)",
          border: `1.5px dashed ${dragging ? "var(--fi-solid)" : "var(--card-bd)"}`,
        }}
      >
        <UploadCloud size={22} aria-hidden="true" style={{ color: dragging ? "var(--fi-solid)" : "var(--muted-tx)" }} />
        <span style={{ color: "var(--title-tx)" }} className="text-sm font-medium">
          Drop {rules.noun} here, or <span style={{ color: "var(--fi-solid)" }} className="underline underline-offset-2">browse</span>
        </span>
        <span style={{ color: "var(--muted-tx)" }} className="text-xs">{rules.hint}</span>
        <input
          ref={inputRef}
          id={inputId}
          type="file"
          accept={rules.accept}
          onChange={(e) => {
            const picked = e.target.files?.[0];
            if (picked) onFile(picked);
          }}
          className="sr-only"
        />
      </label>
      {fileError && (
        <p role="alert" style={{ color: "var(--fi-danger-tx)" }} className="mt-2 text-xs">{fileError}</p>
      )}
    </div>
  );
}

export default function StepConcept({
  testType, mode, onSubmit,
}: {
  testType: TestType;
  mode: ConceptMode;
  onSubmit: (conceptIds: string[]) => void;
}) {
  const maxItems = mode === "multiple" ? MAX_CONCEPTS : 1;
  const [items, setItems] = useState<PendingConcept[]>([newConcept()]);
  const [submitting, setSubmitting] = useState(false);
  const [error, setError] = useState<string | null>(null);

  function updateItem(id: string, patch: Partial<PendingConcept>) {
    setItems((prev) => prev.map((it) => (it.id === id ? { ...it, ...patch } : it)));
  }

  function acceptFile(item: PendingConcept, kind: FileKind, file: File) {
    if (fileKind(file) !== kind) {
      updateItem(item.id, { fileError: `That file isn't ${FILE_RULES[kind].noun}. Use ${FILE_RULES[kind].hint}.` });
      return;
    }
    if (file.size > MAX_FILE_BYTES) {
      updateItem(item.id, { fileError: `That file is ${formatBytes(file.size)}. The limit is 15 MB.` });
      return;
    }
    updateItem(item.id, { [kind]: file, fileError: null });
  }

  async function handleSubmit() {
    setSubmitting(true);
    setError(null);
    try {
      const ready = items.map((item, index) => {
        const name = item.title.trim() || `Concept ${index + 1}`;
        if (!item.title.trim()) throw new ValidationError(`${name} needs a title.`);
        if (item.inputType === "text") {
          if (!item.text.trim()) throw new ValidationError(`"${name}" needs concept text.`);
          return { title: item.title, text: item.text, file: null };
        }
        const file = item[item.inputType];
        if (!file) throw new ValidationError(`"${name}" needs ${FILE_RULES[item.inputType].noun} attached.`);
        return { title: item.title, text: item.notes[item.inputType], file };
      });
      const conceptIds: string[] = [];
      for (const concept of ready) {
        const result = concept.file
          ? await createConceptFromFile(concept.title, concept.file, concept.text)
          : await createConceptFromText(concept.title, concept.text);
        conceptIds.push(result.concept_id);
      }
      onSubmit(conceptIds);
    } catch (e) {
      setError(e instanceof ValidationError ? e.message : friendlyError(e));
    } finally {
      setSubmitting(false);
    }
  }

  return (
    <div className="space-y-6">
      {items.map((item, index) => (
        <div key={item.id} className="chart-card space-y-4 rounded-2xl p-5">
          {mode === "multiple" && (
            <div className="flex items-center gap-2">
              <span
                className="flex size-6 items-center justify-center rounded-full text-xs font-semibold tabular-nums"
                style={{ background: "var(--card-bg-2)", color: "var(--title-tx)", border: "1px solid var(--card-bd)" }}
              >
                {index + 1}
              </span>
              <span style={{ color: "var(--title-tx)" }} className="text-sm font-semibold">Concept {index + 1}</span>
              {items.length > 1 && (
                <button
                  type="button"
                  onClick={() => setItems((prev) => prev.filter((it) => it.id !== item.id))}
                  style={{ color: "var(--muted-tx)" }}
                  className="ml-auto text-xs font-medium transition-colors hover:text-[var(--title-tx)]"
                >
                  Remove
                </button>
              )}
            </div>
          )}

          <input
            value={item.title}
            onChange={(e) => updateItem(item.id, { title: e.target.value })}
            placeholder="Concept title"
            aria-label="Concept title"
            style={fieldStyle}
            className="w-full rounded-xl px-4 py-2.5 text-sm"
          />

          <InputTypeTabs
            conceptId={item.id}
            value={item.inputType}
            onChange={(next) => updateItem(item.id, { inputType: next, fileError: null })}
          />

          <div
            role="tabpanel"
            id={`${item.id}-panel`}
            aria-labelledby={`${item.id}-tab-${item.inputType}`}
          >
            {item.inputType === "text" ? (
              <textarea
                value={item.text}
                onChange={(e) => updateItem(item.id, { text: e.target.value })}
                placeholder="Paste or write your concept here. Include the headline, the core benefit and any supporting message."
                aria-label="Concept text"
                rows={6}
                style={fieldStyle}
                className="block w-full resize-y rounded-xl px-4 py-3 text-sm leading-relaxed"
              />
            ) : (
              <div className="space-y-3">
                <FileDropzone
                  key={item.inputType}
                  conceptId={item.id}
                  kind={item.inputType}
                  file={item[item.inputType]}
                  fileError={item.fileError}
                  onFile={(file) => acceptFile(item, item.inputType as FileKind, file)}
                  onClear={() => updateItem(item.id, { [item.inputType]: null, fileError: null })}
                />
                <textarea
                  value={item.notes[item.inputType]}
                  onChange={(e) => updateItem(item.id, {
                    notes: { ...item.notes, [item.inputType]: e.target.value },
                  })}
                  placeholder="Optional: add context the card doesn't show, like pricing, audience or launch details, to sharpen the read."
                  aria-label="Optional notes about the card"
                  maxLength={2000}
                  rows={3}
                  style={fieldStyle}
                  className="block w-full resize-y rounded-xl px-4 py-3 text-sm leading-relaxed"
                />
              </div>
            )}
          </div>
        </div>
      ))}

      {mode === "multiple" && items.length < maxItems && (
        <button
          type="button"
          onClick={() => setItems((prev) => [...prev, newConcept()])}
          style={{ color: "var(--muted-tx)" }}
          className="text-sm font-medium transition-colors hover:text-[var(--title-tx)]"
        >
          + Add another concept ({items.length}/{maxItems})
        </button>
      )}

      {error && <p role="alert" style={{ color: "var(--fi-danger-tx)" }} className="text-sm">{error}</p>}

      <div className="flex justify-end">
        <button
          type="button"
          onClick={handleSubmit}
          disabled={submitting}
          style={{ background: "var(--fi-solid)", color: "var(--fi-solid-tx)" }}
          className="rounded-full px-5 py-2 text-sm font-semibold disabled:opacity-60"
        >
          {submitting ? "Creating concept…" : `Assess ${testType.replace("-", " ")}`}
        </button>
      </div>
    </div>
  );
}
