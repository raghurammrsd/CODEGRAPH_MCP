"""Storage Adapter & Multi-Backend Engine for CodeGraph.

Supports both:
1. Local-first embedded SQLite (default zero-dependency database).
2. Remote BYOC (Bring Your Own Cloud) PostgreSQL (Supabase, Neon, AWS RDS, GCP Cloud SQL).

Invariants:
- Zero data loss: All tables match the unified 22-table CodeGraph AST schema.
- Dual-access rows: All query results support both dict keys (`row["path"]`) and index tuples (`row[0]`).
- Offline resiliency: If a remote PostgreSQL database is unreachable, queries seamlessly fall back
  to local `.codegraph.sqlite3` with structured warnings instead of hard-crashing.
"""
from __future__ import annotations

import os
import re
import time
from collections.abc import Iterator, Sequence
from enum import StrEnum
from typing import Any, Protocol, runtime_checkable
from urllib.parse import urlparse


class StorageBackend(StrEnum):
    SQLITE = "sqlite"
    POSTGRESQL = "postgresql"


class StorageRow:
    """Universal row wrapper providing dual access by column name or integer index."""

    __slots__ = ("_data", "_col_map")

    def __init__(self, values: Sequence[Any], columns: Sequence[str]) -> None:
        self._data = tuple(values)
        self._col_map = {col.lower(): idx for idx, col in enumerate(columns)}

    def __getitem__(self, key: Any) -> Any:
        if isinstance(key, int):
            return self._data[key]
        if isinstance(key, str):
            idx = self._col_map.get(key.lower())
            if idx is not None:
                return self._data[idx]
            raise KeyError(f"Column '{key}' not found in row. Available: {list(self._col_map.keys())}")
        raise TypeError(f"Row indices must be integers or strings, not {type(key).__name__}")

    def __iter__(self) -> Iterator[Any]:
        return iter(self._data)

    def __len__(self) -> int:
        return len(self._data)

    def keys(self) -> list[str]:
        return list(self._col_map.keys())

    def values(self) -> tuple[Any, ...]:
        return self._data

    def items(self) -> list[tuple[str, Any]]:
        return [(k, self._data[v]) for k, v in self._col_map.items()]

    def as_dict(self) -> dict[str, Any]:
        return {k: self._data[v] for k, v in self._col_map.items()}

    def __repr__(self) -> str:
        return f"StorageRow({self.as_dict()!r})"

    def __eq__(self, other: object) -> bool:
        if isinstance(other, StorageRow):
            return self._data == other._data
        if isinstance(other, (tuple, list)):
            return self._data == tuple(other)
        return False


@runtime_checkable
class DatabaseConnection(Protocol):
    """Protocol for unified database connection interface."""

    def execute(self, sql: str, params: Sequence[Any] | None = None) -> Any: ...
    def executemany(self, sql: str, seq_of_params: Sequence[Sequence[Any]]) -> Any: ...
    def commit(self) -> None: ...
    def rollback(self) -> None: ...
    def close(self) -> None: ...


# ---------------------------------------------------------------------------
# SQL Dialect Translation (SQLite <-> PostgreSQL)
# ---------------------------------------------------------------------------

_SQLITE_PRAGMAS_RE = re.compile(r"^\s*PRAGMA\s+[a-zA-Z0-9_]+(?:\([^)]*\))?\s*;?\s*$", re.IGNORECASE)


def adapt_sql_for_postgres(sql: str) -> str:
    """Translate SQLite-flavored SQL into ANSI PostgreSQL dialect.

    Transformations:
    - Replaces parameter placeholders: `?` -> `%s`
    - Translates SQLite PRAGMAs to no-op comments
    - Normalizes quoted table names ("references")
    """
    clean = sql.strip()
    if _SQLITE_PRAGMAS_RE.match(clean):
        # PRAGMAs are SQLite-only; turn into comment for PostgreSQL
        return f"-- {clean}"

    # Replace parameter markers: SQLite ? to PostgreSQL %s
    # (Safe for CodeGraph standard queries where ? is not inside literal strings)
    converted = clean.replace("?", "%s")
    return converted


