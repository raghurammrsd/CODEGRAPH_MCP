"""Tests for dataflow taint-tracking and SAST security engine."""
from __future__ import annotations

from pathlib import Path

from codegraph.security.taint import (
    TaintSeverity,
    audit_file_taint,
    audit_repository_taint,
)


def test_detect_sql_injection_taint(tmp_path: Path) -> None:
    code = (
        "from flask import request\n"
        "import sqlite3\n\n"
        "def unsafe_endpoint():\n"
        "    user_id = request.args.get('id')\n"
        "    query = f'SELECT * FROM users WHERE id = {user_id}'\n"
        "    con = sqlite3.connect(':memory:')\n"
        "    con.execute(query)\n"
    )
    test_file = tmp_path / "app.py"
    test_file.write_text(code)

    findings = audit_file_taint(test_file)
    assert len(findings) >= 1
    f = [x for x in findings if x.vulnerability_type == "SQL_INJECTION"][0]
    assert f.cwe_id == "CWE-89"
    assert f.severity == TaintSeverity.CRITICAL
    assert "execute" in f.sink_expr
    assert len(f.trace) >= 2


def test_detect_command_injection_taint(tmp_path: Path) -> None:
    code = (
        "import subprocess\n"
        "from flask import request\n\n"
        "def unsafe_ping():\n"
        "    host = request.args.get('host')\n"
        "    cmd = 'ping -c 1 ' + host\n"
        "    subprocess.run(cmd, shell=True)\n"
    )
    test_file = tmp_path / "ping.py"
    test_file.write_text(code)

    findings = audit_file_taint(test_file)
    assert len(findings) >= 1
    f = [x for x in findings if x.vulnerability_type == "COMMAND_INJECTION"][0]
    assert f.cwe_id == "CWE-78"
    assert f.severity == TaintSeverity.CRITICAL


def test_detect_ssrf_and_path_traversal(tmp_path: Path) -> None:
    code = (
        "import requests\n"
        "from flask import request\n\n"
        "def proxy():\n"
        "    target_url = request.args.get('url')\n"
        "    file_name = request.args.get('file')\n"
        "    requests.get(target_url)\n"
        "    with open(file_name) as f:\n"
        "        pass\n"
    )
    test_file = tmp_path / "proxy.py"
    test_file.write_text(code)

    findings = audit_file_taint(test_file)
    types = {f.vulnerability_type for f in findings}
    assert "SSRF" in types
    assert "PATH_TRAVERSAL" in types


def test_clean_safe_code_has_no_findings(tmp_path: Path) -> None:
    code = (
        "import sqlite3\n\n"
        "def safe_query(user_id: int):\n"
        "    con = sqlite3.connect(':memory:')\n"
        "    con.execute('SELECT * FROM users WHERE id = ?', (user_id,))\n"
    )
    test_file = tmp_path / "safe.py"
    test_file.write_text(code)

    findings = audit_file_taint(test_file)
    assert len(findings) == 0


def test_audit_repository_taint(tmp_path: Path) -> None:
    (tmp_path / "vuln.py").write_text(
        "from flask import request\n"
        "import os\n"
        "def run():\n"
        "    os.system(request.args.get('cmd'))\n"
    )
    report = audit_repository_taint(tmp_path)
    assert report.total_vulnerabilities >= 1
    assert report.critical_count >= 1

    # Verify SARIF 2.1.0 structure
    sarif = report.to_sarif()
    assert sarif["version"] == "2.1.0"
    assert "https://json.schemastore.org/sarif-2.1.0.json" in sarif["$schema"]
    runs = sarif["runs"]
    assert len(runs) == 1
    driver = runs[0]["tool"]["driver"]
    assert driver["name"] == "CodeGraph SAST"
    assert len(driver["rules"]) >= 1
    assert driver["rules"][0]["id"] == "CWE-78"

    results = runs[0]["results"]
    assert len(results) >= 1
    assert results[0]["ruleId"] == "CWE-78"
    assert results[0]["level"] == "error"
    assert len(results[0]["codeFlows"]) == 1
