"""Trend pipeline orchestrator.

Stages: embed -> cluster -> name -> group -> metrics.
embed is incremental (skips what is stored); cluster/name/group
results are cached per run under .trend_cache/{run_key}/run_{run_id}.json so
later stages can re-run without repeating LLM spend.

Usage:
    python -m services.food_intelligence_service.app.trends.run                 # all stages
    python -m services.food_intelligence_service.app.trends.run --stages embed --limit 100
    python -m services.food_intelligence_service.app.trends.run --stages metrics --run-id <id>
"""
import argparse
import json
import logging
from datetime import datetime, timezone
from pathlib import Path

import numpy as np
from openai import OpenAI

from services.food_intelligence_service.app.core.config import get_settings
from services.food_intelligence_service.app.trends import (
    clusterer, documents, embedder, metrics, namer, prompts, store, trend_embedding,
)

logger = logging.getLogger("trends.run")
ALL_STAGES = ["embed", "cluster", "name", "group", "assign", "metrics", "interpret",
              "trend_embed"]


def resolve_run_key(cohort: str, tracked: bool, country: str | None) -> str:
    """Names the run and its cache directory, so a country run never reuses
    another market's cached clusters or naming."""
    if country:
        return country.lower()
    return "tracked" if tracked else cohort


def build_scope(tracked: bool, country: str | None,
                tracked_sources: list[str], exclude_authors: list[str]) -> dict:
    """The run's post scope, threaded through discovery, assignment and metrics so
    all three read the same post set."""
    if not tracked:
        return {}
    return {"sources": list(tracked_sources), "country": country,
            "exclude_authors": list(exclude_authors)}


def anchor_date(posts: list[dict]):
    community_dates = [p["posted_at"] for p in posts
                       if (p.get("source") or "community") == "community"]
    if len(community_dates) * 2 > len(posts):
        return max(community_dates).date()
    return max(p["posted_at"] for p in posts).date()


def stamp_country(rows: list[dict], country: str | None) -> None:
    for r in rows:
        r["country"] = country


def _run_cache(run_key: str, run_id: str) -> Path:
    p = Path(get_settings().TREND_CACHE_DIR) / run_key
    p.mkdir(parents=True, exist_ok=True)
    return p / f"run_{run_id}.json"


def _load_run(run_key: str, run_id: str) -> dict:
    path = _run_cache(run_key, run_id)
    if path.exists():
        return json.loads(path.read_text(encoding="utf-8"))
    return {}


def _save_run(run_key: str, run_id: str, state: dict) -> None:
    _run_cache(run_key, run_id).write_text(
        json.dumps(state, ensure_ascii=False), encoding="utf-8")


def stage_cluster(posts: list[dict], min_cluster_size: int,
                  cohort: str, run_id: str, merge_distance: float = 0.10) -> dict:
    vectors = np.array([p["vec"] for p in posts], dtype=np.float32)
    docs = [embedder.build_embed_text(p["caption"], p.get("hashtags")) for p in posts]
    model_path = str(Path(get_settings().TREND_CACHE_DIR) / cohort / f"bertopic_{run_id}")
    try:
        # Outlier rescue was written and never switched on: 21,358 of 51,603
        # posts sat in -1 waiting for it. HDBSCAN refuses anything it cannot fit
        # into a dense group, which on short social text is most of the corpus;
        # reassigning those by embedding distance is what the stage was for.
        labels, keywords = clusterer.cluster_via_bertopic(
            docs, vectors, min_cluster_size=min_cluster_size, save_path=model_path,
            rescue_outliers=True)
        algorithm = "bertopic(umap+hdbscan)"
    except ImportError:
        logger.warning("bertopic unavailable — falling back to direct umap+hdbscan")
        labels = clusterer.cluster_vectors(vectors, min_cluster_size=min_cluster_size)
        keywords = clusterer.ctfidf_keywords(docs, labels)
        algorithm = "umap+hdbscan"
    labels, merged = clusterer.merge_close_clusters(
        labels, max_distance=merge_distance, vectors=vectors)
    if merged:
        logger.info("merged %s near-duplicate clusters (centroids within %.2f)",
                    merged, merge_distance)
        keywords = clusterer.ctfidf_keywords(docs, labels)
    cent = clusterer.centrality(vectors, labels)
    cents = clusterer.centroids(vectors, labels)
    member_sims = cent[labels != -1]
    floor = float(np.percentile(member_sims, 10)) if len(member_sims) else 0.0
    return {
        "labels": {f"{p['platform']}:{p['post_id']}": int(l) for p, l in zip(posts, labels)},
        "keywords": {str(k): v for k, v in keywords.items()},
        "centrality": {f"{p['platform']}:{p['post_id']}": round(float(c), 5)
                       for p, c in zip(posts, cent)},
        "centroids": {str(k): [round(float(x), 5) for x in v] for k, v in cents.items()},
        "belong_floor": round(floor, 5),
        "n_clusters": len(set(labels.tolist()) - {-1}),
        "noise": int((labels == -1).sum()),
        "algorithm": algorithm,
    }