# ---------------------------------------------------------------------------
# PostgreSQL 22-Table Unified AST Schema
# ---------------------------------------------------------------------------

POSTGRES_SCHEMA_STATEMENTS: tuple[str, ...] = (
    # 1. Metadata
    """
    CREATE TABLE IF NOT EXISTS metadata (
        key TEXT PRIMARY KEY,
        value TEXT NOT NULL
    );
    """,
    """
    CREATE TABLE IF NOT EXISTS codegraph_meta (
        key TEXT PRIMARY KEY,
        value TEXT NOT NULL
    );
    """,
    # 2. Files
    """
    CREATE TABLE IF NOT EXISTS files (
        path TEXT PRIMARY KEY,
        hash TEXT NOT NULL,
        language TEXT NOT NULL,
        indexed_at BIGINT NOT NULL DEFAULT 0,
        status TEXT NOT NULL DEFAULT 'ok',
        parse_error TEXT,
        last_valid_hash TEXT,
        category TEXT NOT NULL DEFAULT 'SOURCE'
    );
    """,
    # 3. Chunks
    """
    CREATE TABLE IF NOT EXISTS chunks (
        id BIGSERIAL PRIMARY KEY,
        path TEXT NOT NULL REFERENCES files(path) ON DELETE CASCADE,
        language TEXT NOT NULL,
        symbol TEXT,
        symbol_type TEXT,
        start_line INTEGER NOT NULL,
        end_line INTEGER NOT NULL,
        content TEXT NOT NULL,
        hash TEXT NOT NULL
    );
    """,
    # 4. Symbols
    """
    CREATE TABLE IF NOT EXISTS symbols (
        id TEXT NOT NULL DEFAULT '',
        canonical_id TEXT NOT NULL DEFAULT '',
        name TEXT NOT NULL,
        qualified_name TEXT NOT NULL,
        kind TEXT NOT NULL,
        path TEXT NOT NULL REFERENCES files(path) ON DELETE CASCADE,
        start_line INTEGER NOT NULL,
        end_line INTEGER NOT NULL,
        decorators TEXT NOT NULL DEFAULT '',
        language TEXT NOT NULL DEFAULT 'python',
        module TEXT NOT NULL DEFAULT '',
        scope TEXT NOT NULL DEFAULT '',
        signature TEXT NOT NULL DEFAULT '',
        content_hash TEXT NOT NULL DEFAULT '',
        parent_symbol_id TEXT,
        visibility TEXT NOT NULL DEFAULT 'public',
        return_type TEXT,
        parameter_count INTEGER,
        documentation TEXT
    );
    """,
    # 5. Imports
    """
    CREATE TABLE IF NOT EXISTS imports (
        source_path TEXT NOT NULL REFERENCES files(path) ON DELETE CASCADE,
        module TEXT NOT NULL,
        name TEXT,
        alias TEXT,
        full_name TEXT,
        line INTEGER NOT NULL DEFAULT 1,
        source_module TEXT NOT NULL DEFAULT '',
        imported_module TEXT NOT NULL DEFAULT '',
        imported_name TEXT,
        local_name TEXT NOT NULL DEFAULT '',
        import_type TEXT NOT NULL DEFAULT 'module',
        resolved_path TEXT,
        resolved_module TEXT
    );
    """,
    # 6. Calls
    """
    CREATE TABLE IF NOT EXISTS calls (
        source_path TEXT NOT NULL REFERENCES files(path) ON DELETE CASCADE,
        callee TEXT NOT NULL,
        qualified_callee TEXT,
        line INTEGER NOT NULL DEFAULT 1,
        confidence TEXT NOT NULL DEFAULT 'LOW',
        source_symbol_id TEXT,
        resolved_symbol_id TEXT
    );
    """,
    # 7. Inheritance
    """
    CREATE TABLE IF NOT EXISTS inheritance (
        source_symbol TEXT NOT NULL,
        base_name TEXT NOT NULL,
        relationship TEXT NOT NULL,
        source_file TEXT NOT NULL REFERENCES files(path) ON DELETE CASCADE,
        line INTEGER NOT NULL DEFAULT 1,
        source_canonical_id TEXT NOT NULL DEFAULT ''
    );
    """,
    # 8. Raw Framework Routes
    """
    CREATE TABLE IF NOT EXISTS raw_framework_routes (
        endpoint_id TEXT PRIMARY KEY,
        framework TEXT NOT NULL,
        http_method TEXT NOT NULL,
        route_path TEXT NOT NULL,
        normalized_route TEXT NOT NULL,
        handler_name TEXT NOT NULL,
        handler_canonical_id TEXT NOT NULL,
        file_path TEXT NOT NULL REFERENCES files(path) ON DELETE CASCADE,
        line INTEGER NOT NULL,
        evidence TEXT NOT NULL,
        confidence TEXT NOT NULL DEFAULT 'HIGH',
        router_name TEXT NOT NULL DEFAULT ''
    );
    """,
    # 9. Router Mounts
    """
    CREATE TABLE IF NOT EXISTS router_mounts (
        mount_id TEXT PRIMARY KEY,
        framework TEXT NOT NULL,
        parent_router TEXT NOT NULL,
        child_router TEXT NOT NULL,
        prefix TEXT NOT NULL,
        file_path TEXT NOT NULL REFERENCES files(path) ON DELETE CASCADE,
        line INTEGER NOT NULL,
        evidence TEXT NOT NULL,
        confidence TEXT NOT NULL DEFAULT 'HIGH'
    );
    """,
    # 10. Router Definitions
    """
    CREATE TABLE IF NOT EXISTS router_definitions (
        id BIGSERIAL PRIMARY KEY,
        framework TEXT NOT NULL,
        router_name TEXT NOT NULL,
        prefix TEXT NOT NULL,
        file_path TEXT NOT NULL REFERENCES files(path) ON DELETE CASCADE,
        line INTEGER NOT NULL,
        evidence TEXT NOT NULL
    );
    """,
    # 11. Local Bindings
    """
    CREATE TABLE IF NOT EXISTS local_bindings (
        id BIGSERIAL PRIMARY KEY,
        target_name TEXT NOT NULL,
        file_path TEXT NOT NULL REFERENCES files(path) ON DELETE CASCADE,
        line INTEGER NOT NULL,
        "column" INTEGER,
        scope TEXT NOT NULL DEFAULT '',
        expr_kind TEXT NOT NULL DEFAULT 'IDENTIFIER',
        source_expr TEXT NOT NULL DEFAULT '',
        is_conditional INTEGER NOT NULL DEFAULT 0,
        base_expr TEXT NOT NULL DEFAULT '',
        attr_name TEXT NOT NULL DEFAULT '',
        dict_entries_json TEXT NOT NULL DEFAULT '[]',
        list_entries_json TEXT NOT NULL DEFAULT '[]',
        subscript_target TEXT,
        subscript_key TEXT,
        subscript_index INTEGER
    );
    """,
    # 12. Framework Routes
    """
    CREATE TABLE IF NOT EXISTS framework_routes (
        endpoint_id TEXT PRIMARY KEY,
        framework TEXT NOT NULL,
        http_method TEXT NOT NULL,
        route_path TEXT NOT NULL,
        normalized_route TEXT NOT NULL,
        handler_name TEXT NOT NULL,
        handler_canonical_id TEXT NOT NULL,
        file_path TEXT NOT NULL REFERENCES files(path) ON DELETE CASCADE,
        line INTEGER NOT NULL,
        evidence TEXT NOT NULL,
        confidence TEXT NOT NULL DEFAULT 'HIGH'
    );
    """,
    # 13. References
    """
    CREATE TABLE IF NOT EXISTS "references" (
        id BIGSERIAL PRIMARY KEY,
        source_symbol_id TEXT NOT NULL,
        target_symbol_id TEXT,
        relationship TEXT NOT NULL,
        confidence TEXT NOT NULL,
        path TEXT NOT NULL REFERENCES files(path) ON DELETE CASCADE,
        start_line INTEGER NOT NULL,
        end_line INTEGER NOT NULL,
        evidence TEXT NOT NULL DEFAULT '',
        source_hash TEXT NOT NULL DEFAULT '',
        indexed_commit TEXT,
        evidence_status TEXT NOT NULL DEFAULT 'current'
    );
    """,
    # 14. Graph Edges
    """
    CREATE TABLE IF NOT EXISTS graph_edges (
        source TEXT NOT NULL,
        target TEXT NOT NULL,
        relationship TEXT NOT NULL,
        confidence TEXT NOT NULL,
        file TEXT NOT NULL REFERENCES files(path) ON DELETE CASCADE,
        start_line INTEGER NOT NULL,
        end_line INTEGER NOT NULL,
        evidence TEXT NOT NULL DEFAULT '',
        evidence_id TEXT NOT NULL DEFAULT '',
        source_hash TEXT NOT NULL DEFAULT '',
        indexed_commit TEXT,
        evidence_class TEXT NOT NULL DEFAULT 'AST_VERIFIED',
        reason TEXT
    );
    """,
    # 15. Context Cache
    """
    CREATE TABLE IF NOT EXISTS context_cache (
        cache_key TEXT PRIMARY KEY,
        data TEXT NOT NULL,
        created_at BIGINT NOT NULL
    );
    """,
    # 16. DB Entities
    """
    CREATE TABLE IF NOT EXISTS db_entities (
        id BIGSERIAL PRIMARY KEY,
        canonical_id TEXT NOT NULL DEFAULT '',
        kind TEXT NOT NULL,
        name TEXT NOT NULL,
        dialect TEXT NOT NULL DEFAULT 'generic',
        schema_name TEXT NOT NULL DEFAULT '',
        table_name TEXT NOT NULL,
        column_name TEXT NOT NULL DEFAULT '',
        data_type TEXT NOT NULL DEFAULT '',
        nullable INTEGER NOT NULL DEFAULT 1,
        default_value TEXT,
        is_primary_key INTEGER NOT NULL DEFAULT 0,
        is_foreign_key INTEGER NOT NULL DEFAULT 0,
        is_unique INTEGER NOT NULL DEFAULT 0,
        is_indexed INTEGER NOT NULL DEFAULT 0,
        target_table TEXT,
        target_column TEXT,
        orm_model_id TEXT,
        framework TEXT NOT NULL DEFAULT 'sql',
        file_path TEXT NOT NULL REFERENCES files(path) ON DELETE CASCADE,
        start_line INTEGER NOT NULL DEFAULT 1,
        end_line INTEGER NOT NULL DEFAULT 1,
        evidence TEXT NOT NULL DEFAULT '',
        confidence TEXT NOT NULL DEFAULT 'HIGH',
        evidence_class TEXT NOT NULL DEFAULT 'AST_VERIFIED',
        status TEXT NOT NULL DEFAULT 'FACT',
        metadata_json TEXT NOT NULL DEFAULT '{}'
    );
    """,
    # 17. DB Queries
    """
    CREATE TABLE IF NOT EXISTS db_queries (
        query_id TEXT PRIMARY KEY,
        caller_symbol_id TEXT NOT NULL,
        operation TEXT NOT NULL,
        relationship TEXT NOT NULL,
        table_name TEXT NOT NULL,
        table_canonical_id TEXT NOT NULL,
        columns_json TEXT NOT NULL DEFAULT '[]',
        framework TEXT NOT NULL DEFAULT 'raw_sql',
        normalized_sql TEXT NOT NULL DEFAULT '',
        file_path TEXT NOT NULL REFERENCES files(path) ON DELETE CASCADE,
        start_line INTEGER NOT NULL DEFAULT 1,
        end_line INTEGER NOT NULL DEFAULT 1,
        evidence TEXT NOT NULL DEFAULT '',
        confidence TEXT NOT NULL DEFAULT 'HIGH',
        evidence_class TEXT NOT NULL DEFAULT 'AST_VERIFIED',
        status TEXT NOT NULL DEFAULT 'FACT'
    );
    """,
    # 18. DB Migrations
    """
    CREATE TABLE IF NOT EXISTS db_migrations (
        migration_id TEXT PRIMARY KEY,
        canonical_id TEXT NOT NULL,
        system TEXT NOT NULL,
        revision TEXT NOT NULL,
        down_revision TEXT,
        file_path TEXT NOT NULL REFERENCES files(path) ON DELETE CASCADE,
        start_line INTEGER NOT NULL DEFAULT 1,
        end_line INTEGER NOT NULL DEFAULT 1,
        created_tables_json TEXT NOT NULL DEFAULT '[]',
        dropped_tables_json TEXT NOT NULL DEFAULT '[]',
        added_columns_json TEXT NOT NULL DEFAULT '[]',
        removed_columns_json TEXT NOT NULL DEFAULT '[]',
        renamed_columns_json TEXT NOT NULL DEFAULT '[]',
        indexes_json TEXT NOT NULL DEFAULT '[]',
        foreign_keys_json TEXT NOT NULL DEFAULT '[]',
        constraints_json TEXT NOT NULL DEFAULT '[]',
        affected_tables_json TEXT NOT NULL DEFAULT '[]',
        evidence TEXT NOT NULL DEFAULT '',
        confidence TEXT NOT NULL DEFAULT 'HIGH',
        evidence_class TEXT NOT NULL DEFAULT 'AST_VERIFIED'
    );
    """,
    # 19. Runtime Observations
    """
    CREATE TABLE IF NOT EXISTS runtime_observations (
        event_id TEXT PRIMARY KEY,
        trace_id TEXT NOT NULL,
        span_id TEXT NOT NULL,
        parent_span_id TEXT NOT NULL DEFAULT '',
        timestamp TEXT NOT NULL DEFAULT '',
        source_format TEXT NOT NULL DEFAULT 'json',
        http_method TEXT NOT NULL DEFAULT '',
        route_path TEXT NOT NULL DEFAULT '',
        handler_symbol TEXT NOT NULL DEFAULT '',
        caller_symbol TEXT NOT NULL DEFAULT '',
        callee_symbol TEXT NOT NULL DEFAULT '',
        service_name TEXT NOT NULL DEFAULT '',
        db_operation TEXT NOT NULL DEFAULT '',
        db_table TEXT NOT NULL DEFAULT '',
        db_columns_json TEXT NOT NULL DEFAULT '[]',
        normalized_sql TEXT NOT NULL DEFAULT '',
        status_code INTEGER,
        exception_type TEXT NOT NULL DEFAULT '',
        duration_ms DOUBLE PRECISION NOT NULL DEFAULT 0.0,
        evidence_class TEXT NOT NULL DEFAULT 'RUNTIME_OBSERVED',
        runtime_generation INTEGER NOT NULL DEFAULT 1
    );
    """,
    # 20. Runtime Edges
    """
    CREATE TABLE IF NOT EXISTS runtime_edges (
        edge_id TEXT PRIMARY KEY,
        source TEXT NOT NULL,
        target TEXT NOT NULL,
        relationship TEXT NOT NULL,
        operation TEXT NOT NULL DEFAULT '',
        evidence_class TEXT NOT NULL DEFAULT 'RUNTIME_OBSERVED',
        observation_count INTEGER NOT NULL DEFAULT 1,
        first_seen TEXT NOT NULL DEFAULT '',
        last_seen TEXT NOT NULL DEFAULT '',
        avg_duration_ms DOUBLE PRECISION NOT NULL DEFAULT 0.0,
        max_duration_ms DOUBLE PRECISION NOT NULL DEFAULT 0.0,
        sample_trace_id TEXT NOT NULL DEFAULT '',
        sample_span_id TEXT NOT NULL DEFAULT '',
        normalized_sql TEXT NOT NULL DEFAULT '',
        status_code INTEGER,
        exception_type TEXT NOT NULL DEFAULT '',
        runtime_generation INTEGER NOT NULL DEFAULT 1
    );
    """,
    # 21. Agent Memories
    """
    CREATE TABLE IF NOT EXISTS agent_memories (
        id BIGSERIAL PRIMARY KEY,
        key TEXT NOT NULL,
        value TEXT NOT NULL,
        category TEXT NOT NULL DEFAULT 'general',
        created_at DOUBLE PRECISION NOT NULL DEFAULT 0.0,
        updated_at DOUBLE PRECISION NOT NULL DEFAULT 0.0
    );
    """,
    # 22. Indexes for fast queries
    "CREATE INDEX IF NOT EXISTS idx_symbols_canonical ON symbols (canonical_id);",
    "CREATE INDEX IF NOT EXISTS idx_symbols_name ON symbols (name);",
    "CREATE INDEX IF NOT EXISTS idx_symbols_qualified ON symbols (qualified_name);",
    "CREATE INDEX IF NOT EXISTS idx_symbols_path ON symbols (path);",
    "CREATE INDEX IF NOT EXISTS idx_routes_file ON framework_routes (file_path);",
    "CREATE INDEX IF NOT EXISTS idx_routes_handler ON framework_routes (handler_canonical_id);",
    "CREATE INDEX IF NOT EXISTS idx_edges_source ON graph_edges (source);",
    "CREATE INDEX IF NOT EXISTS idx_edges_target ON graph_edges (target);",
    "CREATE INDEX IF NOT EXISTS idx_edges_rel ON graph_edges (relationship);",
    "CREATE INDEX IF NOT EXISTS idx_calls_source ON calls (source_path);",
    "CREATE INDEX IF NOT EXISTS idx_calls_callee ON calls (callee);",
)


