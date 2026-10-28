import asyncio
import json
import logging
from collections import OrderedDict
from typing import Any

from fastapi import APIRouter, Depends, HTTPException
from fastapi.concurrency import run_in_threadpool
from fastapi.responses import StreamingResponse
from pydantic import BaseModel, Field

from services.trends_real_estate_service.app.api.deps import get_current_user
from services.trends_real_estate_service.app.assistant import agent, graph, session
from services.trends_real_estate_service.app.personas import definitions

logger = logging.getLogger("assistant.api")

router = APIRouter(prefix="/assistant", tags=["assistant"])

# Per-user locks so two messages from one user serialize: the whole
# read -> answer -> save sequence has to be atomic, or a second question can
# read the transcript before the first has written its turn into it. Different
# users still run in parallel. asyncio locks rather than threading ones, since
# the agent is an async generator now. Bounded LRU so the dict cannot grow
# without limit; dropping a lock is harmless, because the durable state lives
# in Postgres and the next request simply makes a new one.
MAX_SESSIONS = 1000
_session_locks: "OrderedDict[str, asyncio.Lock]" = OrderedDict()


def _lock_for(key: str) -> asyncio.Lock:
    lock = _session_locks.get(key)
    if lock is None:
        lock = asyncio.Lock()
        _session_locks[key] = lock
        if len(_session_locks) > MAX_SESSIONS:
            _session_locks.popitem(last=False)
    else:
        _session_locks.move_to_end(key)
    return lock


class ChatRequest(BaseModel):
    message: str = Field(min_length=1, max_length=2000)
    conversation_id: str | None = Field(default=None, max_length=64)
    # None leaves the conversation's persona as it is; "" clears it to the
    # general view. A persona sent with a message is remembered on the chat.
    persona: str | None = Field(default=None, max_length=64)


class PersonaChange(BaseModel):
    persona: str | None = Field(default=None, max_length=64)


def _effective_persona(persona: str | None) -> str | None:
    """The canonical id for a persisted persona, or General view.

    Stored ids outlive code deployments. A persona that was renamed or removed
    must not be returned to a client, because clients send the selected value
    back with the next message and an obsolete id would then fail validation.
    """
    found = definitions.get(persona)
    return found["persona_id"] if found else None


def _known_persona(persona: str | None) -> str | None:
    """A persona id the assistant defines, or None. An unknown id is refused
    here rather than stored: stored, it would pin a chat to a lens that is
    silently never applied."""
    if not persona:
        return None
    canonical = _effective_persona(persona)
    if canonical is None:
        raise HTTPException(status_code=422, detail=f"Unknown persona {persona!r}.")
    return canonical


def _requested_persona(persona: str | None) -> str | None:
    """None = keep the chat's persona, "" = general view, else a known id."""
    if persona is None or persona == "":
        return persona
    return _known_persona(persona)


def _owned_or_404(conversation_id: str, user_sub: str) -> dict:
    """Every read and write goes through here.

    A conversation the caller does not own and one that does not exist return
    the same 404 on purpose: a different status would confirm that somebody
    else's conversation is real.
    """
    state = session.get_state(conversation_id, user_sub)
    if state is None:
        raise HTTPException(status_code=404, detail="No such conversation.")
    return state


async def _run_turn(user_sub: str, message: str, conversation_id: str | None = None,
                    persona: str | None = None):
    """One question through the graph, yielding the events the client expects.

    Retrieval runs before the graph: it is the same context the assistant has
    always been given - the real trend vocabulary and the nearest posts - and it
    takes long enough that the wait needs a status of its own.

    The turn is saved when the stream completes. A client that disconnects
    part-way leaves nothing stored, which is the safe direction: a half-written
    answer in the transcript is indistinguishable from a real one, and it would
    be replayed as history on the next question.
    """
    # A first message with no conversation starts one, so the caller never has
    # to create before it can ask. The id is announced on the stream below,
    # because the client needs it to send the second message into the same chat.
    created = False
    if not conversation_id:
        conversation_id = await run_in_threadpool(session.create, user_sub,
                                                  persona or None)
        created = True

    # Locked per conversation, not per user: the read -> answer -> save sequence
    # has to be atomic within one chat, but two of a user's own chats answering
    # at once is fine and is the point of having several.
    async with _lock_for(f"{user_sub}:{conversation_id}"):
        state = await run_in_threadpool(session.get_state, conversation_id, user_sub)
        if state is None:
            yield {"type": "error", "message": "That conversation is not available."}
            return
        yield {"type": "conversation", "conversation_id": conversation_id,
               "created": created}
        # The persona lives on the conversation. One sent with the message wins
        # and is remembered, so switching the picker takes effect on this
        # question and still holds after a reload.
        stored_persona = state.get("persona")
        if persona is not None and (persona or None) != stored_persona:
            await run_in_threadpool(session.set_persona, conversation_id,
                                    user_sub, persona or None)
        elif persona is None:
            persona = _effective_persona(stored_persona)
            if stored_persona and persona is None:
                # A deployment removed or renamed the persisted definition.
                # Heal it when the chat is next used so all later readers see
                # the same General-view state.
                await run_in_threadpool(session.set_persona, conversation_id,
                                        user_sub, None)
        yield {"type": "status", "stage": "retrieving"}
        context, _ = await run_in_threadpool(agent.build_context, message)

        async for event in graph.astream(message, context, state["transcript"],
                                         agent.embed_query, user_sub=user_sub,
                                         persona=persona or None):
            if event.get("type") == "done":
                await run_in_threadpool(
                    session.save_turn, conversation_id, user_sub, message,
                    event["answer"], event["from_data"],
                    event.get("trends") or [],
                    event.get("tool_calls") or [],
                    event.get("persona"))
            yield event


