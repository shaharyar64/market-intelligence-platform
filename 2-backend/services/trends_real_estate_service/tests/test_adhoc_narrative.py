from services.trends_real_estate_service.app.trends import adhoc, namer

INTERPRET = {"name": "sustainability", "level": "micro", "quadrant": "slow-burner",
             "post_count": 425, "unique_creators": 72, "growth_pct_8w": 61.1,
             "platform_mix": {}, "source_mix": {}}


def _named(**overrides):
    fields = {"name": "Green Building", "summary": "Posts on green building and solar.",
              "related_themes": ["green building", "solar energy"],
              "offering_entities": ["villas"], "is_coherent": True, "confidence": 0.8}
    return namer.ClusterName(**{**fields, **overrides})


def test_a_chat_trend_gets_the_pipeline_narrative(monkeypatch):
    seen = {}
    monkeypatch.setattr(namer, "name_cluster", lambda kw, client, model: _named())

    def opportunity(payload, client, model):
        seen.update(payload)
        return "Brand-led conversation; watch certification claims."
    monkeypatch.setattr(namer, "opportunity_summary", opportunity)
    out = adhoc._narrative("sustainability", "sustainability", ["solar", "leed"], None,
                           INTERPRET, client=object())
    assert out["summary"] == "Posts on green building and solar."
    assert out["related_themes"] == ["green building", "solar energy"]
    assert out["offering_entities"] == ["villas"]
    assert out["keywords"] == ["solar", "leed"]
    assert out["naming_confidence"] == 0.8
    assert out["opportunity_summary"].startswith("Brand-led")
    assert seen["summary"] == out["summary"] and seen["post_count"] == 425


def test_a_given_summary_is_kept(monkeypatch):
    monkeypatch.setattr(namer, "name_cluster", lambda kw, client, model: _named())
    monkeypatch.setattr(namer, "opportunity_summary", lambda *a: "")
    out = adhoc._narrative("x", "x", ["solar"], "Caller's summary", INTERPRET, client=object())
    assert out["summary"] == "Caller's summary" and out["related_themes"]
    assert "opportunity_summary" not in out


def test_a_naming_failure_still_creates_the_trend(monkeypatch):
    def boom(*a):
        raise RuntimeError("quota")
    monkeypatch.setattr(namer, "name_cluster", boom)
    out = adhoc._narrative("x", "branded residences", ["armani"], None, INTERPRET,
                           client=object())
    assert out["summary"] == "Posts retrieved for the question: branded residences"
    assert out["related_themes"] == [] and out["keywords"] == ["armani"]


def test_no_keywords_skips_the_model(monkeypatch):
    monkeypatch.setattr(namer, "name_cluster",
                        lambda *a: (_ for _ in ()).throw(AssertionError("not called")))
    out = adhoc._narrative("x", "q", [], None, INTERPRET, client=object())
    assert out["keywords"] == [] and out["related_themes"] == []


def test_keywords_come_from_the_trend_posts_not_the_background():
    trend = [{"caption": f"solar panels and leed certified green villa {i}",
              "author_username": f"dev{i}"} for i in range(8)]
    background = [{"caption": f"luxury waterfront penthouse launch {i}",
                   "author_username": f"other{i}"} for i in range(8)]
    words = adhoc._keywords(trend, background)
    assert {"solar", "leed"} & set(words)
    assert not {"waterfront", "penthouse"} & set(words)
