"""Entry point: full MongoDB benchmark suite.

Usage:
    uv run python -m runner.run_mongo
"""

import pymongo

from benchmarks.mongo import analyze, bench_insert, bench_select, bench_update
from config.settings import MONGO_DB_NAME, MONGO_URL
from reports.collector import ResultCollector
from reports.formatter import save_all


def main() -> None:
    print("=" * 60)
    print("MongoDB UUID v4 vs v7 Benchmark Suite")
    print("=" * 60)

    collector = ResultCollector()
    analysis_data: dict = {}

    client = pymongo.MongoClient(MONGO_URL)
    db = client[MONGO_DB_NAME]

    try:
        for prefix, uuid_version in [("uuid_v4", "v4"), ("uuid_v7", "v7")]:
            print(f"\n--- {prefix} ({uuid_version}) ---")

            print("\n[Inserts]")
            results = bench_insert.run(db, prefix, uuid_version)
            collector.add_many(results)

            print("\n[Selects]")
            results = bench_select.run(db, prefix, uuid_version)
            collector.add_many(results)

            print("\n[Updates]")
            results = bench_update.run(db, prefix, uuid_version)
            collector.add_many(results)

            print("\n[Analysis]")
            analysis_data[prefix] = analyze.run(db, prefix)
    finally:
        client.close()

    save_all(collector, "mongodb", extra=analysis_data)


if __name__ == "__main__":
    main()