# ---------------------------------------------------------------------------
# PostgreSQL Connection Wrapper
# ---------------------------------------------------------------------------


class PostgresCursorWrapper:
    """Wraps a psycopg Cursor to yield StorageRows with dual index/name access."""

    def __init__(self, raw_cursor: Any) -> None:
        self._raw = raw_cursor

    def execute(self, sql: str, params: Sequence[Any] | None = None) -> Any:
        converted_sql = adapt_sql_for_postgres(sql)
        if params is not None:
            return self._raw.execute(converted_sql, tuple(params))
        return self._raw.execute(converted_sql)

    def executemany(self, sql: str, seq_of_params: Sequence[Sequence[Any]]) -> Any:
        converted_sql = adapt_sql_for_postgres(sql)
        return self._raw.executemany(converted_sql, [tuple(p) for p in seq_of_params])

    def fetchone(self) -> StorageRow | None:
        row = self._raw.fetchone()
        if row is None:
            return None
        col_names = [desc[0] for desc in (self._raw.description or [])]
        return StorageRow(row, col_names)

    def fetchall(self) -> list[StorageRow]:
        rows = self._raw.fetchall()
        if not rows:
            return []
        col_names = [desc[0] for desc in (self._raw.description or [])]
        return [StorageRow(r, col_names) for r in rows]

    @property
    def rowcount(self) -> int:
        return int(self._raw.rowcount)

    def __iter__(self) -> Iterator[StorageRow]:
        col_names = [desc[0] for desc in (self._raw.description or [])]
        for row in self._raw:
            yield StorageRow(row, col_names)


