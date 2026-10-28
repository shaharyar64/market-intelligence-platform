"""The assistant as a LangGraph agent.

The enrichment pipeline has been a LangGraph graph since it was written; the
assistant was not - it ran a tool-calling loop written by hand against the raw
OpenAI Responses API. Two agent frameworks in one service is one too many, and
the hand-written loop had to reimplement what the framework already does: the
call-and-feed-back cycle, a budget on tool calls, token streaming, and reporting
which tools ran.

What this keeps deliberately unchanged is the event contract. The route, the
gateway and the browser all speak `status` / `tool` / `delta` / `done`, so the
graph is mapped onto those rather than the wire format changing underneath a
working client.

Conversation memory moves with it. The Responses API kept the thread on OpenAI's
side and we stored a pointer to it; a graph carries its own messages, so the
transcript we already keep in Postgres is replayed instead. That costs tokens on
every turn, which is why only the recent turns are sent - but it makes the
conversation ours rather than a handle into someone else's store.
"""
import logging

from langchain_core.callbacks import UsageMetadataCallbackHandler
from langchain_core.messages import AIMessage, HumanMessage, SystemMessage
from langchain_core.tools import StructuredTool
from langchain_openai import ChatOpenAI
from langgraph.prebuilt import create_react_agent

from services.food_intelligence_service.app.assistant import prompts, toolargs, tools as tool_impl
from services.food_intelligence_service.app.assistant.agent import _truncate_payload
from services.food_intelligence_service.app.core.config import get_settings
from services.food_intelligence_service.app.idea_testing.usage import chat_usage

logger = logging.getLogger("assistant.graph")

# Tool calls the agent may make for one question. LangGraph counts graph steps
# rather than tool calls, and one call costs two steps (the model turn that asks
# for it, and the tool turn that answers), plus the final model turn.
MAX_TOOL_CALLS = 6
RECURSION_LIMIT = MAX_TOOL_CALLS * 2 + 2

# Turns of prior conversation replayed into the graph. The whole transcript is
# kept for the UI, but sending all of it would grow the prompt without bound.
HISTORY_TURNS = 8


def build_tools(embed_query, user_sub: str | None, seen: dict, calls: list,
                context_ledger: set | None = None):
    """Wrap the existing dispatch as LangChain tools.

    The tool bodies are not reimplemented - `tools.dispatch` stays the single
    place a tool is executed. What the wrapper adds is bookkeeping: the raw
    result carries `ok` and `count`, which the UI shows and which LangGraph
    would otherwise flatten into a string by the time the stream sees it.

    Arguments are validated by the pydantic models in toolargs. A raw JSON
    schema is advertised to the model but never enforced - measured, both an
    invalid quadrant and a `limit` of "twelve" reached the tool body, and the
    second would have arrived at SQL as a string. With a model, LangChain
    rejects the call and the agent gets the error back and can correct itself.
    """
    built = []

    def _make_run(tool_name: str):
        """Capture the tool's name in a closure, not a default argument.

        `def _run(name=tool_name, **kwargs)` looks equivalent and is not: any
        tool with an argument of its own called `name` overwrites it. create_trend
        has exactly that - an optional display name - so passing one dispatched
        under the trend's name instead of the tool's, hit "unknown tool", and
        the assistant reported "not enough data to build a trend" for topics
        with plenty. It never once created a trend when asked with a name.
        """
        def _run(**kwargs):
            # Unset optional arguments arrive as None. dispatch reads them as
            # args.get("level", "micro"), which returns None when the key is
            # present and empty - so an explicit None overrode the default.
            kwargs = {k: v for k, v in kwargs.items() if v is not None}
            result = tool_impl.dispatch(tool_name, kwargs, embed_query, user_sub=user_sub,
                                        context_ledger=context_ledger)
            # A relaxed filter is a fact about what was run, so it travels with
            # ok and count rather than only inside the message handed to the
            # model. Left as prose it is the model's choice whether to mention
            # it, and a run that omits the sentence presents whole-market
            # results under a pinned segment with nothing to show otherwise.
            calls.append({"name": tool_name, "args": kwargs,
                          "ok": result["ok"], "count": result["count"],
                          "relaxed_filters": result.get("relaxed_filters") or []})
            _collect_trends(result, seen)
            # Truncated by element, never by character: cutting the JSON at a
            # fixed length can sever a string mid-token.
            return _truncate_payload(result)
        return _run

    for name, (args_model, description) in toolargs.TOOL_ARGS.items():
        _run = _make_run(name)
        built.append(StructuredTool.from_function(
            func=_run, name=name, description=description, args_schema=args_model))
    return built


def _collect_trends(result: dict, into: dict) -> None:
    data = result.get("data")
    rows = data if isinstance(data, list) else [data]
    for row in rows:
        if isinstance(row, dict) and row.get("trend_id") and row.get("name"):
            into.setdefault(row["trend_id"], row["name"])


