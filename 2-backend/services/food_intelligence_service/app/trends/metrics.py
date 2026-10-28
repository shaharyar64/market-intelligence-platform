"""All trend numbers + trend-row assembly. SQL/numpy facts only — no LLM here."""
import hashlib
import logging
import re
from collections import Counter, defaultdict
from datetime import date, datetime, timedelta

logger = logging.getLogger("trends.metrics")


def run_token(run_id: str) -> str:
    """A short trend-id suffix unique to one run.

    This used to be `run_id[:8]`: "tracked-" for every tracked run and "sa-20261"
    for every SA run in late 2026. upsert_trends is ON CONFLICT (trend_id) DO
    UPDATE, so a later run with the same slug took over the earlier run's row and
    silently emptied it. Same fix as the real-estate service.
    """
    return hashlib.blake2s(run_id.encode("utf-8"), digest_size=4).hexdigest()


def assign_quadrant(volume_index: float, growth_index: float) -> str:
    if volume_index >= 50:
        return "slow-burner" if growth_index >= 50 else "mainstream"
    return "breakthrough" if growth_index >= 50 else "watchlist"


def percentile_index(values: list[float]) -> list[float]:
    n = len(values)
    if n == 0:
        return []
    if n == 1:
        return [50.0]
    order = sorted(range(n), key=lambda i: values[i])
    ranks = [0.0] * n
    i = 0
    while i < n:
        j = i
        while j + 1 < n and values[order[j + 1]] == values[order[i]]:
            j += 1
        avg_rank = (i + j) / 2.0
        for k in range(i, j + 1):
            ranks[order[k]] = avg_rank
        i = j + 1
    return [r / (n - 1) * 100.0 for r in ranks]


# Posts added to each side of the ratio before dividing. It stops a baseline of
# one post from producing a five-figure percentage: 1 -> 208 read as 20,700%
# raw, which is arithmetic, not a finding.
GROWTH_SMOOTHING = 5


def compute_growth_pct(recent: int, previous: int,
                       total_recent: int, total_previous: int,
                       cohort_size: int) -> float:
    """Change in the trend's SHARE of the conversation, as a percentage.

    Raw volume growth measures the scrape, not the category. Between the two
    windows in this corpus the total post count grew 4.1x, so every trend
    inherited that multiplier and the leaderboard read 22,300%, 20,700%,
    14,000% - all of it collection artefact. Comparing each trend's share of
    its own window cancels the common factor and leaves only movement relative
    to everything else, which is the question a category manager is asking.

    Both sides are smoothed, so a tiny baseline cannot dominate and the value
    is always defined - there is no divide-by-zero and therefore no sentinel.
    Floored at -100%: a share cannot fall further than to nothing.
    """
    pad = GROWTH_SMOOTHING
    share_recent = (recent + pad) / (total_recent + pad * cohort_size)
    share_previous = (previous + pad) / (total_previous + pad * cohort_size)
    if share_previous <= 0:
        return 0.0
    return max(-100.0, (share_recent / share_previous - 1.0) * 100.0)


def compute_momentum_pct(recent: int, previous: int,
                         total_recent: int, total_previous: int,
                         cohort_size: int) -> float:
    """Share of a trend's two-window presence falling in the recent window,
    0-100. 50 is flat, above is rising, below is falling."""
    pad = GROWTH_SMOOTHING
    share_recent = (recent + pad) / (total_recent + pad * cohort_size)
    share_previous = (previous + pad) / (total_previous + pad * cohort_size)
    both = share_recent + share_previous
    if both <= 0:
        return 50.0
    return max(0.0, min(100.0, 100.0 * share_recent / both))


def week_start(d: date) -> str:
    return (d - timedelta(days=d.weekday())).isoformat()


_TERM_STOPWORDS = {
    "and", "the", "with", "creations", "delights", "craze", "trends", "moments",
    "experiences", "collection", "varieties", "based", "adventures", "pairings",
    "lovers", "offers", "deals", "recipes", "food", "foods",
}


def topical_terms(name: str, narrative: dict) -> set[str]:
    terms = {k.lower() for k in (narrative.get("keywords") or [])[:10]}
    terms |= {e.lower() for e in (narrative.get("product_entities") or [])[:8]}
    terms |= {w.lower() for w in re.findall(r"[^\W\d_]{4,}", name, re.UNICODE)}
    return {t for t in terms if t and t not in _TERM_STOPWORDS}


def _mentions_topic(post: dict, terms: set[str]) -> bool:
    if not terms:
        return True
    blob = re.sub(r"[^\w\s]", " ", (post.get("caption") or "").lower(), flags=re.UNICODE)
    blob += " " + " ".join(t.lower() for t in (post.get("hashtags") or []))
    return any(t in blob for t in terms)


