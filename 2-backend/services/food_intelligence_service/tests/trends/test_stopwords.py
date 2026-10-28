"""The NLTK stopwords corpus must self-install, and never break clustering."""
from unittest.mock import patch


def _fresh():
    from services.food_intelligence_service.app.trends import clusterer
    clusterer._stopwords.cache_clear()
    return clusterer


def test_stopwords_cover_english_and_arabic():
    clusterer = _fresh()
    words = set(clusterer._stopwords())
    assert "the" in words
    assert "من" in words
    assert "fyp" in words and "اكسبلور" in words


def test_missing_corpus_triggers_download_then_succeeds():
    clusterer = _fresh()
    calls = {"n": 0}

    def words(lang):
        calls["n"] += 1
        if calls["n"] == 1:
            raise LookupError("Resource stopwords not found")
        return ["alpha", "beta"]

    with patch("nltk.download") as download, \
         patch("nltk.corpus.stopwords.words", side_effect=words):
        result = clusterer._nltk_stopwords()

    download.assert_called_once()
    assert result == {"alpha", "beta"}


def test_unavailable_corpus_raises_rather_than_degrading():
    import pytest
    clusterer = _fresh()
    with patch.object(clusterer, "_nltk_stopwords", side_effect=RuntimeError("offline")):
        with pytest.raises(RuntimeError):
            clusterer._stopwords()


def test_result_is_cached():
    clusterer = _fresh()
    with patch.object(clusterer, "_nltk_stopwords", return_value={"x"}) as spy:
        clusterer._stopwords()
        clusterer._stopwords()
    assert spy.call_count == 1
