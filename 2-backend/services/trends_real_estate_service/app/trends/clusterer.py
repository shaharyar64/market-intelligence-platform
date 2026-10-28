"""Topic clustering over embedding vectors.

Primary path: BERTopic (embedding_model=None — we supply OpenAI vectors) with
our tuned UMAP/HDBSCAN and an Arabic-aware CountVectorizer; the fitted model
can be persisted for a later train-once/predict-weekly migration.
Fallback path: the same UMAP->HDBSCAN + hand-rolled c-TF-IDF, kept for tests
and for environments without the bertopic/torch stack.
"""
import logging
from functools import lru_cache

import numpy as np

logger = logging.getLogger("trends.clusterer")

_ARABIC = r"؀-ۿ"
_TOKEN = rf"(?u)\b(?![\d_]+\b)[\w{_ARABIC}]{{3,}}\b"

_STOPWORD_LANGUAGES = ("english", "arabic")

_PLATFORM_NOISE = {
    "explore", "explorepage", "fyp", "fypage", "foryou", "foryoupage", "viral",
    "viralvideo", "trending", "trend", "trends", "capcut", "duet", "xyzbca",
    "followme", "subscribe", "reel", "reels", "tiktok", "instagram", "insta",
    "video", "videos", "page", "account", "link", "bio", "www", "com", "http",
    "https",
    "اكسبلور", "اكسبلورر", "اكسبلوررر", "الاكسبلور", "ترند", "ترندات", "فولو",
    "لايك", "متابعة", "متابعه", "مشاهدات", "explorer",
}



_ANALYSIS_META = {
    "description", "themes", "theme", "offering", "offerings", "semantic", "context",
    "visual", "tone", "caption", "captions", "hashtags", "hashtag", "emojis", "emoji",
    "english", "arabic", "bilingual", "suggesting", "suggests", "indicated", "indicating",
    "expresses", "conveys", "conveying", "emphasizing", "emphasizes", "evokes", "cues",
}


def account_bias(vectors: np.ndarray, accounts: list[str],
                shrink: int = 20) -> dict[str, np.ndarray]:
    keys, inverse, counts = np.unique(np.asarray(accounts, dtype=object).astype(str),
                                      return_inverse=True, return_counts=True)
    sums = np.zeros((len(keys), vectors.shape[1]), dtype=np.float64)
    np.add.at(sums, inverse, vectors)
    weights = counts / (counts + shrink)
    offsets = sums / counts[:, None] * weights[:, None]
    return {str(k): offsets[i].astype(np.float32) for i, k in enumerate(keys)}


def remove_account_bias(vectors: np.ndarray, accounts: list[str],
                       offsets: dict[str, np.ndarray]) -> np.ndarray:
    out =np.array(vectors, dtype=np.float32, copy=True)
    keys = np.asarray(accounts, dtype=object).astype(str)
    uniq, inverse = np.unique(keys, return_inverse=True)
    for i, key in enumerate(uniq):
        offset = offsets.get(str(key))
        if offset is not None:
            out[inverse == i] -= offset
    out /= np.maximum(np.linalg.norm(out, axis=1, keepdims=True), 1e-12)
    return out


def _nltk_stopwords() -> set[str]:
    """NLTK stopwords, downloading the corpus on first use if absent."""
    from nltk.corpus import stopwords as nltk_stopwords

    def collect() -> set[str]:
        return {w for lang in _STOPWORD_LANGUAGES for w in nltk_stopwords.words(lang)}

    try:
        return collect()
    except LookupError:
        import nltk
        logger.info("NLTK stopwords corpus missing — downloading once")
        nltk.download("stopwords", quiet=True, raise_on_error=True)
        return collect()


@lru_cache(maxsize=1)
def _stopwords() -> tuple[str, ...]:
    """General stopwords come from NLTK (english + arabic); only social-platform
    noise is hand-listed, since no general corpus covers #fyp or اكسبلور."""
    return tuple(sorted(set(_PLATFORM_NOISE) | _ANALYSIS_META | _nltk_stopwords()))


