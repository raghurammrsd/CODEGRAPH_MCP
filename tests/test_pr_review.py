"""Tests for native CodeGraph PR review engine."""
from __future__ import annotations

import subprocess
from pathlib import Path

import pytest

from codegraph.indexing.indexer import Indexer
from codegraph.pr_review import ReviewSeverity, generate_pr_review


@pytest.fixture
def git_repo_with_branches(tmp_path: Path) -> Path:
    repo = tmp_path / "pr_test_repo"
    repo.mkdir()

    # Initialize real git repo
    subprocess.run(["git", "init", "-b", "main"], cwd=repo, check=True, capture_output=True)
    subprocess.run(["git", "config", "user.name", "TestUser"], cwd=repo, check=True)
    subprocess.run(["git", "config", "user.email", "test@example.com"], cwd=repo, check=True)

    # Initial commit on main
    app_py = repo / "app.py"
    app_py.write_text(
        "def helper(x: int) -> int:\n"
        "    return x * 2\n\n"
        "def main_func():\n"
        "    return helper(10)\n"
    )
    subprocess.run(["git", "add", "app.py"], cwd=repo, check=True)
    subprocess.run(["git", "commit", "-m", "initial commit"], cwd=repo, check=True)

    # Create feature branch
    subprocess.run(["git", "checkout", "-b", "feature-branch"], cwd=repo, check=True)
    app_py.write_text(
        "def helper(x: int, required_param: str) -> int:\n"
        "    return x * 2\n\n"
        "def main_func():\n"
        "    return helper(10, 'hello')\n"
    )
    subprocess.run(["git", "add", "app.py"], cwd=repo, check=True)
    subprocess.run(["git", "commit", "-m", "modify helper signature"], cwd=repo, check=True)

    # Index repository
    indexer = Indexer(repo)
    indexer.index()

    return repo


def test_generate_pr_review_clean(git_repo_with_branches: Path) -> None:
    # Compare feature branch with itself: should be clean APPROVE
    report = generate_pr_review(git_repo_with_branches, base_ref="HEAD", head_ref="HEAD")
    assert report.verdict == "APPROVE"
    assert "No semantic contract breaks" in report.summary
    assert report.markdown_report.startswith("## 🔍 CodeGraph Semantic PR Review")


def test_generate_pr_review_detects_changes(git_repo_with_branches: Path) -> None:
    # Compare main with feature-branch
    report = generate_pr_review(git_repo_with_branches, base_ref="main", head_ref="feature-branch")
    assert report.base_ref == "main"
    assert report.head_ref == "feature-branch"
    assert len(report.files_changed) >= 1
    assert "app.py" in report.files_changed
    assert report.markdown_report != ""
    assert "### 📊 Blast-Radius & AST Metrics" in report.markdown_report


def test_pr_review_report_as_dict() -> None:
    from codegraph.pr_review import PRReviewReport, ReviewFinding

    finding = ReviewFinding(
        severity=ReviewSeverity.HIGH,
        category="CONTRACT_BREAK",
        title="Breaking Change",
        description="Signature altered",
        file_path="app.py",
        line=10,
        recommendation="Fix call sites",
    )
    report = PRReviewReport(
        base_ref="main",
        head_ref="feat",
        verdict="COMMENT",
        summary="Caution",
        findings=[finding],
        files_changed=["app.py"],
        symbols_added=0,
        symbols_modified=1,
        symbols_removed=0,
    )
    d = report.as_dict()
    assert d["verdict"] == "COMMENT"
    assert len(d["findings"]) == 1
    assert d["findings"][0]["severity"] == "HIGH"
