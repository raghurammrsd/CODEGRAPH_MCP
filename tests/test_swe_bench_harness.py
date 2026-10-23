"""Comprehensive test suite for SWE-bench Comparative Evaluation Harness."""
from __future__ import annotations

from pathlib import Path

import pytest

from benchmarks.swe_bench.harness import evaluate_task, run_swe_bench_suite
from benchmarks.swe_bench.models import SWEBenchTask
from codegraph.indexing.indexer import Indexer


@pytest.fixture
def swe_bench_sample_repo(tmp_path: Path) -> Path:
    repo = tmp_path / "swe_repo"
    repo.mkdir()

    src = repo / "src"
    src.mkdir()

    (src / "validators.py").write_text(
        "import re\n\n"
        "class ASCIIUsernameValidator:\n"
        "    regex = r'^[\\w.@+-]+$'\n"
        "    def validate(self, value: str) -> bool:\n"
        "        return bool(re.match(self.regex, value))\n",
        encoding="utf-8",
    )

    indexer = Indexer(repo)
    indexer.index()
    return repo


def test_evaluate_single_task(swe_bench_sample_repo: Path) -> None:
    task = SWEBenchTask(
        instance_id="django__django-11099",
        repository_name="django",
        problem_statement="ASCIIUsernameValidator regex trailing newline bug",
        target_symbol="ASCIIUsernameValidator",
        golden_files=("src/validators.py",),
        golden_lines=(3, 7),
    )

    comparison = evaluate_task(swe_bench_sample_repo, task)
    assert comparison.instance_id == "django__django-11099"
    assert comparison.token_reduction_pct > 0.0
    assert comparison.turns_reduction_pct > 0.0
    assert comparison.codegraph.target_localized is True
    assert comparison.cost_reduction_est_usd >= 0.0


def test_run_swe_bench_suite(swe_bench_sample_repo: Path) -> None:
    tasks = [
        SWEBenchTask(
            instance_id="task-1",
            repository_name="test",
            problem_statement="Fix ASCIIUsernameValidator regex",
            target_symbol="ASCIIUsernameValidator",
            golden_files=("src/validators.py",),
            golden_lines=(3, 7),
        ),
        SWEBenchTask(
            instance_id="task-2",
            repository_name="test",
            problem_statement="Validate username characters",
            target_symbol="ASCIIUsernameValidator.validate",
            golden_files=("src/validators.py",),
            golden_lines=(5, 6),
        ),
    ]

    report = run_swe_bench_suite(swe_bench_sample_repo, tasks)
    assert report.total_tasks == 2
    assert len(report.comparisons) == 2
    assert report.avg_token_reduction_pct > 0.0
    assert report.codegraph_localization_accuracy == 100.0
    assert "avg_token_reduction_pct" in report.as_dict()
