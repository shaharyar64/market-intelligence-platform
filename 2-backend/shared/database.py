import os
import json
import time
import boto3
import logging
import polars as pl
from sqlalchemy import create_engine
from urllib.parse import quote_plus
from pathlib import Path
from types import SimpleNamespace
from dotenv import load_dotenv

# Read straight from env (same names/defaults as gateway Settings) so shared/ has
# no dependency on the gateway package — each service image ships only shared/ +
# its own dir. .env is loaded for local runs; in containers env_file already set it.
load_dotenv(Path(__file__).resolve().parents[1] / ".env")
settings = SimpleNamespace(
    DB_NAME=os.getenv("DB_NAME"),
    SECRET_NAME=os.getenv("SECRET_NAME"),
    DB_HOST=os.getenv("DB_HOST"),
    DB_PORT=os.getenv("DB_PORT", "5432"),
    AWS_ACCESS_KEY_ID=os.getenv("AWS_ACCESS_KEY_ID"),
    AWS_SECRET_ACCESS_KEY=os.getenv("AWS_SECRET_ACCESS_KEY"),
    AWS_REGION=os.getenv("AWS_REGION"),
)

_AUTH_ERROR_PHRASES = (
    "password authentication failed",
    "invalid password",
    "no password supplied",
)


def _is_auth_error(exc: Exception) -> bool:
    msg = str(exc).lower()
    return any(phrase in msg for phrase in _AUTH_ERROR_PHRASES)


class Database:
    """Postgres handler with SQLAlchemy connection pooling, Polars support, and credential self-healing."""

    def __init__(self, db_name: str = None):
        self.db_name = db_name or settings.DB_NAME
        self.secret_name = settings.SECRET_NAME
        self.host = settings.DB_HOST
        self.port = settings.DB_PORT
        self.client = boto3.client(
            "secretsmanager",
            aws_access_key_id=settings.AWS_ACCESS_KEY_ID,
            aws_secret_access_key=settings.AWS_SECRET_ACCESS_KEY,
            region_name=settings.AWS_REGION,
        )
        self.engine = None
        self._secret_cache: dict | None = None
        self._secret_fetched_at: float = 0
        self._SECRET_TTL: float = 300  # 5 minutes

    def get_secret(self, force_refresh: bool = False) -> dict:
        """Fetch credentials from Secrets Manager with 5-min TTL cache."""
        now = time.monotonic()
        if (
            force_refresh
            or self._secret_cache is None
            or (now - self._secret_fetched_at) > self._SECRET_TTL
        ):
            logging.info("Fetching DB credentials from Secrets Manager...")
            response = self.client.get_secret_value(SecretId=self.secret_name)
            self._secret_cache = json.loads(response["SecretString"])
            self._secret_fetched_at = now
        return self._secret_cache

    def get_uri(self, override_db: str = None, force_refresh: bool = False) -> str:
        secret = self.get_secret(force_refresh=force_refresh)
        username = quote_plus(secret["username"])
        password = quote_plus(secret["password"])
        db = override_db or self.db_name
        return (
            f"postgresql+psycopg2://{username}:{password}"
            f"@{self.host}:{self.port}/{db}?sslmode=require"
        )

    def _build_engine(self, force_refresh: bool = False):
        uri = self.get_uri(force_refresh=force_refresh)
        return create_engine(
            uri,
            pool_pre_ping=True,
            pool_size=5,
            max_overflow=2,
            pool_recycle=1800,
        )

    def get_engine(self):
        if self.engine is None:
            self.engine = self._build_engine()
            logging.info("✅ Database connection pool created.")
        return self.engine

    def reset_engine(self):
        """Dispose current pool, refresh credentials, rebuild engine."""
        logging.warning("Auth failure — resetting DB engine with fresh credentials")
        if self.engine:
            self.engine.dispose()
            self.engine = None
        self.engine = self._build_engine(force_refresh=True)
        logging.info("✅ DB engine rebuilt with fresh credentials.")

    def query(self, sql: str) -> pl.DataFrame:
        """Execute SQL, auto-healing once on credential errors."""
        start = time.perf_counter()
        try:
            return self._execute(sql, start)
        except Exception as e:
            if not _is_auth_error(e):
                raise RuntimeError(f"Database query failed: {e}")
            logging.warning(f"Auth error detected — retrying with fresh credentials: {e}")
            self.reset_engine()
            try:
                return self._execute(sql, start)
            except Exception as retry_exc:
                raise RuntimeError(f"Database query failed after credential refresh: {retry_exc}")

    def _execute(self, sql: str, start: float) -> pl.DataFrame:
        engine = self.get_engine()
        with engine.connect() as conn:
            df = pl.read_database(query=sql, connection=conn, infer_schema_length=10000)
        logging.info(f"DB query time: {time.perf_counter() - start:.3f}s")
        return df

    def show_tables(self) -> pl.DataFrame:
        query = """
        SELECT table_schema, table_name
        FROM information_schema.tables
        WHERE table_schema NOT IN ('pg_catalog', 'information_schema')
        ORDER BY table_schema, table_name;
        """
        return self.query(query)


# Global instance (import and reuse anywhere)
db = Database()
