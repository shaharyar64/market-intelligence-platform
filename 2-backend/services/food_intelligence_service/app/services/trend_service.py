"""Read queries for the trends API. Serves the latest run in food_intel.trends.

Shapes mirror dashboards-ui/lib/foodDummy.ts so the UI swap is a drop-in.
"""
import json
import logging
import os
import time
from datetime import datetime, timedelta, timezone
import psycopg2.extras
from functools import lru_cache

from services.food_intelligence_service.app.core.config import get_settings
from services.food_intelligence_service.app.trends import store

logger = logging.getLogger(__name__)
QUADRANT_ORDER = ["slow-burner", "mainstream", "breakthrough", "watchlist"]


@lru_cache()
def _s3():
    import boto3
    return boto3.client(
        "s3",
        aws_access_key_id=os.getenv("AWS_ACCESS_KEY_ID"),
        aws_secret_access_key=os.getenv("AWS_SECRET_ACCESS_KEY"),
        region_name=os.getenv("AWS_REGION", "us-east-1"),
    )


def _media_url(key: str | None) -> str | None:
    """Presign a media key.

    A key may name its own bucket as "s3://bucket/key". The tracked brand and
    influencer accounts were crawled by a different collector, which left their
    images in the raw bucket rather than the trends one; 99.6% of their posts
    have a picture sitting there already, so the view points at it in place
    instead of anything being copied. Bare keys mean the trends bucket, as
    before.

    Originals are served directly; there is no thumbnail variant.
    """
    if not key:
        return None
    settings = get_settings()
    bucket, target = settings.TRENDS_MEDIA_S3_BUCKET, settings.TRENDS_MEDIA_KEY_PREFIX + key
    if key.startswith("s3://"):
        bucket, _, target = key[len("s3://"):].partition("/")
        if not bucket or not target:
            return None
    try:
        return _s3().generate_presigned_url(
            "get_object", Params={"Bucket": bucket, "Key": target}, ExpiresIn=3600)
    except Exception as exc:
        logger.warning("presign failed for %s/%s: %s", bucket, target, exc)
        return None


def _loads(row: dict) -> dict:
    for c in ("narrative", "metrics", "timeline", "example_posts", "member_posts"):
        if isinstance(row.get(c), str):
            row[c] = json.loads(row[c])
    return row


_latest_run_cache: dict = {}
_LATEST_RUN_TTL = 60.0


def latest_run_id(country: str | None = None) -> str | None:
    """Cached per market: every endpoint resolves the newest run before doing its
    own query, and the answer only changes when a pipeline run finishes.

    country IS NULL is the all-markets run and stays the default, so a country
    run is only ever read when a caller names its market.
    """
    now = time.monotonic()
    hit = _latest_run_cache.get(country)
    if hit and now - hit[0] < _LATEST_RUN_TTL:
        return hit[1]
    with store.get_conn() as conn, conn.cursor() as cur:
        if country:
            cur.execute("""SELECT run_id FROM food_intel.trends
                           WHERE country = %s
                           ORDER BY created_at DESC LIMIT 1""", (country,))
        else:
            cur.execute("""SELECT run_id FROM food_intel.trends
                           WHERE country IS NULL
                           ORDER BY created_at DESC LIMIT 1""")
        row = cur.fetchone()
        value = row[0] if row else None
    _latest_run_cache[country] = (now, value)
    return value


def previous_run_id(current: str) -> str | None:
    """The newest run before `current` in the same market and of the same kind.

    Comparing across markets (an all-markets run against a country run, or two
    different countries) would match unrelated corpora - see D8. The same holds
    across kinds: run ids are "<run_key>-<timestamp>", and a tracked run compared
    with a community "all" run reported a 140-trend drop that was only the
    difference in corpus.
    """
    kind = current.rsplit("-", 1)[0]
    with store.get_conn() as conn, conn.cursor() as cur:
        cur.execute("""SELECT run_id FROM food_intel.trends
                       WHERE run_id <> %s
                         AND run_id LIKE %s
                         AND country IS NOT DISTINCT FROM (
                             SELECT country FROM food_intel.trends
                             WHERE run_id = %s LIMIT 1)
                       GROUP BY run_id ORDER BY max(created_at) DESC LIMIT 1""",
                    (current, f"{kind}-%", current))
        row = cur.fetchone()
        return row[0] if row else None


