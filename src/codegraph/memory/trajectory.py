"""Long-Term Agent Trajectory & Debugging Memory for CodeGraph.

Maintains persistent, FTS5 full-text indexed records of past agent debugging sessions,
bug investigations, test repair trajectories, and architectural decisions to accelerate future
agent tasks and eliminate repeated troubleshooting mistakes.
"""
from __future__ import annotations

import json
import re
import sqlite3
import time
import uuid
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any


@dataclass
class AgentMemoryRecord:
    id: str
    created_at: str
    session_id: str
    category: str  # BUG_FIX, ARCHITECTURE_DECISION, TEST_PATTERN, ROOT_CAUSE, REFACTORING
    title: str
    symptoms: str
    root_cause: str
    resolution: str
    files: list[str] = field(default_factory=list)
    tags: list[str] = field(default_factory=list)
    outcome: str = "SUCCESS"
    score: float = 1.0

    def as_dict(self) -> dict[str, Any]:
        return {
            "id": self.id,
            "created_at": self.created_at,
            "session_id": self.session_id,
            "category": self.category,
            "title": self.title,
            "symptoms": self.symptoms,
            "root_cause": self.root_cause,
            "resolution": self.resolution,
            "files": self.files,
            "tags": self.tags,
            "outcome": self.outcome,
            "score": round(self.score, 3),
        }


