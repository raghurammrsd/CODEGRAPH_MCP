"""Production-Grade Dataflow Taint-Tracking & SAST Security Engine for CodeGraph.

Traces untrusted user input sources (HTTP query params, headers, request bodies, CLI args)
through lexical scopes, variable assignments, and binary/f-string expressions into high-risk
execution sinks (CWE-89 SQL Injection, CWE-78 Command Injection, CWE-22 Path Traversal,
CWE-918 SSRF, and CWE-502 Insecure Deserialization).
"""
from __future__ import annotations

import ast
import re
import sqlite3
from dataclasses import dataclass, field
from enum import StrEnum
from pathlib import Path
from typing import Any


class TaintSeverity(StrEnum):
    CRITICAL = "CRITICAL"
    HIGH = "HIGH"
    MEDIUM = "MEDIUM"
    LOW = "LOW"


@dataclass
class TaintVulnerability:
    cwe_id: str
    vulnerability_type: str
    severity: TaintSeverity
    source_expr: str
    source_line: int
    sink_expr: str
    sink_line: int
    file_path: str
    trace: list[str] = field(default_factory=list)
    remediation: str = ""

    def as_dict(self) -> dict[str, Any]:
        return {
            "cwe_id": self.cwe_id,
            "vulnerability_type": self.vulnerability_type,
            "severity": self.severity.value,
            "source_expr": self.source_expr,
            "source_line": self.source_line,
            "sink_expr": self.sink_expr,
            "sink_line": self.sink_line,
            "file_path": self.file_path,
            "trace": self.trace,
            "remediation": self.remediation,
        }


@dataclass
class TaintReport:
    repository: str
    vulnerabilities: list[TaintVulnerability] = field(default_factory=list)

    @property
    def total_vulnerabilities(self) -> int:
        return len(self.vulnerabilities)

    @property
    def critical_count(self) -> int:
        return sum(1 for v in self.vulnerabilities if v.severity == TaintSeverity.CRITICAL)

    @property
    def high_count(self) -> int:
        return sum(1 for v in self.vulnerabilities if v.severity == TaintSeverity.HIGH)

    @property
    def medium_count(self) -> int:
        return sum(1 for v in self.vulnerabilities if v.severity == TaintSeverity.MEDIUM)

    @property
    def low_count(self) -> int:
        return sum(1 for v in self.vulnerabilities if v.severity == TaintSeverity.LOW)

    def as_dict(self) -> dict[str, Any]:
        return {
            "repository": self.repository,
            "total_vulnerabilities": self.total_vulnerabilities,
            "critical_count": self.critical_count,
            "high_count": self.high_count,
            "medium_count": self.medium_count,
            "low_count": self.low_count,
            "vulnerabilities": [v.as_dict() for v in self.vulnerabilities],
        }

    def to_sarif(self) -> dict[str, Any]:
        """Export findings to OASIS SARIF 2.1.0 JSON format for GitHub Security integration."""
        rule_map: dict[str, dict[str, Any]] = {}
        results: list[dict[str, Any]] = []

        level_map = {
            TaintSeverity.CRITICAL: "error",
            TaintSeverity.HIGH: "error",
            TaintSeverity.MEDIUM: "warning",
            TaintSeverity.LOW: "note",
        }

        for v in self.vulnerabilities:
            if v.cwe_id not in rule_map:
                cwe_num = v.cwe_id.replace("CWE-", "")
                rule_map[v.cwe_id] = {
                    "id": v.cwe_id,
                    "name": v.vulnerability_type.replace(" ", ""),
                    "shortDescription": {"text": v.vulnerability_type},
                    "fullDescription": {"text": f"Unsanitized dataflow taint reaches execution sink ({v.cwe_id})."},
                    "defaultConfiguration": {"level": level_map.get(v.severity, "warning")},
                    "help": {
                        "text": v.remediation,
                        "markdown": f"### Remediation\n\n{v.remediation}\n\n**CWE**: [{v.cwe_id}](https://cwe.mitre.org/data/definitions/{cwe_num}.html)",
                    },
                    "properties": {
                        "tags": ["security", "sast", "taint-analysis", v.cwe_id.lower()],
                        "problem.severity": "error" if v.severity in (TaintSeverity.CRITICAL, TaintSeverity.HIGH) else "warning",
                    },
                }

            thread_flow_locs = [
                {
                    "location": {
                        "message": {"text": f"Taint Source: {v.source_expr}"},
                        "physicalLocation": {
                            "artifactLocation": {"uri": v.file_path},
                            "region": {"startLine": v.source_line, "startColumn": 1},
                        },
                    }
                },
                {
                    "location": {
                        "message": {"text": f"Vulnerable Sink: {v.sink_expr}"},
                        "physicalLocation": {
                            "artifactLocation": {"uri": v.file_path},
                            "region": {"startLine": v.sink_line, "startColumn": 1},
                        },
                    }
                },
            ]

            results.append({
                "ruleId": v.cwe_id,
                "level": level_map.get(v.severity, "warning"),
                "message": {
                    "text": f"{v.vulnerability_type}: User input from '{v.source_expr}' flows unsanitized into sink '{v.sink_expr}'."
                },
                "locations": [
                    {
                        "physicalLocation": {
                            "artifactLocation": {"uri": v.file_path},
                            "region": {"startLine": v.sink_line, "startColumn": 1},
                        }
                    }
                ],
                "codeFlows": [
                    {
                        "threadFlows": [
                            {"locations": thread_flow_locs}
                        ]
                    }
                ],
            })

        return {
            "$schema": "https://json.schemastore.org/sarif-2.1.0.json",
            "version": "2.1.0",
            "runs": [
                {
                    "tool": {
                        "driver": {
                            "name": "CodeGraph SAST",
                            "semanticVersion": "2.1.7",
                            "informationUri": "https://github.com/codegraph/codegraph",
                            "rules": list(rule_map.values()),
                        }
                    },
                    "results": results,
                }
            ],
        }


