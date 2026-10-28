import json
import os

import boto3
import polars as pl
import psycopg2
from dotenv import load_dotenv

load_dotenv()


class Database:
    """Thin Postgres helper backed by the RDS-managed Secrets Manager credential.

    Credentials come from SECRET_NAME (an `rds!db-...` auto-rotated secret) so
    no DB password is ever stored in .env or code.
    """

    def __init__(self, dbname: str):
        self.dbname = dbname
        self.host = os.environ["DB_HOST"]
        self.port = os.environ.get("DB_PORT", "5432")
        self.secret_name = os.environ["SECRET_NAME"]
        self._username = None
        self._password = None

    def _credentials(self) -> tuple[str, str]:
        if self._password is None:
            client = boto3.client(
                "secretsmanager",
                region_name=os.environ.get("AWS_DEFAULT_REGION") or os.environ.get("AWS_REGION"),
            )
            secret = json.loads(client.get_secret_value(SecretId=self.secret_name)["SecretString"])
            self._username = secret["username"]
            self._password = secret["password"]
        return self._username, self._password

    def get_uri(self, override_db: str | None = None) -> str:
        username, password = self._credentials()
        dbname = override_db or self.dbname
        return f"postgresql+psycopg2://{username}:{password}@{self.host}:{self.port}/{dbname}"

    def connect(self, override_db: str | None = None):
        username, password = self._credentials()
        return psycopg2.connect(
            host=self.host,
            port=self.port,
            dbname=override_db or self.dbname,
            user=username,
            password=password,
            sslmode="require",
        )

    def read_sql(self, query: str, override_db: str | None = None) -> pl.DataFrame:
        with self.connect(override_db) as conn, conn.cursor() as cur:
            cur.execute(query)
            columns = [desc[0] for desc in cur.description]
            rows = cur.fetchall()
        return pl.DataFrame(rows, schema=columns, orient="row")
