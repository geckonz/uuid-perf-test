"""PostgreSQL select/query benchmarks: PK lookup, range query, join."""

import random
from datetime import datetime, timedelta, timezone

import psycopg

from benchmarks.timer import TimingResult, timed
from config.settings import (
    BENCH_JOIN_COUNT,
    BENCH_SELECT_COUNT,
    POSTGRES_URL,
    RANGE_QUERY_DAYS,
    RANGE_QUERY_HOURS,
)


def _sample_ids(conn: psycopg.Connection, table: str, n: int) -> list:
    with conn.cursor() as cur:
        cur.execute(f"SELECT id FROM {table} ORDER BY random() LIMIT %s", (n,))
        return [row[0] for row in cur.fetchall()]


def _sample_customer_ids_for_join(conn: psycopg.Connection, schema: str, n: int) -> list:
    with conn.cursor() as cur:
        cur.execute(
            f"SELECT customer_id FROM {schema}.accounts ORDER BY random() LIMIT %s",
            (n,),
        )
        return [row[0] for row in cur.fetchall()]


def bench_pk_select(
    conn: psycopg.Connection,
    schema: str,
    uuid_version: str,
    count: int = BENCH_SELECT_COUNT,
) -> TimingResult:
    """SELECT * WHERE id = ? on customers table."""
    ids = _sample_ids(conn, f"{schema}.customers", count)
    sql = f"SELECT * FROM {schema}.customers WHERE id = %s"

    with timed("pk_select_customers", "postgres", uuid_version, "pk_lookup", count) as t:
        with conn.cursor() as cur:
            for uid in ids:
                cur.execute(sql, (uid,))
                cur.fetchone()

    return t.result


def bench_range_query(
    conn: psycopg.Connection,
    schema: str,
    uuid_version: str,
    window_hours: int,
    label: str,
) -> TimingResult:
    """SELECT * WHERE created_at BETWEEN start AND end."""
    # Sample a random start within the data range
    with conn.cursor() as cur:
        cur.execute(f"SELECT MIN(created_at), MAX(created_at) FROM {schema}.customers")
        min_ts, max_ts = cur.fetchone()

    span = (max_ts - min_ts).total_seconds()
    window_sec = window_hours * 3600

    results = []
    for _ in range(10):  # run 10 range queries, average them
        offset_sec = random.uniform(0, max(0, span - window_sec))
        start_ts = min_ts + timedelta(seconds=offset_sec)
        end_ts = start_ts + timedelta(hours=window_hours)

        with conn.cursor() as cur:
            cur.execute(
                f"SELECT * FROM {schema}.customers "
                f"WHERE created_at BETWEEN %s AND %s",
                (start_ts, end_ts),
            )
            rows = cur.fetchall()
            results.append(len(rows))

    total_rows = sum(results)
    op = f"range_query_{label}"

    with timed(op, "postgres", uuid_version, op, total_rows) as t:
        for _ in range(10):
            offset_sec = random.uniform(0, max(0, span - window_sec))
            start_ts = min_ts + timedelta(seconds=offset_sec)
            end_ts = start_ts + timedelta(hours=window_hours)
            with conn.cursor() as cur:
                cur.execute(
                    f"SELECT * FROM {schema}.customers "
                    f"WHERE created_at BETWEEN %s AND %s",
                    (start_ts, end_ts),
                )
                cur.fetchall()

    return t.result


def bench_join(
    conn: psycopg.Connection,
    schema: str,
    uuid_version: str,
    count: int = BENCH_JOIN_COUNT,
) -> TimingResult:
    """JOIN customers + accounts by customer PK."""
    cust_ids = _sample_customer_ids_for_join(conn, schema, count)
    sql = (
        f"SELECT c.id, c.name, a.id, a.account_type, a.balance "
        f"FROM {schema}.customers c "
        f"JOIN {schema}.accounts a ON a.customer_id = c.id "
        f"WHERE c.id = %s"
    )

    with timed("join_customer_accounts", "postgres", uuid_version, "join_lookup", count) as t:
        with conn.cursor() as cur:
            for cid in cust_ids:
                cur.execute(sql, (cid,))
                cur.fetchall()

    return t.result


def run(
    conn: psycopg.Connection,
    schema: str,
    uuid_version: str,
) -> list[TimingResult]:
    """Run all select benchmarks. Returns TimingResult list."""
    results = []

    print(f"  [select] {schema} PK lookup ({BENCH_SELECT_COUNT:,} rows)...")
    r = bench_pk_select(conn, schema, uuid_version)
    print(f"    → {r.elapsed_seconds:.2f}s ({r.records_per_second:,.0f} rps)")
    results.append(r)

    print(f"  [select] {schema} range query (1 hour window)...")
    r = bench_range_query(conn, schema, uuid_version, RANGE_QUERY_HOURS, "1hr")
    print(f"    → {r.elapsed_seconds:.2f}s ({r.record_count:,} rows returned)")
    results.append(r)

    print(f"  [select] {schema} range query (1 day window)...")
    r = bench_range_query(conn, schema, uuid_version, RANGE_QUERY_DAYS * 24, "1day")
    print(f"    → {r.elapsed_seconds:.2f}s ({r.record_count:,} rows returned)")
    results.append(r)

    print(f"  [select] {schema} join ({BENCH_JOIN_COUNT:,} customers)...")
    r = bench_join(conn, schema, uuid_version)
    print(f"    → {r.elapsed_seconds:.2f}s ({r.records_per_second:,.0f} rps)")
    results.append(r)

    return results
