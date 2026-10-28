import os
import sqlite3
from types import SimpleNamespace

import pytest

os.environ["DEBUG"] = "false"

from services.ceer_campaign_service.app.services import campaign


def test_top_posts_ranks_full_filtered_dataset_and_rejects_invalid_inputs(monkeypatch):
    connection = sqlite3.connect(":memory:")
    connection.row_factory = sqlite3.Row
    connection.execute("ATTACH DATABASE ':memory:' AS ceer_campaign")
    connection.execute("CREATE TABLE ceer_campaign.social_data_posts (post_id TEXT, platform TEXT, post_url TEXT, post_text TEXT, likes INT, shares INT, comments INT, views INT, theme TEXT, sub_theme TEXT)")
    connection.executemany("INSERT INTO ceer_campaign.social_data_posts VALUES (?, ?, NULL, NULL, ?, ?, ?, ?, NULL, NULL)", [
        ("null", "twitter", 1, 0, 0, None),
        ("reach", "twitter", 5, 2, 1, 200),
        ("engagement", "twitter", 20, 10, 5, 100),
        ("instagram", "instagram", 60, 0, 0, None),
    ])
    monkeypatch.setattr(campaign.db, "query", lambda sql: SimpleNamespace(to_dicts=lambda: [dict(row) for row in connection.execute(sql)]))
    assert [row["post_id"] for row in campaign.get_top_posts(2, "twitter", "views")] == ["reach", "engagement"]
    assert [row["post_id"] for row in campaign.get_top_posts(1, "all", "engagement")] == ["instagram"]
    with pytest.raises(ValueError):
        campaign.get_top_posts(6, "unknown", "views")
    with pytest.raises(ValueError):
        campaign.get_top_posts(6, "all", "unknown")
    connection.close()


def test_activity_combines_dates_and_reports_undated_posts(monkeypatch):
    rows = [
        {"uploaded_at": "2026-09-21", "platform": "twitter", "posts": 2, "views": 100, "engagements": 20},
        {"uploaded_at": "2026-09-21T12:00:00Z", "platform": "twitter", "posts": 1, "views": 50, "engagements": 10},
        {"uploaded_at": "2026-09-22", "platform": "instagram", "posts": 1, "views": 0, "engagements": 5},
        {"uploaded_at": "unknown", "platform": "twitter", "posts": 3, "views": 0, "engagements": 0},
    ]
    monkeypatch.setattr(campaign.db, "query", lambda sql: SimpleNamespace(to_dicts=lambda: rows))
    assert campaign.get_activity() == {
        "days": [
            {"date": "2026-09-21", "platform": "twitter", "posts": 3, "views": 150, "engagements": 30},
            {"date": "2026-09-22", "platform": "instagram", "posts": 1, "views": 0, "engagements": 5},
        ],
        "undated_posts": 3,
    }
