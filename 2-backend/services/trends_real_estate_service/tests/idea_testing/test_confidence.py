from datetime import date, datetime, timezone

from services.trends_real_estate_service.app.idea_testing import confidence as c


def test_relevance_score_is_100_at_zero_distance():
    assert c.relevance_score([0.0]) == 100.0


def test_relevance_score_is_0_at_or_beyond_the_ceiling():
    assert c.relevance_score([0.72]) == 0.0
    assert c.relevance_score([0.9]) == 0.0


def test_relevance_score_ignores_missing_distances():
    assert c.relevance_score([None, None]) == 0.0


def test_relevance_score_averages_multiple_items():
    # 0.0 -> 100, 0.36 -> 50
    assert round(c.relevance_score([0.0, 0.36])) == 75


def test_volume_score_is_0_with_no_evidence():
    assert c.volume_score(0) == 0.0


def test_volume_score_reaches_100_at_the_baseline():
    assert c.volume_score(c.VOLUME_BASELINE) == 100.0


def test_volume_score_is_monotonic():
    assert c.volume_score(5) < c.volume_score(20) < c.volume_score(c.VOLUME_BASELINE)


def test_spread_score_counts_distinct_known_sources():
    assert c.spread_score({"community"}) == 100.0 / 3
    assert c.spread_score({"community", "brand"}) == 200.0 / 3
    assert c.spread_score({"community", "brand", "influencer"}) == 100.0
    assert c.spread_score(set()) == 0.0


def test_spread_score_ignores_unknown_source_values():
    assert c.spread_score({"community", "made_up_source"}) == 100.0 / 3


def test_recency_score_is_the_recent_share():
    assert c.recency_score(5, 10) == 50.0
    assert c.recency_score(0, 0) == 0.0


def test_quality_score_is_unique_author_ratio_capped_at_100():
    assert c.quality_score(3, 3) == 100.0
    assert c.quality_score(1, 4) == 25.0
    assert c.quality_score(0, 0) == 0.0


def test_combine_applies_the_brief_weights_and_caps_at_95():
    components = {"relevance": 100.0, "volume": 100.0, "spread": 100.0,
                  "recency": 100.0, "quality": 100.0}
    assert c.combine(components) == 95

def test_combine_weights_relevance_heaviest():
    low_relevance = {"relevance": 0.0, "volume": 100.0, "spread": 100.0,
                     "recency": 100.0, "quality": 100.0}
    low_volume = {"relevance": 100.0, "volume": 0.0, "spread": 100.0,
                  "recency": 100.0, "quality": 100.0}
    assert c.combine(low_relevance) < c.combine(low_volume)


def test_count_recent_counts_posts_inside_the_window_before_as_of():
    as_of = date(2026, 8, 31)
    dates = [datetime(2026, 8, 1, tzinfo=timezone.utc), date(2025, 9, 1),
             date(2025, 8, 31), date(2019, 10, 9)]
    assert c.count_recent(dates, as_of) == 2


def test_count_recent_treats_posts_newer_than_as_of_as_recent():
    assert c.count_recent([date(2026, 9, 10)], date(2026, 8, 31)) == 1


def test_count_recent_is_0_without_an_anchor():
    assert c.count_recent([date(2026, 8, 1)], None) == 0


def test_confidence_label_follows_the_brief_bands():
    assert c.confidence_label(0) == "Very limited"
    assert c.confidence_label(20) == "Very limited"
    assert c.confidence_label(21) == "Low"
    assert c.confidence_label(41) == "Moderate"
    assert c.confidence_label(61) == "Good"
    assert c.confidence_label(81) == "High"


_GOLDEN_VISA = {"relevance": 37.4, "volume": 86.7, "spread": 100.0,
                "recency": 25.0, "quality": 66.7}


def test_explain_confidence_names_strengths_and_the_costliest_weaknesses():
    raw = c.explain_confidence(64, _GOLDEN_VISA)
    assert raw.startswith("Plenty of relevant posts")
    text = raw.lower()
    assert "plenty of relevant posts" in text
    assert "brands, influencers and the community" in text
    assert "only loosely match" in text
    assert "more than a year old" in text
    assert text.index("loosely") < text.index("year old")


def test_explain_confidence_warns_when_confidence_is_low():
    weak = {"relevance": 10.0, "volume": 20.0, "spread": 100.0 / 3,
            "recency": 0.0, "quality": 50.0}
    text = c.explain_confidence(15, weak)
    assert text.startswith("Most of the evidence only loosely matches")
    assert text.endswith("Treat these scores as directional, not conclusive.")


def test_explain_confidence_does_not_warn_when_confidence_is_moderate_or_better():
    assert "directional" not in c.explain_confidence(64, _GOLDEN_VISA)


def test_explain_confidence_handles_no_evidence():
    empty = {"relevance": 0.0, "volume": 0.0, "spread": 0.0, "recency": 0.0, "quality": 0.0}
    assert "No relevant posts or trends were found" in c.explain_confidence(0, empty)


def test_explain_confidence_never_uses_dashes_as_punctuation():
    for comps in (_GOLDEN_VISA, {k: 100.0 for k in c.WEIGHTS}, {k: 0.0 for k in c.WEIGHTS}):
        text = c.explain_confidence(c.combine(comps), comps)
        assert "—" not in text and "–" not in text


def test_overall_score_is_the_simple_average_rounded():
    assert c.overall_score([80, 60, 70, 50, 90, 40]) == 65
    assert c.overall_score([100, 100, 100, 100, 100, 99]) == 100  # rounds up
