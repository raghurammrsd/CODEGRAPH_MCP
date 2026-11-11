"""Tests for v3.0.2 optimizations and enhancements:
1. Large-repo index performance and stat cache (mtime_ns, size) fast-path.
2. Clear error for shallow Git history (SHALLOW_CLONE_INSUFFICIENT_HISTORY).
3. Transparent OpenTelemetry setup (codegraph otel env and runtime injection).
4. "Why this context was selected" structured rationale report.
5. GitHub/GitLab PR review intelligence (codegraph review).
"""
from __future__ import annotations

import json
import subprocess
from pathlib import Path

from typer.testing import CliRunner

from codegraph.cli import app
from codegraph.context import get_context
from codegraph.git import analyze_change_impact, is_shallow_repository, verify_git_ref
from codegraph.indexing import Indexer
from codegraph.interrogation import get_git_impact

runner = CliRunner()


def test_stat_cache_fast_path_avoids_reparsing_unchanged_files(tmp_path: Path) -> None:
    """Unchanged files hit OS stat cache (mtime_ns, size) avoiding file reading and sha256 hashing."""
    repo = tmp_path / "repo"
    repo.mkdir()
    f1 = repo / "alpha.py"
    f1.write_text("def alpha():\n    return 42\n", encoding="utf-8")
    f2 = repo / "beta.py"
    f2.write_text("def beta():\n    return 100\n", encoding="utf-8")

    idx = Indexer(repo)
    # First indexing pass: indexes both files and populates stat cache
    res1 = idx.index()
    assert res1.get("indexed", 0) == 2
    assert res1.get("unchanged", 0) == 0

    # Verify mtime_ns and size are stored in files table
    with idx.session() as con:
        rows = con.execute("SELECT path, mtime_ns, size FROM files").fetchall()
        assert len(rows) == 2
        for r in rows:
            assert int(r["mtime_ns"]) > 0
            assert int(r["size"]) > 0

    # Second indexing pass: both files match stat cache exactly -> 0 indexed, 2 unchanged
    res2 = idx.index()
    assert res2.get("indexed", 0) == 0
    assert res2.get("unchanged", 0) == 2

    # Modify only f1
    f1.write_text("def alpha():\n    return 99\n", encoding="utf-8")
    res3 = idx.index()
    assert res3.get("indexed", 0) == 1
    assert res3.get("unchanged", 0) == 1


def test_shallow_clone_error_reporting(tmp_path: Path) -> None:
    """Shallow repository comparisons return structured SHALLOW_CLONE_INSUFFICIENT_HISTORY error."""
    repo = tmp_path / "shallow_repo"
    repo.mkdir()

    def run_git(*args: str) -> None:
        subprocess.run(["git", *args], cwd=str(repo), check=True, capture_output=True, text=True)

    run_git("init", "-b", "main")
    run_git("config", "user.email", "test@codegraph.dev")
    run_git("config", "user.name", "Tester")

    (repo / "file1.py").write_text("def run(): pass\n")
    run_git("add", ".")
    run_git("commit", "-m", "First commit")

    # Mark the repository as shallow by writing shallow file in .git
    git_dir = repo / ".git"
    head_sha = subprocess.run(["git", "rev-parse", "HEAD"], cwd=str(repo), capture_output=True, text=True).stdout.strip()
    (git_dir / "shallow").write_text(f"{head_sha}\n")

    assert is_shallow_repository(repo) is True
    ok, err_code = verify_git_ref(repo, "HEAD~10")
    assert ok is False
    assert err_code == "SHALLOW_CLONE_INSUFFICIENT_HISTORY"

    idx = Indexer(repo)
    idx.index()

    with idx.session() as con:
        res = analyze_change_impact(con, repo, since="HEAD~1", until="HEAD")
        assert res.get("error") == "SHALLOW_CLONE_INSUFFICIENT_HISTORY"
        assert "shallow clone" in str(res.get("message", "")).lower()
        assert "git fetch --unshallow" in str(res.get("resolution", ""))
        assert res.get("is_shallow") is True

        # Interrogation get_git_impact also reports the structured error
        impact = get_git_impact(con, repo, base="HEAD~1", head="HEAD")
        assert impact.get("error") == "SHALLOW_CLONE_INSUFFICIENT_HISTORY"
        assert impact.get("is_shallow") is True


