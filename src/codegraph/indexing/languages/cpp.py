"""Deep, production-grade C/C++ (.c, .cc, .cpp, .cxx, .h, .hpp, .hxx) language parser and framework resolver for CodeGraph.

Provides deep AST extraction for:
- Full scope tree: namespace -> class / struct / union / enum -> method / function
- Header includes (#include <...> and #include "...")
- Exact parameters, type signatures, return types, and parameter counts
- Doxygen comments (/** ... */ and /// ...) attached to symbols
- Class / struct inheritance hierarchies (InheritanceRef)
- Modern C++ Web & RPC routes:
  - Crow (CROW_ROUTE(app, "/path"))
  - Pistache (Routes::Get(router, "/path", ...))
  - Drogon (ADD_METHOD_TO(Class::method, "/path", Get))
  - cpp-httplib (svr.Get("/path", ...), svr.Post(...))
- Caller-to-callee enclosing linkage (CallRef with caller_canonical_id and receiver)
- Local variable bindings (BindingRef)
"""
from __future__ import annotations

import hashlib
import re
from typing import Any

from codegraph.frameworks import RouteDetection, RouterMountDetection
from codegraph.indexing.models import (
    BindingRef,
    CallRef,
    ImportRef,
    InheritanceRef,
    Symbol,
)


