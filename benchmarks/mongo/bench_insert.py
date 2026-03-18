"""MongoDB individual insert benchmarks."""

import random
import uuid as _uuid_mod
from datetime import datetime

import bson
import pymongo

from benchmarks.timer import TimingResult, timed
from config.settings import BENCH_INSERT_COUNT
from generators.data_factory import account_fields, customer_fields
from generators.uuid_factory import new_uuid4, new_uuid7


def _coerce_datetimes(doc: dict) -> dict:
    """Convert any ISO string timestamps to datetime objects for MongoDB storage."""
    for key in ("created_at", "updated_at", "opened_at"):
        if key in doc and isinstance(doc[key], str):
            doc[key] = datetime.fromisoformat(doc[key])
    return doc


def _to_binary(u) -> bson.Binary:
    return bson.Binary(u.bytes, subtype=4)


def _insert_customers(
    db: pymongo.database.Database,
    prefix: str,
    uuid_version: str,
    count: int,
) -> TimingResult:
    uuid_fn = new_uuid7 if uuid_version == "v7" else new_uuid4
    col = db[f"{prefix}.customers"]

    docs = []
    for _ in range(count):
        fields, ts = customer_fields()
        uid = uuid_fn(ts)
        
        fields["email"] = f"{uid}@bench.test"  # avoid collision with loaded data
        doc = _coerce_datetimes({"_id": _to_binary(uid), **fields})
        docs.append(doc)

    with timed("insert_customers", "mongodb", uuid_version, "individual_insert", count) as t:
        for doc in docs:
            col.insert_one(doc)

    return t.result


def _insert_accounts(
    db: pymongo.database.Database,
    prefix: str,
    uuid_version: str,
    count: int,
    sample_customer_ids: list[bson.Binary],
) -> TimingResult:
    uuid_fn = new_uuid7 if uuid_version == "v7" else new_uuid4
    col = db[f"{prefix}.accounts"]

    docs = []
    for _ in range(count):
        fields, ts = account_fields()
        uid = uuid_fn(ts)
            
        docs.append(
            _coerce_datetimes(
                {
                    "_id": _to_binary(uid),
                    "customer_id": random.choice(sample_customer_ids),
                    **fields,
                }
            )
        )

    with timed("insert_accounts", "mongodb", uuid_version, "individual_insert", count) as t:
        for doc in docs:
            col.insert_one(doc)

    return t.result


def run(
    db: pymongo.database.Database,
    prefix: str,
    uuid_version: str,
    count: int = BENCH_INSERT_COUNT,
) -> list[TimingResult]:
    """Run individual insert benchmarks for the given prefix. Returns TimingResult list."""
    print(f"  [insert] {prefix} customers ({count:,} docs)...")
    cust_result = _insert_customers(db, prefix, uuid_version, count)
    print(
        f"    → {cust_result.elapsed_seconds:.2f}s "
        f"({cust_result.records_per_second:,.0f} rps)"
    )

    # Sample existing customer IDs for FK-like references
    sample = list(
        db[f"{prefix}.customers"].aggregate([{"$sample": {"size": 1000}}, {"$project": {"_id": 1}}])
    )
    sample_ids = [doc["_id"] for doc in sample]

    print(f"  [insert] {prefix} accounts ({count:,} docs)...")
    acct_result = _insert_accounts(db, prefix, uuid_version, count, sample_ids)
    print(
        f"    → {acct_result.elapsed_seconds:.2f}s "
        f"({acct_result.records_per_second:,.0f} rps)"
    )

    return [cust_result, acct_result]
