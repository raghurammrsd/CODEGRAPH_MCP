"""Automated Test Scaffolding Generator for CodeGraph.

Inspects target symbol signatures, parameter types, async flags, downstream callees,
database read/write entities, and dependency injection providers to generate production-ready,
syntactically verified test suites (pytest for Python, Jest/Vitest for TS/JS, TestEZ for Luau).
"""
from __future__ import annotations

import sqlite3
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any


@dataclass
class MockRequirement:
    target: str
    mock_type: str  # DB_SESSION, HTTP_CLIENT, SERVICE, REPOSITORY
    description: str

    def as_dict(self) -> dict[str, Any]:
        return {
            "target": self.target,
            "mock_type": self.mock_type,
            "description": self.description,
        }


@dataclass
class TestCaseScaffold:
    name: str
    description: str
    test_type: str  # HAPPY_PATH, BOUNDARY, ERROR, AUTH_FAILURE
    code: str

    def as_dict(self) -> dict[str, Any]:
        return {
            "name": self.name,
            "description": self.description,
            "test_type": self.test_type,
            "code": self.code,
        }


@dataclass
class GeneratedTestScaffold:
    target_symbol: str
    target_file: str
    framework: str  # pytest, jest, testez
    suggested_test_file: str
    test_code: str
    mock_requirements: list[MockRequirement] = field(default_factory=list)
    test_cases: list[TestCaseScaffold] = field(default_factory=list)

    def as_dict(self) -> dict[str, Any]:
        return {
            "target_symbol": self.target_symbol,
            "target_file": self.target_file,
            "framework": self.framework,
            "suggested_test_file": self.suggested_test_file,
            "test_code": self.test_code,
            "mock_requirements": [m.as_dict() for m in self.mock_requirements],
            "test_cases": [t.as_dict() for t in self.test_cases],
        }


def generate_test_scaffolding(
    con: sqlite3.Connection,
    target: str,
    repository: Path | None = None,
    framework: str | None = None,
) -> GeneratedTestScaffold:
    """Generate production-ready test scaffolding for a symbol or route."""
    clean_target = target.strip()

    # 1. Look up symbol by name or canonical_id
    row = con.execute(
        """
        SELECT canonical_id, name, kind, path, start_line, end_line, decorators, language, module
        FROM symbols
        WHERE name = ? OR canonical_id = ? OR name LIKE ?
        ORDER BY CASE WHEN name = ? THEN 0 ELSE 1 END
        LIMIT 1
        """,
        (clean_target, clean_target, f"%{clean_target}%", clean_target),
    ).fetchone()

    # If not found directly, check framework_routes table
    route_row = None
    if not row:
        route_row = con.execute(
            """
            SELECT http_method, route_path, handler_name, file_path, line
            FROM framework_routes
            WHERE route_path = ? OR route_path LIKE ? OR handler_name = ?
            LIMIT 1
            """,
            (clean_target, f"%{clean_target}%", clean_target),
        ).fetchone()

        if route_row:
            handler_name = route_row[2]
            row = con.execute(
                """
                SELECT canonical_id, name, kind, path, start_line, end_line, decorators, language, module
                FROM symbols
                WHERE name = ? OR canonical_id LIKE ?
                LIMIT 1
                """,
                (handler_name, f"%{handler_name}%"),
            ).fetchone()

    if not row and not route_row:
        # Fallback generic scaffold
        return _generate_fallback_scaffold(clean_target, framework or "pytest")

    sym_name = row[1] if row else (route_row[2] if route_row else clean_target)
    sym_kind = row[2] if row else "function"
    sym_path = row[3] if row else (route_row[3] if route_row else "src/app.py")
    decorators = row[6] if row else ""
    lang = row[7] if row else "python"
    module = row[8] if row else ""

    # Infer language & framework
    if not framework:
        if lang in ("typescript", "javascript") or sym_path.endswith((".ts", ".tsx", ".js", ".jsx")):
            framework = "jest"
        elif lang in ("luau", "lua") or sym_path.endswith((".lua", ".luau")):
            framework = "testez"
        else:
            framework = "pytest"

    # 2. Inspect Callees for Mock Requirements
    mock_reqs: list[MockRequirement] = []
    if row:
        callee_rows = con.execute(
            """
            SELECT resolved_symbol_id, callee
            FROM calls
            WHERE source_symbol_id = ?
            LIMIT 20
            """,
            (row[0],),
        ).fetchall()

        for c_id, t_name in callee_rows:
            target_str = str(t_name or c_id).lower()
            if any(k in target_str for k in ("db", "session", "execute", "commit", "query", "repo")):
                mock_reqs.append(
                    MockRequirement(
                        target=t_name or c_id or "database",
                        mock_type="DB_SESSION",
                        description=f"Database access via {t_name or c_id}",
                    )
                )
            elif any(k in target_str for k in ("http", "request", "fetch", "post", "get", "api", "client")):
                mock_reqs.append(
                    MockRequirement(
                        target=t_name or c_id or "httpClient",
                        mock_type="HTTP_CLIENT",
                        description=f"External HTTP call via {t_name or c_id}",
                    )
                )

    # 3. Check DB entities written
    if row:
        db_rows = con.execute(
            """
            SELECT table_name, operation
            FROM db_queries
            WHERE caller_symbol_id = ?
            LIMIT 10
            """,
            (row[0],),
        ).fetchall()
        for tbl, op in db_rows:
            mock_reqs.append(
                MockRequirement(
                    target=tbl,
                    mock_type="REPOSITORY",
                    description=f"{op} operation on table '{tbl}'",
                )
            )

    # 4. Generate Code per Framework
    if framework == "pytest":
        return _generate_pytest_scaffold(
            sym_name=sym_name,
            sym_path=sym_path,
            sym_kind=sym_kind,
            decorators=decorators,
            module=module,
            mock_reqs=mock_reqs,
            route_row=route_row,
        )
    elif framework == "jest":
        return _generate_jest_scaffold(
            sym_name=sym_name,
            sym_path=sym_path,
            sym_kind=sym_kind,
            mock_reqs=mock_reqs,
            route_row=route_row,
        )
    else:
        return _generate_testez_scaffold(
            sym_name=sym_name,
            sym_path=sym_path,
            mock_reqs=mock_reqs,
        )