def _slug(trend_id: str) -> str:
    """trend ids are '<slug>--<run suffix>' — the slug is stable across runs."""
    return trend_id.rsplit("--", 1)[0]


def platform_today() -> "datetime.date":
    """Today where the audience is, not where the server happens to run.

    A server on UTC rolls the month over four hours before Dubai does, so on
    the first of the month the dashboard would disagree with the reader's
    calendar. Falls back to a fixed +04:00 when the tz database is missing,
    which is exact for Dubai: it has never observed daylight saving.
    """
    name = get_settings().PLATFORM_TIMEZONE
    try:
        from zoneinfo import ZoneInfo
        return datetime.now(ZoneInfo(name)).date()
    except Exception:
        logger.warning("timezone %s unavailable, using a fixed +04:00 offset", name)
        return datetime.now(timezone(timedelta(hours=4))).date()


def _latest_month(trends: list[dict]) -> str | None:
    """The newest calendar month any trend has posts in."""
    months = {m["month"] for t in trends for m in (t["metrics"].get("months") or [])}
    return max(months) if months else None


def _annotate_momentum(trends: list[dict]) -> None:
    """Write metrics.momentum_pct onto each trend, in place.

    Computed at serve time because it needs the totals across whatever cohort
    is being shown, and that cohort changes with the period.
    """
    from services.food_intelligence_service.app.trends.metrics import compute_momentum_pct
    total_recent = sum(t["metrics"].get("recent_posts") or 0 for t in trends)
    total_previous = sum(t["metrics"].get("previous_posts") or 0 for t in trends)
    cohort = len(trends) or 1
    for t in trends:
        t["metrics"] = {**t["metrics"], "momentum_pct": round(compute_momentum_pct(
            t["metrics"].get("recent_posts") or 0,
            t["metrics"].get("previous_posts") or 0,
            total_recent, total_previous, cohort), 1)}


def _annotate_momentum_one(t: dict) -> None:
    """Momentum for a single trend, using the run's totals rather than a cohort
    already in memory. The detail view fetches one row, so the list path's
    annotate cannot serve it."""
    from services.food_intelligence_service.app.trends.metrics import compute_momentum_pct
    with store.get_conn() as conn, conn.cursor() as cur:
        cur.execute("SET LOCAL statement_timeout = '20s'")
        cur.execute("""
            SELECT coalesce(sum((metrics->>'recent_posts')::int), 0),
                   coalesce(sum((metrics->>'previous_posts')::int), 0),
                   count(*)
            FROM food_intel.trends
            WHERE run_id = %s AND level = %s
        """, (t["run_id"], t["level"]))
        total_recent, total_previous, cohort = cur.fetchone()
    t["metrics"] = {**t["metrics"], "momentum_pct": round(compute_momentum_pct(
        int(t["metrics"].get("recent_posts") or 0),
        int(t["metrics"].get("previous_posts") or 0),
        int(total_recent), int(total_previous), int(cohort) or 1), 1)}