def _history_messages(transcript: list[dict]) -> list:
    """Replay recent turns as graph messages."""
    messages = []
    for entry in (transcript or [])[-HISTORY_TURNS * 2:]:
        text = entry.get("text") or ""
        if not text:
            continue
        if entry.get("role") == "user":
            messages.append(HumanMessage(content=text))
        else:
            # "bot" is the old name for this role; transcripts written before
            # the rename are still on disk and in browsers' local storage.
            messages.append(AIMessage(content=text))
    return messages


def build_agent(embed_query, user_sub: str | None, seen: dict, calls: list,
                context_ledger: set | None = None):
    settings = get_settings()
    model = ChatOpenAI(model=settings.ASSISTANT_MODEL, temperature=0,
                       api_key=settings.OPENAI_API_KEY, streaming=True, stream_usage=True)
    return create_react_agent(
        model=model,
        tools=build_tools(embed_query, user_sub, seen, calls, context_ledger),
        prompt=prompts.SYSTEM_PROMPT,
    )


def _persona_instruction(persona: str | None) -> tuple[str, str] | None:
    """What a pinned persona means for this turn.

    Stated as an instruction rather than injected as a tool argument, because
    not every question the user asks while a persona is pinned is about that
    persona - "how many trends are there in total" is not - and hard-wiring the
    filter would answer a question about everything with a slice of it.

    The interpretive half lives in personas/context.py and never reaches the
    embedding path, so enriching it cannot move a persona's membership.
    """
    if not persona:
        return None
    from services.food_intelligence_service.app.personas import store as pstore
    from services.food_intelligence_service.app.personas import context as pcontext
    found = pstore.resolve(persona)
    if not found:
        return None
    return pcontext.build(found["name"], found["persona_id"]), found["persona_id"]


async def astream(question: str, context: str, transcript: list[dict],
                  embed_query, user_sub: str | None = None,
                  persona: str | None = None):
    """Run one question through the graph, emitting the route's event shape.

    LangGraph's own event names are not exposed to the browser: the client and
    the gateway already speak a small vocabulary, and translating here keeps the
    framework an implementation detail rather than something a UI change has to
    follow.
    """
    seen: dict[str, str] = {}
    calls: list[dict] = []
    # Persona ids whose interpretive block has already reached the model this
    # turn. Pinning seeds it below, so get_persona does not repeat ~800 tokens
    # the system message already carries.
    context_ledger: set[str] = set()
    agent = build_agent(embed_query, user_sub, seen, calls, context_ledger)

    messages = []
    if context:
        messages.append(SystemMessage(content=context))
    pinned = _persona_instruction(persona)
    if pinned:
        pinned_text, pinned_id = pinned
        messages.append(SystemMessage(content=pinned_text))
        context_ledger.add(pinned_id)
    messages += _history_messages(transcript)
    messages.append(HumanMessage(content=question))

    answer = ""
    reported = 0
    # Passed in config, not via get_usage_metadata_callback(): this is an async
    # generator, and a context manager held across its yields leaks its context.
    usage_handler = UsageMetadataCallbackHandler()
    yield {"type": "status", "stage": "thinking"}

    async for event in agent.astream_events(
        {"messages": messages},
        config={"recursion_limit": RECURSION_LIMIT, "callbacks": [usage_handler]},
        version="v2",
    ):
        kind = event.get("event")
        if kind == "on_chat_model_stream":
            chunk = event["data"].get("chunk")
            text = getattr(chunk, "content", "") or ""
            if isinstance(text, list):
                text = "".join(part.get("text", "") for part in text
                               if isinstance(part, dict))
            if text:
                answer += text
                yield {"type": "delta", "text": text}
        elif kind == "on_tool_start":
            yield {"type": "status", "stage": "tool", "name": event.get("name")}
        elif kind == "on_tool_end":
            # The wrapper recorded ok and count before LangGraph stringified the
            # result; report whichever calls have completed since the last event.
            while reported < len(calls):
                done = calls[reported]
                reported += 1
                yield {"type": "tool", "name": done["name"],
                       "ok": done["ok"], "count": done["count"]}
            answer = ""   # text produced while deciding on a tool is not the answer

    relaxed = sorted({f for c in calls for f in (c.get("relaxed_filters") or [])})
    yield {"type": "done",
           "answer": answer,
           "tool_calls": calls,
           "relaxed_filters": relaxed,
           # Whether the pinned segment actually reached a lookup. The chip
           # under the box claimed it had, on every turn, including the ones
           # that quietly widened to the whole market.
           "persona_applied": any(
               c.get("args", {}).get("persona") and not (c.get("relaxed_filters") or [])
               for c in calls) if persona else None,
           "trends": [{"trend_id": tid, "name": name} for tid, name in seen.items()],
           # True when at least one tool returned something. An answer without
           # it came from the model rather than our data.
           "from_data": any(c.get("ok") for c in calls),
           "usage": chat_usage(usage_handler.usage_metadata)}
