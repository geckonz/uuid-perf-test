"""Entry point: full MongoDB benchmark suite.

Usage:
    uv run python -m runner.run_mongo
"""

import pymongo

from benchmarks.mongo import analyze, bench_insert, bench_select, bench_update
from benchmarks.timer import medians_by_name
from config.settings import BENCH_ITERATIONS, MONGO_DB_NAME, MONGO_URL
from reports.collector import ResultCollector
from reports.formatter import save_all

PREFIXES = [("uuid_v4", "v4"), ("uuid_v7", "v7")]


def _run_interleaved(db, bench_fn, iterations):
    """Run bench_fn for v4 and v7 with 1 warmup + N interleaved timed iterations.

    Returns (v4_medians, v7_medians) — each a list[TimingResult].
    """
    # Warmup: one untimed pass per prefix
    print("\n  ── Warmup (untimed) ──")
    for prefix, uv in PREFIXES:
        bench_fn(db, prefix, uv)

    # Timed iterations — alternate v4/v7 each iteration so cache effects
    # are symmetric rather than biasing whichever version runs second.
    runs = {"v4": [], "v7": []}
    for i in range(iterations):
        print(f"\n  ── Iteration {i + 1}/{iterations} ──")
        for prefix, uv in PREFIXES:
            results = bench_fn(db, prefix, uv)
            runs[uv].append(results)

    # Compute medians and print summary
    medians = {}
    for uv in ("v4", "v7"):
        medians[uv] = medians_by_name(runs[uv])
        print(f"\n  uuid_{uv} medians:")
        for m in medians[uv]:
            all_times = m.extra.get("all_elapsed_seconds", [])
            spread = ", ".join(f"{e:.2f}s" for e in all_times)
            print(f"    {m.test_name}: {m.elapsed_seconds:.2f}s  [{spread}]")

    return medians["v4"], medians["v7"]


def main() -> None:
    print("=" * 60)
    print("MongoDB UUID v4 vs v7 Benchmark Suite")
    print(f"  {BENCH_ITERATIONS} timed iterations + 1 warmup per benchmark")
    print("=" * 60)

    collector = ResultCollector()
    analysis_data: dict = {}

    client = pymongo.MongoClient(MONGO_URL)
    db = client[MONGO_DB_NAME]

    try:
        for label, bench_fn in [
            ("Inserts", bench_insert.run),
            ("Selects", bench_select.run),
            ("Updates", bench_update.run),
        ]:
            print(f"\n{'─' * 50}")
            print(f"  [{label}]")
            v4_medians, v7_medians = _run_interleaved(
                db, bench_fn, BENCH_ITERATIONS
            )
            collector.add_many(v4_medians)
            collector.add_many(v7_medians)

        # Analysis (collection stats are stable — no iterations needed)
        print(f"\n{'─' * 50}")
        for prefix, uv in PREFIXES:
            print(f"\n  [Analysis] {prefix}")
            analysis_data[prefix] = analyze.run(db, prefix)
    finally:
        client.close()

    save_all(collector, "mongodb", extra=analysis_data)


if __name__ == "__main__":
    main()