def _pick_examples(pool: list[dict], k: int, terms: set[str] | None = None) -> list[dict]:
    """Showcase posts that visibly demonstrate the trend, most-engaging first.

    Ranking on engagement alone surfaced whatever went viral inside a cluster,
    which is frequently its least typical post. Centrality was tried and
    rejected: in a noisy cluster the centroid describes the noise, so the
    correlation with topical relevance is weak and sometimes inverted.
    """
    if not pool:
        return []

    def by_engagement(items: list[dict]) -> list[dict]:
        """Showable posts first, then by engagement.

        A third of the community corpus has no media we can serve - its images
        sit in an Azure container that returns 409 and we hold no credentials
        for. Ranking on engagement alone filled whole trends with cards that
        render as empty boxes, which reads as a broken page rather than as a
        missing image. Engagement still decides the order; having something to
        show decides which group you are ordered within.
        """
        return sorted(items, key=lambda p: (0 if p.get("media_keys") else 1,
                                            -(p.get("engagement_total") or 0)))

    on_topic = by_engagement([p for p in pool if _mentions_topic(p, terms or set())])
    if len(on_topic) >= k:
        return on_topic[:k]
    chosen_ids = {(p["platform"], p["post_id"]) for p in on_topic}
    remainder = by_engagement([p for p in pool
                               if (p["platform"], p["post_id"]) not in chosen_ids])
    return (on_topic + remainder)[:k]


def _post_facts(posts: list[dict], as_of: date,
                terms: set[str] | None = None) -> dict:
    """Aggregate one trend's member posts into every fact the row needs."""
    d90 = as_of - timedelta(days=90)
    d56 = as_of - timedelta(days=56)
    d112 = as_of - timedelta(days=112)
    volume_raw = recent = prev = 0
    first_seen: date | None = None
    engagement = 0
    authors: set[str] = set()
    platform_counter: Counter = Counter()
    source_counter: Counter = Counter()
    weekly: dict[str, dict] = defaultdict(lambda: {"post_count": 0, "engagement": 0, "authors": set()})
    monthly: dict[str, dict] = defaultdict(lambda: {"post_count": 0, "engagement": 0, "authors": set()})

    for p in posts:
        d = p["posted_at"].date() if isinstance(p["posted_at"], datetime) else p["posted_at"]
        engagement += p.get("engagement_total") or 0
        first_seen = d if first_seen is None or d < first_seen else first_seen
        authors.add(p["author_username"])
        platform_counter[p["platform"]] += 1
        source_counter[p.get("source") or "community"] += 1
        if d > d90:
            volume_raw += 1
        if d > d56:
            recent += 1
        elif d > d112:
            prev += 1
        wk = week_start(d)
        weekly[wk]["post_count"] += 1
        weekly[wk]["engagement"] += p.get("engagement_total") or 0
        weekly[wk]["authors"].add(p["author_username"])
        mo = d.strftime("%Y-%m")
        monthly[mo]["post_count"] += 1
        monthly[mo]["engagement"] += p.get("engagement_total") or 0
        monthly[mo]["authors"].add(p["author_username"])

    timeline = [
        {"week_start": wk, "post_count": v["post_count"], "engagement": v["engagement"],
         "unique_authors": len(v["authors"])}
        for wk, v in sorted(weekly.items())
    ]
    # Calendar months, not rolling weeks. ISO weeks straddle month boundaries,
    # so "posts in June" cannot be derived from the weekly series.
    months = [
        {"month": mo, "post_count": v["post_count"], "engagement": v["engagement"],
         "unique_authors": len(v["authors"])}
        for mo, v in sorted(monthly.items())
    ]
    def _example(p: dict) -> dict:
        return {"platform": p["platform"], "post_id": p["post_id"],
                "source": p.get("source") or "community",
                "author": p["author_username"], "caption": (p.get("caption") or "")[:280],
                "post_url": p.get("post_url"), "engagement": p.get("engagement_total") or 0,
                "likes": p.get("likes") or 0, "comments": p.get("comments") or 0,
                "views": p.get("views") or 0,
                "media_key": (p.get("media_keys") or [None])[0]}

    ranked = _pick_examples(posts, 6, terms)
    by_source: dict[str, list[dict]] = {}
    for src in {p.get("source") or "community" for p in posts}:
        pool = [p for p in posts if (p.get("source") or "community") == src]
        by_source[src] = [_example(p) for p in _pick_examples(pool, 3, terms)]
    return {
        "volume_raw": volume_raw,
        "engagement_total": engagement,
        "unique_authors": len(authors),
        "post_count": len(posts),
        "platform_mix": dict(platform_counter),
        "source_mix": dict(source_counter),
        "timeline": timeline,
        "example_posts": [_example(p) for p in ranked[:6]],
        "example_posts_by_source": by_source,
        "recent_posts": recent,
        "previous_posts": prev,
        "months": months,
        "first_post": first_seen.isoformat() if first_seen else None,
        # Genuinely new: nothing before the recent window. An empty PREVIOUS
        # window is not the same thing - a trend can have years of history and
        # still be silent for one 56-day stretch, and calling that "new" was
        # wrong for trends dating back to 2023.
        "is_new": bool(first_seen and first_seen > d56),
        "member_posts": [{"platform": p["platform"], "post_id": p["post_id"],
                          "source": p.get("source") or "community",
                          "posted_at": (p["posted_at"].date().isoformat()
                                        if isinstance(p["posted_at"], datetime)
                                        else str(p["posted_at"]))} for p in posts],
    }


