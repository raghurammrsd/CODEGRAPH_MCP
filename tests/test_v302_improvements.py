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


def test_delta_relationship_resolution_on_small_change(tmp_path: Path) -> None:
    """Incremental indexing recalculates only affected callers and dirty resolvers, preserving untouched edges."""
    repo = tmp_path / "delta_repo"
    repo.mkdir()

    p1 = repo / "producer.py"
    p1.write_text("def compute(x: int) -> int:\n    return x * 2\n", encoding="utf-8")

    c1 = repo / "consumer.py"
    c1.write_text("from producer import compute\ndef process():\n    return compute(10)\n", encoding="utf-8")

    u1 = repo / "unrelated.py"
    u1.write_text("def unrelated():\n    return 42\n", encoding="utf-8")

    idx = Indexer(repo)
    idx.index()

    with idx.session() as con:
        # Check initial edges
        edges_init = con.execute("SELECT source, target, relationship, file FROM graph_edges").fetchall()
        assert any(r["source"] == "unrelated.py" for r in edges_init)
        assert any(r["target"] == "producer.compute" for r in edges_init)

    # Modify ONLY producer.py
    p1.write_text("def compute(x: int) -> int:\n    return (x * 2) + 1\n", encoding="utf-8")
    res = idx.index()
    assert res.get("indexed", 0) == 1
    assert res.get("unchanged", 0) == 2

    with idx.session() as con:
        # Untouched file edges (unrelated.py) remain intact in graph_edges
        edges_after = con.execute("SELECT source, target, relationship, file FROM graph_edges").fetchall()
        assert any(r["source"] == "unrelated.py" for r in edges_after)
        # Relationship from consumer.py to producer.compute remains resolved
        assert any(r["target"] == "producer.compute" and r["file"] == "consumer.py" for r in edges_after)


def test_compact_wire_serialization_and_token_cap(tmp_path: Path) -> None:
    """ContextPacket to_wire_dict enforces compact representation and final payload token capping."""
    repo = tmp_path / "wire_repo"
    repo.mkdir()
    (repo / "app.py").write_text(
        "def entry():\n    return 1\n",
        encoding="utf-8",
    )
    idx = Indexer(repo)
    idx.index()

    with idx.session() as con:
        packet = get_context(con, repo, "how does entry work?")

        # Default compact wire payload
        wire = packet.to_wire_dict(compact=True, explain=False, max_tokens=1000)
        assert wire["schema_version"]
        assert wire["task"] == "how does entry work?"
        assert wire["symbols"]
        assert "rejections" not in wire.get("budget", {})  # Rejection bloat removed
        assert "covered_dimensions" not in wire.get("budget", {})
        assert "execution" not in wire  # Timing telemetry removed
        assert "architecture" not in wire  # Architecture dump removed

        # Canonical token count must be <= 1000
        serialized = json.dumps(wire, separators=(",", ":"))
        est_tokens = len(serialized) // 4
        assert est_tokens <= 1000

        # When explain=True, full diagnostics are preserved
        full = packet.to_wire_dict(compact=True, explain=True)
        assert "budget" in full
        assert "execution" in full

        # Default as_dict() maintains compatibility with existing tests
        legacy = packet.as_dict()
        assert "schema_version" in legacy
        assert "candidate_token_estimate" in legacy


def test_factory_nested_callees_are_strictly_scoped(tmp_path: Path) -> None:
    """Outer factory functions do not swallow call sites from nested inner functions."""
    from codegraph.graph.traversal import find_callees
    from codegraph.interrogation import get_callees

    repo = tmp_path / "factory_repo"
    repo.mkdir()
    (repo / "factory.py").write_text(
        "def helper_outer():\n"
        "    return 'outer'\n\n"
        "def helper_inner():\n"
        "    return 'inner'\n\n"
        "def make_engine():\n"
        "    helper_outer()\n"
        "    def run_worker():\n"
        "        helper_inner()\n"
        "        helper_inner()\n"
        "    return run_worker\n",
        encoding="utf-8",
    )
    idx = Indexer(repo)
    idx.index()

    with idx.session() as con:
        # Check callees of outer factory: only helper_outer must be called directly
        outer_res = get_callees(con, repo, symbol="make_engine")
        outer_callees = [c["callee"] for c in outer_res.get("callees", [])]
        assert "helper_outer" in outer_callees
        assert "helper_inner" not in outer_callees

        # Check callees via find_callees
        trav_callees = find_callees(con, "make_engine")
        trav_names = [c.callee for c in trav_callees]
        assert "helper_outer" in trav_names
        assert "helper_inner" not in trav_names

        # Check nested inner function: owns its own calls
        inner_res = get_callees(con, repo, symbol="run_worker")
        inner_callees = [c["callee"] for c in inner_res.get("callees", [])]
        assert "helper_inner" in inner_callees
        assert "helper_outer" not in inner_callees


