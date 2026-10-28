import pytest

from services.trends_real_estate_service.app.registry import brands


@pytest.mark.parametrize("name,expected", [
    ("DAMAC Properties", "damac_properties"),
    ("Majid Al Futtaim", "majid_al_futtaim"),
    ("Emaar", "emaar"),
    ("Al Hamra", "al_hamra"),
    ("ROSHN Group l مجموعة روشن", "roshn_group"),
    ("Binghatti  بن غاطي", "binghatti"),
    ("reportage.group", "reportage_group"),
])
def test_slugify_produces_stable_ascii_keys(name, expected):
    assert brands.slugify(name) == expected


def test_slugify_collapses_repeated_separators():
    assert brands.slugify("A -- B") == "a_b"


def test_slugify_returns_empty_string_for_non_ascii_only_names():
    """An Arabic-only name yields no ASCII, so the caller must fall back to
    the username rather than storing an empty key."""
    assert brands.slugify("دار الاركان") == ""


def test_load_registry_prefers_social_data_over_auto_resolution(monkeypatch):
    """social_data is curated, so a username it covers must never be
    auto-resolved from a display name."""
    calls = {}

    def fake_run_query(sql, params=None):
        if "social_data" in sql:
            return [
                {"brand_name": "Aldar", "platform": "instagram", "username": "aldar", "followers": 165281},
                {"brand_name": "DAMAC Properties", "platform": "tiktok",
                 "username": "damacproperties", "followers": 53897},
            ]
        if "brand_posts" in sql:
            return [
                {"platform": "instagram", "author_username": "aldar"},
                {"platform": "tiktok", "author_username": "damacproperties"},
                {"platform": "instagram", "author_username": "roshnksa"},
            ]
        if "instagram_profile" in sql:
            return [{"platform": "instagram", "username": "roshnksa",
                     "display_name": "ROSHN Group l مجموعة روشن",
                     "followers": 92880, "project": "realestate_trends"}]
        calls["written"] = params
        return []

    monkeypatch.setattr(brands.store, "run_query", fake_run_query)
    monkeypatch.setattr(brands, "_write_rows", lambda rows: calls.setdefault("rows", rows))

    report = brands.load_registry()

    by_username = {r["username"]: r for r in calls["rows"]}
    assert by_username["aldar"]["resolution"] == "social_data"
    assert by_username["aldar"]["brand_key"] == "aldar"
    assert by_username["damacproperties"]["brand_key"] == "damac_properties"
    assert by_username["roshnksa"]["resolution"] == "auto"
    assert by_username["roshnksa"]["brand_key"] == "roshn_group"
    assert report["seeded"] == 2
    assert [r["username"] for r in report["auto_resolved"]] == ["roshnksa"]
    assert report["unresolved"] == []


def test_load_registry_falls_back_to_username_when_the_name_has_no_ascii(monkeypatch):
    def fake_run_query(sql, params=None):
        if "social_data" in sql:
            return []
        if "brand_posts" in sql:
            return [{"platform": "instagram", "author_username": "daralarkan"}]
        if "instagram_profile" in sql:
            return [{"platform": "instagram", "username": "daralarkan",
                     "display_name": "دار الاركان", "followers": 40493,
                     "project": "realestate_trends"}]
        return []

    written = {}
    monkeypatch.setattr(brands.store, "run_query", fake_run_query)
    monkeypatch.setattr(brands, "_write_rows", lambda rows: written.setdefault("rows", rows))

    report = brands.load_registry()

    row = written["rows"][0]
    assert row["brand_key"] == "daralarkan"
    assert row["brand_name"] == "دار الاركان"
    assert [r["username"] for r in report["unresolved"]] == ["daralarkan"]


def test_account_to_brand_key_is_case_insensitive(monkeypatch):
    monkeypatch.setattr(brands.store, "run_query",
                        lambda sql, params=None: [{"brand_key": "aldar"}])
    assert brands.account_to_brand_key("instagram", "ALDAR") == "aldar"


def test_load_registry_shares_one_brand_key_across_platforms_for_the_same_username(monkeypatch):
    """The real production defect: 'roshnksa' carries a differently
    formatted display name on each platform ("ROSHN Group l مجموعة روشن" on
    Instagram, "ROSHN l روشن" on Twitter, "ROSHN Group" on LinkedIn). Under
    the old per-account algorithm these slugify to three different keys,
    fragmenting one brand's posts. All three rows must share one brand_key
    and one brand_name, chosen as the display name with the longest slug
    ("ROSHN Group")."""
    def fake_run_query(sql, params=None):
        if "social_data" in sql:
            return []
        if "brand_posts" in sql:
            return [
                {"platform": "instagram", "author_username": "roshnksa"},
                {"platform": "twitter", "author_username": "roshnksa"},
                {"platform": "linkedin", "author_username": "roshnksa"},
            ]
        if "instagram_profile" in sql:
            return [
                {"platform": "instagram", "username": "roshnksa",
                 "display_name": "ROSHN Group l مجموعة روشن",
                 "followers": 92880, "project": "realestate_trends"},
                {"platform": "twitter", "username": "roshnksa",
                 "display_name": "ROSHN l روشن",
                 "followers": 41000, "project": "realestate_trends"},
                {"platform": "linkedin", "username": "roshnksa",
                 "display_name": "ROSHN Group",
                 "followers": 12000, "project": "realestate_trends"},
            ]
        return []

    written = {}
    monkeypatch.setattr(brands.store, "run_query", fake_run_query)
    monkeypatch.setattr(brands, "_write_rows", lambda rows: written.setdefault("rows", rows))

    brands.load_registry()

    rows_by_platform = {r["platform"]: r for r in written["rows"]}
    assert len(rows_by_platform) == 3
    assert {r["brand_key"] for r in rows_by_platform.values()} == {"roshn_group"}
    assert {r["brand_name"] for r in rows_by_platform.values()} == {"ROSHN Group"}