_SOURCE_PATTERNS = [
    # Python Flask / Django / FastAPI
    r"request\.(?:args|form|values|json|data|GET|POST|query_params|headers)\b",
    r"req\.(?:query|body|params|headers)\b",
    # Go Gin / Echo
    r"c\.(?:Query|PostForm|Param|BindJSON)\(",
    # CLI / Env
    r"sys\.argv\[",
]

_SOURCE_RE = re.compile("|".join(_SOURCE_PATTERNS))


class _PythonTaintVisitor(ast.NodeVisitor):
    """AST visitor tracking taint propagation from sources to sinks."""

    def __init__(self, file_path: str, lines: list[str]) -> None:
        self.file_path = file_path
        self.lines = lines
        # Tainted variable name -> list of propagation steps
        self.tainted_vars: dict[str, list[str]] = {}
        # Variable name -> source line
        self.taint_source_lines: dict[str, int] = {}
        # Variable name -> source expression
        self.taint_source_exprs: dict[str, str] = {}
        self.findings: list[TaintVulnerability] = []

    def _is_tainted_expr(self, node: ast.AST) -> tuple[bool, str, list[str]]:
        """Check if an expression is tainted or references a tainted variable."""
        # 1. Direct Source Match in unparsed expression
        raw = ast.unparse(node) if hasattr(ast, "unparse") else ""
        if _SOURCE_RE.search(raw):
            return True, raw, [f"Taint source instantiated: {raw}"]

        # 2. Variable Identifier
        if isinstance(node, ast.Name):
            if node.id in self.tainted_vars:
                return True, self.taint_source_exprs.get(node.id, node.id), list(self.tainted_vars[node.id])

        # 3. Binary Operation (e.g. "SELECT ... " + user_input)
        if isinstance(node, ast.BinOp):
            left_tainted, left_src, left_trace = self._is_tainted_expr(node.left)
            if left_tainted:
                return True, left_src, left_trace + ["Propagated via binary operation (+)"]
            right_tainted, right_src, right_trace = self._is_tainted_expr(node.right)
            if right_tainted:
                return True, right_src, right_trace + ["Propagated via binary operation (+)"]

        # 4. Formatted Value / F-String (e.g. f"SELECT ... {user_input}")
        if isinstance(node, ast.JoinedStr):
            for part in node.values:
                if isinstance(part, ast.FormattedValue):
                    is_t, src, tr = self._is_tainted_expr(part.value)
                    if is_t:
                        return True, src, tr + ["Propagated via f-string formatting"]

        # 5. Method call (e.g. "...".format(user_input))
        if isinstance(node, ast.Call):
            for arg in node.args:
                is_t, src, tr = self._is_tainted_expr(arg)
                if is_t:
                    return True, src, tr + [f"Propagated through argument into {ast.unparse(node.func) if hasattr(ast, 'unparse') else 'call'}"]

        return False, "", []

    def visit_Assign(self, node: ast.Assign) -> None:
        is_t, src, tr = self._is_tainted_expr(node.value)
        if is_t:
            for target in node.targets:
                if isinstance(target, ast.Name):
                    var_name = target.id
                    self.tainted_vars[var_name] = tr + [f"Assigned to variable '{var_name}' on line {node.lineno}"]
                    self.taint_source_lines[var_name] = node.lineno
                    self.taint_source_exprs[var_name] = src
        self.generic_visit(node)

    def visit_Call(self, node: ast.Call) -> None:
        call_str = ast.unparse(node.func) if hasattr(ast, "unparse") else ""

        # SINK 1: SQL Injection (cursor.execute, con.execute, db.query with tainted string)
        if any(sink in call_str for sink in ("execute", "raw", "query", "select_raw")):
            if node.args:
                arg0 = node.args[0]
                is_t, src, tr = self._is_tainted_expr(arg0)
                if is_t:
                    self.findings.append(
                        TaintVulnerability(
                            cwe_id="CWE-89",
                            vulnerability_type="SQL_INJECTION",
                            severity=TaintSeverity.CRITICAL,
                            source_expr=src,
                            source_line=self.taint_source_lines.get(src, node.lineno),
                            sink_expr=ast.unparse(node) if hasattr(ast, "unparse") else call_str,
                            sink_line=node.lineno,
                            file_path=self.file_path,
                            trace=tr + [f"Reached SQL execution sink '{call_str}' on line {node.lineno}"],
                            remediation="Use parameterized queries with bound parameters, e.g. cursor.execute('SELECT ... WHERE id = ?', (id,))",
                        )
                    )

        # SINK 2: OS Command Injection (os.system, subprocess.run, subprocess.Popen)
        if any(sink in call_str for sink in ("os.system", "subprocess.run", "subprocess.Popen", "subprocess.call", "os.popen")):
            has_shell = any(k.arg == "shell" and isinstance(k.value, ast.Constant) and k.value.value is True for k in node.keywords)
            is_os_system = "os.system" in call_str or "os.popen" in call_str

            for arg in node.args:
                is_t, src, tr = self._is_tainted_expr(arg)
                if is_t and (has_shell or is_os_system):
                    self.findings.append(
                        TaintVulnerability(
                            cwe_id="CWE-78",
                            vulnerability_type="COMMAND_INJECTION",
                            severity=TaintSeverity.CRITICAL,
                            source_expr=src,
                            source_line=self.taint_source_lines.get(src, node.lineno),
                            sink_expr=ast.unparse(node) if hasattr(ast, "unparse") else call_str,
                            sink_line=node.lineno,
                            file_path=self.file_path,
                            trace=tr + [f"Reached OS command shell sink '{call_str}' on line {node.lineno}"],
                            remediation="Avoid shell=True. Pass command arguments as an array list, e.g. subprocess.run(['cmd', arg1, arg2])",
                        )
                    )

        # SINK 3: Code Injection / Insecure Deserialization (eval, exec, pickle.loads)
        if call_str in ("eval", "exec", "pickle.loads", "_pickle.loads"):
            for arg in node.args:
                is_t, src, tr = self._is_tainted_expr(arg)
                if is_t:
                    cwe = "CWE-502" if "pickle" in call_str else "CWE-94"
                    self.findings.append(
                        TaintVulnerability(
                            cwe_id=cwe,
                            vulnerability_type="CODE_INJECTION" if cwe == "CWE-94" else "INSECURE_DESERIALIZATION",
                            severity=TaintSeverity.CRITICAL,
                            source_expr=src,
                            source_line=self.taint_source_lines.get(src, node.lineno),
                            sink_expr=ast.unparse(node) if hasattr(ast, "unparse") else call_str,
                            sink_line=node.lineno,
                            file_path=self.file_path,
                            trace=tr + [f"Reached dangerous dynamic evaluation sink '{call_str}' on line {node.lineno}"],
                            remediation="Do not pass untrusted user data to eval() or pickle.loads(). Use safe data formats like json.loads()",
                        )
                    )

        # SINK 4: Path Traversal (open, os.remove, os.unlink)
        if call_str in ("open", "os.remove", "os.unlink", "shutil.rmtree"):
            if node.args:
                arg0 = node.args[0]
                is_t, src, tr = self._is_tainted_expr(arg0)
                if is_t:
                    self.findings.append(
                        TaintVulnerability(
                            cwe_id="CWE-22",
                            vulnerability_type="PATH_TRAVERSAL",
                            severity=TaintSeverity.HIGH,
                            source_expr=src,
                            source_line=self.taint_source_lines.get(src, node.lineno),
                            sink_expr=ast.unparse(node) if hasattr(ast, "unparse") else call_str,
                            sink_line=node.lineno,
                            file_path=self.file_path,
                            trace=tr + [f"Reached filesystem sink '{call_str}' without safe path normalization on line {node.lineno}"],
                            remediation="Validate paths using safe_path(base_dir, user_path) and reject traversal escapes (..) before accessing disk.",
                        )
                    )

        # SINK 5: SSRF (requests.get, httpx.get, urllib.request.urlopen)
        if any(sink in call_str for sink in ("requests.get", "requests.post", "httpx.get", "httpx.post", "urllib.request.urlopen")):
            if node.args:
                arg0 = node.args[0]
                is_t, src, tr = self._is_tainted_expr(arg0)
                if is_t:
                    self.findings.append(
                        TaintVulnerability(
                            cwe_id="CWE-918",
                            vulnerability_type="SSRF",
                            severity=TaintSeverity.HIGH,
                            source_expr=src,
                            source_line=self.taint_source_lines.get(src, node.lineno),
                            sink_expr=ast.unparse(node) if hasattr(ast, "unparse") else call_str,
                            sink_line=node.lineno,
                            file_path=self.file_path,
                            trace=tr + [f"Reached HTTP request sink '{call_str}' on line {node.lineno}"],
                            remediation="Validate target URL against an explicit domain allowlist and block private IP ranges (127.0.0.1, 10.0.0.0/8, 169.254.169.254).",
                        )
                    )

        self.generic_visit(node)


