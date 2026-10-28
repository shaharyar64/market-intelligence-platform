"""The personas a caller can pin a conversation to.

Read-only and deliberately thin: the assistant is where a persona is used, and
this exists so the picker beside the chat box can be filled from the same rows
the tools read, rather than from a list the UI keeps its own copy of.
"""
import logging
from typing import Any, Dict

from fastapi import APIRouter, Depends
from fastapi.concurrency import run_in_threadpool

from services.food_intelligence_service.app.api.deps import get_current_user
from services.food_intelligence_service.app.personas import store

logger = logging.getLogger("personas.api")

router = APIRouter(prefix="/personas", tags=["personas"])


@router.get("")
async def list_personas(current_user: Dict[str, Any] = Depends(get_current_user)):
    """Every persona with a centroid, smallest payload that fills the picker.

    A failure here returns an empty list rather than an error: the picker is an
    optional narrowing of the chat, and a chat that will not load because the
    persona list is down is a worse outcome than a chat with no picker.
    """
    try:
        rows = await run_in_threadpool(store.list_personas)
    except Exception:
        logger.exception("could not list personas")
        return {"personas": []}
    return {"personas": [
        {"persona_id": r["persona_id"], "name": r["name"],
         "tagline": r["tagline"],
         "posts": (r["stats"] or {}).get("post_count"),
         "share_of_food_posts_pct": (r["stats"] or {}).get("share_of_food_posts_pct")}
        for r in rows]}