class TrajectoryMemoryStore:
    """Persistent SQLite + FTS5 store for agent debugging trajectories."""

    def __init__(self, db_path: Path) -> None:
        self.db_path = db_path
        self._init_db()

    def _init_db(self) -> None:
        self.db_path.parent.mkdir(parents=True, exist_ok=True)
        with sqlite3.connect(self.db_path) as con:
            con.execute("PRAGMA journal_mode = WAL")
            con.execute("PRAGMA synchronous = NORMAL")
            con.execute(
                """
                CREATE TABLE IF NOT EXISTS agent_trajectories (
                    id TEXT PRIMARY KEY,
                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    session_id TEXT NOT NULL,
                    category TEXT NOT NULL,
                    title TEXT NOT NULL,
                    symptoms TEXT NOT NULL DEFAULT '',
                    root_cause TEXT NOT NULL DEFAULT '',
                    resolution TEXT NOT NULL DEFAULT '',
                    files_json TEXT NOT NULL DEFAULT '[]',
                    tags_json TEXT NOT NULL DEFAULT '[]',
                    outcome TEXT NOT NULL DEFAULT 'SUCCESS'
                )
                """
            )
            con.execute(
                """
                CREATE VIRTUAL TABLE IF NOT EXISTS agent_trajectories_fts USING fts5(
                    id UNINDEXED,
                    title,
                    symptoms,
                    root_cause,
                    resolution,
                    content='agent_trajectories',
                    content_rowid='rowid'
                )
                """
            )

    def store(
        self,
        title: str,
        resolution: str,
        category: str = "BUG_FIX",
        session_id: str | None = None,
        symptoms: str = "",
        root_cause: str = "",
        files: list[str] | None = None,
        tags: list[str] | None = None,
        outcome: str = "SUCCESS",
    ) -> AgentMemoryRecord:
        """Store an agent debugging or architectural trajectory into memory."""
        mem_id = f"mem_{uuid.uuid4().hex[:12]}"
        sess = session_id or f"sess_{uuid.uuid4().hex[:8]}"
        files_json = json.dumps(files or [])
        tags_json = json.dumps(tags or [])

        with sqlite3.connect(self.db_path) as con:
            cur = con.cursor()
            cur.execute(
                """
                INSERT INTO agent_trajectories (
                    id, session_id, category, title, symptoms, root_cause, resolution, files_json, tags_json, outcome
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (mem_id, sess, category, title, symptoms, root_cause, resolution, files_json, tags_json, outcome),
            )
            # Update FTS5
            cur.execute(
                """
                INSERT INTO agent_trajectories_fts (rowid, id, title, symptoms, root_cause, resolution)
                VALUES (last_insert_rowid(), ?, ?, ?, ?, ?)
                """,
                (mem_id, title, symptoms, root_cause, resolution),
            )
            con.commit()

        return AgentMemoryRecord(
            id=mem_id,
            created_at=time.strftime("%Y-%m-%d %H:%M:%S"),
            session_id=sess,
            category=category,
            title=title,
            symptoms=symptoms,
            root_cause=root_cause,
            resolution=resolution,
            files=files or [],
            tags=tags or [],
            outcome=outcome,
        )

    def search(
        self,
        query: str,
        category: str | None = None,
        limit: int = 5,
        max_tokens: int = 1500,
    ) -> list[AgentMemoryRecord]:
        """Search past agent memories using FTS5 BM25 relevance and recency weighting."""
        clean_q = query.strip()
        if not clean_q:
            return self.list_recent(limit=limit)

        records: list[AgentMemoryRecord] = []
        with sqlite3.connect(self.db_path) as con:
            con.row_factory = sqlite3.Row
            # FTS5 search
            safe_query = re.sub(r'[^\w\s]', ' ', clean_q).strip()
            if not safe_query:
                return self.list_recent(limit=limit)

            match_clause = "agent_trajectories_fts MATCH ?"
            params: list[Any] = [safe_query]

            cat_clause = ""
            if category:
                cat_clause = "AND t.category = ?"
                params.append(category)

            sql = f"""
                SELECT t.id, t.created_at, t.session_id, t.category, t.title,
                       t.symptoms, t.root_cause, t.resolution, t.files_json, t.tags_json, t.outcome,
                       bm25(agent_trajectories_fts) as rank
                FROM agent_trajectories_fts fts
                JOIN agent_trajectories t ON t.rowid = fts.rowid
                WHERE {match_clause} {cat_clause}
                ORDER BY rank ASC
                LIMIT ?
            """
            params.append(limit * 2)

            try:
                rows = con.execute(sql, params).fetchall()
            except sqlite3.OperationalError:
                # Fallback to LIKE
                like_sql = """
                    SELECT id, created_at, session_id, category, title, symptoms, root_cause, resolution,
                           files_json, tags_json, outcome, 1.0 as rank
                    FROM agent_trajectories
                    WHERE title LIKE ? OR resolution LIKE ? OR symptoms LIKE ?
                    ORDER BY id DESC LIMIT ?
                """
                rows = con.execute(like_sql, (f"%{clean_q}%", f"%{clean_q}%", f"%{clean_q}%", limit)).fetchall()

            total_chars = 0
            char_budget = max_tokens * 4

            for r in rows:
                files = json.loads(r["files_json"]) if r["files_json"] else []
                tags = json.loads(r["tags_json"]) if r["tags_json"] else []
                bm_score = float(r["rank"])
                relevance = round(1.0 / (1.0 + max(0.0, bm_score)), 3)

                rec = AgentMemoryRecord(
                    id=r["id"],
                    created_at=str(r["created_at"]),
                    session_id=r["session_id"],
                    category=r["category"],
                    title=r["title"],
                    symptoms=r["symptoms"],
                    root_cause=r["root_cause"],
                    resolution=r["resolution"],
                    files=files,
                    tags=tags,
                    outcome=r["outcome"],
                    score=relevance,
                )

                # Token budget check
                rec_len = len(rec.title) + len(rec.symptoms) + len(rec.root_cause) + len(rec.resolution)
                if total_chars + rec_len > char_budget and records:
                    break
                total_chars += rec_len
                records.append(rec)
                if len(records) >= limit:
                    break

        return records

    def list_recent(self, limit: int = 10) -> list[AgentMemoryRecord]:
        """List most recent agent memories."""
        records: list[AgentMemoryRecord] = []
        with sqlite3.connect(self.db_path) as con:
            con.row_factory = sqlite3.Row
            rows = con.execute(
                """
                SELECT id, created_at, session_id, category, title, symptoms, root_cause,
                       resolution, files_json, tags_json, outcome
                FROM agent_trajectories
                ORDER BY rowid DESC
                LIMIT ?
                """,
                (limit,),
            ).fetchall()

            for r in rows:
                files = json.loads(r["files_json"]) if r["files_json"] else []
                tags = json.loads(r["tags_json"]) if r["tags_json"] else []
                records.append(
                    AgentMemoryRecord(
                        id=r["id"],
                        created_at=str(r["created_at"]),
                        session_id=r["session_id"],
                        category=r["category"],
                        title=r["title"],
                        symptoms=r["symptoms"],
                        root_cause=r["root_cause"],
                        resolution=r["resolution"],
                        files=files,
                        tags=tags,
                        outcome=r["outcome"],
                        score=1.0,
                    )
                )
        return records

    def clear(self) -> None:
        """Clear all stored agent trajectories."""
        with sqlite3.connect(self.db_path) as con:
            con.execute("DELETE FROM agent_trajectories")
            con.execute("DELETE FROM agent_trajectories_fts")
            con.commit()


def get_trajectory_memory_store(repository: Path) -> TrajectoryMemoryStore:
    """Get the default trajectory memory store for a repository."""
    db_path = repository.resolve() / ".codegraph" / "memory.sqlite3"
    return TrajectoryMemoryStore(db_path)
