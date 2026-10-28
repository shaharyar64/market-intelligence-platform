"""Tool schemas the model sees, and the dispatch that runs them.

Every tool returns the same envelope so the agent can tell "no data" from
"data", and so an empty result can never be mistaken for a successful answer.
"""
import logging
from datetime import date

from services.food_intelligence_service.app.assistant import retrieval
from services.food_intelligence_service.app.personas import store as personas
from services.food_intelligence_service.app.personas import context as personas_context
from services.food_intelligence_service.app.trends import adhoc

logger = logging.getLogger("assistant.tools")

_QUADRANTS = {"breakthrough", "slow-burner", "mainstream", "watchlist"}


def _parse_date(value):
    return date.fromisoformat(value) if value else None


def _filters(args: dict) -> retrieval.PostFilters:
    return retrieval.PostFilters(
        platforms=args.get("platforms"), sources=args.get("sources"),
        date_from=_parse_date(args.get("date_from")),
        date_to=_parse_date(args.get("date_to")),
        countries=args.get("countries"), min_engagement=args.get("min_engagement"),
        hashtag=args.get("hashtag"), persona=_persona_id(args.get("persona")))


def _persona_id(value: str | None) -> str | None:
    """The model is given ids but users say "the busy family one", and the model
    passes that through. An unmatched name must not silently become no filter at
    all: that answers a question about one segment with data about everyone."""
    if not value:
        return None
    found = personas.resolve(value)
    return found["persona_id"] if found else f"{UNKNOWN_PERSONA}{value}"


def _envelope(data, subject: str) -> dict:
    count = len(data) if isinstance(data, list) else (0 if data is None else 1)
    if not count:
        return {"ok": False, "data": [], "count": 0,
                "message": f"No data found for {subject}."}
    return {"ok": True, "data": data, "count": count, "message": ""}


UNKNOWN_PERSONA = "__unknown__"