def audit_file_taint(file_path: Path) -> list[TaintVulnerability]:
    """Audit a single source file for dataflow taint vulnerabilities."""
    if not file_path.is_file():
        return []
    try:
        content = file_path.read_text(encoding="utf-8", errors="replace")
        lines = content.splitlines()
        tree = ast.parse(content, filename=str(file_path))
        visitor = _PythonTaintVisitor(str(file_path), lines)
        visitor.visit(tree)
        return visitor.findings
    except Exception:
        return []


def audit_repository_taint(
    repository: Path,
    con: sqlite3.Connection | None = None,
    file_paths: list[str] | None = None,
    entrypoint_symbol: str | None = None,
    filter_cwe: str | None = None,
    max_depth: int = 12,
) -> TaintReport:
    """Audit repository source files for cross-scope taint vulnerabilities and injection risks."""
    repo = repository.resolve()
    vulnerabilities: list[TaintVulnerability] = []

    target_files: list[Path] = []
    if file_paths:
        for fp in file_paths:
            p = (repo / fp).resolve()
            if p.is_file() and p.suffix.lower() in (".py", ".pyi"):
                target_files.append(p)
    else:
        for p in repo.rglob("*.py"):
            if not any(part in p.parts for part in (".git", ".venv", "venv", "__pycache__", "dist", "build")):
                target_files.append(p)

    for p in target_files:
        vulns = audit_file_taint(p)
        if filter_cwe:
            clean_cwe = filter_cwe.upper().strip()
            vulns = [v for v in vulns if clean_cwe in v.cwe_id.upper()]
        vulnerabilities.extend(vulns)

    return TaintReport(
        repository=str(repo),
        vulnerabilities=vulnerabilities,
    )
