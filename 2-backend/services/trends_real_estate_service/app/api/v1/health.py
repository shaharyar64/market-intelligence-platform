"""Liveness plus a real dependency probe.

A static {"status":"ok"} is what the container healthcheck and the gateway's
/services/health both read. Returning it unconditionally meant a service that
could not reach Postgres booted, reported Healthy, was never restarted, and
500ed on every data route.
"""
import logging

from fastapi import APIRouter
from fastapi.concurrency import run_in_threadpool

from services.trends_real_estate_service.app.db import analysis_store

logger = logging.getLogger(__name__)
router = APIRouter(tags=["health"])


@router.get("/health")
async def health():
    try:
        await run_in_threadpool(analysis_store.run_query, "SELECT 1")
        postgres = "ok"
    except Exception:
        logger.exception("health probe could not reach postgres")
        postgres = "unavailable"
    return {
        "status": "ok" if postgres == "ok" else "degraded",
        "service": "trends_real_estate",
        "postgres": postgres,
    }
