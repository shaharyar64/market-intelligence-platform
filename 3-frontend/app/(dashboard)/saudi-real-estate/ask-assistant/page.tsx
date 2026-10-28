"use client";

import { useEffect, useMemo, useRef, useState } from "react";
import DashboardTopbar from "@/components/layout/DashboardTopbar";
import StructuredResponse from "@/components/askAssistant/StructuredResponse";
import {
  ArrowUp,
  BarChart2,
  FileText,
  ImageIcon,
  Lightbulb,
  Target,
  TrendingUp,
} from "lucide-react";

// TODO: point at a dedicated saudi-real-estate chat backend once one exists.
// The proxy below currently forwards to the same stopgap host real-estate uses.
const CHAT_API_URL = "/api/saudi-real-estate/chat";
const API_BASE = "http://localhost:5003";

type ChatMessage = {
  role: "user" | "bot";
  text: string;
  image?: string | null;
  pdfPath?: string | null;
};

const SECTION_META: Record<
  string,
  { label: string; accent: string; Icon: React.ElementType }
> = {
  A: { label: "Summary", accent: "#6366f1", Icon: Lightbulb },
  B: { label: "Insights", accent: "#0ea5e9", Icon: BarChart2 },
  C: { label: "Drivers & Notes", accent: "#f59e0b", Icon: TrendingUp },
  D: { label: "Recommendation", accent: "#10b981", Icon: Target },
};

const SUGGESTIONS = [
  { text: "Summarize BrandIQ performance", icon: "📊" },
  { text: "Compare developers by ratings and review sentiment", icon: "⭐" },
  { text: "Which review topics need attention?", icon: "💬" },
  { text: "Explain AI score gaps across developers", icon: "🧠" },
];

function parseSections(text: string) {
  const regex = /Section\s+([A-Z]):\s*/gi;
  const matches = [...text.matchAll(regex)];
  if (!matches.length) return null;

  return matches.map((match, index) => ({
    key: match[1].toUpperCase(),
    content: text
      .slice(
        (match.index ?? 0) + match[0].length,
        matches[index + 1]?.index ?? text.length
      )
      .trim(),
  }));
}

function RenderContent({ content }: { content: string }) {
  return <StructuredResponse text={content} />;
}

function pickString(...values: unknown[]) {
  for (const value of values) {
    if (typeof value === "string" && value.trim()) return value.trim();
  }

  return null;
}

function parseJsonString(value: string) {
  const trimmed = value.trim();
  if (!trimmed.startsWith("{") && !trimmed.startsWith("[")) return null;

  try {
    return JSON.parse(trimmed) as unknown;
  } catch {
    return null;
  }
}

function findStringValue(
  payload: unknown,
  keys: string[],
  seen = new WeakSet<object>()
): string | null {
  if (typeof payload === "string") {
    const parsed = parseJsonString(payload);
    return parsed ? findStringValue(parsed, keys, seen) : null;
  }

  if (!payload || typeof payload !== "object") return null;
  if (seen.has(payload)) return null;
  seen.add(payload);

  const record = payload as Record<string, unknown>;
  const direct = pickString(...keys.map((key) => record[key]));
  if (direct) return direct;

  for (const value of Object.values(record)) {
    const nested = findStringValue(value, keys, seen);
    if (nested) return nested;
  }

  return null;
}

function getImageSrc(image: string) {
  if (image.startsWith("http") || image.startsWith("data:")) return image;
  return `data:image/png;base64,${image}`;
}

function getApiAssetUrl(pathOrUrl: string) {
  if (/^https?:\/\/(127\.0\.0\.1|localhost)(:\d+)?\//i.test(pathOrUrl)) {
    const url = new URL(pathOrUrl);
    return `${API_BASE}${url.pathname}${url.search}${url.hash}`;
  }

  if (pathOrUrl.startsWith("http")) return pathOrUrl;
  return `${API_BASE}${pathOrUrl.startsWith("/") ? "" : "/"}${pathOrUrl}`;
}

function dataUrlToBlobUrl(dataUrl: string) {
  const match = dataUrl.match(/^data:([^;,]+)?(;base64)?,([\s\S]*)$/);
  if (!match) return null;

  const mime = match[1] || "image/png";
  const isBase64 = !!match[2];
  let raw = "";

  try {
    raw = isBase64 ? atob(match[3]) : decodeURIComponent(match[3]);
  } catch {
    return null;
  }

  const bytes = new Uint8Array(raw.length);
  for (let i = 0; i < raw.length; i += 1) {
    bytes[i] = raw.charCodeAt(i);
  }

  return URL.createObjectURL(new Blob([bytes], { type: mime }));
}

