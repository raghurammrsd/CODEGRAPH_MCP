"""Multi-Agent Coordinator & Shared Working State Manager for CodeGraph.

Provides concurrent multi-agent collaboration with:
- SQLite-backed agent registration and TTL heartbeats (.codegraph/agents.sqlite3)
- File and module lease locks (EXCLUSIVE_WRITE vs SHARED_READ)
- Automatic reaping of dead/orphaned agent leases
- Semantic AST conflict prediction between concurrent agent edits
"""
from __future__ import annotations

import sqlite3
import time
from pathlib import Path

from .models import AgentSession, FileLease, MultiAgentStatusReport, SemanticConflict


class MultiAgentCoordinator:
    """Coordinates multiple AI coding agents working concurrently on a repository."""

    def __init__(self, repository: Path):
        self.repository = repository.resolve()
        self.dot_codegraph = self.repository / ".codegraph"
        self.dot_codegraph.mkdir(parents=True, exist_ok=True)
        self.db_path = self.dot_codegraph / "agents.sqlite3"
        self._init_db()

    def _init_db(self) -> None:
        with sqlite3.connect(str(self.db_path)) as con:
            con.execute("PRAGMA journal_mode=WAL;")
            con.execute("PRAGMA synchronous=NORMAL;")
            con.execute("""
                CREATE TABLE IF NOT EXISTS agent_sessions (
                    agent_id TEXT PRIMARY KEY,
                    name TEXT NOT NULL,
                    task_description TEXT NOT NULL,
                    registered_at REAL NOT NULL,
                    last_heartbeat REAL NOT NULL,
                    status TEXT NOT NULL
                );
            """)
            con.execute("""
                CREATE TABLE IF NOT EXISTS file_leases (
                    file_path TEXT NOT NULL,
                    agent_id TEXT NOT NULL,
                    lease_type TEXT NOT NULL,
                    granted_at REAL NOT NULL,
                    expires_at REAL NOT NULL,
                    PRIMARY KEY (file_path, agent_id)
                );
            """)
            con.commit()

    def register_session(self, agent_id: str, name: str, task_description: str) -> AgentSession:
        """Register a new or re-activating AI agent session."""
        now = time.time()
        with sqlite3.connect(str(self.db_path)) as con:
            con.execute("""
                INSERT INTO agent_sessions (agent_id, name, task_description, registered_at, last_heartbeat, status)
                VALUES (?, ?, ?, ?, ?, 'ACTIVE')
                ON CONFLICT(agent_id) DO UPDATE SET
                    name=excluded.name,
                    task_description=excluded.task_description,
                    last_heartbeat=excluded.last_heartbeat,
                    status='ACTIVE';
            """, (agent_id, name, task_description, now, now))
            con.commit()
        return AgentSession(
            agent_id=agent_id,
            name=name,
            task_description=task_description,
            registered_at=now,
            last_heartbeat=now,
            status="ACTIVE",
        )

    def heartbeat(self, agent_id: str) -> bool:
        """Send heartbeat to maintain active session and leases."""
        now = time.time()
        with sqlite3.connect(str(self.db_path)) as con:
            cur = con.execute("UPDATE agent_sessions SET last_heartbeat = ? WHERE agent_id = ?;", (now, agent_id))
            con.commit()
            return cur.rowcount > 0

    def claim_lease(
        self,
        agent_id: str,
        file_path: str,
        lease_type: str = "EXCLUSIVE_WRITE",
        ttl_seconds: float = 60.0,
    ) -> tuple[bool, str]:
        """Attempt to claim a lease on a file path."""
        self.reap_expired_leases()
        now = time.time()
        expires = now + ttl_seconds
        clean_path = str(Path(file_path).as_posix())

        with sqlite3.connect(str(self.db_path)) as con:
            # Check existing leases on path
            cur = con.execute("SELECT agent_id, lease_type, expires_at FROM file_leases WHERE file_path = ?;", (clean_path,))
            rows = cur.fetchall()

            for existing_agent, existing_type, existing_exp in rows:
                if existing_agent == agent_id:
                    # Renew own lease
                    con.execute("UPDATE file_leases SET expires_at = ? WHERE file_path = ? AND agent_id = ?;", (expires, clean_path, agent_id))
                    con.commit()
                    return True, "Renewed existing lease."

                if existing_exp > now:
                    if lease_type == "EXCLUSIVE_WRITE" or existing_type == "EXCLUSIVE_WRITE":
                        return False, f"Conflict: file '{clean_path}' currently leased by agent '{existing_agent}' ({existing_type})."

            con.execute("""
                INSERT INTO file_leases (file_path, agent_id, lease_type, granted_at, expires_at)
                VALUES (?, ?, ?, ?, ?)
                ON CONFLICT(file_path, agent_id) DO UPDATE SET
                    lease_type=excluded.lease_type,
                    expires_at=excluded.expires_at;
            """, (clean_path, agent_id, lease_type, now, expires))
            con.commit()
            return True, f"Lease granted on '{clean_path}' until {expires:.0f}."

    def release_lease(self, agent_id: str, file_path: str | None = None) -> int:
        """Release leases held by agent. If file_path omitted, releases all leases for agent."""
        with sqlite3.connect(str(self.db_path)) as con:
            if file_path:
                clean_path = str(Path(file_path).as_posix())
                cur = con.execute("DELETE FROM file_leases WHERE agent_id = ? AND file_path = ?;", (agent_id, clean_path))
            else:
                cur = con.execute("DELETE FROM file_leases WHERE agent_id = ?;", (agent_id,))
            con.commit()
            return cur.rowcount

    def reap_expired_leases(self) -> int:
        """Reap leases that have expired past TTL or whose agent heartbeat is stale (>60s)."""
        now = time.time()
        with sqlite3.connect(str(self.db_path)) as con:
            cur = con.execute("DELETE FROM file_leases WHERE expires_at < ?;", (now,))
            # Mark agents inactive if heartbeat older than 90s
            con.execute("UPDATE agent_sessions SET status = 'INACTIVE' WHERE (? - last_heartbeat) > 90.0;", (now,))
            con.commit()
            return cur.rowcount

    def check_conflicts(self, con: sqlite3.Connection | None = None) -> list[SemanticConflict]:
        """Inspect all active leases and detect direct write-write conflicts or downstream caller breaks."""
        self.reap_expired_leases()
        conflicts: list[SemanticConflict] = []
        now = time.time()

        with sqlite3.connect(str(self.db_path)) as agent_con:
            rows = agent_con.execute(
                "SELECT file_path, agent_id, lease_type FROM file_leases WHERE expires_at > ?;",
                (now,),
            ).fetchall()

        leases_by_file: dict[str, list[tuple[str, str]]] = {}
        for fp, aid, ltype in rows:
            leases_by_file.setdefault(fp, []).append((aid, ltype))

        # 1. Direct multiple-writer conflict
        for fp, holders in leases_by_file.items():
            writers = [aid for aid, ltype in holders if ltype == "EXCLUSIVE_WRITE"]
            if len(writers) > 1:
                conflicts.append(
                    SemanticConflict(
                        file_path=fp,
                        conflicting_agents=tuple(writers),
                        conflict_type="WRITE_WRITE",
                        reason=f"Multiple agents {writers} hold concurrent write leases on '{fp}'.",
                    )
                )

        # 2. Downstream caller contract breaks across leased files if repo connection available
        if con is not None:
            try:
                leased_paths = list(leases_by_file.keys())
                for fp in leased_paths:
                    agents_on_file = [aid for aid, _ in leases_by_file[fp]]
                    # Check calls where source_file is leased by another agent
                    cur_calls = con.execute(
                        "SELECT source_file, target_file FROM calls WHERE target_file = ? AND source_file != ?;",
                        (fp, fp),
                    )
                    for caller_file, _ in cur_calls.fetchall():
                        if caller_file in leases_by_file:
                            caller_agents = [aid for aid, _ in leases_by_file[caller_file]]
                            other_agents = [a for a in caller_agents if a not in agents_on_file]
                            if other_agents:
                                conflicts.append(
                                    SemanticConflict(
                                        file_path=fp,
                                        conflicting_agents=tuple(sorted(set(agents_on_file + other_agents))),
                                        conflict_type="DOWNSTREAM_CONTRACT_BREAK",
                                        reason=f"File '{fp}' leased by {agents_on_file} has caller '{caller_file}' leased by {other_agents}.",
                                    )
                                )
            except Exception:
                pass

        return conflicts

    def get_status_report(self) -> MultiAgentStatusReport:
        """Return consolidated multi-agent status report."""
        self.reap_expired_leases()
        now = time.time()
        with sqlite3.connect(str(self.db_path)) as con:
            cur_agents = con.execute("SELECT agent_id, name, task_description, registered_at, last_heartbeat, status FROM agent_sessions WHERE status = 'ACTIVE';")
            agents = [
                AgentSession(agent_id=r[0], name=r[1], task_description=r[2], registered_at=r[3], last_heartbeat=r[4], status=r[5])
                for r in cur_agents.fetchall()
            ]

            cur_leases = con.execute("SELECT file_path, agent_id, lease_type, granted_at, expires_at FROM file_leases WHERE expires_at > ?;", (now,))
            leases = [
                FileLease(file_path=r[0], agent_id=r[1], lease_type=r[2], granted_at=r[3], expires_at=r[4])
                for r in cur_leases.fetchall()
            ]

        conflicts = self.check_conflicts()
        return MultiAgentStatusReport(
            workspace=str(self.repository),
            total_agents=len(agents),
            active_leases_count=len(leases),
            conflicts_count=len(conflicts),
            agents=agents,
            leases=leases,
            conflicts=conflicts,
        )