def _near_duplicate_groups(topics, embeddings: np.ndarray,
                           threshold: float) -> list[list[int]]:
    """Topics whose centroids are nearly identical, as connected components.

    BERTopic's nr_topics='auto' was tried and rejected: on this corpus it
    collapsed 65 topics into 27 with one absorbing 62% of all posts. Merging
    only genuine near-duplicates fixes fragmentation without mega-clusters.
    """
    labels = np.asarray(topics, dtype=int)
    ids = sorted(set(labels.tolist()) - {-1})
    if len(ids) < 2:
        return []
    centroids = np.array([embeddings[labels == i].mean(axis=0) for i in ids])
    centroids /= np.maximum(np.linalg.norm(centroids, axis=1, keepdims=True), 1e-12)
    sims = centroids @ centroids.T

    parent = {i: i for i in ids}

    def find(x):
        while parent[x] != x:
            parent[x] = parent[parent[x]]
            x = parent[x]
        return x

    for a in range(len(ids)):
        for b in range(a + 1, len(ids)):
            if sims[a, b] >= threshold:
                ra, rb = find(ids[a]), find(ids[b])
                if ra != rb:
                    parent[rb] = ra

    clusters: dict[int, list[int]] = {}
    for i in ids:
        clusters.setdefault(find(i), []).append(i)
    return [sorted(g) for g in clusters.values() if len(g) > 1]


def cluster_via_bertopic(docs: list[str], vectors: np.ndarray,
                         min_cluster_size: int = 15, umap_dim: int = 32,
                         random_state: int = 42, top_k: int = 10,
                         save_path: str | None = None,
                         merge_similar: bool = True,
                         merge_threshold: float = 0.92,
                         rescue_outliers: bool = False,
                         outlier_percentile: float = 50.0,
                         min_df: int = 3) -> tuple[np.ndarray, dict[int, list[str]]]:
    """BERTopic with pre-computed embeddings: our UMAP/HDBSCAN, BERTopic's
    c-TF-IDF for keywords. Returns (labels, keywords)."""
    import hdbscan
    import umap
    from bertopic import BERTopic
    from bertopic.vectorizers import ClassTfidfTransformer
    from sklearn.feature_extraction.text import CountVectorizer

    embeddings = np.asarray(vectors, dtype=np.float64)
    umap_model = umap.UMAP(n_components=umap_dim, metric="cosine",
                           n_neighbors=15, min_dist=0.0, random_state=random_state)
    hdbscan_model = hdbscan.HDBSCAN(min_cluster_size=min_cluster_size,
                                    min_samples=5, metric="euclidean",
                                    cluster_selection_method="eom",
                                    prediction_data=True)
    # Bigrams as well as single words: "waraq enab" says what "waraq" and
    # "enab" separately do not, both in the trend name and when matching a post
    # against its topic.
    vectorizer = CountVectorizer(token_pattern=_TOKEN, lowercase=True,
                                 stop_words=list(_stopwords()),
                                 ngram_range=(1, 2),
                                 max_features=50000, min_df=min_df)
    topic_model = BERTopic(
        embedding_model=None,
        representation_model=None,
        umap_model=umap_model,
        hdbscan_model=hdbscan_model,
        vectorizer_model=vectorizer,
        ctfidf_model=ClassTfidfTransformer(reduce_frequent_words=True),
        calculate_probabilities=False,
        top_n_words=top_k,
        verbose=False,
    )
    topics, _ = topic_model.fit_transform(docs, embeddings=embeddings)

    if merge_similar:
        groups = _near_duplicate_groups(topics, embeddings, merge_threshold)
        if groups:
            before = len(set(topics) - {-1})
            try:
                topic_model.merge_topics(docs, groups)
                topics = topic_model.topics_
                logger.info("merged %s near-duplicate groups: %s -> %s topics",
                            len(groups), before, len(set(topics) - {-1}))
            except Exception as exc:
                logger.warning("merge_topics failed, keeping originals: %s", exc)

    if rescue_outliers:
        noise_before = sum(1 for t in topics if t == -1)
        current = np.asarray(topics, dtype=int)
        members = current != -1
        threshold = 1.0
        if members.any():
            threshold = float(np.percentile(centrality(embeddings, current)[members],
                                            outlier_percentile))
        logger.info("outlier rescue threshold %.3f (p%.0f of cluster members)",
                    threshold, outlier_percentile)
        try:
            topics = topic_model.reduce_outliers(
                docs, topics, strategy="embeddings", embeddings=embeddings,
                threshold=threshold)
            topic_model.update_topics(docs, topics=topics,
                                      vectorizer_model=vectorizer,
                                      ctfidf_model=ClassTfidfTransformer(reduce_frequent_words=True),
                                      top_n_words=top_k)
            logger.info("rescued outliers: %s -> %s noise",
                        noise_before, sum(1 for t in topics if t == -1))
        except Exception as exc:
            logger.warning("reduce_outliers failed, keeping noise: %s", exc)

    labels = np.asarray(topics, dtype=int)

    keywords: dict[int, list[str]] = {}
    for label in sorted(set(labels.tolist()) - {-1}):
        terms = topic_model.get_topic(label) or []
        keywords[label] = [w for w, _score in terms if str(w).strip()][:top_k]

    if save_path:
        try:
            topic_model.save(save_path, serialization="pickle")
            logger.info("bertopic model saved: %s", save_path)
        except Exception as exc:                 # persistence is best-effort
            logger.warning("bertopic save failed: %s", exc)

    n = len(keywords)
    noise = int((labels == -1).sum())
    logger.info("bertopic clusters=%s noise=%s/%s", n, noise, len(labels))
    return labels, keywords


