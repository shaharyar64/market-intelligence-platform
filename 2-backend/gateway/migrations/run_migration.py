"""Run a SQL migration file against the gateway's admin database (DB_ADMIN).

Mirrors shared/migrations/run_migration.py, but that one targets DB_NAME
(the "raw_data" service data DB) via shared.database.db. The services /
users / user_services tables live in DB_ADMIN (the "dashboards" auth/admin
DB) instead, so this reuses gateway.app.db.session.get_engine() — the same
async engine and credential-refresh logic the gateway API itself uses.
"""
import sys
import os
import asyncio

# Allow running from repo root: python gateway/migrations/run_migration.py <file.sql>
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "../..")))

from dotenv import load_dotenv
load_dotenv(os.path.join(os.path.dirname(__file__), "../../.env"))

import sqlalchemy
from gateway.app.db.session import get_engine


def _split_statements(sql: str) -> list[str]:
    # Strip `-- ...` comments (whole-line or trailing) BEFORE splitting on
    # semicolons — a `;` inside a comment must not end a statement early.
    stripped_lines = []
    for line in sql.splitlines():
        idx = line.find("--")
        stripped_lines.append(line[:idx] if idx != -1 else line)
    sql = "\n".join(stripped_lines)

    return [chunk.strip() for chunk in sql.split(";") if chunk.strip()]


async def run(sql_file: str):
    with open(sql_file) as f:
        sql = f.read()

    statements = _split_statements(sql)
    engine = get_engine()
    if engine is None:
        raise RuntimeError(
            "Could not build a DB engine — check DB_ADMIN/DB_HOST/POSTGRES_DSN settings"
        )

    for stmt in statements:
        async with engine.begin() as conn:
            result = await conn.execute(sqlalchemy.text(stmt))
            if result.returns_rows:
                for row in result.fetchall():
                    print(row)

    print(f"✅  Migration applied: {sql_file}")


if __name__ == "__main__":
    if len(sys.argv) < 2:
        print("Usage: python gateway/migrations/run_migration.py <path/to/file.sql>")
        sys.exit(1)
    asyncio.run(run(sys.argv[1]))
