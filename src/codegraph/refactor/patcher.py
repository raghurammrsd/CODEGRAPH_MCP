"""Deterministic, syntax-validated, transaction-safe multi-file semantic patch engine.

Invariants:
1. Zero disk mutation during planning, dry-run preview, or validation.
2. Pre-flight AST and syntax validation (Python, Luau, JSON, JS/TS bracket balancing)
   before any disk write. If ANY file fails validation, the entire transaction is aborted.
3. Strict path validation: boundary enforcement and sensitive file redaction.
4. Precondition hash checking: verifies files on disk match expected baseline.
5. Atomic multi-file commit via sibling temporary files and os.replace() under RefactorLock.
6. Persistent rollback manifest allowing deterministic, byte-exact restoration.
"""
from __future__ import annotations

import ast
import difflib
import hashlib
import json
import uuid
from collections.abc import Sequence
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

from codegraph.errors import SecurityError
from codegraph.refactor.models import (
    RefactorPlan,
    RefactorResult,
    RefactorRisk,
    RefactorStatus,
)
from codegraph.refactor.transactions import commit_refactor_transaction
from codegraph.security.paths import is_sensitive_path, safe_path


@dataclass
class PatchHunk:
    """A target-replacement hunk within a file."""

    target: str
    replacement: str


@dataclass
class FilePatchSpec:
    """Specification of a patch on a single file."""

    path: str
    hunks: list[PatchHunk] = field(default_factory=list)
    new_content: str | None = None
    expected_hash: str | None = None


def validate_file_syntax(path: str, content: str) -> tuple[bool, str | None]:
    """Validate syntax of proposed content based on file extension.
    
    Returns (is_valid, error_message).
    """
    ext = Path(path).suffix.lower()

    if ext in (".py", ".pyi"):
        try:
            ast.parse(content, filename=path)
        except SyntaxError as e:
            return False, f"Python SyntaxError in '{path}' at line {e.lineno}, col {e.offset}: {e.msg}"

    elif ext == ".json":
        try:
            json.loads(content)
        except json.JSONDecodeError as e:
            return False, f"JSON DecodeError in '{path}' at line {e.lineno}, col {e.colno}: {e.msg}"

    elif ext in (".lua", ".luau"):
        # Bounded Luau syntax check: verify deterministic parsing
        try:
            from codegraph.roblox import parse_luau
            _ = parse_luau(content, path)
        except Exception as e:
            return False, f"Luau Syntax/Parse Error in '{path}': {e}"

    elif ext in (".js", ".jsx", ".ts", ".tsx"):
        # Fast structural delimiter balance check
        stack: list[tuple[str, int]] = []
        pairs = {')': '(', '}': '{', ']': '['}
        lines = content.splitlines()
        in_multiline_comment = False

        for line_num, line in enumerate(lines, start=1):
            i = 0
            while i < len(line):
                if in_multiline_comment:
                    if line[i:i+2] == "*/":
                        in_multiline_comment = False
                        i += 2
                        continue
                    i += 1
                    continue
                
                if line[i:i+2] == "//":
                    break
                if line[i:i+2] == "/*":
                    in_multiline_comment = True
                    i += 2
                    continue

                ch = line[i]
                if ch in ("'", '"', '`'):
                    quote = ch
                    i += 1
                    while i < len(line):
                        if line[i] == "\\":
                            i += 2
                            continue
                        if line[i] == quote:
                            break
                        i += 1
                elif ch in "({[":
                    stack.append((ch, line_num))
                elif ch in ")}]":
                    if not stack:
                        return False, f"JavaScript/TypeScript unbalanced '{ch}' at line {line_num} in '{path}'"
                    expected_open, open_line = stack.pop()
                    if pairs[ch] != expected_open:
                        return False, (
                            f"JavaScript/TypeScript mismatched '{ch}' at line {line_num} "
                            f"(expected closing for '{expected_open}' opened at line {open_line}) in '{path}'"
                        )
                i += 1

        if stack:
            unclosed, open_line = stack[-1]
            return False, f"JavaScript/TypeScript unclosed '{unclosed}' opened at line {open_line} in '{path}'"

    return True, None


