from dataclasses import dataclass
from pathlib import Path
from typing import Sequence


@dataclass(frozen=True)
class ValidationResult:
    valid: bool
    errors: list[str]


@dataclass(frozen=True)
class RunItem:
    id: str
    task: str
    domain: str
    input_path: Path


@dataclass(frozen=True)
class RunPaths:
    root: Path

    def __post_init__(self) -> None:
        object.__setattr__(self, "root", Path(self.root).resolve())

    @property
    def input(self) -> Path:
        return self.root / "input"

    @property
    def work(self) -> Path:
        return self.root / "work"

    @property
    def results(self) -> Path:
        return self.root / "results"

    @property
    def logs(self) -> Path:
        return self.root / "logs"

    def ensure(self) -> None:
        for path in (self.root, self.input, self.work, self.results, self.logs):
            path.mkdir(parents=True, exist_ok=True)


@dataclass(frozen=True)
class EvaluationStage:
    name: str
    command: Sequence[str]
    cwd: Path
    result_path: Path | None = None
    report_path: Path | None = None


@dataclass(frozen=True)
class MetricRecord:
    dimension: str
    layer: str
    metric_name: str
    value: float | None
    unit: str
    scope: str
    tp: int | None = None
    fp: int | None = None
    fn: int | None = None
    numerator: int | float | None = None
    denominator: int | float | None = None