def stage_name(posts: list[dict], state: dict, client, model: str,
               min_posts: int, min_authors: int, run_id: str) -> dict:
    labels = state["cluster"]["labels"]
    cent = state["cluster"]["centrality"]
    by_cluster: dict[int, list[dict]] = {}
    for p in posts:
        label = labels.get(f"{p['platform']}:{p['post_id']}", -1)
        if label >= 0:
            by_cluster.setdefault(label, []).append(p)

    named: dict[str, dict] = {}
    stats = {"named": 0, "skipped_small": 0, "skipped_incoherent": 0}
    used_slugs: set[str] = set()
    for label, members in sorted(by_cluster.items()):
        authors = {m["author_username"] for m in members}
        # min_authors is 0 for tracked runs (see call site): the floor is
        # calibrated for the large community corpus, where it screens out
        # single-account spam clusters, and a small tracked corpus cannot
        # clear it at all. Do not "restore" it here — that was deliberate.
        if len(members) < min_posts or len(authors) < min_authors:
            stats["skipped_small"] += 1
            continue
        # evidence: top 25 captions by centrality x engagement
        def rank(m):
            c = cent.get(f"{m['platform']}:{m['post_id']}", 0.0)
            return -(c * (1 + (m.get("engagement_total") or 0)))
        top = sorted(members, key=rank)[:25]
        tags: dict[str, int] = {}
        for m in members:
            for t in (m.get("hashtags") or []):
                tags[t] = tags.get(t, 0) + 1
        top_tags = [t for t, _ in sorted(tags.items(), key=lambda kv: -kv[1])[:10]]
        keywords = state["cluster"]["keywords"].get(str(label), [])

        result = namer.name_cluster([m["caption"] for m in top], top_tags, keywords,
                                    client, model)
        if not result.is_coherent:
            stats["skipped_incoherent"] += 1
            continue
        slug = namer.slugify(result.name) or f"cluster-{label}"
        if slug in used_slugs:
            slug = f"{slug}-{label}"
        used_slugs.add(slug)
        trend_id = f"{slug}--{metrics.run_token(run_id)}"
        named[trend_id] = {
            "cluster_label": label,
            "name": result.name, "summary": result.summary,
            "related_themes": result.related_themes,
            "product_entities": result.product_entities,
            "confidence": result.confidence,
            "keywords": keywords,
        }
        stats["named"] += 1
        logger.info("cluster %s -> %s (%s posts)", label, result.name, len(members))
    state["named"] = named
    return stats


