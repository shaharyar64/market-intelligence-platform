import os
import pathlib

import pytest
from sqlalchemy import create_engine, text

DSN = os.environ.get("TEST_POSTGRES_DSN")
pytestmark = pytest.mark.skipif(not DSN, reason="TEST_POSTGRES_DSN not set")

MIGRATIONS = pathlib.Path(__file__).resolve().parents[4] / "shared" / "migrations"


@pytest.mark.parametrize("name", [
    "031_create_food_intel_idea_testing.sql",
    "032_create_food_intel_knowledge_base.sql",
])
def test_migration_applies_and_is_idempotent(name):
    sql = (MIGRATIONS / name).read_text(encoding="utf-8")
    engine = create_engine(DSN)
    with engine.begin() as conn:
        conn.execute(text("CREATE EXTENSION IF NOT EXISTS vector"))
        conn.execute(text(sql))
        conn.execute(text(sql))


@pytest.mark.parametrize("table", [
    "idea_concepts", "idea_assessments", "idea_comparisons",
    "knowledge_documents", "knowledge_chunks",
])
def test_table_exists(table):
    engine = create_engine(DSN)
    with engine.connect() as conn:
        found = conn.execute(text(
            "SELECT 1 FROM information_schema.tables "
            "WHERE table_schema='food_intel' AND table_name=:t"
        ), {"t": table}).scalar()
    assert found == 1
