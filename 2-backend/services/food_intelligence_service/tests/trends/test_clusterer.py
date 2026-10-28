import numpy as np


def _blobs():
    """Three blobs in distinct directions — cosine metric needs directional
    separation, not offsets around the origin."""
    rng = np.random.default_rng(7)
    centers = np.zeros((3, 64))
    centers[0, 0] = 1.0
    centers[1, 20] = 1.0
    centers[2, 40] = 1.0
    return np.vstack([
        center + rng.normal(scale=0.05, size=(120, 64)) for center in centers
    ])


def test_cluster_vectors_finds_three_blobs():
    from services.food_intelligence_service.app.trends.clusterer import cluster_vectors
    labels = cluster_vectors(_blobs(), min_cluster_size=15)
    assert len(set(labels.tolist()) - {-1}) == 3
    assert len(set(labels[:120].tolist()) - {-1}) == 1   # blob stays together


def test_cluster_vectors_small_input_does_not_crash():
    from services.food_intelligence_service.app.trends.clusterer import cluster_vectors
    rng = np.random.default_rng(1)
    labels = cluster_vectors(rng.normal(size=(20, 8)), min_cluster_size=5)
    assert len(labels) == 20


def test_ctfidf_keywords_finds_distinctive_terms():
    from services.food_intelligence_service.app.trends.clusterer import ctfidf_keywords
    docs = (["pizza cheese slice pizza"] * 5) + (["sushi salmon rice sushi"] * 5)
    labels = np.array([0] * 5 + [1] * 5)
    kw = ctfidf_keywords(docs, labels, top_k=3)
    assert "pizza" in kw[0] and "pizza" not in kw[1]
    assert "sushi" in kw[1] and "sushi" not in kw[0]


def test_centroids_are_unit_length_and_skip_noise():
    from services.food_intelligence_service.app.trends.clusterer import centroids
    vecs = np.array([[2.0, 0.0], [0.0, 2.0], [5.0, 5.0]])
    labels = np.array([0, 0, -1])
    cents = centroids(vecs, labels)
    assert set(cents) == {0}
    assert np.isclose(np.linalg.norm(cents[0]), 1.0)


def test_centroid_similarity_separates_off_topic_posts():
    """The belonging gate must rank an unrelated vector below a member."""
    from services.food_intelligence_service.app.trends.clusterer import centroids
    members = np.array([[1.0, 0.0], [0.95, 0.05], [0.9, 0.1]])
    cent = centroids(members, np.array([0, 0, 0]))[0]
    member_sim = float(members[0] @ cent) / np.linalg.norm(members[0])
    off_topic = np.array([0.0, 1.0])
    off_sim = float(off_topic @ cent) / np.linalg.norm(off_topic)
    assert off_sim < member_sim


def test_centrality_peaks_at_centroid():
    from services.food_intelligence_service.app.trends.clusterer import centrality
    vecs = np.array([[1.0, 0.0], [0.9, 0.1], [0.0, 1.0]])
    labels = np.array([0, 0, -1])
    sims = centrality(vecs, labels)
    assert sims[0] > 0.9 and sims[1] > 0.9 and sims[2] == 0.0