def stage_assign(cohort: str, run_id: str, state: dict, tag: str,
                 scope: dict | None = None) -> dict:
    """Attach any tracked post discovery did not already cluster to the run's topics.

    They join trends discovered from community posts and never create new ones.
    scope is the run's own post scope (sources, country, excluded authors) — a
    country-scoped run must not pull the other market's posts in here.

    Under the default run discovery only sees community posts, so this still
    fetches and assigns every brand/influencer post. Under a tracked or country
    run discovery already saw the same scope and fitted those posts directly,
    so this usually has nothing left to do.

    Every assignment must clear a belonging test: the post's cosine similarity
    to its topic centroid has to reach the 10th percentile of what the topic's
    own community members scored. BERTopic's transform hands every post its
    nearest topic no matter how far away it sits, so without the gate a dairy
    brand's Ramadan greeting lands in whichever food trend it drifts closest to
    and inflates that trend's counts. The food filter upstream removes posts
    that are not about food at all; this removes posts that are about food but
    not about this topic. Community posts never needed it: a non-food cluster is
    refused a name by the food-domain gate in the naming prompt, but assigned
    posts skip naming entirely, so this is the only place they are checked.
    """
    settings = get_settings()
    posts = store.fetch_cohort_posts("all", tag, **(scope or {"sources": ["brand", "influencer"]}))
    already = set(state.get("cluster", {}).get("labels", {}))
    posts = [p for p in posts if f"{p['platform']}:{p['post_id']}" not in already]
    if not posts:
        return {"assigned": 0, "note": "discovery already placed every tracked post"}
    model_path = str(Path(settings.TREND_CACHE_DIR) / cohort / f"bertopic_{run_id}")
    from bertopic import BERTopic
    topic_model = BERTopic.load(model_path)
    docs = [embedder.build_embed_text(p["caption"], p.get("hashtags")) for p in posts]
    vectors = np.array([p["vec"] for p in posts], dtype=np.float64)
    topics, _ = topic_model.transform(docs, embeddings=vectors)

    cluster = state["cluster"]
    centroids = {int(k): np.array(v, dtype=np.float64)
                 for k, v in cluster.get("centroids", {}).items()}
    floor = cluster.get("belong_floor", 0.0)
    norms = np.maximum(np.linalg.norm(vectors, axis=1), 1e-12)

    labels: dict[str, int] = {}
    rejected = 0
    for i, (p, topic) in enumerate(zip(posts, topics)):
        topic = int(topic)
        centroid = centroids.get(topic)
        if topic >= 0 and centroid is not None:
            if float(vectors[i] @ centroid) / norms[i] < floor:
                topic = -1
                rejected += 1
        labels[f"{p['platform']}:{p['post_id']}"] = topic
    assigned = sum(1 for t in labels.values() if t >= 0)
    logger.info("assign: %s of %s tracked posts joined trends "
                "(%s rejected below belonging floor %.3f)",
                assigned, len(posts), rejected, floor)
    return {"labels": labels, "assigned": assigned, "noise": len(labels) - assigned,
            "rejected_off_topic": rejected, "belong_floor": floor}


def stage_interpret(run_id: str, client, model: str) -> dict:
    """Author narrative.opportunity_summary per trend from its computed metrics.
    The model interprets numbers we supply; it never invents any."""
    import json as _json
    rows = []
    with store.get_conn() as conn, conn.cursor() as cur:
        cur.execute("""SELECT trend_id, name, level, quadrant, post_count,
                              unique_authors, narrative, metrics
                       FROM food_intel.trends WHERE run_id = %s""", (run_id,))
        cols = [d[0] for d in cur.description]
        for r in cur.fetchall():
            row = dict(zip(cols, r))
            for c in ("narrative", "metrics"):
                if isinstance(row[c], str):
                    row[c] = _json.loads(row[c])
            rows.append(row)
    done = 0
    for row in rows:
        if row["narrative"].get("opportunity_summary"):
            continue
        payload = {
            "name": row["name"], "level": row["level"], "summary": row["narrative"].get("summary"),
            "quadrant": row["quadrant"],
            "post_count": row["post_count"], "unique_creators": row["unique_authors"],
            "growth_pct_8w": row["metrics"].get("growth_pct"),
            "platform_mix": row["metrics"].get("platform_mix"),
            "source_mix": row["metrics"].get("source_mix"),
        }
        try:
            resp = client.chat.completions.create(
                model=model, temperature=0,
                response_format={"type": "json_object"},
                messages=[{"role": "system", "content": prompts.OPPORTUNITY_SYSTEM},
                          {"role": "user", "content": _json.dumps(payload, ensure_ascii=False)}],
            )
            summary = _json.loads(resp.choices[0].message.content).get("opportunity_summary", "")
        except Exception as exc:
            logger.warning("interpret failed for %s: %s", row["trend_id"], exc)
            continue
        if summary:
            row["narrative"]["opportunity_summary"] = summary
            store.update_trend_narrative(row["trend_id"], row["narrative"])
            done += 1
    return {"interpreted": done, "total": len(rows)}


MISC_UMBRELLA = "Misc (needs review)"


