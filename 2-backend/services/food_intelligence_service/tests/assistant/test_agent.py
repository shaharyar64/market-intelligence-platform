import json
from unittest.mock import patch

import pytest


def test_truncate_payload_stays_parseable_and_records_omitted_count():
    from services.food_intelligence_service.app.assistant import agent
    big_item = {"trend_id": "t1", "name": "x" * 500, "likes": 1234}
    result = {"ok": True, "data": [dict(big_item, i=i) for i in range(100)],
              "count": 100, "message": ""}
    serialized = agent._truncate_payload(result, limit=2000)
    assert len(serialized) <= 2000 or len(serialized) < len(
        json.dumps(result, default=str))
    parsed = json.loads(serialized)
    assert parsed["truncated_items"] > 0
    assert parsed["count"] == len(parsed["data"])
    assert parsed["count"] + parsed["truncated_items"] == 100
    # No value straddles the cut: every retained item is a complete dict
    # with its likes value intact, never a severed number.
    for item in parsed["data"]:
        assert item["likes"] == 1234


def test_truncate_payload_leaves_small_payloads_untouched():
    from services.food_intelligence_service.app.assistant import agent
    result = {"ok": True, "data": [{"name": "Mandi"}], "count": 1, "message": ""}
    serialized = agent._truncate_payload(result)
    parsed = json.loads(serialized)
    assert "truncated_items" not in parsed
    assert parsed == result


def test_truncate_payload_handles_non_list_data_without_corrupting_json():
    from services.food_intelligence_service.app.assistant import agent
    result = {"ok": True, "data": {"blob": "x" * 30000}, "count": 1, "message": ""}
    serialized = agent._truncate_payload(result, limit=2000)
    # Cannot drop elements from a non-list payload; must still be valid JSON.
    parsed = json.loads(serialized)
    assert parsed["data"]["blob"]


def test_route_session_lock_lru_evicts_oldest_past_the_cap():
    from services.food_intelligence_service.app.api.v1 import assistant as assistant_route
    original_locks = assistant_route._session_locks
    assistant_route._session_locks = type(original_locks)()
    try:
        cap = assistant_route.MAX_SESSIONS
        for i in range(cap):
            assistant_route._lock_for(f"lockuser:{i}")
        assert len(assistant_route._session_locks) == cap
        assistant_route._lock_for("lockuser:new")
        assert len(assistant_route._session_locks) == cap
        assert "lockuser:0" not in assistant_route._session_locks
        assert "lockuser:new" in assistant_route._session_locks
    finally:
        assistant_route._session_locks = original_locks


def test_route_returns_generic_500_detail_without_exception_text():
    import asyncio
    from services.food_intelligence_service.app.api.v1 import assistant as assistant_route
    from fastapi import HTTPException

    body = assistant_route.ChatRequest(message="hi", session_id="err-sess")
    current_user = {"sub": "err-user", "username": "err-user"}
    async def boom(*a, **k):
        raise RuntimeError("column posts.secret_col missing")
        yield  # pragma: no cover - makes this an async generator

    with patch.object(assistant_route.graph, "astream", boom):
        with pytest.raises(HTTPException) as exc_info:
            asyncio.run(assistant_route.chat(body, current_user=current_user))
    assert exc_info.value.status_code == 500
    assert "secret_col" not in exc_info.value.detail
