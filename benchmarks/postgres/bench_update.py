"""PostgreSQL update benchmarks: UPDATE by PK."""

import random

import psycopg

from benchmarks.timer import TimingResult, timed
from config.settings import BENCH_UPDATE_COUNT


def run(
    conn: psycopg.Connection,
    schema: str,
    uuid_version: str,
    count: int = BENCH_UPDATE_COUNT,
) -> list[TimingResult]:
    """Run update-by-PK benchmarks on accounts. Returns TimingResult list."""
    # Sample account IDs
    with conn.cursor() as cur:
        cur.execute(
            f"SELECT id FROM {schema}.accounts ORDER BY random() LIMIT %s", (count,)
        )
        ids = [row[0] for row in cur.fetchall()]

    sql = f"UPDATE {schema}.accounts SET balance = %s, updated_at = NOW() WHERE id = %s"

    print(f"  [update] {schema} accounts by PK ({count:,} rows)...")

    with timed("update_accounts_by_pk", "postgres", uuid_version, "pk_update", count) as t:
        with conn.cursor() as cur:
            for uid in ids:
                new_balance = round(random.uniform(-10_000, 500_000), 2)
                cur.execute(sql, (new_balance, uid))
        conn.commit()

    r = t.result
    print(f"    → {r.elapsed_seconds:.2f}s ({r.records_per_second:,.0f} rps)")
    return [r]
