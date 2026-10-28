from datetime import date, datetime, timedelta, timezone

from services.trends_real_estate_service.app.trends import metrics

AS_OF = date(2025, 10, 1)


def test_no_posts_in_either_window_has_no_growth():
    assert metrics.compute_growth_pct(0, 0, 100, 400, 10) is None


def test_no_recent_posts_is_a_full_decline():
    assert metrics.compute_growth_pct(0, 12, 100, 400, 10) == -100.0


def test_too_few_posts_across_both_windows_has_no_growth():
    assert metrics.compute_growth_pct(1, 1, 100, 400, 10) is None
    assert metrics.compute_growth_pct(4, 5, 100, 400, 10) is None
    assert metrics.compute_growth_pct(5, 5, 100, 400, 10) is not None


def test_growth_is_still_share_of_conversation_when_both_windows_have_posts():
    growth = metrics.compute_growth_pct(20, 10, 100, 100, 5)
    assert growth is not None
    assert growth > 0


def test_momentum_is_undefined_without_posts_and_zero_without_recent_ones():
    assert metrics.compute_momentum_pct(0, 0, 100, 400, 10) is None
    assert metrics.compute_momentum_pct(0, 12, 100, 400, 10) == 0.0
    assert metrics.compute_momentum_pct(1, 2, 100, 400, 10) is None


def _posts(prefix, days_ago):
    return [{"platform": "instagram", "post_id": f"{prefix}{i}", "source": "brand",
             "author_username": f"{prefix}_author{i % 3}", "caption": prefix,
             "engagement_total": 1,
             "posted_at": datetime.combine(AS_OF - timedelta(days=d), datetime.min.time(),
                                           tzinfo=timezone.utc)}
            for i, d in enumerate(days_ago)]


def _group(name, posts):
    return {"named": {"name": name, "summary": "", "related_themes": [],
                      "offering_entities": [], "confidence": 0.8},
            "keywords": [], "posts": posts}


def test_a_dormant_trend_is_not_ranked_as_growing():
    groups = {
        "rising": _group("Rising", _posts("r", [5] * 10 + [70] * 5)),
        "steady": _group("Steady", _posts("s", [5] * 6 + [70] * 6)),
        "dormant": _group("Dormant", _posts("d", [400, 410, 420])),
        "faded": _group("Faded", _posts("f", list(range(60, 72)))),
        "sparse": _group("Sparse", _posts("x", [5, 70])),
    }
    rows = {r["trend_id"]: r for r in metrics.build_trend_rows("run", groups, [], AS_OF)}

    assert rows["dormant"]["metrics"]["growth_pct"] is None
    assert rows["dormant"]["growth_index"] == 0.0
    assert rows["dormant"]["quadrant"] in ("watchlist", "mainstream")
    assert rows["faded"]["metrics"]["growth_pct"] == -100.0
    assert rows["rising"]["growth_index"] > rows["faded"]["growth_index"]
    assert rows["sparse"]["metrics"]["growth_pct"] is None
    assert rows["sparse"]["quadrant"] != "breakthrough"


def test_umbrella_target_scales_with_the_number_of_trends():
    from services.trends_real_estate_service.app.trends import namer
    assert namer.umbrella_target(28) == 8
    assert namer.umbrella_target(6) == 4
    assert namer.umbrella_target(90) == 12
