"""Example posts must visibly demonstrate the trend, not merely be loud."""


def _post(pid, eng, caption, source="community", hashtags=None):
    from datetime import datetime, timezone
    return {"platform": "tiktok", "post_id": pid, "source": source,
            "author_username": f"a{pid}", "engagement_total": eng,
            "caption": caption, "hashtags": hashtags or [], "post_url": "u",
            "likes": 1, "comments": 1, "views": 1, "media_keys": ["k.jpg"],
            "posted_at": datetime(2026, 5, 1, tzinfo=timezone.utc)}


def test_viral_off_topic_post_loses_to_on_topic_ones():
    from services.food_intelligence_service.app.trends.metrics import _pick_examples
    pool = [
        _post("viral", 1_000_000, "#حج #اكسبلور"),
        _post("core1", 500, "birthday cake decorating"),
        _post("core2", 400, "cupcakes for the weekend"),
        _post("core3", 300, "cake recipe"),
    ]
    picked = [p["post_id"] for p in _pick_examples(pool, 3, {"cake", "cupcakes"})]
    assert "viral" not in picked
    assert picked == ["core1", "core2", "core3"]


def test_hashtags_count_as_topical_evidence():
    from services.food_intelligence_service.app.trends.metrics import _pick_examples
    pool = [_post("tagged", 10, "no words here", hashtags=["cake", "fyp"]),
            _post("plain", 5, "unrelated text")]
    assert [p["post_id"] for p in _pick_examples(pool, 1, {"cake"})] == ["tagged"]


def test_engagement_orders_within_on_topic_posts():
    from services.food_intelligence_service.app.trends.metrics import _pick_examples
    pool = [_post("low", 10, "cake"), _post("high", 900, "cake"), _post("mid", 90, "cake")]
    assert [p["post_id"] for p in _pick_examples(pool, 3, {"cake"})] == ["high", "mid", "low"]


def test_falls_back_when_too_few_on_topic():
    from services.food_intelligence_service.app.trends.metrics import _pick_examples
    pool = [_post("a", 100, "cake"), _post("b", 50, "nothing relevant")]
    picked = [p["post_id"] for p in _pick_examples(pool, 2, {"cake"})]
    assert picked == ["a", "b"]


def test_no_terms_means_pure_engagement_order():
    from services.food_intelligence_service.app.trends.metrics import _pick_examples
    pool = [_post("x", 5, "c"), _post("y", 50, "c")]
    assert [p["post_id"] for p in _pick_examples(pool, 2, set())] == ["y", "x"]


def test_empty_pool():
    from services.food_intelligence_service.app.trends.metrics import _pick_examples
    assert _pick_examples([], 3, {"cake"}) == []


def test_topical_terms_drops_generic_words():
    from services.food_intelligence_service.app.trends.metrics import topical_terms
    terms = topical_terms("Cake Creations", {"keywords": ["cake", "cupcakes"],
                                             "product_entities": ["birthday cake"]})
    assert "cake" in terms and "cupcakes" in terms
    assert "creations" not in terms