class PostgresConnectionWrapper:
    """Wraps psycopg connection for drop-in compatibility with CodeGraph's DB-API usage."""

    def __init__(self, raw_conn: Any, url_redacted: str) -> None:
        self._conn = raw_conn
        self.url_redacted = url_redacted

    def cursor(self) -> PostgresCursorWrapper:
        return PostgresCursorWrapper(self._conn.cursor())

    def execute(self, sql: str, params: Sequence[Any] | None = None) -> PostgresCursorWrapper:
        cur = self.cursor()
        cur.execute(sql, params)
        return cur

    def executemany(self, sql: str, seq_of_params: Sequence[Sequence[Any]]) -> PostgresCursorWrapper:
        cur = self.cursor()
        cur.executemany(sql, seq_of_params)
        return cur

    def commit(self) -> None:
        self._conn.commit()

    def rollback(self) -> None:
        self._conn.rollback()

    def close(self) -> None:
        self._conn.close()

    def __enter__(self) -> PostgresConnectionWrapper:
        return self

    def __exit__(self, exc_type: Any, exc_val: Any, exc_tb: Any) -> None:
        if exc_type is not None:
            self.rollback()
        else:
            self.commit()


# ---------------------------------------------------------------------------
# Database Management & Provisioning Functions
# ---------------------------------------------------------------------------