def test_giant_symbol_guard_and_uncertainty_propagation(tmp_path: Path) -> None:
    """Giant container functions with >10 child symbols trigger giant-symbol guard and summarize child tools."""
    repo = tmp_path / "giant_repo"
    repo.mkdir()

    # Generate a factory defining 12 child functions
    tool_defs = "\n".join(
        f"    def tool_{i}():\n        return {i}\n"
        for i in range(12)
    )
    (repo / "server.py").write_text(
        "def init_config():\n    return {}\n\n"
        "def create_app():\n"
        "    init_config()\n"
        f"{tool_defs}"
        "    return True\n",
        encoding="utf-8",
    )

    idx = Indexer(repo)
    idx.index()

    with idx.session() as con:
        pkt = get_context(con, repo, "how does create_app work?")
        wire = pkt.to_wire_dict(compact=True, explain=False, max_tokens=1000)

        # Giant-Symbol Guard activated
        assert "factory defining 12 nested tools" in wire.get("summary", "")
        assert "child_tools" in wire
        assert len(wire["child_tools"]) >= 10
        assert "tool_0" in wire["child_tools"]

        # create_app ranks #1 production symbol, not overwhelmed by 12 child tools
        assert "create_app" in wire["symbols"][0]["symbol"]

        # Epistemic uncertainties are present if stale or unverified
        assert isinstance(wire.get("uncertainties", []), list)


def test_production_first_ranking_policy(tmp_path: Path) -> None:
    """Non-test queries rank production code before test fixtures and discount test files."""
    repo = tmp_path / "prod_test_repo"
    repo.mkdir()
    (repo / "user_service.py").write_text(
        "def create_user(name: str):\n    return {'name': name}\n",
        encoding="utf-8",
    )
    tests_dir = repo / "tests"
    tests_dir.mkdir()
    (tests_dir / "test_user.py").write_text(
        "from user_service import create_user\n"
        "def test_create_user():\n"
        "    u = create_user('alice')\n"
        "    assert u['name'] == 'alice'\n",
        encoding="utf-8",
    )

    idx = Indexer(repo)
    idx.index()

    with idx.session() as con:
        pkt = get_context(con, repo, "create_user")
        wire = pkt.to_wire_dict(compact=True, explain=False, max_tokens=1000)

        # Production symbol is #1
        top_sym = wire["symbols"][0]
        assert top_sym["symbol"] == "create_user"
        assert "user_service.py" in top_sym["location"]

        # Tests appear under statically_linked_tests, not crowding out production symbols
        if "statically_linked_tests" in wire:
            test_files = [t[1] for t in wire["statically_linked_tests"]]
            assert any("test_user.py" in tf for tf in test_files)


def test_strict_wire_budget_and_file_ordering(tmp_path: Path) -> None:
    """Strict wire token budget <= 1000 tokens and production files precede test files."""
    repo = tmp_path / "strict_wire_repo"
    repo.mkdir()
    (repo / "core_service.py").write_text(
        "def execute_task():\n    return 'done'\n",
        encoding="utf-8",
    )
    tests_dir = repo / "tests"
    tests_dir.mkdir()
    (tests_dir / "test_core.py").write_text(
        "from core_service import execute_task\n"
        "def test_execute():\n"
        "    assert execute_task() == 'done'\n",
        encoding="utf-8",
    )

    idx = Indexer(repo)
    idx.index()

    with idx.session() as con:
        pkt = get_context(con, repo, "execute_task", max_tokens=1000)
        wire = pkt.to_wire_dict(compact=True, explain=False, max_tokens=1000)

        # Wire token cap strictly enforced
        raw_json = json.dumps(wire, ensure_ascii=False, separators=(",", ":"))
        try:
            import tiktoken
            enc = tiktoken.get_encoding("o200k_base")
            tok_count = len(enc.encode(raw_json))
        except Exception:
            tok_count = (len(raw_json) + 3) // 4
        assert tok_count <= 1000

        # Wire structure keys
        assert "target" in wire
        assert isinstance(wire.get("uncertainties"), list)

        # Production files precede test files in wire['files']
        if "files" in wire and len(wire["files"]) > 1:
            file_names = [f["file"] for f in wire["files"]]
            prod_indices = [i for i, fn in enumerate(file_names) if "tests" not in fn and "test_" not in fn]
            test_indices = [i for i, fn in enumerate(file_names) if "tests" in fn or "test_" in fn]
            if prod_indices and test_indices:
                assert max(prod_indices) < min(test_indices)


def test_trace_call_scoped_callees_no_child_expansion(tmp_path: Path) -> None:
    """trace_call on a factory function does not expand callees of its nested child functions."""
    from codegraph.graph.traversal import trace_call

    repo = tmp_path / "scoped_callee_repo"
    repo.mkdir()
    (repo / "factory.py").write_text(
        "def outer_setup():\n    pass\n\n"
        "def nested_callee():\n    pass\n\n"
        "def build_factory():\n"
        "    outer_setup()\n"
        "    def nested_worker():\n"
        "        nested_callee()\n"
        "    return nested_worker\n",
        encoding="utf-8",
    )

    idx = Indexer(repo)
    idx.index()

    with idx.session() as con:
        res = trace_call(con, "build_factory", max_depth=1, callers=False, callees=True)
        callee_edges = [x for x in res if x.get("relationship") in ("CALLS", "CALLEE")]
        callee_names = [str(x.get("callee") or x.get("target_symbol") or x.get("symbol")) for x in callee_edges]
        assert any("outer_setup" in c for c in callee_names)
        assert not any("nested_callee" in c for c in callee_names)


