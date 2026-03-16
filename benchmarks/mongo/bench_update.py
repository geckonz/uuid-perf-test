"""MongoDB update benchmarks: update_one by _id."""

import random
from datetime import datetime, timezone

import pymongo

from benchmarks.timer import TimingResult, timed
from config.settings import BENCH_UPDATE_COUNT


def run(
    db: pymongo.database.Database,
    prefix: str,
    uuid_version: str,
    count: int = BENCH_UPDATE_COUNT,
) -> list[TimingResult]:
    """Run update-by-_id benchmarks on accounts. Returns TimingResult list."""
    col = db[f"{prefix}.accounts"]

    sample = list(col.aggregate([{"$sample": {"size": count}}, {"$project": {"_id": 1}}]))
    ids = [doc["_id"] for doc in sample]

    print(f"  [update] {prefix} accounts by _id ({count:,} docs)...")

    with timed("update_accounts_by_id", "mongodb", uuid_version, "pk_update", count) as t:
        for uid in ids:
            col.update_one(
                {"_id": uid},
                {
                    "$set": {
                        "balance": round(random.uniform(-10_000, 500_000), 2),
                        "updated_at": datetime.now(tz=timezone.utc),
                    }
                },
            )

    r = t.result
    print(f"    → {r.elapsed_seconds:.2f}s ({r.records_per_second:,.0f} rps)")
    return [r]
