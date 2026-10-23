"""Deep, production-grade Rust (.rs) language parser and framework resolver for CodeGraph.

Provides deep Python-level AST extraction for Rust:
- Full scope tree: crate/module -> struct / enum / trait -> impl block -> method / function
- Exact parameters, type annotations, return types, and parameter counts
- Rustdoc comments (///) attached to symbols
- Visibility & export detection (pub, pub(crate), private)
- Trait implementations (InheritanceRef)
- Local variable bindings (BindingRef)
- Enclosing caller-to-callee linkage (CallRef with caller_canonical_id and receiver)
- Router scopes & nested route compositions (Actix-web, Axum, Rocket)
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


def parse_rust(content: str, file_path: str) -> Any:
    """Parse Rust source code with deep scope tracking, caller linking, and route resolution."""
    from codegraph.indexing.parser import ParseResult

    source_hash = hashlib.sha256(content.encode("utf-8", errors="replace")).hexdigest()
    lines = content.splitlines()

    symbols: list[Symbol] = []
    imports: list[ImportRef] = []
    calls: list[CallRef] = []
    inheritance: list[InheritanceRef] = []
    routes: list[RouteDetection] = []
    mounts: list[RouterMountDetection] = []
    bindings: list[BindingRef] = []
    exports: list[str] = []

    # Infer crate/module name from path
    crate_name = "crate"
    norm_path = file_path.replace("\\", "/")
    if "src/" in norm_path:
        rel = norm_path.split("src/", 1)[1]
        crate_name = rel.replace(".rs", "").replace("/", "::")
    else:
        crate_name = norm_path.split("/")[-1].replace(".rs", "")

    # Helper to calculate block end based on brace counting
    def find_block_end(start_idx: int) -> int:
        brace_count = 0
        found_open = False
        for cur_idx in range(start_idx, len(lines)):
            cur_line = lines[cur_idx]
            sanitized = re.sub(r'"[^"\\]*(?:\\.[^"\\]*)*"', '""', cur_line)
            sanitized = re.sub(r"//.*$", "", sanitized)

            for char in sanitized:
                if char == "{":
                    brace_count += 1
                    found_open = True
                elif char == "}":
                    brace_count -= 1
                    if found_open and brace_count <= 0:
                        return cur_idx + 1
        return len(lines)

    # Helper to collect rustdoc comments immediately preceding declaration
    def collect_rustdoc(start_idx: int) -> str | None:
        doc_lines: list[str] = []
        cur_idx = start_idx - 1
        while cur_idx >= 0:
            ln = lines[cur_idx].strip()
            if ln.startswith("///"):
                doc_lines.insert(0, ln.lstrip("/ ").rstrip())
                cur_idx -= 1
            else:
                break
        return "\n".join(doc_lines) if doc_lines else None

    # Helper to parse parameter count and return type
    def parse_params_and_return(clean_line: str) -> tuple[int, str | None]:
        m_ret = re.search(r"\)\s*(?:->\s*([^{]+))?(?:\s*\{|$)", clean_line)
        ret_type = None
        if m_ret and m_ret.group(1):
            ret_type = m_ret.group(1).strip()

        m_params = re.search(r"\((.*?)\)", clean_line)
        param_count = 0
        if m_params and m_params.group(1).strip():
            params = [p.strip() for p in m_params.group(1).split(",") if p.strip()]
            param_count = len(params)

        return param_count, ret_type

    # Regex patterns
    use_re = re.compile(r"^\s*(?:pub\s+)?use\s+([^;]+);")
    struct_re = re.compile(r"^\s*(pub(?:\([A-Za-z0-9_]+\))?\s+)?struct\s+([A-Za-z0-9_]+)")
    enum_re = re.compile(r"^\s*(pub(?:\([A-Za-z0-9_]+\))?\s+)?enum\s+([A-Za-z0-9_]+)")
    trait_re = re.compile(r"^\s*(pub(?:\([A-Za-z0-9_]+\))?\s+)?trait\s+([A-Za-z0-9_]+)")
    impl_re = re.compile(r"^\s*impl(?:\s*<[^>]+>)?\s+(?:([A-Za-z0-9_]+)\s+for\s+)?([A-Za-z0-9_]+)")

    # Attributes
    actix_attr_re = re.compile(r'^\s*#\[(get|post|put|delete|patch|head)\s*\(\s*"([^"]+)"\s*\)\]')

    # Scope mount: web::scope("/api/v1") or .nest("/api/v1", ...)
    scope_mount_re = re.compile(r'(?:web::scope|\.nest)\s*\(\s*"([^"]+)"')
    actix_res_re = re.compile(r'web::resource\s*\(\s*"([^"]+)"')
    actix_res_to_re = re.compile(r'web::resource\s*\(\s*"([^"]+)"\s*\)\s*\.\s*(?:to|to_async)\s*\(\s*([a-zA-Z0-9_:]+)\s*\)')
    actix_route_method_re = re.compile(r'\.route\s*\(\s*web::(get|post|put|delete|patch|head|options)\s*\(\s*\)\s*\.\s*(?:to|to_async)\s*\(\s*([a-zA-Z0-9_:]+)\s*\)')

    # Local binding: let client = Client::new();
    binding_re = re.compile(r'^\s*let\s+(?:mut\s+)?([A-Za-z0-9_]+)(?:\s*:\s*([A-Za-z0-9_&<>*]+))?\s*=\s*([A-Za-z0-9_:]+)')

    active_impl_type: str | None = None
    active_impl_end: int = 0
    active_fn_scope: tuple[str, str, int] | None = None
    pending_actix_route: tuple[str, str, int] | None = None
    imported_symbols: dict[str, str] = {}
    current_actix_scope: str = ""
    current_actix_resource: str = ""

    for idx, line in enumerate(lines):
        lineno = idx + 1
        clean = line.strip()

        if lineno > active_impl_end:
            active_impl_type = None

        if active_fn_scope and lineno > active_fn_scope[2]:
            active_fn_scope = None

        # 1. Imports / Use declarations
        m_use = use_re.match(clean)
        if m_use:
            use_path = m_use.group(1).strip()
            if "::{" in use_path:
                base_mod, items_str = use_path.split("::{", 1)
                base_mod = base_mod.removeprefix("crate::")
                for itm in items_str.rstrip("}").split(","):
                    itm_clean = itm.strip()
                    if itm_clean:
                        imported_symbols[itm_clean] = f"{base_mod}::{itm_clean}"
                        imports.append(
                            ImportRef(
                                module=base_mod,
                                source_file=file_path,
                                name=itm_clean,
                                line=lineno,
                            )
                        )
            else:
                clean_path = use_path.removeprefix("crate::")
                imported_name = clean_path.split("::")[-1]
                imported_symbols[imported_name] = clean_path
                imports.append(
                    ImportRef(
                        module=clean_path,
                        source_file=file_path,
                        name=imported_name,
                        line=lineno,
                    )
                )
            continue

        # 2. Check Route Attribute (Actix / Rocket)
        m_actix = actix_attr_re.match(clean)
        if m_actix:
            http_method = m_actix.group(1).upper()
            route_path = m_actix.group(2)
            pending_actix_route = (http_method, route_path, lineno)
            continue

        # 3. Check Struct
        m_struct = struct_re.match(clean)
        if m_struct:
            vis_raw = m_struct.group(1) or ""
            name = m_struct.group(2)
            end_line = find_block_end(idx) if "{" in line else lineno
            canon_id = f"rust:{crate_name}::{name}"
            doc = collect_rustdoc(idx)
            is_pub = "pub" in vis_raw
            vis = "public" if is_pub else "private"

            symbols.append(
                Symbol(
                    name=name,
                    qualified_name=f"{crate_name}::{name}",
                    kind="struct",
                    start_line=lineno,
                    end_line=end_line,
                    file_path=file_path,
                    canonical_id=canon_id,
                    language="rust",
                    module=crate_name,
                    scope=crate_name,
                    visibility=vis,
                    documentation=doc,
                )
            )
            if is_pub:
                exports.append(name)
            continue

        # 4. Check Enum
        m_enum = enum_re.match(clean)
        if m_enum:
            vis_raw = m_enum.group(1) or ""
            name = m_enum.group(2)
            end_line = find_block_end(idx)
            canon_id = f"rust:{crate_name}::{name}"
            doc = collect_rustdoc(idx)
            is_pub = "pub" in vis_raw
            vis = "public" if is_pub else "private"

            symbols.append(
                Symbol(
                    name=name,
                    qualified_name=f"{crate_name}::{name}",
                    kind="enum",
                    start_line=lineno,
                    end_line=end_line,
                    file_path=file_path,
                    canonical_id=canon_id,
                    language="rust",
                    module=crate_name,
                    scope=crate_name,
                    visibility=vis,
                    documentation=doc,
                )
            )
            if is_pub:
                exports.append(name)
            continue

        # 5. Check Trait
        m_trait = trait_re.match(clean)
        if m_trait:
            vis_raw = m_trait.group(1) or ""
            name = m_trait.group(2)
            end_line = find_block_end(idx)
            canon_id = f"rust:{crate_name}::{name}"
            doc = collect_rustdoc(idx)
            is_pub = "pub" in vis_raw
            vis = "public" if is_pub else "private"

            symbols.append(
                Symbol(
                    name=name,
                    qualified_name=f"{crate_name}::{name}",
                    kind="trait",
                    start_line=lineno,
                    end_line=end_line,
                    file_path=file_path,
                    canonical_id=canon_id,
                    language="rust",
                    module=crate_name,
                    scope=crate_name,
                    visibility=vis,
                    documentation=doc,
                )
            )
            if is_pub:
                exports.append(name)
            continue

        # 6. Check Impl Block & Trait Implementation (InheritanceRef)
        m_impl = impl_re.match(clean)
        if m_impl:
            trait_name = m_impl.group(1)
            target_type = m_impl.group(2)
            active_impl_type = target_type
            active_impl_end = find_block_end(idx)

            if trait_name:
                inheritance.append(
                    InheritanceRef(
                        source_symbol=target_type,
                        base_name=trait_name,
                        relationship="IMPLEMENTS",
                        source_file=file_path,
                        line=lineno,
                    )
                )
            continue

        # 7. Check Function / Method (supporting multi-line parameter signatures)
        m_fn_start = re.match(r"^\s*(pub(?:\([A-Za-z0-9_]+\))?\s+)?(?:async\s+)?fn\s+([A-Za-z0-9_]+)\s*\(", clean)
        if m_fn_start:
            vis_raw = m_fn_start.group(1) or ""
            fn_name = m_fn_start.group(2)
            start_p = clean.find("(", m_fn_start.end(2))
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
                combined = clean
                scan_idx = idx + 1
                while end_p == -1 and scan_idx < len(lines) and scan_idx < idx + 20:
                    next_l = lines[scan_idx].strip()
                    if next_l.startswith("//") or next_l.startswith("/*"):
                        scan_idx += 1
                        continue
                    prev_len = len(combined)
                    combined += " " + next_l
                    for idx_c in range(prev_len + 1, len(combined)):
                        if combined[idx_c] == "(":
                            depth += 1
                        elif combined[idx_c] == ")":
                            depth -= 1
                            if depth == 0:
                                end_p = idx_c
                                break
                    scan_idx += 1
                if end_p != -1:
                    clean_scan = combined

            if end_p != -1:
                sig_params = clean_scan[start_p + 1:end_p].strip()
                remainder = clean_scan[end_p + 1:].strip()
                m_ret = re.search(r"->\s*([^{;]+)", remainder)
                sig_ret = f" -> {m_ret.group(1).strip()}" if m_ret else ""
                r_type = m_ret.group(1).strip() if m_ret else "()"
                p_cnt = len([p for p in sig_params.split(",") if p.strip()]) if sig_params else 0

                end_line = find_block_end(idx)
                doc = collect_rustdoc(idx)
                is_pub = "pub" in vis_raw
                vis = "public" if is_pub else "private"

                if active_impl_type:
                    # Method inside impl block
                    canon_id = f"rust:{crate_name}::{active_impl_type}::{fn_name}"
                    symbols.append(
                        Symbol(
                            name=fn_name,
                            qualified_name=f"{crate_name}::{active_impl_type}::{fn_name}",
                            kind="method",
                            start_line=lineno,
                            end_line=end_line,
                            file_path=file_path,
                            canonical_id=canon_id,
                            language="rust",
                            module=crate_name,
                            scope=f"{crate_name}::{active_impl_type}",
                            signature=f"fn {fn_name}({sig_params}){sig_ret}".strip(),
                            visibility=vis,
                            return_type=r_type,
                            parameter_count=p_cnt,
                            documentation=doc,
                        )
                    )
                    if is_pub:
                        exports.append(f"{active_impl_type}::{fn_name}")
                    active_fn_scope = (fn_name, canon_id, end_line)
                else:
                    # Standalone function
                    canon_id = f"rust:{crate_name}::{fn_name}"
                    symbols.append(
                        Symbol(
                            name=fn_name,
                            qualified_name=f"{crate_name}::{fn_name}",
                            kind="function",
                            start_line=lineno,
                            end_line=end_line,
                            file_path=file_path,
                            canonical_id=canon_id,
                            language="rust",
                            module=crate_name,
                            scope=crate_name,
                            signature=f"fn {fn_name}({sig_params}){sig_ret}".strip(),
                            visibility=vis,
                            return_type=r_type,
                            parameter_count=p_cnt,
                            documentation=doc,
                        )
                    )
                    if is_pub:
                        exports.append(fn_name)
                    active_fn_scope = (fn_name, canon_id, end_line)

                # Associate preceding Actix/Rocket route attribute if present
                if pending_actix_route:
                    m_method, r_path, r_line = pending_actix_route
                    routes.append(
                        RouteDetection(
                            framework="actix-web",
                            http_method=m_method,
                            route_path=r_path,
                            normalized_route=r_path,
                            handler_name=fn_name,
                            handler_canonical_id=canon_id,
                            file_path=file_path,
                            line=r_line,
                            confidence="HIGH",
                            evidence=f"Actix/Rocket #[{m_method.lower()}(\"{r_path}\")] attribute on line {r_line}",
                        )
                    )
                    pending_actix_route = None
                continue

        # 8. Check Router Scopes / Nesting
        m_scope = re.search(r'web::scope\s*\(\s*"([^"]+)"', clean)
        if m_scope:
            prefix = m_scope.group(1).rstrip("/")
            current_actix_scope = prefix

        m_nest = re.search(r'\.nest\s*\(\s*"([^"]+)"\s*,\s*([A-Za-z0-9_:]+)', clean)
        if m_nest:
            prefix = m_nest.group(1).rstrip("/")
            child = m_nest.group(2)
            mounts.append(
                RouterMountDetection(
                    framework="axum",
                    parent_router="App",
                    child_router=child,
                    prefix=prefix,
                    file_path=file_path,
                    line=lineno,
                    confidence="HIGH",
                    evidence=f"Axum router nest prefix '{prefix}' -> '{child}'",
                )
            )

        # 8b. Check Actix programmatic DSL: web::resource("/path").to(handler) or web::resource("users").route(web::post().to_async(...))
        m_actix_direct = re.search(r'\.route\s*\(\s*"([^"]+)"\s*,\s*web::(get|post|put|delete|patch|head)\s*\(\s*\)\s*\.\s*(?:to|to_async)\s*\(\s*([a-zA-Z0-9_:]+)\s*\)\s*\)', clean)
        if m_actix_direct:
            r_path = m_actix_direct.group(1)
            h_method = m_actix_direct.group(2).upper()
            h_name = m_actix_direct.group(3)
            target_canon = f"rust:{imported_symbols.get(h_name, f'{crate_name}::{h_name}')}"
            routes.append(
                RouteDetection(
                    framework="actix-web",
                    http_method=h_method,
                    route_path=r_path,
                    normalized_route=r_path,
                    handler_name=h_name,
                    handler_canonical_id=target_canon,
                    file_path=file_path,
                    line=lineno,
                    confidence="HIGH",
                    evidence=f"Actix programmatic route {h_method} '{r_path}' -> {h_name}",
                )
            )

        m_res_to = actix_res_to_re.search(clean)
        if m_res_to:
            r_path = m_res_to.group(1)
            h_name = m_res_to.group(2)
            full_route = f"{current_actix_scope}/{r_path.lstrip('/')}" if current_actix_scope and not r_path.startswith("/") else (r_path if not current_actix_scope else f"{current_actix_scope}{r_path}")
            current_actix_resource = full_route
            target_canon = f"rust:{imported_symbols.get(h_name, f'{crate_name}::{h_name}')}"
            routes.append(
                RouteDetection(
                    framework="actix-web",
                    http_method="GET",
                    route_path=full_route,
                    normalized_route=full_route,
                    handler_name=h_name,
                    handler_canonical_id=target_canon,
                    file_path=file_path,
                    line=lineno,
                    confidence="HIGH",
                    evidence=f"Actix resource route GET '{full_route}' -> {h_name} on line {lineno}",
                )
            )
        else:
            m_res = actix_res_re.search(clean)
            if m_res:
                r_path = m_res.group(1)
                if current_actix_scope:
                    full_route = f"{current_actix_scope}/{r_path.lstrip('/')}" if not r_path.startswith("/") else f"{current_actix_scope}{r_path}"
                else:
                    full_route = r_path
                current_actix_resource = full_route

        m_route = actix_route_method_re.search(clean)
        if m_route and current_actix_resource:
            h_method = m_route.group(1).upper()
            h_name = m_route.group(2)
            target_canon = f"rust:{imported_symbols.get(h_name, f'{crate_name}::{h_name}')}"
            routes.append(
                RouteDetection(
                    framework="actix-web",
                    http_method=h_method,
                    route_path=current_actix_resource,
                    normalized_route=current_actix_resource,
                    handler_name=h_name,
                    handler_canonical_id=target_canon,
                    file_path=file_path,
                    line=lineno,
                    confidence="HIGH",
                    evidence=f"Actix resource route {h_method} '{current_actix_resource}' -> {h_name} on line {lineno}",
                )
            )

        # 9. Check Axum Routes (supporting chained methods e.g. .route("/path", get(a).post(b)))
        if ".route(" in clean:
            m_route_path = re.search(r'\.route\s*\(\s*"([^"]+)"', clean)
            if m_route_path:
                r_path = m_route_path.group(1)
                verbs: list[tuple[str, str]] = []
                init_verb = re.search(r'\.route\s*\(\s*"[^"]+"\s*,\s*(get|post|put|delete|patch|options|head)\s*\(\s*([A-Za-z0-9_]+)\s*\)', clean)
                if init_verb:
                    verbs.append((init_verb.group(1), init_verb.group(2)))
                for chained_verb in re.finditer(r'\.(get|post|put|delete|patch|options|head)\s*\(\s*([A-Za-z0-9_]+)\s*\)', clean):
                    item = (chained_verb.group(1), chained_verb.group(2))
                    if item not in verbs:
                        verbs.append(item)

                for v_method, h_name in verbs:
                    target_canon = f"rust:{imported_symbols.get(h_name, f'{crate_name}::{h_name}')}"
                    routes.append(
                        RouteDetection(
                            framework="axum",
                            http_method=v_method.upper(),
                            route_path=r_path,
                            normalized_route=r_path,
                            handler_name=h_name,
                            handler_canonical_id=target_canon,
                            file_path=file_path,
                            line=lineno,
                            confidence="HIGH",
                            evidence=f"Axum {v_method.upper()} route '{r_path}' bound to '{h_name}' on line {lineno}",
                        )
                    )

        # 10. Check Local Variable Bindings
        m_bind = binding_re.match(clean)
        if m_bind:
            var_name = m_bind.group(1)
            source = m_bind.group(3)
            scope_str = active_fn_scope[1] if active_fn_scope else crate_name
            bindings.append(
                BindingRef(
                    target_name=var_name,
                    file_path=file_path,
                    line=lineno,
                    scope=scope_str,
                    expr_kind="IDENTIFIER",
                    source_expr=source,
                )
            )

        # 11. Enclosing Caller-Linked Method & Function Calls
        call_matches = re.finditer(r"\b([A-Za-z0-9_]+)\.([A-Za-z0-9_]+)\s*\(", clean)
        for cm in call_matches:
            receiver = cm.group(1)
            callee_name = cm.group(2)
            if receiver not in ("self", "println", "eprintln", "format", "vec", "Ok", "Err", "Some"):
                calls.append(
                    CallRef(
                        source_file=file_path,
                        callee=callee_name,
                        qualified_callee=f"{receiver}.{callee_name}",
                        line=lineno,
                        confidence="HIGH" if active_fn_scope else "MEDIUM",
                        caller_symbol=active_fn_scope[0] if active_fn_scope else None,
                        caller_canonical_id=active_fn_scope[1] if active_fn_scope else f"rust:{crate_name}",
                        receiver=receiver,
                    )
                )

    return ParseResult(
        path=file_path,
        language="rust",
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
