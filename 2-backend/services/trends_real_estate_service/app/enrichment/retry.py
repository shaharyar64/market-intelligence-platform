import logging
import random
import time
from collections.abc import Callable
from typing import TypeVar

from openai import (
    APIConnectionError,
    APITimeoutError,
    InternalServerError,
    RateLimitError,
)

logger = logging.getLogger(__name__)
T = TypeVar("T")


class NodeFailed(Exception):
    def __init__(self, node_name: str, reason: str):
        self.node_name = node_name
        self.reason = reason
        super().__init__(f"{node_name} failed: {reason}")


# Retrying these is worth the wait: they are about the connection or the rate
# limit, not about the request. Everything else - a validation error, a refusal,
# a bad key - will fail again identically, and paying 3x for that is how a run
# turns a broken prompt into three times the bill.
RETRYABLE = (RateLimitError, APITimeoutError, APIConnectionError, InternalServerError)


def _retry_after(exc: Exception) -> float | None:
    """The server's own backoff hint, when it sends one."""
    response = getattr(exc, "response", None)
    header = getattr(response, "headers", {}) or {}
    try:
        value = header.get("retry-after") or header.get("Retry-After")
        return float(value) if value else None
    except (TypeError, ValueError):
        return None


def invoke_with_retry(fn: Callable[[], T], node_name: str, max_attempts: int = 3) -> T:
    last_err: Exception | None = None
    for attempt in range(1, max_attempts + 1):
        try:
            return fn()
        except Exception as e:
            last_err = e
            if not isinstance(e, RETRYABLE):
                logger.warning(f"[{node_name}] failed and is not retryable: {e}")
                raise NodeFailed(node_name, str(e)) from e
            logger.warning(f"[{node_name}] attempt {attempt}/{max_attempts} failed: {e}")
            if attempt < max_attempts:
                # Jitter, because six workers backing off in lockstep re-collide
                # on the same second and re-trigger the limit they are waiting out.
                wait = _retry_after(e) or 2 ** (attempt - 1)
                time.sleep(wait + random.uniform(0, 0.5))  # noqa: S311 - backoff jitter, not crypto
    raise NodeFailed(node_name, str(last_err))