def cluster_vectors(vectors: np.ndarray, min_cluster_size: int = 15,
                    umap_dim: int = 32, random_state: int = 42) -> np.ndarray:
    import hdbscan

    if len(vectors) < 50:
        reduced = np.asarray(vectors, dtype=np.float64)
    else:
        import umap
        reducer = umap.UMAP(n_components=umap_dim, metric="cosine",
                            n_neighbors=15, min_dist=0.0, random_state=random_state)
        reduced = reducer.fit_transform(vectors)

    clusterer = hdbscan.HDBSCAN(min_cluster_size=min_cluster_size,
                                min_samples=5, metric="euclidean",
                                cluster_selection_method="eom")
    labels = clusterer.fit_predict(reduced)
    n = len(set(labels.tolist()) - {-1})
    noise = int((labels == -1).sum())
    logger.info("clusters=%s noise=%s/%s", n, noise, len(labels))
    return labels


def one_account_terms(counts, accounts: list[str], max_account_share: float) -> np.ndarray:
    from scipy import sparse

    present = (counts > 0).astype(np.float64)
    keys, inverse = np.unique(np.asarray(accounts, dtype=object).astype(str), return_inverse=True)
    by_account = sparse.csr_matrix((np.ones(len(inverse)), (inverse, np.arange(len(inverse)))),
                                   shape=(len(keys), len(inverse)))
    biggest = np.asarray((by_account @ present).max(axis=0).todense()).ravel()
    doc_freq = np.asarray(present.sum(axis=0)).ravel()
    return biggest / np.maximum(doc_freq, 1.0) > max_account_share


def clean_keywords(docs: list[str], labels: np.ndarray, accounts: list[str], top_k: int = 10,
                   max_account_share: float = 0.5, min_cluster_posts: int = 3,
                   min_df: int = 5) -> dict[int, list[str]]:
    from scipy import sparse
    from sklearn.feature_extraction.text import CountVectorizer

    labels = np.asarray(labels, dtype=int)
    unique = sorted(set(labels.tolist()) - {-1})
    if not unique:
        return {}

    vectorizer = CountVectorizer(token_pattern=_TOKEN, lowercase=True,
                                 stop_words=list(_stopwords()), min_df=min_df)
    counts = vectorizer.fit_transform(docs).tocsr()
    terms = np.array(vectorizer.get_feature_names_out())
    banned = one_account_terms(counts, accounts, max_account_share)

    classes = sorted(set(labels.tolist()))
    index = {c: i for i, c in enumerate(classes)}
    rows = np.array([index[c] for c in labels.tolist()])
    by_class = sparse.csr_matrix((np.ones(len(rows)), (rows, np.arange(len(rows)))),
                                 shape=(len(classes), len(rows)))
    tf = np.asarray((by_class @ counts).todense(), dtype=np.float64)
    class_posts = np.asarray((by_class @ (counts > 0).astype(np.float64)).todense())

    avg = tf.sum() / len(classes)
    idf = np.log(1.0 + avg / np.maximum(tf.sum(axis=0), 1.0))
    scores = tf / np.maximum(tf.sum(axis=1, keepdims=True), 1.0) * idf
    scores[:, banned] = 0.0
    scores[class_posts < min_cluster_posts] = 0.0

    out: dict[int, list[str]] = {}
    for label in unique:
        row = scores[index[label]]
        top = np.argsort(row)[::-1][:top_k]
        out[label] = [str(terms[i]) for i in top if row[i] > 0]
    return out


