"""Entry point: full PostgreSQL benchmark suite.

Usage:
    uv run python -m runner.run_postgres
"""

import psycopg

from benchmarks.postgres import analyze, bench_insert, bench_select, bench_update
from benchmarks.timer import medians_by_name
from config.settings import BENCH_ITERATIONS, POSTGRES_URL
from reports.collector import ResultCollector
from reports.formatter import save_all

SCHEMAS = [("bench_v4", "v4"), ("bench_v7", "v7")]


def _run_interleaved(conn, bench_fn, iterations):
    """Run bench_fn for v4 and v7 with 1 warmup + N interleaved timed iterations.

    Returns (v4_medians, v7_medians) — each a list[TimingResult].
    """
    # Warmup: one untimed pass per schema
    print("\n  ── Warmup (untimed) ──")
    for schema, uv in SCHEMAS:
        bench_fn(conn, schema, uv)

    # Timed iterations — alternate v4/v7 each iteration so cache effects
    # are symmetric rather than biasing whichever version runs second.
    runs = {"v4": [], "v7": []}
    for i in range(iterations):
        print(f"\n  ── Iteration {i + 1}/{iterations} ──")
        for schema, uv in SCHEMAS:
            results = bench_fn(conn, schema, uv)
            runs[uv].append(results)

    # Compute medians and print summary
    medians = {}
    for uv in ("v4", "v7"):
        medians[uv] = medians_by_name(runs[uv])
        print(f"\n  bench_{uv} medians:")
        for m in medians[uv]:
            all_times = m.extra.get("all_elapsed_seconds", [])
            spread = ", ".join(f"{e:.2f}s" for e in all_times)
            print(f"    {m.test_name}: {m.elapsed_seconds:.2f}s  [{spread}]")

    return medians["v4"], medians["v7"]


def main() -> None:
    print("=" * 60)
    print("PostgreSQL UUID v4 vs v7 Benchmark Suite")
    print(f"  {BENCH_ITERATIONS} timed iterations + 1 warmup per benchmark")
    print("=" * 60)

    collector = ResultCollector()
    analysis_data: dict = {}

    with psycopg.connect(POSTGRES_URL) as conn:
        for label, bench_fn in [
            ("Inserts", bench_insert.run),
            ("Selects", bench_select.run),
            ("Updates", bench_update.run),
        ]:
            print(f"\n{'─' * 50}")
            print(f"  [{label}]")
            v4_medians, v7_medians = _run_interleaved(
                conn, bench_fn, BENCH_ITERATIONS
            )
            collector.add_many(v4_medians)
            collector.add_many(v7_medians)

        # Analysis (index sizes are stable — no iterations needed)
        print(f"\n{'─' * 50}")
        for schema, uv in SCHEMAS:
            print(f"\n  [Analysis] {schema}")
            analysis_data[schema] = analyze.run(conn, schema)

    save_all(collector, "postgres", extra=analysis_data)


if __name__ == "__main__":
    main()