def test_otel_env_cli_command() -> None:
    """`codegraph otel env` emits standard OpenTelemetry environment variables for multiple shells."""
    # Default bash/zsh
    res_bash = runner.invoke(app, ["otel", "env"])
    assert res_bash.exit_code == 0
    assert 'export OTEL_EXPORTER_OTLP_ENDPOINT="http://127.0.0.1:4318/v1/traces"' in res_bash.stdout
    assert 'export OTEL_TRACES_EXPORTER="otlp"' in res_bash.stdout
    assert 'export OTEL_EXPORTER_OTLP_PROTOCOL="http/json"' in res_bash.stdout
    assert 'export CODEGRAPH_RUNTIME_RECORD="1"' in res_bash.stdout

    # PowerShell
    res_ps = runner.invoke(app, ["otel", "env", "--shell", "powershell"])
    assert res_ps.exit_code == 0
    assert '$env:OTEL_EXPORTER_OTLP_ENDPOINT="http://127.0.0.1:4318/v1/traces"' in res_ps.stdout

    # Fish
    res_fish = runner.invoke(app, ["otel", "env", "--shell", "fish"])
    assert res_fish.exit_code == 0
    assert "set -gx OTEL_EXPORTER_OTLP_ENDPOINT http://127.0.0.1:4318/v1/traces" in res_fish.stdout


def test_why_this_context_was_selected_report(tmp_path: Path) -> None:
    """ContextPacket includes structured selection_rationale and human-readable why-selected section."""
    repo = tmp_path / "context_repo"
    repo.mkdir()
    (repo / "service.py").write_text(
        "class UserService:\n"
        "    def create_user(self, name: str) -> bool:\n"
        "        return True\n",
        encoding="utf-8",
    )
    (repo / "handler.py").write_text(
        "from service import UserService\n"
        "def user_handler():\n"
        "    s = UserService()\n"
        "    return s.create_user('alice')\n",
        encoding="utf-8",
    )

    idx = Indexer(repo)
    idx.index()

    with idx.session() as con:
        packet = get_context(con, repo, task="how does create_user work?", intent="explain")
        assert packet.selection_rationale
        assert packet.selection_rationale.get("intent") == "EXPLAIN"
        assert "relevance_signals" in packet.selection_rationale
        assert "expansion_hops" in packet.selection_rationale
        assert "summary" in packet.selection_rationale

        human = packet.format_human()
        assert "## Why This Context Was Selected" in human
        assert "- **Relevance**:" in human
        assert "- **Token Budget**:" in human


def test_codegraph_review_cli_command(tmp_path: Path) -> None:
    """`codegraph review` computes blast radius and formats GitHub/GitLab markdown."""
    repo = tmp_path / "git_review_repo"
    repo.mkdir()

    def run_git(*args: str) -> None:
        subprocess.run(["git", *args], cwd=str(repo), check=True, capture_output=True, text=True)

    run_git("init", "-b", "main")
    run_git("config", "user.email", "test@codegraph.dev")
    run_git("config", "user.name", "Tester")

    f = repo / "calc.py"
    f.write_text("def add(a: int, b: int) -> int:\n    return a + b\n")
    run_git("add", ".")
    run_git("commit", "-m", "Initial commit")

    # Modify calc.py in commit 2
    f.write_text("def add(a: int, b: int) -> int:\n    return (a + b) * 1\n\ndef sub(a: int, b: int) -> int:\n    return a - b\n")
    run_git("add", ".")
    run_git("commit", "-m", "Add subtraction")

    Indexer(repo).index()

    # Run review command
    res = runner.invoke(app, ["review", "--base", "HEAD~1", "--head", "HEAD", "--repo", str(repo)])
    assert res.exit_code == 0
    assert "CodeGraph Pull Request Intelligence & Blast Radius Report" in res.stdout
    assert "| **Blast Radius Score** |" in res.stdout
    assert "| **Changed Files** | `1` |" in res.stdout

    # Run review command in JSON mode
    res_json = runner.invoke(app, ["review", "--base", "HEAD~1", "--head", "HEAD", "--repo", str(repo), "--json"])
    assert res_json.exit_code == 0
    data = json.loads(res_json.stdout)
    assert data["changed_files_count"] == 1
    assert "blast_radius_score" in data
