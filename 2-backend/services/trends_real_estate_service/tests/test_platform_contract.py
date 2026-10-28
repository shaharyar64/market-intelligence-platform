"""Guards for the three configs that must agree about which platforms exist.

Every bug these cover was found in production rather than here: the assistant
told people it had no LinkedIn data for weeks because `Platform` still carried
food's two-platform enum, and enrichment crashed partway through a default run
because ENRICH_PLATFORMS listed four platforms that PLATFORM_CONFIG did not.

Both failures are one set-comparison apart from being caught at import time.
"""
from datetime import date, datetime, timezone
from typing import get_args

from services.trends_real_estate_service.app.assistant.toolargs import Platform
from services.trends_real_estate_service.app.core.config import get_settings
from services.trends_real_estate_service.app.enrichment.adapters import (
    PLATFORM_CONFIG,
    _to_iso,
)


def test_enrichment_can_reach_every_platform_it_is_configured_to_enrich():
    """ENRICH_PLATFORMS drives the default run; PLATFORM_CONFIG is what makes a
    platform fetchable. A name in the first without an entry in the second is a
    KeyError raised outside the per-post try, so it aborts the whole batch.
    """
    assert set(get_settings().ENRICH_PLATFORMS) == set(PLATFORM_CONFIG)


def test_the_assistant_can_ask_for_every_platform_that_exists():
    """`Platform` is the tool schema the model sees. A platform missing from it
    is one the model will truthfully report having no tool for, however much
    data sits behind it.
    """
    assert set(get_args(Platform)) == set(PLATFORM_CONFIG)


def test_every_platform_declares_the_columns_fetch_posts_interpolates():
    """fetch_posts builds SQL from these keys, so a missing one fails at query
    time in a batch job rather than at import.
    """
    required = {"post_id", "account_username", "text", "posted_at"}
    for platform, cfg in PLATFORM_CONFIG.items():
        missing = required - set(cfg["columns"])
        assert not missing, f"{platform} is missing columns {sorted(missing)}"
        assert cfg["profile_columns"].get("username"), f"{platform} has no profile username"
        for key in ("posts_table", "profile_table", "profile_join_key"):
            assert cfg.get(key), f"{platform} is missing {key}"


def test_a_post_url_can_be_built_for_every_platform():
    """Either the source table carries a URL column or the config supplies a
    template. A platform with neither yields posts nobody can click through to.
    """
    for platform, cfg in PLATFORM_CONFIG.items():
        assert cfg.get("post_url_template") or cfg["columns"].get("post_url"), (
            f"{platform} can produce neither a real nor a templated post_url")


def test_dates_are_normalised_to_utc_not_stringified():
    """twitter_posts.uploaded_at and linkedin_posts.uploaded_at are date, and
    date is not an instance of datetime - so without an explicit branch these
    reach a timestamptz column as a bare "2026-08-30" and get resolved in the
    session's timezone instead of UTC.
    """
    assert _to_iso(date(2026, 8, 30)) == "2026-08-30T00:00:00+00:00"
    assert _to_iso(datetime(2026, 8, 30, 19, 15)) == "2026-08-30T19:15:00+00:00"
    assert _to_iso(datetime(2026, 8, 30, 19, 15, tzinfo=timezone.utc)) == "2026-08-30T19:15:00+00:00"
    assert _to_iso(None) is None
