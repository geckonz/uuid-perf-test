"""MongoDB select/query benchmarks: PK lookup, range query, lookup."""

import random
from datetime import datetime, timedelta

import bson
import pymongo

from benchmarks.timer import TimingResult, timed
from config.settings import BENCH_JOIN_COUNT, BENCH_SELECT_COUNT


def bench_pk_select(
    db: pymongo.database.Database,
    prefix: str,
    uuid_version: str,
    count: int = BENCH_SELECT_COUNT,
) -> TimingResult:
    """find_one by _id on customers collection."""
    col = db[f"{prefix}.customers"]
    sample = list(col.aggregate([{"$sample": {"size": count}}, {"$project": {"_id": 1}}]))
    ids = [doc["_id"] for doc in sample]

    with timed("pk_select_customers", "mongodb", uuid_version, "pk_lookup", count) as t:
        for uid in ids:
            col.find_one({"_id": uid})

    return t.result


def bench_range_query(
    db: pymongo.database.Database,
    prefix: str,
    uuid_version: str,
    window_hours: int,
    label: str,
) -> TimingResult:
    """find() with created_at range filter."""
    col = db[f"{prefix}.customers"]

    # Find approximate min/max dates via sample
    pipeline = [
        {"$group": {"_id": None, "min": {"$min": "$created_at"}, "max": {"$max": "$created_at"}}}
    ]
    agg = list(col.aggregate(pipeline))
    if not agg:
        return None
    min_ts = agg[0]["min"]
    max_ts = agg[0]["max"]
    if isinstance(min_ts, str):
        min_ts = datetime.fromisoformat(min_ts)
    if isinstance(max_ts, str):
        max_ts = datetime.fromisoformat(max_ts)
    span = (max_ts - min_ts).total_seconds()
    window_sec = window_hours * 3600

    total_rows = 0
    op = f"range_query_{label}"

    with timed(op, "mongodb", uuid_version, op, 0) as t:
        for _ in range(10):
            offset_sec = random.uniform(0, max(0, span - window_sec))
            start_ts = min_ts + timedelta(seconds=offset_sec)
            end_ts = start_ts + timedelta(hours=window_hours)
            cursor = col.find({"created_at": {"$gte": start_ts, "$lt": end_ts}})
            total_rows += len(list(cursor))

    # Patch record count after measurement
    t.result.record_count = total_rows
    t.result.records_per_second = total_rows / t.result.elapsed_seconds if t.result.elapsed_seconds > 0 else 0

    return t.result


def bench_lookup(
    db: pymongo.database.Database,
    prefix: str,
    uuid_version: str,
    count: int = BENCH_JOIN_COUNT,
) -> TimingResult:
    """Fetch account + customer (lookup pattern)."""
    acct_col = db[f"{prefix}.accounts"]
    cust_col = db[f"{prefix}.customers"]

    sample = list(acct_col.aggregate([{"$sample": {"size": count}}, {"$project": {"_id": 1, "customer_id": 1}}]))

    with timed("lookup_account_customer", "mongodb", uuid_version, "lookup", count) as t:
        for doc in sample:
            acct_col.find_one({"_id": doc["_id"]})
            cust_col.find_one({"_id": doc["customer_id"]})

    return t.result


def run(
    db: pymongo.database.Database,
    prefix: str,
    uuid_version: str,
) -> list[TimingResult]:
    """Run all select benchmarks. Returns TimingResult list."""
    results = []

    print(f"  [select] {prefix} PK lookup ({BENCH_SELECT_COUNT:,} docs)...")
    r = bench_pk_select(db, prefix, uuid_version)
    print(f"    → {r.elapsed_seconds:.2f}s ({r.records_per_second:,.0f} rps)")
    results.append(r)

    print(f"  [select] {prefix} range query (1 hour window)...")
    r = bench_range_query(db, prefix, uuid_version, 1, "1hr")
    if r:
        print(f"    → {r.elapsed_seconds:.2f}s ({r.record_count:,} docs returned)")
        results.append(r)

    print(f"  [select] {prefix} range query (1 day window)...")
    r = bench_range_query(db, prefix, uuid_version, 24, "1day")
    if r:
        print(f"    → {r.elapsed_seconds:.2f}s ({r.record_count:,} docs returned)")
        results.append(r)

    print(f"  [select] {prefix} lookup ({BENCH_JOIN_COUNT:,} account+customer pairs)...")
    r = bench_lookup(db, prefix, uuid_version)
    print(f"    → {r.elapsed_seconds:.2f}s ({r.records_per_second:,.0f} rps)")
    results.append(r)

    return results
