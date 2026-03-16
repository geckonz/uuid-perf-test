"""Aggregate TimingResult objects and compute v4 vs v7 ratios."""

from dataclasses import dataclass

from benchmarks.timer import TimingResult


@dataclass
class ComparisonRow:
    operation: str
    test_name: str
    v4: TimingResult | None
    v7: TimingResult | None

    @property
    def v4_elapsed(self) -> float | None:
        return self.v4.elapsed_seconds if self.v4 else None

    @property
    def v7_elapsed(self) -> float | None:
        return self.v7.elapsed_seconds if self.v7 else None

    @property
    def speedup(self) -> float | None:
        """v7 speedup over v4 (>1 means v7 is faster)."""
        if self.v4 and self.v7 and self.v7.elapsed_seconds > 0:
            return self.v4.elapsed_seconds / self.v7.elapsed_seconds
        return None

    @property
    def v4_rps(self) -> float | None:
        return self.v4.records_per_second if self.v4 else None

    @property
    def v7_rps(self) -> float | None:
        return self.v7.records_per_second if self.v7 else None


class ResultCollector:
    """Aggregates TimingResult objects and computes comparison rows."""

    def __init__(self) -> None:
        self._v4: list[TimingResult] = []
        self._v7: list[TimingResult] = []

    def add(self, result: TimingResult) -> None:
        if result.uuid_version == "v4":
            self._v4.append(result)
        elif result.uuid_version == "v7":
            self._v7.append(result)

    def add_many(self, results: list[TimingResult]) -> None:
        for r in results:
            self.add(r)

    def comparisons(self) -> list[ComparisonRow]:
        """Return a list of ComparisonRow objects, pairing v4 and v7 results by test_name."""
        v4_by_name: dict[str, TimingResult] = {r.test_name: r for r in self._v4}
        v7_by_name: dict[str, TimingResult] = {r.test_name: r for r in self._v7}

        all_names = list(dict.fromkeys(list(v4_by_name) + list(v7_by_name)))
        rows = []
        for name in all_names:
            v4 = v4_by_name.get(name)
            v7 = v7_by_name.get(name)
            op = (v4 or v7).operation
            rows.append(ComparisonRow(operation=op, test_name=name, v4=v4, v7=v7))
        return rows

    def all_results(self) -> list[TimingResult]:
        return self._v4 + self._v7