def apply_hunks_to_content(original_content: str, hunks: list[PatchHunk], path: str) -> str:
    """Deterministically apply target->replacement hunks to content buffer."""
    current = original_content
    for hunk in hunks:
        if not hunk.target:
            raise ValueError(f"Empty target hunk in patch for '{path}'")
        count = current.count(hunk.target)
        if count == 0:
            raise ValueError(
                f"Target hunk not found in '{path}':\n```\n{hunk.target[:100]}\n```"
            )
        if count > 1:
            raise ValueError(
                f"Target hunk is ambiguous (found {count} matches) in '{path}'. Please provide more context."
            )
        current = current.replace(hunk.target, hunk.replacement, 1)
    return current


def plan_semantic_patch(
    repository: Path,
    patch_specs: Sequence[FilePatchSpec | dict[str, Any]],
) -> tuple[RefactorPlan | None, dict[str, str], list[str]]:
    """Plan and validate a semantic patch across repository files.
    
    Returns:
        (plan, modified_buffers, errors)
    """
    repo_root = repository.resolve()
    errors: list[str] = []
    normalized_specs: list[FilePatchSpec] = []

    for item in patch_specs:
        if isinstance(item, FilePatchSpec):
            normalized_specs.append(item)
        elif isinstance(item, dict):
            hunks: list[PatchHunk] = []
            for h in item.get("hunks", []):
                hunks.append(PatchHunk(target=h["target"], replacement=h["replacement"]))
            normalized_specs.append(
                FilePatchSpec(
                    path=item["path"],
                    hunks=hunks,
                    new_content=item.get("new_content") or item.get("content"),
                    expected_hash=item.get("expected_hash"),
                )
            )

    if not normalized_specs:
        return None, {}, ["NO_PATCHES_PROVIDED: patch_specs list cannot be empty."]

    modified_buffers: dict[str, str] = {}
    original_hashes: dict[str, str] = {}
    files: list[str] = []

    for spec in normalized_specs:
        rel_path = spec.path.replace("\\", "/").strip()
        if not rel_path:
            errors.append("EMPTY_PATH: File path cannot be empty.")
            continue

        if is_sensitive_path(rel_path):
            errors.append(f"SENSITIVE_FILE: Cannot patch sensitive file '{rel_path}'.")
            continue

        try:
            abs_path = safe_path(repo_root, rel_path)
        except SecurityError as sec_err:
            errors.append(f"SECURITY_ERROR: {sec_err}")
            continue

        if not abs_path.exists() or not abs_path.is_file():
            errors.append(f"FILE_NOT_FOUND: Target file '{rel_path}' does not exist.")
            continue

        try:
            orig_bytes = abs_path.read_bytes()
            orig_content = orig_bytes.decode("utf-8")
        except UnicodeDecodeError:
            errors.append(f"BINARY_FILE: Cannot patch non-UTF8 binary file '{rel_path}'.")
            continue

        current_hash = hashlib.sha256(orig_bytes).hexdigest()
        if spec.expected_hash and current_hash != spec.expected_hash:
            errors.append(
                f"HASH_MISMATCH: File '{rel_path}' hash ({current_hash[:12]}...) "
                f"does not match expected ({spec.expected_hash[:12]}...)."
            )
            continue

        # Compute modified content
        try:
            if spec.new_content is not None:
                mod_content = spec.new_content
            elif spec.hunks:
                mod_content = apply_hunks_to_content(orig_content, spec.hunks, rel_path)
            else:
                errors.append(f"NO_CHANGES_SPECIFIED: File '{rel_path}' has neither hunks nor new_content.")
                continue
        except ValueError as err:
            errors.append(str(err))
            continue

        # Validate syntax
        is_valid, syn_err = validate_file_syntax(rel_path, mod_content)
        if not is_valid and syn_err:
            errors.append(f"SYNTAX_VALIDATION_FAILED: {syn_err}")
            continue

        files.append(rel_path)
        original_hashes[rel_path] = current_hash
        modified_buffers[rel_path] = mod_content

    if errors:
        return None, {}, errors

    tx_id = f"patch-{uuid.uuid4().hex[:12]}"
    plan = RefactorPlan(
        transaction_id=tx_id,
        target_symbol="semantic_patch",
        new_name="applied_patch",
        files=files,
        risk=RefactorRisk.LOW,
        original_file_hashes=original_hashes,
    )
    return plan, modified_buffers, []


