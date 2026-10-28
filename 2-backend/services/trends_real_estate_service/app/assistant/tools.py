"""Tool schemas the model sees, and the dispatch that runs them.

Every tool returns the same envelope so the agent can tell "no data" from
"data", and so an empty result can never be mistaken for a successful answer.
"""
import logging
from datetime import date

from services.trends_real_estate_service.app.assistant import retrieval
from services.trends_real_estate_service.app.trends import adhoc

logger = logging.getLogger("assistant.tools")

_QUADRANTS = {"breakthrough", "slow-burner", "mainstream", "watchlist"}
WEAK_MATCH_DISTANCE = 0.50


def _flag_weak_match(result: dict, query: str | None) -> dict:
    rows = result.get("data") if isinstance(result.get("data"), list) else []
    if not result.get("ok") or not query or any(r.get("exact") for r in rows):
        return result
    distances = [r["distance"] for r in rows if r.get("distance") is not None]
    if distances and min(distances) > WEAK_MATCH_DISTANCE:
        result["weak_match"] = True
        result["best_distance"] = round(min(distances), 3)
        result["message"] = (
            f"WEAK MATCH: no trend is close to {query!r} (best distance "
            f"{min(distances):.2f}). These trends are only loosely related and may not "
            "be about the topic at all. Do not present them as the answer. Search again "
            "with concrete terms people would write in a post, check search_posts, or "
            "call create_trend; if nothing fits, say plainly that no trend in the data "
            "covers this topic.")
    return result


def _parse_date(value):
    return date.fromisoformat(value) if value else None


def _filters(args: dict) -> retrieval.PostFilters:
    return retrieval.PostFilters(
        platforms=args.get("platforms"), sources=args.get("sources"),
        date_from=_parse_date(args.get("date_from")),
        date_to=_parse_date(args.get("date_to")),
        countries=args.get("countries"), min_engagement=args.get("min_engagement"),
        hashtag=args.get("hashtag"))


def _envelope(data, subject: str) -> dict:
    count = len(data) if isinstance(data, list) else (0 if data is None else 1)
    if not count:
        return {"ok": False, "data": [], "count": 0,
                "message": f"No data found for {subject}."}
    return {"ok": True, "data": data, "count": count, "message": ""}



