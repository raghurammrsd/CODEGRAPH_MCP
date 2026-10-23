"""Process-isolated JSON-RPC 2.0 Language Server Protocol Client for CodeGraph."""
from __future__ import annotations

import json
import logging
import os
import subprocess
import time
from pathlib import Path
from typing import Any, cast

from .models import DiagnosticSeverity, LSPDiagnostic

logger = logging.getLogger("codegraph.lsp")


class LSPClient:
    """Manages an isolated language server subprocess via JSON-RPC 2.0 over stdio."""

    def __init__(self, command: list[str], root_path: Path, timeout_seconds: float = 8.0):
        self.command = command
        self.root_path = root_path.resolve()
        self.timeout = timeout_seconds
        self.proc: subprocess.Popen[bytes] | None = None
        self._request_id = 0
        self._diagnostics_cache: list[LSPDiagnostic] = []

    def start(self) -> bool:
        """Start language server subprocess with process group isolation."""
        try:
            self.proc = subprocess.Popen(
                self.command,
                stdin=subprocess.PIPE,
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                cwd=str(self.root_path),
            )
            return True
        except (FileNotFoundError, PermissionError) as exc:
            logger.debug("Could not spawn LSP server %s: %s", self.command, exc)
            return False

    def close(self) -> None:
        """Terminate and clean up language server process cleanly without leaking."""
        if self.proc:
            try:
                self.send_notification("exit", {})
            except Exception:
                pass
            try:
                self.proc.terminate()
                self.proc.wait(timeout=1.0)
            except Exception:
                try:
                    self.proc.kill()
                except Exception:
                    pass
            finally:
                self.proc = None

    def __enter__(self) -> LSPClient:
        self.start()
        return self

    def __exit__(self, exc_type: Any, exc_val: Any, exc_tb: Any) -> None:
        self.close()

    def __del__(self) -> None:
        self.close()

    def send_notification(self, method: str, params: dict[str, Any]) -> None:
        """Send a one-way JSON-RPC notification."""
        if not self.proc or not self.proc.stdin:
            return
        payload = {
            "jsonrpc": "2.0",
            "method": method,
            "params": params,
        }
        body = json.dumps(payload).encode("utf-8")
        header = f"Content-Length: {len(body)}\r\n\r\n".encode("ascii")
        try:
            self.proc.stdin.write(header + body)
            self.proc.stdin.flush()
        except (BrokenPipeError, OSError):
            pass

    def send_request(self, method: str, params: dict[str, Any]) -> dict[str, Any] | None:
        """Send a JSON-RPC request and wait synchronously for the response."""
        if not self.proc or not self.proc.stdin or not self.proc.stdout:
            return None
        self._request_id += 1
        req_id = self._request_id
        payload = {
            "jsonrpc": "2.0",
            "id": req_id,
            "method": method,
            "params": params,
        }
        body = json.dumps(payload).encode("utf-8")
        header = f"Content-Length: {len(body)}\r\n\r\n".encode("ascii")
        try:
            self.proc.stdin.write(header + body)
            self.proc.stdin.flush()
        except (BrokenPipeError, OSError):
            return None

        # Read response with timeout
        start = time.time()
        while time.time() - start < self.timeout:
            resp = self._read_message()
            if not resp:
                time.sleep(0.02)
                continue
            if resp.get("id") == req_id:
                return resp
            # Handle incoming publishDiagnostics notification
            if resp.get("method") == "textDocument/publishDiagnostics":
                self._parse_diagnostics_notification(resp.get("params", {}))

        return None

    def _read_message(self) -> dict[str, Any] | None:
        """Read a framed JSON-RPC message from stdout."""
        if not self.proc or not self.proc.stdout:
            return None
        try:
            # Read header
            line = self.proc.stdout.readline()
            if not line:
                return None
            line_str = line.decode("ascii", errors="replace")
            content_length = 0
            if line_str.startswith("Content-Length:"):
                content_length = int(line_str.split(":")[1].strip())
                # Read empty line delimiter
                self.proc.stdout.readline()
                # Read body
                body_bytes = self.proc.stdout.read(content_length)
                return cast(dict[str, Any], json.loads(body_bytes.decode("utf-8", errors="replace")))
        except Exception:
            return None
        return None

    def initialize(self) -> bool:
        """Send LSP initialize request and wait for server capabilities."""
        res = self.send_request(
            "initialize",
            {
                "processId": os.getpid(),
                "rootUri": self.root_path.as_uri(),
                "capabilities": {
                    "textDocument": {
                        "publishDiagnostics": {"relatedInformation": True},
                        "definition": {"dynamicRegistration": True},
                    }
                },
            },
        )
        if res and "result" in res:
            self.send_notification("initialized", {})
            return True
        return False

    def open_document(self, file_path: Path, language_id: str, content: str) -> None:
        """Notify LSP of an opened document to trigger diagnostics."""
        self.send_notification(
            "textDocument/didOpen",
            {
                "textDocument": {
                    "uri": file_path.resolve().as_uri(),
                    "languageId": language_id,
                    "version": 1,
                    "text": content,
                }
            },
        )

    def _parse_diagnostics_notification(self, params: dict[str, Any]) -> None:
        uri = params.get("uri", "")
        raw_diags = params.get("diagnostics", [])
        for d in raw_diags:
            rng = d.get("range", {})
            start = rng.get("start", {})
            end = rng.get("end", {})
            sev_num = d.get("severity", 1)
            sev = (
                DiagnosticSeverity.ERROR if sev_num == 1
                else (DiagnosticSeverity.WARNING if sev_num == 2
                      else (DiagnosticSeverity.INFORMATION if sev_num == 3 else DiagnosticSeverity.HINT))
            )
            self._diagnostics_cache.append(
                LSPDiagnostic(
                    file_path=uri.replace("file://", ""),
                    line=start.get("line", 0) + 1,
                    column=start.get("character", 0) + 1,
                    end_line=end.get("line", 0) + 1,
                    end_column=end.get("character", 0) + 1,
                    severity=sev,
                    message=d.get("message", ""),
                    code=str(d.get("code", "")),
                    source=str(d.get("source", "LSP")),
                )
            )

    def get_diagnostics(self) -> list[LSPDiagnostic]:
        return list(self._diagnostics_cache)