def build_trend_rows(run_id: str, groups: dict[str, dict], umbrellas: list[dict],
                     as_of: date) -> list[dict]:
    """groups: {micro_trend_id: {"named": ClusterName-like dict, "keywords": [...],
                                 "posts": [post dicts]}}
       umbrellas: [{"name","summary","members":[micro ids]}]
       Returns rows for store.upsert_trends (micro + umbrella), indices ranked per level."""
    rows: list[dict] = []

    def base_row(trend_id: str, level: str, name: str, narrative: dict,
                 facts: dict, parent: str | None) -> dict:
        return {
            "trend_id": trend_id, "run_id": run_id, "level": level,
            "parent_trend_id": parent, "name": name,
            "quadrant": "watchlist", "volume_index": 0.0, "growth_index": 0.0,
            "post_count": facts["post_count"], "unique_authors": facts["unique_authors"],
            "narrative": narrative,
            "metrics": {"volume_raw": facts["volume_raw"],
                        "growth_pct": 0.0,   # filled in per level below
                        "engagement_total": facts["engagement_total"],
                        "platform_mix": facts["platform_mix"],
                        "source_mix": facts["source_mix"],
                        "months": facts["months"],
                        "recent_posts": facts["recent_posts"],
                        "previous_posts": facts["previous_posts"],
                        "first_post": facts["first_post"],
                        "is_new": facts["is_new"],
                        "as_of": as_of.isoformat()},
            "timeline": facts["timeline"],
            "example_posts": {"top": facts["example_posts"],
                              "by_source": facts["example_posts_by_source"]},
            "member_posts": facts["member_posts"],
        }

    micro_ids = list(groups.keys())
    for tid in micro_ids:
        g = groups[tid]
        named = g["named"]
        terms = topical_terms(named["name"], {**named, "keywords": g.get("keywords", [])})
        facts = _post_facts(g["posts"], as_of, terms)
        narrative = {"summary": named["summary"],
                     "related_themes": named["related_themes"],
                     "product_entities": named["product_entities"],
                     "keywords": g.get("keywords", []),
                     "naming_confidence": named["confidence"]}
        rows.append(base_row(tid, "micro", named["name"], narrative, facts, None))

    umbrella_rows: list[dict] = []
    for u in umbrellas:
        posts = [p for m in u["members"] if m in groups for p in groups[m]["posts"]]
        if not posts:
            continue
        member_terms: set[str] = set()
        for m in u["members"]:
            if m in groups:
                member_terms |= topical_terms(groups[m]["named"]["name"],
                                              {**groups[m]["named"],
                                               "keywords": groups[m].get("keywords", [])})
        facts = _post_facts(posts, as_of, member_terms)
        uid = f"u-{u['slug']}--{run_token(run_id)}"
        narrative = {"summary": u["summary"], "related_themes": [],
                     "product_entities": [], "keywords": [],
                     "member_trend_ids": u["members"], "naming_confidence": None}
        umbrella_rows.append(base_row(uid, "umbrella", u["name"], narrative, facts, None))
        for m in u["members"]:
            for r in rows:
                if r["trend_id"] == m:
                    r["parent_trend_id"] = uid
    rows.extend(umbrella_rows)

    # percentile indices + quadrant, ranked within each level
    for level in ("micro", "umbrella"):
        level_rows = [r for r in rows if r["level"] == level]
        if not level_rows:
            continue
        vol_idx = percentile_index([float(r["metrics"]["volume_raw"]) for r in level_rows])
        # Share of the conversation needs the whole level's volume, so growth
        # is computed here rather than per trend.
        total_recent = sum(r["metrics"]["recent_posts"] for r in level_rows)
        total_previous = sum(r["metrics"]["previous_posts"] for r in level_rows)
        for r in level_rows:
            r["metrics"]["growth_pct"] = round(compute_growth_pct(
                r["metrics"]["recent_posts"], r["metrics"]["previous_posts"],
                total_recent, total_previous, len(level_rows)), 2)
        gro_idx = percentile_index([float(r["metrics"]["growth_pct"])
                                    for r in level_rows])
        for r, vi, gi in zip(level_rows, vol_idx, gro_idx):
            r["volume_index"] = round(vi, 2)
            r["growth_index"] = round(gi, 2)
            r["quadrant"] = assign_quadrant(vi, gi)

    return rows
