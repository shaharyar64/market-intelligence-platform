import logging
import time
from typing import Callable, TypeVar

logger = logging.getLogger(__name__)
T = TypeVar("T")


class NodeFailed(Exception):
    def __init__(self, node_name: str, reason: str):
        self.node_name = node_name
        self.reason = reason
        super().__init__(f"{node_name} failed: {reason}")


def invoke_with_retry(fn: Callable[[], T], node_name: str, max_attempts: int = 3) -> T:
    last_err = None
    for attempt in range(1, max_attempts + 1):
        try:
            return fn()
        except Exception as e:
            last_err = e
            logger.warning(f"[{node_name}] attempt {attempt}/{max_attempts} failed: {e}")
            if attempt < max_attempts:
                time.sleep(2 ** (attempt - 1))
    raise NodeFailed(node_name, str(last_err))