def centroids(vectors: np.ndarray, labels: np.ndarray) -> dict[int, np.ndarray]:
    """Unit-length mean vector per cluster, noise excluded."""
    out: dict[int, np.ndarray] = {}
    for label in set(labels.tolist()) - {-1}:
        centroid = vectors[np.where(labels == label)[0]].mean(axis=0)
        norm = np.linalg.norm(centroid)
        if norm:
            out[int(label)] = centroid / norm
    return out


def centrality(vectors: np.ndarray, labels: np.ndarray) -> np.ndarray:
    """Cosine similarity of each vector to its cluster centroid (noise -> 0)."""
    sims = np.zeros(len(vectors), dtype=np.float64)
    norms = np.linalg.norm(vectors, axis=1)
    for label in set(labels.tolist()) - {-1}:
        idx = np.where(labels == label)[0]
        centroid = vectors[idx].mean(axis=0)
        cn = np.linalg.norm(centroid)
        if cn == 0:
            continue
        denom = np.maximum(norms[idx] * cn, 1e-12)
        sims[idx] = (vectors[idx] @ centroid) / denom
    return sims


def merge_close_clusters(labels: np.ndarray, max_distance: float = 0.10,
                         vectors: np.ndarray | None = None
                         ) -> tuple[np.ndarray, int, dict[int, int]]:
    """Collapse clusters whose centroids sit within `max_distance` of each other.

    HDBSCAN splits one subject across several clusters when the density dips
    inside it, and the namer then gives each fragment its own name - a run
    carried "Ramadan Desserts" beside "Ramadan Desserts and Sweets", and
    "Hydration and Health Drinks" twice over.

    The threshold is measured on centroid distance between clusters of post
    embeddings, which is a tighter space than the trend-text embeddings the
    duplicates were first spotted in - 0.20 there is 0.10 here. At 0.20 this
    caught a fifth of all cluster pairs and fused hummus with labneh, which are
    separate sub-categories to the client; 0.10 sits at the first percentile,
    where a pair is the same subject rather than a neighbouring one.

    Returns the remapped labels, how many merges happened, and the
    {absorbed_label: surviving_label} mapping the assign stage needs.

    Complete linkage, not single linkage: two groups merge only when EVERY
    cross-pair is within the threshold. Merging on any single close pair lets
    A-B, B-C, C-D chain together while A and D are unrelated - tried on a real
    run it collapsed 63 topics into 5, one of which held 15,650 posts. Requiring
    the whole group to stay tight is what keeps a merge meaning "these are the
    same subject" rather than "these are connected by a path".
    """
    cents = centroids(vectors, labels)
    ids = sorted(cents)
    if len(ids) < 2:
        return labels, 0, {}

    groups: list[list[int]] = [[i] for i in ids]
    merged = 0
    changed = True
    while changed:
        changed = False
        for i in range(len(groups)):
            for j in range(i + 1, len(groups)):
                if all(1.0 - float(np.dot(cents[a], cents[b])) <= max_distance
                       for a in groups[i] for b in groups[j]):
                    groups[i] = groups[i] + groups[j]
                    del groups[j]
                    merged += 1
                    changed = True
                    break
            if changed:
                break

    out = labels.copy()
    # The remap travels with the labels. The fitted model is persisted before
    # this runs, so transform() in the assign stage still returns pre-merge topic
    # ids; without the mapping those ids miss the post-merge centroid lookup, the
    # belonging gate is skipped entirely, and the post is stamped with a topic
    # that no longer exists and is then silently dropped.
    remap: dict[int, int] = {}
    for group in groups:
        if len(group) > 1:
            keep = min(group)
            for label in group:
                if label != keep:
                    out[labels == label] = keep
                    remap[int(label)] = int(keep)
    return out, merged, remap
