from services.trends_real_estate_service.app.trends import documents, namer, run

ANALYSIS = {
    "description": "Waterfront homes on an island.",
    "themes": [{"label": "Waterfront Luxury"}, {"label": "Island Lifestyle"}, {"label": ""}],
    "offering_focus": [{"offering": "damac islands 2"}],
    "semiotic": {"text": "Calm and aspirational.",
                 "visual": {"urban": 0.2, "aspirational": 0.9, "bold": 0.7, "natural": None}},
    "functional_visual": [{"category": "view", "visual_evidence": "Sea behind two people."},
                          {"category": "people", "visual_evidence": ""}],
    "keywords": ["damac"],
}


def test_document_has_each_section_in_order():
    doc = documents.semantic_document(ANALYSIS)
    assert doc == ("Description:\nWaterfront homes on an island.\n\n"
                   "Themes:\nWaterfront Luxury; Island Lifestyle.\n\n"
                   "Offering:\ndamac islands 2.\n\n"
                   "Semantic Context:\nCalm and aspirational.\n\n"
                   "Visual Context:\naspirational, bold. Sea behind two people.")


def test_keywords_and_metadata_stay_out_of_the_document():
    assert "damac\n" not in documents.semantic_document(ANALYSIS)
    assert "keywords" not in documents.semantic_document(ANALYSIS).lower()


def test_missing_sections_are_left_out():
    doc = documents.semantic_document({"themes": [{"label": "Golf Living"}]})
    assert doc == "Themes:\nGolf Living."


def test_analysis_can_arrive_as_json_text_or_be_absent():
    assert documents.semantic_document('{"description": "Villas."}') == "Description:\nVillas."
    assert documents.semantic_document(None) == ""
    assert documents.semantic_document({"semiotic": "not a dict"}) == ""


def test_document_tag_is_separate_from_the_caption_tag():
    assert documents.document_tag().endswith("+" + documents.VERSION)


def _cluster(n, label, start):
    return [{"platform": "instagram", "post_id": str(start + i)} for i in range(n)], \
        {f"instagram:{start + i}": label for i in range(n)}


def test_clusters_given_the_same_name_become_one_trend(monkeypatch):
    posts_a, labels_a = _cluster(60, 0, 0)
    posts_b, labels_b = _cluster(80, 1, 100)
    posts_c, labels_c = _cluster(70, 2, 200)
    names = {"a": "Waterfront Living", "b": "Waterfront Living", "c": "Golf Course Living"}
    monkeypatch.setattr(namer, "name_cluster", lambda kw, client, model: namer.ClusterName(
        name=names[kw[0]], summary="", is_coherent=True, confidence=0.8))
    state = {"cluster": {"labels": {**labels_a, **labels_b, **labels_c},
                         "keywords": {"0": ["a"], "1": ["b"], "2": ["c"]}}}

    stats = run.stage_name(posts_a + posts_b + posts_c, state, None, "m", 50, "run")

    assert stats["named"] == 2
    assert stats["merged_same_name"] == 1
    by_name = {n["name"]: n for n in state["named"].values()}
    assert by_name["Waterfront Living"]["cluster_label"] == 1
    assert by_name["Waterfront Living"]["merged_labels"] == [0]
    trend_of = run._labels_of(state["named"])
    assert trend_of[0] == trend_of[1] != trend_of[2]
