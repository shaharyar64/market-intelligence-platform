from services.food_intelligence_service.app.assistant import retrieval


class _FakeCursor:
    def __init__(self, script):
        self._script = list(script)
        self.description = None

    def execute(self, sql, params=None):
        self._last = self._script.pop(0)
        self.description = [(c,) for c in self._last["cols"]]

    def fetchall(self):
        return self._last["rows"]

    def __enter__(self):
        return self

    def __exit__(self, *a):
        return False


class _FakeConn:
    def __init__(self, cursor):
        self._cursor = cursor

    def cursor(self):
        return self._cursor

    def __enter__(self):
        return self

    def __exit__(self, *a):
        return False


def test_search_posts_attaches_distance_per_result(monkeypatch):
    script = [
        {"cols": [], "rows": []},  # SET LOCAL statement_timeout
        {"cols": [], "rows": []},  # SET LOCAL hnsw.ef_search
        {"cols": ["platform", "post_id", "distance"],
         "rows": [("instagram", "p1", 0.20), ("instagram", "p2", 0.35)]},
        {"cols": ["platform", "post_id", "source", "caption", "post_url",
                  "author_username", "likes", "comments", "views",
                  "posted_at", "country", "hashtags"],
         "rows": [("instagram", "p2", "community", "cap2", "url2", "u2", 1, 1, 1,
                   None, "AE", []),
                  ("instagram", "p1", "community", "cap1", "url1", "u1", 2, 2, 2,
                   None, "AE", [])]},
    ]
    cursor = _FakeCursor(script)
    conn = _FakeConn(cursor)
    monkeypatch.setattr(retrieval.store, "get_conn", lambda: conn)
    monkeypatch.setattr(retrieval.store, "model_tag", lambda *a: "tag")

    results = retrieval.search_posts([0.1] * 4, retrieval.PostFilters(), limit=2)

    by_id = {r["post_id"]: r for r in results}
    assert by_id["p1"]["distance"] == 0.20
    assert by_id["p2"]["distance"] == 0.35
    assert [r["post_id"] for r in results] == ["p1", "p2"]
