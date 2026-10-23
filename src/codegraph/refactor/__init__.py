"""Deterministic, syntax-validated, transaction-safe refactoring engine for CodeGraph MCP."""
from __future__ import annotations

from codegraph.refactor.models import (
    RefactorPlan,
    RefactorResult,
    RefactorRisk,
    RefactorStatus,
    TokenReplacementSpan,
)
from codegraph.refactor.patcher import (
    FilePatchSpec,
    PatchHunk,
    apply_semantic_patch,
    plan_semantic_patch,
    preview_semantic_patch,
)
from codegraph.refactor.renamer import (
    execute_safe_rename,
    plan_safe_rename,
    preview_safe_rename,
)
from codegraph.refactor.transactions import (
    RefactorLock,
    RefactorLockError,
    commit_refactor_transaction,
    rollback_refactor,
)

__all__ = [
    "FilePatchSpec",
    "PatchHunk",
    "RefactorLock",
    "RefactorLockError",
    "RefactorPlan",
    "RefactorResult",
    "RefactorRisk",
    "RefactorStatus",
    "TokenReplacementSpan",
    "apply_semantic_patch",
    "commit_refactor_transaction",
    "execute_safe_rename",
    "plan_safe_rename",
    "plan_semantic_patch",
    "preview_safe_rename",
    "preview_semantic_patch",
    "rollback_refactor",
]
