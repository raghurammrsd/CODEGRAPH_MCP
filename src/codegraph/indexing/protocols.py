"""Protocol Buffers (Protobuf / gRPC) and GraphQL Schema Parser for CodeGraph.

Extracts schema definitions and RPC services:
- Protobuf (.proto): extracts packages, messages, services, and RPC methods (rpc GetUser(Request) returns (Response))
- GraphQL (.graphql, .gql): extracts Query, Mutation, Subscription, and Object types
- Links RPC methods and GraphQL resolvers into CodeGraph's global route and endpoint topology
"""
from __future__ import annotations

import hashlib
import re
from typing import Any

from codegraph.frameworks import RouteDetection
from codegraph.indexing.models import Symbol


def parse_proto(content: str, file_path: str) -> Any:
    """Parse Protocol Buffers (.proto) source code into symbols and gRPC RPC route detections."""
    from codegraph.indexing.parser import ParseResult

    source_hash = hashlib.sha256(content.encode("utf-8", errors="replace")).hexdigest()
    lines = content.splitlines()

    symbols: list[Symbol] = []
    routes: list[RouteDetection] = []

    # 1. Package extraction: package order.v1;
    pkg_name = ""
    for line in lines[:30]:
        m_pkg = re.match(r"^\s*package\s+([A-Za-z0-9_.]+);", line)
        if m_pkg:
            pkg_name = m_pkg.group(1)
            break

    # 2. Service & Message Extraction
    service_re = re.compile(r"^\s*service\s+([A-Za-z0-9_]+)\s*\{")
    rpc_re = re.compile(r"^\s*rpc\s+([A-Za-z0-9_]+)\s*\(\s*([A-Za-z0-9_.]+)\s*\)\s*returns\s*\(\s*([A-Za-z0-9_.]+)\s*\);?")
    message_re = re.compile(r"^\s*message\s+([A-Za-z0-9_]+)\s*\{")

    current_service = ""
    for idx, line in enumerate(lines, start=1):
        clean = line.strip()
        if not clean or clean.startswith("//"):
            continue

        # Service
        m_svc = service_re.match(clean)
        if m_svc:
            current_service = m_svc.group(1)
            canon = f"proto:{pkg_name}.{current_service}" if pkg_name else f"proto:{current_service}"
            symbols.append(
                Symbol(
                    name=current_service,
                    qualified_name=f"{pkg_name}.{current_service}" if pkg_name else current_service,
                    kind="service",
                    start_line=idx,
                    end_line=idx,
                    file_path=file_path,
                    canonical_id=canon,
                    language="proto",
                    visibility="public",
                )
            )
            continue

        # RPC Method
        m_rpc = rpc_re.match(clean)
        if m_rpc and current_service:
            method_name = m_rpc.group(1)
            req_type = m_rpc.group(2)
            res_type = m_rpc.group(3)
            canon = f"proto:{pkg_name}.{current_service}.{method_name}" if pkg_name else f"proto:{current_service}.{method_name}"

            symbols.append(
                Symbol(
                    name=method_name,
                    qualified_name=f"{current_service}.{method_name}",
                    kind="rpc_method",
                    start_line=idx,
                    end_line=idx,
                    file_path=file_path,
                    canonical_id=canon,
                    language="proto",
                    signature=f"({req_type}) -> {res_type}",
                    parameter_count=1,
                    return_type=res_type,
                    visibility="public",
                )
            )

            # Register as gRPC route
            full_rpc_path = f"/{pkg_name}.{current_service}/{method_name}" if pkg_name else f"/{current_service}/{method_name}"
            routes.append(
                RouteDetection(
                    framework="grpc",
                    http_method="POST",
                    route_path=full_rpc_path,
                    normalized_route=full_rpc_path,
                    handler_name=canon,
                    handler_canonical_id=canon,
                    file_path=file_path,
                    line=idx,
                    confidence="HIGH",
                    evidence=f"gRPC RPC method '{full_rpc_path}' declared in {file_path}:{idx}",
                )
            )
            continue

        # Message definition
        m_msg = message_re.match(clean)
        if m_msg:
            msg_name = m_msg.group(1)
            canon = f"proto:{pkg_name}.{msg_name}" if pkg_name else f"proto:{msg_name}"
            symbols.append(
                Symbol(
                    name=msg_name,
                    qualified_name=f"{pkg_name}.{msg_name}" if pkg_name else msg_name,
                    kind="message",
                    start_line=idx,
                    end_line=idx,
                    file_path=file_path,
                    canonical_id=canon,
                    language="proto",
                    visibility="public",
                )
            )

    return ParseResult(
        path=file_path,
        language="proto",
        source_hash=source_hash,
        symbols=tuple(symbols),
        routes=tuple(routes),
        parse_failed=False,
    )


def parse_graphql(content: str, file_path: str) -> Any:
    """Parse GraphQL Schema (.graphql, .gql) into symbols and GraphQL query/mutation routes."""
    from codegraph.indexing.parser import ParseResult

    source_hash = hashlib.sha256(content.encode("utf-8", errors="replace")).hexdigest()
    lines = content.splitlines()

    symbols: list[Symbol] = []
    routes: list[RouteDetection] = []

    type_re = re.compile(r"^\s*type\s+([A-Za-z0-9_]+)\s*(?:implements\s+[^{]+)?\s*\{")
    field_re = re.compile(r"^\s*([A-Za-z0-9_]+)\s*(?:\([^)]*\))?\s*:\s*([A-Za-z0-9_!\[\]]+)")

    current_type = ""
    for idx, line in enumerate(lines, start=1):
        clean = line.strip()
        if not clean or clean.startswith("#"):
            continue

        m_t = type_re.match(clean)
        if m_t:
            current_type = m_t.group(1)
            symbols.append(
                Symbol(
                    name=current_type,
                    qualified_name=current_type,
                    kind="graphql_type",
                    start_line=idx,
                    end_line=idx,
                    file_path=file_path,
                    canonical_id=f"graphql:{current_type}",
                    language="graphql",
                    visibility="public",
                )
            )
            continue

        m_f = field_re.match(clean)
        if m_f and current_type:
            fname = m_f.group(1)
            ftype = m_f.group(2)
            qname = f"{current_type}.{fname}"
            symbols.append(
                Symbol(
                    name=fname,
                    qualified_name=qname,
                    kind="graphql_field",
                    start_line=idx,
                    end_line=idx,
                    file_path=file_path,
                    canonical_id=f"graphql:{qname}",
                    language="graphql",
                    return_type=ftype,
                    visibility="public",
                )
            )

            # If inside type Query or type Mutation, register as GraphQL route
            if current_type in ("Query", "Mutation", "Subscription"):
                routes.append(
                    RouteDetection(
                        framework="graphql",
                        http_method=current_type.upper(),
                        route_path=f"graphql:{current_type}.{fname}",
                        normalized_route=f"graphql:{fname}",
                        handler_name=qname,
                        handler_canonical_id=f"graphql:{qname}",
                        file_path=file_path,
                        line=idx,
                        confidence="HIGH",
                        evidence=f"GraphQL {current_type} field '{fname}' defined in {file_path}:{idx}",
                    )
                )

    return ParseResult(
        path=file_path,
        language="graphql",
        source_hash=source_hash,
        symbols=tuple(symbols),
        routes=tuple(routes),
        parse_failed=False,
    )
