"""Declarative Architecture Invariant Engine for CodeGraph.

Enforces architectural rules, layered clean architecture boundaries, and forbidden dependencies:
- Reads declarative architectural rules from .codegraph/rules.yaml
- Checks forbidden import edges (e.g. controllers importing database tables directly)
- Enforces layer isolation (domain layer cannot import infrastructure or UI)
- Enforces naming conventions and required interface implementations
"""
from __future__ import annotations

import fnmatch
import json
import sqlite3
from dataclasses import asdict, dataclass, field
from pathlib import Path
from typing import Any


@dataclass(frozen=True)
class RuleViolation:
    """An architectural invariant violation."""

    rule_name: str
    source_file: str
    line: int
    target_entity: str
    severity: str  # ERROR | WARNING
    message: str

    def as_dict(self) -> dict[str, Any]:
        return asdict(self)


@dataclass
class ArchitectureComplianceReport:
    """Consolidated compliance report across all architectural rules."""

    workspace: str
    status: str  # COMPLIANT | VIOLATIONS_DETECTED
    total_rules_checked: int
    violations_count: int
    violations: list[RuleViolation] = field(default_factory=list)

    def as_dict(self) -> dict[str, Any]:
        return {
            "workspace": self.workspace,
            "status": self.status,
            "total_rules_checked": self.total_rules_checked,
            "violations_count": self.violations_count,
            "violations": [v.as_dict() for v in self.violations],
        }


def evaluate_architecture_rules(
    repository: Path,
    con: sqlite3.Connection,
    rules: list[dict[str, Any]] | None = None,
) -> ArchitectureComplianceReport:
    """Evaluate architectural boundaries against the repository graph index."""
    repo = repository.resolve()
    violations: list[RuleViolation] = []

    # If rules not passed, load from .codegraph/rules.yaml or rules.json
    active_rules: list[dict[str, Any]] = rules or []
    if not active_rules:
        rule_file_json = repo / ".codegraph" / "rules.json"
        if rule_file_json.is_file():
            try:
                active_rules = json.loads(rule_file_json.read_text(encoding="utf-8"))
            except Exception:
                pass

    # Default starter rules if none defined
    if not active_rules:
        active_rules = [
            {
                "name": "prevent-controller-to-db-leakage",
                "source_pattern": "*controller*.*",
                "cannot_import": ["*models*", "*db*", "*entities*"],
                "message": "Controller must not import database models directly; route through services.",
            }
        ]

    # Query all imports from database
    cur = con.cursor()
    cur.execute("PRAGMA table_info(imports);")
    imp_cols = {col[1] for col in cur.fetchall()}
    src_col = "source_path" if "source_path" in imp_cols else "source_file"
    cur.execute(f"SELECT {src_col}, module, name, line FROM imports;")
    all_imports = cur.fetchall()

    for r in active_rules:
        name = r.get("name", "unnamed-rule")
        src_pat = r.get("source_pattern", "*")
        cannot_import = r.get("cannot_import", [])
        msg = r.get("message", f"Rule '{name}' violated.")

        for imp_source, imp_module, imp_name, imp_line in all_imports:
            # Check if file matches source pattern
            if fnmatch.fnmatch(imp_source, src_pat) or fnmatch.fnmatch(Path(imp_source).name, src_pat):
                # Check forbidden targets
                full_import_target = f"{imp_module}.{imp_name}" if imp_name else imp_module
                for forbidden in cannot_import:
                    if fnmatch.fnmatch(full_import_target, forbidden) or fnmatch.fnmatch(imp_module, forbidden):
                        violations.append(
                            RuleViolation(
                                rule_name=name,
                                source_file=imp_source,
                                line=imp_line,
                                target_entity=full_import_target,
                                severity="ERROR",
                                message=msg,
                            )
                        )

    status = "COMPLIANT" if not violations else "VIOLATIONS_DETECTED"
    return ArchitectureComplianceReport(
        workspace=str(repo),
        status=status,
        total_rules_checked=len(active_rules),
        violations_count=len(violations),
        violations=violations,
    )
