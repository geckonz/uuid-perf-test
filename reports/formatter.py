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
INDEX_HEADERS = ["Index", "v4 size", "v7 size", "v7 reduction"]


def _fmt_bytes(b: int) -> str:
    if b >= 1_073_741_824:
        return f"{b / 1_073_741_824:.1f} GB"
    if b >= 1_048_576:
        return f"{b / 1_048_576:.0f} MB"
    if b >= 1024:
        return f"{b / 1024:.0f} KB"
    return f"{b} B"


def _build_index_comparison(extra: dict | None) -> list[list] | None:
    """Build index size comparison rows from analysis data.

    Works for both PostgreSQL (index_sizes per schema) and MongoDB (coll_stats).
    Returns list of [label, v4_size, v7_size, reduction%] rows, or None.
    """
    if not extra:
        return None

    keys = list(extra.keys())
    if len(keys) < 2:
        return None

    v4_key = [k for k in keys if "v4" in k]
    v7_key = [k for k in keys if "v7" in k]
    if not v4_key or not v7_key:
        return None
    v4_data = extra[v4_key[0]]
    v7_data = extra[v7_key[0]]

    rows = []

    # PostgreSQL: match indexes by stripping version from name
    if "index_sizes" in v4_data and "index_sizes" in v7_data:
        v4_idx = v4_data["index_sizes"]
        v7_idx = v7_data["index_sizes"]

        # Build lookup: normalized name → (v4_bytes, v7_bytes)
        def _normalize(name: str) -> str:
            return name.replace("_v4_", "_").replace("_v7_", "_")

        v4_by_norm = {_normalize(k): v for k, v in v4_idx.items()}
        v7_by_norm = {_normalize(k): v for k, v in v7_idx.items()}

        for norm_name in v4_by_norm:
            if norm_name in v7_by_norm:
                v4_bytes = v4_by_norm[norm_name]["size_bytes"]
                v7_bytes = v7_by_norm[norm_name]["size_bytes"]
                if v4_bytes > 0:
                    reduction = (1 - v7_bytes / v4_bytes) * 100
                    rows.append([
                        norm_name,
                        _fmt_bytes(v4_bytes),
                        _fmt_bytes(v7_bytes),
                        f"{reduction:+.0f}%",
                    ])

        # Sort largest first
        rows.sort(key=lambda r: -int(''.join(c for c in r[1] if c.isdigit()) or '0'))

    # MongoDB: compare total_index_size_bytes per collection
    elif "coll_stats" in v4_data and "coll_stats" in v7_data:
        for coll in v4_data["coll_stats"]:
            if coll in v7_data["coll_stats"]:
                v4_stats = v4_data["coll_stats"][coll]
                v7_stats = v7_data["coll_stats"][coll]
                if "error" in v4_stats or "error" in v7_stats:
                    continue
                v4_bytes = v4_stats.get("total_index_size_bytes", 0)
                v7_bytes = v7_stats.get("total_index_size_bytes", 0)
                if v4_bytes > 0:
                    reduction = (1 - v7_bytes / v4_bytes) * 100
                    rows.append([
                        f"{coll} (all indexes)",
                        _fmt_bytes(v4_bytes),
                        _fmt_bytes(v7_bytes),
                        f"{reduction:+.0f}%",
                    ])

    return rows if rows else None


def print_ascii_table(
    collector: ResultCollector, db_type: str, extra: dict | None = None
) -> None:
    """Print an ASCII table to stdout."""
    comparisons = collector.comparisons()
    rows = _build_table_rows(comparisons)
    print(f"\n{'=' * 70}")
    print(f"  {db_type.upper()} Benchmark Results")
    print(f"{'=' * 70}")
    print(tabulate(rows, headers=HEADERS, tablefmt="simple"))

    idx_rows = _build_index_comparison(extra)
    if idx_rows:
        print(f"\n  Index Size Comparison")
        print(f"  {'-' * 60}")
        print(tabulate(idx_rows, headers=INDEX_HEADERS, tablefmt="simple"))

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

    # Index size comparison summary
    idx_rows = _build_index_comparison(extra)
    if idx_rows:
        lines.append("## Index Size Comparison")
        lines.append("")
        lines.append(tabulate(idx_rows, headers=INDEX_HEADERS, tablefmt="github"))
        lines.append("")

    # Detailed index analysis per schema/prefix
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
    print_ascii_table(collector, db_type, extra)
    ts = datetime.now(tz=timezone.utc).strftime("%Y%m%d_%H%M%S")
    json_path = save_json(collector, db_type, extra, ts)
    md_path = save_markdown(collector, db_type, extra, ts)
    return json_path, md_path
