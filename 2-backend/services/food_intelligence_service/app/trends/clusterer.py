"""Topic clustering over embedding vectors.

Primary path: BERTopic (embedding_model=None — we supply OpenAI vectors) with
our tuned UMAP/HDBSCAN and an Arabic-aware CountVectorizer; the fitted model
can be persisted for a later train-once/predict-weekly migration.
Fallback path: the same UMAP->HDBSCAN + hand-rolled c-TF-IDF, kept for tests
and for environments without the bertopic/torch stack.
"""
import logging
import re
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



def _openai_backend():
    """An embedding backend so representation models score in OUR vector space.

    KeyBERTInspired embeds the topic's representative documents and the
    candidate keywords, then compares them. It reaches for
    `topic_model.embedding_model`, and we pass None because we supply
    pre-computed vectors - so BERTopic quietly downloaded an English
    all-MiniLM-L6-v2 and judged a corpus that is two thirds Arabic with it.

    It has to be a real BaseEmbedder subclass: select_backend does an isinstance
    check and silently falls back otherwise, which is exactly how the first
    attempt at this went unnoticed. Built lazily because importing bertopic at
    module scope drags in torch.

    Only representation models call this, on a vocabulary and a few documents
    per topic, so it costs cents rather than a re-embedding run.
    """
    from bertopic.backend import BaseEmbedder

    class _OpenAIBackend(BaseEmbedder):
        def embed(self, documents, verbose=False):
            from openai import OpenAI
            from services.food_intelligence_service.app.core.config import get_settings
            from services.food_intelligence_service.app.trends import embedder

            settings = get_settings()
            client = OpenAI(api_key=settings.OPENAI_API_KEY, max_retries=6, timeout=120)
            texts = [d if isinstance(d, str) and d.strip() else " " for d in documents]
            vectors = embedder.embed_texts(texts, client, settings.TREND_EMBED_MODEL,
                                           settings.TREND_EMBED_DIM)
            return np.asarray(vectors, dtype=np.float64)

    return _OpenAIBackend()


def _representation_models():
    """Refine the keywords c-TF-IDF proposes.

    Raw c-TF-IDF ranks a term by how distinctive it is to a cluster, which is
    not the same as how well it describes one: a word appearing in a single post
    of a 399-post trend is maximally distinctive, and "tableware" became a
    headline keyword for a grape-leaves trend on the strength of one kitchenware
    post. KeyBERTInspired re-scores those candidates by how close they sit to
    the topic's own documents, and MMR stops near-duplicates filling the list.
    """
    from bertopic.representation import KeyBERTInspired, MaximalMarginalRelevance
    return [KeyBERTInspired(top_n_words=20), MaximalMarginalRelevance(diversity=0.3)]


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
    return tuple(sorted(set(_PLATFORM_NOISE) | _nltk_stopwords()))


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
                         outlier_threshold: float = 0.60,
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
        embedding_model=_openai_backend(),
        representation_model=_representation_models(),
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
        try:
            topics = topic_model.reduce_outliers(
                docs, topics, strategy="embeddings", embeddings=embeddings,
                threshold=outlier_threshold)
            # The representation chain has to be passed here too. update_topics
            # recomputes keywords from scratch, so omitting it would quietly
            # rebuild them with raw c-TF-IDF and undo the refinement - the
            # rescued run would look worse than the one that kept its noise.
            topic_model.update_topics(docs, topics=topics,
                                      vectorizer_model=vectorizer,
                                      ctfidf_model=ClassTfidfTransformer(reduce_frequent_words=True),
                                      representation_model=_representation_models(),
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
            # The embedding backend is a class defined inside a function, which
            # pickle cannot name and therefore cannot save. It is only needed
            # while fitting - the assign stage supplies its own vectors to
            # transform() - so it is detached for the write and put back after.
            backend = topic_model.embedding_model
            topic_model.embedding_model = None
            try:
                topic_model.save(save_path, serialization="pickle")
            finally:
                topic_model.embedding_model = backend
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


def ctfidf_keywords(docs: list[str], labels: np.ndarray, top_k: int = 10) -> dict[int, list[str]]:
    """Class-based TF-IDF: concatenate each cluster's docs into one class doc,
    weight terms by in-class frequency x inverse cross-class frequency."""
    from sklearn.feature_extraction.text import CountVectorizer

    unique = sorted(set(labels.tolist()) - {-1})
    if not unique:
        return {}
    class_docs = [" ".join(d for d, l in zip(docs, labels) if l == label) for label in unique]

    vectorizer = CountVectorizer(token_pattern=_TOKEN, lowercase=True,
                                 stop_words=list(_stopwords()),
                                 max_features=50000, min_df=1)
    tf = vectorizer.fit_transform(class_docs)          # classes x terms
    tf = np.asarray(tf.todense(), dtype=np.float64)
    # normalize term counts within each class
    tf_norm = tf / np.maximum(tf.sum(axis=1, keepdims=True), 1.0)
    # idf across classes: log(1 + avg_count / term_total)
    avg = tf.sum() / max(len(unique), 1)
    idf = np.log(1.0 + avg / np.maximum(tf.sum(axis=0), 1.0))
    scores = tf_norm * idf

    terms = np.array(vectorizer.get_feature_names_out())
    out: dict[int, list[str]] = {}
    for row, label in enumerate(unique):
        top = np.argsort(scores[row])[::-1][:top_k]
        out[label] = [terms[i] for i in top if scores[row][i] > 0]
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
                         vectors: np.ndarray | None = None) -> tuple[np.ndarray, int]:
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
        return labels, 0

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
    for group in groups:
        if len(group) > 1:
            keep = min(group)
            for label in group:
                if label != keep:
                    out[labels == label] = keep
    return out, merged
