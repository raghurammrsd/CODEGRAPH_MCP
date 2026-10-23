"""Comprehensive tests for Batch MCP tools and Semantic Patch MCP tools."""
from __future__ import annotations

import asyncio
from pathlib import Path

import pytest

from codegraph.indexing import Indexer
from codegraph.mcp import create_server


@pytest.fixture
def sample_mcp_repo(tmp_path: Path) -> Path:
    repo = tmp_path / "batch_repo"
    repo.mkdir()

    (repo / "service.py").write_text(
        "class UserService:\n"
        "    def get_user(self, user_id: int) -> dict:\n"
        "        return {'id': user_id}\n\n"
        "class OrderService:\n"
        "    def create_order(self, user_id: int, item: str) -> dict:\n"
        "        user = UserService().get_user(user_id)\n"
        "        return {'user': user, 'item': item}\n",
        encoding="utf-8",
    )

    indexer = Indexer(repo)
    indexer.index()
    return repo


async def _run_batch_mcp_tests(sample_mcp_repo: Path) -> None:
    server = create_server(sample_mcp_repo, profile="full")
    tools = await server.list_tools()
    tool_names = {t.name for t in tools}

    assert "batch_get_symbols" in tool_names
    assert "batch_find_callers" in tool_names
    assert "batch_get_context" in tool_names
    assert "preview_semantic_patch" in tool_names
    assert "apply_semantic_patch" in tool_names

    # 1. Test batch_get_symbols
    _, meta = await server.call_tool(
        "batch_get_symbols",
        {"symbols": ["UserService", "OrderService.create_order", "NonExistentSymbol"]},
    )
    result = meta.get("result") or meta
    assert result["count"] == 3
    assert result["found_count"] >= 2
    assert "UserService" in result["results"]
    assert "OrderService.create_order" in result["results"]

    # 2. Test batch_find_callers
    _, meta_callers = await server.call_tool(
        "batch_find_callers",
        {"symbols": ["UserService.get_user", "OrderService.create_order"]},
    )
    callers_res = meta_callers.get("result") or meta_callers
    assert callers_res["count"] == 2
    assert "UserService.get_user" in callers_res["results"]
    assert "OrderService.create_order" in callers_res["results"]

    # 3. Test batch_get_context
    _, meta_ctx = await server.call_tool(
        "batch_get_context",
        {
            "tasks": [
                {"query": "Understand UserService", "intent": "UNDERSTAND"},
                {"query": "Trace OrderService create_order", "intent": "TRACE"},
            ],
            "max_tokens_per_task": 1000,
        },
    )
    ctx_res = meta_ctx.get("result") or meta_ctx
    assert ctx_res["count"] == 2
    assert len(ctx_res["results"]) == 2

    # 4. Test preview_semantic_patch
    _, meta_prev = await server.call_tool(
        "preview_semantic_patch",
        {
            "patches": [
                {
                    "path": "service.py",
                    "hunks": [
                        {
                            "target": "return {'id': user_id}",
                            "replacement": "return {'id': user_id, 'active': True}",
                        }
                    ],
                }
            ]
        },
    )
    prev_res = meta_prev.get("result") or meta_prev
    assert prev_res["status"] == "READY"
    assert prev_res["files_changed"] == 1
    assert "service.py" in prev_res["diffs"]

    # Disk must be unchanged
    service_content = (sample_mcp_repo / "service.py").read_text(encoding="utf-8")
    assert "return {'id': user_id}" in service_content
    assert "'active': True" not in service_content

    # 5. Test apply_semantic_patch
    _, meta_apply = await server.call_tool(
        "apply_semantic_patch",
        {
            "patches": [
                {
                    "path": "service.py",
                    "hunks": [
                        {
                            "target": "return {'id': user_id}",
                            "replacement": "return {'id': user_id, 'active': True}",
                        }
                    ],
                }
            ],
            "dry_run": False,
        },
    )
    apply_res = meta_apply.get("result") or meta_apply
    assert apply_res["status"] == "APPLIED"
    assert apply_res["rollback_id"] is not None

    # Disk must now be updated
    new_content = (sample_mcp_repo / "service.py").read_text(encoding="utf-8")
    assert "'active': True" in new_content


def test_batch_mcp_tools(sample_mcp_repo: Path) -> None:
    asyncio.run(_run_batch_mcp_tests(sample_mcp_repo))
