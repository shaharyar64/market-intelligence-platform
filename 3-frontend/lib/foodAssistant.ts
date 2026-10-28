import { apiFetch } from "@/lib/apiClient";

const BASE = "/api/v1/food-intelligence/assistant";

export type ToolCall = {
  name: string;
  ok: boolean;
  count: number;
  args?: Record<string, unknown>;
  /** Filters the server dropped to get a result, e.g. ["persona='busy-family'"].
   *  Present means this call did NOT run with the filters it was given. */
  relaxed_filters?: string[];
};
export type TrendRef = { trend_id: string; name: string };

export type StoredMessage = {
  /** "bot" is the previous name for "assistant"; transcripts written before the
   *  rename are still in browsers' local storage. */
  role: "user" | "assistant" | "bot";
  text: string;
  from_data?: boolean;
  trends?: TrendRef[];
  tool_calls?: ToolCall[];
};

/** One chat in the sidebar. The transcript is deliberately absent: the list has
 *  to stay cheap however many conversations a user accumulates. */
export type ConversationSummary = {
  conversation_id: string;
  title: string;
  persona: string | null;
  updated_at: string | null;
  messages: number;
};

export type Conversation = {
  conversation_id: string;
  title: string;
  persona: string | null;
  transcript: StoredMessage[];
  has_history: boolean;
};

export type StreamEvent =
  /** Sent before any work. A message sent without an id starts a conversation,
   *  and this is how the client learns which one to send the next message to. */
  | { type: "conversation"; conversation_id: string; created: boolean }
  | { type: "status"; stage: "retrieving" | "thinking" | "tool"; name?: string }
  | { type: "tool"; name: string; ok: boolean; count: number }
  | { type: "delta"; text: string }
  | { type: "done"; answer: string; tool_calls: ToolCall[]; trends: TrendRef[];
      from_data: boolean; relaxed_filters?: string[]; persona_applied?: boolean | null }
  | { type: "error"; message: string };

/** Streams one answer into a conversation.
 *
 *  EventSource cannot POST and cannot carry an Authorization header, so this
 *  reads the response body itself. Frames are split on the blank line SSE uses
 *  as a terminator, and a partial frame is carried over to the next chunk -
 *  a chunk boundary lands mid-JSON often enough that parsing per chunk drops
 *  events.
 */
export async function streamAssistant(
  message: string,
  onEvent: (event: StreamEvent) => void,
  opts: { conversationId?: string | null; persona?: string | null } = {},
): Promise<void> {
  const res = await apiFetch(`${BASE}/chat/stream`, {
    method: "POST",
    body: JSON.stringify({
      message,
      conversation_id: opts.conversationId ?? null,
      persona: opts.persona ?? null,
    }),
  });
  if (!res.ok || !res.body) throw new Error(`${res.status} ${await res.text().catch(() => "")}`);

  const reader = res.body.getReader();
  const decoder = new TextDecoder();
  let buffer = "";

  for (;;) {
    const { done, value } = await reader.read();
    if (done) break;
    buffer += decoder.decode(value, { stream: true });
    const frames = buffer.split("\n\n");
    buffer = frames.pop() ?? "";
    for (const frame of frames) {
      const line = frame.split("\n").find((l) => l.startsWith("data:"));
      if (!line) continue;
      try {
        onEvent(JSON.parse(line.slice(5).trim()) as StreamEvent);
      } catch {
        // A frame we cannot parse is dropped rather than killing the stream.
      }
    }
  }
}

/** The caller's chats, newest first. */
export async function listConversations(): Promise<ConversationSummary[]> {
  const res = await apiFetch(`${BASE}/conversations`);
  if (!res.ok) throw new Error(`${res.status}`);
  const body = (await res.json()) as { conversations?: ConversationSummary[] };
  return body.conversations ?? [];
}

export async function createConversation(
  persona?: string | null,
): Promise<ConversationSummary> {
  const res = await apiFetch(`${BASE}/conversations`, {
    method: "POST",
    body: JSON.stringify({ persona: persona ?? null }),
  });
  if (!res.ok) throw new Error(`${res.status} ${await res.text().catch(() => "")}`);
  const body = (await res.json()) as Omit<ConversationSummary, "updated_at">;
  return { ...body, updated_at: null };
}

export async function fetchConversation(id: string): Promise<Conversation | null> {
  const res = await apiFetch(`${BASE}/conversations/${id}`);
  // 404 covers both "deleted" and "not yours" - the server does not distinguish
  // them on purpose, and neither should the caller.
  if (res.status === 404) return null;
  if (!res.ok) throw new Error(`${res.status}`);
  return res.json() as Promise<Conversation>;
}

export async function deleteConversation(id: string): Promise<void> {
  const res = await apiFetch(`${BASE}/conversations/${id}`, { method: "DELETE" });
  if (!res.ok && res.status !== 404) throw new Error(`${res.status}`);
}

export async function setConversationPersona(
  id: string,
  persona: string | null,
): Promise<void> {
  const res = await apiFetch(`${BASE}/conversations/${id}/persona`, {
    method: "PUT",
    body: JSON.stringify({ persona }),
  });
  if (!res.ok) throw new Error(`${res.status}`);
}

export type Persona = {
  persona_id: string;
  name: string;
  tagline: string | null;
  posts: number | null;
  share_of_food_posts_pct: number | null;
};

/** The segments a conversation can be pinned to.
 *
 *  Throws on failure rather than returning an empty list. Swallowing the error
 *  here was a mistake: the picker hides itself when the list is empty, so a 401
 *  or a stale bundle looked identical to "no personas exist" - the feature
 *  simply was not on screen and nothing said why. The caller still keeps the
 *  chat usable; it just gets told what went wrong.
 */
export async function fetchPersonas(): Promise<Persona[]> {
  const res = await apiFetch("/api/v1/food-intelligence/personas");
  if (!res.ok) {
    throw new Error(`${res.status} ${await res.text().catch(() => "")}`.trim());
  }
  const body = (await res.json()) as { personas?: Persona[] };
  return body.personas ?? [];
}
