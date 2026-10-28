"""The proxy must relay a response as it arrives, not read it whole first.

The assistant answers over server-sent events. While this buffered, every event
reached the browser in one burst at the end: no progress indicator, no partial
answer, just a wait and then a finished reply. These tests pin the behaviour so
it cannot quietly regress to `content=response.content`.
"""
import asyncio

import httpx
import pytest
from fastapi.responses import StreamingResponse
from starlette.datastructures import Headers

from gateway.app.utils import proxy


class _FakeRequest:
    """The parts of starlette's Request that forward_request touches."""

    def __init__(self, method="POST", body=b"{}", headers=None):
        self.method = method
        self._body = body
        self.headers = Headers(headers or {"content-type": "application/json"})
        self.query_params = httpx.QueryParams()

    async def body(self):
        return self._body


class _FakeUpstream:
    def __init__(self, chunks, status_code=200, headers=None):
        self._chunks = chunks
        self.status_code = status_code
        self.headers = Headers(headers or {"content-type": "text/event-stream"})
        self.closed = False

    async def aiter_raw(self):
        for chunk in self._chunks:
            yield chunk

    async def aclose(self):
        self.closed = True


@pytest.fixture
def sse_upstream(monkeypatch):
    upstream = _FakeUpstream([
        b'data: {"type":"status"}\n\n',
        b'data: {"type":"delta","text":"He"}\n\n',
        b'data: {"type":"delta","text":"llo"}\n\n',
        b'data: {"type":"done"}\n\n',
    ])
    closed = {"client": False}

    async def fake_send(self, request, stream=False, follow_redirects=False):
        assert stream is True, "the proxy must ask for a streaming response"
        return upstream

    async def fake_aclose(self):
        closed["client"] = True

    monkeypatch.setattr(httpx.AsyncClient, "send", fake_send)
    monkeypatch.setattr(httpx.AsyncClient, "aclose", fake_aclose)
    return upstream, closed


def _forward(path="assistant/chat/stream"):
    return proxy.forward_request(
        service_url="http://svc", path=path, request=_FakeRequest())


def test_response_is_streamed_not_buffered(sse_upstream):
    async def run():
        response = await _forward()
        assert isinstance(response, StreamingResponse)
        return [chunk async for chunk in response.body_iterator]

    seen = asyncio.run(run())
    assert len(seen) == 4, "each event should arrive as its own chunk"
    assert b"delta" in seen[1]


def test_sockets_are_released_once_the_stream_ends(sse_upstream):
    """The client outlives the function that made it, so something has to close
    it — a leak here exhausts the gateway's connections under load."""
    upstream, closed = sse_upstream

    async def run():
        response = await _forward()
        async for _ in response.body_iterator:
            pass

    asyncio.run(run())
    assert upstream.closed is True
    assert closed["client"] is True


def test_content_type_survives_the_hop(sse_upstream):
    """A browser only treats the body as events if it arrives as text/event-stream."""
    response = asyncio.run(_forward())
    assert response.media_type == "text/event-stream"


def test_unreachable_upstream_still_reports_502(monkeypatch):
    async def boom(self, request, stream=False, follow_redirects=False):
        raise httpx.ConnectError("refused")

    closed = {"client": False}

    async def fake_aclose(self):
        closed["client"] = True

    monkeypatch.setattr(httpx.AsyncClient, "send", boom)
    monkeypatch.setattr(httpx.AsyncClient, "aclose", fake_aclose)

    response = asyncio.run(_forward(path="whatever"))
    assert response.status_code == 502
    assert closed["client"] is True, "a failed request must not leak its client"
