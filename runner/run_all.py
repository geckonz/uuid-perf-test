"""Entry point: run both PostgreSQL and MongoDB benchmark suites sequentially.

Usage:
    uv run python -m runner.run_all
"""

import sys

from runner.run_mongo import main as run_mongo
from runner.run_postgres import main as run_postgres


def main() -> None:
    print("\n" + "#" * 70)
    print("# UUID v4 vs v7 Full Benchmark Suite")
    print("#" * 70 + "\n")

    print(">>> Running PostgreSQL benchmarks...")
    run_postgres()

    print("\n>>> Running MongoDB benchmarks...")
    run_mongo()

    print("\n>>> All benchmarks complete. Check reports/results/ for output.")


if __name__ == "__main__":
    main()
