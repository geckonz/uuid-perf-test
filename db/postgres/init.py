"""Initialize PostgreSQL schemas and tables for the UUID benchmark."""

from pathlib import Path

import psycopg

from config.settings import POSTGRES_URL

SCHEMA_DIR = Path(__file__).parent


def init_postgres() -> None:
    sql_v4 = (SCHEMA_DIR / "schema_v4.sql").read_text()
    sql_v7 = (SCHEMA_DIR / "schema_v7.sql").read_text()

    with psycopg.connect(POSTGRES_URL, autocommit=True) as conn:
        print("Creating bench_v4 schema...")
        conn.execute(sql_v4)
        print("Creating bench_v7 schema...")
        conn.execute(sql_v7)
        print("PostgreSQL schemas initialized.")


if __name__ == "__main__":
    init_postgres()
