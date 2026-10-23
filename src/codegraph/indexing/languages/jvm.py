"""Deep, production-grade JVM (Java & Kotlin) language parser and framework resolver for CodeGraph.

Provides deep AST extraction for:
- Full scope tree: package -> class / interface / enum / record / object -> method / function
- Exact parameters, type signatures, return types, and parameter counts
- Javadoc (/** ... */) and KDoc comments attached to symbols
- Spring Boot & JAX-RS / Quarkus route decorators:
  - Class-level @RequestMapping, @Path, @RestController
  - Method-level @GetMapping, @PostMapping, @PutMapping, @DeleteMapping, @PatchMapping, @GET, @POST, @PUT, @DELETE
  - Composed prefix path resolution
- JPA & database entity mappings (@Entity, @Table(name="..."))
- Dependency Injection bindings (@Autowired, @Inject)
- Class inheritance & interface implementations (InheritanceRef)
- Caller-to-callee enclosing linkage (CallRef with caller_canonical_id and receiver)
- Local variable bindings (BindingRef)
"""
from __future__ import annotations

import hashlib
import re
from typing import Any

from codegraph.frameworks import RouteDetection, RouterMountDetection, join_route_prefixes
from codegraph.indexing.models import (
    BindingRef,
    CallRef,
    ImportRef,
    InheritanceRef,
    Symbol,
)


