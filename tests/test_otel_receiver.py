"""Comprehensive test suite for CodeGraph OTLP HTTP Receiver."""
from __future__ import annotations

import asyncio
import gzip
import json
import socket
import urllib.request
from pathlib import Path

import pytest

from codegraph.indexing.indexer import Indexer
from codegraph.runtime.otel_receiver import run_otel_listener


def _get_free_port() -> int:
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
        s.bind(("127.0.0.1", 0))
        return s.getsockname()[1]


@pytest.fixture
def otel_repo(tmp_path: Path) -> Path:
    repo = tmp_path / "otel_repo"
    repo.mkdir()
    (repo / "app.py").write_text("def ping(): return 'pong'\n", encoding="utf-8")
    indexer = Indexer(repo)
    indexer.index()
    return repo


def _send_http(req: urllib.request.Request) -> tuple[int, dict[str, str], bytes]:
    with urllib.request.urlopen(req, timeout=5.0) as resp:
        return resp.status, dict(resp.headers), resp.read()


async def _run_otel_receiver_suite(otel_repo: Path) -> None:
    port = _get_free_port()
    indexer = Indexer(otel_repo)

    received_batches: list[dict] = []

    def on_batch(b: dict) -> None:
        received_batches.append(b)

    receiver = await run_otel_listener(
        db_path=indexer.db_path,
        host="127.0.0.1",
        port=port,
        on_batch=on_batch,
    )

    base_url = f"http://127.0.0.1:{port}"

    try:
        # 1. Test CORS OPTIONS preflight
        req_options = urllib.request.Request(
            f"{base_url}/v1/traces",
            method="OPTIONS",
        )
        status, headers, _ = await asyncio.to_thread(_send_http, req_options)
        assert status == 204
        assert headers.get("Access-Control-Allow-Origin") == "*"

        # 2. Test standard OTLP JSON trace POST
        trace_payload = {
            "resourceSpans": [
                {
                    "resource": {
                        "attributes": [
                            {"key": "service.name", "value": {"stringValue": "payment-service"}}
                        ]
                    },
                    "scopeSpans": [
                        {
                            "spans": [
                                {
                                    "traceId": "4bf92f3577b34da6a3ce929d0e0e4736",
                                    "spanId": "00f067aa0ba902b7",
                                    "name": "POST /api/v1/charge",
                                    "attributes": [
                                        {"key": "http.method", "value": {"stringValue": "POST"}},
                                        {"key": "http.route", "value": {"stringValue": "/api/v1/charge"}},
                                        {"key": "http.status_code", "value": {"intValue": 200}},
                                    ],
                                }
                            ]
                        }
                    ]
                }
            ]
        }

        body_bytes = json.dumps(trace_payload).encode("utf-8")
        req_post = urllib.request.Request(
            f"{base_url}/v1/traces",
            data=body_bytes,
            headers={"Content-Type": "application/json"},
            method="POST",
        )
        status, _, resp_raw = await asyncio.to_thread(_send_http, req_post)
        assert status == 200
        resp_body = json.loads(resp_raw.decode("utf-8"))
        assert "partialSuccess" in resp_body

        # 3. Test gzip compressed payload with distinct span ID
        trace_payload_2 = {
            "resourceSpans": [
                {
                    "resource": {
                        "attributes": [
                            {"key": "service.name", "value": {"stringValue": "payment-service"}}
                        ]
                    },
                    "scopeSpans": [
                        {
                            "spans": [
                                {
                                    "traceId": "4bf92f3577b34da6a3ce929d0e0e4736",
                                    "spanId": "00f067aa0ba902b8",
                                    "name": "POST /api/v1/charge",
                                    "attributes": [
                                        {"key": "http.method", "value": {"stringValue": "POST"}},
                                        {"key": "http.route", "value": {"stringValue": "/api/v1/charge"}},
                                        {"key": "http.status_code", "value": {"intValue": 200}},
                                    ],
                                }
                            ]
                        }
                    ]
                }
            ]
        }
        body_bytes_2 = json.dumps(trace_payload_2).encode("utf-8")
        gzip_bytes = gzip.compress(body_bytes_2)
        req_gzip = urllib.request.Request(
            f"{base_url}/v1/traces",
            data=gzip_bytes,
            headers={
                "Content-Type": "application/json",
                "Content-Encoding": "gzip",
            },
            method="POST",
        )
        status_gzip, _, _ = await asyncio.to_thread(_send_http, req_gzip)
        assert status_gzip == 200

        # Verify on_batch callbacks
        assert len(received_batches) == 2

        # 4. Verify SQLite ingestion
        with indexer.session() as con:
            row = con.execute("SELECT COUNT(*) FROM runtime_observations").fetchone()
            assert row[0] >= 2

    finally:
        await receiver.stop()


def test_otel_receiver_live(otel_repo: Path) -> None:
    """Run full live OTLP HTTP receiver test."""
    asyncio.run(_run_otel_receiver_suite(otel_repo))