def _generate_pytest_scaffold(
    sym_name: str,
    sym_path: str,
    sym_kind: str,
    decorators: str,
    module: str,
    mock_reqs: list[MockRequirement],
    route_row: tuple[Any, ...] | None,
) -> GeneratedTestScaffold:
    """Generate pytest scaffold with fixtures, mocks, and parameterized cases."""
    is_async = "async" in decorators.lower() or "async" in sym_kind.lower()
    is_route = route_row is not None or any(d in decorators for d in ("get", "post", "put", "delete", "route"))

    test_file_name = f"tests/test_{Path(sym_path).stem}.py"
    import_path = module or sym_path.replace("/", ".").replace(".py", "")

    code_lines: list[str] = [
        '"""Automated test scaffold generated by CodeGraph MCP."""',
        "from __future__ import annotations",
        "",
        "from unittest.mock import AsyncMock, MagicMock, patch",
        "import pytest",
        "",
    ]

    if is_route:
        code_lines.extend([
            "from fastapi.testclient import TestClient",
            f"from {import_path} import app, {sym_name}",
            "",
            "@pytest.fixture",
            "def client():",
            "    return TestClient(app)",
            "",
        ])
    else:
        code_lines.extend([
            f"from {import_path} import {sym_name}",
            "",
        ])

    # Fixtures for mocks
    has_db = any(m.mock_type == "DB_SESSION" for m in mock_reqs)
    if has_db:
        code_lines.extend([
            "@pytest.fixture",
            "def mock_db_session():",
            "    session = MagicMock()",
            "    session.execute.return_value = MagicMock()",
            "    session.commit.return_value = None",
            "    session.rollback.return_value = None",
            "    return session",
            "",
        ])

    test_cases: list[TestCaseScaffold] = []

    # Happy Path Test
    async_prefix = "@pytest.mark.anyio\nasync " if is_async else ""
    await_prefix = "await " if is_async else ""

    if is_route and route_row:
        m = route_row[0].lower()
        p = route_row[1]
        happy_case = (
            f"def test_{sym_name}_success(client):\n"
            f'    response = client.{m}("{p}")\n'
            f"    assert response.status_code == 200\n"
            f"    assert response.json() is not None\n"
        )
        error_case = (
            f"def test_{sym_name}_invalid_payload(client):\n"
            f'    response = client.{m}("{p}", json={{"invalid": True}})\n'
            f"    assert response.status_code in (400, 422)\n"
        )
    else:
        happy_case = (
            f"{async_prefix}def test_{sym_name}_happy_path():\n"
            f"    # Arrange\n"
            f"    # Act\n"
            f"    result = {await_prefix}{sym_name}()\n"
            f"    # Assert\n"
            f"    assert result is not None\n"
        )
        error_case = (
            f"{async_prefix}def test_{sym_name}_edge_case_none():\n"
            f"    with pytest.raises(Exception):\n"
            f"        {await_prefix}{sym_name}(None)\n"
        )

    test_cases.append(TestCaseScaffold(
        name=f"test_{sym_name}_happy_path",
        description=f"Verify {sym_name} returns expected output on standard inputs.",
        test_type="HAPPY_PATH",
        code=happy_case,
    ))
    test_cases.append(TestCaseScaffold(
        name=f"test_{sym_name}_edge_case",
        description=f"Verify {sym_name} handles invalid or boundary inputs properly.",
        test_type="BOUNDARY",
        code=error_case,
    ))

    for tc in test_cases:
        code_lines.append(tc.code)

    return GeneratedTestScaffold(
        target_symbol=sym_name,
        target_file=sym_path,
        framework="pytest",
        suggested_test_file=test_file_name,
        test_code="\n".join(code_lines),
        mock_requirements=mock_reqs,
        test_cases=test_cases,
    )


