"""Bridge connecting CodeGraph to local Language Server Protocol (LSP) daemons."""
from __future__ import annotations

import shutil
import time
from pathlib import Path

from .client import LSPClient
from .models import DiagnosticSeverity, LSPBridgeReport, LSPDiagnostic

_SUPPORTED_SERVERS = {
    "python": ["pyright-langserver", "--stdio"],
    "typescript": ["typescript-language-server", "--stdio"],
    "go": ["gopls"],
    "rust": ["rust-analyzer"],
    "cpp": ["clangd"],
}


def detect_lsp_servers(workspace: Path | None = None) -> dict[str, str]:
    """Scan host system for installed language server binaries."""
    found: dict[str, str] = {}
    for lang, cmd_parts in _SUPPORTED_SERVERS.items():
        bin_name = cmd_parts[0]
        path = shutil.which(bin_name)
        if path:
            found[lang] = path
    return found


def collect_lsp_diagnostics(
    workspace: Path,
    file_path: str | None = None,
    timeout_seconds: float = 3.0,
) -> LSPBridgeReport:
    """Collect live compiler and language server diagnostics for files in workspace."""
    t0 = time.perf_counter()
    repo = workspace.resolve()
    discovered = detect_lsp_servers(repo)

    if not discovered:
        elapsed = (time.perf_counter() - t0) * 1000.0
        return LSPBridgeReport(
            workspace=str(repo),
            status="FALLBACK_STATIC",
            discovered_servers={},
            total_diagnostics=0,
            error_count=0,
            warning_count=0,
            diagnostics=[],
            latency_ms=elapsed,
        )

    all_diagnostics: list[LSPDiagnostic] = []

    # If specific file given, pick server by extension
    target_langs = list(discovered.keys())
    if file_path:
        ext = Path(file_path).suffix.lower()
        if ext in (".py", ".pyi"):
            target_langs = ["python"] if "python" in discovered else []
        elif ext in (".ts", ".tsx", ".js", ".jsx"):
            target_langs = ["typescript"] if "typescript" in discovered else []
        elif ext == ".go":
            target_langs = ["go"] if "go" in discovered else []
        elif ext == ".rs":
            target_langs = ["rust"] if "rust" in discovered else []
        elif ext in (".c", ".cc", ".cpp", ".h", ".hpp"):
            target_langs = ["cpp"] if "cpp" in discovered else []

    for lang in target_langs:
        cmd = _SUPPORTED_SERVERS[lang]
        client = LSPClient(cmd, repo, timeout_seconds=timeout_seconds)
        try:
            if client.start() and client.initialize():
                # Open target file or sample files
                if file_path:
                    p = repo / file_path
                    if p.is_file():
                        client.open_document(p, lang, p.read_text(encoding="utf-8", errors="replace"))
                # Short read window
                time.sleep(0.1)
                all_diagnostics.extend(client.get_diagnostics())
        except Exception:
            pass
        finally:
            client.close()

    errors = sum(1 for d in all_diagnostics if d.severity == DiagnosticSeverity.ERROR)
    warnings = sum(1 for d in all_diagnostics if d.severity == DiagnosticSeverity.WARNING)
    elapsed = (time.perf_counter() - t0) * 1000.0

    return LSPBridgeReport(
        workspace=str(repo),
        status="READY" if discovered else "FALLBACK_STATIC",
        discovered_servers=discovered,
        total_diagnostics=len(all_diagnostics),
        error_count=errors,
        warning_count=warnings,
        diagnostics=all_diagnostics,
        latency_ms=elapsed,
    )