def parse_jvm(content: str, file_path: str) -> Any:
    """Parse Java (.java) or Kotlin (.kt, .kts) source code with deep scope tracking, caller linking, and Spring/JAX-RS route resolution."""
    from codegraph.indexing.parser import ParseResult

    source_hash = hashlib.sha256(content.encode("utf-8", errors="replace")).hexdigest()
    lines = content.splitlines()
    is_kotlin = file_path.lower().endswith((".kt", ".kts"))
    lang_name = "kotlin" if is_kotlin else "java"

    symbols: list[Symbol] = []
    imports: list[ImportRef] = []
    calls: list[CallRef] = []
    inheritance: list[InheritanceRef] = []
    routes: list[RouteDetection] = []
    mounts: list[RouterMountDetection] = []
    bindings: list[BindingRef] = []
    exports: list[str] = []

    # 1. Package Extraction
    pkg_name = ""
    for line in lines[:50]:
        clean = line.strip()
        m_pkg = re.match(r"^package\s+([A-Za-z0-9_.]+);?", clean)
        if m_pkg:
            pkg_name = m_pkg.group(1)
            break

    # 2. Imports Extraction
    for line_idx, line in enumerate(lines, start=1):
        clean = line.strip()
        if not clean or clean.startswith("//") or clean.startswith("/*") or clean.startswith("*"):
            continue

        # Java / Kotlin imports
        m_imp = re.match(r"^import\s+(?:static\s+)?([A-Za-z0-9_.]+)(?:\s+as\s+([A-Za-z0-9_]+))?;?", clean)
        if m_imp:
            full_path = m_imp.group(1)
            alias = m_imp.group(2)
            parts = full_path.split(".")
            imp_name = alias or parts[-1]
            mod_path = ".".join(parts[:-1]) if len(parts) > 1 else full_path
            imports.append(
                ImportRef(
                    module=mod_path,
                    source_file=file_path,
                    name=imp_name,
                    line=line_idx,
                    alias=alias,
                )
            )

    # 3. Block tracking helper via curly brace counting
    def find_block_end(start_idx: int) -> int:
        brace_count = 0
        found_open = False
        for i in range(start_idx - 1, len(lines)):
            line_str = lines[i]
            for ch in line_str:
                if ch == "{":
                    brace_count += 1
                    found_open = True
                elif ch == "}":
                    brace_count -= 1
                    if found_open and brace_count <= 0:
                        return i + 1
        return len(lines)

    # 4. Docstring helper (Javadoc / KDoc)
    def extract_docstring(start_idx: int) -> str | None:
        idx = start_idx - 2
        doc_lines: list[str] = []
        in_doc = False
        while idx >= 0:
            doc_line = lines[idx].strip()
            if doc_line.endswith("*/"):
                in_doc = True
            if in_doc:
                cleaned = doc_line.lstrip("/*").rstrip("*/").strip()
                if cleaned:
                    doc_lines.insert(0, cleaned)
                if doc_line.startswith("/**"):
                    break
            elif doc_line.startswith("@") or not doc_line:
                idx -= 1
                continue
            else:
                break
            idx -= 1
        return "\n".join(doc_lines) if doc_lines else None

    # Regex definitions for Class/Interface/Object/Record
    # Java: public class UserService extends BaseService implements IUserService, Auditable
    # Kotlin: class UserService(val repo: UserRepository) : BaseService(), IUserService
    class_pattern = re.compile(
        r"^(?:(?:public|private|protected|internal|abstract|final|open|sealed|data)\s+)*"
        r"(class|interface|enum|record|object|companion\s+object)\s+([A-Za-z0-9_]+)"
        r"(?:<[^>]+>)?"
        r"(?:\s*\([^)]*\))?"
        r"(?:\s+extends\s+([A-Za-z0-9_<>,\s]+?))?"
        r"(?:\s+implements\s+([A-Za-z0-9_<>,\s]+?))?"
        r"(?:\s*:\s*([^{]+))?"
        r"\s*\{"
    )

    # Spring / JAX-RS class annotation patterns
    request_mapping_re = re.compile(r'@RequestMapping\s*\(\s*(?:value\s*=\s*)?["\']([^"\']+)["\']')
    jaxrs_path_re = re.compile(r'@Path\s*\(\s*(?:value\s*=\s*)?["\']([^"\']+)["\']')
    spring_controller_re = re.compile(r'@(?:Rest)?Controller\b')

    # Method-level route patterns
    spring_route_method_re = re.compile(
        r'@(Get|Post|Put|Delete|Patch)Mapping(?:\s*\(\s*(?:(?:value|path)\s*=\s*)?(?:\{?\s*)?["\']([^"\']*)["\'](?:\s*\}?)?[^)]*\))?'
    )
    spring_request_mapping_method_re = re.compile(
        r'@RequestMapping\s*\(\s*(?:(?:value|path)\s*=\s*)?\{?["\']?([^"\'},]*)["\']?\}?(?:.*?method\s*=\s*(?:RequestMethod\.)?([A-Za-z]+))?[^)]*\)'
    )
    jaxrs_method_re = re.compile(r'@(GET|POST|PUT|DELETE|PATCH)\b')

    # Database Entity patterns
    entity_re = re.compile(r'@Entity\b')
    table_re = re.compile(r'@Table\s*\(\s*name\s*=\s*["\']([^"\']+)["\']')

    # Dependency Injection
    autowired_re = re.compile(r'@(?:Autowired|Inject)\b')

    # Local variable bindings
    binding_java_re = re.compile(r"^\s*(?:var|[A-Z][A-Za-z0-9_<>]+)\s+([a-z][A-Za-z0-9_]*)\s*=\s*([A-Za-z0-9_.]+\s*\([^;]*\));?")
    binding_kt_re = re.compile(r"^\s*(?:val|var)\s+([a-z][A-Za-z0-9_]*)(?:\s*:\s*[^=]+)?\s*=\s*([A-Za-z0-9_.]+\s*\([^;\n]*\))")

    # Enclosing scope tracking
    class ScopeContext:
        def __init__(self, name: str, kind: str, canonical_id: str, start: int, end: int, base_route: str = ""):
            self.name = name
            self.kind = kind
            self.canonical_id = canonical_id
            self.start = start
            self.end = end
            self.base_route = base_route

    scope_stack: list[ScopeContext] = []

    # First pass: Scan symbols, classes, methods
    line_idx = 1
    total_lines = len(lines)
    while line_idx <= total_lines:
        line = lines[line_idx - 1]
        clean = line.strip()

        # Check annotations in previous 5 lines for class
        pending_annotations: list[str] = []
        lookback = line_idx - 2
        while lookback >= 0 and lookback >= line_idx - 7:
            prev = lines[lookback].strip()
            if prev.startswith("@"):
                pending_annotations.insert(0, prev)
                lookback -= 1
            elif not prev or prev.startswith("//") or prev.endswith("*/"):
                lookback -= 1
            else:
                break

        full_annot_str = " ".join(pending_annotations) + " " + clean

        # Check for Class / Interface / Object
        m_cls = class_pattern.match(clean)
        if m_cls and not clean.startswith("//"):
            kind_kw = m_cls.group(1).replace("companion object", "companion_object")
            class_name = m_cls.group(2)
            end_line = find_block_end(line_idx)

            # Determine base route prefix from class annotations
            base_route = ""
            m_rm = request_mapping_re.search(full_annot_str)
            if m_rm:
                base_route = m_rm.group(1)
            else:
                m_path = jaxrs_path_re.search(full_annot_str)
                if m_path:
                    base_route = m_path.group(1)

            symbol_kind = "interface" if "interface" in kind_kw else ("enum" if "enum" in kind_kw else "class")
            canonical_id = f"jvm:{pkg_name}.{class_name}" if pkg_name else f"jvm:{class_name}"
            doc = extract_docstring(line_idx - len(pending_annotations))

            symbols.append(
                Symbol(
                    name=class_name,
                    qualified_name=f"{pkg_name}.{class_name}" if pkg_name else class_name,
                    kind=symbol_kind,
                    start_line=line_idx,
                    end_line=end_line,
                    file_path=file_path,
                    canonical_id=canonical_id,
                    language=lang_name,
                    module=pkg_name,
                    scope=pkg_name,
                    documentation=doc,
                    visibility="public" if ("public" in clean or is_kotlin) else "private",
                )
            )
            exports.append(canonical_id)

            if base_route:
                mounts.append(
                    RouterMountDetection(
                        framework="spring" if "Mapping" in full_annot_str or spring_controller_re.search(full_annot_str) else "jax-rs",
                        parent_router="",
                        child_router=class_name,
                        prefix=base_route,
                        file_path=file_path,
                        line=line_idx,
                        evidence=f"Controller class '{class_name}' mounted with base route '{base_route}'",
                    )
                )

            # Check Inheritance
            ext_part = m_cls.group(3)
            imp_part = m_cls.group(4)
            colon_part = m_cls.group(5)
            bases: list[str] = []
            if ext_part:
                bases.extend([b.strip().split("<")[0].strip() for b in ext_part.split(",") if b.strip()])
            if imp_part:
                bases.extend([b.strip().split("<")[0].strip() for b in imp_part.split(",") if b.strip()])
            if colon_part:
                # Kotlin style: BaseClass(), IFoo, IBar
                bases.extend([re.sub(r"\(.*?\)", "", b).strip().split("<")[0].strip() for b in colon_part.split(",") if b.strip()])

            for base in bases:
                if base and base != "{":
                    inheritance.append(
                        InheritanceRef(
                            source_symbol=class_name,
                            base_name=base,
                            relationship="EXTENDS",
                            source_file=file_path,
                            line=line_idx,
                            source_canonical_id=canonical_id,
                        )
                    )

            # Check Database Entity
            if entity_re.search(full_annot_str):
                tbl_m = table_re.search(full_annot_str)
                table_name = tbl_m.group(1) if tbl_m else class_name.lower() + "s"
                bindings.append(
                    BindingRef(
                        target_name=table_name,
                        file_path=file_path,
                        line=line_idx,
                        scope=canonical_id,
                        expr_kind="DATABASE_TABLE",
                        source_expr=f"@Entity class {class_name}",
                    )
                )

            scope_stack.append(ScopeContext(class_name, "class", canonical_id, line_idx, end_line, base_route=base_route))
            line_idx += 1
            continue

        # Check for Method / Function
        m_jprefix = re.match(
            r"^(?:(?:public|private|protected|static|final|abstract|synchronized)\s+)*"
            r"([A-Za-z0-9_<>\[\],\s]+?)\s+([A-Za-z0-9_]+)\s*\(",
            clean,
        )
        m_ktprefix = re.match(
            r"^(?:(?:public|private|protected|internal|override|suspend|open|inline)\s+)*"
            r"fun\s+(?:<[^>]+>\s+)?([A-Za-z0-9_]+)\s*\(",
            clean,
        )

        matched_method = False
        method_name = ""
        ret_type = ""
        raw_params = ""

        if not clean.startswith("//") and not clean.startswith("/*"):
            if m_jprefix:
                m_candidate_name = m_jprefix.group(2)
                if m_candidate_name not in ("if", "for", "while", "switch", "catch", "synchronized"):
                    # Find matching closing paren (supporting multi-line method signatures)
                    start_p = clean.find("(", m_jprefix.start(2))
                    depth = 1
                    end_p = -1
                    clean_scan = clean
                    for idx_c in range(start_p + 1, len(clean)):
                        if clean[idx_c] == "(":
                            depth += 1
                        elif clean[idx_c] == ")":
                            depth -= 1
                            if depth == 0:
                                end_p = idx_c
                                break
                    if end_p == -1:
                        combined_clean = clean
                        scan_idx = line_idx
                        while end_p == -1 and scan_idx < len(lines) and scan_idx < line_idx + 15:
                            next_l = lines[scan_idx].strip()
                            if next_l.startswith("//") or next_l.startswith("/*"):
                                scan_idx += 1
                                continue
                            prev_len = len(combined_clean)
                            combined_clean += " " + next_l
                            for idx_c in range(prev_len + 1, len(combined_clean)):
                                if combined_clean[idx_c] == "(":
                                    depth += 1
                                elif combined_clean[idx_c] == ")":
                                    depth -= 1
                                    if depth == 0:
                                        end_p = idx_c
                                        break
                            scan_idx += 1
                        if end_p != -1:
                            clean_scan = combined_clean

                    if end_p != -1:
                        remainder = clean_scan[end_p + 1:].strip()
                        if remainder.endswith("{") or not remainder or "throws" in remainder or remainder.endswith(";"):
                            matched_method = True
                            ret_type = m_jprefix.group(1).strip()
                            method_name = m_candidate_name
                            raw_params = clean_scan[start_p + 1:end_p].strip()
            elif m_ktprefix:
                m_candidate_name = m_ktprefix.group(1)
                start_p = clean.find("(", m_ktprefix.start(1))
                depth = 1
                end_p = -1
                clean_scan = clean
                for idx_c in range(start_p + 1, len(clean)):
                    if clean[idx_c] == "(":
                        depth += 1
                    elif clean[idx_c] == ")":
                        depth -= 1
                        if depth == 0:
                            end_p = idx_c
                            break
                if end_p == -1:
                    combined_clean = clean
                    scan_idx = line_idx
                    while end_p == -1 and scan_idx < len(lines) and scan_idx < line_idx + 15:
                        next_l = lines[scan_idx].strip()
                        if next_l.startswith("//") or next_l.startswith("/*"):
                            scan_idx += 1
                            continue
                        prev_len = len(combined_clean)
                        combined_clean += " " + next_l
                        for idx_c in range(prev_len + 1, len(combined_clean)):
                            if combined_clean[idx_c] == "(":
                                depth += 1
                            elif combined_clean[idx_c] == ")":
                                depth -= 1
                                if depth == 0:
                                    end_p = idx_c
                                    break
                        scan_idx += 1
                    if end_p != -1:
                        clean_scan = combined_clean

                if end_p != -1:
                    matched_method = True
                    method_name = m_candidate_name
                    raw_params = clean_scan[start_p + 1:end_p].strip()
                    remainder = clean_scan[end_p + 1:].strip()
                    m_ret = re.match(r"^:\s*([A-Za-z0-9_<>?\[\],\s]+)", remainder)
                    ret_type = m_ret.group(1).strip() if m_ret else "Unit"

        if matched_method:
            end_line = find_block_end(line_idx)
            current_parent = [s for s in scope_stack if s.kind == "class"]
            parent_scope = current_parent[-1] if current_parent else None
            class_prefix = f"{parent_scope.name}." if parent_scope else ""
            canonical_id = f"{parent_scope.canonical_id}.{method_name}" if parent_scope else (
                f"jvm:{pkg_name}.{method_name}" if pkg_name else f"jvm:{method_name}"
            )

            param_count = len([p for p in raw_params.split(",") if p.strip()]) if raw_params else 0
            sig = f"({raw_params}) -> {ret_type}"
            doc = extract_docstring(line_idx - len(pending_annotations))

            symbols.append(
                Symbol(
                    name=method_name,
                    qualified_name=f"{class_prefix}{method_name}",
                    kind="method" if parent_scope else "function",
                    start_line=line_idx,
                    end_line=end_line,
                    file_path=file_path,
                    canonical_id=canonical_id,
                    language=lang_name,
                    module=pkg_name,
                    scope=parent_scope.canonical_id if parent_scope else pkg_name,
                    signature=sig,
                    parameter_count=param_count,
                    return_type=ret_type,
                    documentation=doc,
                    visibility="public" if ("public" in clean or is_kotlin) else "private",
                )
            )
            exports.append(canonical_id)

            # Check HTTP Route Annotations on method
            # 1. Spring @GetMapping, @PostMapping, etc.
            m_spr = spring_route_method_re.search(full_annot_str)
            http_verb = ""
            sub_path = ""
            if m_spr:
                http_verb = m_spr.group(1).upper()
                sub_path = m_spr.group(2) or ""
            else:
                m_spr_req = spring_request_mapping_method_re.search(full_annot_str)
                if m_spr_req:
                    http_verb = (m_spr_req.group(2) or "GET").upper()
                    sub_path = m_spr_req.group(1) or ""
                    m_spr = m_spr_req

            if m_spr:
                base_p = parent_scope.base_route if parent_scope else ""
                full_route = join_route_prefixes(base_p, sub_path)

                routes.append(
                    RouteDetection(
                        framework="spring",
                        http_method=http_verb,
                        route_path=full_route,
                        normalized_route=re.sub(r"\{[^}]+\}", "*", full_route),
                        handler_name=canonical_id,
                        handler_canonical_id=canonical_id,
                        file_path=file_path,
                        line=line_idx,
                        confidence="HIGH",
                        evidence=f"Spring route '{full_route}' bound to {method_name}()",
                    )
                )

            # 2. JAX-RS @GET, @POST with optional @Path
            m_jax_verb = jaxrs_method_re.search(full_annot_str)
            if m_jax_verb:
                http_verb = m_jax_verb.group(1)
                m_p = jaxrs_path_re.search(full_annot_str)
                sub_path = m_p.group(1) if m_p else ""
                base_p = parent_scope.base_route if parent_scope else ""
                full_route = join_route_prefixes(base_p, sub_path)

                routes.append(
                    RouteDetection(
                        framework="jax-rs",
                        http_method=http_verb,
                        route_path=full_route,
                        normalized_route=re.sub(r"\{[^}]+\}", "*", full_route),
                        handler_name=canonical_id,
                        handler_canonical_id=canonical_id,
                        file_path=file_path,
                        line=line_idx,
                        confidence="HIGH",
                        evidence=f"JAX-RS @{http_verb} route '{full_route}' bound to {method_name}()",
                    )
                )

            scope_stack.append(ScopeContext(method_name, "method", canonical_id, line_idx, end_line))
            line_idx += 1
            continue

        line_idx += 1

    # Second pass: Extract Calls, Bindings, and Enclosing Callers within scopes
    for line_idx, line in enumerate(lines, start=1):
        clean = line.strip()
        if not clean or clean.startswith("//") or clean.startswith("/*") or clean.startswith("*"):
            continue

        # Find innermost enclosing scope for line
        active_scope: ScopeContext | None = None
        for sc in reversed(scope_stack):
            if sc.start <= line_idx <= sc.end:
                active_scope = sc
                break

        # 1. Local variable bindings
        m_b = binding_kt_re.match(clean) if is_kotlin else binding_java_re.match(clean)
        if m_b:
            var_name = m_b.group(1)
            src_expr = m_b.group(2)
            scope_str = active_scope.canonical_id if active_scope else (f"jvm:{pkg_name}" if pkg_name else "jvm:global")
            bindings.append(
                BindingRef(
                    target_name=var_name,
                    file_path=file_path,
                    line=line_idx,
                    scope=scope_str,
                    expr_kind="CALL" if "(" in src_expr else "IDENTIFIER",
                    source_expr=src_expr,
                )
            )

        # 2. Dependency injection field bindings
        if autowired_re.search(clean) or "@Inject" in clean:
            target_str = clean
            if not re.search(r";", clean) and line_idx < len(lines):
                target_str = clean + " " + lines[line_idx].strip()
            clean_target = re.sub(r"@\w+\s*", "", target_str)
            clean_target = re.sub(r"\b(?:public|private|protected|final)\s+", "", clean_target).strip()
            m_field = re.search(r"^([A-Z][A-Za-z0-9_<>]+)\s+([a-zA-Z0-9_]+);?", clean_target)
            if m_field:
                dep_type = m_field.group(1)
                dep_name = m_field.group(2)
                scope_str = active_scope.canonical_id if active_scope else (f"jvm:{pkg_name}" if pkg_name else "jvm:global")
                bindings.append(
                    BindingRef(
                        target_name=dep_name,
                        file_path=file_path,
                        line=line_idx,
                        scope=scope_str,
                        expr_kind="DEPENDENCY_INJECTION",
                        source_expr=f"@Autowired {dep_type}",
                    )
                )

        # 3. Caller-linked Method & Function Calls
        call_matches = re.finditer(r"\b([a-zA-Z0-9_]+)\.([a-zA-Z0-9_]+)\s*\(", clean)
        for cm in call_matches:
            receiver = cm.group(1)
            callee_name = cm.group(2)
            if receiver not in ("System", "out", "err", "log", "logger", "Arrays", "Collections", "Objects", "Math", "String"):
                calls.append(
                    CallRef(
                        source_file=file_path,
                        callee=callee_name,
                        qualified_callee=f"{receiver}.{callee_name}",
                        line=line_idx,
                        confidence="HIGH" if active_scope else "MEDIUM",
                        caller_symbol=active_scope.name if active_scope else None,
                        caller_canonical_id=active_scope.canonical_id if active_scope else (f"jvm:{pkg_name}" if pkg_name else "jvm:global"),
                        receiver=receiver,
                    )
                )

    return ParseResult(
        path=file_path,
        language=lang_name,
        source_hash=source_hash,
        symbols=tuple(symbols),
        imports=tuple(imports),
        calls=tuple(calls),
        inheritance=tuple(inheritance),
        routes=tuple(routes),
        mounts=tuple(mounts),
        bindings=tuple(bindings),
        exports=tuple(exports),
        parse_failed=False,
    )
