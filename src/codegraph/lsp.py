"""Language Server Protocol (LSP) Bridge for CodeGraph MCP.

Exposes CodeGraph's deterministic, SQLite-backed repository graph as a
standard Language Server Protocol server (JSON-RPC 2.0 over stdio).

Capabilities:
- `textDocument/definition`: Jump to definition across Python, TypeScript, and Luau.
- `textDocument/references`: Find all verified AST callers and references across the repository.
- `textDocument/codeLens`: Display live caller counts (e.g. `▲ 4 callers`) and remote links above functions.
- `textDocument/documentSymbol`: Outline symbols in the current file.
"""
from __future__ import annotations

import io
import json
import sys
import urllib.parse
from pathlib import Path
from typing import Any

from codegraph.indexing.indexer import Indexer


def uri_to_path(uri: str) -> Path:
    """Convert file:// URI to Path."""
    parsed = urllib.parse.urlparse(uri)
    if parsed.scheme == "file":
        path_str = urllib.parse.unquote(parsed.path)
        # Handle Windows drive letters like /C:/path
        if sys.platform == "win32" and path_str.startswith("/") and len(path_str) > 2 and path_str[2] == ":":
            path_str = path_str[1:]
        return Path(path_str)
    return Path(uri)


def path_to_uri(path: Path | str) -> str:
    """Convert Path to file:// URI."""
    p = Path(path).resolve()
    return p.as_uri()


