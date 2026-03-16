"""CLI: Load benchmark CSV data into PostgreSQL using COPY protocol.

Usage:
    uv run python -m loaders.load_postgres

Loads v4 schema first, then v7. Times each phase and saves load_timings.json.
"""

import json
import time
from datetime import datetime, timezone
from pathlib import Path

import psycopg

from config.settings import (
    ACCOUNTS_V4_CSV,
    ACCOUNTS_V7_CSV,
    CUSTOMERS_V4_CSV,
    CUSTOMERS_V7_CSV,
    POSTGRES_URL,
    RESULTS_DIR,
)

CUSTOMER_COLS = ["id", "name", "email", "phone", "address", "created_at", "updated_at"]
ACCOUNT_COLS = [
    "id",
    "customer_id",
    "account_type",
    "balance",
    "currency",
    "status",
    "opened_at",
    "updated_at",
]


def _copy_csv(conn: psycopg.Connection, table: str, columns: list[str], csv_path: Path) -> float:
    """COPY a CSV file into a table. Returns elapsed seconds."""
    col_list = ", ".join(columns)
    sql = f"COPY {table} ({col_list}) FROM STDIN WITH (FORMAT CSV, HEADER TRUE)"
    start = time.monotonic()
    with conn.cursor() as cur:
        with cur.copy(sql) as copy:
            with csv_path.open("rb") as f:
                while chunk := f.read(65536):
                    copy.write(chunk)
    elapsed = time.monotonic() - start
    print(f"  COPY {table}: {elapsed:.2f}s")
    return elapsed


def _rebuild_indexes(conn: psycopg.Connection, schema: str) -> dict[str, float]:
    """Drop and recreate secondary indexes concurrently. Returns timing dict."""
    timings: dict[str, float] = {}

    index_defs = {
        f"{schema}_customers_email": (
            f"CREATE UNIQUE INDEX CONCURRENTLY {schema}_customers_email_idx"
            f" ON {schema}.customers (email)"
        ),
        f"{schema}_customers_created_at": (
            f"CREATE INDEX CONCURRENTLY {schema}_customers_created_at_idx"
            f" ON {schema}.customers (created_at)"
        ),
        f"{schema}_accounts_customer_id": (
            f"CREATE INDEX CONCURRENTLY {schema}_accounts_customer_id_idx"
            f" ON {schema}.accounts (customer_id)"
        ),
        f"{schema}_accounts_opened_at": (
            f"CREATE INDEX CONCURRENTLY {schema}_accounts_opened_at_idx"
            f" ON {schema}.accounts (opened_at)"
        ),
        f"{schema}_accounts_status": (
            f"CREATE INDEX CONCURRENTLY {schema}_accounts_status_idx"
            f" ON {schema}.accounts (status)"
        ),
    }

    # Drop existing secondary indexes (PK indexes are kept)
    with conn.cursor() as cur:
        for name in index_defs:
            cur.execute(f"DROP INDEX IF EXISTS {schema}.{name}_idx")
    conn.commit()

    # Recreate each index (CONCURRENTLY cannot run inside a transaction)
    for name, ddl in index_defs.items():
        start = time.monotonic()
        # CONCURRENTLY requires autocommit
        old_autocommit = conn.autocommit
        conn.autocommit = True
        try:
            conn.execute(ddl)
        finally:
            conn.autocommit = old_autocommit
        elapsed = time.monotonic() - start
        timings[name] = elapsed
        print(f"  Index {name}: {elapsed:.2f}s")

    return timings


def load_schema(
    conn: psycopg.Connection,
    schema: str,
    customers_csv: Path,
    accounts_csv: Path,
) -> dict:
    """Load one schema (v4 or v7). Returns timing dict."""
    print(f"\n=== Loading {schema} ===")
    timings: dict = {}

    # Truncate tables (accounts first due to FK)
    print("  Truncating tables...")
    with conn.cursor() as cur:
        cur.execute(f"TRUNCATE {schema}.accounts, {schema}.customers RESTART IDENTITY CASCADE")
    conn.commit()

    # Disable FK constraint trigger during load
    with conn.cursor() as cur:
        cur.execute(f"ALTER TABLE {schema}.accounts DISABLE TRIGGER ALL")
    conn.commit()

    # COPY customers
    timings["copy_customers"] = _copy_csv(
        conn, f"{schema}.customers", CUSTOMER_COLS, customers_csv
    )
    conn.commit()

    # COPY accounts
    timings["copy_accounts"] = _copy_csv(conn, f"{schema}.accounts", ACCOUNT_COLS, accounts_csv)
    conn.commit()

    # Re-enable and validate FK
    print("  Re-enabling FK constraint...")
    with conn.cursor() as cur:
        cur.execute(f"ALTER TABLE {schema}.accounts ENABLE TRIGGER ALL")
    conn.commit()

    # Rebuild secondary indexes (timed)
    print("  Rebuilding secondary indexes...")
    timings["indexes"] = _rebuild_indexes(conn, schema)

    # VACUUM ANALYZE
    print("  VACUUM ANALYZE...")
    conn.autocommit = True
    start = time.monotonic()
    conn.execute(f"VACUUM ANALYZE {schema}.customers")
    conn.execute(f"VACUUM ANALYZE {schema}.accounts")
    timings["vacuum_analyze"] = time.monotonic() - start
    conn.autocommit = False

    print(f"  {schema} load complete.")
    return timings


def main() -> None:
    RESULTS_DIR.mkdir(parents=True, exist_ok=True)

    all_timings: dict = {}

    with psycopg.connect(POSTGRES_URL) as conn:
        all_timings["bench_v4"] = load_schema(
            conn, "bench_v4", CUSTOMERS_V4_CSV, ACCOUNTS_V4_CSV
        )
        all_timings["bench_v7"] = load_schema(
            conn, "bench_v7", CUSTOMERS_V7_CSV, ACCOUNTS_V7_CSV
        )

    ts = datetime.now(tz=timezone.utc).strftime("%Y%m%d_%H%M%S")
    out_path = RESULTS_DIR / f"load_timings_{ts}_postgres.json"
    out_path.write_text(json.dumps(all_timings, indent=2))
    print(f"\nLoad timings saved → {out_path}")


if __name__ == "__main__":
    main()
