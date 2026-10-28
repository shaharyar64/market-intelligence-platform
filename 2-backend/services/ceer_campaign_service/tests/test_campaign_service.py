import os
import re
from unittest.mock import patch

import pytest


os.environ["DEBUG"] = "false"


def test_overview_aggregates_social_totals_and_returns_platforms():
    from services.ceer_campaign_service.app.services import campaign

    rows = [
        {
            "platform": "instagram",
            "followers": 100,
            "total_posts": 5,
            "total_likes": 40,
            "total_shares": 2,
            "public_comment_count": 8,
            "total_views": 0,
            "collected_comments": 6,
        },
        {
            "platform": "tiktok",
            "followers": 200,
            "total_posts": 4,
            "total_likes": 60,
            "total_shares": 3,
            "public_comment_count": 12,
            "total_views": 1_000,
            "collected_comments": 10,
        },
    ]

    with patch.object(campaign.db, "query") as query:
        query.return_value.to_dicts.side_effect = [rows, [{"comments": 978}]]
        result = campaign.get_overview()

    assert result["kpis"] == {
        "followers": 300,
        "posts": 9,
        "likes": 100,
        "shares": 5,
        "public_comments": 20,
        "views": 1_000,
        "collected_comments": 994,
        "social_collected_comments": 16,
        "youtube_collected_comments": 978,
    }
    assert result["platforms"] == rows
    social_sql, youtube_sql = [call.args[0] for call in query.call_args_list]
    assert "ceer_campaign.social_data" in social_sql
    assert "ceer_campaign.youtube_comment_theme_labels" in youtube_sql


def test_before_after_and_sentiment_use_campaign_summary_tables():
    from services.ceer_campaign_service.app.services import campaign

    metric_rows = [{"platform": "twitter", "likes_per_post_change_pct": 231.5}]
    sentiment_rows = [{"comparison_period": "after", "sentiment": "positive", "share_pct": 66.4}]

    with patch.object(campaign.db, "query") as query:
        query.return_value.to_dicts.side_effect = [metric_rows, sentiment_rows]
        assert campaign.get_before_after_metrics() == metric_rows
        assert campaign.get_sentiment() == sentiment_rows

    sql = [call.args[0] for call in query.call_args_list]
    assert "ceer_campaign.launch_before_after_metrics" in sql[0]
    assert "ceer_campaign.launch_sentiment_summary" in sql[1]


def test_launch_impact_uses_the_new_before_day_and_after_analysis_tables():
    from services.ceer_campaign_service.app.services import campaign

    rows = [
        {"period": "before", "posts": 18, "engagements": 17_849},
        {"period": "launch_day", "posts": 25, "engagements": 75_777},
        {"period": "after", "posts": 25, "engagements": 15_496},
    ]
    with patch.object(campaign.db, "query") as query:
        query.return_value.to_dicts.return_value = rows
        assert campaign.get_launch_impact() == rows

    sql = query.call_args.args[0]
    assert "2026-09-14" in sql
    assert "2026-09-20" in sql
    assert "2026-09-21" in sql
    assert "2026-09-22" in sql
    assert "2026-09-28" in sql
    assert "ceer_campaign.launch_before_analysis" in sql
    assert "ceer_campaign.launch_day_analysis" in sql
    assert "ceer_campaign.launch_after_analysis" in sql
    assert "public_comments AS comments" in sql
    assert "ceer_campaign.social_data_posts" not in sql


def test_launch_themes_use_the_new_before_day_and_after_analysis_tables():
    from services.ceer_campaign_service.app.services import campaign

    rows = [{"period": "launch_day", "theme": "Launch & Anticipation", "items": 25, "period_items": 25, "share_pct": 100.0}]
    with patch.object(campaign.db, "query") as query:
        query.return_value.to_dicts.return_value = rows
        assert campaign.get_launch_themes() == rows

    sql = query.call_args.args[0]
    assert "ceer_campaign.launch_before_analysis" in sql
    assert "ceer_campaign.launch_day_analysis" in sql
    assert "ceer_campaign.launch_after_analysis" in sql
    assert "Other / Limited Signal" in sql
    assert "No usable text" in sql
    assert "PARTITION BY period" in sql