def _apply_period(trends: list[dict], period: str) -> tuple[list[dict], str | None]:
    """Rescore trends for a period mode.

    'cumulative' keeps the run's stored full-history metrics. 'month' scores a
    real calendar month - the current one when the corpus reaches it, otherwise
    the newest month with data - and compares it against the month before.
    The month actually used is returned so the UI can name it instead of
    claiming a recency the data may not have.

    Months, not trailing four-week windows: a caller asking for June wants
    posts published in June, and ISO weeks straddle month boundaries.
    """
    if period != "month":
        _annotate_momentum(trends)
        return trends, None
    # Always the real calendar month. Falling back to the newest month with
    # data made a seven-week-old corpus look current; an empty month is the
    # honest answer and the reader can switch to cumulative.
    month = platform_today().strftime("%Y-%m")

    def _prev(m: str) -> str:
        year, mon = int(m[:4]), int(m[5:])
        return f"{year - 1}-12" if mon == 1 else f"{year}-{mon - 1:02d}"

    previous = _prev(month)
    # Only trends that were actually posted in during the month belong to it.
    # Keeping the rest at volume 0 padded the list with trends that had nothing
    # to say that month.
    active = []
    for t in trends:
        by_month = {m["month"]: m for m in (t["metrics"].get("months") or [])}
        recent = by_month.get(month, {}).get("post_count", 0)
        if recent:
            active.append((t, recent, by_month.get(previous, {}).get("post_count", 0)))
    if not active:
        return [], month
    trends = [t for t, _, _ in active]
    vols = [float(r) for _, r, _ in active]
    from services.food_intelligence_service.app.trends.metrics import (
        assign_quadrant, compute_growth_pct, percentile_index)
    # Same share-of-voice definition the pipeline uses, applied to the month's
    # own totals: comparing raw counts across months would report the size of
    # each month's collection rather than a trend's movement within it.
    total_recent = sum(r for _, r, _ in active)
    total_previous = sum(p for _, _, p in active)
    gros = [compute_growth_pct(r, p, total_recent, total_previous, len(active))
            for _, r, p in active]
    vol_idx = percentile_index(vols)
    gro_idx = percentile_index(gros)
    for (t, recent, prior), vi, gi, g in zip(active, vol_idx, gro_idx, gros):
        t["volume_index"] = round(vi, 2)
        t["growth_index"] = round(gi, 2)
        t["quadrant"] = assign_quadrant(vi, gi)
        t["metrics"] = {**t["metrics"], "volume_raw": int(recent),
                        "growth_pct": round(g, 2),
                        "recent_posts": int(recent), "previous_posts": int(prior)}
    _annotate_momentum(trends)
    trends.sort(key=lambda t: -t["growth_index"])
    return trends, month


# member_posts is the full membership list (428 kB per run) and example_posts
# another 196 kB — neither is needed for list/overview rendering, and pulling
# them made SELECT * 7x slower than the columns we actually use.
_LIST_COLUMNS = """trend_id, run_id, level, parent_trend_id, name, quadrant,
                   volume_index, growth_index, post_count,
                   unique_authors, narrative, metrics, timeline, created_at,
                   origin, created_by, source_query"""


def _fetch(run_id: str, level: str | None = None) -> list[dict]:
    sql = f"SELECT {_LIST_COLUMNS} FROM food_intel.trends WHERE run_id = %s"
    params: list = [run_id]
    if level:
        sql += " AND level = %s"
        params.append(level)
    sql += " ORDER BY growth_index DESC, post_count DESC"
    with store.get_conn() as conn, conn.cursor() as cur:
        cur.execute(sql, params)
        cols = [d[0] for d in cur.description]
        return [_loads(dict(zip(cols, r))) for r in cur.fetchall()]


def _sparkline(timeline: list[dict]) -> list[int]:
    return [t["post_count"] for t in timeline][-7:]


def _trend_row(t: dict) -> dict:
    """foodDummy.TrendRow shape."""
    return {
        "id": t["trend_id"],
        "name": t["name"],
        "level": t["level"],
        "parent_trend_id": t["parent_trend_id"],
        "quadrant": t["quadrant"],
        "growth": round(t["growth_index"]),
        "growth_pct": (None if t["metrics"].get("growth_pct") is None
                       else round(float(t["metrics"]["growth_pct"]), 1)),
        "momentum_pct": (None if t["metrics"].get("momentum_pct") is None
                         else round(float(t["metrics"]["momentum_pct"]), 1)),
        "is_new": bool(t["metrics"].get("is_new")),
        "recent_posts": t["metrics"].get("recent_posts"),
        "previous_posts": t["metrics"].get("previous_posts"),
        "first_post": t["metrics"].get("first_post"),
        "volume": round(t["volume_index"]),
        "post_count": t["post_count"],
        "platforms": sorted(t["metrics"]["platform_mix"].keys()),
        "source_mix": t["metrics"].get("source_mix") or {},
        "sparkline": _sparkline(t["timeline"]),
        "summary": t["narrative"].get("summary") or "",
        "opportunity_summary": t["narrative"].get("opportunity_summary") or "",
        # 'pipeline' when clustering discovered it, 'chat' when a user asked the
        # assistant to build it. Both are measured identically; the distinction
        # is provenance, and the explorer lets you filter on it.
        "origin": t.get("origin") or "pipeline",
        "source_query": t.get("source_query"),
    }


