"""Trend pipeline orchestrator.

Stages: embed -> cluster -> name -> group -> metrics.
embed is incremental (skips what is stored); cluster/name/group
results are cached per run under .trend_cache/{cohort}/run_{run_id}.json so
later stages can re-run without repeating LLM spend.

Usage:
    python -m services.trends_real_estate_service.app.trends.run                 # all stages
    python -m services.trends_real_estate_service.app.trends.run --stages embed --limit 100
    python -m services.trends_real_estate_service.app.trends.run --stages metrics --run-id <id>
"""
import argparse
import json
import logging
from datetime import datetime, timezone
from pathlib import Path

import numpy as np
from openai import OpenAI

from services.trends_real_estate_service.app.core.config import get_settings
from services.trends_real_estate_service.app.trends import (
    clusterer,
    documents,
    embedder,
    metrics,
    namer,
    store,
)

logger = logging.getLogger("trends.run")
ALL_STAGES = ["embed", "cluster", "name", "group", "assign", "metrics", "interpret"]


def _run_cache(cohort: str, run_id: str) -> Path:
    p = Path(get_settings().TREND_CACHE_DIR) / cohort
    p.mkdir(parents=True, exist_ok=True)
    return p / f"run_{run_id}.json"


def _load_run(cohort: str, run_id: str) -> dict:
    path = _run_cache(cohort, run_id)
    if path.exists():
        return json.loads(path.read_text(encoding="utf-8"))
    return {}


def _save_run(cohort: str, run_id: str, state: dict) -> None:
    _run_cache(cohort, run_id).write_text(
        json.dumps(state, ensure_ascii=False), encoding="utf-8")


def _text(p: dict) -> str:
    return p.get("document") or embedder.build_embed_text(p["caption"], p.get("hashtags"))


def _labels_of(named: dict) -> dict[int, str]:
    out: dict[int, str] = {}
    for tid, n in named.items():
        for label in [n["cluster_label"], *n.get("merged_labels", [])]:
            out[int(label)] = tid
    return out


def _accounts(posts: list[dict], companies: dict[tuple[str, str], str]) -> list[str]:
    out = []
    for p in posts:
        user = (p.get("author_username") or "").strip().lower()
        if not user:
            out.append(f"post:{p['platform']}:{p['post_id']}")
        else:
            out.append(companies.get((p["platform"], user), f"user:{user}"))
    return out


def _account_bias_path(cohort: str, run_id: str) -> Path:
    return Path(get_settings().TREND_CACHE_DIR) / cohort / f"account_bias_{run_id}.npz"


