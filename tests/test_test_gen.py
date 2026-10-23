"""Tests for automated test scaffolding generator."""
from __future__ import annotations

import ast
from pathlib import Path

import pytest

from codegraph.indexing.indexer import Indexer
from codegraph.test_gen import generate_test_scaffolding


@pytest.fixture
def repo_with_code(tmp_path: Path) -> Path:
    repo = tmp_path / "test_gen_repo"
    repo.mkdir()

    src = repo / "src"
    src.mkdir()

    service_file = src / "service.py"
    service_file.write_text(
        "class Database:\n"
        "    def query(self, sql: str):\n"
        "        pass\n\n"
        "class PaymentService:\n"
        "    def __init__(self, db: Database):\n"
        "        self.db = db\n\n"
        "    def process_payment(self, amount: float) -> bool:\n"
        "        if amount <= 0:\n"
        "            raise ValueError('Invalid amount')\n"
        "        self.db.query('INSERT INTO payments VALUES (?)')\n"
        "        return True\n"
    )

    indexer = Indexer(repo)
    indexer.index()
    return repo


def test_generate_pytest_scaffold(repo_with_code: Path) -> None:
    indexer = Indexer(repo_with_code)
    with indexer.session() as con:
        scaffold = generate_test_scaffolding(con, target="process_payment", repository=repo_with_code)

    assert scaffold.target_symbol == "process_payment"
    assert scaffold.framework == "pytest"
    assert "def test_process_payment_happy_path" in scaffold.test_code
    assert "test_process_payment_edge_case" in scaffold.test_code
    # Must be valid Python syntax
    parsed = ast.parse(scaffold.test_code)
    assert parsed is not None


def test_generate_jest_scaffold(repo_with_code: Path) -> None:
    indexer = Indexer(repo_with_code)
    with indexer.session() as con:
        scaffold = generate_test_scaffolding(
            con, target="process_payment", repository=repo_with_code, framework="jest"
        )

    assert scaffold.framework == "jest"
    assert 'describe("process_payment"' in scaffold.test_code
    assert "vitest" in scaffold.test_code


def test_generate_testez_scaffold(repo_with_code: Path) -> None:
    indexer = Indexer(repo_with_code)
    with indexer.session() as con:
        scaffold = generate_test_scaffolding(
            con, target="process_payment", repository=repo_with_code, framework="testez"
        )

    assert scaffold.framework == "testez"
    assert 'describe("process_payment"' in scaffold.test_code
    assert scaffold.suggested_test_file.endswith(".spec.luau")


def test_generate_fallback_scaffold(repo_with_code: Path) -> None:
    indexer = Indexer(repo_with_code)
    with indexer.session() as con:
        scaffold = generate_test_scaffolding(con, target="non_existent_symbol", repository=repo_with_code)

    assert scaffold.target_symbol == "non_existent_symbol"
    assert "def test_non_existent_symbol_placeholder" in scaffold.test_code
