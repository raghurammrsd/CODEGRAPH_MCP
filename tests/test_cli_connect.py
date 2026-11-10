"""Tests for `codegraph connect` and MCP profile/db integration."""
from __future__ import annotations

import json
from pathlib import Path

from typer.testing import CliRunner

from codegraph.cli import app
from codegraph.installer import build_agent_mcp_entry

runner = CliRunner()


def test_build_agent_mcp_entry_with_profile_and_db_url() -> None:
    entry = build_agent_mcp_entry(
        "cursor",
        command="codegraph",
        profile="core12",
        db_url="postgres://user:secret@db.supabase.co:5432/codegraph",
    )
    assert entry["command"] == "codegraph"
    assert entry["args"] == ["mcp", "serve", "--profile", "core12"]
    assert entry["env"] == {
        "CODEGRAPH_DATABASE_URL": "postgres://user:secret@db.supabase.co:5432/codegraph"
    }


def test_cli_connect_help() -> None:
    res = runner.invoke(app, ["connect", "--help"])
    assert res.exit_code == 0
    assert "Connect CodeGraph to your AI editors" in res.stdout
    assert "--profile" in res.stdout
    assert "--db-url" in res.stdout


def test_cli_connect_dry_run_json(tmp_path: Path) -> None:
    res = runner.invoke(
        app,
        [
            "connect",
            str(tmp_path),
            "--dry-run",
            "--target",
            "cursor",
            "--profile",
            "core12",
            "--json",
        ],
    )
    assert res.exit_code == 0
    data = json.loads(res.stdout)
    assert data["status"] in ("dry_run", "ok")
    assert data["profile"] == "core12"


def test_cli_connect_execution_configures_core12(tmp_path: Path) -> None:
    cursor_dir = tmp_path / ".cursor"
    cursor_dir.mkdir(parents=True)

    res = runner.invoke(
        app,
        [
            "connect",
            str(tmp_path),
            "--target",
            "cursor",
            "--profile",
            "core12",
            "--db-url",
            "postgres://user:pw@db.neon.tech/main",
            "--yes",
        ],
    )
    assert res.exit_code == 0
    assert "Configured MCP profile: core12" in res.stdout
    assert "postgres://user:******@db.neon.tech/main" in res.stdout

    mcp_json = cursor_dir / "mcp.json"
    assert mcp_json.exists()
    cfg = json.loads(mcp_json.read_text(encoding="utf-8"))
    assert cfg["mcpServers"]["codegraph"]["args"] == ["mcp", "serve", "--profile", "core12"]
    assert cfg["mcpServers"]["codegraph"]["env"]["CODEGRAPH_DATABASE_URL"] == (
        "postgres://user:pw@db.neon.tech/main"
    )
