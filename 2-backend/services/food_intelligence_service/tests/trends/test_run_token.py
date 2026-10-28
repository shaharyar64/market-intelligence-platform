from services.food_intelligence_service.app.trends.metrics import run_token


def test_run_token_differs_for_runs_sharing_a_prefix():
    runs = ["tracked-202610141102", "tracked-202610141140", "sa-202610141101", "sa-202610141147"]
    assert len({run_token(r) for r in runs}) == len(runs)


def test_run_token_is_stable_for_one_run():
    assert run_token("sa-202610141147") == run_token("sa-202610141147")


def _post(source, day):
    from datetime import datetime
    return {"source": source, "posted_at": datetime(2026, *day)}


def test_anchor_date_follows_community_when_it_is_the_majority():
    from services.food_intelligence_service.app.trends.run import anchor_date
    posts = [_post("community", (5, 12))] * 3 + [_post("brand", (10, 13))]
    assert str(anchor_date(posts)) == "2026-05-12"


def test_anchor_date_follows_newest_post_when_community_is_a_minority():
    from services.food_intelligence_service.app.trends.run import anchor_date
    posts = [_post("community", (5, 12))] + [_post("brand", (10, 13))] * 3
    assert str(anchor_date(posts)) == "2026-10-13"
