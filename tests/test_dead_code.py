"""Comprehensive test suite for CodeGraph Dead Code & Zombie Route Detection Engine.

Covers:
1. Dead symbol discovery (functions/classes with 0 static and 0 runtime callers).
2. Exclusions (main/cli entry points, test functions, framework route handlers, dunder methods).
3. Zombie HTTP routes (uncalled routes in presence of runtime traces).
4. Unobserved HTTP routes (clean reporting when no runtime traces exist).
5. Orphaned database tables (0 static/runtime readers and 0 writers).
6. CLI command `codegraph dead-code` (--json and human-readable).
7. MCP tool `find_dead_code`.
"""
from __future__ import annotations

import asyncio
import json
from pathlib import Path

import pytest
from typer.testing import CliRunner

from codegraph.cli import app
from codegraph.dead_code import (
    find_dead_symbols,
    find_orphaned_tables,
    find_zombie_routes,
)
from codegraph.indexing.indexer import Indexer
from codegraph.mcp import create_server
from codegraph.runtime.ingestor import ingest_runtime_traces

runner = CliRunner()


@pytest.fixture
def dead_code_repo(tmp_path: Path) -> Path:
    """Create a repository containing active and dead code across Python and SQLite."""
    repo = tmp_path / "dead_code_repo"
    repo.mkdir()

    # Active and dead functions
    (repo / "service.py").write_text(
        "def active_function() -> str:\n"
        "    return 'active'\n\n"
        "def dead_utility_never_called() -> int:\n"
        "    return 42\n\n"
        "def main():\n"
        "    print(active_function())\n",
        encoding="utf-8",
    )

    # FastAPI routes (one active, one zombie)
    (repo / "api.py").write_text(
        "from fastapi import FastAPI\n"
        "app = FastAPI()\n\n"
        "@app.get('/api/v1/active')\n"
        "def active_endpoint():\n"
        "    return {'status': 'ok'}\n\n"
        "@app.get('/api/v1/zombie')\n"
        "def zombie_endpoint():\n"
        "    return {'deprecated': True}\n",
        encoding="utf-8",
    )

    # Database models (one active table, one orphaned table)
    (repo / "models.py").write_text(
        "from sqlalchemy import Column, Integer, String\n"
        "from sqlalchemy.orm import declarative_base\n"
        "Base = declarative_base()\n\n"
        "class Users(Base):\n"
        "    __tablename__ = 'users'\n"
        "    id = Column(Integer, primary_key=True)\n"
        "    name = Column(String)\n\n"
        "class LegacyAudit(Base):\n"
        "    __tablename__ = 'legacy_audit'\n"
        "    id = Column(Integer, primary_key=True)\n"
        "    notes = Column(String)\n",
        encoding="utf-8",
    )

    indexer = Indexer(repo)
    indexer.index()
    return repo


def test_dead_symbols_detection(dead_code_repo: Path) -> None:
    """Scenario 1: Flag unused function while excluding entry points and route handlers."""
    indexer = Indexer(dead_code_repo)
    with indexer.session() as con:
        dead = find_dead_symbols(con)
        names = {d.name for d in dead}

        assert "dead_utility_never_called" in names
        assert "main" not in names  # Entrypoint excluded
        assert "active_function" not in names  # Called by main()
        assert "active_endpoint" not in names  # Registered route handler
        assert "zombie_endpoint" not in names  # Registered route handler


def test_zombie_routes_without_runtime_telemetry(dead_code_repo: Path) -> None:
    """Scenario 2: When no runtime telemetry exists, routes are reported as UNOBSERVED_AT_RUNTIME."""
    indexer = Indexer(dead_code_repo)
    with indexer.session() as con:
        zombies, has_rt = find_zombie_routes(con)
        assert has_rt is False
        assert len(zombies) >= 2
        for r in zombies:
            assert r.status == "UNOBSERVED_AT_RUNTIME"
            assert "no runtime trace telemetry" in r.reason


def test_zombie_routes_with_runtime_telemetry(dead_code_repo: Path) -> None:
    """Scenario 3: When runtime traces exist, endpoints with 0 hits are flagged as ZOMBIE_ROUTE."""
    indexer = Indexer(dead_code_repo)
    with indexer.session() as con:
        # Ingest a runtime trace hit for /api/v1/active
        sample_trace = {
            "resourceSpans": [
                {
                    "scopeSpans": [
                        {
                            "spans": [
                                {
                                    "traceId": "4bf92f3577b34da6a3ce929d0e0e4736",
                                    "spanId": "00f067aa0ba902b7",
                                    "name": "GET /api/v1/active",
                                    "attributes": [
                                        {"key": "http.method", "value": {"stringValue": "GET"}},
                                        {"key": "http.route", "value": {"stringValue": "/api/v1/active"}},
                                        {"key": "http.status_code", "value": {"intValue": 200}},
                                    ],
                                }
                            ]
                        }
                    ]
                }
            ]
        }
        ingest_runtime_traces(con, data_or_path=sample_trace, format="otel")

        zombies, has_rt = find_zombie_routes(con)
        assert has_rt is True

        zombie_paths = {r.route_path: r.status for r in zombies}
        # /api/v1/zombie has 0 hits in traces -> ZOMBIE_ROUTE
        assert zombie_paths.get("/api/v1/zombie") == "ZOMBIE_ROUTE"
        # /api/v1/active was observed -> NOT in zombie list
        assert "/api/v1/active" not in zombie_paths


def test_orphaned_database_tables(dead_code_repo: Path) -> None:
    """Scenario 4: Identify orphaned tables with 0 queries."""
    indexer = Indexer(dead_code_repo)
    with indexer.session() as con:
        orphans = find_orphaned_tables(con)
        names = {t.table_name for t in orphans}
        assert "legacy_audit" in names


def test_cli_dead_code(dead_code_repo: Path) -> None:
    """Scenario 5: Test CLI codegraph dead-code command."""
    res = runner.invoke(app, ["dead-code", "-r", str(dead_code_repo), "--json"])
    assert res.exit_code == 0
    data = json.loads(res.stdout)
    assert data["total_dead_count"] > 0
    assert any(s["name"] == "dead_utility_never_called" for s in data["dead_symbols"])

    # Test text output
    res_text = runner.invoke(app, ["dead-code", "-r", str(dead_code_repo)])
    assert res_text.exit_code == 0
    assert "Dead Symbols" in res_text.stdout
    assert "dead_utility_never_called" in res_text.stdout


async def _run_mcp_dead_code_test(repo: Path) -> None:
    server = create_server(repo, profile="full")
    _, meta = await server.call_tool("find_dead_code", {"max_symbols": 50})
    result = meta.get("result") or meta
    assert "dead_symbols" in result
    assert "zombie_routes" in result
    assert any(s["name"] == "dead_utility_never_called" for s in result["dead_symbols"])


def test_mcp_find_dead_code(dead_code_repo: Path) -> None:
    """Scenario 6: Test find_dead_code tool via MCP server."""
    asyncio.run(_run_mcp_dead_code_test(dead_code_repo))
