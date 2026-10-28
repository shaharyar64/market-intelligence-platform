"use client";

import { useState, useEffect, useMemo, useRef } from "react";
import DashboardTopbar from "@/components/layout/DashboardTopbar";
import { BarChart2, TrendingUp, Lightbulb, Target, ArrowUp, ImageIcon, FileText } from "lucide-react";

const API_BASE = process.env.NEXT_PUBLIC_AI_CHAT_API_URL;
console.log("[AskAssistant] API_BASE =", API_BASE);

/* ─── types ─────────────────────────────────────────────────────────── */
type ChatMessage = { role: "user" | "bot"; text: string; image?: string | null; pdfPath?: string | null };

/* ─── section meta ───────────────────────────────────────────────────── */
const SECTION_META: Record<string, { label: string; accent: string; Icon: React.ElementType }> = {
  A: { label: "Summary",          accent: "#6366f1", Icon: Lightbulb  },
  B: { label: "Insights",         accent: "#0ea5e9", Icon: BarChart2  },
  C: { label: "Drivers & Notes",  accent: "#f59e0b", Icon: TrendingUp },
  D: { label: "Recommendation",   accent: "#10b981", Icon: Target     },
};

const SUGGESTIONS = [
  { text: "What are the top performing SKUs this week?",        icon: "📊" },
  { text: "Compare Heineken pricing vs core competition",       icon: "⚖️" },
  { text: "Which markets have the highest promo frequency?",    icon: "📍" },
  { text: "Analyze pack size distribution trends",              icon: "📦" },
];

/* ─── helpers ────────────────────────────────────────────────────────── */
function parseSections(text: string) {
  const regex = /Section\s+([A-Z]):\s*/gi;
  const matches = [...text.matchAll(regex)];
  if (!matches.length) return null;
  return matches.map((m, i) => ({
    key: m[1].toUpperCase(),
    content: text.slice((m.index ?? 0) + m[0].length, matches[i + 1]?.index ?? text.length).trim(),
  }));
}

function RenderContent({ content }: { content: string }) {
  const lines = content.split("\n").map((l) => l.trim()).filter(Boolean);
  const hasBullets = lines.some((l) => l.startsWith("-"));

  if (hasBullets) {
    return (
      <ul style={{ margin: 0, paddingLeft: 18 }} className="space-y-1.5">
        {lines.map((line, i) =>
          line.startsWith("-") ? (
            <li key={i} style={{ color: "var(--body-tx)", fontSize: 13.5, lineHeight: 1.7 }}>
              {line.slice(1).trim()}
            </li>
          ) : (
            <p key={i} style={{ color: "var(--body-tx)", fontSize: 13.5, lineHeight: 1.7, margin: 0 }}>
              {line}
            </p>
          )
        )}
      </ul>
    );
  }
  return <p style={{ color: "var(--body-tx)", fontSize: 13.5, lineHeight: 1.7, margin: 0 }}>{content}</p>;
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

function findStringValue(payload: unknown, keys: string[], seen = new WeakSet<object>()): string | null {
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
    return imageSrc.startsWith("data:") ? dataUrlToBlobUrl(imageSrc) || imageSrc : imageSrc;
  }, [image]);

  useEffect(() => () => {
    if (src.startsWith("blob:")) URL.revokeObjectURL(src);
  }, [src]);

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
        Chart image was returned by the API but could not be rendered in the browser. Use Download Chart to open it.
      </div>
    );
  }

  return (
    // eslint-disable-next-line @next/next/no-img-element
    <img
      src={src}
      alt="Chart"
      style={{ display: "block", width: "100%", height: "auto", borderRadius: 12, border: "1px solid var(--card-bd)", background: "#fff" }}
      onLoad={() => console.log("[Analytics Platform] Image loaded OK")}
      onError={(e) => {
        console.error("[Analytics Platform] Image failed to load", (e.target as HTMLImageElement).src.slice(0, 60));
        setFailedSrc(src);
      }}
    />
  );
}

/* ─── download helpers ───────────────────────────────────────────────── */
function downloadImage(base64: string, filename = "chart.png") {
  const link = document.createElement("a");
  link.href = getImageSrc(base64);
  link.download = filename;
  link.click();
}

