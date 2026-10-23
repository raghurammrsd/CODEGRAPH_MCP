"""Data models for SWE-bench Comparative Evaluation Harness."""
from __future__ import annotations

from dataclasses import asdict, dataclass, field
from typing import Any


@dataclass(frozen=True)
class SWEBenchTask:
    """A realistic benchmark problem instance modeled after SWE-bench Lite."""

    instance_id: str
    repository_name: str
    problem_statement: str
    target_symbol: str
    golden_files: tuple[str, ...]
    golden_lines: tuple[int, ...]
    hints: str = ""


@dataclass(frozen=True)
class StrategyResult:
    """Execution results for a single agent strategy (Baseline vs CodeGraph)."""

    strategy_name: str
    tokens_consumed: int
    turns_count: int
    files_read_count: int
    lines_read_count: int
    target_localized: bool
    first_turn_accuracy: bool
    duration_ms: float

    def as_dict(self) -> dict[str, Any]:
        return asdict(self)


@dataclass(frozen=True)
class TaskComparison:
    """Side-by-side comparison of Baseline vs CodeGraph for one task."""

    instance_id: str
    baseline: StrategyResult
    codegraph: StrategyResult
    token_reduction_pct: float
    turns_reduction_pct: float
    cost_reduction_est_usd: float

    def as_dict(self) -> dict[str, Any]:
        return {
            "instance_id": self.instance_id,
            "baseline": self.baseline.as_dict(),
            "codegraph": self.codegraph.as_dict(),
            "token_reduction_pct": round(self.token_reduction_pct, 2),
            "turns_reduction_pct": round(self.turns_reduction_pct, 2),
            "cost_reduction_est_usd": round(self.cost_reduction_est_usd, 4),
        }


@dataclass
class SWEBenchReport:
    """Aggregated empirical benchmark report across all evaluated tasks."""

    total_tasks: int
    comparisons: list[TaskComparison] = field(default_factory=list)
    avg_token_reduction_pct: float = 0.0
    avg_turns_reduction_pct: float = 0.0
    codegraph_localization_accuracy: float = 0.0
    baseline_localization_accuracy: float = 0.0
    total_cost_savings_usd: float = 0.0

    def as_dict(self) -> dict[str, Any]:
        return {
            "total_tasks": self.total_tasks,
            "comparisons": [c.as_dict() for c in self.comparisons],
            "avg_token_reduction_pct": round(self.avg_token_reduction_pct, 2),
            "avg_turns_reduction_pct": round(self.avg_turns_reduction_pct, 2),
            "codegraph_localization_accuracy": round(self.codegraph_localization_accuracy, 2),
            "baseline_localization_accuracy": round(self.baseline_localization_accuracy, 2),
            "total_cost_savings_usd": round(self.total_cost_savings_usd, 4),
        }
