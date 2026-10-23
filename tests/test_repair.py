"""Unit tests for automated database repair and self-healing."""
from __future__ import annotations

import sqlite3
import time
from pathlib import Path

from codegraph.repair import repair_repository_index


def test_repair_clean_repository(tmp_path: Path) -> None:
    rep = repair_repository_index(tmp_path)
    assert rep.status == "HEALTHY"
    assert rep.integrity_check_passed
    assert rep.foreign_keys_valid


def test_repair_pruning_and_stale_locks(tmp_path: Path) -> None:
    dot_codegraph = tmp_path / ".codegraph"
    dot_codegraph.mkdir(parents=True)

    # Create stale lock file with backdated timestamp
    lock_file = dot_codegraph / "worker.lock"
    lock_file.write_text("12345", encoding="utf-8")
    old_time = time.time() - 100.0
    import os
    os.utime(lock_file, (old_time, old_time))

    # Create an sqlite database with dangling calls
    db_file = dot_codegraph / "index.db"
    con = sqlite3.connect(str(db_file))
    cur = con.cursor()
    cur.execute("CREATE TABLE files (path TEXT PRIMARY KEY);")
    cur.execute("CREATE TABLE calls (source_file TEXT, callee TEXT);")
    cur.execute("INSERT INTO files VALUES ('main.py');")
    cur.execute("INSERT INTO calls VALUES ('main.py', 'helper');")
    cur.execute("INSERT INTO calls VALUES ('deleted.py', 'ghost');")
    con.commit()
    con.close()

    rep = repair_repository_index(tmp_path, deep=True, vacuum=True)
    assert rep.status == "REPAIRED"
    assert rep.stale_locks_cleared == 1
    assert not lock_file.exists()
    assert rep.dangling_records_pruned.get("calls") == 1
    assert rep.wal_checkpointed
    assert rep.vacuumed

    # Verify dangling row was pruned
    con2 = sqlite3.connect(str(db_file))
    cur2 = con2.cursor()
    cur2.execute("SELECT COUNT(*) FROM calls;")
    count = cur2.fetchone()[0]
    con2.close()
    assert count == 1
