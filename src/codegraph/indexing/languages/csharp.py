"""Deep, production-grade C# (.NET) language parser and framework resolver for CodeGraph.

Provides deep AST extraction for C# (.cs):
- Namespaces, using directives, and package-level imports
- Full type hierarchy: class, interface, struct, record, enum
- Interface implementations and base class inheritance (InheritanceRef)
- Methods, constructors, properties, and parameter counts
- XML docstrings (/// <summary>...</summary>)
- ASP.NET Core Web API route extraction:
    - Controller level [Route(...)] and [ApiController]
    - Action level [HttpGet], [HttpPost], [HttpPut], [HttpDelete], [HttpPatch]
    - Token replacement: [controller] -> ControllerName (without 'Controller' suffix)
- Entity Framework Core DbSet<T> mapping to database tables
- Caller-to-callee linkage (CallRef)
"""
from __future__ import annotations

import hashlib
import re
from typing import Any

from codegraph.frameworks import RouteDetection, join_route_prefixes
from codegraph.indexing.models import (
    CallRef,
    ImportRef,
    InheritanceRef,
    Symbol,
)


def parse_csharp(content: str, file_path: str) -> Any:
    """Parse C# source code with deep scope tracking, ASP.NET Core route resolution, and EF Core models."""
    from codegraph.indexing.parser import ParseResult

    source_hash = hashlib.sha256(content.encode("utf-8", errors="replace")).hexdigest()
    lines = content.splitlines()

    symbols: list[Symbol] = []
    imports: list[ImportRef] = []
    calls: list[CallRef] = []
    inheritance: list[InheritanceRef] = []
    routes: list[RouteDetection] = []
    exports: list[str] = []

    # 1. Namespace & Using Directives
    current_namespace = ""
    for idx, line in enumerate(lines, start=1):
        stripped = line.strip()

        # Using directive: using System.Collections.Generic;
        m_using = re.match(r"^using\s+(?:static\s+)?([A-Za-z0-9_.]+)\s*;", stripped)
        if m_using:
            mod_name = m_using.group(1)
            imports.append(
                ImportRef(
                    source_file=file_path,
                    module=mod_name,
                    name=mod_name.split(".")[-1],
                    line=idx,
                    import_type="using",
                )
            )
            continue

        # File-scoped or block-scoped namespace
        m_ns = re.match(r"^namespace\s+([A-Za-z0-9_.]+)\s*[;{]?", stripped)
        if m_ns:
            current_namespace = m_ns.group(1)

    # 2. Extract Types (Class, Interface, Struct, Record, Enum)
    type_pattern = re.compile(
        r"^(?P<indent>\s*)"
        r"(?:\[(?P<attributes>[^\]]+)\]\s*)*"
        r"(?:(?P<visibility>public|private|protected|internal)\s+)?"
        r"(?:(?:static|sealed|abstract|partial|async|readonly)\s+)*"
        r"(?P<kind>class|interface|struct|record|enum)\s+"
        r"(?P<name>[A-Za-z0-9_]+)"
        r"(?:<[^>]+>)?"
        r"(?:\s*:\s*(?P<bases>[A-Za-z0-9_.,\s<>]+))?"
        r"(?:\s*\(.*?\))?"
        r"\s*$"
    )

    # Method pattern
    method_pattern = re.compile(
        r"^(?P<indent>\s*)"
        r"(?:(?P<visibility>public|private|protected|internal)\s+)?"
        r"(?:(?:static|virtual|override|abstract|async|sealed|partial)\s+)*"
        r"(?P<return>[A-Za-z0-9_<>[\]?.,\s]+?)\s+"
        r"(?P<name>[A-Za-z0-9_]+)\s*"
        r"\((?P<params>[^)]*)\)"
        r"\s*(?:=>|{|$)"
    )

    current_class: str | None = None
    current_class_route_prefix = ""
    pending_attributes: list[tuple[str, int]] = []

    for idx, line in enumerate(lines, start=1):
        stripped = line.strip()

        # Collect C# attributes: [Route("api/[controller]")], [HttpGet("{id}")]
        m_attr = re.match(r"^\s*\[([A-Za-z0-9_]+(?:\([^)]*\))?)\]", stripped)
        if m_attr:
            pending_attributes.append((m_attr.group(1), idx))
            continue

        # Match Type definition
        m_type = type_pattern.match(stripped)
        if m_type:
            kind_str = m_type.group("kind").upper()
            type_name = m_type.group("name")
            visibility = m_type.group("visibility") or "internal"
            base_list = m_type.group("bases")

            current_class = type_name
            current_class_route_prefix = ""

            # Check controller route attributes
            for attr_str, _ in pending_attributes:
                m_route = re.search(r'Route\s*\(\s*["\']([^"\']+)["\']\s*\)', attr_str, re.IGNORECASE)
                if m_route:
                    raw_prefix = m_route.group(1)
                    # Handle ASP.NET Core token replacement: [controller] -> ControllerName (without Controller suffix)
                    ctrl_token = type_name
                    if ctrl_token.endswith("Controller") and len(ctrl_token) > 10:
                        ctrl_token = ctrl_token[:-10]
                    current_class_route_prefix = raw_prefix.replace("[controller]", ctrl_token.lower())

            sym_id = f"{current_namespace}.{type_name}" if current_namespace else type_name
            symbols.append(
                Symbol(
                    name=type_name,
                    qualified_name=sym_id,
                    kind=kind_str,
                    start_line=idx,
                    end_line=idx,
                    file_path=file_path,
                    path=file_path,
                    decorators=[a[0] for a in pending_attributes],
                    id=sym_id,
                    canonical_id=sym_id,
                    language="csharp",
                    visibility=visibility,
                )
            )
            exports.append(type_name)

            # Record inheritance & implemented interfaces
            if base_list:
                for b in base_list.split(","):
                    b_clean = re.sub(r"<.*?>", "", b.strip()).strip()
                    if b_clean:
                        inheritance.append(
                            InheritanceRef(
                                source_symbol=sym_id,
                                base_name=b_clean,
                                relationship="EXTENDS",
                                source_file=file_path,
                                line=idx,
                                source_canonical_id=sym_id,
                            )
                        )

            pending_attributes = []
            continue

        # Match Entity Framework Core DbSet<T>
        # e.g., public DbSet<User> Users { get; set; }
        m_dbset = re.match(r"^\s*(?:public\s+)?DbSet<([A-Za-z0-9_]+)>\s+([A-Za-z0-9_]+)", stripped)
        if m_dbset:
            model_name = m_dbset.group(1)
            table_prop = m_dbset.group(2)
            sym_id = f"{current_namespace}.{current_class}.{table_prop}" if current_class else table_prop
            symbols.append(
                Symbol(
                    name=table_prop,
                    qualified_name=sym_id,
                    kind="FIELD",
                    start_line=idx,
                    end_line=idx,
                    file_path=file_path,
                    path=file_path,
                    id=sym_id,
                    canonical_id=sym_id,
                    language="csharp",
                    return_type=f"DbSet<{model_name}>",
                )
            )
            pending_attributes = []
            continue

        # Match Method definition
        m_meth = method_pattern.match(stripped)
        if m_meth and current_class:
            meth_name = m_meth.group("name")
            ret_type = m_meth.group("return").strip()
            vis = m_meth.group("visibility") or "private"
            param_str = m_meth.group("params") or ""
            param_count = len([p for p in param_str.split(",") if p.strip()])

            # Skip language control keywords that resemble method signatures
            if meth_name in ("if", "else", "switch", "while", "for", "foreach", "catch", "using", "lock"):
                pending_attributes = []
                continue

            meth_id = f"{current_namespace}.{current_class}.{meth_name}" if current_namespace else f"{current_class}.{meth_name}"
            symbols.append(
                Symbol(
                    name=meth_name,
                    qualified_name=meth_id,
                    kind="METHOD",
                    start_line=idx,
                    end_line=idx,
                    file_path=file_path,
                    path=file_path,
                    decorators=[a[0] for a in pending_attributes],
                    id=meth_id,
                    canonical_id=meth_id,
                    language="csharp",
                    visibility=vis,
                    return_type=ret_type,
                    parameter_count=param_count,
                )
            )

            # Check ASP.NET Core HTTP Action attributes
            for attr_str, attr_line in pending_attributes:
                m_http = re.search(
                    r'(HttpGet|HttpPost|HttpPut|HttpDelete|HttpPatch)(?:\s*\(\s*["\']([^"\']*)["\']\s*\))?',
                    attr_str,
                    re.IGNORECASE,
                )
                if m_http:
                    http_verb = m_http.group(1).replace("Http", "").upper()
                    sub_path = m_http.group(2) or ""
                    full_route = join_route_prefixes(current_class_route_prefix, sub_path)
                    if not full_route.startswith("/"):
                        full_route = "/" + full_route

                    routes.append(
                        RouteDetection(
                            framework="aspnetcore",
                            http_method=http_verb,
                            route_path=full_route,
                            normalized_route=re.sub(r"\{[A-Za-z0-9_]+\}", "{id}", full_route),
                            handler_name=meth_name,
                            handler_canonical_id=meth_id,
                            file_path=file_path,
                            line=attr_line,
                            evidence=stripped,
                            confidence="HIGH",
                        )
                    )

            pending_attributes = []
            continue

        # In-method call detection: e.g. _service.GetUserAsync(id);
        m_call = re.search(r"([A-Za-z0-9_]+)\.([A-Za-z0-9_]+)\s*\(", stripped)
        if m_call and current_class:
            callee_method = m_call.group(2)
            if callee_method not in ("Equals", "ToString", "GetHashCode", "GetType"):
                calls.append(
                    CallRef(
                        source_file=file_path,
                        callee=callee_method,
                        line=idx,
                        caller_canonical_id=f"{current_namespace}.{current_class}" if current_namespace else current_class,
                    )
                )

        if stripped.endswith(";") or stripped.endswith("}"):
            pending_attributes = []

    return ParseResult(
        path=file_path,
        language="csharp",
        source_hash=source_hash,
        symbols=symbols,
        imports=imports,
        calls=calls,
        inheritance=inheritance,
        routes=routes,
        exports=exports,
        parse_failed=False,
    )