def list_trends(run_id: str, level: str = "micro", period: str = "cumulative") -> list[dict]:
    scored, _ = _apply_period(_fetch(run_id, level), period)
    return [_trend_row(t) for t in scored]


def _movers(current: list[dict], prev_rows: list[dict]) -> list[dict]:
    """Growth-index change vs the previous run, matched on the stable name slug.
    Positive movement only — mirrors the dummy 'Biggest Movers' semantics."""
    if not prev_rows:
        return []
    prev = {_slug(t["trend_id"]): t for t in prev_rows}
    movers = []
    for t in current:
        p = prev.get(_slug(t["trend_id"]))
        if not p:
            continue
        pts = round(t["growth_index"] - p["growth_index"])
        if pts > 0:
            movers.append({"id": t["trend_id"], "name": t["name"], "pts": pts})
    movers.sort(key=lambda m: -m["pts"])
    return [{"rank": i + 1, **m} for i, m in enumerate(movers[:5])]


def _kpi_deltas(quadrant_counts: dict[str, int], n_micro: int,
                prev_rows: list[dict]) -> dict[str, int | None]:
    if not prev_rows:
        return {}
    prev_counts: dict[str, int] = {}
    for t in prev_rows:
        prev_counts[t["quadrant"]] = prev_counts.get(t["quadrant"], 0) + 1
    return {
        "trends": n_micro - len(prev_rows),
        **{q: quadrant_counts.get(q, 0) - prev_counts.get(q, 0) for q in QUADRANT_ORDER},
    }


def overview(run_id: str, period: str = "cumulative") -> dict:
    # one query for both levels: each extra round trip to RDS is ~0.5s from
    # outside the VPC, so the page is dominated by query count, not query cost
    all_rows = _fetch(run_id)
    micro, period_month = _apply_period(
        [t for t in all_rows if t["level"] == "micro"], period)
    umbrellas, _ = _apply_period(
        [t for t in all_rows if t["level"] == "umbrella"], period)
    quadrants: dict[str, list] = {q: [] for q in QUADRANT_ORDER}
    for t in micro:
        quadrants[t["quadrant"]].append(
            {"id": t["trend_id"], "name": t["name"],
             "volume": round(t["volume_index"]), "growth": round(t["growth_index"])})
    emerging = sorted((t for t in micro if t["quadrant"] == "breakthrough"),
                      key=lambda t: -t["growth_index"])[:4] or \
               sorted(micro, key=lambda t: -t["growth_index"])[:4]
    counts = {q: len(ts) for q, ts in quadrants.items()}
    # fetch the comparison run once — movers and KPI deltas both need it
    prev_run = previous_run_id(run_id)
    prev_rows = _fetch(prev_run, "micro") if prev_run else []
    deltas = _kpi_deltas(counts, len(micro), prev_rows)
    kpis = [
        {"key": "trends", "label": "Tracked Trends", "value": len(micro),
         "delta": deltas.get("trends")},
        {"key": "watchlist", "label": "Watchlist", "value": counts["watchlist"],
         "delta": deltas.get("watchlist")},
        {"key": "breakthrough", "label": "Breakthrough", "value": counts["breakthrough"],
         "delta": deltas.get("breakthrough")},
        {"key": "slow", "label": "Slow Burners", "value": counts["slow-burner"],
         "delta": deltas.get("slow-burner")},
        {"key": "mainstream", "label": "Mainstream", "value": counts["mainstream"],
         "delta": deltas.get("mainstream")},
        {"key": "brands", "label": "Brands Tracked", "value": store.count_brand_accounts(),
         "delta": None},
    ]
    return {
        "run_id": run_id,
        "period": period,
        "period_month": period_month,
        "computed_at": str(micro[0]["created_at"]) if micro else None,
        # From the unfiltered run, not the period slice: an empty month still
        # needs to report when the corpus actually ends.
        "as_of": next((t["metrics"].get("as_of") for t in all_rows
                       if t["metrics"].get("as_of")), None),
        "kpis": kpis,
        "quadrants": [{"quadrant": q, "trends": ts} for q, ts in quadrants.items()],
        "emerging": [{"id": t["trend_id"], "name": t["name"],
                      "growth": round(t["growth_index"]), "quadrant": t["quadrant"],
                      "summary": t["narrative"].get("summary") or ""} for t in emerging],
        "movers": _movers(micro, prev_rows),
        "umbrellas": [_trend_row(u) for u in umbrellas],
    }


