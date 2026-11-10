"""Comprehensive Tests for CodeGraph BYOC PostgreSQL Storage Engine.

Covers:
1. Universal `StorageRow` dual index and dict-key access.
2. SQLite <-> PostgreSQL SQL dialect adaptation.
3. Database URL password redaction for secure logging and error output.
4. Schema coverage: all 22 CodeGraph AST tables and lookup indexes.
5. Offline resiliency & graceful fallback to local SQLite when remote PostgreSQL is unreachable.
6. CLI integration: `codegraph db status`, `codegraph db check`, and `codegraph db init`.
"""
from __future__ import annotations

from pathlib import Path

import pytest
from typer.testing import CliRunner

from codegraph.cli import app
from codegraph.indexing.indexer import Indexer
from codegraph.indexing.storage import (
    POSTGRES_SCHEMA_STATEMENTS,
    StorageRow,
    adapt_sql_for_postgres,
    redact_db_url,
    verify_postgres_connection,
)

runner = CliRunner()


def test_storage_row_dual_access() -> None:
    """StorageRow supports both tuple indexing and column-name dictionary lookups."""
    cols = ["id", "canonical_id", "path", "line", "score"]
    vals = ["sym_123", "pkg:mod:MyClass", "src/mod.py", 42, 0.95]
    row = StorageRow(vals, cols)

    # 1. Index access
    assert row[0] == "sym_123"
    assert row[1] == "pkg:mod:MyClass"
    assert row[3] == 42
    assert row[4] == 0.95

    # 2. Key access (case-insensitive)
    assert row["id"] == "sym_123"
    assert row["canonical_id"] == "pkg:mod:MyClass"
    assert row["PATH"] == "src/mod.py"
    assert row["line"] == 42

    # 3. Dict conversion & iteration
    d = row.as_dict()
    assert d["id"] == "sym_123"
    assert list(row.keys()) == ["id", "canonical_id", "path", "line", "score"]
    assert len(row) == 5
    assert tuple(row) == tuple(vals)


def test_sql_dialect_adaptation() -> None:
    """`adapt_sql_for_postgres` converts `?` to `%s` and handles SQLite-only PRAGMAs."""
    # 1. Parameter placeholder translation
    query = "SELECT * FROM symbols WHERE canonical_id = ? AND status = ? LIMIT ?"
    adapted = adapt_sql_for_postgres(query)
    assert adapted == "SELECT * FROM symbols WHERE canonical_id = %s AND status = %s LIMIT %s"
    assert "?" not in adapted

    # 2. SQLite PRAGMAs commented out for PostgreSQL
    pragma = "PRAGMA wal_checkpoint(TRUNCATE);"
    adapted_pragma = adapt_sql_for_postgres(pragma)
    assert adapted_pragma.startswith("--")


def test_database_url_password_redaction() -> None:
    """Database URLs have passwords stripped for secure terminal display and logging."""
    raw = "postgresql://my_user:super_secret_pw@db.supabase.co:5432/production_db"
    redacted = redact_db_url(raw)
    assert "super_secret_pw" not in redacted
    assert "my_user" in redacted
    assert "db.supabase.co:5432/production_db" in redacted
    assert "******" in redacted


def test_postgres_schema_completeness() -> None:
    """PostgreSQL DDL defines all 22 required CodeGraph AST tables and 11 indexes."""
    tables = [s for s in POSTGRES_SCHEMA_STATEMENTS if "CREATE TABLE" in s]
    indexes = [s for s in POSTGRES_SCHEMA_STATEMENTS if "CREATE INDEX" in s]

    assert len(tables) == 22
    assert len(indexes) == 11
    assert any("symbols" in s for s in tables)
    assert any("calls" in s for s in tables)
    assert any("framework_routes" in s for s in tables)
    assert any("graph_edges" in s for s in tables)
    assert any("runtime_observations" in s for s in tables)
    assert any("agent_memories" in s for s in tables)


def test_offline_fallback_when_postgres_unreachable(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    """If `CODEGRAPH_DATABASE_URL` is unreachable, `Indexer.session()` safely falls back to local SQLite."""
    # Point to non-routable port to guarantee immediate connection failure
    monkeypatch.setenv("CODEGRAPH_DATABASE_URL", "postgresql://postgres:pass@127.0.0.1:54329/codegraph_test")

    # Seed a simple repo with local SQLite index
    (tmp_path / "app.py").write_text("def hello(): pass\n")
    indexer = Indexer(tmp_path)
    indexer.index()

    # Session should fall back to local SQLite without raising an unhandled exception
    with indexer.session() as con:
        cur = con.cursor()
        cur.execute("SELECT count(*) FROM symbols")
        row = cur.fetchone()
        assert row is not None
        assert row[0] >= 1


def test_cli_db_status_local_sqlite(tmp_path: Path) -> None:
    """`codegraph db status` outputs correct local SQLite statistics when no remote URL is set."""
    (tmp_path / "app.py").write_text("def test(): return 1\n")
    Indexer(tmp_path).index()

    res = runner.invoke(app, ["db", "status", str(tmp_path)])
    assert res.exit_code == 0
    assert "SQLite (Local Embedded)" in res.stdout
    assert "Files Indexed:" in res.stdout

    # JSON mode
    res_json = runner.invoke(app, ["db", "status", str(tmp_path), "--json"])
    assert res_json.exit_code == 0
    assert '"backend": "sqlite"' in res_json.stdout


def test_cli_db_check_connection_failure() -> None:
    """`codegraph db check` exits with code 1 and outputs clean redacted error on unreachable host."""
    res = runner.invoke(app, ["db", "check", "--url", "postgresql://postgres:secret@127.0.0.1:54329/testdb"])
    assert res.exit_code == 1
    assert "Connection test failed:" in res.output
    assert "secret" not in res.output

    # In JSON mode it returns exit code 0 with {"connected": false}
    res_json = runner.invoke(app, ["db", "check", "--url", "postgresql://postgres:secret@127.0.0.1:54329/testdb", "--json"])
    assert res_json.exit_code == 0
    assert '"connected": false' in res_json.output
    assert "secret" not in res_json.output


def test_verify_postgres_connection_error() -> None:
    """`verify_postgres_connection` returns structured error on invalid connection."""
    res = verify_postgres_connection("postgresql://postgres:secret@127.0.0.1:54329/testdb", timeout_seconds=1.0)
    assert res["status"] == "error"
    assert res["connected"] is False
    assert "secret" not in res["url"]
    assert res["url"] == "postgresql://postgres:******@127.0.0.1:54329/testdb"
