"""Benchmark timing primitives."""

import statistics
import time
from collections import defaultdict
from contextlib import contextmanager
from dataclasses import dataclass, field
from typing import Iterator


@dataclass
class TimingResult:
    test_name: str
    db_type: str          # "postgres" | "mongodb"
    uuid_version: str     # "v4" | "v7"
    operation: str
    record_count: int
    elapsed_seconds: float
    records_per_second: float
    extra: dict = field(default_factory=dict)

    def to_dict(self) -> dict:
        return {
            "test_name": self.test_name,
            "db_type": self.db_type,
            "uuid_version": self.uuid_version,
            "operation": self.operation,
            "record_count": self.record_count,
            "elapsed_seconds": round(self.elapsed_seconds, 4),
            "records_per_second": round(self.records_per_second, 1),
            "extra": self.extra,
        }


class BenchmarkTimer:
    """Context manager that measures elapsed time and produces a TimingResult."""

    def __init__(
        self,
        test_name: str,
        db_type: str,
        uuid_version: str,
        operation: str,
        record_count: int,
    ) -> None:
        self.test_name = test_name
        self.db_type = db_type
        self.uuid_version = uuid_version
        self.operation = operation
        self.record_count = record_count
        self._start: float = 0.0
        self.result: TimingResult | None = None

    def __enter__(self) -> "BenchmarkTimer":
        self._start = time.monotonic()
        return self

    def __exit__(self, *_) -> None:
        elapsed = time.monotonic() - self._start
        rps = self.record_count / elapsed if elapsed > 0 else 0.0
        self.result = TimingResult(
            test_name=self.test_name,
            db_type=self.db_type,
            uuid_version=self.uuid_version,
            operation=self.operation,
            record_count=self.record_count,
            elapsed_seconds=elapsed,
            records_per_second=rps,
        )


def median_result(results: list[TimingResult]) -> TimingResult:
    """Compute a TimingResult with the median elapsed time from multiple runs."""
    if len(results) == 1:
        return results[0]

    elapsed_values = [r.elapsed_seconds for r in results]
    med = statistics.median(elapsed_values)
    count = results[0].record_count

    return TimingResult(
        test_name=results[0].test_name,
        db_type=results[0].db_type,
        uuid_version=results[0].uuid_version,
        operation=results[0].operation,
        record_count=count,
        elapsed_seconds=med,
        records_per_second=count / med if med > 0 else 0.0,
        extra={
            "iterations": len(results),
            "all_elapsed_seconds": [round(e, 4) for e in elapsed_values],
            "min_elapsed": round(min(elapsed_values), 4),
            "max_elapsed": round(max(elapsed_values), 4),
        },
    )


def medians_by_name(runs: list[list[TimingResult]]) -> list[TimingResult]:
    """Group results from multiple runs by test_name and return median for each."""
    by_name: dict[str, list[TimingResult]] = defaultdict(list)
    name_order: list[str] = []
    for run in runs:
        for r in run:
            by_name[r.test_name].append(r)
            if r.test_name not in name_order:
                name_order.append(r.test_name)
    return [median_result(by_name[name]) for name in name_order]


@contextmanager
def timed(
    test_name: str,
    db_type: str,
    uuid_version: str,
    operation: str,
    record_count: int,
) -> Iterator[BenchmarkTimer]:
    """Convenience context manager yielding a BenchmarkTimer."""
    timer = BenchmarkTimer(test_name, db_type, uuid_version, operation, record_count)
    with timer:
        yield timer
