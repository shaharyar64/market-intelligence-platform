from unittest.mock import MagicMock, patch

from services.food_intelligence_service.app.enrichment import products_refresh as pr

_ROWS = [{"platform": "instagram", "post_id": "p1", "caption": "حليب طازج", "old": [{"product": "حليب"}]},
         {"platform": "instagram", "post_id": "p2", "caption": "fail me", "old": []}]
_ITEM = {"product": "milk", "product_ar": "حليب", "kind": "product", "confidence": 0.9, "evidence": ["حليب"]}


def _extract(caption):
    return None if caption == "fail me" else [_ITEM]


def test_dry_run_writes_nothing_and_counts_failures(capsys):
    with patch.object(pr, "run_query", return_value=_ROWS), \
         patch.object(pr, "extract", side_effect=_extract), \
         patch.object(pr, "engine") as engine:
        stats = pr.run(limit=10, workers=2, dry_run=True)
    assert stats == {"selected": 2, "previewed": 1, "failed": 1}
    engine.assert_not_called()
    assert "milk / حليب (product)" in capsys.readouterr().out


def test_update_replaces_products_and_stamps_version_only_on_success():
    conn = MagicMock()
    with patch.object(pr, "run_query", return_value=_ROWS), \
         patch.object(pr, "extract", side_effect=_extract), \
         patch.object(pr, "engine") as engine:
        engine.return_value.begin.return_value.__enter__.return_value = conn
        stats = pr.run(limit=10, workers=1, dry_run=False)
    assert stats == {"selected": 2, "updated": 1, "failed": 1}
    (_, params), = [c.args for c in conn.execute.call_args_list]
    assert params["post_id"] == "p1" and params["version"] == pr.PRODUCT_FOCUS_VERSION
    assert '"product_ar": "حليب"' in params["items"]
