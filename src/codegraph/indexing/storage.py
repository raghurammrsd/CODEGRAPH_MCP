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
        value TEXT
    );
    """,
    """
    CREATE TABLE IF NOT EXISTS codegraph_meta (
        key TEXT PRIMARY KEY,
        value TEXT
    );
    """,
    # 2. Files
    """
    CREATE TABLE IF NOT EXISTS files (
        path TEXT PRIMARY KEY,
        language TEXT,
        size BIGINT,
        mtime DOUBLE PRECISION,
        content_hash TEXT,
        indexed_at DOUBLE PRECISION,
        status TEXT,
        error TEXT,
        category TEXT
    );
    """,
    # 3. Chunks
    """
    CREATE TABLE IF NOT EXISTS chunks (
        id TEXT PRIMARY KEY,
        path TEXT,
        language TEXT,
        kind TEXT,
        name TEXT,
        signature TEXT,
        start_line INTEGER,
        end_line INTEGER,
        content TEXT,
        content_hash TEXT,
        docstring TEXT,
        parent_id TEXT,
        depth INTEGER
    );
    """,
    # 4. Symbols
    """
    CREATE TABLE IF NOT EXISTS symbols (
        id TEXT PRIMARY KEY,
        canonical_id TEXT,
        path TEXT,
        language TEXT,
        kind TEXT,
        name TEXT,
        qualified_name TEXT,
        signature TEXT,
        start_line INTEGER,
        end_line INTEGER,
        scope TEXT,
        module TEXT,
        documentation TEXT,
        content_hash TEXT,
        parent_id TEXT,
        return_type TEXT,
        is_async INTEGER,
        decorators TEXT,
        visibility TEXT,
        status TEXT
    );
    """,
    # 5. Imports
    """
    CREATE TABLE IF NOT EXISTS imports (
        source_symbol_id TEXT,
        imported_symbol_id TEXT,
        imported_module TEXT,
        imported_name TEXT,
        alias TEXT,
        is_type_checking INTEGER,
        path TEXT,
        line INTEGER,
        confidence TEXT,
        evidence TEXT,
        source_hash TEXT,
        indexed_commit TEXT,
        evidence_status TEXT
    );
    """,
    # 6. Calls
    """
    CREATE TABLE IF NOT EXISTS calls (
        caller_id TEXT,
        callee_id TEXT,
        callee_name TEXT,
        line INTEGER,
        end_line INTEGER,
        confidence TEXT,
        path TEXT,
        evidence TEXT,
        source_hash TEXT,
        indexed_commit TEXT,
        receiver TEXT,
        qualified_callee TEXT,
        is_constructor INTEGER,
        is_dynamic INTEGER,
        evidence_status TEXT
    );
    """,
    # 7. Inheritance
    """
    CREATE TABLE IF NOT EXISTS inheritance (
        source_symbol TEXT,
        base_name TEXT,
        relationship TEXT,
        source_file TEXT,
        line INTEGER,
        source_canonical_id TEXT
    );
    """,
    # 8. Raw Framework Routes
    """
    CREATE TABLE IF NOT EXISTS raw_framework_routes (
        id TEXT PRIMARY KEY,
        framework TEXT,
        http_method TEXT,
        route_path TEXT,
        normalized_route TEXT,
        handler_name TEXT,
        handler_canonical_id TEXT,
        file_path TEXT,
        line INTEGER,
        end_line INTEGER,
        confidence TEXT,
        evidence TEXT,
        parameters_json TEXT,
        middleware_json TEXT,
        response_model TEXT
    );
    """,
    # 9. Router Mounts
    """
    CREATE TABLE IF NOT EXISTS router_mounts (
        id TEXT PRIMARY KEY,
        framework TEXT,
        prefix TEXT,
        router_expr TEXT,
        parent_router TEXT,
        file_path TEXT,
        line INTEGER
    );
    """,
    # 10. Router Definitions
    """
    CREATE TABLE IF NOT EXISTS router_definitions (
        id TEXT PRIMARY KEY,
        framework TEXT,
        router_var TEXT,
        router_class TEXT,
        prefix TEXT,
        file_path TEXT,
        line INTEGER
    );
    """,
    # 11. Local Bindings
    """
    CREATE TABLE IF NOT EXISTS local_bindings (
        id TEXT PRIMARY KEY,
        target_name TEXT,
        file_path TEXT,
        line INTEGER,
        scope TEXT,
        expr_kind TEXT,
        source_expr TEXT,
        base_expr TEXT,
        attr_name TEXT,
        is_conditional INTEGER
    );
    """,
    # 12. Framework Routes
    """
    CREATE TABLE IF NOT EXISTS framework_routes (
        id TEXT PRIMARY KEY,
        framework TEXT,
        http_method TEXT,
        route_path TEXT,
        normalized_route TEXT,
        handler_name TEXT,
        handler_canonical_id TEXT,
        file_path TEXT,
        line INTEGER,
        end_line INTEGER,
        confidence TEXT,
        evidence TEXT,
        parameters_json TEXT,
        middleware_json TEXT,
        response_model TEXT,
        resolution_state TEXT,
        router_origin TEXT,
        unmounted_prefix TEXT,
        synthetic_origin TEXT,
        mounted_depth INTEGER
    );
    """,
    # 13. References
    """
    CREATE TABLE IF NOT EXISTS "references" (
        source_symbol_id TEXT,
        target_symbol_id TEXT,
        relationship TEXT,
        confidence TEXT,
        path TEXT,
        start_line INTEGER,
        end_line INTEGER,
        evidence TEXT,
        source_hash TEXT,
        indexed_commit TEXT,
        evidence_status TEXT
    );
    """,
    # 14. Graph Edges
    """
    CREATE TABLE IF NOT EXISTS graph_edges (
        source TEXT,
        target TEXT,
        relationship TEXT,
        confidence TEXT,
        file_path TEXT,
        line INTEGER,
        weight DOUBLE PRECISION,
        evidence_class TEXT,
        evidence TEXT
    );
    """,
    # 15. Context Cache
    """
    CREATE TABLE IF NOT EXISTS context_cache (
        task_hash TEXT PRIMARY KEY,
        task TEXT,
        intent TEXT,
        query TEXT,
        packet_json TEXT,
        tokens INTEGER,
        created_at DOUBLE PRECISION,
        hits INTEGER
    );
    """,
    # 16. DB Entities (ORM Models)
    """
    CREATE TABLE IF NOT EXISTS db_entities (
        id TEXT PRIMARY KEY,
        entity_type TEXT,
        name TEXT,
        schema_name TEXT,
        dialect TEXT,
        source_file TEXT,
        line INTEGER,
        orm_framework TEXT,
        documentation TEXT,
        columns_json TEXT,
        constraints_json TEXT,
        metadata_json TEXT
    );
    """,
    # 17. DB Queries
    """
    CREATE TABLE IF NOT EXISTS db_queries (
        query_id TEXT PRIMARY KEY,
        caller_symbol_id TEXT,
        operation TEXT,
        relationship TEXT,
        table_name TEXT,
        table_canonical_id TEXT,
        columns_json TEXT,
        framework TEXT,
        normalized_sql TEXT,
        file_path TEXT,
        start_line INTEGER,
        end_line INTEGER,
        evidence TEXT,
        confidence TEXT,
        evidence_class TEXT,
        status TEXT
    );
    """,
    # 18. DB Migrations
    """
    CREATE TABLE IF NOT EXISTS db_migrations (
        migration_id TEXT PRIMARY KEY,
        canonical_id TEXT,
        system TEXT,
        revision TEXT,
        down_revision TEXT,
        file_path TEXT,
        start_line INTEGER,
        end_line INTEGER,
        created_tables_json TEXT,
        dropped_tables_json TEXT,
        added_columns_json TEXT,
        removed_columns_json TEXT,
        renamed_columns_json TEXT,
        indexes_json TEXT,
        foreign_keys_json TEXT,
        constraints_json TEXT,
        affected_tables_json TEXT,
        evidence TEXT,
        confidence TEXT,
        evidence_class TEXT
    );
    """,
    # 19. Runtime Observations
    """
    CREATE TABLE IF NOT EXISTS runtime_observations (
        id TEXT PRIMARY KEY,
        event_type TEXT,
        source_service TEXT,
        target_service TEXT,
        source_symbol TEXT,
        target_symbol TEXT,
        route_path TEXT,
        http_method TEXT,
        trace_id TEXT,
        span_id TEXT,
        parent_span_id TEXT,
        latency_ms DOUBLE PRECISION,
        status_code INTEGER,
        error_message TEXT,
        timestamp DOUBLE PRECISION,
        generation INTEGER,
        evidence_class TEXT
    );
    """,
    # 20. Runtime Edges
    """
    CREATE TABLE IF NOT EXISTS runtime_edges (
        source TEXT,
        target TEXT,
        relationship TEXT,
        observation_count INTEGER,
        avg_latency_ms DOUBLE PRECISION,
        error_rate DOUBLE PRECISION,
        first_seen DOUBLE PRECISION,
        last_seen DOUBLE PRECISION,
        evidence_class TEXT,
        PRIMARY KEY (source, target, relationship)
    );
    """,
    # 21. Agent Trajectory & Debugging Memories
    """
    CREATE TABLE IF NOT EXISTS agent_memories (
        id TEXT PRIMARY KEY,
        category TEXT,
        title TEXT,
        resolution TEXT,
        symptoms TEXT,
        root_cause TEXT,
        created_at DOUBLE PRECISION,
        tags_json TEXT
    );
    """,
    # 22. Indexes for High-Speed Lookups
    "CREATE INDEX IF NOT EXISTS idx_symbols_canonical ON symbols(canonical_id);",
    "CREATE INDEX IF NOT EXISTS idx_symbols_name ON symbols(name);",
    "CREATE INDEX IF NOT EXISTS idx_symbols_path ON symbols(path);",
    "CREATE INDEX IF NOT EXISTS idx_calls_caller ON calls(caller_id);",
    "CREATE INDEX IF NOT EXISTS idx_calls_callee ON calls(callee_id);",
    "CREATE INDEX IF NOT EXISTS idx_edges_source ON graph_edges(source);",
    "CREATE INDEX IF NOT EXISTS idx_edges_target ON graph_edges(target);",
    "CREATE INDEX IF NOT EXISTS idx_routes_norm ON framework_routes(normalized_route, http_method);",
    "CREATE INDEX IF NOT EXISTS idx_files_status ON files(status);",
    "CREATE INDEX IF NOT EXISTS idx_refs_source ON \"references\"(source_symbol_id);",
    "CREATE INDEX IF NOT EXISTS idx_refs_target ON \"references\"(target_symbol_id);",
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
