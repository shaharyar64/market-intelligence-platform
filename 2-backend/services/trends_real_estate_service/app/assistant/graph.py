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
import asyncio
import json
import logging
import re
import time

from langchain_core.messages import AIMessage, HumanMessage, SystemMessage
from langchain_core.tools import StructuredTool
from langchain_openai import ChatOpenAI
from langgraph.prebuilt import create_react_agent

from services.trends_real_estate_service.app.assistant import guard, intent, prompts, toolargs
from services.trends_real_estate_service.app.assistant import tools as tool_impl
from services.trends_real_estate_service.app.assistant.agent import _truncate_payload
from services.trends_real_estate_service.app.core.config import get_settings
from services.trends_real_estate_service.app.personas import definitions as personas

logger = logging.getLogger("assistant.graph")

# Tool calls the agent may make for one question. LangGraph counts graph steps
# rather than tool calls, and one call costs two steps (the model turn that asks
# for it, and the tool turn that answers), plus the final model turn.
MAX_TOOL_CALLS = 6
RECURSION_LIMIT = MAX_TOOL_CALLS * 2 + 2

# Turns of prior conversation replayed into the graph. The whole transcript is
# kept for the UI, but sending all of it would grow the prompt without bound.
HISTORY_TURNS = 8

_PLAIN_DATA_QUESTION = re.compile(
    r"\b(?:how\s+many|count|coverage|what\s+data|which\s+trends|list\s+(?:the\s+)?trends|"
    r"top\s+trends|breaking\s+out|growth\s+index|volume\s+index)\b", re.I)
_PROPERTY_SUBJECT = re.compile(
    r"\b(?:propert(?:y|ies)|projects?|developers?|communities|community|areas?|locations?|"
    r"harbou?r|homes?|apartments?|villas?|residences?|real\s+estate|invest(?:or|ment)?)\b",
    re.I)
_COMPARISON = re.compile(
    r"\bvs\.?\b|\bversus\b|\bcompar(?:e|es|ed|ing|ison)\b|\bbetween\b.*\band\b|"
    r"\bwhich\s+(?:one|of\s+(?:the\s+)?two)\b|\b(?:better|worse)\s+than\b", re.I)


def _is_property_record_question(question: str) -> bool:
    """Whether a persona question should use the exact-record composer."""
    return (not _PLAIN_DATA_QUESTION.search(question or "")
            and not _COMPARISON.search(question or "")
            and bool(_PROPERTY_SUBJECT.search(question or "")))


TRACE_TOP = 8


def _call_key(name: str, args: dict) -> str:
    return name + json.dumps(args or {}, sort_keys=True, ensure_ascii=False).lower()


def _top_names(result: dict) -> list[str]:
    data = result.get("data")
    rows = data if isinstance(data, list) else [data]
    names = []
    for row in rows:
        if isinstance(row, dict):
            label = (row.get("name") or row.get("developer") or row.get("brand_name")
                     or row.get("author_username"))
            if label and label not in names:
                names.append(str(label))
    return names[:TRACE_TOP]


def _trend_ids(result: dict) -> dict[str, str]:
    data = result.get("data")
    rows = data if isinstance(data, list) else [data]
    ids = {}
    for row in rows:
        if isinstance(row, dict) and row.get("trend_id") and row.get("name"):
            ids.setdefault(str(row["name"]), str(row["trend_id"]))
    return dict(list(ids.items())[:TRACE_TOP])


