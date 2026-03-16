"""Entry point: full PostgreSQL benchmark suite.

Usage:
    uv run python -m runner.run_postgres
"""

import psycopg

from benchmarks.postgres import analyze, bench_insert, bench_select, bench_update
from config.settings import POSTGRES_URL
from reports.collector import ResultCollector
from reports.formatter import save_all


def main() -> None:
    print("=" * 60)
    print("PostgreSQL UUID v4 vs v7 Benchmark Suite")
    print("=" * 60)

    collector = ResultCollector()
    analysis_data: dict = {}

    with psycopg.connect(POSTGRES_URL) as conn:
        for schema, uuid_version in [("bench_v4", "v4"), ("bench_v7", "v7")]:
            print(f"\n--- {schema} ({uuid_version}) ---")

            print("\n[Inserts]")
            results = bench_insert.run(conn, schema, uuid_version)
            collector.add_many(results)

            print("\n[Selects]")
            results = bench_select.run(conn, schema, uuid_version)
            collector.add_many(results)

            print("\n[Updates]")
            results = bench_update.run(conn, schema, uuid_version)
            collector.add_many(results)

            print("\n[Analysis]")
            analysis_data[schema] = analyze.run(conn, schema)

    save_all(collector, "postgres", extra=analysis_data)


if __name__ == "__main__":
    main()
