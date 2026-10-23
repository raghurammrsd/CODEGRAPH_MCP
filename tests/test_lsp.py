"""Comprehensive test suite for CodeGraph Language Server Protocol (LSP) Bridge."""
from __future__ import annotations

import io
import json
from pathlib import Path

import pytest

from codegraph.indexing.indexer import Indexer
from codegraph.lsp import LSPServer, path_to_uri, run_stdio_lsp_server, uri_to_path


@pytest.fixture
def lsp_repo(tmp_path: Path) -> Path:
    repo = tmp_path / "lsp_repo"
    repo.mkdir()

    # Create caller and callee
    (repo / "calc.py").write_text(
        "def compute_tax(amount: float) -> float:\n"
        "    return amount * 0.2\n\n"
        "def process_invoice(amount: float) -> float:\n"
        "    tax = compute_tax(amount)\n"
        "    return amount + tax\n",
        encoding="utf-8",
    )

    indexer = Indexer(repo)
    indexer.index()
    return repo


def test_uri_path_conversions(tmp_path: Path) -> None:
    uri = path_to_uri(tmp_path)
    assert uri.startswith("file://")
    p = uri_to_path(uri)
    assert p.resolve() == tmp_path.resolve()


def test_lsp_initialize(lsp_repo: Path) -> None:
    server = LSPServer(lsp_repo)
    resp = server.handle_request("initialize", {})
    assert "capabilities" in resp
    caps = resp["capabilities"]
    assert caps["definitionProvider"] is True
    assert caps["referencesProvider"] is True
    assert caps["codeLensProvider"]["resolveProvider"] is False
    assert caps["documentSymbolProvider"] is True


def test_lsp_definition_and_references(lsp_repo: Path) -> None:
    server = LSPServer(lsp_repo)
    calc_path = lsp_repo / "calc.py"
    uri = path_to_uri(calc_path)

    # Line 4 (process_invoice calling compute_tax)
    def_resp = server.handle_request(
        "textDocument/definition",
        {
            "textDocument": {"uri": uri},
            "position": {"line": 4, "character": 12},
        },
    )
    assert len(def_resp) >= 1
    assert def_resp[0]["uri"] == uri

    # Find references for compute_tax (line 0)
    ref_resp = server.handle_request(
        "textDocument/references",
        {
            "textDocument": {"uri": uri},
            "position": {"line": 0, "character": 4},
        },
    )
    assert len(ref_resp) >= 1
    assert any(loc["uri"] == uri for loc in ref_resp)


def test_lsp_codelens_and_document_symbol(lsp_repo: Path) -> None:
    server = LSPServer(lsp_repo)
    calc_path = lsp_repo / "calc.py"
    uri = path_to_uri(calc_path)

    # Test CodeLens
    lens_resp = server.handle_request(
        "textDocument/codeLens",
        {"textDocument": {"uri": uri}},
    )
    assert len(lens_resp) >= 2
    titles = [item["command"]["title"] for item in lens_resp]
    assert any("caller" in t for t in titles)

    # Test Document Symbols
    sym_resp = server.handle_request(
        "textDocument/documentSymbol",
        {"textDocument": {"uri": uri}},
    )
    assert len(sym_resp) >= 2
    names = {s["name"] for s in sym_resp}
    assert "compute_tax" in names
    assert "process_invoice" in names


def test_stdio_lsp_server_stream(lsp_repo: Path) -> None:
    """Test full JSON-RPC 2.0 message parsing over byte streams."""
    calc_path = lsp_repo / "calc.py"
    uri = path_to_uri(calc_path)

    req_init = {
        "jsonrpc": "2.0",
        "id": 1,
        "method": "initialize",
        "params": {},
    }
    req_lens = {
        "jsonrpc": "2.0",
        "id": 2,
        "method": "textDocument/codeLens",
        "params": {"textDocument": {"uri": uri}},
    }

    body1 = json.dumps(req_init).encode("utf-8")
    body2 = json.dumps(req_lens).encode("utf-8")

    stream_in = io.BytesIO(
        f"Content-Length: {len(body1)}\r\n\r\n".encode("ascii") + body1 +
        f"Content-Length: {len(body2)}\r\n\r\n".encode("ascii") + body2
    )
    stream_out = io.BytesIO()

    run_stdio_lsp_server(lsp_repo, input_stream=stream_in, output_stream=stream_out)

    out_bytes = stream_out.getvalue()
    assert b"jsonrpc" in out_bytes
    assert b"capabilities" in out_bytes
    assert b"callers" in out_bytes
