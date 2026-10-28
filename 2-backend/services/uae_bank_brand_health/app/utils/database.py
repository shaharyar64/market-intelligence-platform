import os
import json
import time
import boto3
import logging
import polars as pl
from sqlalchemy import create_engine, text
from urllib.parse import quote_plus
from functools import lru_cache
from dotenv import load_dotenv
from services.uae_bank_brand_health.app.core.config import get_settings

# Load .env variables
load_dotenv()
settings = get_settings()


class Database:
    """Optimized Postgres handler with SQLAlchemy connection pooling and Polars support."""

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
        self.engine = None  # SQLAlchemy connection pool (lazy-init)

    def get_secret(self) -> dict:
        """Fetch database credentials from AWS Secrets Manager (cached)."""
        logging.info("Fetching database credentials from AWS Secrets Manager...")
        response = self.client.get_secret_value(SecretId=self.secret_name)
        return json.loads(response["SecretString"])

    def get_uri(self, override_db: str = None) -> str:
        """Construct the PostgreSQL connection URI."""
        secret = self.get_secret()
        username = quote_plus(secret["username"])
        password = quote_plus(secret["password"])
        db = override_db or self.db_name
        return (
            f"postgresql+psycopg2://{username}:{password}"
            f"@{self.host}:{self.port}/{db}?sslmode=require"
        )

    def get_engine(self):
        """Create (or reuse) a SQLAlchemy engine with connection pooling."""
        if self.engine is None:
            uri = self.get_uri()
            self.engine = create_engine(
                uri,
                pool_pre_ping=True,     # auto-check dead connections
                pool_size=5,            # keep 5 open connections
                max_overflow=2,         # allow 2 temporary extra
                pool_recycle=1800,      # refresh every 30 mins
            )
            logging.info("✅ Database connection pool created.")
        return self.engine

    def query(self, sql: str) -> pl.DataFrame:
        """Execute SQL and return a Polars DataFrame (fast, pooled connection)."""
        start = time.perf_counter()
        engine = self.get_engine()
        try:
            with engine.connect() as conn:
                df = pl.read_database(query=sql, connection=conn)
                end = time.perf_counter()
                logging.info(f"DB query time: {end - start:.3f}s")
            return df
        except Exception as e:
            raise RuntimeError(f"Database query failed: {e}")

    def show_tables(self) -> pl.DataFrame:
        """Return a list of all tables (excluding system schemas)."""
        query = """
        SELECT table_schema, table_name
        FROM information_schema.tables
        WHERE table_schema NOT IN ('pg_catalog', 'information_schema')
        ORDER BY table_schema, table_name;
        """
        return self.query(query)


# ✅ Global instance (import and reuse anywhere)
db = Database()
