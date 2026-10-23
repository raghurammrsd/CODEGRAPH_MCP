"""Tests for long-term agent trajectory and debugging memory store."""
from __future__ import annotations

from pathlib import Path

import pytest

from codegraph.memory.trajectory import TrajectoryMemoryStore


@pytest.fixture
def memory_store(tmp_path: Path) -> TrajectoryMemoryStore:
    db_path = tmp_path / "memory.sqlite3"
    return TrajectoryMemoryStore(db_path)


def test_store_and_search_memory(memory_store: TrajectoryMemoryStore) -> None:
    # 1. Store memories
    rec1 = memory_store.store(
        title="JWT Token Expiry Bug",
        symptoms="Users getting 401 Unauthorized after 15 minutes",
        root_cause="clock_skew leeway was not configured in jwt.decode",
        resolution="Added leeway=timedelta(seconds=60) to verify_jwt()",
        category="BUG_FIX",
        files=["src/auth/jwt.py"],
        tags=["auth", "jwt", "security"],
    )
    assert rec1.id.startswith("mem_")
    assert rec1.category == "BUG_FIX"

    rec2 = memory_store.store(
        title="SQLite WAL Mode Deadlock",
        symptoms="database is locked under parallel agent interrogation",
        root_cause="Missing busy_timeout configuration and default delete journal mode",
        resolution="Set PRAGMA journal_mode = WAL and busy_timeout = 15000",
        category="ARCHITECTURE_DECISION",
        files=["src/db.py"],
        tags=["sqlite", "concurrency"],
    )
    assert rec2.id.startswith("mem_")

    # 2. Search for JWT
    results_jwt = memory_store.search("jwt token 401")
    assert len(results_jwt) >= 1
    assert results_jwt[0].title == "JWT Token Expiry Bug"
    assert "leeway" in results_jwt[0].resolution

    # 3. Search for SQLite WAL
    results_wal = memory_store.search("sqlite database locked")
    assert len(results_wal) >= 1
    assert results_wal[0].title == "SQLite WAL Mode Deadlock"

    # 4. Filter by category
    results_cat = memory_store.search("sqlite", category="BUG_FIX")
    assert len(results_cat) == 0

    results_cat_arch = memory_store.search("sqlite", category="ARCHITECTURE_DECISION")
    assert len(results_cat_arch) >= 1


def test_list_recent_and_clear(memory_store: TrajectoryMemoryStore) -> None:
    for i in range(5):
        memory_store.store(
            title=f"Bug Fix #{i}",
            resolution=f"Fixed issue {i}",
            category="BUG_FIX",
        )

    recent = memory_store.list_recent(limit=3)
    assert len(recent) == 3

    memory_store.clear()
    assert len(memory_store.list_recent()) == 0
