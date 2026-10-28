import json
from unittest.mock import MagicMock


def _client_returning(payload: dict):
    client = MagicMock()
    client.chat.completions.create.return_value.choices = [
        MagicMock(message=MagicMock(content=json.dumps(payload)))
    ]
    return client


def test_slugify():
    from services.food_intelligence_service.app.trends.namer import slugify
    assert slugify("Protein Coffee!") == "protein-coffee"
    assert slugify("  Gut -- Health ") == "gut-health"


def test_name_cluster_parses_structured_output():
    from services.food_intelligence_service.app.trends.namer import name_cluster
    payload = {"name": "Protein Coffee", "summary": "RTD coffee with protein.",
               "related_themes": ["fitness"], "product_entities": ["protein coffee"],
               "is_coherent": True, "confidence": 0.9}
    out = name_cluster(["cap1"], ["fitness"], ["protein"], _client_returning(payload), "m")
    assert out.name == "Protein Coffee" and out.is_coherent is True


def test_name_cluster_falls_back_incoherent_on_garbage():
    from services.food_intelligence_service.app.trends.namer import name_cluster
    client = MagicMock()
    client.chat.completions.create.return_value.choices = [
        MagicMock(message=MagicMock(content="not json at all"))
    ]
    out = name_cluster(["cap"], [], [], client, "m")
    assert out.is_coherent is False and out.confidence == 0.0


def test_repair_partition_dedupes_and_buckets_strays():
    from services.food_intelligence_service.app.trends.namer import Umbrella, repair_partition
    umbrellas = [
        Umbrella(name="A", summary="s", members=["t1", "t2", "unknown"]),
        Umbrella(name="B", summary="s", members=["t2", "t3"]),   # t2 duplicated
    ]
    out = repair_partition(umbrellas, ["t1", "t2", "t3", "t4"])
    placed = [m for u in out for m in u.members]
    assert sorted(placed) == ["t1", "t2", "t3", "t4"]            # exactly once each
    assert out[-1].name.startswith("Misc") and out[-1].members == ["t4"]
    assert "unknown" not in placed


def test_group_umbrellas_parse_failure_yields_misc_bucket():
    from services.food_intelligence_service.app.trends.namer import group_umbrellas
    client = MagicMock()
    client.chat.completions.create.side_effect = RuntimeError("api down")
    out = group_umbrellas([{"trend_id": "t1", "name": "n", "summary": "s",
                            "keywords": [], "post_count": 20}], client, "m")
    assert len(out) == 1 and out[0].members == ["t1"]
