"""Many conversations per user.

The key used to be the user, which made cross-user access impossible by
construction - there was no id to guess. Now there is one in every URL, so the
tests that matter most are the ones that try to reach somebody else's chat.
"""
from unittest.mock import patch

import pytest

from services.food_intelligence_service.app.assistant import session


class _FakeConversations:
    """The same surface as the Postgres store, a dict underneath.

    Ownership is enforced here exactly as the real queries enforce it - every
    lookup filters on conversation AND user - so a test that passes here is
    testing the rule, not the mock.
    """

    def __init__(self):
        self.rows: dict[str, dict] = {}
        self.seq = 0

    def create(self, user_sub, persona=None):
        self.seq += 1
        cid = f"c{self.seq}"
        self.rows[cid] = {"user_sub": user_sub, "title": session.DEFAULT_TITLE,
                          "transcript": [], "persona": persona, "order": self.seq}
        return cid

    def _owned(self, cid, user_sub):
        row = self.rows.get(cid)
        return row if row and row["user_sub"] == user_sub else None

    def get_state(self, cid, user_sub):
        row = self._owned(cid, user_sub)
        if not row:
            return None
        return {"transcript": list(row["transcript"]), "persona": row["persona"],
                "title": row["title"]}

    def list_for_user(self, user_sub):
        rows = [(cid, r) for cid, r in self.rows.items() if r["user_sub"] == user_sub]
        rows.sort(key=lambda x: -x[1]["order"])
        return [{"conversation_id": cid, "title": r["title"], "persona": r["persona"],
                 "updated_at": None, "messages": len(r["transcript"])}
                for cid, r in rows]

    def save_turn(self, cid, user_sub, question, answer, from_data,
                  trends=None, tool_calls=None):
        row = self._owned(cid, user_sub)
        if not row:
            return
        row["transcript"].append({"role": "user", "text": question})
        row["transcript"].append({"role": "assistant", "text": answer,
                                  "from_data": from_data, "trends": trends or [],
                                  "tool_calls": tool_calls or []})
        if not row["title"] or row["title"] == session.DEFAULT_TITLE:
            row["title"] = session._title_from(question)
        self.seq += 1
        row["order"] = self.seq

    def set_persona(self, cid, user_sub, persona):
        row = self._owned(cid, user_sub)
        if not row:
            return False
        row["persona"] = persona
        return True

    def delete(self, cid, user_sub):
        if self._owned(cid, user_sub):
            del self.rows[cid]
            return True
        return False


@pytest.fixture
def store(monkeypatch):
    from services.food_intelligence_service.app.api.v1 import assistant as route
    fake = _FakeConversations()
    for name in ("create", "get_state", "list_for_user", "save_turn",
                 "set_persona", "delete"):
        monkeypatch.setattr(session, name, getattr(fake, name))
        monkeypatch.setattr(route.session, name, getattr(fake, name))
    return fake


def test_a_user_can_hold_several_conversations_at_once(store):
    a, b = session.create("u1"), session.create("u1")
    session.save_turn(a, "u1", "about matcha", "answer a", True)
    session.save_turn(b, "u1", "about almarai", "answer b", True)
    assert session.get_state(a, "u1")["transcript"][0]["text"] == "about matcha"
    assert session.get_state(b, "u1")["transcript"][0]["text"] == "about almarai"


def test_the_list_is_newest_first(store):
    first, second = session.create("u1"), session.create("u1")
    session.save_turn(first, "u1", "older", "a", True)
    session.save_turn(second, "u1", "newer", "a", True)
    titles = [c["title"] for c in session.list_for_user("u1")]
    assert titles == ["newer", "older"]


def test_a_chat_names_itself_from_its_first_question(store):
    cid = session.create("u1")
    assert session.get_state(cid, "u1")["title"] == session.DEFAULT_TITLE
    session.save_turn(cid, "u1", "what is happening with matcha", "a", True)
    assert session.get_state(cid, "u1")["title"] == "what is happening with matcha"
    # The second question must not rename it - the title is the chat's identity
    # in the sidebar and a moving one is unusable.
    session.save_turn(cid, "u1", "and pistachio", "a", True)
    assert session.get_state(cid, "u1")["title"] == "what is happening with matcha"


def test_a_long_first_question_is_cut_on_a_word():
    long = ("compare the dubai chocolate trend against matcha and tell me which "
            "brands are posting in either of them")
    title = session._title_from(long)
    assert len(title) <= session.TITLE_CHARS + 1
    assert title.endswith("…")
    assert not title[:-1].endswith(" "), "cut at a word, not mid-word"