function ChartImage({ image }: { image: string }) {
  const [failedSrc, setFailedSrc] = useState<string | null>(null);

  const src = useMemo(() => {
    const imageSrc = getImageSrc(image);
    return imageSrc.startsWith("data:")
      ? dataUrlToBlobUrl(imageSrc) || imageSrc
      : imageSrc;
  }, [image]);

  useEffect(
    () => () => {
      if (src.startsWith("blob:")) URL.revokeObjectURL(src);
    },
    [src]
  );

  if (failedSrc === src) {
    return (
      <div
        style={{
          border: "1px dashed var(--card-bd)",
          borderRadius: 12,
          padding: 14,
          color: "var(--muted-tx)",
          fontSize: 13,
        }}
      >
        Chart image was returned by the API but could not be rendered in the
        browser. Use Download Chart to open it.
      </div>
    );
  }

  return (
    // eslint-disable-next-line @next/next/no-img-element
    <img
      src={src}
      alt="Chart"
      style={{
        display: "block",
        width: "100%",
        height: "auto",
        borderRadius: 12,
        border: "1px solid var(--card-bd)",
        background: "#fff",
      }}
      onError={(event) => {
        setFailedSrc((event.target as HTMLImageElement).src);
      }}
    />
  );
}

function downloadImage(base64: string, filename = "chart.png") {
  const link = document.createElement("a");
  link.href = getImageSrc(base64);
  link.download = filename;
  link.click();
}

function downloadPdf(pdfPath: string, filename = "report.pdf") {
  const link = document.createElement("a");
  link.href = getApiAssetUrl(pdfPath);
  link.download = filename;
  link.target = "_blank";
  link.click();
}

function BotMessage({
  text,
  image,
  pdfPath,
}: {
  text: string;
  image?: string | null;
  pdfPath?: string | null;
}) {
  const sections = parseSections(text);
  const hasImage = !!image;
  const hasPdf = !!pdfPath;

  return (
    <div className="flex items-start gap-3">
      <div className="mt-0.5 flex h-8 w-8 shrink-0 items-center justify-center rounded-xl bg-gradient-to-br from-indigo-500 to-blue-600 shadow-md">
        {/* eslint-disable-next-line @next/next/no-img-element */}
        <img src="/x.svg" alt="AI" className="h-4 w-4" />
      </div>

      <div
        style={{
          background: "var(--card-bg)",
          border: "1px solid var(--card-bd)",
          backdropFilter: "var(--blur)",
          WebkitBackdropFilter: "var(--blur)",
          boxShadow: "var(--card-shadow)",
        }}
        className="max-w-2xl flex-1 rounded-b-2xl rounded-tr-2xl rounded-tl-sm p-5"
      >
        {sections && sections.length > 0 ? (
          <div className="space-y-4">
            {sections.map((section, index) => {
              const meta = SECTION_META[section.key] ?? {
                label: `Section ${section.key}`,
                accent: "#6b7280",
                Icon: Lightbulb,
              };
              const isSkipped = ["no chart", "not applicable", "n/a"].some(
                (value) => section.content.toLowerCase().includes(value)
              );
              if (isSkipped) return null;
              const { Icon } = meta;

              return (
                <div key={section.key}>
                  {index > 0 && (
                    <hr
                      style={{
                        border: "none",
                        borderTop: "1px solid var(--card-bd)",
                        margin: "16px 0",
                      }}
                    />
                  )}

                  <div className="mb-3 flex items-center gap-2">
                    <div
                      className="flex h-6 w-6 items-center justify-center rounded-md"
                      style={{ background: `${meta.accent}22` }}
                    >
                      <Icon size={12} style={{ color: meta.accent }} />
                    </div>
                    <span
                      style={{
                        color: meta.accent,
                        fontSize: 11,
                        fontWeight: 700,
                        letterSpacing: "0.07em",
                        textTransform: "uppercase",
                      }}
                    >
                      {meta.label}
                    </span>
                  </div>

                  {section.key === "D" ? (
                    <div
                      style={{
                        borderLeft: `3px solid ${meta.accent}`,
                        background: `${meta.accent}0d`,
                        borderRadius: "0 8px 8px 0",
                        padding: "10px 14px",
                      }}
                    >
                      <RenderContent content={section.content} />
                    </div>
                  ) : (
                    <RenderContent content={section.content} />
                  )}
                </div>
              );
            })}
          </div>
        ) : (
          <RenderContent content={text} />
        )}

        {hasImage && (
          <div className="mt-4">
            <hr
              style={{
                border: "none",
                borderTop: "1px solid var(--card-bd)",
                marginBottom: 16,
              }}
            />
            <ChartImage image={image} />
          </div>
        )}

        {(hasImage || hasPdf) && (
          <div className="mt-4 flex flex-wrap gap-2">
            {hasImage && (
              <button
                onClick={() => downloadImage(image)}
                className="flex items-center gap-1.5 rounded-lg px-3 py-1.5 text-xs font-semibold transition-all hover:opacity-80"
                style={{
                  background: "#6366f122",
                  color: "#6366f1",
                  border: "1px solid #6366f144",
                }}
              >
                <ImageIcon size={13} />
                Download Chart
              </button>
            )}
            {hasPdf && (
              <button
                onClick={() => downloadPdf(pdfPath)}
                className="flex items-center gap-1.5 rounded-lg px-3 py-1.5 text-xs font-semibold transition-all hover:opacity-80"
                style={{
                  background: "#10b98122",
                  color: "#10b981",
                  border: "1px solid #10b98144",
                }}
              >
                <FileText size={13} />
                Download PDF
              </button>
            )}
          </div>
        )}
      </div>
    </div>
  );
}