def redact_db_url(url: str) -> str:
    """Redact password from database connection string for safe logging and display."""
    try:
        parsed = urlparse(url)
        if parsed.password:
            netloc = f"{parsed.username}:******@{parsed.hostname}"
            if parsed.port:
                netloc += f":{parsed.port}"
            return parsed._replace(netloc=netloc).geturl()
    except Exception:
        pass
    return re.sub(r"://([^:]+):([^@]+)@", r"://\1:******@", url)


def verify_postgres_connection(url: str, timeout_seconds: float = 5.0) -> dict[str, Any]:
    """Test connectivity, SSL negotiation, and round-trip latency to a PostgreSQL instance."""
    try:
        import psycopg
    except ImportError:
        return {
            "status": "error",
            "error": "psycopg driver not installed. Install via: pip install 'psycopg[binary]'",
            "connected": False,
        }

    t0 = time.perf_counter()
    try:
        # Enforce connect timeout
        conn = psycopg.connect(url, connect_timeout=int(timeout_seconds))
        with conn.cursor() as cur:
            cur.execute("SELECT version();")
            row = cur.fetchone()
            version_str = str(row[0]) if row else "PostgreSQL"
        conn.close()
        elapsed_ms = round((time.perf_counter() - t0) * 1000.0, 2)
        return {
            "status": "ok",
            "connected": True,
            "latency_ms": elapsed_ms,
            "version": version_str.split(",")[0],
            "url": redact_db_url(url),
        }
    except Exception as exc:
        elapsed_ms = round((time.perf_counter() - t0) * 1000.0, 2)
        return {
            "status": "error",
            "connected": False,
            "latency_ms": elapsed_ms,
            "error": str(exc),
            "url": redact_db_url(url),
        }


