"""Stored conversations, in Postgres.

A user has many conversations now, so the primary key is the conversation and
the owner sits beside it. That ordering matters more than it looks: when the key
WAS the user, a caller could not reach another user's chat even by accident,
because there was nothing to name. With ids in the URL there is, so every read
and every write in this module takes user_sub as well and filters on both. A
lookup that misses returns None rather than raising - a guessed id and a deleted
one should be indistinguishable from outside.

The transcript is both what the screen shows and what gives the agent its
memory: the graph carries its own messages, so recent turns are replayed into it
on the next question. That is why this lives in the database rather than in
process memory - a conversation survives a restart, works behind more than one
instance, and follows the user to another machine.

The pinned persona belongs to the conversation, not to the page. Held in the UI
it would leak across a switch: pick a segment in one chat, open another, and the
answers there would quietly be about that segment too.
"""
import json
import logging
import uuid

from services.food_intelligence_service.app.trends import store

logger = logging.getLogger("assistant.session")

MAX_TRANSCRIPT = 60
TITLE_CHARS = 60
DEFAULT_TITLE = "New chat"


def ensure_table() -> None:
    with store.get_conn() as conn, conn.cursor() as cur:
        cur.execute("""
            CREATE TABLE IF NOT EXISTS food_intel.assistant_conversations (
                conversation_id text PRIMARY KEY,
                user_sub        text NOT NULL,
                title           text NOT NULL DEFAULT %s,
                transcript      jsonb NOT NULL DEFAULT '[]'::jsonb,
                persona         text,
                created_at      timestamptz NOT NULL DEFAULT now(),
                updated_at      timestamptz NOT NULL DEFAULT now()
            )
        """, (DEFAULT_TITLE,))
        # The sidebar query is "this user's conversations, newest first" and
        # nothing else, so it gets the index it asks for.
        cur.execute("""CREATE INDEX IF NOT EXISTS assistant_conversations_by_user
                       ON food_intel.assistant_conversations (user_sub, updated_at DESC)""")
        # One row per answered question. Kept apart from the transcript, which is
        # trimmed and can be cleared, so a chat's cost outlives what it says.
        cur.execute("""
            CREATE TABLE IF NOT EXISTS food_intel.assistant_usage (
                usage_id        bigserial PRIMARY KEY,
                user_sub        text NOT NULL,
                conversation_id text NOT NULL,
                usage           jsonb NOT NULL,
                created_at      timestamptz NOT NULL DEFAULT now()
            )
        """)
        cur.execute("""CREATE INDEX IF NOT EXISTS assistant_usage_by_user
                       ON food_intel.assistant_usage (user_sub, created_at)""")


def _title_from(question: str) -> str:
    """A chat names itself from its first question.

    Nobody titles a conversation by hand, and an untitled list is unusable once
    it is more than a few rows long.
    """
    text = " ".join((question or "").split())
    if len(text) <= TITLE_CHARS:
        return text or DEFAULT_TITLE
    return text[:TITLE_CHARS].rsplit(" ", 1)[0] + "…"


def create(user_sub: str, persona: str | None = None) -> str:
    conversation_id = uuid.uuid4().hex
    with store.get_conn() as conn, conn.cursor() as cur:
        cur.execute("""INSERT INTO food_intel.assistant_conversations
                           (conversation_id, user_sub, persona)
                       VALUES (%s, %s, %s)""",
                    (conversation_id, user_sub, persona))
    return conversation_id


def list_for_user(user_sub: str) -> list[dict]:
    """The sidebar. Transcripts are not read - only their length is needed."""
    with store.get_conn() as conn, conn.cursor() as cur:
        cur.execute("""
            SELECT conversation_id, title, persona, updated_at,
                   jsonb_array_length(transcript) AS messages
            FROM food_intel.assistant_conversations
            WHERE user_sub = %s
            ORDER BY updated_at DESC
        """, (user_sub,))
        return [{"conversation_id": r[0], "title": r[1], "persona": r[2],
                 "updated_at": r[3].isoformat() if r[3] else None,
                 "messages": r[4]}
                for r in cur.fetchall()]


