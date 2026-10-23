"""Tests for Language Server Protocol (LSP) Bridge and client models."""
from __future__ import annotations

from pathlib import Path

from codegraph.lsp_bridge.bridge import collect_lsp_diagnostics, detect_lsp_servers
from codegraph.lsp_bridge.models import DiagnosticSeverity, LSPDiagnostic, LSPLocation


def test_lsp_models_and_serialization() -> None:
    diag = LSPDiagnostic(
        file_path="src/main.py",
        line=10,
        column=5,
        end_line=10,
        end_column=15,
        severity=DiagnosticSeverity.ERROR,
        message="Type mismatch: expected int, got str",
        code="type-error",
        source="pyright",
    )
    d_dict = diag.as_dict()
    assert d_dict["severity"] == "ERROR"
    assert d_dict["line"] == 10
    assert d_dict["code"] == "type-error"

    loc = LSPLocation(file_path="src/service.py", line=42, column=8)
    assert loc.as_dict()["line"] == 42


def test_detect_lsp_servers() -> None:
    servers = detect_lsp_servers()
    # Returns dictionary of found servers without error
    assert isinstance(servers, dict)


def test_collect_lsp_diagnostics_fallback(tmp_path: Path) -> None:
    # On a workspace without language server running, it gracefully falls back
    report = collect_lsp_diagnostics(tmp_path)
    assert report.status in ("READY", "FALLBACK_STATIC")
    assert isinstance(report.as_dict(), dict)
    assert report.error_count == 0