function TypingDots() {
  return (
    <div className="flex items-start gap-3">
      <div className="flex h-8 w-8 shrink-0 items-center justify-center rounded-xl bg-gradient-to-br from-indigo-500 to-blue-600 shadow-md">
        {/* eslint-disable-next-line @next/next/no-img-element */}
        <img src="/x.svg" alt="AI" className="h-4 w-4" />
      </div>
      <div
        style={{
          background: "var(--card-bg)",
          border: "1px solid var(--card-bd)",
          backdropFilter: "var(--blur)",
        }}
        className="flex items-center gap-1.5 rounded-b-2xl rounded-tr-2xl rounded-tl-sm px-5 py-4"
      >
        {[0, 1, 2].map((index) => (
          <span
            key={index}
            style={{
              width: 7,
              height: 7,
              borderRadius: "50%",
              background: "var(--muted-tx)",
              display: "inline-block",
              animation: `chatBounce 1.2s ease-in-out ${index * 0.2}s infinite`,
            }}
          />
        ))}
      </div>
    </div>
  );
}

function InputBar({
  value,
  onChange,
  onSend,
  disabled,
}: {
  value: string;
  onChange: (value: string) => void;
  onSend: () => void;
  disabled: boolean;
}) {
  const ref = useRef<HTMLTextAreaElement>(null);

  const handleKey = (event: React.KeyboardEvent) => {
    if (event.key === "Enter" && !event.shiftKey) {
      event.preventDefault();
      onSend();
    }
  };

  useEffect(() => {
    if (ref.current) {
      ref.current.style.height = "auto";
      ref.current.style.height = `${Math.min(ref.current.scrollHeight, 120)}px`;
    }
  }, [value]);

  return (
    <div className="px-6 pb-6 pt-3">
      <div
        className="composer mx-auto flex max-w-3xl items-end gap-3 rounded-2xl px-4 py-3"
        style={{
          background: "var(--card-bg)",
          border: "1px solid var(--card-bd)",
          backdropFilter: "var(--blur)",
          WebkitBackdropFilter: "var(--blur)",
          boxShadow: "0 8px 32px rgba(99,102,241,0.12)",
        }}
      >
        <textarea
          ref={ref}
          rows={1}
          value={value}
          onChange={(event) => onChange(event.target.value)}
          onKeyDown={handleKey}
          placeholder="Ask about AI scores, reviews, sentiment, ratings, or brand health..."
          style={{ color: "var(--title-tx)" }}
          className="max-h-[120px] flex-1 resize-none bg-transparent text-sm leading-relaxed outline-none placeholder:text-[var(--muted-tx)]"
        />
        <button
          type="button"
          onClick={onSend}
          disabled={disabled || !value.trim()}
          aria-label="Send message"
          className="flex h-9 w-9 shrink-0 items-center justify-center rounded-xl bg-gradient-to-br from-indigo-500 to-blue-600 text-white shadow-lg transition-all hover:scale-105 hover:shadow-indigo-300/40 disabled:opacity-40 disabled:hover:scale-100"
        >
          <ArrowUp size={16} />
        </button>
      </div>
      <p
        style={{ color: "var(--muted-tx)" }}
        className="mt-2 text-center text-xs opacity-60"
      >
        Press Enter to send, Shift+Enter for new line
      </p>
    </div>
  );
}

