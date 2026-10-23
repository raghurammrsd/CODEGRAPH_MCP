"""Lightweight, Privacy-Safe OpenTelemetry (OTLP) HTTP Receiver.

Listens for standard OpenTelemetry Protocol (OTLP/HTTP) trace exports
(POST /v1/traces) and streams normalized, redacted observations directly
into `.codegraph.sqlite3` runtime tables.

Invariants:
1. Zero third-party runtime dependencies: built entirely on standard library asyncio.
2. Complies with OTLP/HTTP 1.0 JSON trace export specification.
3. Full CORS support (Access-Control-Allow-Origin: *) for browser/SPA OpenTelemetry SDKs.
4. Redacts secrets, headers, and SQL bound parameters in real-time before SQLite persistence.
5. Handles optional gzip compression automatically.
"""
from __future__ import annotations

import asyncio
import gzip
import json
import sqlite3
from collections.abc import Callable
from pathlib import Path
from typing import Any

from codegraph.runtime.ingestor import ingest_runtime_traces


class OTLPReceiver:
    """Embedded asyncio HTTP server receiving OTLP /v1/traces payloads."""

    def __init__(
        self,
        db_path: Path | str,
        host: str = "127.0.0.1",
        port: int = 4318,
        on_batch: Callable[[dict[str, Any]], None] | None = None,
    ) -> None:
        self.db_path = Path(db_path)
        self.host = host
        self.port = port
        self.on_batch = on_batch
        self.server: asyncio.Server | None = None
        self._is_running = False
        self.total_spans_received = 0
        self.total_batches_received = 0

    async def start(self) -> None:
        """Start listening for incoming OTLP HTTP requests."""
        self.server = await asyncio.start_server(
            self._handle_client,
            self.host,
            self.port,
        )
        self._is_running = True

    async def stop(self) -> None:
        """Gracefully terminate the OTLP server."""
        self._is_running = False
        if self.server:
            self.server.close()
            await self.server.wait_closed()
            self.server = None

    async def _handle_client(
        self,
        reader: asyncio.StreamReader,
        writer: asyncio.StreamWriter,
    ) -> None:
        try:
            # Read HTTP request line
            line = await reader.readline()
            if not line:
                writer.close()
                await writer.wait_closed()
                return

            req_line = line.decode("utf-8", errors="replace").strip()
            parts = req_line.split()
            if len(parts) < 2:
                self._send_response(writer, 400, "Bad Request")
                return

            method, path = parts[0].upper(), parts[1]

            # Read headers
            headers: dict[str, str] = {}
            while True:
                header_line = await reader.readline()
                if not header_line or header_line in (b"\r\n", b"\n"):
                    break
                header_text = header_line.decode("utf-8", errors="replace").strip()
                if ":" in header_text:
                    k, v = header_text.split(":", 1)
                    headers[k.strip().lower()] = v.strip()

            # Handle CORS preflight
            if method == "OPTIONS":
                self._send_cors_response(writer)
                return

            # Read body
            content_length = int(headers.get("content-length", 0))
            body = b""
            if content_length > 0:
                body = await reader.readexactly(content_length)

            if method == "POST" and ("/v1/traces" in path or path == "/"):
                # Handle gzip if present
                if headers.get("content-encoding") == "gzip":
                    try:
                        body = gzip.decompress(body)
                    except Exception:
                        self._send_response(writer, 400, "Invalid gzip body")
                        return

                try:
                    payload = json.loads(body.decode("utf-8"))
                except Exception:
                    self._send_response(writer, 400, "Invalid JSON payload")
                    return

                # Ingest into SQLite
                result = self._persist_batch(payload)
                self.total_batches_received += 1
                self.total_spans_received += result.get("ingested_events", 0)

                if self.on_batch:
                    try:
                        self.on_batch(result)
                    except Exception:
                        pass

                # Return standard OTLP JSON success response
                resp_payload = json.dumps({"partialSuccess": {}}).encode("utf-8")
                self._send_response(
                    writer,
                    200,
                    "OK",
                    body=resp_payload,
                    content_type="application/json",
                )
            else:
                self._send_response(writer, 404, "Not Found")

        except Exception as exc:
            try:
                self._send_response(writer, 500, f"Internal Error: {exc}")
            except Exception:
                pass
        finally:
            try:
                writer.close()
                await writer.wait_closed()
            except Exception:
                pass

    def _persist_batch(self, payload: dict[str, Any]) -> dict[str, Any]:
        """Ingest OTLP batch into SQLite database with thread-safe connection."""
        con = sqlite3.connect(str(self.db_path), timeout=10.0)
        con.row_factory = sqlite3.Row
        try:
            con.execute("PRAGMA journal_mode = WAL")
            con.execute("PRAGMA busy_timeout = 5000")
            result = ingest_runtime_traces(con, data_or_path=payload, format="otel")
            con.commit()
            return result
        finally:
            con.close()

    def _send_response(
        self,
        writer: asyncio.StreamWriter,
        status_code: int,
        status_text: str,
        body: bytes = b"",
        content_type: str = "text/plain",
    ) -> None:
        response = (
            f"HTTP/1.1 {status_code} {status_text}\r\n"
            f"Content-Type: {content_type}\r\n"
            f"Content-Length: {len(body)}\r\n"
            "Access-Control-Allow-Origin: *\r\n"
            "Access-Control-Allow-Headers: *\r\n"
            "Connection: close\r\n\r\n"
        ).encode() + body
        writer.write(response)

    def _send_cors_response(self, writer: asyncio.StreamWriter) -> None:
        response = (
            b"HTTP/1.1 204 No Content\r\n"
            b"Access-Control-Allow-Origin: *\r\n"
            b"Access-Control-Allow-Methods: POST, OPTIONS\r\n"
            b"Access-Control-Allow-Headers: *\r\n"
            b"Access-Control-Max-Age: 86400\r\n"
            b"Connection: close\r\n\r\n"
        )
        writer.write(response)


async def run_otel_listener(
    db_path: Path | str,
    host: str = "127.0.0.1",
    port: int = 4318,
    on_batch: Callable[[dict[str, Any]], None] | None = None,
) -> OTLPReceiver:
    """Start an asynchronous OTLP receiver instance."""
    receiver = OTLPReceiver(db_path, host=host, port=port, on_batch=on_batch)
    await receiver.start()
    return receiver
