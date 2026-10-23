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
    """Sample realistic bug-resolution tasks modeled after SWE-bench Lite across multiple languages."""
    return [
        SWEBenchTask(
            instance_id="django__django-11099",
            repository_name="django",
            problem_statement="UsernameValidator allows trailing newline in ASCII usernames",
            target_symbol="ASCIIUsernameValidator",
            golden_files=("django/contrib/auth/validators.py",),
            golden_lines=(17, 24),
            language="python",
            hints="Regex pattern should match with \\A and \\Z instead of ^ and $",
        ),
        SWEBenchTask(
            instance_id="psf__requests-2148",
            repository_name="requests",
            problem_statement="socket.error exception not caught in response iter_content",
            target_symbol="Response.iter_content",
            golden_files=("requests/models.py",),
            golden_lines=(680, 720),
            language="python",
            hints="socket.error should be wrapped in StreamConsumedError or ConnectionError",
        ),
        SWEBenchTask(
            instance_id="gin-gonic__gin-2840",
            repository_name="gin",
            problem_statement="Engine router group mount does not compose prefix correctly with trailing slash",
            target_symbol="RouterGroup.Group",
            golden_files=("routergroup.go",),
            golden_lines=(70, 95),
            language="go",
            hints="Clean path join logic before mounting sub-router",
        ),
        SWEBenchTask(
            instance_id="tokio-rs__axum-1492",
            repository_name="axum",
            problem_statement="Nested router path extraction fails on wildcard patterns",
            target_symbol="Router::nest",
            golden_files=("src/routing/mod.rs",),
            golden_lines=(120, 150),
            language="rust",
            hints="Strip wildcard prefix before delegating to inner match tree",
        ),
        SWEBenchTask(
            instance_id="spring-projects__spring-boot-3102",
            repository_name="spring-boot",
            problem_statement="RequestMapping handler fails URI variable resolution with nested path brackets",
            target_symbol="RequestMappingHandlerMapping",
            golden_files=("src/main/java/org/springframework/boot/web/servlet/FilterRegistrationBean.java",),
            golden_lines=(45, 80),
            language="java",
            hints="Escape URI template curly braces in path matcher",
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