def parse_cpp(content: str, file_path: str) -> Any:
    """Parse C/C++ source code with deep scope tracking, caller linking, and C++ route resolution."""
    from codegraph.indexing.parser import ParseResult

    source_hash = hashlib.sha256(content.encode("utf-8", errors="replace")).hexdigest()
    lines = content.splitlines()
    is_header = file_path.lower().endswith((".h", ".hpp", ".hxx"))
    lang_name = "cpp_header" if is_header else "cpp"

    symbols: list[Symbol] = []
    imports: list[ImportRef] = []
    calls: list[CallRef] = []
    inheritance: list[InheritanceRef] = []
    routes: list[RouteDetection] = []
    mounts: list[RouterMountDetection] = []
    bindings: list[BindingRef] = []
    exports: list[str] = []

    # 1. Includes Extraction (#include <...> and #include "...")
    include_re = re.compile(r'^\s*#\s*include\s+([<"])([^>"]+)[>"]')
    for line_idx, line in enumerate(lines, start=1):
        clean = line.strip()
        m_inc = include_re.match(clean)
        if m_inc:
            inc_kind = m_inc.group(1)
            inc_path = m_inc.group(2)
            inc_name = inc_path.split("/")[-1]
            imports.append(
                ImportRef(
                    module=inc_path,
                    source_file=file_path,
                    name=inc_name,
                    line=line_idx,
                    alias="system" if inc_kind == "<" else "local",
                )
            )

    # 2. Block tracking helper via curly brace counting
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

    # 3. Doxygen comment extraction helper
    def extract_doxygen(start_idx: int) -> str | None:
        idx = start_idx - 2
        doc_lines: list[str] = []
        # Check single line /// comments above
        if idx >= 0 and lines[idx].strip().startswith("///"):
            while idx >= 0 and lines[idx].strip().startswith("///"):
                doc_lines.insert(0, lines[idx].strip().lstrip("/").strip())
                idx -= 1
            return "\n".join(doc_lines)

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
            elif not doc_line:
                idx -= 1
                continue
            else:
                break
            idx -= 1
        return "\n".join(doc_lines) if doc_lines else None

    # Namespace regex: namespace foo { or namespace foo::bar {
    namespace_re = re.compile(r"^\s*namespace\s+([A-Za-z0-9_:]+)\s*\{")

    # Class / Struct regex:
    # template <typename T> class MyClass : public BaseClass, private IOther
    # struct Point {
    class_struct_re = re.compile(
        r"^(?:template\s*<[^>]+>\s*)?"
        r"(?:(?:public|private|protected|virtual|final|alignas\([^)]+\))\s+)*"
        r"(class|struct|union|enum\s+class|enum)\s+([A-Za-z0-9_]+)"
        r"(?:\s*final)?"
        r"(?:\s*:\s*([^{;]+))?"
        r"\s*(?:\{|;)"
    )

    # Function / Method regex:
    # int add(int a, int b) {
    # virtual void ProcessRequest(const Request& req, Response* res) override {
    # auto compute(double x) -> double {
    func_method_re = re.compile(
        r"^(?:template\s*<[^>]+>\s*)?"
        r"(?:(?:static|inline|virtual|constexpr|explicit|friend|const)\s+)*"
        r"([A-Za-z0-9_:*&<>~]+(?:\s*[*&]+)?)\s+([A-Za-z0-9_:]+)\s*\(([^)]*)\)"
        r"(?:\s*const)?"
        r"(?:\s*noexcept)?"
        r"(?:\s*override|\s*final)?"
        r"(?:\s*->\s*[A-Za-z0-9_:*&<>]+)?"
        r"\s*\{"
    )

    # Local variable bindings:
    # auto client = std::make_shared<HttpClient>();
    # int count = get_total_count();
    binding_re = re.compile(r"^\s*(?:auto|[A-Za-z0-9_:<>&*]+)\s+([a-zA-Z0-9_]+)\s*=\s*([A-Za-z0-9_:.]+\s*\([^;]*\));")

    # Route patterns for C++ Web Frameworks:
    # Crow: CROW_ROUTE(app, "/api/users")([]() { ... })
    crow_route_re = re.compile(r'CROW_ROUTE\s*\(\s*([a-zA-Z0-9_]+)\s*,\s*["\']([^"\']+)["\']\s*\)')
    # Pistache: Routes::Get(router, "/api/users", ...);
    pistache_route_re = re.compile(r'Routes::(Get|Post|Put|Delete)\s*\(\s*([a-zA-Z0-9_]+)\s*,\s*["\']([^"\']+)["\']\s*,\s*Routes::bind\s*\(\s*&?([A-Za-z0-9_:]+)')
    # Drogon: ADD_METHOD_TO(UserController::getUsers, "/api/users", Get);
    drogon_route_re = re.compile(r'ADD_METHOD_TO\s*\(\s*([A-Za-z0-9_:]+)\s*,\s*["\']([^"\']+)["\']\s*,\s*([A-Za-z0-9_]+)\s*\)')
    # cpp-httplib: svr.Get("/api/users", handler);
    httplib_route_re = re.compile(r'([a-zA-Z0-9_]+)\.(Get|Post|Put|Delete|Patch)\s*\(\s*["\']([^"\']+)["\']\s*,\s*([^)]+)\)')

    class ScopeContext:
        def __init__(self, name: str, kind: str, canonical_id: str, start: int, end: int):
            self.name = name
            self.kind = kind
            self.canonical_id = canonical_id
            self.start = start
            self.end = end

    scope_stack: list[ScopeContext] = []

    # First pass: namespaces, classes, functions, routes
    line_idx = 1
    total_lines = len(lines)
    while line_idx <= total_lines:
        line = lines[line_idx - 1]
        clean = line.strip()

        if not clean or clean.startswith("//") or clean.startswith("/*") or clean.startswith("*"):
            line_idx += 1
            continue

        # Check for Namespace
        m_ns = namespace_re.match(clean)
        if m_ns:
            ns_name = m_ns.group(1)
            end_line = find_block_end(line_idx)
            current_ns = [s for s in scope_stack if s.kind == "namespace"]
            prefix = f"{current_ns[-1].canonical_id}::" if current_ns else "cpp:"
            canonical_id = f"{prefix}{ns_name}"
            scope_stack.append(ScopeContext(ns_name, "namespace", canonical_id, line_idx, end_line))
            line_idx += 1
            continue

        # Check for Class / Struct / Enum
        m_cls = class_struct_re.match(clean)
        if m_cls and not clean.endswith(";"):
            kw = m_cls.group(1)
            cls_name = m_cls.group(2)
            end_line = find_block_end(line_idx)

            active_ns = [s for s in scope_stack if s.kind in ("namespace", "class")]
            prefix = f"{active_ns[-1].canonical_id}::" if active_ns else "cpp:"
            canonical_id = f"{prefix}{cls_name}"
            doc = extract_doxygen(line_idx)

            kind = "struct" if "struct" in kw else ("enum" if "enum" in kw else "class")
            symbols.append(
                Symbol(
                    name=cls_name,
                    qualified_name=f"{prefix}{cls_name}".replace("cpp:", ""),
                    kind=kind,
                    start_line=line_idx,
                    end_line=end_line,
                    file_path=file_path,
                    canonical_id=canonical_id,
                    language=lang_name,
                    module=active_ns[-1].name if active_ns else "",
                    scope=active_ns[-1].canonical_id if active_ns else "cpp:global",
                    documentation=doc,
                    visibility="public",
                )
            )
            exports.append(canonical_id)

            # Check Inheritance
            inheritance_str = m_cls.group(3)
            if inheritance_str:
                for base in inheritance_str.split(","):
                    clean_b = re.sub(r"\b(public|private|protected|virtual)\b", "", base).strip()
                    if clean_b:
                        inheritance.append(
                            InheritanceRef(
                                source_symbol=cls_name,
                                base_name=clean_b,
                                relationship="EXTENDS",
                                source_file=file_path,
                                line=line_idx,
                                source_canonical_id=canonical_id,
                            )
                        )

            scope_stack.append(ScopeContext(cls_name, "class", canonical_id, line_idx, end_line))
            line_idx += 1
            continue

        # Check for Function / Method
        m_fn = func_method_re.match(clean)
        if m_fn:
            ret_type = m_fn.group(1).strip()
            fn_name = m_fn.group(2).strip()
            params = m_fn.group(3).strip()

            # Skip control structures
            if fn_name not in ("if", "for", "while", "switch", "catch"):
                end_line = find_block_end(line_idx)
                active_parent = [s for s in scope_stack if s.kind in ("class", "namespace")]
                prefix = f"{active_parent[-1].canonical_id}::" if active_parent else "cpp:"
                canonical_id = f"{prefix}{fn_name}" if "::" not in fn_name else f"cpp:{fn_name}"
                doc = extract_doxygen(line_idx)

                param_count = len([p for p in params.split(",") if p.strip()]) if params else 0
                sig = f"({params}) -> {ret_type}"

                is_method = any(s.kind == "class" for s in scope_stack) or "::" in fn_name
                symbols.append(
                    Symbol(
                        name=fn_name,
                        qualified_name=f"{prefix}{fn_name}".replace("cpp:", ""),
                        kind="method" if is_method else "function",
                        start_line=line_idx,
                        end_line=end_line,
                        file_path=file_path,
                        canonical_id=canonical_id,
                        language=lang_name,
                        module=active_parent[-1].name if active_parent else "",
                        scope=active_parent[-1].canonical_id if active_parent else "cpp:global",
                        signature=sig,
                        parameter_count=param_count,
                        return_type=ret_type,
                        documentation=doc,
                        visibility="public",
                    )
                )
                exports.append(canonical_id)

                scope_stack.append(ScopeContext(fn_name, "method" if is_method else "function", canonical_id, line_idx, end_line))
                line_idx += 1
                continue

        line_idx += 1

    # Second pass: C++ Web Framework Routes, Local Bindings, and Caller-to-Callee Calls
    for line_idx, line in enumerate(lines, start=1):
        clean = line.strip()
        if not clean or clean.startswith("//") or clean.startswith("/*") or clean.startswith("*"):
            continue

        # Find enclosing scope
        active_scope: ScopeContext | None = None
        for sc in reversed(scope_stack):
            if sc.start <= line_idx <= sc.end:
                active_scope = sc
                break

        # 1. Crow Routes: CROW_ROUTE(app, "/api/users")
        m_crow = crow_route_re.search(clean)
        if m_crow:
            route_path = m_crow.group(2)
            handler_id = active_scope.canonical_id if active_scope else f"cpp:{file_path}:{line_idx}"
            routes.append(
                RouteDetection(
                    framework="crow",
                    http_method="ANY",
                    route_path=route_path,
                    normalized_route=route_path,
                    handler_name=handler_id,
                    handler_canonical_id=handler_id,
                    file_path=file_path,
                    line=line_idx,
                    confidence="HIGH",
                    evidence=f"Crow route '{route_path}' registered on line {line_idx}",
                )
            )

        # 2. Pistache Routes: Routes::Get(router, "/api/users", Routes::bind(&Class::method))
        m_pis = pistache_route_re.search(clean)
        if m_pis:
            verb = m_pis.group(1).upper()
            route_path = m_pis.group(3)
            handler = m_pis.group(4)
            routes.append(
                RouteDetection(
                    framework="pistache",
                    http_method=verb,
                    route_path=route_path,
                    normalized_route=route_path,
                    handler_name=handler,
                    handler_canonical_id=f"cpp:{handler}",
                    file_path=file_path,
                    line=line_idx,
                    confidence="HIGH",
                    evidence=f"Pistache {verb} route '{route_path}' bound to {handler}",
                )
            )

        # 3. Drogon Routes: ADD_METHOD_TO(UserController::getUsers, "/api/users", Get)
        m_dro = drogon_route_re.search(clean)
        if m_dro:
            handler = m_dro.group(1)
            route_path = m_dro.group(2)
            verb = m_dro.group(3).upper()
            routes.append(
                RouteDetection(
                    framework="drogon",
                    http_method=verb,
                    route_path=route_path,
                    normalized_route=route_path,
                    handler_name=handler,
                    handler_canonical_id=f"cpp:{handler}",
                    file_path=file_path,
                    line=line_idx,
                    confidence="HIGH",
                    evidence=f"Drogon {verb} route '{route_path}' bound to {handler}",
                )
            )

        # 4. cpp-httplib Routes: svr.Get("/api/users", handler)
        m_http = httplib_route_re.search(clean)
        if m_http and m_http.group(2).upper() in ("GET", "POST", "PUT", "DELETE", "PATCH"):
            verb = m_http.group(2).upper()
            route_path = m_http.group(3)
            handler = m_http.group(4).strip()
            routes.append(
                RouteDetection(
                    framework="cpp-httplib",
                    http_method=verb,
                    route_path=route_path,
                    normalized_route=route_path,
                    handler_name=handler,
                    handler_canonical_id=f"cpp:{handler}" if not handler.startswith("[") else (active_scope.canonical_id if active_scope else f"cpp:{file_path}:{line_idx}"),
                    file_path=file_path,
                    line=line_idx,
                    confidence="HIGH",
                    evidence=f"cpp-httplib {verb} route '{route_path}' registered on line {line_idx}",
                )
            )

        # 5. Local variable bindings: auto x = ...
        m_bind = binding_re.match(clean)
        if m_bind:
            var_name = m_bind.group(1)
            src_expr = m_bind.group(2)
            scope_str = active_scope.canonical_id if active_scope else "cpp:global"
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

        # 6. Caller-linked Method & Function Calls
        # obj.method() or ptr->method()
        call_matches = re.finditer(r"\b([a-zA-Z0-9_]+)(?:\.|\->)([a-zA-Z0-9_]+)\s*\(", clean)
        for cm in call_matches:
            receiver = cm.group(1)
            callee_name = cm.group(2)
            if receiver not in ("std", "cout", "cin", "cerr", "endl", "this"):
                calls.append(
                    CallRef(
                        source_file=file_path,
                        callee=callee_name,
                        qualified_callee=f"{receiver}->{callee_name}",
                        line=line_idx,
                        confidence="HIGH" if active_scope else "MEDIUM",
                        caller_symbol=active_scope.name if active_scope else None,
                        caller_canonical_id=active_scope.canonical_id if active_scope else "cpp:global",
                        receiver=receiver,
                    )
                )

        # Free functions / namespace calls: ns::function()
        ns_call_matches = re.finditer(r"\b([a-zA-Z0-9_]+)::([a-zA-Z0-9_]+)\s*\(", clean)
        for ncm in ns_call_matches:
            ns = ncm.group(1)
            fn = ncm.group(2)
            if ns not in ("std", "boost", "crow", "Routes"):
                calls.append(
                    CallRef(
                        source_file=file_path,
                        callee=fn,
                        qualified_callee=f"{ns}::{fn}",
                        line=line_idx,
                        confidence="HIGH" if active_scope else "MEDIUM",
                        caller_symbol=active_scope.name if active_scope else None,
                        caller_canonical_id=active_scope.canonical_id if active_scope else "cpp:global",
                        receiver=ns,
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
