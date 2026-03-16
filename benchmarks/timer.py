"""Benchmark timing primitives."""

import time
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