def build_tools(embed_query, user_sub: str | None, seen: dict, calls: list,
                context_ledger: set | None = None, evidence: list | None = None,
                refused: set | None = None, shown: set | None = None):
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
            if refused and _call_key(tool_name, kwargs) in refused:
                return json.dumps({
                    "ok": False, "count": 0, "data": [], "refused": True,
                    "message": "Refused: this exact call produced the answer the user just "
                               "rejected. Use different terms or a different tool."})
            result = tool_impl.dispatch(tool_name, kwargs, embed_query, user_sub=user_sub,
                                        context_ledger=context_ledger)
            if shown:
                _mark_shown(result, shown)
            # A relaxed filter is a fact about what was run, so it travels with
            # ok and count rather than only inside the message handed to the
            # model. Left as prose it is the model's choice whether to mention
            # it, and a run that omits the sentence presents whole-market
            # results under a pinned segment with nothing to show otherwise.
            calls.append({"name": tool_name, "args": kwargs,
                          "ok": result["ok"], "count": result["count"],
                          "top": _top_names(result),
                          "ids": _trend_ids(result),
                          "weak_match": bool(result.get("weak_match")),
                          "relaxed_filters": result.get("relaxed_filters") or []})
            _collect_trends(result, seen)
            # Truncated by element, never by character: cutting the JSON at a
            # fixed length can sever a string mid-token.
            payload = _truncate_payload(result)
            if evidence is not None:
                evidence.append(payload)
            return payload
        return _run

    for name, (args_model, description) in toolargs.TOOL_ARGS.items():
        _run = _make_run(name)
        built.append(StructuredTool.from_function(
            func=_run, name=name, description=description, args_schema=args_model))
    return built


def _collect_trends(result: dict, into: dict) -> None:
    """Remember each trend a tool returned, with the market its run covers, so
    the page can link a trend to the run it lives in (?market=SA)."""
    data = result.get("data")
    rows = data if isinstance(data, list) else [data]
    for row in rows:
        if isinstance(row, dict) and row.get("trend_id") and row.get("name"):
            into.setdefault(row["trend_id"], {"name": row["name"],
                                              "country": row.get("country")})


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
            trace = intent.trace_text(entry.get("tool_calls") or [])
            if trace:
                messages.append(SystemMessage(
                    content=f"Tool calls behind the answer above: {trace}"))
    return messages


def _mark_shown(result: dict, shown: set[str]) -> None:
    data = result.get("data")
    rows = data if isinstance(data, list) else [data]
    hits = []
    for row in rows:
        if not isinstance(row, dict):
            continue
        label = row.get("name") or row.get("developer") or row.get("post_url")
        if (label and str(label).lower() in shown) or \
                str(row.get("post_url") or "").lower() in shown:
            row["previously_shown"] = True
            hits.append(str(label))
    if hits:
        result["message"] = ((result.get("message") or "") + " " + (
            f"{', '.join(hits)} were in the answer the user just rejected (previously_shown). "
            "Do not lead with them. Lead with what is new; mention them only after that, "
            "saying why they still matter, or leave them out.")).strip()


SHOWN_TURNS = 3


def _previous_names(transcript: list[dict], plan: intent.QueryPlan | None) -> set[str]:
    names = {n.lower() for n in (plan.rejected_items if plan else [])}
    answers = [e for e in (transcript or []) if e.get("role") != "user"][-SHOWN_TURNS:]
    for entry in answers:
        for c in entry.get("tool_calls") or []:
            names |= {str(n).lower() for n in c.get("top") or []}
        names |= {str(t.get("name")).lower() for t in entry.get("trends") or []
                  if t.get("name")}
        names |= {u.lower() for u in guard._URL.findall(entry.get("text") or "")}
    names.discard("")
    return names


def _nothing_new(answer: str, transcript: list[dict]) -> bool:
    seen_urls = {u for text in _recent_answers(transcript) for u in guard._URL.findall(text)}
    return not set(guard._URL.findall(answer)) - seen_urls


RETRY_AFTER_REPEAT = (
    "The answer above repeats what you already told the user, who has rejected it. "
    "Do not send it. Run different searches from the ones already made this turn and "
    "earlier (repeating them is refused): the plan's expanded terms with search_posts, "
    "developers_by_topic or create_trend. Then answer with what is new. If the data has "
    "nothing new on this, say so plainly in two or three sentences, name what you "
    "searched, and stop.")


def _recent_answers(transcript: list[dict]) -> list[str]:
    return [e.get("text") or "" for e in (transcript or [])
            if e.get("role") != "user"][-SHOWN_TURNS:]


def _previous_answer(transcript: list[dict]) -> str:
    for entry in reversed(transcript or []):
        if entry.get("role") != "user":
            return entry.get("text") or ""
    return ""