def preview_semantic_patch(
    repository: Path,
    patch_specs: Sequence[FilePatchSpec | dict[str, Any]],
) -> RefactorResult:
    """Dry-run preview a semantic patch with syntax validation and unified diffs.
    
    Zero disk mutation invariant guaranteed.
    """
    repo_root = repository.resolve()
    plan, modified_buffers, errors = plan_semantic_patch(repo_root, patch_specs)

    if errors or plan is None:
        return RefactorResult(
            status=RefactorStatus.BLOCKED if any("SECURITY" in e or "SENSITIVE" in e for e in errors) else RefactorStatus.ERROR,
            target_symbol="semantic_patch",
            new_name="",
            risk=RefactorRisk.HIGH,
            errors=errors,
        )

    # Generate unified diffs
    diffs: dict[str, str] = {}
    for rel_path, new_text in modified_buffers.items():
        abs_path = safe_path(repo_root, rel_path)
        orig_text = abs_path.read_text(encoding="utf-8")
        orig_lines = orig_text.splitlines(keepends=True)
        new_lines = new_text.splitlines(keepends=True)
        diff = difflib.unified_diff(
            orig_lines,
            new_lines,
            fromfile=f"a/{rel_path}",
            tofile=f"b/{rel_path}",
        )
        diffs[rel_path] = "".join(diff)

    return RefactorResult(
        status=RefactorStatus.READY,
        target_symbol="semantic_patch",
        new_name="",
        risk=RefactorRisk.LOW,
        files_changed=len(plan.files),
        diffs=diffs,
    )


def apply_semantic_patch(
    repository: Path,
    patch_specs: Sequence[FilePatchSpec | dict[str, Any]],
    dry_run: bool = False,
) -> RefactorResult:
    """Atomically apply a semantic patch across files with pre-flight syntax validation and rollback support."""
    repo_root = repository.resolve()

    if dry_run:
        return preview_semantic_patch(repo_root, patch_specs)

    plan, modified_buffers, errors = plan_semantic_patch(repo_root, patch_specs)
    if errors or plan is None:
        return RefactorResult(
            status=RefactorStatus.BLOCKED if any("SECURITY" in e or "SENSITIVE" in e for e in errors) else RefactorStatus.ERROR,
            target_symbol="semantic_patch",
            new_name="",
            risk=RefactorRisk.HIGH,
            errors=errors,
        )

    # Compute diffs for result
    diffs: dict[str, str] = {}
    for rel_path, new_text in modified_buffers.items():
        abs_path = safe_path(repo_root, rel_path)
        orig_text = abs_path.read_text(encoding="utf-8")
        orig_lines = orig_text.splitlines(keepends=True)
        new_lines = new_text.splitlines(keepends=True)
        diff = difflib.unified_diff(
            orig_lines,
            new_lines,
            fromfile=f"a/{rel_path}",
            tofile=f"b/{rel_path}",
        )
        diffs[rel_path] = "".join(diff)

    # Execute commit under RefactorLock
    result = commit_refactor_transaction(repo_root, plan, modified_buffers)
    result.diffs = diffs
    return result
