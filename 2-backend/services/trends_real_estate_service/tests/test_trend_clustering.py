import json

import numpy as np
import pytest

from services.trends_real_estate_service.app.trends import clusterer, namer, run


def _unit(v):
    v = np.asarray(v, dtype=np.float32)
    return v / np.linalg.norm(v)


HOUSE_A = np.array([10, 0, 0, 0], dtype=np.float32)
HOUSE_B = np.array([0, 10, 0, 0], dtype=np.float32)
WATERFRONT = np.array([0, 0, 1, 0], dtype=np.float32)
GOLF = np.array([0, 0, 0, 1], dtype=np.float32)

VECTORS = np.stack([
    _unit(HOUSE_A + WATERFRONT),
    _unit(HOUSE_A + GOLF),
    _unit(HOUSE_B + WATERFRONT),
    _unit(HOUSE_B + GOLF),
])
ACCOUNTS = ["a", "a", "b", "b"]


def _nearest(vectors, i):
    sims = vectors @ vectors[i]
    sims[i] = -np.inf
    return int(np.argmax(sims))


def test_before_removal_posts_cluster_by_account():
    assert _nearest(VECTORS, 0) == 1


def test_after_removal_posts_cluster_by_subject():
    offsets = clusterer.account_bias(VECTORS, ACCOUNTS, shrink=0)
    cleaned = clusterer.remove_account_bias(VECTORS, ACCOUNTS, offsets)
    assert _nearest(cleaned, 0) == 2
    assert _nearest(cleaned, 1) == 3


def test_offset_is_the_account_mean_shrunk_by_its_size():
    offsets = clusterer.account_bias(VECTORS, ACCOUNTS, shrink=2)
    expected = VECTORS[:2].mean(axis=0) * (2 / (2 + 2))
    np.testing.assert_allclose(offsets["a"], expected, rtol=1e-6)


def test_removed_vectors_are_unit_length():
    offsets = clusterer.account_bias(VECTORS, ACCOUNTS, shrink=20)
    cleaned = clusterer.remove_account_bias(VECTORS, ACCOUNTS, offsets)
    np.testing.assert_allclose(np.linalg.norm(cleaned, axis=1), 1.0, rtol=1e-6)


def test_account_without_offset_is_left_unchanged():
    offsets = clusterer.account_bias(VECTORS[:2], ACCOUNTS[:2], shrink=0)
    cleaned = clusterer.remove_account_bias(VECTORS, ACCOUNTS, offsets)
    np.testing.assert_allclose(cleaned[2:], VECTORS[2:], rtol=1e-6)


def _corpus():
    docs, labels, accounts = [], [], []
    for i in range(6):
        docs.append(f"sobharealty waterfront villas lagoon post{i}")
        labels.append(0)
        accounts.append("sobha")
    for i in range(6):
        docs.append(f"waterfront lagoon beach living note{i}")
        labels.append(0)
        accounts.append(f"broker{i}")
    for i in range(6):
        docs.append(f"golf course fairway views item{i}")
        labels.append(1)
        accounts.append(f"agent{i}")
    for account in ("agent0", "agent1"):
        docs.append("tableware golf course")
        labels.append(1)
        accounts.append(account)
    return docs, np.array(labels), accounts


@pytest.fixture
def no_stopwords(monkeypatch):
    monkeypatch.setattr(clusterer, "_stopwords", lambda: ())


def test_one_account_terms_never_become_keywords(no_stopwords):
    docs, labels, accounts = _corpus()
    keywords = clusterer.clean_keywords(docs, labels, accounts, min_df=1)
    assert "sobharealty" not in keywords[0]
    assert "waterfront" in keywords[0]
    assert "lagoon" in keywords[0]


def test_a_term_in_too_few_cluster_posts_is_dropped(no_stopwords):
    docs, labels, accounts = _corpus()
    keywords = clusterer.clean_keywords(docs, labels, accounts, min_df=1, min_cluster_posts=3)
    assert "tableware" not in keywords[1]
    assert "golf" in keywords[1]


def test_noise_is_not_given_keywords(no_stopwords):
    docs, labels, accounts = _corpus()
    labels[-1] = -1
    assert -1 not in clusterer.clean_keywords(docs, labels, accounts, min_df=1)


def test_company_handles_count_as_one_account():
    posts = [
        {"platform": "instagram", "post_id": "1", "author_username": "DamacOfficial"},
        {"platform": "tiktok", "post_id": "2", "author_username": "damacproperties"},
        {"platform": "instagram", "post_id": "3", "author_username": "some_broker"},
        {"platform": "instagram", "post_id": "4", "author_username": None},
    ]
    companies = {("instagram", "damacofficial"): "damac_properties",
                 ("tiktok", "damacproperties"): "damac_properties"}
    assert run._accounts(posts, companies) == [
        "damac_properties", "damac_properties", "user:some_broker", "post:instagram:4"]


def test_account_bias_survives_a_save_and_load(tmp_path):
    offsets = clusterer.account_bias(VECTORS, ACCOUNTS, shrink=20)
    path = tmp_path / "all" / "account_bias_run.npz"
    run._save_account_bias(path, offsets)
    loaded = run._load_account_bias(path)
    assert set(loaded) == {"a", "b"}
    np.testing.assert_allclose(loaded["a"], offsets["a"])


def test_missing_account_bias_file_loads_as_none(tmp_path):
    assert run._load_account_bias(tmp_path / "absent.npz") is None


class _Completions:
    def __init__(self):
        self.messages = None

    def create(self, **kwargs):
        self.messages = kwargs["messages"]
        body = json.dumps({"name": "Waterfront Living", "summary": "Lagoon homes.",
                           "related_themes": [], "offering_entities": [],
                           "is_coherent": True, "confidence": 0.8})
        choice = type("C", (), {"message": type("M", (), {"content": body})()})()
        return type("R", (), {"choices": [choice]})()


class _Client:
    def __init__(self):
        self.chat = type("Chat", (), {})()
        self.chat.completions = _Completions()


@pytest.fixture
def known_companies(monkeypatch):
    monkeypatch.setattr(namer, "_company_tokens", lambda: frozenset({"sobha"}))


def test_naming_sees_keywords_only(known_companies):
    client = _Client()
    result = namer.name_cluster(["waterfront", "lagoon", "sobha"], client, "gpt-4o")
    assert result.name == "Waterfront Living"
    user = client.chat.completions.messages[1]["content"]
    assert user == "DISTINCTIVE KEYWORDS: waterfront, lagoon"


def test_naming_without_keywords_makes_no_call(known_companies):
    client = _Client()
    result = namer.name_cluster(["sobha"], client, "gpt-4o")
    assert result.is_coherent is False
    assert client.chat.completions.messages is None
