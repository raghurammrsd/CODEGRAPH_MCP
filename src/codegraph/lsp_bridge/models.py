"""Data models for Language Server Protocol (LSP) Bridge."""
from __future__ import annotations

from dataclasses import asdict, dataclass, field
from enum import StrEnum
from typing import Any


class DiagnosticSeverity(StrEnum):
    ERROR = "ERROR"
    WARNING = "WARNING"
    INFORMATION = "INFORMATION"
    HINT = "HINT"


@dataclass(frozen=True)
class LSPDiagnostic:
    """A compiler or language server diagnostic finding."""

    file_path: str
    line: int
    column: int
    end_line: int
    end_column: int
    severity: DiagnosticSeverity
    message: str
    code: str = ""
    source: str = ""

    def as_dict(self) -> dict[str, Any]:
        d = asdict(self)
        d["severity"] = self.severity.value
        return d


@dataclass(frozen=True)
class LSPLocation:
    """Definition or reference location resolved by LSP."""

    file_path: str
    line: int
    column: int

    def as_dict(self) -> dict[str, Any]:
        return asdict(self)


@dataclass
class LSPBridgeReport:
    """Consolidated status and diagnostic report across language servers."""

    workspace: str
    status: str  # READY | FALLBACK_STATIC | NOT_INSTALLED | ERROR
    discovered_servers: dict[str, str] = field(default_factory=dict)
    total_diagnostics: int = 0
    error_count: int = 0
    warning_count: int = 0
    diagnostics: list[LSPDiagnostic] = field(default_factory=list)
    latency_ms: float = 0.0

    def as_dict(self) -> dict[str, Any]:
        return {
            "workspace": self.workspace,
            "status": self.status,
            "discovered_servers": self.discovered_servers,
            "total_diagnostics": self.total_diagnostics,
            "error_count": self.error_count,
            "warning_count": self.warning_count,
            "diagnostics": [d.as_dict() for d in self.diagnostics],
            "latency_ms": round(self.latency_ms, 2),
        }