def test_activity_uses_the_same_campaign_scope_as_launch_impact():
    from services.ceer_campaign_service.app.services import campaign

    with patch.object(campaign.db, "query") as query:
        query.return_value.to_dicts.return_value = []
        assert campaign.get_activity() == {"days": [], "undated_posts": 0}

    sql = query.call_args.args[0]
    assert "project = 'ceer_campaign'" in sql
    assert "post_id <> '2102783013289652567'" in sql


def test_themes_rejects_unknown_content_type_and_uses_fixed_allowed_value():
    from services.ceer_campaign_service.app.services import campaign

    with pytest.raises(ValueError, match="content_type"):
        campaign.get_themes("unknown")

    with patch.object(campaign.db, "query") as query:
        query.return_value.to_dicts.return_value = []
        assert campaign.get_themes("post") == []

    sql = query.call_args.args[0]
    assert "ceer_campaign.launch_theme_summary" in sql
    assert "content_type = 'post'" in sql


def test_themes_exclude_unreadable_buckets_and_normalize_readable_shares():
    from services.ceer_campaign_service.app.services import campaign

    readable_rows = [{"comparison_period": "after", "theme": "Saudi Pride", "items": 20, "share_pct": 100.0}]
    with patch.object(campaign.db, "query") as query:
        query.return_value.to_dicts.return_value = readable_rows
        assert campaign.get_themes("audience_comment") == readable_rows

    sql = query.call_args.args[0]
    assert "Other / Limited Signal" in sql
    assert "No usable text" in sql
    assert "SUM(items) OVER (PARTITION BY comparison_period)" in sql


def test_google_trends_queries_use_ceer_project_and_escape_filters():
    from services.ceer_campaign_service.app.services import campaign

    line_rows = [{"date": "2026-09-01", "keyword": "CEER", "interest": 42.0}]
    region_rows = [{"keyword": "CEER", "geo_code": "SA-01", "geo_name": "Riyadh", "country": "SA", "score": 50.0}]
    with patch.object(campaign.db, "query") as query:
        query.return_value.to_dicts.side_effect = [line_rows, region_rows]
        assert campaign.get_search_interest(keyword="CEER's", country="SA") == line_rows
        assert campaign.get_search_regions(keyword="CEER's", country="SA") == region_rows

    line_sql, region_sql = [call.args[0] for call in query.call_args_list]
    assert "public.google_trends" in line_sql
    assert "project = 'ceer_campaign'" in line_sql
    assert "keyword = 'CEER''s'" in line_sql
    assert "country = 'SA'" in line_sql
    assert "public.google_trends_regions" in region_sql
    assert "project = 'ceer_campaign'" in region_sql
    assert "keyword = 'CEER''s'" in region_sql


def test_search_regions_scopes_the_latest_snapshot_to_the_selected_term():
    from services.ceer_campaign_service.app.services import campaign

    with patch.object(campaign.db, "query") as query:
        query.return_value.to_dicts.return_value = []
        campaign.get_search_regions(keyword="ceer", country="SA")

    sql = query.call_args.args[0]
    assert re.search(
        r"SELECT MAX\(last_updated\) AS last_updated\s+FROM public\.google_trends_regions\s+WHERE project = 'ceer_campaign' AND country = 'SA' AND keyword = 'ceer'",
        sql,
    )


def test_raw_post_and_comment_analyses_use_the_remaining_campaign_tables():
    from services.ceer_campaign_service.app.services import campaign

    performance_rows = [{"platform": "tiktok", "posts": 6, "views": 1000}]
    top_post_rows = [{"post_id": "post-1", "platform": "tiktok", "views": 900}]
    community_rows = [{"platform": "instagram", "comments": 20, "comment_likes": 5, "themes": 3}]

    with patch.object(campaign.db, "query") as query:
        query.return_value.to_dicts.side_effect = [performance_rows, top_post_rows, community_rows]
        assert campaign.get_content_performance() == performance_rows
        assert campaign.get_top_posts(limit=100) == top_post_rows
        assert campaign.get_community_pulse() == community_rows

    sql = [call.args[0] for call in query.call_args_list]
    assert "ceer_campaign.social_data_posts" in sql[0]
    assert "ceer_campaign.social_data_posts" in sql[1]
    assert "LIMIT 12" in sql[1]
    assert "ceer_campaign.social_data_comments" in sql[2]


