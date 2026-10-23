"""Native Pull Request Review & Semantic Blast-Radius Auditor for CodeGraph.

Performs deep structural AST diffs, caller contract verification, affected HTTP route
detection, database schema impact analysis, and test coverage gap identification to generate
an actionable, high-density PR review report for CI/CD pipelines (GitHub Actions, GitLab CI).
"""
from __future__ import annotations

import sqlite3
from dataclasses import dataclass, field
from enum import StrEnum
from pathlib import Path
from typing import Any

from codegraph.change_impact import get_deep_change_impact
from codegraph.semantic_conflicts import detect_semantic_conflicts
from codegraph.structural_diff import compare_branches


class ReviewSeverity(StrEnum):
    CRITICAL = "CRITICAL"
    HIGH = "HIGH"
    MEDIUM = "MEDIUM"
    LOW = "LOW"
    INFO = "INFO"


@dataclass
class ReviewFinding:
    severity: ReviewSeverity
    category: str
    title: str
    description: str
    file_path: str
    line: int | None = None
    recommendation: str = ""

    def as_dict(self) -> dict[str, Any]:
        return {
            "severity": self.severity.value,
            "category": self.category,
            "title": self.title,
            "description": self.description,
            "file_path": self.file_path,
            "line": self.line,
            "recommendation": self.recommendation,
        }


@dataclass
class PRReviewReport:
    base_ref: str
    head_ref: str
    verdict: str  # APPROVE, COMMENT, REQUEST_CHANGES
    summary: str
    findings: list[ReviewFinding] = field(default_factory=list)
    files_changed: list[str] = field(default_factory=list)
    symbols_added: int = 0
    symbols_modified: int = 0
    symbols_removed: int = 0
    affected_routes: list[dict[str, Any]] = field(default_factory=list)
    affected_tests: list[str] = field(default_factory=list)
    suggested_test_command: str = ""
    markdown_report: str = ""

    def as_dict(self) -> dict[str, Any]:
        return {
            "base_ref": self.base_ref,
            "head_ref": self.head_ref,
            "verdict": self.verdict,
            "summary": self.summary,
            "findings": [f.as_dict() for f in self.findings],
            "files_changed": self.files_changed,
            "symbols_added": self.symbols_added,
            "symbols_modified": self.symbols_modified,
            "symbols_removed": self.symbols_removed,
            "affected_routes": self.affected_routes,
            "affected_tests": self.affected_tests,
            "suggested_test_command": self.suggested_test_command,
            "markdown_report": self.markdown_report,
        }


def generate_pr_review(
    repository: Path,
    base_ref: str = "main",
    head_ref: str = "HEAD",
    con: sqlite3.Connection | None = None,
) -> PRReviewReport:
    """Generate a comprehensive semantic PR review evaluating structural diffs, contract breaks, and tests."""
    repo = repository.resolve()

    # 1. Structural AST Diff
    diff_report = compare_branches(repo, base_branch=base_ref, head_branch=head_ref, con=con)

    # 2. Semantic Conflict & Contract Break Analysis
    conflicts_report = detect_semantic_conflicts(repo, base_branch=base_ref, head_branch=head_ref, con=con)

    # 3. Deep Change Impact Analysis
    files_changed = sorted(
        set(diff_report.added_files + diff_report.modified_files + diff_report.deleted_files)
    )
    impact_report = None
    if files_changed and con is not None:
        try:
            impact_report = get_deep_change_impact(repo, con, base=base_ref, head=head_ref)
        except Exception:
            impact_report = None

    # 4. Synthesize Findings
    findings: list[ReviewFinding] = []

    # Map semantic contract breaks
    for conf in conflicts_report.conflicts:
        sev = ReviewSeverity.CRITICAL if conf.severity == "CRITICAL" else ReviewSeverity.HIGH
        findings.append(
            ReviewFinding(
                severity=sev,
                category="CONTRACT_BREAK",
                title=f"Semantic Contract Break: {conf.symbol}",
                description=conf.description,
                file_path=conf.head_file or conf.base_file,
                line=conf.line,
                recommendation="Update consuming call sites or maintain backward-compatible argument signatures.",
            )
        )

    # Map removed symbols without replacement
    for sym in diff_report.removed_symbols:
        findings.append(
            ReviewFinding(
                severity=ReviewSeverity.HIGH,
                category="DELETED_SYMBOL",
                title=f"Deleted Symbol: {sym.name}",
                description=f"{sym.kind} '{sym.name}' was removed from {sym.path}.",
                file_path=sym.path,
                line=sym.new_line or sym.old_line,
                recommendation="Verify that no external packages or unindexed scripts rely on this symbol.",
            )
        )

    # Map modified routes & missing test coverage
    affected_routes_list: list[dict[str, Any]] = []
    for r in diff_report.changed_routes:
        affected_routes_list.append(r.as_dict())

    if impact_report:
        for r_item in impact_report.affected_routes:
            r_dict = r_item.as_dict()
            if r_dict not in affected_routes_list:
                affected_routes_list.append(r_dict)

    # Test coverage gap analysis: Check if modified routes have tests
    covered_test_paths = set(diff_report.affected_tests)
    if impact_report:
        covered_test_paths.update(t.file for t in impact_report.affected_tests)

    if affected_routes_list and not covered_test_paths:
        findings.append(
            ReviewFinding(
                severity=ReviewSeverity.HIGH,
                category="TEST_GAP",
                title="Uncovered Route Modifications",
                description=f"{len(affected_routes_list)} HTTP route(s) were added or modified without any associated test coverage.",
                file_path=str(affected_routes_list[0].get("file_path") or "routes"),
                recommendation="Add integration tests exercising the modified HTTP endpoints.",
            )
        )

    # Verdict calculation
    has_critical = any(f.severity == ReviewSeverity.CRITICAL for f in findings)
    has_high = any(f.severity == ReviewSeverity.HIGH for f in findings)

    if has_critical:
        verdict = "REQUEST_CHANGES"
        summary = f"Blocked: {len([f for f in findings if f.severity == ReviewSeverity.CRITICAL])} critical contract break(s) detected."
    elif has_high:
        verdict = "COMMENT"
        summary = f"Caution: {len([f for f in findings if f.severity == ReviewSeverity.HIGH])} high-priority finding(s) require verification."
    else:
        verdict = "APPROVE"
        summary = "Clean: No semantic contract breaks or uncovered route regressions detected."

    # Build suggested test command
    suggested_test_cmd = ""
    if impact_report and impact_report.recommended_test_command:
        suggested_test_cmd = impact_report.recommended_test_command
    elif covered_test_paths:
        suggested_test_cmd = f"pytest {' '.join(sorted(covered_test_paths)[:10])}"

    # Build High-Density GitHub PR Markdown
    markdown = _format_pr_markdown(
        base_ref=base_ref,
        head_ref=head_ref,
        verdict=verdict,
        summary=summary,
        findings=findings,
        files_changed=files_changed,
        symbols_added=len(diff_report.added_symbols),
        symbols_modified=len(diff_report.changed_symbols),
        symbols_removed=len(diff_report.removed_symbols),
        affected_routes=affected_routes_list,
        affected_tests=sorted(covered_test_paths),
        suggested_test_command=suggested_test_cmd,
    )

    return PRReviewReport(
        base_ref=base_ref,
        head_ref=head_ref,
        verdict=verdict,
        summary=summary,
        findings=findings,
        files_changed=files_changed,
        symbols_added=len(diff_report.added_symbols),
        symbols_modified=len(diff_report.changed_symbols),
        symbols_removed=len(diff_report.removed_symbols),
        affected_routes=affected_routes_list,
        affected_tests=sorted(covered_test_paths),
        suggested_test_command=suggested_test_cmd,
        markdown_report=markdown,
    )


