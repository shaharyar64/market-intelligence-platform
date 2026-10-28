from datetime import date, datetime, timezone


def test_assign_quadrant_matrix():
    from services.food_intelligence_service.app.trends.metrics import assign_quadrant
    assert assign_quadrant(80, 80) == "slow-burner"
    assert assign_quadrant(80, 20) == "mainstream"
    assert assign_quadrant(20, 80) == "breakthrough"
    assert assign_quadrant(20, 20) == "watchlist"


def test_percentile_index_ranks_0_to_100():
    from services.food_intelligence_service.app.trends.metrics import percentile_index
    out = percentile_index([10.0, 20.0, 30.0])
    assert out[0] < out[1] < out[2]
    assert out[0] >= 0 and out[2] <= 100
    assert percentile_index([5.0]) == [50.0]
    ties = percentile_index([1.0, 1.0])
    assert ties[0] == ties[1]


def test_growth_is_share_of_voice_not_raw_volume():
    """When the whole corpus doubles, a trend that merely doubled with it has
    not grown its share and must not be reported as +100%."""
    from services.food_intelligence_service.app.trends.metrics import compute_growth_pct
    flat = compute_growth_pct(200, 100, total_recent=2000, total_previous=1000,
                              cohort_size=10)
    assert abs(flat) < 10          # moved with the tide, not against it
    gained = compute_growth_pct(400, 100, total_recent=2000, total_previous=1000,
                                cohort_size=10)
    assert gained > 50             # doubled its share
    lost = compute_growth_pct(120, 100, total_recent=2000, total_previous=1000,
                              cohort_size=10)
    assert lost < 0                # grew in posts but shrank in share


def test_growth_smoothing_tames_a_single_post_baseline():
    """1 -> 208 posts read as 20,700% raw. Smoothing keeps a lone post from
    setting the denominator."""
    from services.food_intelligence_service.app.trends.metrics import compute_growth_pct
    g = compute_growth_pct(208, 1, total_recent=12893, total_previous=3144,
                           cohort_size=88)
    assert 0 < g < 5000


def test_growth_is_always_defined_and_floored():
    from services.food_intelligence_service.app.trends.metrics import compute_growth_pct
    # No prior posts is no longer a special case: smoothing keeps it finite.
    assert isinstance(compute_growth_pct(5, 0, 100, 100, 10), float)
    # A share cannot fall below nothing.
    assert compute_growth_pct(0, 500, 1000, 1000, 10) >= -100.0


def test_growth_is_computed_against_the_whole_level(self=None):
    """Share of voice needs the level's totals, so a trend's growth depends on
    what every other trend did in the same windows."""
    from services.food_intelligence_service.app.trends.metrics import build_trend_rows
    from datetime import date

    named = {"name": "N", "summary": "s", "related_themes": [],
             "product_entities": [], "confidence": 0.5}

    def _older(pid, month, day, author):
        p = _post(pid, 1, author)
        p["posted_at"] = datetime(2026, month, day, tzinfo=timezone.utc)
        return p

    groups = {
        # surged in the recent window
        "riser": {"named": dict(named), "keywords": [],
                  "posts": [_post(str(i), 1 + (i % 12), f"a{i}") for i in range(20)]
                           + [_older("old1", 3, 1, "a1")]},
        # steady across both windows
        "steady": {"named": dict(named), "keywords": [],
                   "posts": [_post("s1", 5, "b1"), _older("s2", 3, 2, "b2"),
                             _older("s3", 3, 3, "b3")]},
    }
    rows = build_trend_rows("run", groups, [], date(2026, 5, 13))
    by_id = {r["trend_id"]: r for r in rows}
    assert by_id["riser"]["metrics"]["growth_pct"] > by_id["steady"]["metrics"]["growth_pct"]
    assert by_id["riser"]["growth_index"] >= by_id["steady"]["growth_index"]
    # both sides of the ratio are published so a reader can judge the baseline
    assert by_id["riser"]["metrics"]["recent_posts"] > 0
    assert by_id["steady"]["metrics"]["previous_posts"] > 0


def _post(pid, day, author="a1", eng=10):
    return {"platform": "tiktok", "post_id": pid, "author_username": author,
            "engagement_total": eng, "caption": "cap", "post_url": "u",
            "likes": 1, "comments": 1, "views": 1, "media_keys": ["k.jpg"],
            "posted_at": datetime(2026, 5, day, tzinfo=timezone.utc)}


def test_build_trend_rows_assembles_micro_and_umbrella():
    from services.food_intelligence_service.app.trends.metrics import build_trend_rows
    named = {"name": "N", "summary": "s", "related_themes": ["t"], "product_entities": ["p"], "confidence": 0.9}
    groups = {
        "trend-a": {"named": dict(named), "keywords": ["ka"],
                    "posts": [_post("1", 1), _post("2", 10, "a2")]},
        "trend-b": {"named": dict(named), "keywords": ["kb"],
                    "posts": [_post("3", 12, "a3", eng=99)]},
    }
    umbrellas = [{"name": "Umb", "slug": "umb", "summary": "us",
                  "members": ["trend-a", "trend-b"]}]
    rows = build_trend_rows("run12345", groups, umbrellas,
                            as_of=date(2026, 5, 13))
    micro = [r for r in rows if r["level"] == "micro"]
    umb = [r for r in rows if r["level"] == "umbrella"]
    assert len(micro) == 2 and len(umb) == 1
    assert umb[0]["post_count"] == 3 and umb[0]["unique_authors"] == 3
    assert all(m["parent_trend_id"] == umb[0]["trend_id"] for m in micro)
    a = next(r for r in micro if r["trend_id"] == "trend-a")
    assert a["metrics"]["platform_mix"] == {"tiktok": 2}
    assert a["quadrant"] in {"breakthrough", "slow-burner", "mainstream", "watchlist"}
    assert len(a["timeline"]) == 2                     # two ISO weeks
    assert a["example_posts"]["top"][0]["media_key"] == "k.jpg"
    assert a["example_posts"]["by_source"]["community"][0]["source"] == "community"
    assert a["metrics"]["source_mix"] == {"community": 2}


def test_umbrella_indices_ranked_within_level():
    from services.food_intelligence_service.app.trends.metrics import build_trend_rows
    named = {"name": "N", "summary": "s", "related_themes": [], "product_entities": [], "confidence": 0.5}
    groups = {f"t{i}": {"named": dict(named), "keywords": [],
                        "posts": [_post(str(10 * i + j), 1 + j) for j in range(i + 1)]}
              for i in range(3)}
    rows = build_trend_rows("run", groups, [], date(2026, 5, 13))
    micro = [r for r in rows if r["level"] == "micro"]
    vols = sorted(r["volume_index"] for r in micro)
    assert vols == [0.0, 50.0, 100.0]
