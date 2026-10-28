"use client";

import { Children, memo, useCallback, useEffect, useMemo, useRef, useState } from "react";
import { ArrowUp, Sparkles, TrendingUp, Users, Boxes, Plus, MessageSquare,
         Trash2, PanelLeftClose, PanelLeft, X } from "lucide-react";
import DashboardTopbar from "@/components/layout/DashboardTopbar";
import { Skel } from "@/components/ui/RealEstateTrendsPanels";
import { streamAssistant, listConversations,
         fetchConversation, deleteConversation,
         fetchPersonas, setConversationPersona,
         type TrendRef, type ToolCall, type Persona,
         type ConversationSummary } from "@/lib/realEstateTrendsAssistant";
import { PersonaSaveQueue } from "@/lib/personaSelection";
import Link from "next/link";
import ReactMarkdown, { type Components } from "react-markdown";
import remarkGfm from "remark-gfm";

type Msg = { role: "user" | "assistant"; text: string; from_data?: boolean; trends?: TrendRef[];
              tool_calls?: ToolCall[];
              /** The persona an answer was written for; null = general view. */
              persona?: string | null;
              /** True only while this bubble is being written into. */
              streaming?: boolean };

const SUGGESTIONS = [
  { icon: <TrendingUp size={15} aria-hidden="true" />, text: "Which property trends are breaking out this month?" },
  { icon: <Boxes size={15} aria-hidden="true" />, text: "Which offerings are the tracked brands focusing on?" },
  { icon: <Users size={15} aria-hidden="true" />, text: "Which developers are most present in waterfront trends?" },
  { icon: <Sparkles size={15} aria-hidden="true" />, text: "Compare how developers and the market talk about branded residences." },
];

// Only which chat was open, never the transcript. Caching messages locally made
// sense with one conversation per user; with several it is a second source of
// truth that can disagree with the server about which chat you are even in.
const LAST_CHAT_KEY = "re-assistant-last-conversation";

/** Older transcripts call the assistant "bot" and its provenance flag
 *  "grounded". Those turns are still stored, so they are translated on the way
 *  in rather than rendered as an unknown role.
 *
 *  Module scope rather than inside the component: it closes over nothing, and
 *  as a const inside it was read by an earlier handler than the line that
 *  declared it. */
function normalise(
  m: Msg | (Omit<Msg, "role"> & { role: string; grounded?: boolean }),
): Msg {
  return {
    ...m,
    role: m.role === "user" ? "user" : "assistant",
    from_data: (m as { from_data?: boolean }).from_data
      ?? (m as { grounded?: boolean }).grounded,
  };
}