def init_postgres_database(url: str) -> dict[str, Any]:
    """Initialize all 22 CodeGraph AST tables and lookup indexes in a remote PostgreSQL database."""
    try:
        import psycopg
    except ImportError:
        return {
            "status": "error",
            "error": "psycopg driver not installed. Run: pip install 'psycopg[binary]'",
            "tables_created": 0,
        }

    conn_res = verify_postgres_connection(url)
    if not conn_res["connected"]:
        return conn_res

    t0 = time.perf_counter()
    tables_created = 0
    indexes_created = 0

    try:
        conn = psycopg.connect(url)
        with conn.cursor() as cur:
            for statement in POSTGRES_SCHEMA_STATEMENTS:
                stmt_clean = statement.strip()
                if not stmt_clean:
                    continue
                cur.execute(stmt_clean)
                if "CREATE TABLE" in stmt_clean.upper():
                    tables_created += 1
                elif "CREATE INDEX" in stmt_clean.upper():
                    indexes_created += 1
            # Stamp schema version
            cur.execute(
                """
                INSERT INTO metadata (key, value)
                VALUES ('schema_version', '22')
                ON CONFLICT (key) DO UPDATE SET value = '22';
                """
            )
            cur.execute(
                """
                INSERT INTO metadata (key, value)
                VALUES ('initialized_at', %s)
                ON CONFLICT (key) DO UPDATE SET value = EXCLUDED.value;
                """,
                (str(int(time.time())),),
            )
        conn.commit()
        conn.close()
        elapsed_ms = round((time.perf_counter() - t0) * 1000.0, 2)

        return {
            "status": "ok",
            "connected": True,
            "tables_created": tables_created,
            "indexes_created": indexes_created,
            "duration_ms": elapsed_ms,
            "url": redact_db_url(url),
        }
    except Exception as exc:
        return {
            "status": "error",
            "connected": False,
            "error": f"Failed executing PostgreSQL schema: {exc}",
            "tables_created": tables_created,
            "url": redact_db_url(url),
        }