@router.get("/conversations")
async def list_conversations(current_user: dict[str, Any] = Depends(get_current_user)):
    """The caller's chats, newest first. Titles only - transcripts are not read."""
    try:
        rows = await run_in_threadpool(session.list_for_user, current_user["sub"])
    except Exception:
        logger.exception("could not list conversations")
        # A sidebar that will not load must not stop someone asking a question.
        return {"conversations": []}
    return {"conversations": [
        {**row, "persona": _effective_persona(row.get("persona"))}
        for row in rows
    ]}


@router.post("/conversations")
async def new_conversation(current_user: dict[str, Any] = Depends(get_current_user)):
    try:
        conversation_id = await run_in_threadpool(
            session.create, current_user["sub"])
    except Exception:
        logger.exception("could not create conversation")
        raise HTTPException(status_code=500, detail="Could not start a new chat.") from None
    return {"conversation_id": conversation_id, "title": session.DEFAULT_TITLE,
            "messages": 0}


@router.get("/conversations/{conversation_id}")
async def get_conversation(conversation_id: str,
                           current_user: dict[str, Any] = Depends(get_current_user)):
    state = await run_in_threadpool(_owned_or_404, conversation_id,
                                    current_user["sub"])
    return {"conversation_id": conversation_id, "title": state["title"],
            "persona": _effective_persona(state.get("persona")),
            "transcript": state["transcript"],
            "has_history": bool(state["transcript"])}


@router.put("/conversations/{conversation_id}/persona")
async def change_persona(conversation_id: str, body: PersonaChange,
                         current_user: dict[str, Any] = Depends(get_current_user)):
    """The persona is a property of the chat, so it is stored on the chat."""
    persona = _known_persona(body.persona)
    changed = await run_in_threadpool(session.set_persona, conversation_id,
                                      current_user["sub"], persona)
    if not changed:
        raise HTTPException(status_code=404, detail="No such conversation.")
    return {"persona": persona}


@router.delete("/conversations/{conversation_id}")
async def delete_conversation(conversation_id: str,
                              current_user: dict[str, Any] = Depends(get_current_user)):
    removed = await run_in_threadpool(session.delete, conversation_id,
                                      current_user["sub"])
    if not removed:
        raise HTTPException(status_code=404, detail="No such conversation.")
    return {"deleted": True}


@router.post("/chat/stream")
async def chat_stream(body: ChatRequest,
                      current_user: dict[str, Any] = Depends(get_current_user)):
    """The answer, delivered as it is produced."""
    user_sub = current_user["sub"]
    persona = _requested_persona(body.persona)

    async def events():
        try:
            async for event in _run_turn(user_sub, body.message,
                                         conversation_id=body.conversation_id,
                                         persona=persona):
                yield "data: " + json.dumps(event, default=str) + "\n\n"
        except Exception:
            logger.exception("assistant stream failed")
            yield ("data: " + json.dumps({
                "type": "error",
                "message": "The assistant could not answer that question. "
                           "Please try again."}) + "\n\n")

    return StreamingResponse(
        events(),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache, no-transform",
            # Proxies that buffer defeat the point of streaming entirely.
            "X-Accel-Buffering": "no",
            "Connection": "keep-alive",
        },
    )


@router.post("/chat")
async def chat(body: ChatRequest,
               current_user: dict[str, Any] = Depends(get_current_user)):
    """The same answer in one piece, for callers that do not stream.

    Runs the same graph rather than a second implementation: two code paths
    answering the same question is how they drift apart.
    """
    user_sub = current_user["sub"]
    persona = _requested_persona(body.persona)
    try:
        final = None
        conversation_id = body.conversation_id
        async for event in _run_turn(user_sub, body.message,
                                     conversation_id=body.conversation_id,
                                     persona=persona):
            if event.get("type") == "conversation":
                conversation_id = event["conversation_id"]
            elif event.get("type") == "done":
                final = event
    except Exception:
        logger.exception("assistant chat turn failed")
        raise HTTPException(status_code=500,
                            detail="The assistant could not answer that question. "
                                   "Please try again.") from None
    if final is None:
        raise HTTPException(status_code=500,
                            detail="The assistant produced no answer.")
    return {
        "conversation_id": conversation_id,
        "answer": final["answer"],
        "tool_calls": final["tool_calls"],
        "trends": final.get("trends") or [],
        "from_data": final["from_data"],
        "relaxed_filters": final.get("relaxed_filters") or [],
        "persona": final.get("persona"),
    }