def _previous_calls(transcript: list[dict]) -> set[str]:
    for entry in reversed(transcript or []):
        if entry.get("role") != "user":
            return {_call_key(c["name"], c.get("args") or {})
                    for c in entry.get("tool_calls") or []
                    if c.get("name") and "args" in c}
    return set()


def build_agent(embed_query, user_sub: str | None, seen: dict, calls: list,
                context_ledger: set | None = None, evidence: list | None = None,
                refused: set | None = None, shown: set | None = None):
    settings = get_settings()
    model = ChatOpenAI(model=settings.ASSISTANT_MODEL,
                       temperature=settings.ASSISTANT_TEMPERATURE,
                       api_key=settings.OPENAI_API_KEY, streaming=True)
    return create_react_agent(
        model=model,
        tools=build_tools(embed_query, user_sub, seen, calls, context_ledger, evidence,
                          refused, shown),
        prompt=prompts.SYSTEM_PROMPT,
    )


async def astream(question: str, context: str, transcript: list[dict],
                  embed_query, user_sub: str | None = None,
                  persona: str | None = None):
    """Run one question through the graph, emitting the route's event shape.

    LangGraph's own event names are not exposed to the browser: the client and
    the gateway already speak a small vocabulary, and translating here keeps the
    framework an implementation detail rather than something a UI change has to
    follow.

    A persona arrives as one more system message ahead of the question - the
    whole of how it works. The tools, their arguments and the data they read
    are the same with or without it.
    """
    seen: dict[str, dict] = {}
    calls: list[dict] = []
    # Context blocks already sent to the model this turn, so one turn pays
    # for each of them once however often the agent reaches for it.
    context_ledger: set[str] = set()
    # Every tool result this turn, as text: what the answer guard checks a
    # quotation against.
    evidence: list[str] = []
    persona_prefetch: dict | None = None

    lens = personas.instruction(persona)
    persona_definition = personas.get(persona)
    yield {"type": "status", "stage": "thinking"}
    plan = await asyncio.to_thread(intent.classify, question, transcript)
    property_question = _is_property_record_question(question) and (
        plan is None or plan.intent == "property_evaluation")
    correcting = bool(plan and plan.is_correction)
    refused = _previous_calls(transcript) if correcting else set()
    shown = _previous_names(transcript, plan) if correcting else set()

    # A persona must affect which records are considered, not merely the prose
    # written after retrieval. This is one deterministic corpus-wide semantic
    # lookup built only from the approved priorities. It applies no persona
    # filter, and the normal toolset remains available for counter-evidence.
    if lens and callable(embed_query):
        query = personas.priority_query(persona, question)
        yield {"type": "status", "stage": "tool", "name": "search_posts"}
        result = None
        for attempt in range(2):
            result = await asyncio.to_thread(
                tool_impl.dispatch,
                "search_posts",
                {"query": query, "limit": 10},
                embed_query,
                user_sub=user_sub,
                context_ledger=context_ledger,
            )
            if result["ok"]:
                break
            if attempt == 0:
                logger.warning("persona priority prefetch failed; retrying once")
        persona_prefetch = result
        call = {"name": "search_posts", "args": {"query": query, "limit": 10},
                "ok": result["ok"], "count": result["count"],
                "relaxed_filters": result.get("relaxed_filters") or []}
        calls.append(call)
        _collect_trends(result, seen)
        payload = _truncate_payload(result)
        if result["ok"]:
            context = "\n\n".join(filter(None, [
                context,
                "PERSONA-PRIORITY POSTS (deterministic corpus-wide retrieval):\n" + payload,
            ]))
        evidence.append(payload)
        yield {"type": "tool", "name": "search_posts",
               "ok": result["ok"], "count": result["count"]}

    # Property evaluation is the path where persona relevance matters and
    # where free-form synthesis repeatedly introduced unsupported conclusions.
    # Once its deterministic records exist, compose and return without paying
    # for a model-authored factual answer. Catalogue/count questions and
    # out-of-domain prompts continue through the normal agent below.
    if (lens and persona_prefetch and persona_prefetch.get("ok")
            and property_question):
        yield {"type": "status", "stage": "writing"}
        answer, report = guard.compose_persona_answer(
            persona_definition, persona_prefetch)
        yield {"type": "status", "stage": "checking"}
        yield {"type": "delta", "text": answer}
        relaxed = sorted({f for c in calls for f in (c.get("relaxed_filters") or [])})
        yield {"type": "done", "answer": answer, "tool_calls": calls,
               "relaxed_filters": relaxed, "trends": [], "persona": persona,
               "guard": report, "from_data": True}
        return

    agent = build_agent(embed_query, user_sub, seen, calls, context_ledger, evidence,
                        refused, shown)

    messages = []
    if context:
        messages.append(SystemMessage(content=context))
    messages += _history_messages(transcript)
    planned = intent.plan_message(plan)
    if planned:
        messages.append(SystemMessage(content=planned))
    # Directly ahead of the question rather than ahead of the history: the
    # persona is about this answer, and placed before a long replayed history
    # its closing rules were the first thing the model let go of.
    if lens:
        messages.append(SystemMessage(content=lens))
    messages.append(HumanMessage(content=question))

    answer = ""
    reported = len(calls)
    held = True
    for attempt in range(2):
        answer = ""
        writing_announced = False
        async for event in agent.astream_events(
            {"messages": messages},
            config={"recursion_limit": RECURSION_LIMIT},
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
                    if not held:
                        yield {"type": "delta", "text": text}
                    elif not writing_announced:
                        writing_announced = True
                        yield {"type": "status", "stage": "writing"}
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
                writing_announced = False
        if (attempt or lens or not correcting or not answer.strip()
                or not (_nothing_new(answer, transcript)
                        or any(guard.is_repeat(answer, p) for p in _recent_answers(transcript)))):
            break
        refused.update(_call_key(c["name"], c.get("args") or {}) for c in calls)
        messages += [AIMessage(content=answer), SystemMessage(content=RETRY_AFTER_REPEAT)]
        yield {"type": "status", "stage": "thinking"}

    report = None
    if not lens and answer.strip():
        yield {"type": "status", "stage": "checking"}
        previous = _previous_answer(transcript)
        if not correcting and guard.is_repeat(answer, previous):
            answer = await asyncio.to_thread(
                guard.answer_without_repeating, answer, question=question, previous=previous)
        answer, report = await asyncio.to_thread(
            guard.verify_general_answer, answer, question=question,
            topic=plan.topic if plan else None,
            sources=guard.bounded_evidence(
                "TOOL CALLS MADE THIS TURN: " + (intent.trace_text(calls) or "none"),
                [context, *evidence]))
        logger.info("general answer grounding status=%s removed=%d",
                    report["status"], len(report.get("removed") or []))
        yield {"type": "delta", "text": answer}
    elif lens:
        yield {"type": "status", "stage": "checking"}
        source_text = guard.bounded_evidence(context, evidence)
        started = time.perf_counter()
        article = "an" if persona_definition["name"][0].lower() in "aeiou" else "a"
        property_opening = f"For {article} {persona_definition['name']}, the posts show"
        answer, report = await asyncio.to_thread(
            guard.verify_persona_answer,
            answer,
            question=question,
            persona=persona_definition,
            sources=source_text,
            require_persona_format=answer.strip().startswith(property_opening),
        )
        logger.info(
            "persona answer verification status=%s violations=%d duration_ms=%.0f",
            report["status"], len(report.get("violations") or []),
            (time.perf_counter() - started) * 1000)
        if answer:
            yield {"type": "delta", "text": answer}

    relaxed = sorted({f for c in calls for f in (c.get("relaxed_filters") or [])})
    yield {"type": "done",
           "answer": answer,
           "tool_calls": calls,
           "relaxed_filters": relaxed,
           "trends": [{"trend_id": tid, "name": ref["name"], "country": ref["country"]}
                      for tid, ref in seen.items()],
           "plan": plan.model_dump() if plan else None,
           # The persona this answer was written for, or None for the general
           # view. An id nobody defines any more was never applied, so it is
           # reported as None rather than echoed back.
           "persona": persona if lens else None,
           # What the answer guard found and did; None when it did not run.
           "guard": report,
           # True when at least one tool returned something. An answer without
           # it came from the model rather than our data.
           "from_data": any(c.get("ok") for c in calls)}
