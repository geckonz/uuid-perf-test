"""Format benchmark results as ASCII table, JSON, and Markdown."""

import json
from datetime import datetime, timezone
from pathlib import Path

from tabulate import tabulate

from config.settings import RESULTS_DIR
from reports.collector import ComparisonRow, ResultCollector


def _fmt_elapsed(seconds: float | None) -> str:
    if seconds is None:
        return "—"
    return f"{seconds:.2f}s"


def _fmt_speedup(speedup: float | None) -> str:
    if speedup is None:
        return "—"
    return f"{speedup:.2f}x"


def _fmt_rps(rps: float | None) -> str:
    if rps is None:
        return "—"
    return f"{rps:,.0f}"


def _build_table_rows(comparisons: list[ComparisonRow]) -> list[list]:
    rows = []
    for c in comparisons:
        rows.append(
            [
                c.test_name,
                _fmt_elapsed(c.v4_elapsed),
                _fmt_elapsed(c.v7_elapsed),
                _fmt_speedup(c.speedup),
                _fmt_rps(c.v4_rps),
                _fmt_rps(c.v7_rps),
            ]
        )
    return rows


HEADERS = ["Operation", "v4 time", "v7 time", "v7 speedup", "v4 rps", "v7 rps"]


def print_ascii_table(collector: ResultCollector, db_type: str) -> None:
    """Print an ASCII table to stdout."""
    comparisons = collector.comparisons()
    rows = _build_table_rows(comparisons)
    print(f"\n{'=' * 70}")
    print(f"  {db_type.upper()} Benchmark Results")
    print(f"{'=' * 70}")
    print(tabulate(rows, headers=HEADERS, tablefmt="simple"))
    print(f"{'=' * 70}\n")


def save_json(
    collector: ResultCollector,
    db_type: str,
    extra: dict | None = None,
    timestamp: str | None = None,
) -> Path:
    """Save results as JSON. Returns the output path."""
    RESULTS_DIR.mkdir(parents=True, exist_ok=True)
    ts = timestamp or datetime.now(tz=timezone.utc).strftime("%Y%m%d_%H%M%S")
    path = RESULTS_DIR / f"run_{ts}_{db_type}.json"

    comparisons = collector.comparisons()
    payload = {
        "db_type": db_type,
        "timestamp": ts,
        "results": [r.to_dict() for r in collector.all_results()],
        "comparisons": [
            {
                "test_name": c.test_name,
                "operation": c.operation,
                "v4_elapsed_seconds": c.v4_elapsed,
                "v7_elapsed_seconds": c.v7_elapsed,
                "speedup": c.speedup,
                "v4_records_per_second": c.v4_rps,
                "v7_records_per_second": c.v7_rps,
            }
            for c in comparisons
        ],
        "extra": extra or {},
    }
    path.write_text(json.dumps(payload, indent=2, default=str))
    print(f"JSON results saved → {path}")
    return path


def save_markdown(
    collector: ResultCollector,
    db_type: str,
    extra: dict | None = None,
    timestamp: str | None = None,
) -> Path:
    """Save results as a Markdown file with GFM tables. Returns the output path."""
    RESULTS_DIR.mkdir(parents=True, exist_ok=True)
    ts = timestamp or datetime.now(tz=timezone.utc).strftime("%Y%m%d_%H%M%S")
    path = RESULTS_DIR / f"run_{ts}_{db_type}.md"

    comparisons = collector.comparisons()
    rows = _build_table_rows(comparisons)

    lines = [
        f"# {db_type.upper()} UUID v4 vs v7 Benchmark Results",
        f"",
        f"**Run timestamp:** {ts}",
        f"",
        f"## Performance Comparison",
        f"",
        tabulate(rows, headers=HEADERS, tablefmt="github"),
        f"",
    ]

    # Index size section (if provided)
    if extra:
        for schema_key, analysis in extra.items():
            lines.append(f"## Index Analysis — `{schema_key}`")
            lines.append("")
            if "index_sizes" in analysis:
                lines.append("### Index Sizes")
                lines.append("")
                idx_rows = [
                    [name, info.get("size_pretty", "—"), info.get("size_bytes", 0)]
                    for name, info in analysis["index_sizes"].items()
                ]
                lines.append(
                    tabulate(idx_rows, headers=["Index", "Size", "Bytes"], tablefmt="github")
                )
                lines.append("")
            if "coll_stats" in analysis:
                lines.append("### Collection Stats")
                lines.append("")
                for coll, stats in analysis["coll_stats"].items():
                    lines.append(f"**{coll}**")
                    lines.append("")
                    stat_rows = [[k, v] for k, v in stats.items() if k != "index_sizes"]
                    lines.append(tabulate(stat_rows, headers=["Stat", "Value"], tablefmt="github"))
                    lines.append("")

    path.write_text("\n".join(lines))
    print(f"Markdown results saved → {path}")
    return path


def save_all(
    collector: ResultCollector,
    db_type: str,
    extra: dict | None = None,
) -> tuple[Path, Path]:
    """Print ASCII table + save JSON + Markdown. Returns (json_path, md_path)."""
    print_ascii_table(collector, db_type)
    ts = datetime.now(tz=timezone.utc).strftime("%Y%m%d_%H%M%S")
    json_path = save_json(collector, db_type, extra, ts)
    md_path = save_markdown(collector, db_type, extra, ts)
    return json_path, md_path