def _posts_in_range(members: list[dict], date_from: str | None,
                    date_to: str | None) -> list[dict]:
    """The trend's own posts, re-read from the corpus for a date window.

    The stored snapshot is computed over the trend's whole life, so a date
    filter cannot be served from it: counts, source mix, charts and example
    posts all have to come from the posts themselves. Membership is fixed by
    the run - only the window changes.
    """
    keys = {(m["platform"], m["post_id"]) for m in members
            if m.get("platform") and m.get("post_id")}
    if not keys:
        return []
    clauses, params = [], [sorted({p for p, _ in keys}), sorted({i for _, i in keys})]
    if date_from:
        clauses.append("p.posted_at >= %s")
        params.append(date_from)
    if date_to:
        # inclusive of the end day, whatever time the post carries
        clauses.append("p.posted_at < (%s::date + 1)")
        params.append(date_to)
    where = (" AND " + " AND ".join(clauses)) if clauses else ""
    sql = f"""
        SELECT p.platform, p.post_id, p.source, p.caption, p.post_url,
               p.author_username, p.likes, p.comments, p.views,
               p.engagement_total, p.posted_at, p.media_keys
        FROM food_intel.trend_posts p
        WHERE p.platform = ANY(%s::text[]) AND p.post_id = ANY(%s::text[]){where}
    """
    with store.get_conn() as conn, conn.cursor() as cur:
        cur.execute("SET LOCAL statement_timeout = '25s'")
        cur.execute(sql, params)
        cols = [d[0] for d in cur.description]
        rows = [dict(zip(cols, r)) for r in cur.fetchall()]
    return [r for r in rows if (r["platform"], r["post_id"]) in keys]


def _recompute(posts: list[dict], keywords: list[str]) -> dict:
    """Rebuild the numbers and showcase posts a detail page renders."""
    from collections import Counter, defaultdict
    from services.food_intelligence_service.app.trends import metrics as M

    weekly: dict[str, dict] = defaultdict(lambda: {"post_count": 0, "engagement": 0,
                                                   "authors": set()})
    platform_mix: Counter = Counter()
    source_mix: Counter = Counter()
    authors: set = set()
    engagement = 0
    for p in posts:
        d = p["posted_at"].date() if hasattr(p["posted_at"], "date") else p["posted_at"]
        wk = M.week_start(d)
        weekly[wk]["post_count"] += 1
        weekly[wk]["engagement"] += p.get("engagement_total") or 0
        weekly[wk]["authors"].add(p["author_username"])
        platform_mix[p["platform"]] += 1
        source_mix[p.get("source") or "community"] += 1
        authors.add(p["author_username"])
        engagement += p.get("engagement_total") or 0

    def _example(p: dict) -> dict:
        return {"platform": p["platform"], "post_id": p["post_id"],
                "source": p.get("source") or "community",
                "author": p["author_username"], "caption": (p.get("caption") or "")[:280],
                "post_url": p.get("post_url"), "engagement": p.get("engagement_total") or 0,
                "likes": p.get("likes") or 0, "comments": p.get("comments") or 0,
                "views": p.get("views") or 0,
                "media_key": (p.get("media_keys") or [None])[0]}

    terms = set(keywords or [])
    by_source: dict[str, list[dict]] = {}
    for src in {p.get("source") or "community" for p in posts}:
        pool = [p for p in posts if (p.get("source") or "community") == src]
        by_source[src] = [_example(p) for p in M._pick_examples(pool, 3, terms)]
    return {
        "post_count": len(posts),
        "unique_authors": len(authors),
        "engagement_total": engagement,
        "platform_mix": dict(platform_mix),
        "source_mix": dict(source_mix),
        "timeline": [{"week_start": wk, "post_count": v["post_count"],
                      "engagement": v["engagement"], "unique_authors": len(v["authors"])}
                     for wk, v in sorted(weekly.items())],
        "example_posts": [_example(p) for p in M._pick_examples(posts, 6, terms)],
        "example_posts_by_source": by_source,
    }