def dispatch(name: str, args: dict, embed_query, user_sub: str | None = None,
             context_ledger: set | None = None) -> dict:
    try:
        if name == "search_trends":
            result = _flag_weak_match(_envelope(retrieval.search_trends(
                query=args.get("query"), quadrant=args.get("quadrant"),
                limit=args.get("limit", 10),
                countries=args.get("countries"), embed_query=embed_query),
                f"trends matching {args.get('query') or 'those filters'!r}"),
                args.get("query"))
            # Retry once without the narrowing filters. The model volunteers a
            # quadrant it was never asked for, and a wrong guess returns nothing
            # for a trend that plainly exists - which the assistant then reported
            # as "no data". The relaxation is announced in the envelope so the
            # answer can say the filter was dropped rather than quietly ignore it.
            if result.get("weak_match") and args.get("countries"):
                wider = _flag_weak_match(_envelope(retrieval.search_trends(
                    query=args.get("query"), quadrant=args.get("quadrant"),
                    limit=args.get("limit", 10), countries=None, embed_query=embed_query),
                    f"trends matching {args.get('query')!r}"), args.get("query"))
                if wider["ok"] and not wider.get("weak_match"):
                    wider["relaxed_filters"] = [f"countries={args['countries']!r}"]
                    wider["message"] = (
                        f"Nothing in the {', '.join(args['countries'])} run matched closely, so "
                        "these come from the all-markets run. Say so, and do not describe "
                        "them as specific to that country.")
                    return wider
            if result["ok"]:
                return result
            query = (args.get("query") or "").strip()
            # A quadrant name used as the search text matches nothing: no trend
            # is called "breakthrough". Drop the text and keep the quadrant,
            # which is what the question actually meant.
            if query.lower() in _QUADRANTS:
                retried = _envelope(retrieval.search_trends(
                    query=None, quadrant=args.get("quadrant") or query.lower(),
                    limit=args.get("limit", 10),
                    countries=args.get("countries"), embed_query=embed_query),
                    f"{query.lower()} trends")
                if retried["ok"]:
                    return retried
            # A quadrant asked for with no topic can be empty for the whole
            # market: the UAE and KSA runs have no breakthrough trends at all,
            # because a small trend in one market rarely has enough posts for
            # its growth to be measured. "Which trends are breaking out in KSA"
            # then answered "no data" - and once as "the lookup failed". The
            # market's fastest-growing trends are the answer to that question,
            # provided the reply says none of them is in the quadrant.
            if not query and args.get("quadrant"):
                fastest = _envelope(retrieval.search_trends(
                    query=None, quadrant=None,
                    limit=args.get("limit", 10), countries=args.get("countries"),
                    embed_query=embed_query), "trends")
                if fastest["ok"]:
                    fastest["relaxed_filters"] = [f"quadrant={args['quadrant']!r}"]
                    fastest["message"] = (
                        f"No trend in this run is in the {args['quadrant']} quadrant. "
                        "These are the run's trends ordered by growth_index instead. "
                        f"Say plainly that none is {args['quadrant']}, then give these "
                        "as the fastest-growing, with their own quadrants.")
                    return fastest
            narrowing = [f"quadrant={args['quadrant']!r}"] if args.get("quadrant") else []
            if narrowing and query:
                widened = _flag_weak_match(_envelope(retrieval.search_trends(
                    query=query, quadrant=None,
                    limit=args.get("limit", 10),
                    countries=args.get("countries"), embed_query=embed_query),
                    f"trends matching {query!r}"), query)
                if widened["ok"]:
                    widened["relaxed_filters"] = narrowing
                    widened["message"] = (widened["message"] + " " if widened.get("weak_match") else "") + (
                        f"No trend matched with {', '.join(narrowing)}, so those "
                        "filters were dropped. These results ignore them - say so "
                        "if the user asked for that filter.")
                    return widened
            # Country is the filter this ladder never relaxed, and it empties a
            # search most often because country is unknown on most posts.
            # Dropping it last, and saying so, turns "I have no data on
            # waterfront in the UAE" into the market answer plus the reason the
            # country cut could not be made.
            scoped = [f"countries={args['countries']!r}"] if args.get("countries") else []
            if scoped and query:
                unscoped = _flag_weak_match(_envelope(retrieval.search_trends(
                    query=query, quadrant=None,
                    limit=args.get("limit", 10), countries=None,
                    embed_query=embed_query),
                    f"trends matching {query!r}"), query)
                if unscoped["ok"]:
                    unscoped["relaxed_filters"] = scoped
                    unscoped["message"] = (unscoped["message"] + " " if unscoped.get("weak_match") else "") + (
                        f"No trend cleared {', '.join(scoped)} - either too few "
                        "posts in that country, or the country is unknown for "
                        "most of them. These results are for the whole market. "
                        "Say that the narrower cut could not be made, and do "
                        "not describe these as being about that country.")
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
            result = _envelope(retrieval.search_posts(
                vector, _filters(args), limit=args.get("limit", 10)),
                f"posts about {args['query']!r}")
            # Country is applied after the nearest-neighbour pool is drawn, and
            # it is unknown on community posts, so a pool that happens to be
            # mostly community comes back empty for a place that plainly has
            # posts. Measured: "Dubai Creek Harbour payment plan handover" with
            # countries=['AE'] returned nothing; without it, five on-topic
            # posts. Retry once without it, and say so.
            if result["ok"] or not args.get("countries"):
                return result
            unscoped = _envelope(retrieval.search_posts(
                vector, _filters({**args, "countries": None}),
                limit=args.get("limit", 10)), f"posts about {args['query']!r}")
            if unscoped["ok"]:
                unscoped["relaxed_filters"] = [f"countries={args['countries']!r}"]
                unscoped["message"] = (
                    f"No post matched with countries={args['countries']!r} - the "
                    "country is unknown on community posts, which make up most of "
                    "the nearest matches - so that filter was dropped. Each post "
                    "still carries its own country where known; say the country "
                    "cut could not be made if the user asked for it.")
                return unscoped
            return result
        if name == "list_brands":
            return _envelope(retrieval.list_brands(limit=args.get("limit", 30),
                                                   countries=args.get("countries")),
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
        if name == "developers_by_topic":
            query = (args.get("query") or "").strip()
            rows = retrieval.developers_by_topic(
                embed_query(query), countries=args.get("countries"),
                limit=args.get("limit") or 10)
            if not rows and args.get("countries"):
                rows = retrieval.developers_by_topic(
                    embed_query(query), countries=None, limit=args.get("limit") or 10)
                result = _envelope(rows, f"developer posts about {query!r}")
                if result["ok"]:
                    result["relaxed_filters"] = [f"countries={args['countries']!r}"]
                    result["message"] = ("No developer post in that country matched, so the "
                                         "country filter was dropped. Say so.")
                return result
            return _envelope(rows, f"developer posts about {query!r}")
        if name == "developers_in_trend":
            rows = retrieval.developers_in_trend(
                args["trend_id"], limit=args.get("limit") or 15,
                countries=args.get("countries"))
            result = _envelope(rows, f"developer posts inside trend {args['trend_id']!r}")
            if result["ok"]:
                result["message"] = (
                    "Each developer carries developer_country (SA, AE or null if unknown) and "
                    "trend_market. Never describe a developer as being in a country other than "
                    "its developer_country.")
            return result
        if name == "create_trend":
            query = (args.get("query") or "").strip()
            if not query:
                return {"ok": False, "data": [], "count": 0,
                        "message": "create_trend needs a query describing the topic."}
            existing = adhoc.existing_chat_trend(query, embed_query)
            trend = retrieval.get_trend(existing["trend_id"]) if existing else None
            if trend:
                return {"ok": True, "count": trend["post_count"], "reused": True,
                        "message": f"A chat-created trend already covers {query!r}: "
                                   f"{trend['name']!r}. It was reused instead of creating a "
                                   "duplicate. Say that an existing trend was used.",
                        "data": {"trend_id": trend["trend_id"], "name": trend["name"],
                                 "quadrant": trend["quadrant"],
                                 "post_count": trend["post_count"],
                                 "unique_authors": trend["unique_authors"],
                                 "volume_index": trend["volume_index"],
                                 "growth_index": trend["growth_index"],
                                 "growth_pct": trend.get("growth_pct"),
                                 "source_mix": trend.get("source_mix"),
                                 "created": False, "reused": True}}
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