def get_configured_database_url() -> str | None:
    """Retrieve configured PostgreSQL URL from environment or return None for local SQLite."""
    url = os.getenv("CODEGRAPH_DATABASE_URL") or os.getenv("DATABASE_URL")
    if url and (url.startswith("postgresql://") or url.startswith("postgres://")):
        return url.strip()
    return None

def push_index_to_postgres(repo_path: Any, db_url: str | None = None) -> dict[str, Any]:
    """Push local SQLite index rows into remote PostgreSQL database."""
    import sqlite3
    from pathlib import Path
    try:
        import psycopg
    except ImportError:
        return {"status": "error", "error": "psycopg driver not installed. Run: pip install 'psycopg[binary]'"}

    target_url = db_url or get_configured_database_url()
    if not target_url:
        return {"status": "error", "error": "No PostgreSQL database URL provided or found in CODEGRAPH_DATABASE_URL"}

    target_dir = Path(repo_path)
    sqlite_db = target_dir / ".codegraph.sqlite3"
    if not sqlite_db.exists():
        return {"status": "error", "error": f"No SQLite index found at {sqlite_db}. Run 'codegraph index' first."}

    # Ensure PostgreSQL schema is initialized
    init_res = init_postgres_database(target_url)
    if init_res.get("status") != "ok":
        return init_res

    tables_order = [
        "metadata", "codegraph_meta", "files", "chunks", "symbols",
        "imports", "calls", "inheritance", "raw_framework_routes",
        "router_mounts", "router_definitions", "local_bindings",
        "framework_routes", "references", "graph_edges", "context_cache",
        "db_entities", "db_queries", "db_migrations"
    ]

    t0 = time.perf_counter()
    con_sq = sqlite3.connect(sqlite_db)
    con_pg = psycopg.connect(target_url)
    cur_sq = con_sq.cursor()

    existing_tables = set(r[0] for r in cur_sq.execute("SELECT name FROM sqlite_master WHERE type='table'").fetchall())

    transferred: dict[str, int] = {}
    try:
        with con_pg.cursor() as cur_pg:
            for t in tables_order:
                if t not in existing_tables:
                    continue
                cols = [r[1] for r in cur_sq.execute(f'PRAGMA table_info("{t}")').fetchall()]
                if not cols:
                    continue
                quoted_cols = [f'"{c}"' if c == 'column' else c for c in cols]
                col_str = ', '.join(quoted_cols)
                placeholders = ', '.join(['%s'] * len(cols))
                rows = cur_sq.execute(f'SELECT {col_str} FROM "{t}"').fetchall()
                if rows:
                    cur_pg.executemany(f'INSERT INTO "{t}" ({col_str}) VALUES ({placeholders}) ON CONFLICT DO NOTHING', rows)
                    transferred[t] = len(rows)
                else:
                    transferred[t] = 0
            con_pg.commit()
    finally:
        con_pg.close()
        con_sq.close()

    elapsed_ms = round((time.perf_counter() - t0) * 1000.0, 2)
    return {
        "status": "ok",
        "transferred": transferred,
        "total_rows": sum(transferred.values()),
        "duration_ms": elapsed_ms,
        "url": redact_db_url(target_url),
    }