export default function DigitalBrandHealthAskAssistantPage() {
  const [input, setInput] = useState("");
  const [chat, setChat] = useState<ChatMessage[]>([]);
  const [loading, setLoading] = useState(false);
  const [started, setStarted] = useState(false);
  const bottomRef = useRef<HTMLDivElement>(null);

  useEffect(() => {
    bottomRef.current?.scrollIntoView({ behavior: "smooth" });
  }, [chat, loading]);

  const sendMessage = async () => {
    const message = input.trim();
    if (!message) return;

    setStarted(true);
    setChat((previous) => [...previous, { role: "user", text: message }]);
    setInput("");
    setLoading(true);

    try {
      const response = await fetch(CHAT_API_URL, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ data: "overall", message }),
      });
      if (!response.ok) {
        throw new Error(`Chat request failed with status ${response.status}`);
      }
      const result = await response.json();
      const responseText =
        findStringValue(result, ["message", "answer", "response", "output"]) ||
        "No response";
      const responseImage = findStringValue(result, [
        "image",
        "chart",
        "chart_image",
        "image_base64",
        "base64_image",
      ]);
      const responsePdfPath = findStringValue(result, ["pdf_path", "pdfPath"]);

      setChat((previous) => [
        ...previous,
        {
          role: "bot",
          text: responseText,
          image: responseImage,
          pdfPath: responsePdfPath,
        },
      ]);
    } catch {
      setChat((previous) => [
        ...previous,
        {
          role: "bot",
          text: "Couldn't reach the server. Please try again.",
        },
      ]);
    } finally {
      setLoading(false);
    }
  };

  return (
    <div className="flex h-screen w-full flex-col" style={{ background: "transparent" }}>
      <style>{`
        @keyframes chatBounce {
          0%, 80%, 100% { transform: translateY(0); opacity: 0.4; }
          40% { transform: translateY(-6px); opacity: 1; }
        }
      `}</style>

      <DashboardTopbar title="BrandIQ" />

      {!started ? (
        <div className="flex flex-1 flex-col overflow-hidden">
          <div className="flex flex-1 flex-col items-center justify-center px-8 pb-6">
            <div className="relative mb-6">
              <div
                className="absolute inset-0 scale-150 rounded-full opacity-20 blur-3xl"
                style={{ background: "var(--card-bd)" }}
              />
              <div
                className="relative flex h-20 w-20 items-center justify-center rounded-3xl"
                style={{
                  background: "var(--card-bg)",
                  border: "1px solid var(--card-bd)",
                  backdropFilter: "var(--blur)",
                  WebkitBackdropFilter: "var(--blur)",
                  boxShadow: "0 8px 32px rgba(0,0,0,0.1)",
                }}
              >
                {/* eslint-disable-next-line @next/next/no-img-element */}
                <img src="/x.svg" alt="Analytics Platform" className="h-12 w-12" />
              </div>
            </div>

            <h1
              style={{ color: "var(--title-tx)" }}
              className="mb-2 text-center text-4xl font-bold tracking-tight"
            >
              Ask{" "}
              <span className="bg-gradient-to-r from-indigo-500 to-blue-500 bg-clip-text text-transparent">
                Analytics Platform
              </span>
            </h1>
            <p
              style={{ color: "var(--muted-tx)" }}
              className="mb-10 max-w-sm text-center text-base"
            >
              AI-powered insights for digital brand health, reviews, sentiment,
              AI score, and competitive visibility.
            </p>

            <div className="grid w-full max-w-2xl grid-cols-1 gap-3 sm:grid-cols-2">
              {SUGGESTIONS.map((suggestion, index) => (
                <button
                  key={index}
                  onClick={() => setInput(suggestion.text)}
                  style={{
                    background: "var(--card-bg)",
                    border: "1px solid var(--card-bd)",
                    backdropFilter: "var(--blur)",
                    WebkitBackdropFilter: "var(--blur)",
                    color: "var(--body-tx)",
                  }}
                  className="flex items-start gap-3 rounded-2xl px-4 py-3.5 text-left text-sm transition-all hover:-translate-y-0.5 hover:border-indigo-400 hover:shadow-md"
                >
                  <span className="mt-0.5 shrink-0 text-lg leading-none">
                    {suggestion.icon}
                  </span>
                  <span className="leading-snug">{suggestion.text}</span>
                </button>
              ))}
            </div>
          </div>

          <InputBar
            value={input}
            onChange={setInput}
            onSend={sendMessage}
            disabled={loading}
          />
        </div>
      ) : (
        <div className="flex flex-1 flex-col overflow-hidden">
          <div className="flex-1 space-y-6 overflow-y-auto px-6 py-6">
            <div className="mx-auto max-w-3xl space-y-6">
              {chat.map((message, index) => (
                <div key={index}>
                  {message.role === "user" ? (
                    <div className="flex justify-end">
                      <div
                        className="max-w-lg rounded-2xl rounded-br-sm px-5 py-3.5 text-sm text-white shadow-lg"
                        style={{
                          background: "linear-gradient(135deg, #6366f1, #3b82f6)",
                        }}
                      >
                        {message.text}
                      </div>
                    </div>
                  ) : (
                    <BotMessage
                      text={message.text}
                      image={message.image}
                      pdfPath={message.pdfPath}
                    />
                  )}
                </div>
              ))}

              {loading && <TypingDots />}
              <div ref={bottomRef} />
            </div>
          </div>

          <InputBar
            value={input}
            onChange={setInput}
            onSend={sendMessage}
            disabled={loading}
          />
        </div>
      )}
    </div>
  );
}
