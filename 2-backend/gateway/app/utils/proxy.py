import httpx
from fastapi import Request, Response
from fastapi.responses import StreamingResponse
from starlette.requests import ClientDisconnect
from gateway.app.core.config import get_settings

settings = get_settings()


HOP_BY_HOP_HEADERS = {
    "connection",
    "keep-alive",
    "proxy-authenticate",
    "proxy-authorization",
    "te",
    "trailers",
    "transfer-encoding",
    "upgrade",
}


async def forward_request(
    *,
    service_url: str,
    path: str,
    request: Request,
) -> Response:
    """Forward an incoming request to a downstream service.

    The response is relayed as it arrives rather than read into memory first.
    That matters for anything the caller consumes progressively: the assistant
    answers over server-sent events, and buffering the whole body here delivered
    every event in one burst at the end - the browser saw no progress, then a
    finished answer, which is exactly what streaming exists to avoid. It also
    keeps a large download from sitting in the gateway's memory.
    """

    url = f"{service_url.rstrip('/')}/{path}"

    headers = {
        key: value
        for key, value in request.headers.items()
        if key.lower() not in HOP_BY_HOP_HEADERS
    }

    try:
        body = await request.body()
    except ClientDisconnect:
        return Response(status_code=499)

    # The client must outlive this function: it owns the socket the response is
    # still being read from. It is closed by the iterator below, in a finally so
    # a client that disconnects mid-stream cannot leak it.
    client = httpx.AsyncClient(timeout=settings.REQUEST_TIMEOUT)
    try:
        upstream_request = client.build_request(
            method=request.method,
            url=url,
            params=list(request.query_params.multi_items()),
            headers=headers,
            content=body,
        )
        upstream_response = await client.send(
            upstream_request, stream=True, follow_redirects=False
        )
    except httpx.RequestError as exc:
        await client.aclose()
        return Response(
            content=f"Upstream service unreachable: {exc}",
            status_code=502,
        )

    response_headers = {
        key: value
        for key, value in upstream_response.headers.items()
        if key.lower() not in HOP_BY_HOP_HEADERS
    }

    async def relay():
        try:
            # Raw bytes: the upstream's content-encoding header is forwarded
            # untouched, so the payload must stay in the encoding it describes.
            async for chunk in upstream_response.aiter_raw():
                yield chunk
        finally:
            await upstream_response.aclose()
            await client.aclose()

    return StreamingResponse(
        relay(),
        status_code=upstream_response.status_code,
        headers=response_headers,
        media_type=upstream_response.headers.get("content-type"),
    )
