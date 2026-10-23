"""CLI runner for SWE-bench Comparative Evaluation."""
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

from codegraph.indexing.indexer import Indexer

from .harness import run_swe_bench_suite
from .models import SWEBenchTask


def get_sample_swe_bench_tasks() -> list[SWEBenchTask]:
    """Sample realistic bug-resolution tasks modeled after SWE-bench Lite."""
    return [
        SWEBenchTask(
            instance_id="django__django-11099",
            repository_name="django",
            problem_statement="UsernameValidator allows trailing newline in ASCII usernames",
            target_symbol="ASCIIUsernameValidator",
            golden_files=("django/contrib/auth/validators.py",),
            golden_lines=(17, 24),
            hints="Regex pattern should match with \\A and \\Z instead of ^ and $",
        ),
        SWEBenchTask(
            instance_id="psf__requests-2148",
            repository_name="requests",
            problem_statement="socket.error exception not caught in response iter_content",
            target_symbol="Response.iter_content",
            golden_files=("requests/models.py",),
            golden_lines=(680, 720),
            hints="socket.error should be wrapped in StreamConsumedError or ConnectionError",
        ),
        SWEBenchTask(
            instance_id="pallets__flask-4045",
            repository_name="flask",
            problem_statement="Blueprint with dots in name raises ValueError when mounting",
            target_symbol="Blueprint.__init__",
            golden_files=("src/flask/blueprints.py",),
            golden_lines=(160, 190),
            hints="Blueprint names containing dots cause collision in nested routing trees",
        ),
    ]


def main() -> int:
    parser = argparse.ArgumentParser(description="Run SWE-bench Comparative Benchmark Harness")
    parser.add_argument("--repo", "-r", type=Path, default=Path("."), help="Target repository path")
    parser.add_argument("--output", "-o", type=Path, default=None, help="Output JSON report path")
    args = parser.parse_args()

    repo = args.repo.resolve()
    indexer = Indexer(repo)
    if not indexer.db_path.exists():
        indexer.index()

    tasks = get_sample_swe_bench_tasks()
    print(f"Running SWE-bench Evaluation on {repo.name} ({len(tasks)} tasks)...")

    report = run_swe_bench_suite(repo, tasks)

    print("\n" + "=" * 60)
    print("SWE-bench Comparative Benchmark Report:")
    print("=" * 60)
    print(f"Tasks Evaluated:             {report.total_tasks}")
    print(f"Average Token Reduction:     {report.avg_token_reduction_pct:.1f}%")
    print(f"Average Turn Count Drop:     {report.avg_turns_reduction_pct:.1f}%")
    print(f"CodeGraph Localization Acc:  {report.codegraph_localization_accuracy:.1f}%")
    print(f"Baseline Localization Acc:   {report.baseline_localization_accuracy:.1f}%")
    print(f"Estimated Cost Savings:      ${report.total_cost_savings_usd:.4f}")
    print("=" * 60 + "\n")

    for c in report.comparisons:
        print(f"Task: {c.instance_id}")
        print(f"  Baseline:  {c.baseline.tokens_consumed} tokens, {c.baseline.turns_count} turns ({c.baseline.duration_ms:.1f}ms)")
        print(f"  CodeGraph: {c.codegraph.tokens_consumed} tokens, {c.codegraph.turns_count} turns ({c.codegraph.duration_ms:.1f}ms)")
        print(f"  Savings:   {c.token_reduction_pct:.1f}% tokens, {c.turns_reduction_pct:.1f}% turns\n")

    if args.output:
        args.output.parent.mkdir(parents=True, exist_ok=True)
        args.output.write_text(json.dumps(report.as_dict(), indent=2), encoding="utf-8")
        print(f"Wrote report to {args.output}")

    return 0


if __name__ == "__main__":
    sys.exit(main())