def _place_strays(umbrellas: list, named: dict, centroids: dict) -> list:
    """Move trends the grouping model skipped into their nearest real umbrella.

    The model left 22 of 88 micro-trends unplaced, and a bucket named
    "Misc (needs review)" holding a quarter of the corpus is worse than a rough
    home for each one. Placement is by cosine distance between the trend's
    cluster centroid and the mean centroid of each umbrella's members — the same
    vectors the clustering already produced, so this adds no model calls and is
    deterministic.
    """
    misc = [u for u in umbrellas if u["name"] == MISC_UMBRELLA]
    real = [u for u in umbrellas if u["name"] != MISC_UMBRELLA]
    if not misc or not real:
        return umbrellas

    label_of = {tid: n["cluster_label"] for tid, n in named.items()}

    def centroid_for(trend_ids: list[str]):
        vecs = [centroids[str(label_of[t])] for t in trend_ids
                if t in label_of and str(label_of[t]) in centroids]
        if not vecs:
            return None
        mean = np.mean(np.array(vecs, dtype=np.float64), axis=0)
        norm = np.linalg.norm(mean)
        return mean / norm if norm else None

    targets = [(u, centroid_for(u["members"])) for u in real]
    targets = [(u, c) for u, c in targets if c is not None]
    if not targets:
        return umbrellas

    placed = 0
    for trend_id in misc[0]["members"]:
        own = centroid_for([trend_id])
        if own is None:
            targets[0][0]["members"].append(trend_id)
            placed += 1
            continue
        best = max(targets, key=lambda t: float(own @ t[1]))
        best[0]["members"].append(trend_id)
        placed += 1
    logger.info("placed %s stray micro-trends into their nearest umbrella", placed)
    return real


def stage_group(state: dict, client, model: str) -> dict:
    named = state["named"]
    label_counts: dict[int, int] = {}
    for label in state["cluster"]["labels"].values():
        label_counts[label] = label_counts.get(label, 0) + 1
    micro_summaries = [
        {"trend_id": tid, "name": n["name"], "summary": n["summary"],
         "keywords": n["keywords"], "post_count": label_counts.get(n["cluster_label"], 0)}
        for tid, n in named.items()
    ]
    umbrellas = namer.group_umbrellas(micro_summaries, client, model)
    rows = [
        {"name": u.name, "slug": namer.slugify(u.name) or f"umbrella-{i}",
         "summary": u.summary, "members": u.members}
        for i, u in enumerate(umbrellas)
    ]
    state["umbrellas"] = _place_strays(rows, named, state["cluster"].get("centroids", {}))
    return {"umbrellas": len(state["umbrellas"])}


def stage_metrics(posts: list[dict], state: dict, run_key: str, run_id: str,
                  country: str | None = None, embed_tag: str | None = None) -> dict:
    settings = get_settings()
    labels = dict(state["cluster"]["labels"])
    labels.update(state.get("assign", {}).get("labels", {}))   # brand/influencer joins
    named = state["named"]

    label_to_tid = {n["cluster_label"]: tid for tid, n in named.items()}
    groups: dict[str, dict] = {tid: {"named": n, "keywords": n["keywords"], "posts": []}
                               for tid, n in named.items()}
    for p in posts:
        label = labels.get(f"{p['platform']}:{p['post_id']}", -1)
        tid = label_to_tid.get(label)
        if tid:
            groups[tid]["posts"].append(p)

    for g in groups.values():
        members = g["posts"]
        if not members:
            continue
        vecs = np.array([m["vec"] for m in members], dtype=np.float32)
        centroid = vecs.mean(axis=0)
        norm = np.linalg.norm(centroid)
        if norm == 0:
            continue
        sims = (vecs @ centroid) / np.maximum(np.linalg.norm(vecs, axis=1) * norm, 1e-12)
        for m, s in zip(members, sims):
            m["_centrality"] = float(s)

    # Anchored on the community corpus, not on the newest post of any source.
    # The two corpora were collected at different times: community scraping
    # stopped on 2026-06-23, the tracked accounts were crawled through 07-26.
    # Taking the overall maximum would end the 56-day recency window a month
    # past the point where community posts exist, leaving that window 40% empty
    # of the source that supplies 99% of the volume — and every community-driven
    # trend would read as collapsing. The windows end where the corpus is
    # complete; tracked posts newer than that still count in totals, just not in
    # the recency comparison.
    # That reasoning holds only while community supplies most of the volume. In
    # an enriched run community is a minority (1,326 of 6,834 posts), and pinning
    # to its last date put the run's "data to" two quarters behind its own
    # October posts. So anchor on community only when it is the majority.
    as_of = anchor_date(posts)
    state["provenance"] = {
        "embed_model": embed_tag or store.model_tag(settings.TREND_EMBED_MODEL,
                                                     settings.TREND_EMBED_DIM),
        "naming_model": settings.TREND_NAMING_MODEL or settings.OPENAI_MODEL,
        "prompt_version": settings.TREND_PROMPT_VERSION,
        "computed_at": datetime.now(timezone.utc).isoformat(),
    }
    _save_run(run_key, run_id, state)
    rows = metrics.build_trend_rows(run_id, groups, state.get("umbrellas", []),
                                    as_of)
    stamp_country(rows, country)
    written = store.replace_run(run_id, rows)
    return {"trends_written": written, "as_of": str(as_of),
            "micro": sum(1 for r in rows if r["level"] == "micro"),
            "umbrella": sum(1 for r in rows if r["level"] == "umbrella")}