def _format_pr_markdown(
    base_ref: str,
    head_ref: str,
    verdict: str,
    summary: str,
    findings: list[ReviewFinding],
    files_changed: list[str],
    symbols_added: int,
    symbols_modified: int,
    symbols_removed: int,
    affected_routes: list[dict[str, Any]],
    affected_tests: list[str],
    suggested_test_command: str,
) -> str:
    """Format markdown for GitHub PR review comment."""
    verdict_badge = {
        "APPROVE": "🟢 **APPROVED**",
        "COMMENT": "🟡 **CAUTION / COMMENT**",
        "REQUEST_CHANGES": "🔴 **CHANGES REQUESTED**",
    }.get(verdict, verdict)

    lines: list[str] = [
        "## 🔍 CodeGraph Semantic PR Review",
        "",
        f"**Verdict**: {verdict_badge} &mdash; {summary}",
        f"**Revisions**: `{base_ref}` &rarr; `{head_ref}`",
        "",
        "### 📊 Blast-Radius & AST Metrics",
        "",
        "| Files Changed | Symbols Added | Symbols Modified | Symbols Removed | Affected Routes | Covered Tests |",
        "| :---: | :---: | :---: | :---: | :---: | :---: |",
        f"| {len(files_changed)} | {symbols_added} | {symbols_modified} | {symbols_removed} | {len(affected_routes)} | {len(affected_tests)} |",
        "",
    ]

    if findings:
        lines.append("### ⚠️ Key Findings")
        lines.append("")
        for f in findings:
            badge = "🔴" if f.severity == ReviewSeverity.CRITICAL else ("🟠" if f.severity == ReviewSeverity.HIGH else "🔵")
            loc = f"`{f.file_path}:{f.line}`" if f.line else f"`{f.file_path}`"
            lines.append(f"- {badge} **[{f.severity.value}] {f.title}** ({loc})")
            lines.append(f"  {f.description}")
            if f.recommendation:
                lines.append(f"  *Recommendation*: {f.recommendation}")
            lines.append("")

    if affected_routes:
        lines.append("<details><summary><b>🌐 Affected HTTP Routes (" + str(len(affected_routes)) + ")</b></summary>")
        lines.append("")
        lines.append("| Method | Path | Handler | File |")
        lines.append("| :--- | :--- | :--- | :--- |")
        for r in affected_routes[:20]:
            m = r.get("method") or r.get("http_method") or "ANY"
            p = r.get("path") or r.get("route_path") or "-"
            h = r.get("handler") or r.get("handler_name") or "-"
            f_path = r.get("file_path") or "-"
            lines.append(f"| `{m}` | `{p}` | `{h}` | `{f_path}` |")
        lines.append("")
        lines.append("</details>")
        lines.append("")

    if suggested_test_command:
        lines.append("### 🧪 Recommended Targeted Test Suite")
        lines.append("```bash")
        lines.append(suggested_test_command)
        lines.append("```")
        lines.append("")

    lines.append("---")
    lines.append("*Generated by [CodeGraph MCP](https://github.com/raghurammrsd/CODE_GRAPH_MCP) &bull; Deterministic Repository Intelligence*")

    return "\n".join(lines)
