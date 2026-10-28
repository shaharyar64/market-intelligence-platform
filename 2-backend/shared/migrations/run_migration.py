"""Run a SQL migration file against the configured database."""
import sys
import os

# Allow running from repo root: python shared/migrations/run_migration.py <file.sql>
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "../..")))

from dotenv import load_dotenv
load_dotenv(os.path.join(os.path.dirname(__file__), "../../.env"))

from shared.database import db


def run(sql_file: str):
    with open(sql_file) as f:
        sql = f.read()

    # Split on semicolons, strip leading comment lines, skip empty chunks
    raw = [s.strip() for s in sql.split(";")]
    statements = []
    for chunk in raw:
        # Drop leading comment lines to get the actual SQL keyword
        lines = [l for l in chunk.splitlines() if not l.strip().startswith("--")]
        sql_body = "\n".join(lines).strip()
        if sql_body:
            statements.append(sql_body)

    import sqlalchemy
    engine = db.get_engine()
    for stmt in statements:
        with engine.begin() as conn:
            conn.execute(sqlalchemy.text(stmt))
    print(f"✅  Migration applied: {sql_file}")


if __name__ == "__main__":
    if len(sys.argv) < 2:
        print("Usage: python run_migration.py <path/to/file.sql>")
        sys.exit(1)
    run(sys.argv[1])