def trend_detail(run_id: str, trend_id: str, date_from: str | None = None,
                 date_to: str | None = None) -> dict | None:
    columns = f"{_LIST_COLUMNS}, example_posts" + (", member_posts" if date_from or date_to else "")
    with store.get_conn() as conn, conn.cursor() as cur:
        for where, args in (
                ("run_id = %s AND trend_id = %s", (run_id, trend_id)),
                ("run_id = %s AND trend_id LIKE %s", (run_id, _slug(trend_id) + "--%")),
                ("trend_id = %s", (trend_id,))):
            cur.execute(f"SELECT {columns} FROM food_intel.trends WHERE {where} "
                        "ORDER BY created_at DESC LIMIT 1", args)
            row = cur.fetchone()
            if row:
                break
        else:
            return None
        cols = [d[0] for d in cur.description]
        t = _loads(dict(zip(cols, row)))

    # example_posts is {"top": [...], "by_source": {...}}; older runs stored a flat list.
    ep = t["example_posts"]
    top = ep["top"] if isinstance(ep, dict) else ep
    by_source = ep.get("by_source", {}) if isinstance(ep, dict) else {}

    def _sign(posts: list[dict]) -> list[dict]:
        return [{**p, "media_url": _media_url(p.get("media_key"))} for p in posts]

    _annotate_momentum_one(t)
    detail = _trend_row(t)
    windowed = None
    if date_from or date_to:
        windowed = _recompute(_posts_in_range(t.get("member_posts") or [],
                                              date_from, date_to),
                              t["narrative"].get("keywords") or [])
        top = windowed["example_posts"]
        by_source = windowed["example_posts_by_source"]

    detail.update({
        "metrics": t["metrics"],
        "timeline": t["timeline"],
        "related_themes": t["narrative"].get("related_themes") or [],
        "product_entities": t["narrative"].get("product_entities") or [],
        "keywords": t["narrative"].get("keywords") or [],
        "unique_authors": t["unique_authors"],
        "example_posts": _sign(top),
        "example_posts_by_source": {src: _sign(posts) for src, posts in by_source.items()},
        "search_timeline": None,   # no food search-interest source yet; UI shows empty state
        "date_from": date_from,
        "date_to": date_to,
    })
    if windowed is not None:
        # Everything the page renders is replaced, not merged: a mix of
        # windowed counts and full-history charts would be unreadable.
        detail.update({
            "post_count": windowed["post_count"],
            "unique_authors": windowed["unique_authors"],
            "timeline": windowed["timeline"],
            "source_mix": windowed["source_mix"],
            "metrics": {**t["metrics"],
                        "engagement_total": windowed["engagement_total"],
                        "platform_mix": windowed["platform_mix"],
                        "source_mix": windowed["source_mix"]},
            "platforms": sorted(windowed["platform_mix"].keys()),
        })
    if t["level"] == "umbrella":
        member_ids = t["narrative"].get("member_trend_ids") or []
        if member_ids:
            with store.get_conn() as conn, conn.cursor() as cur:
                cur.execute(f"SELECT {_LIST_COLUMNS} FROM food_intel.trends "
                            "WHERE run_id = %s AND trend_id = ANY(%s) ORDER BY growth_index DESC",
                            (run_id, member_ids))
                cols = [d[0] for d in cur.description]
                detail["members"] = [_trend_row(_loads(dict(zip(cols, r)))) for r in cur.fetchall()]
        else:
            detail["members"] = []
    return detail