export default function AiAssistantPage() {
  const [input, setInput] = useState("");
  const [chat, setChat] = useState<Msg[]>([]);
  const [typing, setTyping] = useState(false);
  const [started, setStarted] = useState(false);
  const [conversations, setConversations] = useState<ConversationSummary[]>([]);
  // null means "a new chat that has not been sent yet". The row is only created
  // on the first message, so browsing away from an empty chat leaves nothing
  // behind in the list.
  const [activeId, setActiveId] = useState<string | null>(null);
  const [restored, setRestored] = useState(false);
  const [openingId, setOpeningId] = useState<string | null>(null);
  const [railOpen, setRailOpen] = useState(true);
  const [sheetOpen, setSheetOpen] = useState(false);
  // What the assistant is doing right now, shown beside the dots.
  const [stage, setStage] = useState<string | null>(null);
  const [personas, setPersonas] = useState<Persona[]>([]);
  const [personasLoading, setPersonasLoading] = useState(true);
  // The perspective the next answer is written from. null is the general view.
  // It is carried into a new chat, because it describes the reader rather than
  // the question, and opening a chat adopts that chat's own.
  const [persona, setPersona] = useState<string | null>(null);
  const listRef = useRef<HTMLDivElement>(null);
  const taRef = useRef<HTMLTextAreaElement>(null);
  const personaSaves = useRef(new PersonaSaveQueue());
  const personaRevision = useRef(0);

  useEffect(() => {
    let live = true;
    fetchPersonas()
      .then((rows) => { if (live) setPersonas(rows); })
      // The chat works without a persona, so a failure here must not break the
      // page - the picker simply offers the general view alone.
      .catch((err) => console.error("Could not load personas:", err))
      .finally(() => { if (live) setPersonasLoading(false); });
    return () => { live = false; };
  }, []);

  const refreshConversations = () =>
    listConversations()
      .then(setConversations)
      .catch((err) => console.error("Could not list conversations:", err));

  const openConversation = useCallback(async (id: string) => {
    ++personaRevision.current;
    setOpeningId(id);
    setSheetOpen(false);
    try {
      const found = await fetchConversation(id);
      if (!found) {
        // Deleted in another tab, or never ours. Fall back to a fresh chat
        // rather than showing an empty transcript under a stale title.
        setActiveId(null);
        setChat([]);
        setStarted(false);
        await refreshConversations();
        return;
      }
      setActiveId(found.conversation_id);
      setChat(found.transcript.map(normalise));
      setStarted(found.transcript.length > 0);
      setPersona(found.persona ?? null);
      try { localStorage.setItem(LAST_CHAT_KEY, found.conversation_id); } catch { /* private mode */ }
    } finally {
      setOpeningId(null);
    }
  }, []);

  useEffect(() => {
    let live = true;
    listConversations()
      .then(async (rows) => {
        if (!live) return;
        setConversations(rows);
        let wanted: string | null = null;
        try { wanted = localStorage.getItem(LAST_CHAT_KEY); } catch { /* private mode */ }
        const target = rows.find((r) => r.conversation_id === wanted) ?? rows[0];
        if (target) await openConversation(target.conversation_id);
      })
      .catch((err) => console.error("Could not load conversations:", err))
      .finally(() => { if (live) setRestored(true); });
    return () => { live = false; };
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, []);

  // Follow the answer only while the reader is already at the bottom.
  //
  // The effect below runs on every streamed token. Scrolling unconditionally
  // meant that reading back through the conversation while an answer was being
  // written was impossible - each token snapped the view down again. A ref
  // rather than state because this changes on every scroll event and must not
  // re-render the transcript.
  const pinnedToBottom = useRef(true);

  useEffect(() => {
    const list = listRef.current;
    if (!list) return;
    const onScroll = () => {
      const gap = list.scrollHeight - list.scrollTop - list.clientHeight;
      // A small tolerance: smooth scrolling and sub-pixel heights mean "at the
      // bottom" is rarely exactly zero.
      pinnedToBottom.current = gap < 80;
    };
    list.addEventListener("scroll", onScroll, { passive: true });
    return () => list.removeEventListener("scroll", onScroll);
    // Re-attaches when the transcript mounts: it does not exist on the empty
    // state, so binding once on first render would bind to nothing.
  }, [started]);

  // Scroll the transcript itself rather than calling scrollIntoView on the
  // sentinel: scrollIntoView walks up and scrolls every scrollable ancestor,
  // including the window, which dragged the composer up off the screen.
  useEffect(() => {
    const list = listRef.current;
    if (list && pinnedToBottom.current) {
      list.scrollTo({ top: list.scrollHeight, behavior: "smooth" });
    }
  }, [chat, typing]);

  useEffect(() => {
    if (taRef.current) { taRef.current.style.height = "auto"; taRef.current.style.height = `${Math.min(taRef.current.scrollHeight, 120)}px`; }
  }, [input]);

  /** A new chat exists only on screen until the first message is sent.
   *
   *  Creating the row up front looked simpler and filled the sidebar with empty
   *  "New chat" entries every time somebody clicked the button and changed
   *  their mind. The stream creates it instead, and reports the id back.
   */
  const startNewChat = () => {
    ++personaRevision.current;
    setActiveId(null);
    setChat([]);
    setStarted(false);
    setInput("");
    setStage(null);
    setSheetOpen(false);
    try { localStorage.removeItem(LAST_CHAT_KEY); } catch { /* private mode */ }
  };

  const removeConversation = async (id: string) => {
    try {
      await deleteConversation(id);
    } catch (err) {
      console.error("Could not delete conversation:", err);
      return;
    }
    setConversations((rows) => rows.filter((r) => r.conversation_id !== id));
    if (id === activeId) startNewChat();
  };

  /** Switching persona takes effect on the next question, and is saved on the
   *  open chat straight away so a reload does not lose it. */
  const choosePersona = (next: string | null) => {
    const id = activeId;
    const revision = ++personaRevision.current;
    setPersona(next);
    if (!id) return;
    setConversations((rows) => rows.map((r) =>
      r.conversation_id === id ? { ...r, persona: next } : r));
    void personaSaves.current
      .enqueue(() => setConversationPersona(id, next))
      .catch(async (error) => {
        console.error("Could not save persona:", error);
        if (personaRevision.current !== revision) return;
        const found = await fetchConversation(id).catch(() => null);
        if (!found || personaRevision.current !== revision) return;
        const restoredPersona = found.persona ?? null;
        setPersona(restoredPersona);
        setConversations((rows) => rows.map((row) =>
          row.conversation_id === id
            ? { ...row, persona: restoredPersona }
            : row));
      });
  };

  const send = async (text?: string) => {
    if (typing) return;
    const msg = (text ?? input).trim();
    if (!msg) return;
    setStarted(true);
    pinnedToBottom.current = true;
    setChat((p) => [...p, { role: "user", text: msg }]);
    setInput("");
    setTyping(true);
    setStage("retrieving");

    // Every decision about the streaming bubble is made INSIDE the updater,
    // against the list React actually holds. Tracking its index in a closure
    // variable assigned inside a previous updater did not work: updaters run
    // later than the deltas arrive, so each delta still saw "no bubble yet" and
    // appended another one - one bubble per token.
    const patchBot = (patch: Partial<Msg>) =>
      setChat((p) => {
        const last = p[p.length - 1];
        if (last && last.role === "assistant" && last.streaming) {
          return [...p.slice(0, -1), { ...last, ...patch }];
        }
        return [...p, { role: "assistant", text: "", streaming: true, ...patch }];
      });

    let answer = "";
    let newlyCreated = false;
    const calls: ToolCall[] = [];
    try {
      await streamAssistant(msg, (event) => {
        switch (event.type) {
          case "conversation":
            // A chat with no id gets one here. Adopting it immediately is what
            // makes the second message land in the same conversation.
            setActiveId(event.conversation_id);
            try { localStorage.setItem(LAST_CHAT_KEY, event.conversation_id); }
            catch { /* private mode */ }
            if (event.created) newlyCreated = true;
            break;
          case "status":
            setStage(event.stage === "tool" ? `tool:${event.name ?? ""}` : event.stage);
            break;
          case "tool":
            calls.push({ name: event.name, ok: event.ok, count: event.count });
            // Shown while the answer is still being written, so the wait reads
            // as work rather than a hang.
            patchBot({ tool_calls: [...calls] });
            break;
          case "delta":
            answer += event.text;
            patchBot({ text: answer });
            break;
          case "done":
            patchBot({ text: event.answer || answer, from_data: event.from_data,
                       trends: event.trends, tool_calls: event.tool_calls,
                       persona: event.persona ?? null, streaming: false });
            break;
          case "error":
            patchBot({ text: event.message, from_data: false, streaming: false });
            break;
        }
      }, { conversationId: activeId, persona });
    } catch {
      setChat((p) => [...p, { role: "assistant", text: "I could not reach the assistant just now. Please try again." }]);
    } finally {
      setChat((p) => p.map((m) => (m.streaming ? { ...m, streaming: false } : m)));
      setTyping(false);
      setStage(null);
      // The turn renamed the chat if it was its first, and moved it to the top
      // of the list either way.
      if (newlyCreated || activeId) refreshConversations();
    }
  };

  return (
    <div className="flex h-dvh w-full flex-col">
      <style>{`@keyframes aiBounce{0%,80%,100%{transform:translateY(0);opacity:.4}40%{transform:translateY(-6px);opacity:1}}`}</style>
      <DashboardTopbar title="AI Assistant" />

      <div className="relative flex min-h-0 flex-1">
        <ConversationList
          conversations={conversations}
          activeId={activeId}
          openingId={openingId}
          railOpen={railOpen}
          sheetOpen={sheetOpen}
          onToggleRail={() => setRailOpen((v) => !v)}
          onCloseSheet={() => setSheetOpen(false)}
          onSelect={openConversation}
          onNew={startNewChat}
          onDelete={removeConversation}
          busy={typing}
          loaded={restored}
        />

        <div className="flex min-w-0 flex-1 flex-col">
          <div className="flex shrink-0 items-center gap-2 px-4 py-2 lg:hidden" style={{ borderBottom: "1px solid var(--card-bd)" }}>
            <button
              onClick={() => setSheetOpen(true)}
              aria-label="Show chats"
              aria-expanded={sheetOpen}
              style={{ color: "var(--body-tx)", border: "1px solid var(--card-bd)" }}
              className="flex h-10 w-10 items-center justify-center rounded-xl"
            >
              <MessageSquare size={17} aria-hidden="true" />
            </button>
            <button
              onClick={startNewChat}
              disabled={typing}
              style={{ color: "var(--body-tx)", border: "1px solid var(--card-bd)" }}
              className="flex h-10 items-center gap-2 rounded-xl px-3 text-sm font-medium disabled:opacity-50"
            >
              <Plus size={15} aria-hidden="true" /> New chat
            </button>
          </div>

          {!started ? (
            <div className="flex min-h-0 flex-1 flex-col overflow-hidden">
              <div className="flex min-h-0 flex-1 flex-col items-center justify-center overflow-y-auto px-6 py-8 sm:px-8">
                <div className="mb-6 flex h-20 w-20 items-center justify-center rounded-3xl"
                  style={{ background: "var(--fi-solid)", color: "var(--fi-solid-tx)" }}>
                  <Sparkles size={34} aria-hidden="true" />
                </div>
                <h1 style={{ color: "var(--title-tx)" }} className="mb-2 text-center text-3xl font-bold tracking-tight sm:text-4xl">
                  Ask Real Estate Intelligence
                </h1>
                <p style={{ color: "var(--body-tx)" }} className="mb-3 max-w-md text-center text-base">
                  Ask about trends, developers and offerings across the tracked property market.
                </p>
                <span
                  className="mb-8 inline-flex items-center gap-1 rounded-full px-2.5 py-1 text-xs font-semibold uppercase tracking-wider"
                  style={{ background: "var(--fi-mainstream-soft)", color: "var(--fi-mainstream-tx)", border: "1px solid var(--fi-mainstream-soft-bd)" }}
                >
                  Answers from your property trends and social posts
                </span>

                <div className="grid w-full max-w-2xl grid-cols-1 gap-3 sm:grid-cols-2">
                  {SUGGESTIONS.map((s, i) => (
                    <button
                      key={i}
                      onClick={() => send(s.text)}
                      className="flex items-start gap-3 rounded-2xl px-4 py-3.5 text-left text-sm transition-all hover:-translate-y-0.5 hover:shadow-md"
                      style={{ background: "var(--card-bg)", border: "1px solid var(--card-bd)", color: "var(--body-tx)", backdropFilter: "var(--blur)" }}
                    >
                      <span className="mt-0.5 shrink-0" style={{ color: "var(--fi-watchlist-tx)" }}>{s.icon}</span>
                      <span className="leading-snug">{s.text}</span>
                    </button>
                  ))}
                </div>
              </div>
              <InputBar taRef={taRef} value={input} onChange={setInput} onSend={() => send()} disabled={typing}
                        personas={personas} personasLoading={personasLoading} persona={persona} onPersona={choosePersona} />
            </div>
          ) : (
            <div className="flex min-h-0 flex-1 flex-col overflow-hidden">
              {/* min-h-0 is load-bearing: a flex child defaults to min-height:auto,
                  so this pane refused to shrink below its transcript and grew the
                  column past the viewport, pushing the composer below the fold. */}
              <div ref={listRef} className="min-h-0 flex-1 overflow-y-auto px-4 py-6 sm:px-6">
                <div
                  className="mx-auto max-w-3xl space-y-6"
                  role="log"
                  aria-live="polite"
                  aria-relevant="additions text"
                  aria-busy={typing}
                >
                  {chat.map((m, i) => (
                    // Keyed by position AND role: the transcript is swapped
                    // wholesale when the server copy lands, and a bare index key
                    // lets React reuse a user bubble to paint a bot message.
                    <Bubble key={`${i}-${m.role}`} m={m} personas={personas}
                            stage={m.streaming ? stage : null} />
                  ))}
                  {typing && chat[chat.length - 1]?.role !== "assistant" && (
                    <div className="flex items-center gap-3">
                      <div className="flex h-8 w-8 items-center justify-center rounded-xl"
                        style={{ background: "var(--fi-solid)", color: "var(--fi-solid-tx)" }}>
                        <Sparkles size={15} aria-hidden="true" />
                      </div>
                      <div className="flex items-center gap-2.5 rounded-2xl px-5 py-4" style={{ background: "var(--card-bg)", border: "1px solid var(--card-bd)" }}>
                        <span className="flex items-center gap-1.5" aria-hidden="true">
                          {[0, 1, 2].map((i) => (
                            <span key={i} style={{ width: 7, height: 7, borderRadius: "50%", background: "var(--muted-tx)", display: "inline-block", animation: `aiBounce 1.2s ease-in-out ${i * 0.2}s infinite` }} />
                          ))}
                        </span>
                        {stage && (
                          <span style={{ color: "var(--body-tx)" }} className="text-xs">{stageLabel(stage)}</span>
                        )}
                      </div>
                    </div>
                  )}
                </div>
              </div>
              <InputBar taRef={taRef} value={input} onChange={setInput} onSend={() => send()} disabled={typing}
                        personas={personas} personasLoading={personasLoading} persona={persona} onPersona={choosePersona} />
            </div>
          )}
        </div>
      </div>
    </div>
  );
}

const Bubble = memo(function Bubble({ m, personas, stage }: {
  m: Msg; personas: Persona[]; stage: string | null;
}) {
  if (m.role === "user") {
    return (
      <div className="flex justify-end">
        <div className="max-w-lg whitespace-pre-wrap break-words rounded-2xl rounded-br-sm px-5 py-3.5 text-sm"
          style={{ background: "var(--fi-solid)", color: "var(--fi-solid-tx)" }}>
          {m.text}
        </div>
      </div>
    );
  }
  return (
    <div className="flex items-start gap-3">
      <div className="mt-0.5 flex h-8 w-8 shrink-0 items-center justify-center rounded-xl"
        style={{ background: "var(--fi-solid)", color: "var(--fi-solid-tx)" }}>
        <Sparkles size={15} aria-hidden="true" />
      </div>
      <div className="min-w-0 max-w-2xl flex-1">
        <div
          className="break-words rounded-2xl rounded-tl-sm p-5 text-sm leading-relaxed"
          style={{ background: "var(--card-bg)", border: "1px solid var(--card-bd)", color: "var(--body-tx)", backdropFilter: "var(--blur)", boxShadow: "var(--card-shadow)" }}
        >
          {m.streaming && !m.text ? (
            // A bubble exists before its text does: tool results create it,
            // and a persona answer arrives in one piece once it has been
            // checked. Until then it says what is happening, not nothing.
            <span className="flex items-center gap-2.5" role="status">
              <span className="flex items-center gap-1.5" aria-hidden="true">
                {[0, 1, 2].map((i) => (
                  <span key={i} style={{ width: 7, height: 7, borderRadius: "50%", background: "var(--muted-tx)", display: "inline-block", animation: `aiBounce 1.2s ease-in-out ${i * 0.2}s infinite` }} />
                ))}
              </span>
              <span className="text-xs" style={{ color: "var(--body-tx)" }}>
                {stageLabel(stage ?? "thinking")}
              </span>
            </span>
          ) : (
            <Rich text={m.text} trends={m.trends ?? []} />
          )}
        </div>
        <ToolTrail calls={m.tool_calls} />
        {!m.streaming && m.persona && (
          // Which lens wrote this answer. A chat can change persona part-way,
          // and an answer read back later has to say whose view it took.
          <p className="mt-1.5 px-1 text-xs" style={{ color: "var(--muted-tx)" }}>
            Answered as {personas.find((p) => p.persona_id === m.persona)?.name ?? m.persona}
          </p>
        )}
      </div>
    </div>
  );
});

/** The chats this person has, newest first.
 *
 *  Deleting lives here rather than above the transcript because it acts on one
 *  conversation and the list is where a conversation is a thing you can point
 *  at. It only appears on hover, and asks first - a transcript is not
 *  recoverable once it is gone.
 */
function ConversationList({ conversations, activeId, openingId, railOpen, sheetOpen,
                           onToggleRail, onCloseSheet, onSelect, onNew, onDelete, busy, loaded }: {
  conversations: ConversationSummary[];
  activeId: string | null;
  openingId: string | null;
  railOpen: boolean;
  sheetOpen: boolean;
  onToggleRail: () => void;
  onCloseSheet: () => void;
  onSelect: (id: string) => void;
  onNew: () => void;
  onDelete: (id: string) => void;
  busy: boolean;
  loaded: boolean;
}) {
  const [confirming, setConfirming] = useState<string | null>(null);

  useEffect(() => {
    if (!sheetOpen) return;
    const onKey = (e: KeyboardEvent) => { if (e.key === "Escape") onCloseSheet(); };
    document.addEventListener("keydown", onKey);
    return () => document.removeEventListener("keydown", onKey);
  }, [sheetOpen, onCloseSheet]);

  const collapsedRail = (
    <div className="hidden shrink-0 px-2 py-4 lg:block" style={{ borderRight: "1px solid var(--card-bd)" }}>
      <button onClick={onToggleRail} aria-label="Show chats" aria-expanded={false}
        style={{ color: "var(--muted-tx)" }}
        className="flex h-11 w-11 items-center justify-center rounded-lg transition-colors">
        <PanelLeft size={17} aria-hidden="true" />
      </button>
    </div>
  );

  const panel = (
    <div
      role={sheetOpen ? "dialog" : undefined}
      aria-modal={sheetOpen ? true : undefined}
      aria-label={sheetOpen ? "Chats" : undefined}
      style={{ borderRight: "1px solid var(--card-bd)", background: "var(--sidebar-bg)" }}
      className={`${sheetOpen ? "fixed inset-y-0 left-0 z-40 flex w-72 shadow-2xl" : "hidden"} flex-col ${railOpen ? "lg:static lg:z-auto lg:flex lg:w-64 lg:shadow-none" : "lg:hidden"}`}
    >
      <div className="flex items-center gap-2 px-3 py-3">
        <button
          onClick={onNew}
          disabled={busy}
          style={{ background: "var(--card-bg)", border: "1px solid var(--card-bd)", color: "var(--title-tx)" }}
          className="flex min-h-11 flex-1 items-center gap-2 rounded-lg px-3 py-2 text-sm font-medium transition-colors disabled:opacity-50"
        >
          <Plus size={15} aria-hidden="true" /> New chat
        </button>
        <button onClick={onToggleRail} aria-label="Hide chats" aria-expanded
          style={{ color: "var(--muted-tx)" }}
          className="hidden h-11 w-11 shrink-0 items-center justify-center rounded-lg transition-colors lg:flex">
          <PanelLeftClose size={17} aria-hidden="true" />
        </button>
        <button onClick={onCloseSheet} aria-label="Close chats"
          style={{ color: "var(--muted-tx)" }}
          className="flex h-11 w-11 shrink-0 items-center justify-center rounded-lg transition-colors lg:hidden">
          <X size={17} aria-hidden="true" />
        </button>
      </div>

      <div className="min-h-0 flex-1 overflow-y-auto px-2 pb-4">
        {!loaded && (
          <div className="space-y-1.5 px-1" aria-hidden="true">
            {Array.from({ length: 5 }).map((_, i) => (
              <Skel key={i} className="h-9" style={{ background: "var(--card-bg-2)", width: `${68 + ((i * 11) % 28)}%` }} />
            ))}
          </div>
        )}
        {loaded && !conversations.length && (
          <p style={{ color: "var(--muted-tx)" }} className="px-3 py-2 text-xs">
            Your chats will appear here.
          </p>
        )}
        {conversations.map((c) => {
          const active = c.conversation_id === activeId;
          const opening = c.conversation_id === openingId;
          return (
            <div
              key={c.conversation_id}
              className="group relative mb-0.5 flex items-center rounded-lg"
              style={{
                background: active ? "var(--fi-watchlist-soft)" : "transparent",
                boxShadow: active ? "inset 0 0 0 1.5px var(--fi-watchlist-tx)" : "none",
              }}
            >
              <button
                onClick={() => onSelect(c.conversation_id)}
                disabled={busy}
                aria-current={active ? "true" : undefined}
                className="min-h-11 min-w-0 flex-1 rounded-lg px-3 py-2 text-left disabled:opacity-50"
              >
                <span className="flex items-center gap-2">
                  <MessageSquare size={13} className="shrink-0" aria-hidden="true"
                    style={{ color: active ? "var(--fi-watchlist-tx)" : "var(--muted-tx)" }} />
                  <span
                    className="truncate text-sm"
                    style={{ color: active ? "var(--fi-watchlist-tx)" : "var(--body-tx)" }}
                    title={c.title}
                  >
                    {c.title}
                  </span>
                  {opening && <Skel className="ml-auto h-3 w-3 shrink-0 rounded-full" />}
                </span>
              </button>
              {confirming === c.conversation_id ? (
                <span className="flex shrink-0 items-center gap-1 pr-2">
                  <button
                    onClick={() => { onDelete(c.conversation_id); setConfirming(null); }}
                    className="rounded px-1.5 py-0.5 text-xs font-semibold"
                    style={{ color: "var(--fi-danger-tx)" }}
                  >
                    Delete
                  </button>
                  <button
                    onClick={() => setConfirming(null)}
                    className="rounded px-1 py-0.5 text-xs"
                    style={{ color: "var(--muted-tx)" }}
                  >
                    No
                  </button>
                </span>
              ) : (
                <button
                  onClick={() => setConfirming(c.conversation_id)}
                  aria-label={`Delete chat: ${c.title}`}
                  style={{ color: "var(--muted-tx)" }}
                  className="mr-1 flex h-9 w-9 shrink-0 items-center justify-center rounded opacity-0 transition hover:text-red-500 focus-visible:opacity-100 group-hover:opacity-100"
                >
                  <Trash2 size={13} aria-hidden="true" />
                </button>
              )}
            </div>
          );
        })}
      </div>
    </div>
  );

  return (
    <>
      {sheetOpen && (
        <div onClick={onCloseSheet} aria-hidden="true"
          className="fixed inset-0 z-30 bg-slate-950/50 backdrop-blur-sm lg:hidden" />
      )}
      {!railOpen && collapsedRail}
      {panel}
    </>
  );
}

function stageLabel(stage: string): string {
  if (stage.startsWith("tool:")) {
    const name = stage.slice(5);
    return `${TOOL_LABELS[name] ?? name}...`;
  }
  if (stage === "writing") return "Writing the answer...";
  if (stage === "checking") return "Checking the answer...";
  return stage === "retrieving" ? "Reading the corpus..." : "Thinking...";
}

const TOOL_LABELS: Record<string, string> = {
  search_trends: "Searched trends",
  get_trend: "Read trend",
  compare_trends: "Compared trends",
  get_timeline: "Read timeline",
  aggregate_posts: "Aggregated posts",
  search_posts: "Searched posts",
  list_brands: "Listed brands",
  get_brand_profile: "Read brand profile",
  get_brand_trends: "Read brand trends",
  developers_by_topic: "Found developers by topic",
  developers_in_trend: "Found developers in trend",
  create_trend: "Created trend",
};

function ToolTrail({ calls }: { calls?: ToolCall[] }) {
  // No chips when nothing was called. The tools that did run are the useful
  // signal; a label announcing their absence only adds noise under an answer
  // that already reads as a plain reply.
  if (!calls?.length) return null;
  return (
    <div className="mt-1.5 flex flex-wrap items-center gap-1.5 px-1">
      {calls.map((c, i) => (
        <span
          key={`${c.name}-${i}`}
          title={c.ok ? `${c.count} result${c.count === 1 ? "" : "s"}` : "returned nothing"}
          className="inline-flex items-center gap-1 rounded-full px-2 py-0.5 text-xs"
          style={{
            background: "var(--card-bg-2)",
            border: "1px solid var(--card-bd)",
            color: c.ok ? "var(--muted-tx)" : "var(--fi-danger-tx)",
          }}
        >
          {TOOL_LABELS[c.name] ?? c.name}
          {c.ok ? (
            <span className="tabular-nums" style={{ opacity: 0.75 }}>{c.count}</span>
          ) : (
            <span style={{ opacity: 0.9 }}>none</span>
          )}
        </span>
      ))}
    </div>
  );
}

/** Turns every mention of a referenced trend into a link to its page.
 *  Scans by index rather than building a regex: trend names are arbitrary text
 *  and escaping them into a pattern is easy to get wrong. Longest name first,
 *  so a short name cannot claim part of a longer one. Matching is driven by the
 *  ids the API returned with the answer, so a name is linked only when the
 *  assistant actually used that trend - and the right one opens even where two
 *  trends share a name. */
function linkTrends(text: string, trends: TrendRef[], keyBase: string): React.ReactNode[] {
  if (!trends.length) return [text];
  const byLongest = [...trends].sort((a, b) => b.name.length - a.name.length);
  const out: React.ReactNode[] = [];
  let rest = text;
  let n = 0;
  while (rest.length && n < 200) {
    let hit: { at: number; t: TrendRef } | null = null;
    const lower = rest.toLowerCase();
    for (const t of byLongest) {
      const at = lower.indexOf(t.name.toLowerCase());
      if (at !== -1 && (hit === null || at < hit.at)) hit = { at, t };
    }
    if (!hit) { out.push(rest); break; }
    if (hit.at > 0) out.push(rest.slice(0, hit.at));
    const label = rest.slice(hit.at, hit.at + hit.t.name.length);
    out.push(
      <Link
        key={keyBase + "-" + n}
        href={"/trends-real-estate/trends-explorer?"
          // A market trend only exists in its market's run, so the link names it.
          + (hit.t.country ? `market=${hit.t.country}&` : "")
          + "trend=" + encodeURIComponent(hit.t.trend_id)}
        className="underline decoration-dotted underline-offset-2 hover:decoration-solid"
        style={{ color: "var(--fi-watchlist-tx)" }}
        title="Open this trend"
      >
        {label}
      </Link>
    );
    rest = rest.slice(hit.at + hit.t.name.length);
    n += 1;
  }
  return out;
}

/** Renders the assistant's markdown.
 *
 *  react-markdown parses; this file only styles. The hand-written parser it
 *  replaces could not represent nested lists, so a numbered trend with detail
 *  bullets under it rendered as one <ol> per trend and every item numbered "1".
 *
 *  Raw HTML stays off (no rehype-raw), so nothing the model writes can execute.
 */
function Rich({ text, trends = [] }: { text: string; trends?: TrendRef[] }) {
  const link = useCallback(
    (children: React.ReactNode, keyBase: string): React.ReactNode => {
      if (!trends.length) return children;
      return Children.map(children, (child, i) =>
        typeof child === "string" ? linkTrends(child, trends, `${keyBase}-${i}`) : child);
    },
    [trends],
  );

  const components: Components = useMemo(() => ({
    p: ({ children }) => <p dir="auto">{link(children, "p")}</p>,
    strong: ({ children }) => <strong>{link(children, "b")}</strong>,
    em: ({ children }) => <em>{link(children, "i")}</em>,
    li: ({ children }) => <li dir="auto">{link(children, "li")}</li>,
    ol: ({ children }) => <ol className="list-decimal space-y-2 pl-5">{children}</ol>,
    ul: ({ children }) => <ul className="list-disc space-y-2 pl-5">{children}</ul>,
    a: ({ href, children }) => (
      <a href={href} target="_blank" rel="noopener noreferrer"
         className="underline underline-offset-2"
         style={{ color: "var(--fi-watchlist-tx)" }}>
        {children}
      </a>
    ),
    // Every heading level renders at one size. These sit inside a chat bubble,
    // where an h1 would outweigh the answer around it.
    h1: ({ children }) => <Heading>{link(children, "h")}</Heading>,
    h2: ({ children }) => <Heading>{link(children, "h")}</Heading>,
    h3: ({ children }) => <Heading>{link(children, "h")}</Heading>,
    h4: ({ children }) => <Heading>{link(children, "h")}</Heading>,
    h5: ({ children }) => <Heading>{link(children, "h")}</Heading>,
    h6: ({ children }) => <Heading>{link(children, "h")}</Heading>,
    code: ({ className, children }) => {
      if (className?.includes("language-")) return <code className={className}>{children}</code>;
      return (
        <code className="rounded px-1 py-0.5 text-[0.85em]"
              style={{ background: "var(--card-bg-2)", color: "var(--title-tx)" }}>
          {children}
        </code>
      );
    },
    pre: ({ children }) => (
      <pre className="overflow-x-auto rounded-xl p-3 text-xs"
           style={{ background: "var(--card-bg-2)", border: "1px solid var(--card-bd)" }}>
        {children}
      </pre>
    ),
    blockquote: ({ children }) => (
      <blockquote className="border-l-2 pl-3" style={{ borderColor: "var(--card-bd)", color: "var(--muted-tx)" }}>
        {children}
      </blockquote>
    ),
    hr: () => <hr style={{ borderColor: "var(--card-bd)" }} />,
    table: ({ children }) => (
      <div className="overflow-x-auto">
        <table className="w-full border-collapse text-xs">{children}</table>
      </div>
    ),
    th: ({ children }) => (
      <th className="border-b px-2 py-1.5 text-left font-semibold"
          style={{ borderColor: "var(--card-bd)", color: "var(--title-tx)" }}>
        {children}
      </th>
    ),
    td: ({ children }) => (
      <td className="border-b px-2 py-1.5 align-top"
          style={{ borderColor: "var(--card-bd)" }}>
        {link(children, "td")}
      </td>
    ),
  }), [link]);

  return (
    <div className="space-y-3 [&_li>ol]:mt-2 [&_li>ul]:mt-2">
      <ReactMarkdown remarkPlugins={[remarkGfm]} components={components}>
        {text}
      </ReactMarkdown>
    </div>
  );
}

function Heading({ children }: { children: React.ReactNode }) {
  return (
    <p dir="auto" className="pt-1 text-sm font-semibold" style={{ color: "var(--title-tx)" }}>
      {children}
    </p>
  );
}

function PersonaPicker({ personas, personasLoading, persona, onPersona, disabled }: {
  personas: Persona[];
  personasLoading: boolean;
  persona: string | null;
  onPersona: (id: string | null) => void;
  disabled: boolean;
}) {
  const rowRef = useRef<HTMLDivElement>(null);
  const [edges, setEdges] = useState({ left: false, right: false });
  const active = personas.find((p) => p.persona_id === persona) ?? null;

  const measure = useCallback(() => {
    const row = rowRef.current;
    if (!row) return;
    const left = row.scrollLeft > 2;
    const right = row.scrollLeft + row.clientWidth < row.scrollWidth - 2;
    setEdges((e) => (e.left === left && e.right === right ? e : { left, right }));
  }, []);

  useEffect(() => {
    const row = rowRef.current;
    if (!row) return;
    measure();
    const observer = new ResizeObserver(measure);
    observer.observe(row);
    return () => observer.disconnect();
  }, [measure, personas.length, personasLoading]);

  useEffect(() => {
    const row = rowRef.current;
    const pill = row?.querySelector<HTMLElement>('[aria-pressed="true"]');
    if (!row || !pill) return;
    const pad = 24;
    if (pill.offsetLeft < row.scrollLeft + pad) {
      row.scrollTo({ left: Math.max(0, pill.offsetLeft - pad), behavior: "smooth" });
    } else if (pill.offsetLeft + pill.offsetWidth > row.scrollLeft + row.clientWidth - pad) {
      row.scrollTo({ left: pill.offsetLeft + pill.offsetWidth - row.clientWidth + pad, behavior: "smooth" });
    }
  }, [persona, personas.length]);

  const fade = `linear-gradient(to right, ${edges.left ? "transparent" : "#000"}, #000 28px, #000 calc(100% - 28px), ${edges.right ? "transparent" : "#000"})`;
  const pill = (on: boolean) => ({
    background: on ? "var(--fi-watchlist-soft)" : "transparent",
    color: on ? "var(--fi-watchlist-tx)" : "var(--muted-tx)",
    boxShadow: on ? "inset 0 0 0 1.5px var(--fi-watchlist-tx)" : "inset 0 0 0 1px var(--card-bd)",
  });
  const pillClass = "min-h-9 shrink-0 whitespace-nowrap rounded-full px-3 py-1 text-xs font-medium transition-colors "
    + "focus-visible:outline focus-visible:outline-2 focus-visible:outline-offset-[-2px] focus-visible:outline-[var(--fi-watchlist-tx)] disabled:opacity-50";

  return (
    <div className="mx-auto mb-2 max-w-3xl px-1">
      <div className="flex items-center gap-2">
        <span style={{ color: "var(--muted-tx)" }} className="shrink-0 text-xs">Answer as</span>
        <div
          ref={rowRef}
          role="group"
          aria-label="Answer as"
          onScroll={measure}
          onWheel={(e) => {
            const row = rowRef.current;
            if (row && row.scrollWidth > row.clientWidth && Math.abs(e.deltaY) > Math.abs(e.deltaX)) {
              row.scrollLeft += e.deltaY;
            }
          }}
          // custom-scroll, not Tailwind's [scrollbar-width:none]: globals.css sets
          // scrollbar-width on * outside any layer, which beats a utility.
          className="custom-scroll relative flex min-w-0 flex-1 items-center gap-1.5 overflow-x-auto py-0.5"
          style={{ maskImage: fade, WebkitMaskImage: fade }}
        >
          <button
            onClick={() => onPersona(null)}
            disabled={disabled}
            aria-pressed={persona === null}
            title="Answers for no particular buyer"
            style={pill(persona === null)}
            className={pillClass}
          >
            General view
          </button>
          {personasLoading
            ? <><Skel className="h-7 w-28 shrink-0 rounded-full" /><Skel className="h-7 w-32 shrink-0 rounded-full" /><Skel className="h-7 w-24 shrink-0 rounded-full" /></>
            : personas.map((p) => {
                const on = p.persona_id === persona;
                return (
                  <button
                    key={p.persona_id}
                    onClick={() => onPersona(on ? null : p.persona_id)}
                    disabled={disabled}
                    aria-pressed={on}
                    title={p.mindset}
                    style={pill(on)}
                    className={pillClass}
                  >
                    {p.name}
                  </button>
                );
              })}
        </div>
      </div>
      {active && (
        <p className="mt-1 truncate px-0.5 text-xs italic" style={{ color: "var(--muted-tx)" }}
           title={`Prioritises ${active.prioritise.join(", ")}`}>
          &ldquo;{active.mindset}&rdquo;
        </p>
      )}
    </div>
  );
}

function InputBar({ taRef, value, onChange, onSend, disabled, personas, personasLoading, persona, onPersona }: {
  taRef: React.RefObject<HTMLTextAreaElement | null>;
  value: string;
  onChange: (v: string) => void;
  onSend: () => void;
  disabled: boolean;
  personas: Persona[];
  personasLoading: boolean;
  persona: string | null;
  onPersona: (id: string | null) => void;
}) {
  return (
    <div className="shrink-0 px-4 pb-6 pt-3 sm:px-6">
      <PersonaPicker personas={personas} personasLoading={personasLoading} persona={persona}
                     onPersona={onPersona} disabled={disabled} />
      <div
        className="composer mx-auto flex max-w-3xl items-end gap-2 rounded-2xl p-2"
        style={{ background: "var(--card-bg)", border: "1px solid var(--card-bd)", backdropFilter: "var(--blur)", boxShadow: "var(--card-shadow)" }}
      >
        <label htmlFor="assistant-input" className="sr-only">Ask about trends, developers, offerings or locations</label>
        <textarea
          id="assistant-input"
          ref={taRef}
          rows={1}
          value={value}
          onChange={(e) => onChange(e.target.value)}
          onKeyDown={(e) => { if (e.key === "Enter" && !e.shiftKey) { e.preventDefault(); if (!disabled) onSend(); } }}
          placeholder="Ask about trends, developers, offerings or locations"
          style={{ color: "var(--title-tx)" }}
          className="max-h-[120px] min-h-11 flex-1 resize-none bg-transparent px-3 py-[10px] text-sm leading-relaxed outline-none placeholder:text-[var(--muted-tx)]"
        />
        <button
          onClick={onSend}
          disabled={!value.trim() || disabled}
          aria-label="Send message"
          className="flex h-11 w-11 shrink-0 items-center justify-center rounded-xl transition-all hover:scale-105 disabled:opacity-40 disabled:hover:scale-100"
          style={{ background: "var(--fi-solid)", color: "var(--fi-solid-tx)" }}
        >
          <ArrowUp size={16} aria-hidden="true" />
        </button>
      </div>
    </div>
  );
}
