"""Opt-in live evaluation of every real-estate consumer persona.

This test calls the configured assistant model and the real retrieval store, so
it is deliberately excluded from ordinary deterministic test runs. Run it with
``RUN_LIVE_PERSONA_TESTS=1 pytest -s .../test_personas_live.py``.
"""
import asyncio
import os
import re

import pytest

from services.trends_real_estate_service.app.assistant import agent, graph, guard
from services.trends_real_estate_service.app.personas import definitions


QUESTION = (
    "What do the posts and trends show about Dubai Creek Harbour for someone "
    "deciding whether it fits their needs?"
)

# These are concepts each lens explicitly prioritises. The answer may say that
# the corpus does not cover them; omission is the failure this catches.
QUALITY_TERMS = {
    "first-time-buyer": ("afford", "value for money", "price", "payment", "cost"),
    "resident-investor": ("yield", "rent", "price", "supply", "tenant", "resale"),
    "international-investor": ("ownership", "regulat", "location", "developer", "investment"),
    "family-home-seeker": ("school", "park", "family", "safety", "community"),
    "young-professional": ("commute", "connect", "amenit", "lifestyle", "value"),
    "luxury-buyer": ("premium", "exclus", "prestige", "reputation", "waterfront"),
}


pytestmark = pytest.mark.skipif(
    os.getenv("RUN_LIVE_PERSONA_TESTS") != "1",
    reason="set RUN_LIVE_PERSONA_TESTS=1 to call the live model and retrieval store",
)


async def _answer(persona_id: str, context: str) -> dict:
    events = [
        event
        async for event in graph.astream(
            QUESTION,
            context,
            [],
            embed_query=agent.embed_query,
            persona=persona_id,
        )
    ]
    assert events and events[-1]["type"] == "done"
    return events[-1]


def test_all_six_personas_live_quality_contract():
    context, context_rows = agent.build_context(QUESTION)
    assert context_rows > 0, "the live retrieval store returned no starting evidence"

    async def run_all():
        # Sequential calls avoid turning a routine quality check into a burst
        # against the production model quota.
        results = []
        for persona in definitions.PERSONAS:
            result = await _answer(persona["persona_id"], context)
            results.append((persona, result))
        return results

    results = asyncio.run(run_all())
    post_queries = []
    answers = []
    failures = []

    # Print the complete evidence set before enforcing the contract. A failure
    # in one persona must not hide the answers already generated for the rest.
    for persona, result in results:
        diagnostic = f"\n--- {persona['name']} ---\n{result['answer'].strip()}\n"
        print(diagnostic.encode("ascii", "backslashreplace").decode("ascii"))

    for persona, result in results:
        persona_id = persona["persona_id"]
        answer = result["answer"].strip()
        answers.append(answer)
        calls = result["tool_calls"]
        queries = [
            str(call.get("args", {}).get("query", "")).lower()
            for call in calls
            if call.get("name") == "search_posts"
        ]
        post_queries.extend(queries)
        print(f"{persona['name']} search_posts queries: {queries}")

        checks = {
            "persona identity": result["persona"] == persona_id,
            "used retrieved data": result["from_data"] is True,
            "answer is substantive": len(answer) >= 300,
            "searched persona-relevant posts": bool(queries),
            "contains source URL": "http" in answer.lower(),
            "has persona opening": bool(re.match(
                rf"^For an? {re.escape(persona['name'])}, the posts show", answer)),
            "ends with coverage gap": "does not cover" in answer.lower()[-600:],
            "no deterministic violations": not guard.find_violations(answer),
            "addresses persona priorities": sum(
                term in answer.lower() for term in QUALITY_TERMS[persona_id]) >= 2,
        }
        failures.extend(
            f"{persona['name']}: {name}" for name, passed in checks.items() if not passed)

    if len(set(answers)) != len(answers):
        failures.append("cross-persona: two personas produced the same answer")
    if len(set(post_queries)) < 4:
        failures.append("cross-persona: fewer than four distinct post queries")
    if failures:
        pytest.fail("Live persona quality failures:\n- " + "\n- ".join(failures))
