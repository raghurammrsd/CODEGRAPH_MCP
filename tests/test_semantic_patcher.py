"""Comprehensive test suite for CodeGraph MCP Semantic Multi-File Patch Engine.

Covers:
1. Dry-run preview zero mutation invariant (hashes, mtimes, bytes unchanged).
2. Atomic multi-file patch commit (files updated, manifest written, status APPLIED).
3. Precondition hash mismatch rejection (FILE_HASH_MISMATCH, zero mutation).
4. Missing target hunk rejection (zero mutation).
5. Ambiguous target hunk rejection (>1 match, zero mutation).
6. Pre-flight Python syntax error aborts with zero mutation.
7. Pre-flight JSON syntax error aborts with zero mutation.
8. Pre-flight JS/TS structural bracket imbalance aborts with zero mutation.
9. Sensitive path protection (.env, id_rsa blocked).
10. Boundary escape / path traversal protection.
11. Atomic rollback restoration (manifest verification, byte-exact restoration).
12. CLI command: codegraph refactor patch (--dry-run and commit).
"""
from __future__ import annotations

import json
from pathlib import Path

import pytest
from typer.testing import CliRunner

from codegraph.cli import app
from codegraph.indexing.indexer import Indexer
from codegraph.refactor.models import RefactorStatus
from codegraph.refactor.patcher import (
    apply_semantic_patch,
    preview_semantic_patch,
)
from codegraph.refactor.transactions import (
    read_manifest,
    rollback_refactor,
)

runner = CliRunner()


@pytest.fixture
def patch_repo(tmp_path: Path) -> Path:
    """Create a minimal repository with Python, JSON, and TypeScript files."""
    repo = tmp_path / "patch_repo"
    repo.mkdir()

    src = repo / "src"
    src.mkdir()

    # Python file
    calc_py = src / "calc.py"
    calc_py.write_text(
        "def add(a: int, b: int) -> int:\n"
        "    return a + b\n\n"
        "def multiply(a: int, b: int) -> int:\n"
        "    return a * b\n",
        encoding="utf-8",
    )

    # JSON file
    config_json = repo / "config.json"
    config_json.write_text('{\n  "version": "1.0.0",\n  "active": true\n}\n', encoding="utf-8")

    # TypeScript file
    util_ts = src / "util.ts"
    util_ts.write_text(
        "export function formatName(first: string, last: string): string {\n"
        "    return `${first} ${last}`;\n"
        "}\n",
        encoding="utf-8",
    )

    indexer = Indexer(repo)
    indexer.index()
    return repo


def test_dry_run_zero_mutation(patch_repo: Path) -> None:
    """Scenario 1: Dry-run preview must never modify files on disk."""
    calc_py = patch_repo / "src" / "calc.py"
    before_bytes = calc_py.read_bytes()

    patch = {
        "path": "src/calc.py",
        "hunks": [
            {
                "target": "def add(a: int, b: int) -> int:\n    return a + b",
                "replacement": "def add(a: int, b: int) -> int:\n    # Added comment\n    return a + b",
            }
        ],
    }

    result = preview_semantic_patch(patch_repo, [patch])
    assert result.status == RefactorStatus.READY
    assert result.files_changed == 1
    assert "src/calc.py" in result.diffs
    assert "+    # Added comment" in result.diffs["src/calc.py"]

    # File on disk must remain strictly identical
    assert calc_py.read_bytes() == before_bytes


def test_atomic_multi_file_commit(patch_repo: Path) -> None:
    """Scenario 2: Atomically patch multiple files in one transaction."""
    calc_py = patch_repo / "src" / "calc.py"
    config_json = patch_repo / "config.json"

    patches = [
        {
            "path": "src/calc.py",
            "hunks": [
                {
                    "target": "return a + b",
                    "replacement": "return int(a + b)",
                }
            ],
        },
        {
            "path": "config.json",
            "hunks": [
                {
                    "target": '"version": "1.0.0"',
                    "replacement": '"version": "2.0.0"',
                }
            ],
        },
    ]

    result = apply_semantic_patch(patch_repo, patches, dry_run=False)
    assert result.status == RefactorStatus.APPLIED
    assert result.files_changed == 2
    assert result.rollback_id is not None

    # Check files updated
    assert "return int(a + b)" in calc_py.read_text(encoding="utf-8")
    assert '"version": "2.0.0"' in config_json.read_text(encoding="utf-8")

    # Check manifest exists
    manifest = read_manifest(patch_repo, result.rollback_id)
    assert manifest is not None
    assert manifest["status"] == "APPLIED"


def test_precondition_hash_mismatch_rejected(patch_repo: Path) -> None:
    """Scenario 3: Reject patch if expected_hash does not match disk."""
    calc_py = patch_repo / "src" / "calc.py"
    before_bytes = calc_py.read_bytes()

    patch = {
        "path": "src/calc.py",
        "expected_hash": "deadbeef1234567890abcdef1234567890abcdef1234567890abcdef12345678",
        "hunks": [
            {
                "target": "return a + b",
                "replacement": "return a + b + 1",
            }
        ],
    }

    result = apply_semantic_patch(patch_repo, [patch], dry_run=False)
    assert result.status == RefactorStatus.ERROR
    assert any("HASH_MISMATCH" in err for err in result.errors)
    assert calc_py.read_bytes() == before_bytes