function downloadPdf(pdfPath: string, filename = "report.pdf") {
  const url = getApiAssetUrl(pdfPath);
  const link = document.createElement("a");
  link.href = url;
  link.download = filename;
  link.target = "_blank";
  link.click();
}

/* ─── bot message ────────────────────────────────────────────────────── */
function BotMessage({ text, image, pdfPath }: { text: string; image?: string | null; pdfPath?: string | null }) {
  const sections = parseSections(text);
  const hasImage = !!image;
  const hasPdf = !!pdfPath;

  return (
    <div className="flex gap-3 items-start">
      {/* Avatar */}
      <div className="shrink-0 w-8 h-8 rounded-xl bg-gradient-to-br from-indigo-500 to-blue-600 flex items-center justify-center shadow-md mt-0.5">
        <img src="/x.svg" alt="AI" className="w-4 h-4" />
      </div>

      {/* Bubble */}
      <div
        style={{
          background: "var(--card-bg)",
          border: "1px solid var(--card-bd)",
          backdropFilter: "var(--blur)",
          WebkitBackdropFilter: "var(--blur)",
          boxShadow: "var(--card-shadow)",
        }}
        className="flex-1 max-w-2xl rounded-tl-sm rounded-tr-2xl rounded-b-2xl p-5"
      >
        {sections && sections.length > 0 ? (
          <div className="space-y-4">
            {sections.map((sec, i) => {
              const meta = SECTION_META[sec.key] ?? { label: `Section ${sec.key}`, accent: "#6b7280", Icon: Lightbulb };
              const isSkipped = ["no chart", "not applicable", "n/a"].some((x) =>
                sec.content.toLowerCase().includes(x)
              );
              if (isSkipped) return null;
              const { Icon } = meta;

              return (
                <div key={sec.key}>
                  {i > 0 && <hr style={{ border: "none", borderTop: "1px solid var(--card-bd)", margin: "16px 0" }} />}

                  {/* Section header */}
                  <div className="flex items-center gap-2 mb-3">
                    <div className="w-6 h-6 rounded-md flex items-center justify-center" style={{ background: `${meta.accent}22` }}>
                      <Icon size={12} style={{ color: meta.accent }} />
                    </div>
                    <span style={{ color: meta.accent, fontSize: 11, fontWeight: 700, letterSpacing: "0.07em", textTransform: "uppercase" }}>
                      {meta.label}
                    </span>
                  </div>

                  {/* Recommendation callout */}
                  {sec.key === "D" ? (
                    <div style={{ borderLeft: `3px solid ${meta.accent}`, background: `${meta.accent}0d`, borderRadius: "0 8px 8px 0", padding: "10px 14px" }}>
                      <p style={{ color: "var(--body-tx)", fontSize: 13.5, lineHeight: 1.7, margin: 0 }}>{sec.content}</p>
                    </div>
                  ) : (
                    <RenderContent content={sec.content} />
                  )}
                </div>
              );
            })}
          </div>
        ) : (
          <RenderContent content={text} />
        )}

        {/* Chart image */}
        {hasImage && (
          <div className="mt-4" style={{ display: "block" }}>
            <hr style={{ border: "none", borderTop: "1px solid var(--card-bd)", marginBottom: 16 }} />
            <ChartImage image={image!} />
          </div>
        )}

        {/* Download buttons */}
        {(hasImage || hasPdf) && (
          <div className="flex gap-2 mt-4 flex-wrap">
            {hasImage && (
              <button
                onClick={() => downloadImage(image!)}
                className="flex items-center gap-1.5 px-3 py-1.5 rounded-lg text-xs font-semibold transition-all hover:opacity-80"
                style={{ background: "#6366f122", color: "#6366f1", border: "1px solid #6366f144" }}
              >
                <ImageIcon size={13} />
                Download Chart
              </button>
            )}
            {hasPdf && (
              <button
                onClick={() => downloadPdf(pdfPath!)}
                className="flex items-center gap-1.5 px-3 py-1.5 rounded-lg text-xs font-semibold transition-all hover:opacity-80"
                style={{ background: "#10b98122", color: "#10b981", border: "1px solid #10b98144" }}
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

/* ─── typing dots ────────────────────────────────────────────────────── */
function TypingDots() {
  return (
    <div className="flex gap-3 items-start">
      <div className="shrink-0 w-8 h-8 rounded-xl bg-gradient-to-br from-indigo-500 to-blue-600 flex items-center justify-center shadow-md">
        <img src="/x.svg" alt="AI" className="w-4 h-4" />
      </div>
      <div
        style={{ background: "var(--card-bg)", border: "1px solid var(--card-bd)", backdropFilter: "var(--blur)" }}
        className="rounded-tl-sm rounded-tr-2xl rounded-b-2xl px-5 py-4 flex items-center gap-1.5"
      >
        {[0, 1, 2].map((i) => (
          <span
            key={i}
            style={{
              width: 7, height: 7, borderRadius: "50%",
              background: "var(--muted-tx)",
              display: "inline-block",
              animation: `chatBounce 1.2s ease-in-out ${i * 0.2}s infinite`,
            }}
          />
        ))}
      </div>
    </div>
  );
}

/* ─── input bar ──────────────────────────────────────────────────────── */
function InputBar({ value, onChange, onSend, disabled }: {
  value: string;
  onChange: (v: string) => void;
  onSend: () => void;
  disabled: boolean;
}) {
  const ref = useRef<HTMLTextAreaElement>(null);

  const handleKey = (e: React.KeyboardEvent) => {
    if (e.key === "Enter" && !e.shiftKey) { e.preventDefault(); onSend(); }
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
        className="max-w-3xl mx-auto flex items-end gap-3 rounded-2xl px-4 py-3"
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
          onChange={(e) => onChange(e.target.value)}
          onKeyDown={handleKey}
          placeholder="Ask about pricing insights, trends, or comparisons..."
          style={{ color: "var(--title-tx)" }}
          className="flex-1 bg-transparent outline-none resize-none text-sm leading-relaxed placeholder:text-[var(--muted-tx)] max-h-[120px]"
        />
        <button
          onClick={onSend}
          disabled={disabled || !value.trim()}
          className="shrink-0 w-9 h-9 rounded-xl bg-gradient-to-br from-indigo-500 to-blue-600 flex items-center justify-center text-white shadow-lg transition-all hover:scale-105 hover:shadow-indigo-300/40 disabled:opacity-40 disabled:hover:scale-100"
        >
          <ArrowUp size={16} />
        </button>
      </div>
      <p style={{ color: "var(--muted-tx)" }} className="text-xs text-center mt-2 opacity-60">
        Press Enter to send, Shift+Enter for new line
      </p>
    </div>
  );
}

/* ─── page ───────────────────────────────────────────────────────────── */
export default function PricingAnalysisAskAssistant() {
  const [input, setInput] = useState("");
  const [chat, setChat] = useState<ChatMessage[]>([]);
  const [loading, setLoading] = useState(false);
  const [started, setStarted] = useState(false);
  const bottomRef = useRef<HTMLDivElement>(null);

  useEffect(() => {
    bottomRef.current?.scrollIntoView({ behavior: "smooth" });
  }, [chat, loading]);

  const sendMessage = async () => {
    const msg = input.trim();
    if (!msg) return;
    setStarted(true);
    setChat((p) => [...p, { role: "user", text: msg }]);
    setInput("");
    setLoading(true);
    try {
      const url = `${API_BASE}/chat`;
      console.log("[AskAssistant] fetching →", url);
      const res = await fetch(url, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ data: "price_analysis", message: msg }),
      });
      const result = await res.json();
      const responseText = findStringValue(result, ["message", "answer", "response", "output"]) || "No response";
      const responseImage = findStringValue(result, ["image", "chart", "chart_image", "image_base64", "base64_image"]);
      const responsePdfPath = findStringValue(result, ["pdf_path", "pdfPath"]);

      console.log("[Analytics Platform] API response:", {
        message: responseText.slice(0, 80),
        hasImage: !!responseImage,
        imageLength: responseImage?.length ?? 0,
        imageStart: responseImage?.slice(0, 30),
        pdfPath: responsePdfPath,
      });
      setChat((p) => [...p, {
        role: "bot",
        text: responseText,
        image: responseImage,
        pdfPath: responsePdfPath,
      }]);
    } catch {
      setChat((p) => [...p, { role: "bot", text: "⚠️ Couldn't reach the server. Please try again." }]);
    } finally {
      setLoading(false);
    }
  };

  return (
    <div className="w-full h-screen flex flex-col" style={{ background: "transparent" }}>
      <style>{`
        @keyframes chatBounce {
          0%, 80%, 100% { transform: translateY(0); opacity: 0.4; }
          40%            { transform: translateY(-6px); opacity: 1; }
        }
      `}</style>

      <DashboardTopbar title="Beer & Cider Pricing Analysis" />

      {!started ? (
        /* ── Welcome screen ── */
        <div className="flex-1 flex flex-col overflow-hidden">
          <div className="flex-1 flex flex-col items-center justify-center px-8 pb-6">
            {/* Logo orb */}
            <div className="relative mb-6">
              <div className="absolute inset-0 blur-3xl opacity-20 scale-150 rounded-full" style={{ background: "var(--card-bd)" }} />
              <div
                className="relative w-20 h-20 rounded-3xl flex items-center justify-center"
                style={{
                  background: "var(--card-bg)",
                  border: "1px solid var(--card-bd)",
                  backdropFilter: "var(--blur)",
                  WebkitBackdropFilter: "var(--blur)",
                  boxShadow: "0 8px 32px rgba(0,0,0,0.1)",
                }}
              >
                <img src="/x.svg" alt="Analytics Platform" className="w-12 h-12" />
              </div>
            </div>

            <h1 style={{ color: "var(--title-tx)" }} className="text-4xl font-bold mb-2 tracking-tight text-center">
              Ask <span className="bg-gradient-to-r from-indigo-500 to-blue-500 bg-clip-text text-transparent">Analytics Platform</span>
            </h1>
            <p style={{ color: "var(--muted-tx)" }} className="text-base mb-10 text-center max-w-sm">
              AI-powered insights for beer & cider pricing, promotions, and market trends.
            </p>

            {/* Suggestion chips */}
            <div className="grid grid-cols-2 gap-3 w-full max-w-2xl">
              {SUGGESTIONS.map((s, i) => (
                <button
                  key={i}
                  onClick={() => setInput(s.text)}
                  style={{ background: "var(--card-bg)", border: "1px solid var(--card-bd)", backdropFilter: "var(--blur)", WebkitBackdropFilter: "var(--blur)", color: "var(--body-tx)" }}
                  className="flex items-start gap-3 text-left px-4 py-3.5 rounded-2xl text-sm hover:border-indigo-400 transition-all hover:shadow-md hover:-translate-y-0.5"
                >
                  <span className="text-lg leading-none mt-0.5 shrink-0">{s.icon}</span>
                  <span className="leading-snug">{s.text}</span>
                </button>
              ))}
            </div>
          </div>

          <InputBar value={input} onChange={setInput} onSend={sendMessage} disabled={loading} />
        </div>
      ) : (
        /* ── Chat screen ── */
        <div className="flex-1 flex flex-col overflow-hidden">
          {/* Messages */}
          <div className="flex-1 overflow-y-auto px-6 py-6 space-y-6">
            <div className="max-w-3xl mx-auto space-y-6">
              {chat.map((msg, i) => (
                <div key={i}>
                  {msg.role === "user" ? (
                    <div className="flex justify-end">
                      <div
                        className="max-w-lg px-5 py-3.5 rounded-2xl rounded-br-sm text-sm text-white shadow-lg"
                        style={{ background: "linear-gradient(135deg, #6366f1, #3b82f6)" }}
                      >
                        {msg.text}
                      </div>
                    </div>
                  ) : (
                    <BotMessage text={msg.text} image={msg.image} pdfPath={msg.pdfPath} />
                  )}
                </div>
              ))}

              {loading && <TypingDots />}
              <div ref={bottomRef} />
            </div>
          </div>

          <InputBar value={input} onChange={setInput} onSend={sendMessage} disabled={loading} />
        </div>
      )}
    </div>
  );
}
