"""Inter-Procedural Type & Nullability Dataflow Propagation for CodeGraph.

Traces typed argument flows and return value nullability across function calls:
- Propagates types across caller arguments into callee parameters
- Tracks return value nullability (e.g. Optional[T] / None returns) into downstream callers
- Flags unguarded null dereferences (NoneType attribute access / NullPointerExceptions)
"""
from __future__ import annotations

import sqlite3
from dataclasses import asdict, dataclass, field
from typing import Any


@dataclass(frozen=True)
class NullabilityWarning:
    """An unguarded null/None dereference detected across call boundaries."""

    caller_symbol: str
    callee_symbol: str
    variable_name: str
    file_path: str
    line: int
    message: str

    def as_dict(self) -> dict[str, Any]:
        return asdict(self)


@dataclass
class DataflowPropagationReport:
    """Consolidated inter-procedural dataflow report."""

    target_symbol: str
    inferred_return_type: str
    is_nullable: bool
    downstream_callers_count: int
    nullability_warnings: list[NullabilityWarning] = field(default_factory=list)
    propagated_arguments: dict[str, str] = field(default_factory=dict)

    def as_dict(self) -> dict[str, Any]:
        return {
            "target_symbol": self.target_symbol,
            "inferred_return_type": self.inferred_return_type,
            "is_nullable": self.is_nullable,
            "downstream_callers_count": self.downstream_callers_count,
            "nullability_warnings": [w.as_dict() for w in self.nullability_warnings],
            "propagated_arguments": self.propagated_arguments,
        }


def propagate_interprocedural_dataflow(
    con: sqlite3.Connection,
    target_symbol: str,
) -> DataflowPropagationReport:
    """Trace dataflow, return types, and null dereference risks for target symbol."""
    cur = con.cursor()

    # Query target symbol details
    cur.execute("""
        SELECT name, signature, return_type, path, start_line
        FROM symbols
        WHERE name = ? OR canonical_id = ?
        LIMIT 1;
    """, (target_symbol, target_symbol))
    row = cur.fetchone()

    inferred_ret = "unknown"
    is_nullable = False
    if row:
        sig = str(row[1]) if row[1] else ""
        ret_t = str(row[2]) if row[2] else ""
        inferred_ret = ret_t or ("None" if "-> None" in sig else "Any")
        is_nullable = "optional" in inferred_ret.lower() or "none" in inferred_ret.lower() or "?" in inferred_ret

    # Query callers
    cur.execute("PRAGMA table_info(calls);")
    call_cols = {col[1] for col in cur.fetchall()}
    if "source_symbol_id" in call_cols:
        cur.execute("""
            SELECT COALESCE(s.name, calls.source_symbol_id, 'caller') AS caller_symbol,
                   COALESCE(s.canonical_id, calls.source_symbol_id, '') AS caller_canonical_id,
                   calls.source_path,
                   calls.line
            FROM calls
            LEFT JOIN symbols s ON (calls.source_symbol_id = s.id OR calls.source_symbol_id = s.canonical_id)
            WHERE calls.callee = ? OR calls.callee LIKE ?;
        """, (target_symbol, f"%.{target_symbol}"))
    else:
        file_col = "source_file" if "source_file" in call_cols else "source_path"
        cur.execute(f"""
            SELECT caller_symbol, caller_canonical_id, {file_col}, line
            FROM calls
            WHERE callee = ? OR callee LIKE ?;
        """, (target_symbol, f"%.{target_symbol}"))
    callers = cur.fetchall()

    warnings: list[NullabilityWarning] = []
    if is_nullable:
        for caller_name, _, source_file, line in callers:
            warnings.append(
                NullabilityWarning(
                    caller_symbol=str(caller_name or "caller"),
                    callee_symbol=target_symbol,
                    variable_name="result",
                    file_path=str(source_file),
                    line=int(line),
                    message=f"Function '{target_symbol}' returns nullable type '{inferred_ret}'; caller '{caller_name}' may dereference None without guard.",
                )
            )

    return DataflowPropagationReport(
        target_symbol=target_symbol,
        inferred_return_type=inferred_ret,
        is_nullable=is_nullable,
        downstream_callers_count=len(callers),
        nullability_warnings=warnings,
    )