class LSPServer:
    """Lightweight stdio JSON-RPC Language Server Protocol handler."""

    def __init__(self, repository: Path) -> None:
        self.repository = repository.resolve()
        self.indexer = Indexer(self.repository)

    def handle_request(self, method: str, params: dict[str, Any]) -> Any:
        """Dispatch JSON-RPC request to internal handler."""
        if method == "initialize":
            return self._handle_initialize(params)
        elif method == "textDocument/definition":
            return self._handle_definition(params)
        elif method == "textDocument/references":
            return self._handle_references(params)
        elif method == "textDocument/codeLens":
            return self._handle_codelens(params)
        elif method == "textDocument/documentSymbol":
            return self._handle_document_symbol(params)
        elif method == "shutdown":
            return None
        return None

    def _handle_initialize(self, params: dict[str, Any]) -> dict[str, Any]:
        return {
            "capabilities": {
                "definitionProvider": True,
                "referencesProvider": True,
                "codeLensProvider": {
                    "resolveProvider": False,
                },
                "documentSymbolProvider": True,
            },
            "serverInfo": {
                "name": "codegraph-lsp",
                "version": "3.0.0",
            },
        }

    def _handle_definition(self, params: dict[str, Any]) -> list[dict[str, Any]]:
        text_doc = params.get("textDocument", {})
        pos = params.get("position", {})
        uri = text_doc.get("uri", "")
        line_0 = pos.get("line", 0)
        target_line = line_0 + 1

        file_path = str(uri_to_path(uri).relative_to(self.repository)).replace("\\", "/")

        with self.indexer.session() as con:
            # Check if this line makes a call or reference
            row = con.execute(
                """
                SELECT target, relationship FROM graph_edges
                WHERE file = ? AND start_line <= ? AND end_line >= ?
                LIMIT 1
                """,
                (file_path, target_line, target_line),
            ).fetchone()

            if not row:
                return []

            target_sym = row[0]

            # Find target symbol definition
            target_def = con.execute(
                """
                SELECT path, start_line, end_line
                FROM symbols
                WHERE canonical_id = ? OR name = ?
                LIMIT 1
                """,
                (target_sym, target_sym.split(".")[-1]),
            ).fetchone()

            if not target_def:
                return []

            def_path = self.repository / target_def[0]
            start_l = max(0, int(target_def[1]) - 1)
            end_l = max(0, int(target_def[2]) - 1)

            return [
                {
                    "uri": path_to_uri(def_path),
                    "range": {
                        "start": {"line": start_l, "character": 0},
                        "end": {"line": end_l, "character": 0},
                    },
                }
            ]

    def _handle_references(self, params: dict[str, Any]) -> list[dict[str, Any]]:
        text_doc = params.get("textDocument", {})
        pos = params.get("position", {})
        uri = text_doc.get("uri", "")
        line_0 = pos.get("line", 0)
        target_line = line_0 + 1

        file_path = str(uri_to_path(uri).relative_to(self.repository)).replace("\\", "/")

        with self.indexer.session() as con:
            # Find symbol defined or located at position
            sym_row = con.execute(
                """
                SELECT canonical_id, name FROM symbols
                WHERE path = ? AND start_line <= ? AND end_line >= ?
                ORDER BY start_line DESC
                LIMIT 1
                """,
                (file_path, target_line, target_line),
            ).fetchone()

            if not sym_row:
                return []

            can_id, name = sym_row[0], sym_row[1]

            # Find all callers and references
            edges = con.execute(
                """
                SELECT DISTINCT file, start_line, end_line FROM graph_edges
                WHERE (target = ? OR target = ?)
                  AND relationship IN ('CALLS', 'INSTANTIATES', 'IMPORTS', 'REFERENCES')
                ORDER BY file, start_line
                LIMIT 50
                """,
                (can_id, name),
            ).fetchall()

            locations: list[dict[str, Any]] = []
            for f, sl, el in edges:
                loc_path = self.repository / f
                locations.append(
                    {
                        "uri": path_to_uri(loc_path),
                        "range": {
                            "start": {"line": max(0, int(sl) - 1), "character": 0},
                            "end": {"line": max(0, int(el) - 1), "character": 0},
                        },
                    }
                )
            return locations

    def _handle_codelens(self, params: dict[str, Any]) -> list[dict[str, Any]]:
        text_doc = params.get("textDocument", {})
        uri = text_doc.get("uri", "")
        file_path = str(uri_to_path(uri).relative_to(self.repository)).replace("\\", "/")

        with self.indexer.session() as con:
            symbols = con.execute(
                """
                SELECT name, canonical_id, kind, start_line, end_line
                FROM symbols
                WHERE path = ? AND kind IN ('function', 'method', 'class')
                """,
                (file_path,),
            ).fetchall()

            lenses: list[dict[str, Any]] = []
            for name, can_id, _kind, start_line, _end_line in symbols:
                # Count callers
                caller_count = con.execute(
                    """
                    SELECT COUNT(DISTINCT source) FROM graph_edges
                    WHERE (target = ? OR target = ?)
                      AND relationship IN ('CALLS', 'INSTANTIATES')
                    """,
                    (can_id, name),
                ).fetchone()[0]

                line_0 = max(0, int(start_line) - 1)
                lenses.append(
                    {
                        "range": {
                            "start": {"line": line_0, "character": 0},
                            "end": {"line": line_0, "character": 0},
                        },
                        "command": {
                            "title": f"▲ {caller_count} callers",
                            "command": "codegraph.showReferences",
                            "arguments": [uri, {"line": line_0, "character": 0}],
                        },
                    }
                )
            return lenses

    def _handle_document_symbol(self, params: dict[str, Any]) -> list[dict[str, Any]]:
        text_doc = params.get("textDocument", {})
        uri = text_doc.get("uri", "")
        file_path = str(uri_to_path(uri).relative_to(self.repository)).replace("\\", "/")

        with self.indexer.session() as con:
            rows = con.execute(
                """
                SELECT name, kind, start_line, end_line
                FROM symbols
                WHERE path = ?
                """,
                (file_path,),
            ).fetchall()

            kind_mapping = {
                "function": 12,
                "method": 6,
                "class": 5,
                "variable": 13,
            }

            symbols: list[dict[str, Any]] = []
            for name, kind, sl, el in rows:
                start_l = max(0, int(sl) - 1)
                end_l = max(0, int(el) - 1)
                symbols.append(
                    {
                        "name": name,
                        "kind": kind_mapping.get(kind.lower(), 12),
                        "range": {
                            "start": {"line": start_l, "character": 0},
                            "end": {"line": end_l, "character": 0},
                        },
                        "selectionRange": {
                            "start": {"line": start_l, "character": 0},
                            "end": {"line": start_l, "character": len(name)},
                        },
                    }
                )
            return symbols


def run_stdio_lsp_server(repository: Path, input_stream: io.BufferedReader | None = None, output_stream: io.BufferedWriter | None = None) -> None:
    """Run JSON-RPC 2.0 LSP server over stdio streams."""
    server = LSPServer(repository)
    r = input_stream or sys.stdin.buffer
    w = output_stream or sys.stdout.buffer

    while True:
        # Read Content-Length header
        content_length = 0
        while True:
            line = r.readline()
            if not line:
                return
            line_str = line.decode("ascii", errors="replace").strip()
            if not line_str:
                break
            if line_str.lower().startswith("content-length:"):
                content_length = int(line_str.split(":", 1)[1].strip())

        if content_length <= 0:
            continue

        body_bytes = r.read(content_length)
        if not body_bytes:
            break

        try:
            req = json.loads(body_bytes.decode("utf-8"))
        except Exception:
            continue

        req_id = req.get("id")
        method = req.get("method", "")
        params = req.get("params", {})

        result = server.handle_request(method, params)

        if req_id is not None:
            resp = {
                "jsonrpc": "2.0",
                "id": req_id,
                "result": result,
            }
            resp_bytes = json.dumps(resp).encode("utf-8")
            header = f"Content-Length: {len(resp_bytes)}\r\n\r\n".encode("ascii")
            w.write(header + resp_bytes)
            w.flush()