def test_youtube_comments_are_included_in_collection():
    from services.ceer_campaign_service.app.services import campaign

    community_rows = [{"platform": "youtube", "comments": 978, "comment_likes": 0, "themes": 8}]

    with patch.object(campaign.db, "query") as query:
        query.return_value.to_dicts.return_value = community_rows
        assert campaign.get_community_pulse() == community_rows

    community_sql = query.call_args.args[0]
    assert "ceer_campaign.youtube_comment_theme_labels" in community_sql
    assert "project = 'ceer_campaign'" in community_sql
    assert "public.youtube_comments" not in community_sql


def test_audience_themes_combine_social_and_youtube_comments_without_date_claims():
    from services.ceer_campaign_service.app.services import campaign

    rows = [{"theme": "Brand & Market Perception", "sub_theme": "General Brand Reaction", "items": 42, "total_items": 100, "share_pct": 42.0}]
    with patch.object(campaign.db, "query") as query:
        query.return_value.to_dicts.return_value = rows
        assert campaign.get_all_audience_themes() == rows

    sql = query.call_args.args[0]
    assert "ceer_campaign.social_data_comments" in sql
    assert "ceer_campaign.youtube_comment_theme_labels" in sql
    assert "Data Quality (Internal)" in sql
    assert "No usable text" in sql


def test_post_and_comment_feeds_support_top_and_all_views():
    from services.ceer_campaign_service.app.services import campaign

    post_rows = [{"post_id": "post-1", "platform": "instagram"}]
    comment_rows = [{"comment_id": "comment-1", "platform": "youtube"}]
    with patch.object(campaign.db, "query") as query:
        query.return_value.to_dicts.side_effect = [post_rows, [{"total": 118}], comment_rows, [{"total": 4381}]]
        assert campaign.get_posts_feed("all", limit=50, offset=0)["total"] == 118
        assert campaign.get_comments_feed("top", limit=12, offset=0, platform="instagram", period="after")["total"] == 4381

    post_sql, post_count_sql, comment_sql, comment_count_sql = [call.args[0] for call in query.call_args_list]
    assert "ceer_campaign.launch_before_analysis" in post_sql
    assert "ceer_campaign.launch_day_analysis" in post_sql
    assert "ceer_campaign.launch_after_analysis" in post_sql
    assert "LIMIT 50 OFFSET 0" in post_sql
    assert "ceer_campaign.social_data_comments" in comment_sql
    assert "ceer_campaign.youtube_comment_theme_labels" in comment_sql
    assert "platform = 'instagram'" in comment_sql
    assert "created_at >= '2026-09-22'" in comment_sql
    assert "created_at < '2026-09-29'" in comment_sql
    assert "COUNT(*)" in post_count_sql
    assert "COUNT(*)" in comment_count_sql


def test_post_feed_theme_filter_and_competitor_reference_analysis_are_queryable():
    from services.ceer_campaign_service.app.services import campaign

    reference_rows = [{
        "reference": "Tesla",
        "typical_comparison": "Cybertruck styling and EV comparison",
        "mentions": 3,
        "comparisons": 1,
        "likes": 12,
    }]
    example_rows = [{"comment_id": "comment-1", "platform": "youtube", "reference": "Tesla", "is_comparison": True}]
    with patch.object(campaign.db, "query") as query:
        query.return_value.to_dicts.side_effect = [[], [{"total": 0}], reference_rows, example_rows]
        assert campaign.get_posts_feed(theme="Exterior Design & Product Form")["total"] == 0
        assert campaign.get_competitor_mentions() == {"references": reference_rows, "examples": example_rows}

    post_sql, post_count_sql, references_sql, examples_sql = [call.args[0] for call in query.call_args_list]
    assert "theme = 'Exterior Design & Product Form'" in post_sql
    assert "theme = 'Exterior Design & Product Form'" in post_count_sql
    assert "ceer_campaign.youtube_comment_theme_labels" in references_sql
    assert "China / Chinese makers" in references_sql
    assert "Tesla / Cybertruck" in references_sql
    assert "Cybertruck', 'Angular design" not in references_sql
    assert "Tesla" in references_sql
    assert "typical_comparison" in references_sql
    assert "reference_catalog(reference, typical_comparison, pattern)" in references_sql
    assert "is_comparison" in examples_sql
