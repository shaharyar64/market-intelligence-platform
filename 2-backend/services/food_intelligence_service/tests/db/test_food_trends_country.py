import os
from pathlib import Path

import pytest
from sqlalchemy import create_engine, text
from sqlalchemy.engine import make_url

TEST_POSTGRES_DSN = os.environ.get("TEST_POSTGRES_DSN")
pytestmark = pytest.mark.skipif(
    not TEST_POSTGRES_DSN,
    reason="Set TEST_POSTGRES_DSN to a scratch Postgres database to run this test.",
)

_MIGRATION = (Path(__file__).resolve().parents[4]
              / "shared" / "migrations" / "030_food_trends_country.sql")
_SCRATCH_MARKERS = ("scratch", "test", "tmp")


def _assert_scratch_database(dsn: str) -> None:
    name = make_url(dsn).database or ""
    if not any(marker in name.lower() for marker in _SCRATCH_MARKERS):
        raise RuntimeError(
            f"Refusing to run: TEST_POSTGRES_DSN points at database {name!r}, which does not "
            f"look like a scratch database.")


@pytest.fixture(scope="module")
def scratch_engine():
    _assert_scratch_database(TEST_POSTGRES_DSN)
    engine = create_engine(TEST_POSTGRES_DSN, pool_pre_ping=True)
    with engine.begin() as conn:
        conn.execute(text("CREATE SCHEMA IF NOT EXISTS food_intel"))
        conn.execute(text("""CREATE TABLE IF NOT EXISTS food_intel.trends (
            trend_id text PRIMARY KEY, run_id text, created_at timestamptz DEFAULT now())"""))
        sql = _MIGRATION.read_text(encoding="utf-8")
        for chunk in sql.split(";"):
            lines = [ln for ln in chunk.splitlines() if not ln.strip().startswith("--")]
            statement = "\n".join(lines).strip()
            if statement:
                conn.execute(text(statement))
    yield engine
    engine.dispose()


def test_country_column_exists_and_is_nullable(scratch_engine):
    with scratch_engine.begin() as conn:
        row = conn.execute(text(
            "SELECT is_nullable FROM information_schema.columns "
            "WHERE table_schema='food_intel' AND table_name='trends' AND column_name='country'"
        )).fetchone()
    assert row is not None
    assert row[0] == "YES"


def test_country_index_exists(scratch_engine):
    with scratch_engine.begin() as conn:
        rows = conn.execute(text(
            "SELECT indexdef FROM pg_indexes WHERE schemaname='food_intel' "
            "AND tablename='trends' AND indexname='food_trends_by_country_created'"
        )).fetchall()
    assert len(rows) == 1
    assert "country" in rows[0][0]


def test_existing_rows_default_to_null_country(scratch_engine):
    with scratch_engine.begin() as conn:
        conn.execute(text("INSERT INTO food_intel.trends (trend_id, run_id) "
                          "VALUES ('t-null-check', 'all-1') ON CONFLICT DO NOTHING"))
        value = conn.execute(text(
            "SELECT country FROM food_intel.trends WHERE trend_id='t-null-check'")).scalar()
    assert value is None
