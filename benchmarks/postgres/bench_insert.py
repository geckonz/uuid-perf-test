"""PostgreSQL individual insert benchmarks."""

import random
import uuid
from datetime import datetime, timezone

import psycopg

from benchmarks.timer import TimingResult, timed
from config.settings import BENCH_INSERT_COUNT, POSTGRES_URL
from generators.data_factory import account_fields, customer_fields
from generators.uuid_factory import new_uuid4, new_uuid7

ACCOUNT_TYPES = ("checking", "savings", "credit", "investment")


def _insert_customers(
    conn: psycopg.Connection,
    schema: str,
    uuid_version: str,
    count: int,
) -> TimingResult:
    uuid_fn = new_uuid7 if uuid_version == "v7" else new_uuid4
    sql = (
        f"INSERT INTO {schema}.customers "
        "(id, name, email, phone, address, created_at, updated_at) "
        "VALUES (%s, %s, %s, %s, %s, %s, %s)"
    )
    rows = []
    for _ in range(count):
        uid_str = str(uuid_fn())
        fields = customer_fields()
        fields["email"] = f"{uid_str}@bench.test"  # avoid collision with loaded data
        rows.append((uid_str, *fields.values()))

    with timed("insert_customers", "postgres", uuid_version, "individual_insert", count) as t:
        with conn.cursor() as cur:
            for row in rows:
                cur.execute(sql, row)
        conn.commit()

    return t.result


def _insert_accounts(
    conn: psycopg.Connection,
    schema: str,
    uuid_version: str,
    count: int,
    sample_customer_ids: list[str],
) -> TimingResult:
    uuid_fn = new_uuid7 if uuid_version == "v7" else new_uuid4
    sql = (
        f"INSERT INTO {schema}.accounts "
        "(id, customer_id, account_type, balance, currency, status, opened_at, updated_at) "
        "VALUES (%s, %s, %s, %s, %s, %s, %s, %s)"
    )

    rows = []
    for _ in range(count):
        fields = account_fields()
        rows.append(
            (
                str(uuid_fn()),
                random.choice(sample_customer_ids),
                fields["account_type"],
                fields["balance"],
                fields["currency"],
                fields["status"],
                fields["opened_at"],
                fields["updated_at"],
            )
        )

    with timed("insert_accounts", "postgres", uuid_version, "individual_insert", count) as t:
        with conn.cursor() as cur:
            for row in rows:
                cur.execute(sql, row)
        conn.commit()

    return t.result


def run(
    conn: psycopg.Connection,
    schema: str,
    uuid_version: str,
    count: int = BENCH_INSERT_COUNT,
) -> list[TimingResult]:
    """Run individual insert benchmarks for the given schema. Returns TimingResult list."""
    print(f"  [insert] {schema} customers ({count:,} rows)...")
    cust_result = _insert_customers(conn, schema, uuid_version, count)
    print(f"    → {cust_result.elapsed_seconds:.2f}s ({cust_result.records_per_second:,.0f} rps)")

    # Fetch a sample of customer IDs for account FK references
    with conn.cursor() as cur:
        cur.execute(
            f"SELECT id FROM {schema}.customers ORDER BY random() LIMIT 1000"
        )
        sample_ids = [str(row[0]) for row in cur.fetchall()]

    print(f"  [insert] {schema} accounts ({count:,} rows)...")
    acct_result = _insert_accounts(conn, schema, uuid_version, count, sample_ids)
    print(f"    → {acct_result.elapsed_seconds:.2f}s ({acct_result.records_per_second:,.0f} rps)")

    return [cust_result, acct_result]
