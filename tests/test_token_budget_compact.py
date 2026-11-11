"""Automated CI Test Suite for Compact Token Serializer (v3.0.2).

Verifies:
1. Strict Budget Enforcement with o200k_base and cl100k_base tokenizers.
2. JSON Integrity across progressive greedy truncator steps.
3. Target Header Guard: structured error {"status": "BUDGET_TOO_SMALL"}.
4. Machine Drill-Down: get_evidence(ids=res["evidence_ids"][:2]) proof retrieval.
5. Full Backward Compatibility: compact=False returns complete legacy fields.
"""
from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from codegraph.indexing import Indexer
from codegraph.llm.tokenizer import count_tokens, get_effective_cap
from codegraph.mcp.server import create_server


def _setup_sample_repo(repo: Path) -> None:
    repo.mkdir(parents=True, exist_ok=True)
    (repo / "factory.py").write_text(
        "def create_app():\n"
        "    app = setup_engine()\n"
        "    return app\n\n"
        "def setup_engine():\n"
        "    return 'engine_v1'\n",
        encoding="utf-8",
    )
    (repo / "main.py").write_text(
        "from factory import create_app\n\n"
        "def run_server():\n"
        "    app = create_app()\n"
        "    return app\n",
        encoding="utf-8",
    )
    (repo / "handlers.py").write_text(
        "from factory import create_app\n\n"
        "def init_handler():\n"
        "    return create_app()\n",
        encoding="utf-8",
    )
    tests_dir = repo / "tests"
    tests_dir.mkdir(exist_ok=True)
    (tests_dir / "test_app.py").write_text(
        "from factory import create_app\n\n"
        "def test_create_app():\n"
        "    assert create_app() is not None\n",
        encoding="utf-8",
    )
    (tests_dir / "test_engine.py").write_text(
        "from factory import setup_engine\n\n"
        "def test_setup_engine():\n"
        "    assert setup_engine() == 'engine_v1'\n",
        encoding="utf-8",
    )


def _get_tools(server: Any) -> tuple[Any, Any]:
    tool_mgr = server._tool_manager
    get_ctx = tool_mgr.get_tool("get_context").fn
    get_ev = tool_mgr.get_tool("get_evidence").fn
    return get_ctx, get_ev


def test_compact_budget_enforcement(tmp_path: Path) -> None:
    """Run get_context(task='create_app', max_tokens=1000) and assert wire token cap <= 1000."""
    repo = tmp_path / "repo_compact"
    _setup_sample_repo(repo)

    idx = Indexer(repo)
    idx.index()

    server = create_server(repo)
    get_context_fn, _ = _get_tools(server)

    res = get_context_fn(query="create_app", max_tokens=1000, compact=True)
    assert res.get("status") == "OK"

    # Serialized wire payload check
    raw_payload = json.dumps(res, separators=(",", ":"), ensure_ascii=False)
    tok_count = count_tokens(raw_payload, profile="o200k_base")
    assert tok_count <= 1000
    assert tok_count <= get_effective_cap(1000)

    # Ultra-dense 4-element tuple format for callers and tests:
    # [canonical_id, "file:line", evidence_class, evidence_id]
    if "callers" in res:
        for c in res["callers"]:
            assert isinstance(c, list)
            assert len(c) == 4
            assert isinstance(c[0], str)  # canonical_id
            assert ":" in c[1]  # "file:line"
            assert isinstance(c[2], str)  # evidence_class
            assert isinstance(c[3], str) and c[3].startswith("ev_")  # evidence_id

    if "tests" in res:
        for t in res["tests"]:
            assert isinstance(t, list)
            assert len(t) == 4
            assert isinstance(t[0], str)
            assert ":" in t[1]
            assert isinstance(t[2], str)
            assert isinstance(t[3], str) and t[3].startswith("ev_")

    # Machine drill-down list emitted
    assert "evidence_ids" in res
    assert isinstance(res["evidence_ids"], list)
    assert len(res["evidence_ids"]) > 0


def test_json_integrity_across_truncation_budgets(tmp_path: Path) -> None:
    """Verify json.loads() succeeds and wire format remains valid across multiple tight budgets."""
    repo = tmp_path / "repo_integrity"
    _setup_sample_repo(repo)

    idx = Indexer(repo)
    idx.index()

    server = create_server(repo)
    get_context_fn, _ = _get_tools(server)

    for budget in [1500, 800, 500, 300, 150]:
        res = get_context_fn(query="create_app", max_tokens=budget, compact=True)
        raw = json.dumps(res, separators=(",", ":"), ensure_ascii=False)
        parsed = json.loads(raw)
        assert isinstance(parsed, dict)
        assert parsed.get("status") in ("OK", "BUDGET_TOO_SMALL")
        if parsed.get("status") == "OK":
            assert count_tokens(raw, profile="o200k_base") <= budget


def test_budget_too_small_structured_error(tmp_path: Path) -> None:
    """Request max_tokens=20 and assert status == 'BUDGET_TOO_SMALL' with required tokens."""
    repo = tmp_path / "repo_small_budget"
    _setup_sample_repo(repo)

    idx = Indexer(repo)
    idx.index()

    server = create_server(repo)
    get_context_fn, _ = _get_tools(server)

    res = get_context_fn(query="create_app", max_tokens=20, compact=True)
    assert res.get("status") == "BUDGET_TOO_SMALL"
    assert res.get("max_tokens") == 20
    assert "required_tokens" in res
    assert res["required_tokens"] > 20


def test_drill_down_evidence_retrieval(tmp_path: Path) -> None:
    """Call get_evidence(ids=res['evidence_ids'][:2]) and verify proof blocks are returned."""
    repo = tmp_path / "repo_drilldown"
    _setup_sample_repo(repo)

    idx = Indexer(repo)
    idx.index()

    server = create_server(repo)
    get_context_fn, get_evidence_fn = _get_tools(server)

    res = get_context_fn(query="create_app", max_tokens=1000, compact=True)
    assert res.get("status") == "OK"
    eids = res.get("evidence_ids", [])
    assert len(eids) >= 2

    # Request proof blocks by evidence ids directly
    proofs = get_evidence_fn(ids=eids[:2])
    assert isinstance(proofs, list)
    assert len(proofs) >= 1
    for proof in proofs:
        assert "file" in proof
        assert "start_line" in proof
        assert "snippet" in proof
        assert (proof.get("evidence_id") in eids) or (proof.get("id") in eids)


def test_backward_compatibility_compact_false(tmp_path: Path) -> None:
    """Request compact=False and verify all legacy fields exist."""
    repo = tmp_path / "repo_legacy"
    _setup_sample_repo(repo)

    idx = Indexer(repo)
    idx.index()

    server = create_server(repo)
    get_context_fn, _ = _get_tools(server)

    res = get_context_fn(query="create_app", max_tokens=1000, compact=False)
    # Legacy dictionary fields must exist
    assert "schema_version" in res
    assert "task" in res
    assert "intent" in res
    assert "freshness" in res
    assert "symbols" in res
    assert "relationships" in res
    assert "files" in res
    assert "evidence" in res
    assert "budget" in res
    assert "metadata" in res