def dispatch(name: str, args: dict, embed_query, user_sub: str | None = None,
             context_ledger: set | None = None) -> dict:
    try:
        # An unrecognised persona has to stop the call, not fall through as an
        # empty filter. Filtering on a name that matches nothing returns zero
        # rows, which reads as "this segment has no posts" - a claim about the
        # market made from a typo.
        wanted = args.get("persona")
        if wanted and (_persona_id(wanted) or "").startswith(UNKNOWN_PERSONA):
            known = [p["persona_id"] for p in personas.list_personas()]
            return {"ok": False, "data": [], "count": 0,
                    "message": f"No persona matching {wanted!r}, so no filter was "
                               f"applied and nothing was looked up. The personas "
                               f"are: {', '.join(known) or 'none defined yet'}. "
                               "Ask the user which they meant, or call "
                               "list_personas."}
        if name == "search_trends":
            result = _envelope(retrieval.search_trends(
                query=args.get("query"), quadrant=args.get("quadrant"),
                level=args.get("level", "micro"), limit=args.get("limit", 10),
                persona=_persona_id(args.get("persona")),
                countries=args.get("countries"), embed_query=embed_query),
                f"trends matching {args.get('query') or 'those filters'!r}")
            # Retry once without the narrowing filters. The model volunteers a
            # quadrant it was never asked for, and a wrong guess returns nothing
            # for a trend that plainly exists - which the assistant then reported
            # as "no data". The relaxation is announced in the envelope so the
            # answer can say the filter was dropped rather than quietly ignore it.
            if result["ok"]:
                return result
            query = (args.get("query") or "").strip()
            # A quadrant name used as the search text matches nothing: no trend
            # is called "breakthrough". Drop the text and keep the quadrant,
            # which is what the question actually meant.
            if query.lower() in _QUADRANTS:
                retried = _envelope(retrieval.search_trends(
                    query=None, quadrant=args.get("quadrant") or query.lower(),
                    level=args.get("level", "micro"), limit=args.get("limit", 10),
                    persona=_persona_id(args.get("persona")),
                    countries=args.get("countries"), embed_query=embed_query),
                    f"{query.lower()} trends")
                if retried["ok"]:
                    return retried
            narrowing = [f"{k}={args[k]!r}" for k in ("quadrant", "level")
                         if args.get(k) is not None]
            if narrowing and query:
                widened = _envelope(retrieval.search_trends(
                    query=query, quadrant=None, level="micro",
                    limit=args.get("limit", 10),
                    persona=_persona_id(args.get("persona")),
                    countries=args.get("countries"), embed_query=embed_query),
                    f"trends matching {query!r}")
                if widened["ok"]:
                    widened["relaxed_filters"] = narrowing
                    widened["message"] = (
                        f"No trend matched with {', '.join(narrowing)}, so those "
                        "filters were dropped. These results ignore them - say so "
                        "if the user asked for that filter.")
                    return widened
            # Country and persona were the two filters this ladder never
            # relaxed, and they are the two that empty a search most often: a
            # segment can be too small to clear the membership floor, and a
            # country is unknown on most posts. Dropping them last, and saying
            # so, turns "I have no data on bakery in the UAE" into the market
            # answer plus the reason the country cut could not be made.
            scoped = [f"{k}={args[k]!r}" for k in ("countries", "persona")
                      if args.get(k)]
            if scoped and query:
                unscoped = _envelope(retrieval.search_trends(
                    query=query, quadrant=None, level=args.get("level", "micro"),
                    limit=args.get("limit", 10), persona=None, countries=None,
                    embed_query=embed_query),
                    f"trends matching {query!r}")
                if unscoped["ok"]:
                    unscoped["relaxed_filters"] = scoped
                    unscoped["message"] = (
                        f"No trend cleared {', '.join(scoped)} - either too few "
                        "posts in that segment or country, or the country is "
                        "unknown for most of them. These results are for the "
                        "whole market. Say that the narrower cut could not be "
                        "made, and do not describe these as being about that "
                        "segment or country.")
                    return unscoped
            return result
        if name == "get_trend":
            return _envelope(retrieval.get_trend(args["trend_id"]),
                             f"trend {args['trend_id']!r}")
        if name == "compare_trends":
            requested = args["trend_ids"]
            fetched = {i: retrieval.get_trend(i) for i in requested}
            found = [fetched[i] for i in requested if fetched[i]]
            not_found = [i for i in requested if not fetched[i]]
            result = _envelope(found, "those trends")
            result["not_found"] = not_found
            return result
        if name == "get_timeline":
            trend = retrieval.get_trend(args["trend_id"])
            return _envelope(trend.get("timeline") if trend else None,
                             f"timeline of {args['trend_id']!r}")
        if name == "aggregate_posts":
            return _envelope(retrieval.aggregate_posts(
                _filters(args), group_by=args.get("group_by", "source"),
                metric=args.get("metric", "count")), "those filters")
        if name == "search_posts":
            vector = embed_query(args["query"])
            return _envelope(retrieval.search_posts(
                vector, _filters(args), limit=args.get("limit", 10)),
                f"posts about {args['query']!r}")
        if name == "list_brands":
            return _envelope(retrieval.list_brands(limit=args.get("limit", 30)),
                             "tracked brands")
        if name == "get_brand_profile":
            profile = retrieval.get_brand_profile(
                args["brand"], limit=args.get("limit", 40))
            if not profile:
                return {"ok": False, "data": [], "count": 0,
                        "message": f"No analysed posts for a brand matching "
                                   f"{args['brand']!r}. Call list_brands to see "
                                   "which brands are covered."}
            return {"ok": True, "data": profile,
                    "count": profile["analysed_posts"], "message": ""}
        if name == "get_brand_trends":
            rows = retrieval.get_brand_trends(
                args["brand"], limit=args.get("limit") or 15)
            if not rows:
                return {"ok": False, "data": [], "count": 0,
                        "message": f"None of {args['brand']!r}'s analysed posts "
                                   "fall inside a trend in the current run. Say "
                                   "that plainly - do not name a trend it might "
                                   "be in."}
            return _envelope(rows, f"trends {rows[0]['brand_name']} posts into")
        if name == "list_personas":
            found = personas.list_personas()
            listed = _envelope([
                {"persona_id": p["persona_id"], "name": p["name"],
                 "tagline": p["tagline"],
                 "posts_covered": (p["stats"] or {}).get("post_count"),
                 "unique_authors": (p["stats"] or {}).get("unique_authors"),
                 "share_of_food_posts_pct":
                     (p["stats"] or {}).get("share_of_food_posts_pct")}
                for p in found],
                "personas")
            if listed["ok"]:
                listed["message"] = (
                    "These personas OVERLAP - a post can belong to several, and "
                    "some pairs share most of their posts. Their post counts are "
                    "not a partition and must never be added together or used as "
                    "a denominator. Each persona's share of the corpus is already "
                    "given as share_of_food_posts_pct.")
            return listed
        if name == "get_persona":
            found = personas.resolve(args["persona_id"])
            if not found:
                names = [p["persona_id"] for p in personas.list_personas()]
                return {"ok": False, "data": [], "count": 0,
                        "message": f"No persona matching {args['persona_id']!r}. "
                                   f"The personas are: {', '.join(names) or 'none'}."}
            stats = found.pop("stats", None) or {}
            # Split at the boundary the answer has to respect: one half is the
            # client's own segmentation, the other is counted from posts.
            data = {"definition_given_to_us": found, "measured_from_posts": stats}
            # The interpretive block is ~800 tokens and is already in the system
            # message when this persona is pinned. The ledger makes one turn pay
            # for it once, however many times the agent reaches for it.
            pid = found["persona_id"]
            block = personas_context.for_persona(pid)
            if block and (context_ledger is None or pid not in context_ledger):
                data["interpretive_context"] = block
                data["how_to_use_it"] = personas_context.LENS_RULES
                if context_ledger is not None:
                    context_ledger.add(pid)
            elif block:
                data["context_note"] = (
                    "The interpretive context for this persona was already "
                    "provided earlier in this turn. Use it; do not ask for it "
                    "again.")
            return {"ok": True, "count": stats.get("post_count") or 0, "message": "",
                    "data": data}
        if name == "create_trend":
            query = (args.get("query") or "").strip()
            if not query:
                return {"ok": False, "data": [], "count": 0,
                        "message": "create_trend needs a query describing the topic."}
            overlaps = adhoc.similar_existing(query, embed_query)
            row = adhoc.build(query, embed_query, name=args.get("name"),
                              created_by=user_sub)
            if not row:
                return {"ok": False, "data": [], "count": 0,
                        "message": f"Only a handful of posts in the corpus match "
                                   f"{query!r} closely enough, so no trend was "
                                   "created. Say that plainly - do not describe a "
                                   "trend that was not created."}
            return {"ok": True, "count": row["post_count"], "message": "",
                    "data": {"trend_id": row["trend_id"], "name": row["name"],
                             "quadrant": row["quadrant"],
                             "post_count": row["post_count"],
                             "unique_authors": row["unique_authors"],
                             "volume_index": row["volume_index"],
                             "growth_index": row["growth_index"],
                             "growth_pct": row["metrics"]["growth_pct"],
                             "source_mix": row["metrics"]["source_mix"],
                             "created": True,
                             "already_covered_by": overlaps}}
        return {"ok": False, "data": [], "count": 0,
                "message": f"Unknown tool {name!r}."}
    except Exception:
        logger.exception("tool %s failed", name)
        return {"ok": False, "data": [], "count": 0,
                "message": f"The {name} lookup failed. Please try again."}