def _save_account_bias(path: Path, offsets: dict[str, np.ndarray]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    keys = sorted(offsets)
    np.savez(path, accounts=np.array(keys), offsets=np.stack([offsets[k] for k in keys]))


def _load_account_bias(path: Path) -> dict[str, np.ndarray] | None:
    if not path.exists():
        return None
    with np.load(path, allow_pickle=False) as data:
        return {str(k): v for k, v in zip(data["accounts"], data["offsets"], strict=True)}


def stage_cluster(posts: list[dict], min_cluster_size: int,
                  cohort: str, run_id: str, merge_distance: float = 0.10,
                  rescue_percentile: float | None = None) -> dict:
    settings = get_settings()
    if rescue_percentile is None:
        rescue_percentile = settings.TREND_OUTLIER_RESCUE_PERCENTILE
    accounts = _accounts(posts, store.fetch_company_handles())
    raw = np.array([p["vec"] for p in posts], dtype=np.float32)
    offsets = clusterer.account_bias(raw, accounts, shrink=settings.TREND_ACCOUNT_BIAS_SHRINK)
    vectors = clusterer.remove_account_bias(raw, accounts, offsets)
    del raw
    _save_account_bias(_account_bias_path(cohort, run_id), offsets)
    docs = [_text(p) for p in posts]
    model_path = str(Path(get_settings().TREND_CACHE_DIR) / cohort / f"bertopic_{run_id}")
    try:
        # Outlier rescue was written and never switched on: 21,358 of 51,603
        # posts sat in -1 waiting for it. HDBSCAN refuses anything it cannot fit
        # into a dense group, which on short social text is most of the corpus;
        # reassigning those by embedding distance is what the stage was for.
        labels, _ = clusterer.cluster_via_bertopic(
            docs, vectors, min_cluster_size=min_cluster_size, save_path=model_path,
            rescue_outliers=True,
            outlier_percentile=rescue_percentile)
        algorithm = "bertopic(umap+hdbscan)"
    except ImportError:
        logger.warning("bertopic unavailable — falling back to direct umap+hdbscan")
        labels = clusterer.cluster_vectors(vectors, min_cluster_size=min_cluster_size)
        algorithm = "umap+hdbscan"
    labels, merged, label_remap = clusterer.merge_close_clusters(
        labels, max_distance=merge_distance, vectors=vectors)
    if merged:
        logger.info("merged %s near-duplicate clusters (centroids within %.2f)",
                    merged, merge_distance)
    keywords = clusterer.clean_keywords(
        docs, labels, accounts,
        max_account_share=settings.TREND_KEYWORD_MAX_ACCOUNT_SHARE,
        min_cluster_posts=settings.TREND_KEYWORD_MIN_CLUSTER_POSTS)
    cent = clusterer.centrality(vectors, labels)
    cents = clusterer.centroids(vectors, labels)
    # A floor PER TOPIC, not one number for all of them. The 10th percentile
    # pooled across every cluster ranged 0.408 to 0.855 between clusters, so a
    # single 0.649 was simultaneously too strict for a third of them (rejecting
    # posts those clusters would accept) and too loose for two thirds (admitting
    # posts nothing like their members). A tight cluster and a diffuse one
    # cannot share a threshold.
    member_sims = cent[labels != -1]
    floor = float(np.percentile(member_sims, 10)) if len(member_sims) else 0.0
    floors: dict[int, float] = {}
    for lab in sorted(set(labels.tolist()) - {-1}):
        vals = cent[labels == lab]
        if len(vals):
            floors[int(lab)] = float(np.percentile(vals, 10))
    return {
        "labels": {f"{p['platform']}:{p['post_id']}": int(lab)
                   for p, lab in zip(posts, labels, strict=True)},
        "keywords": {str(k): v for k, v in keywords.items()},
        "centrality": {f"{p['platform']}:{p['post_id']}": round(float(c), 5)
                       for p, c in zip(posts, cent, strict=True)},
        "centroids": {str(k): [round(float(x), 5) for x in v] for k, v in cents.items()},
        # The model on disk was fitted before the merge, so transform() returns
        # pre-merge ids. This maps them onto the labels the rest of the run uses.
        "label_remap": {str(k): int(v) for k, v in label_remap.items()},
        "belong_floor": round(floor, 5),
        "belong_floors": {str(k): round(v, 5) for k, v in floors.items()},
        "n_clusters": len(set(labels.tolist()) - {-1}),
        "noise": int((labels == -1).sum()),
        "algorithm": algorithm,
        "account_bias_accounts": len(offsets),
    }


def stage_name(posts: list[dict], state: dict, client, model: str,
               min_posts: int, run_id: str) -> dict:
    labels = state["cluster"]["labels"]
    by_cluster: dict[int, list[dict]] = {}
    for p in posts:
        label = labels.get(f"{p['platform']}:{p['post_id']}", -1)
        if label >= 0:
            by_cluster.setdefault(label, []).append(p)

    named: dict[str, dict] = {}
    stats = {"named": 0, "skipped_small": 0, "skipped_incoherent": 0, "merged_same_name": 0}
    by_slug: dict[str, str] = {}
    for label, members in sorted(by_cluster.items(), key=lambda kv: -len(kv[1])):
        # Post count only. The author floor was a food-corpus threshold (30
        # distinct authors) carried over unchanged, and this corpus has 510
        # community authors in total with 24 accounts producing 80% of the
        # posts - so requiring 30 authors per cluster asked each one to draw
        # from 6% of every author there is. It discarded 171 of 194 clusters,
        # leaving only the broadest blobs, which is why the surviving trends
        # read as generic developer activity rather than anything specific.
        if len(members) < min_posts:
            stats["skipped_small"] += 1
            continue
        keywords = state["cluster"]["keywords"].get(str(label), [])
        result = namer.name_cluster(keywords, client, model)
        if not result.is_coherent:
            stats["skipped_incoherent"] += 1
            continue
        slug = namer.slugify(result.name) or f"cluster-{label}"
        if slug in by_slug:
            named[by_slug[slug]]["merged_labels"].append(label)
            stats["merged_same_name"] += 1
            logger.info("cluster %s -> %s (%s posts) merged into the trend of the same name",
                        label, result.name, len(members))
            continue
        trend_id = f"{slug}--{metrics.run_token(run_id)}"
        by_slug[slug] = trend_id
        named[trend_id] = {
            "cluster_label": label,
            "merged_labels": [],
            "name": result.name, "summary": result.summary,
            "related_themes": result.related_themes,
            "offering_entities": result.offering_entities,
            "confidence": result.confidence,
            "keywords": keywords,
        }
        stats["named"] += 1
        logger.info("cluster %s -> %s (%s posts)", label, result.name, len(members))
    state["named"] = named
    return stats


def stage_assign(cohort: str, run_id: str, state: dict, tag: str,
                 use_documents: bool, scope: dict | None = None) -> dict:
    """Attach any post the discovery stage did not already cluster.

    Discovery now spans every cohort, so for the 'all' cohort this usually has
    little left to do - it exists for the cohort-scoped runs, where discovery
    sees one cohort and the others still need placing, and for posts that
    arrived between the two stages.

    Every assignment must clear a belonging test: the post's cosine similarity
    to its topic centroid has to reach the 10th percentile of what that topic's
    OWN members scored. BERTopic's transform hands every post its nearest topic
    no matter how far away it sits, so without the gate a dairy brand's Ramadan
    greeting lands in whichever property trend it drifts closest to and inflates
    that trend's counts. Posts placed by discovery are fitted rather than
    transformed, so they do not need it - this is the only place the check
    happens.

    scope is the run's own post scope (sources, market, excluded accounts). A
    market-scoped run must not place the other market's posts into its trends.
    """
    settings = get_settings()
    posts = store.fetch_cohort_posts("all", tag, **(scope or {"sources": ["brand", "influencer"]}))
    # Anything discovery already placed keeps that label: it was fitted with the
    # model rather than transformed against it, which is the stronger signal.
    already = set(state.get("cluster", {}).get("labels", {}))
    posts = [p for p in posts if f"{p['platform']}:{p['post_id']}" not in already]
    if not posts:
        return {"assigned": 0, "note": "discovery already placed every tracked post"}
    logger.info("assign: %s tracked posts were not covered by discovery", len(posts))
    model_path = str(Path(settings.TREND_CACHE_DIR) / cohort / f"bertopic_{run_id}")
    from bertopic import BERTopic
    topic_model = BERTopic.load(model_path)
    if use_documents:
        documents.attach(posts)
    docs = [_text(p) for p in posts]
    raw = np.array([p["vec"] for p in posts], dtype=np.float32)
    offsets = _load_account_bias(_account_bias_path(cohort, run_id))
    if offsets is None:
        logger.info("assign: run %s has no account-bias file - using vectors as stored", run_id)
        vectors = raw.astype(np.float64)
    else:
        accounts = _accounts(posts, store.fetch_company_handles())
        missing = [i for i, a in enumerate(accounts) if a not in offsets]
        if missing:
            offsets.update(clusterer.account_bias(
                raw[missing], [accounts[i] for i in missing],
                shrink=settings.TREND_ACCOUNT_BIAS_SHRINK))
        vectors = clusterer.remove_account_bias(raw, accounts, offsets).astype(np.float64)
    topics, _ = topic_model.transform(docs, embeddings=vectors)

    cluster = state["cluster"]
    centroids = {int(k): np.array(v, dtype=np.float64)
                 for k, v in cluster.get("centroids", {}).items()}
    label_remap = {int(k): int(v) for k, v in cluster.get("label_remap", {}).items()}
    floor = cluster.get("belong_floor", 0.0)
    floors = {int(k): float(v) for k, v in cluster.get("belong_floors", {}).items()}
    norms = np.maximum(np.linalg.norm(vectors, axis=1), 1e-12)

    labels: dict[str, int] = {}
    rejected = 0
    unmapped = 0
    for i, (p, topic) in enumerate(zip(posts, topics, strict=True)):
        topic = label_remap.get(int(topic), int(topic))
        centroid = centroids.get(topic)
        if topic >= 0 and centroid is None:
            # A live topic with no centroid means the two label spaces have
            # drifted apart. Refusing the post is the safe reading: the
            # belonging gate is the only check tracked posts get, and silently
            # skipping it is how off-topic marketing lands inside a trend.
            unmapped += 1
            topic = -1
        elif topic >= 0:
            if float(vectors[i] @ centroid) / norms[i] < floors.get(topic, floor):
                topic = -1
                rejected += 1
        labels[f"{p['platform']}:{p['post_id']}"] = topic
    assigned = sum(1 for t in labels.values() if t >= 0)
    if unmapped:
        logger.warning("assign: %s posts had a topic with no centroid and were "
                       "refused - the saved model and the run's labels disagree", unmapped)
    logger.info("assign: %s of %s tracked posts joined trends "
                "(%s rejected below their topic's own floor, global fallback %.3f)",
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
                       FROM realestate_intel.trends WHERE run_id = %s""", (run_id,))
        cols = [d[0] for d in cur.description]
        for r in cur.fetchall():
            row = dict(zip(cols, r, strict=True))
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
            summary = namer.opportunity_summary(payload, client, model)
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
    trend_of = _labels_of(named)
    trend_counts: dict[str, int] = {}
    for label in state["cluster"]["labels"].values():
        tid = trend_of.get(int(label))
        if tid:
            trend_counts[tid] = trend_counts.get(tid, 0) + 1
    micro_summaries = [
        {"trend_id": tid, "name": n["name"], "summary": n["summary"],
         "keywords": n["keywords"], "post_count": trend_counts.get(tid, 0)}
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


def stage_metrics(posts: list[dict], state: dict, cohort: str, run_id: str,
                  country: str | None = None) -> dict:
    settings = get_settings()
    labels = dict(state["cluster"]["labels"])
    labels.update(state.get("assign", {}).get("labels", {}))   # brand/influencer joins
    named = state["named"]

    label_to_tid = _labels_of(named)
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
        for m, s in zip(members, sims, strict=True):
            m["_centrality"] = float(s)

    as_of = max(p["posted_at"] for p in posts).date()
    state["provenance"] = {
        "embed_model": state.get("embed_tag")
        or store.model_tag(settings.TREND_EMBED_MODEL, settings.TREND_EMBED_DIM),
        "document_source": state.get("document_source", "caption"),
        "naming_model": settings.TREND_NAMING_MODEL or settings.OPENAI_MODEL,
        "prompt_version": settings.TREND_PROMPT_VERSION,
        "computed_at": datetime.now(timezone.utc).isoformat(),
        "scope": state.get("scope", {}),
    }
    _save_run(cohort, run_id, state)
    rows = metrics.build_trend_rows(run_id, groups, state.get("umbrellas", []),
                                    as_of)
    for r in rows:
        r["country"] = country
    # One transaction: a failure here used to leave the run's previous rows
    # already deleted with nothing to roll back to.
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
    parser.add_argument("--documents", choices=["analysis", "caption"], default=None,
                        help="What each post is clustered on: its stored analysis "
                             "(semantic document) or its caption. Defaults to "
                             "TREND_DOCUMENT_SOURCE.")
    parser.add_argument("--tracked", action="store_true",
                        help="Brand and influencer posts only (TREND_TRACKED_SOURCES), "
                             "without TREND_EXCLUDE_AUTHORS.")
    parser.add_argument("--country", choices=["AE", "SA"], default=None,
                        help="Scope the run to one market; implies --tracked. The run's "
                             "trends carry the code, and only readers that ask for that "
                             "market see them.")
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
    # One scope for every stage that reads posts - discovery, assignment and
    # metrics - so a trend is fitted, joined and counted on the same set.
    scope = ({"sources": settings.TREND_TRACKED_SOURCES, "country": country,
              "exclude_authors": settings.TREND_EXCLUDE_AUTHORS} if tracked else {})
    # The run key names the run and its cache directory, so a country run never
    # reads another run's cached clusters or account-bias file.
    run_key = country.lower() if country else ("tracked" if tracked else cohort)
    run_id = args.run_id or f"{run_key}-{datetime.now(timezone.utc):%Y%m%d%H%M}"
    stages = [s.strip() for s in args.stages.split(",") if s.strip()]
    client = OpenAI(api_key=settings.OPENAI_API_KEY, max_retries=8, timeout=120)
    naming_model = settings.TREND_NAMING_MODEL or settings.OPENAI_MODEL

    summary: dict = {"run_id": run_id, "cohort": cohort, "country": country, "tracked": tracked}
    state = _load_run(run_key, run_id)
    state["min_cluster_size"] = mcs
    state["scope"] = {"tracked": tracked, "country": country,
                      "sources": scope.get("sources"), "exclude_authors": scope.get("exclude_authors")}
    _community: list[dict] | None = None
    _all_sources: list[dict] | None = None
    use_documents = (args.documents or settings.TREND_DOCUMENT_SOURCE) == "analysis"
    tag = (documents.document_tag() if use_documents
           else store.model_tag(settings.TREND_EMBED_MODEL, settings.TREND_EMBED_DIM))
    state["document_source"] = "analysis" if use_documents else "caption"
    state["embed_tag"] = tag
    summary["documents"] = state["document_source"]

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

    def discovery_posts() -> list[dict]:
        """The posts trends are DISCOVERED from.

        Every cohort takes part. Discovering from community alone meant a brand
        post could only join a trend if it resembled consumer conversation, and
        developer marketing language largely does not: 47% of tracked posts came
        back from transform() with no topic at all, and 80% reached no trend.
        Worse, the community cohort is itself 61% brokerages and agents, so
        "discovered from the market" was not true even before that.

        Letting every cohort form topics changes what a trend means - it is now
        what the whole corpus talks about rather than what consumers talk about -
        and source mix stays on every trend, so who carries it is still visible.
        """
        nonlocal _community
        if _community is None:
            if cohort == "all" or tracked:
                _community = all_source_posts()
            else:
                _community = store.fetch_cohort_posts(cohort, tag, sources=["community"],
                                                      sample=args.sample,
                                                      sample_threshold=sample_threshold,
                                                      date_from=args.date_from,
                                                      date_to=args.date_to,
                                                      exclude_containers=exclude_containers)
                if use_documents:
                    documents.attach(_community)
            logger.info("loaded %s embedded posts for discovery%s", len(_community),
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
            if use_documents:
                documents.attach(_all_sources)
            logger.info("loaded %s embedded posts (%s)", len(_all_sources),
                        f"tracked accounts, {country or 'all markets'}" if tracked else "all sources")
        return _all_sources

    if "embed" in stages:
        summary["embed"] = (documents.run_embedding(limit=args.limit) if use_documents
                            else embedder.run_embedding(cohort, limit=args.limit))
    if "cluster" in stages:
        state["cluster"] = stage_cluster(
            discovery_posts(), mcs, run_key, run_id, merge_distance=args.merge_distance,
            rescue_percentile=(settings.TREND_DOCUMENT_RESCUE_PERCENTILE if use_documents
                               else settings.TREND_OUTLIER_RESCUE_PERCENTILE))
        _save_run(run_key, run_id, state)
        summary["cluster"] = {k: state["cluster"][k] for k in ("n_clusters", "noise", "algorithm")}
    if "name" in stages:
        if "cluster" not in state:
            raise SystemExit(f"run {run_id} has no cluster stage — run cluster first")
        summary["name"] = stage_name(discovery_posts(), state, client, naming_model,
                                     mcs if tracked else settings.TREND_MIN_POSTS, run_id)
        _save_run(run_key, run_id, state)
    if "group" in stages:
        if not state.get("named"):
            raise SystemExit(f"run {run_id} has no named trends — run name first")
        summary["group"] = stage_group(state, client, naming_model)
        _save_run(run_key, run_id, state)
    if "assign" in stages:
        if "cluster" not in state:
            raise SystemExit(f"run {run_id} has no cluster stage — run cluster first")
        result = stage_assign(run_key, run_id, state, tag, use_documents, scope or None)
        if "labels" in result:
            state["assign"] = {"labels": result.pop("labels"), **result}
            _save_run(run_key, run_id, state)
        summary["assign"] = result
    if "metrics" in stages:
        if not state.get("named"):
            raise SystemExit(f"run {run_id} has no named trends — run name first")
        summary["metrics"] = stage_metrics(all_source_posts(), state, run_key, run_id, country)
    if "interpret" in stages:
        summary["interpret"] = stage_interpret(run_id, client, naming_model)

    print("\nPipeline summary:")
    for k, v in summary.items():
        print(f"  {k}: {v}")


if __name__ == "__main__":
    main()