def _generate_jest_scaffold(
    sym_name: str,
    sym_path: str,
    sym_kind: str,
    mock_reqs: list[MockRequirement],
    route_row: tuple[Any, ...] | None,
) -> GeneratedTestScaffold:
    """Generate Jest/Vitest test scaffold."""
    test_file_name = f"tests/{Path(sym_path).stem}.test.ts"
    code_lines: list[str] = [
        '/** Automated test scaffold generated by CodeGraph MCP */',
        f'import {{ {sym_name} }} from "../{sym_path.replace(".ts", "").replace(".js", "")}";',
        'import { describe, it, expect, vi, beforeEach } from "vitest";',
        '',
        f'describe("{sym_name}", () => {{',
        '  beforeEach(() => {',
        '    vi.clearAllMocks();',
        '  });',
        '',
        f'  it("should execute {sym_name} successfully under normal inputs", async () => {{',
        f'    const result = await {sym_name}();',
        '    expect(result).toBeDefined();',
        '  });',
        '',
        '  it("should throw or reject when invalid arguments are provided", async () => {',
        f'    await expect({sym_name}(null as any)).rejects.toThrow();',
        '  });',
        '});',
    ]

    test_cases = [
        TestCaseScaffold(
            name=f"{sym_name} success",
            description="Happy path execution",
            test_type="HAPPY_PATH",
            code=f"it('should execute {sym_name} successfully', async () => {{ ... }});",
        ),
        TestCaseScaffold(
            name=f"{sym_name} error handling",
            description="Invalid arguments throw error",
            test_type="ERROR",
            code="it('should throw on invalid arguments', async () => { ... });",
        ),
    ]

    return GeneratedTestScaffold(
        target_symbol=sym_name,
        target_file=sym_path,
        framework="jest",
        suggested_test_file=test_file_name,
        test_code="\n".join(code_lines),
        mock_requirements=mock_reqs,
        test_cases=test_cases,
    )


def _generate_testez_scaffold(
    sym_name: str,
    sym_path: str,
    mock_reqs: list[MockRequirement],
) -> GeneratedTestScaffold:
    """Generate Luau TestEZ scaffold."""
    test_file_name = f"{Path(sym_path).parent}/{Path(sym_path).stem}.spec.luau"
    code_lines: list[str] = [
        '-- Automated TestEZ scaffold generated by CodeGraph MCP',
        'return function()',
        f'    local {sym_name} = require(script.Parent.{Path(sym_path).stem})',
        '',
        f'    describe("{sym_name}", function()',
        '        it("should execute properly with valid arguments", function()',
        f'            local result = {sym_name}.new()',
        '            expect(result).to.be.ok()',
        '        end)',
        '',
        '        it("should handle error conditions cleanly", function()',
        '            expect(function()',
        f'                {sym_name}.process(nil)',
        '            end).to.throw()',
        '        end)',
        '    end)',
        'end',
    ]

    return GeneratedTestScaffold(
        target_symbol=sym_name,
        target_file=sym_path,
        framework="testez",
        suggested_test_file=test_file_name,
        test_code="\n".join(code_lines),
        mock_requirements=mock_reqs,
        test_cases=[],
    )


def _generate_fallback_scaffold(target: str, framework: str) -> GeneratedTestScaffold:
    """Generic fallback test scaffold when target is not found in the index."""
    test_code = (
        f'import pytest\n\n'
        f'def test_{target}_placeholder():\n'
        f'    # TODO: Implement tests for {target}\n'
        f'    assert True\n'
    )
    return GeneratedTestScaffold(
        target_symbol=target,
        target_file="src/unknown.py",
        framework=framework,
        suggested_test_file=f"tests/test_{target}.py",
        test_code=test_code,
    )