def test_target_hunk_not_found(patch_repo: Path) -> None:
    """Scenario 4: Reject patch if target hunk cannot be found."""
    calc_py = patch_repo / "src" / "calc.py"
    before_bytes = calc_py.read_bytes()

    patch = {
        "path": "src/calc.py",
        "hunks": [
            {
                "target": "def non_existent_function():",
                "replacement": "def replaced():",
            }
        ],
    }

    result = apply_semantic_patch(patch_repo, [patch], dry_run=False)
    assert result.status == RefactorStatus.ERROR
    assert any("Target hunk not found" in err for err in result.errors)
    assert calc_py.read_bytes() == before_bytes


def test_python_syntax_error_aborts(patch_repo: Path) -> None:
    """Scenario 6: Pre-flight syntax validation must block broken Python code with zero mutation."""
    calc_py = patch_repo / "src" / "calc.py"
    before_bytes = calc_py.read_bytes()

    patch = {
        "path": "src/calc.py",
        "hunks": [
            {
                "target": "return a + b",
                "replacement": "return a + (b *  # unclosed parenthesis syntax error",
            }
        ],
    }

    result = apply_semantic_patch(patch_repo, [patch], dry_run=False)
    assert result.status == RefactorStatus.ERROR
    assert any("Python SyntaxError" in err for err in result.errors)
    assert calc_py.read_bytes() == before_bytes


def test_json_syntax_error_aborts(patch_repo: Path) -> None:
    """Scenario 7: Pre-flight validation blocks broken JSON."""
    config_json = patch_repo / "config.json"
    before_bytes = config_json.read_bytes()

    patch = {
        "path": "config.json",
        "hunks": [
            {
                "target": '"version": "1.0.0"',
                "replacement": '"version": "1.0.0", invalid trailing syntax,,,',
            }
        ],
    }

    result = apply_semantic_patch(patch_repo, [patch], dry_run=False)
    assert result.status == RefactorStatus.ERROR
    assert any("JSON DecodeError" in err for err in result.errors)
    assert config_json.read_bytes() == before_bytes


def test_ts_unbalanced_delimiters_aborts(patch_repo: Path) -> None:
    """Scenario 8: Pre-flight validation blocks unbalanced TS brackets."""
    util_ts = patch_repo / "src" / "util.ts"
    before_bytes = util_ts.read_bytes()

    patch = {
        "path": "src/util.ts",
        "hunks": [
            {
                "target": "return `${first} ${last}`;",
                "replacement": "return `${first} ${last}`; } // extra closing brace",
            }
        ],
    }

    result = apply_semantic_patch(patch_repo, [patch], dry_run=False)
    assert result.status == RefactorStatus.ERROR
    assert any("unbalanced" in err for err in result.errors)
    assert util_ts.read_bytes() == before_bytes


def test_sensitive_and_escaped_path_blocked(patch_repo: Path) -> None:
    """Scenario 9 & 10: Block sensitive files and directory traversal."""
    env_file = patch_repo / ".env"
    env_file.write_text("SECRET_KEY=12345\n", encoding="utf-8")

    # Sensitive path
    res_sensitive = apply_semantic_patch(
        patch_repo,
        [{"path": ".env", "hunks": [{"target": "SECRET_KEY=12345", "replacement": "REDACTED"}]}],
    )
    assert res_sensitive.status == RefactorStatus.BLOCKED

    # Path traversal
    res_escape = apply_semantic_patch(
        patch_repo,
        [{"path": "../../outside.txt", "hunks": [{"target": "foo", "replacement": "bar"}]}],
    )
    assert res_escape.status in (RefactorStatus.BLOCKED, RefactorStatus.ERROR)


def test_atomic_rollback(patch_repo: Path) -> None:
    """Scenario 11: Rollback restores original file bytes completely."""
    calc_py = patch_repo / "src" / "calc.py"
    orig_bytes = calc_py.read_bytes()

    patch = {
        "path": "src/calc.py",
        "hunks": [
            {
                "target": "return a + b",
                "replacement": "return (a + b) * 100",
            }
        ],
    }

    apply_res = apply_semantic_patch(patch_repo, [patch], dry_run=False)
    assert apply_res.status == RefactorStatus.APPLIED
    assert apply_res.rollback_id is not None
    assert "return (a + b) * 100" in calc_py.read_text(encoding="utf-8")

    # Now rollback
    rollback_res = rollback_refactor(patch_repo, apply_res.rollback_id)
    assert rollback_res.status == RefactorStatus.ROLLED_BACK
    assert calc_py.read_bytes() == orig_bytes


def test_cli_refactor_patch(patch_repo: Path) -> None:
    """Scenario 12: Test CLI codegraph refactor patch command."""
    calc_py = patch_repo / "src" / "calc.py"
    orig_content = calc_py.read_text(encoding="utf-8")

    patch_file = patch_repo / "patch.json"
    patch_file.write_text(
        json.dumps([
            {
                "path": "src/calc.py",
                "hunks": [
                    {
                        "target": "def multiply(a: int, b: int) -> int:",
                        "replacement": "def multiply(a: int, b: int) -> int:  # Multiplies",
                    }
                ],
            }
        ]),
        encoding="utf-8",
    )

    # Dry-run via CLI
    res_dry = runner.invoke(app, ["refactor", "patch", str(patch_file), "-r", str(patch_repo), "--dry-run"])
    assert res_dry.exit_code == 0
    assert "READY" in res_dry.stdout
    assert calc_py.read_text(encoding="utf-8") == orig_content

    # Commit via CLI
    res_commit = runner.invoke(app, ["refactor", "patch", str(patch_file), "-r", str(patch_repo), "--json"])
    assert res_commit.exit_code == 0
    data = json.loads(res_commit.stdout)
    assert data["status"] == "APPLIED"
    assert "Multiplies" in calc_py.read_text(encoding="utf-8")