def main():
    parser = argparse.ArgumentParser(description="Run the trend generation pipeline.")
    parser.add_argument("--cohort", default=None)
    parser.add_argument("--stages", default=",".join(ALL_STAGES))
    parser.add_argument("--run-id", default=None)
    parser.add_argument("--min-cluster-size", type=int, default=None)
    parser.add_argument("--limit", type=int, default=None, help="Cap embed work")
    parser.add_argument("--sample-threshold", type=int, default=None,
                        help="Reuse an exact sample cut-off instead of resolving one "
                             "from today's corpus size (see store.resolve_sample_threshold)")
    parser.add_argument("--sample", type=int, default=None,
                        help="Scope the whole run to a representative sample of community "
                             "posts — cluster and metrics both use this same subset")
    parser.add_argument("--merge-distance", type=float, default=0.10)
    parser.add_argument("--date-from", default=None)
    parser.add_argument("--date-to", default=None)
    parser.add_argument("--exclude-container", action="append", default=None)
    parser.add_argument("--tracked", action="store_true",
                        help="Brand and influencer posts only (TREND_TRACKED_SOURCES).")
    parser.add_argument("--country", choices=["SA", "AE"], default=None,
                        help="Scope the run to one market; implies --tracked. The run's "
                             "trends are written with that country.")
    parser.add_argument("--documents", choices=["analysis", "caption"], default=None,
                        help="Cluster analysis-derived semantic documents or raw captions. "
                             "Defaults to TREND_DOCUMENT_SOURCE.")
    parser.add_argument("--log-level", default="INFO")
    args = parser.parse_args()

    logging.basicConfig(level=getattr(logging, args.log_level.upper(), logging.INFO),
                        format="%(asctime)s %(levelname)s %(name)s: %(message)s")
    settings = get_settings()
    if not settings.OPENAI_API_KEY:
        raise SystemExit("OPENAI_API_KEY is not set.")
    cohort = args.cohort or settings.TREND_COHORT
    exclude_containers = args.exclude_container or None
    mcs = args.min_cluster_size or settings.TREND_MIN_POSTS
    country = args.country
    tracked = args.tracked or bool(country)
    scope = build_scope(tracked, country, settings.TREND_TRACKED_SOURCES,
                        settings.TREND_EXCLUDE_AUTHORS)
    use_documents = (args.documents or settings.TREND_DOCUMENT_SOURCE) == "analysis"
    tag = (documents.document_tag() if use_documents
           else store.model_tag(settings.TREND_EMBED_MODEL, settings.TREND_EMBED_DIM))
    run_key = resolve_run_key(cohort, tracked, country)
    run_id = args.run_id or f"{run_key}-{datetime.now(timezone.utc):%Y%m%d%H%M}"
    stages = [s.strip() for s in args.stages.split(",") if s.strip()]
    client = OpenAI(api_key=settings.OPENAI_API_KEY, max_retries=8, timeout=120)
    naming_model = settings.TREND_NAMING_MODEL or settings.OPENAI_MODEL
    logger.info("run_id=%s run_key=%s tag=%s tracked=%s country=%s",
                run_id, run_key, tag, tracked, country)

    summary: dict = {"run_id": run_id, "cohort": cohort}
    state = _load_run(run_key, run_id)
    state["min_cluster_size"] = mcs
    _community: list[dict] | None = None
    _all_sources: list[dict] | None = None

    # Resolved once and kept with the run. The cut-off derives from the corpus
    # size, so re-running a later stage after the corpus has grown would other-
    # wise sample a different set of posts than the one that was clustered.
    sample_threshold = args.sample_threshold or state.get("sample_threshold")
    if args.sample and sample_threshold is None:
        sample_threshold = store.resolve_sample_threshold(cohort, args.sample)
    if sample_threshold is not None:
        state["sample_threshold"] = sample_threshold
        logger.info("sample cut-off %s (%.4f%% of the community corpus)",
                    sample_threshold, sample_threshold / 2**32 * 100)

    def community_posts() -> list[dict]:
        """The discovery stage's post set.

        Trends are DISCOVERED from community posts only — except under a
        tracked or country run, where discovery spans the whole scope
        (brand and influencer posts included) so those accounts are fitted
        directly instead of only transformed onto it in stage_assign.

        For the 'all' cohort untracked, community posts are filtered out of
        the all-sources set rather than fetched separately. Pulling vectors
        from RDS is the pipeline's slowest step by a wide margin — 28 minutes
        for 116k posts — and the two fetches used to overlap almost entirely,
        paying it twice.
        """
        nonlocal _community
        if _community is None:
            if tracked:
                _community = all_source_posts()
            elif cohort == "all":
                _community = [p for p in all_source_posts() if p["source"] == "community"]
            else:
                _community = store.fetch_cohort_posts(cohort, tag, sources=["community"],
                                                      sample=args.sample,
                                                      sample_threshold=sample_threshold,
                                                      date_from=args.date_from,
                                                      date_to=args.date_to,
                                                      exclude_containers=exclude_containers)
            logger.info("loaded %s embedded community posts%s", len(_community),
                        f" (sampled from {store.count_community_posts(cohort):,})"
                        if args.sample else "")
        return _community

    def all_source_posts() -> list[dict]:
        """Metrics COUNT every post in scope, whichever source.

        Under --sample that scope is the sampled community posts plus all brand
        and influencer posts — the same community subset the fit saw, because
        the sample predicate is derived from the post's identity, not from the
        source filter this call happens to pass.
        """
        nonlocal _all_sources
        if _all_sources is None:
            _all_sources = store.fetch_cohort_posts("all", tag, sample=args.sample,
                                                    sample_threshold=sample_threshold,
                                                    date_from=args.date_from,
                                                    date_to=args.date_to,
                                                    exclude_containers=exclude_containers,
                                                    **scope)
            logger.info("loaded %s embedded posts (all sources)", len(_all_sources))
        return _all_sources

    if "embed" in stages:
        summary["embed"] = (documents.run_embedding(limit=args.limit) if use_documents
                            else embedder.run_embedding(cohort, limit=args.limit))
    if "cluster" in stages:
        state["cluster"] = stage_cluster(community_posts(), mcs, cohort, run_id,
                                         merge_distance=args.merge_distance)
        _save_run(run_key, run_id, state)
        summary["cluster"] = {k: state["cluster"][k] for k in ("n_clusters", "noise", "algorithm")}
    if "name" in stages:
        if "cluster" not in state:
            raise SystemExit(f"run {run_id} has no cluster stage — run cluster first")
        # Tracked runs apply no author floor, matching real estate's pipeline:
        # TREND_MIN_AUTHORS is calibrated for the ~415k-post community corpus
        # and a tracked run's much smaller corpus cannot clear it.
        min_authors = 0 if tracked else settings.TREND_MIN_AUTHORS
        summary["name"] = stage_name(community_posts(), state, client, naming_model,
                                     settings.TREND_MIN_POSTS, min_authors, run_id)
        _save_run(run_key, run_id, state)
    if "group" in stages:
        if not state.get("named"):
            raise SystemExit(f"run {run_id} has no named trends — run name first")
        summary["group"] = stage_group(state, client, naming_model)
        _save_run(run_key, run_id, state)
    if "assign" in stages:
        if "cluster" not in state:
            raise SystemExit(f"run {run_id} has no cluster stage — run cluster first")
        result = stage_assign(cohort, run_id, state, tag, scope or None)
        if "labels" in result:
            state["assign"] = {"labels": result.pop("labels"), **result}
            _save_run(run_key, run_id, state)
        summary["assign"] = result
    if "metrics" in stages:
        if not state.get("named"):
            raise SystemExit(f"run {run_id} has no named trends — run name first")
        summary["metrics"] = stage_metrics(all_source_posts(), state, run_key, run_id,
                                           country=country, embed_tag=tag)
    if "interpret" in stages:
        summary["interpret"] = stage_interpret(run_id, client, naming_model)

    if "trend_embed" in stages:
        summary["trend_embed"] = trend_embedding.run(run_id)

    print("\nPipeline summary:")
    for k, v in summary.items():
        print(f"  {k}: {v}")


if __name__ == "__main__":
    main()
