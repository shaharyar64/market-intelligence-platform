from datetime import date


def test_empty_filters_still_constrain_to_food():
    """No caller can opt out of the food guard, including one that passes
    no filters at all."""
    from services.food_intelligence_service.app.assistant.retrieval import (
        PostFilters, build_post_where)
    sql, params = build_post_where(PostFilters())
    assert sql == " AND p.is_food IS TRUE"
    assert params == {}


def test_each_filter_adds_its_clause_and_param():
    from services.food_intelligence_service.app.assistant.retrieval import (
        PostFilters, build_post_where)
    sql, params = build_post_where(PostFilters(
        platforms=["tiktok"], sources=["community"],
        date_from=date(2026, 1, 1), date_to=date(2026, 5, 13),
        countries=["Saudi Arabia"], min_engagement=100, hashtag="mandi"))
    assert "p.platform = ANY(%(platforms)s)" in sql
    assert "p.source = ANY(%(sources)s)" in sql
    assert "p.posted_at >= %(date_from)s" in sql
    assert "p.posted_at <= %(date_to)s" in sql
    assert "p.country = ANY(%(countries)s)" in sql
    assert "p.engagement_total >= %(min_engagement)s" in sql
    assert "%(hashtag)s = ANY(p.hashtags)" in sql
    assert params["platforms"] == ["tiktok"]
    assert params["hashtag"] == "mandi"


def test_partial_filters_only_emit_supplied_clauses():
    from services.food_intelligence_service.app.assistant.retrieval import (
        PostFilters, build_post_where)
    sql, params = build_post_where(PostFilters(sources=["brand"]))
    assert "p.source = ANY(%(sources)s)" in sql
    assert "platform" not in sql
    assert set(params) == {"sources"}


def test_limits_are_capped():
    from services.food_intelligence_service.app.assistant import retrieval
    assert retrieval.clamp_limit(999, retrieval.MAX_POSTS) == retrieval.MAX_POSTS
    assert retrieval.clamp_limit(5, retrieval.MAX_POSTS) == 5
    assert retrieval.clamp_limit(0, retrieval.MAX_POSTS) == 1


class _FakeCursor:
    """Records the SQL a retrieval function builds, returns no rows."""

    def __init__(self, sink):
        self.sink = sink
        self.description = []

    def execute(self, sql, params=None):
        if params is not None:
            self.sink.append((sql, params))

    def fetchall(self):
        return []

    def __enter__(self):
        return self

    def __exit__(self, *a):
        return False


class _FakeConn:
    def __init__(self, sink):
        self.sink = sink

    def cursor(self):
        return _FakeCursor(self.sink)

    def __enter__(self):
        return self

    def __exit__(self, *a):
        return False


def _capture(monkeypatch):
    from services.food_intelligence_service.app.assistant import retrieval
    sink = []
    monkeypatch.setattr(retrieval.store, "get_conn", lambda: _FakeConn(sink))
    return retrieval, sink


def test_topic_survives_a_pinned_persona(monkeypatch):
    """Asking for bakery trends inside a persona must still filter on bakery.

    The persona branch took no query at all, so "top bakery trends for Busy
    Family" and "top dairy trends for Busy Family" ran the same SQL and came
    back with the same list - the persona's top trends by share, with the topic
    silently discarded.
    """
    retrieval, sink = _capture(monkeypatch)
    retrieval.search_trends(query="bakery", persona="busy-family")
    assert sink, "no SQL was executed"
    sql, params = sink[-1]
    assert params.get("persona") == "busy-family"
    assert params.get("q") == "%bakery%", "the topic never reached the query"
    assert "ILIKE %(q)s" in sql, "persona branch has no text match clause"


def test_persona_without_a_topic_is_unfiltered(monkeypatch):
    """No query means the whole persona, which is the existing behaviour."""
    retrieval, sink = _capture(monkeypatch)
    retrieval.search_trends(persona="busy-family")
    sql, params = sink[-1]
    assert "q" not in params
    assert "ILIKE" not in sql


def test_persona_share_ranking_is_kept(monkeypatch):
    """Ordering by share, not size, is deliberate and must survive the fix."""
    retrieval, sink = _capture(monkeypatch)
    retrieval.search_trends(query="bakery", persona="busy-family")
    sql, _ = sink[-1]
    assert "ORDER BY persona_share_pct DESC" in sql


def test_country_filter_reaches_the_sql(monkeypatch):
    """"Bakery trends in Saudi" returned nothing because search_trends had no
    country argument at all - trends were a corpus-wide cluster with no
    geography. The data was always there: 16,532 Saudi bakery posts."""
    retrieval, sink = _capture(monkeypatch)
    retrieval.search_trends(query="bakery", countries=["Saudi Arabia"])
    sql, params = sink[-1]
    assert params.get("countries") == ["Saudi Arabia"]
    assert params.get("q") == "%bakery%", "topic must survive alongside the country"
    assert "country = ANY(%(countries)s)" in sql


def test_country_results_report_attribution_coverage(monkeypatch):
    """60% of posts have no country. A share computed against the whole trend
    would understate it, and a share computed against attributed posts alone
    would overstate confidence - so both travel together."""
    retrieval, sink = _capture(monkeypatch)
    retrieval.search_trends(countries=["Saudi Arabia"])
    sql, _ = sink[-1]
    assert "country_share_pct" in sql
    assert "country_coverage_pct" in sql


def test_country_search_applies_both_floors(monkeypatch):
    """Without a coverage floor, a trend with 14 attributable posts out of 437
    ranked top at "100% Saudi"."""
    retrieval, sink = _capture(monkeypatch)
    retrieval.search_trends(countries=["Saudi Arabia"])
    sql, params = sink[-1]
    assert params.get("floor") == retrieval.COUNTRY_TREND_FLOOR
    assert params.get("min_coverage") == retrieval.MIN_COUNTRY_COVERAGE_PCT


def test_country_and_persona_compose(monkeypatch):
    """Bakery + Saudi + Busy Family is one question, not three."""
    retrieval, sink = _capture(monkeypatch)
    retrieval.search_trends(query="bakery", countries=["Saudi Arabia"],
                            persona="busy-family")
    sql, params = sink[-1]
    assert params.get("persona") == "busy-family"
    assert params.get("countries") == ["Saudi Arabia"]
    assert params.get("q") == "%bakery%"
    assert "persona_post" in sql


def test_persona_only_keeps_its_share_ranking(monkeypatch):
    retrieval, sink = _capture(monkeypatch)
    retrieval.search_trends(persona="busy-family")
    sql, _ = sink[-1]
    assert "ORDER BY persona_share_pct DESC" in sql