def get_state(conversation_id: str, user_sub: str) -> dict | None:
    """One conversation, or None when it is missing or not this caller's."""
    if not conversation_id:
        return None
    with store.get_conn() as conn, conn.cursor() as cur:
        cur.execute("""SELECT transcript, persona, title
                       FROM food_intel.assistant_conversations
                       WHERE conversation_id = %s AND user_sub = %s""",
                    (conversation_id, user_sub))
        row = cur.fetchone()
    if not row:
        return None
    transcript = row[0]
    if isinstance(transcript, str):
        transcript = json.loads(transcript)
    return {"transcript": transcript or [], "persona": row[1], "title": row[2]}


def save_turn(conversation_id: str, user_sub: str, question: str, answer: str,
              from_data: bool, trends: list[dict] | None = None,
              persona_applied: bool | None = None,
              tool_calls: list[dict] | None = None) -> None:
    """Append one exchange, and title the conversation if it has none yet.

    The transcript is trimmed to the most recent MAX_TRANSCRIPT messages: a
    conversation that never ends should not grow a row without limit.

    The trend links and tool calls are stored alongside the text because both
    are derived from tool output that is gone by the time the transcript is read
    back - they are what makes a trend name clickable and the tool chips visible
    in a reloaded conversation.
    """
    state = get_state(conversation_id, user_sub)
    if state is None:
        logger.warning("refusing to write to conversation %s for another user",
                       conversation_id)
        return
    transcript = state["transcript"]
    transcript.append({"role": "user", "text": question})
    transcript.append({"role": "assistant", "text": answer, "from_data": from_data,
                       "trends": trends or [],
                       "persona_applied": persona_applied,
                       "relaxed_filters": sorted(
                           {f for c in (tool_calls or [])
                            for f in (c.get("relaxed_filters") or [])}),
                       "tool_calls": [{"name": c.get("name"), "ok": bool(c.get("ok")),
                                       "count": int(c.get("count") or 0),
                                       "relaxed_filters": c.get("relaxed_filters") or []}
                                      for c in (tool_calls or [])]})
    transcript = transcript[-MAX_TRANSCRIPT:]
    title = state["title"]
    if not title or title == DEFAULT_TITLE:
        title = _title_from(question)
    with store.get_conn() as conn, conn.cursor() as cur:
        cur.execute("""
            UPDATE food_intel.assistant_conversations
               SET transcript = %s, title = %s, updated_at = now()
             WHERE conversation_id = %s AND user_sub = %s
        """, (json.dumps(transcript, ensure_ascii=False), title,
              conversation_id, user_sub))


def save_usage(conversation_id: str, user_sub: str, usage: dict) -> None:
    with store.get_conn() as conn, conn.cursor() as cur:
        cur.execute("""INSERT INTO food_intel.assistant_usage (user_sub, conversation_id, usage)
                       VALUES (%s, %s, %s)""",
                    (user_sub, conversation_id, json.dumps(usage)))


def set_persona(conversation_id: str, user_sub: str, persona: str | None) -> bool:
    with store.get_conn() as conn, conn.cursor() as cur:
        cur.execute("""UPDATE food_intel.assistant_conversations
                          SET persona = %s
                        WHERE conversation_id = %s AND user_sub = %s""",
                    (persona, conversation_id, user_sub))
        return cur.rowcount > 0


def delete(conversation_id: str, user_sub: str) -> bool:
    with store.get_conn() as conn, conn.cursor() as cur:
        cur.execute("""DELETE FROM food_intel.assistant_conversations
                       WHERE conversation_id = %s AND user_sub = %s""",
                    (conversation_id, user_sub))
        return cur.rowcount > 0


def clear(conversation_id: str, user_sub: str) -> bool:
    """Empty a conversation without removing it from the list."""
    with store.get_conn() as conn, conn.cursor() as cur:
        cur.execute("""UPDATE food_intel.assistant_conversations
                          SET transcript = '[]'::jsonb, title = %s, updated_at = now()
                        WHERE conversation_id = %s AND user_sub = %s""",
                    (DEFAULT_TITLE, conversation_id, user_sub))
        return cur.rowcount > 0
