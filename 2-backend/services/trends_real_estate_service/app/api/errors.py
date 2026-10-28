"""One place where an unhandled failure becomes a response.

Every router previously did `raise HTTPException(500, detail=str(e))`. That
hands the caller whatever the exception happened to stringify to - for a query
error, the SQL statement, its bound parameters and the schema names; for a
credential failure, the psycopg2 OperationalError carrying the database host,
its IP and the username. None of that belongs in a response body.

The detail a client sees is now fixed and carries only a correlation id. The
diagnosis goes to the log, where the id ties the two together.
"""
import logging
import uuid

from fastapi import HTTPException

logger = logging.getLogger("api.errors")


def internal_error(operation: str) -> HTTPException:
    """Log the exception being handled and return the HTTPException to raise.

    Call this from inside an `except` block - it relies on there being a live
    exception for `logger.exception` to capture.
    """
    ref = uuid.uuid4().hex[:12]
    logger.exception("%s failed [ref=%s]", operation, ref)
    return HTTPException(status_code=500, detail=f"Internal server error (ref {ref})")