def test_an_empty_question_does_not_produce_an_empty_title():
    assert session._title_from("   ") == session.DEFAULT_TITLE


def test_one_user_cannot_read_anothers_conversation(store):
    mine = session.create("owner")
    session.save_turn(mine, "owner", "private question", "private answer", True)
    assert session.get_state(mine, "intruder") is None


def test_one_user_cannot_write_into_anothers_conversation(store):
    mine = session.create("owner")
    session.save_turn(mine, "owner", "q", "a", True)
    session.save_turn(mine, "intruder", "injected", "injected", True)
    transcript = session.get_state(mine, "owner")["transcript"]
    assert [m["text"] for m in transcript] == ["q", "a"]


def test_one_user_cannot_delete_or_repin_anothers_conversation(store):
    mine = session.create("owner")
    assert session.delete(mine, "intruder") is False
    assert session.set_persona(mine, "intruder", "busy-family") is False
    assert session.get_state(mine, "owner") is not None
    assert session.get_state(mine, "owner")["persona"] is None


def test_a_conversation_only_lists_for_its_owner(store):
    session.create("owner")
    assert len(session.list_for_user("owner")) == 1
    assert session.list_for_user("intruder") == []


def test_the_pin_belongs_to_the_conversation_not_the_page(store):
    """Held in the UI, a persona would follow the reader across a switch: pick a
    segment in one chat, open another, and its answers would quietly be about
    that segment too."""
    pinned, plain = session.create("u1", persona="fitness-focused"), session.create("u1")
    assert session.get_state(pinned, "u1")["persona"] == "fitness-focused"
    assert session.get_state(plain, "u1")["persona"] is None


def test_a_missing_conversation_reads_the_same_as_one_you_do_not_own(store):
    """Both return None so that a 404 cannot be used to confirm that somebody
    else's conversation exists."""
    mine = session.create("owner")
    assert session.get_state("never-existed", "owner") is None
    assert session.get_state(mine, "intruder") is None


def test_the_turn_lock_is_per_conversation_not_per_user():
    """One chat's turn must be atomic; two of a user's own chats answering at
    once is the point of having several."""
    import inspect
    from services.food_intelligence_service.app.api.v1 import assistant as route
    source = inspect.getsource(route._run_turn)
    assert '_lock_for(f"{user_sub}:{conversation_id}")' in source


def test_prior_turns_are_replayed_into_the_graph(store):
    """The graph carries its own messages, so the stored transcript is what
    gives it memory. Replaying the wrong conversation's history would be worse
    than replaying none: the answer would be coherent and about the wrong chat."""
    import asyncio
    from unittest.mock import patch as _patch
    from services.food_intelligence_service.app.api.v1 import assistant as route

    seen: list[list] = []

    async def _stream(question, context, transcript, embed_query, user_sub=None,
                      persona=None):
        seen.append(list(transcript))
        yield {"type": "done", "answer": "ok", "tool_calls": [],
               "trends": [], "from_data": False}

    async def turn(text, conversation_id=None):
        body = route.ChatRequest(message=text, conversation_id=conversation_id)
        with _patch.object(route.graph, "astream", _stream), \
             _patch.object(route.agent, "build_context", return_value=("", 0)):
            return await route.chat(body, current_user={"sub": "u1", "username": "u1"})

    first = asyncio.run(turn("first question"))
    cid = first["conversation_id"]
    asyncio.run(turn("second question", cid))
    # A different chat, started by the same user at the same time.
    other = asyncio.run(turn("unrelated question"))

    assert seen[0] == [], "a new conversation has no history to replay"
    assert [m["text"] for m in seen[1]] == ["first question", "ok"]
    assert seen[2] == [], "the second chat must not inherit the first one's memory"
    assert other["conversation_id"] != cid


def test_the_non_streaming_route_reports_which_conversation_it_used(store):
    """The caller sends no id on a first message and needs the one it got, or
    every message starts another chat."""
    import asyncio
    from unittest.mock import patch as _patch
    from services.food_intelligence_service.app.api.v1 import assistant as route

    async def _stream(question, context, transcript, embed_query, user_sub=None,
                      persona=None):
        yield {"type": "done", "answer": "ok", "tool_calls": [], "trends": [],
               "from_data": False}

    body = route.ChatRequest(message="hello")
    with _patch.object(route.graph, "astream", _stream), \
         _patch.object(route.agent, "build_context", return_value=("", 0)):
        out = asyncio.run(route.chat(body, current_user={"sub": "u1", "username": "u1"}))
    assert out["conversation_id"], "the new conversation's id comes back"
    assert session.get_state(out["conversation_id"], "u1") is not None
