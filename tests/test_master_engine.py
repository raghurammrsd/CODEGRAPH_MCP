"""Comprehensive unit tests for the 11 Next-Gen Core Engine Features."""
from __future__ import annotations

import sqlite3
from pathlib import Path

from codegraph.architecture_rules import evaluate_architecture_rules
from codegraph.changelog import generate_semantic_changelog
from codegraph.dataflow_propagation import propagate_interprocedural_dataflow
from codegraph.graph_csr import CSRGraph
from codegraph.incremental import apply_incremental_file_update
from codegraph.indexing.protocols import parse_graphql, parse_proto
from codegraph.polymorphism import resolve_polymorphic_callees
from codegraph.reachability import compute_di_aware_reachability
from codegraph.reachability_index import TransitiveReachabilityIndex
from codegraph.sandbox import evaluate_speculative_patch
from codegraph.security.supply_chain import analyze_supply_chain


def test_speculative_sandbox(tmp_path: Path) -> None:
    main_py = tmp_path / "main.py"
    main_py.write_text("def fetch_user(user_id, token):\n    return user_id\n", encoding="utf-8")

    # In-memory candidate patch: removes 'token' parameter
    candidate_patches = {
        "main.py": "def fetch_user(user_id):\n    return user_id\n",
    }
    rep = evaluate_speculative_patch(tmp_path, candidate_patches)
    assert not rep.is_safe  # Parameter removed is flagged!
    assert len(rep.contract_breaks) >= 1
    assert rep.contract_breaks[0].break_type == "PARAMETER_REMOVED"


def test_declarative_architecture_rules(tmp_path: Path) -> None:
    con = sqlite3.connect(":memory:")
    con.execute("CREATE TABLE imports (source_file TEXT, module TEXT, name TEXT, line INT);")
    # Controller illegally imports db model
    con.execute("INSERT INTO imports VALUES ('src/api/user_controller.py', 'src.db.models', 'User', 5);")
    con.commit()

    rules = [
        {
            "name": "no-db-in-controller",
            "source_pattern": "*controller*",
            "cannot_import": ["*db*"],
            "message": "Controller cannot touch db directly",
        }
    ]
    rep = evaluate_architecture_rules(tmp_path, con, rules=rules)
    assert rep.status == "VIOLATIONS_DETECTED"
    assert rep.violations_count == 1
    assert rep.violations[0].rule_name == "no-db-in-controller"
    con.close()


def test_di_aware_reachability(tmp_path: Path) -> None:
    con = sqlite3.connect(":memory:")
    con.execute("CREATE TABLE symbols (id TEXT, name TEXT, canonical_id TEXT, kind TEXT, path TEXT, start_line INT);")
    con.execute("CREATE TABLE routes (handler_name TEXT, handler_canonical_id TEXT);")
    con.execute("CREATE TABLE calls (caller_canonical_id TEXT, callee TEXT);")
    con.execute("CREATE TABLE inheritance (source_canonical_id TEXT, base_name TEXT);")
    con.execute("CREATE TABLE bindings (scope TEXT, target_name TEXT, expr_kind TEXT);")

    # Symbols: root_handler, helper_service, dead_function
    con.execute("INSERT INTO symbols VALUES ('1', 'root_handler', 'sym:root', 'function', 'src/api.py', 10);")
    con.execute("INSERT INTO symbols VALUES ('2', 'helper_service', 'sym:helper', 'function', 'src/service.py', 20);")
    con.execute("INSERT INTO symbols VALUES ('3', 'dead_code_func', 'sym:dead', 'function', 'src/old.py', 30);")

    # Route reaches root_handler
    con.execute("INSERT INTO routes VALUES ('root_handler', 'sym:root');")
    # root_handler calls helper_service
    con.execute("INSERT INTO calls VALUES ('sym:root', 'helper_service');")
    con.commit()

    rep = compute_di_aware_reachability(tmp_path, con)
    assert rep.total_symbols == 3
    assert rep.reachable_count == 2
    assert rep.unreachable_count == 1
    assert rep.unreachable_symbols[0].name == "dead_code_func"
    con.close()


def test_csr_graph_and_reachability_bitset() -> None:
    edges = [
        ("A", "B", "CALLS"),
        ("B", "C", "CALLS"),
        ("C", "D", "CALLS"),
        ("X", "Y", "CALLS"),
    ]
    csr = CSRGraph.build_from_edges(edges)
    assert csr.node_count == 6
    assert csr.edge_count == 4

    path = csr.shortest_path("A", "D")
    assert path == ["A", "B", "C", "D"]

    no_path = csr.shortest_path("A", "Y")
    assert no_path is None

    blast = csr.blast_radius("A", max_depth=3)
    assert "B" in blast
    assert "C" in blast
    assert "D" in blast

    # O(1) bitset
    bitset_idx = TransitiveReachabilityIndex.build_from_csr(csr)
    assert bitset_idx.can_reach("A", "D") is True
    assert bitset_idx.can_reach("A", "Y") is False
    assert "D" in bitset_idx.get_descendants("A")


def test_incremental_invalidation(tmp_path: Path) -> None:
    src_file = tmp_path / "calc.py"
    src_file.write_text("def add(a, b):\n    return a + b\n\ndef sub(a, b):\n    return a - b\n", encoding="utf-8")

    con = sqlite3.connect(":memory:")
    con.execute("CREATE TABLE symbols (name TEXT, canonical_id TEXT, start_line INT, end_line INT, path TEXT);")
    con.execute("CREATE TABLE calls (source_file TEXT, callee TEXT, caller_canonical_id TEXT, line INT);")
    con.execute("CREATE TABLE imports (source_file TEXT, module TEXT, name TEXT, line INT);")
    con.execute("CREATE TABLE routes (framework TEXT, http_method TEXT, route_path TEXT, normalized_route TEXT, handler_name TEXT, file_path TEXT, line INT);")
    con.execute("INSERT INTO symbols VALUES ('add', 'py:calc.add', 1, 2, 'calc.py');")
    con.execute("INSERT INTO symbols VALUES ('sub', 'py:calc.sub', 4, 5, 'calc.py');")
    con.commit()

    # Modify sub() by adding a docstring
    src_file.write_text("def add(a, b):\n    return a + b\n\ndef sub(a, b):\n    '''Doc'''\n    return a - b\n", encoding="utf-8")

    rep = apply_incremental_file_update(tmp_path, "calc.py", con)
    assert "add" in rep.unchanged_symbols
    assert "sub" in rep.modified_symbols
    con.close()


def test_polymorphic_resolver() -> None:
    con = sqlite3.connect(":memory:")
    con.execute("CREATE TABLE inheritance (source_symbol TEXT, source_canonical_id TEXT, base_name TEXT, source_file TEXT, line INT);")
    con.execute("CREATE TABLE symbols (name TEXT, qualified_name TEXT, canonical_id TEXT, path TEXT, start_line INT);")

    con.execute("INSERT INTO inheritance VALUES ('StripeProcessor', 'jvm:Stripe', 'PaymentGateway', 'Stripe.java', 10);")
    con.execute("INSERT INTO symbols VALUES ('pay', 'StripeProcessor.pay', 'jvm:Stripe.pay', 'Stripe.java', 20);")
    con.commit()

    rep = resolve_polymorphic_callees(con, "PaymentGateway", "pay")
    assert rep.total_implementations == 1
    assert rep.implementations[0].implementing_class == "StripeProcessor"
    assert rep.implementations[0].method_canonical_id == "jvm:Stripe.pay"
    con.close()


def test_dataflow_propagation() -> None:
    con = sqlite3.connect(":memory:")
    con.execute("CREATE TABLE symbols (name TEXT, canonical_id TEXT, signature TEXT, return_type TEXT, path TEXT, start_line INT);")
    con.execute("CREATE TABLE calls (caller_symbol TEXT, caller_canonical_id TEXT, callee TEXT, source_file TEXT, line INT);")

    con.execute("INSERT INTO symbols VALUES ('find_user', 'py:find_user', '() -> Optional[User]', 'Optional[User]', 'user.py', 10);")
    con.execute("INSERT INTO calls VALUES ('get_profile', 'py:get_profile', 'find_user', 'profile.py', 42);")
    con.commit()

    rep = propagate_interprocedural_dataflow(con, "find_user")
    assert rep.is_nullable
    assert len(rep.nullability_warnings) == 1
    assert "find_user" in rep.nullability_warnings[0].message
    con.close()


def test_protocols_parser() -> None:
    proto_code = '''syntax = "proto3";
package order.v1;

service OrderService {
    rpc CreateOrder (CreateOrderRequest) returns (OrderResponse);
}

message CreateOrderRequest {
    string item_id = 1;
}
'''
    res = parse_proto(proto_code, "order.proto")
    assert not res.parse_failed
    assert len(res.symbols) == 3
    assert len(res.routes) == 1
    assert res.routes[0].route_path == "/order.v1.OrderService/CreateOrder"

    gql_code = '''type Query {
    getUser(id: ID!): User
}

type User {
    id: ID!
    email: String!
}
'''
    gql_res = parse_graphql(gql_code, "schema.graphql")
    assert not gql_res.parse_failed
    assert len(gql_res.routes) == 1
    assert gql_res.routes[0].route_path == "graphql:Query.getUser"


def test_supply_chain_analysis(tmp_path: Path) -> None:
    pkg_json = tmp_path / "package.json"
    pkg_json.write_text('{"dependencies": {"axios": "^1.0.0", "lodash": "^4.17.21"}}', encoding="utf-8")

    con = sqlite3.connect(":memory:")
    con.execute("CREATE TABLE imports (module TEXT, name TEXT, source_file TEXT, line INT);")
    con.execute("INSERT INTO imports VALUES ('axios', 'get', 'src/api.ts', 15);")
    con.commit()

    rep = analyze_supply_chain(tmp_path, con=con)
    assert rep.total_dependencies == 2
    assert rep.actively_imported_count == 1
    assert rep.total_call_sites == 1
    assert rep.packages[0].name == "axios"
    assert rep.packages[0].is_actively_imported is True
    con.close()


def test_semantic_changelog(tmp_path: Path) -> None:
    rep = generate_semantic_changelog(tmp_path, base_ref="HEAD~1", head_ref="HEAD")
    assert isinstance(rep.markdown_changelog, str)
    assert rep.total_changes >= 0


def test_production_sqlite_schema_compatibility(tmp_path: Path) -> None:
    """Verify v3.0 SQLite schema compatibility across reachability, dataflow, and architecture rules."""
    con = sqlite3.connect(":memory:")

    # 1. framework_routes table schema
    con.execute("""
        CREATE TABLE framework_routes (
            endpoint_id TEXT PRIMARY KEY,
            framework TEXT,
            http_method TEXT,
            route_path TEXT,
            normalized_route TEXT,
            handler_name TEXT,
            handler_canonical_id TEXT,
            file_path TEXT,
            line INT
        );
    """)
    con.execute("""
        CREATE TABLE symbols (
            id TEXT,
            name TEXT,
            canonical_id TEXT,
            kind TEXT,
            path TEXT,
            start_line INT,
            signature TEXT,
            return_type TEXT
        );
    """)
    con.execute("""
        CREATE TABLE calls (
            source_path TEXT,
            callee TEXT,
            line INT,
            source_symbol_id TEXT
        );
    """)
    con.execute("""
        CREATE TABLE imports (
            source_path TEXT,
            module TEXT,
            name TEXT,
            imported_module TEXT,
            line INT
        );
    """)
    con.execute("CREATE TABLE inheritance (source_canonical_id TEXT, base_name TEXT);")
    con.execute("CREATE TABLE bindings (scope TEXT, target_name TEXT, expr_kind TEXT);")

    # Insert test data
    con.execute("INSERT INTO symbols VALUES ('s1', 'get_order', 'sym:get_order', 'function', 'src/orders.py', 1, '() -> Optional[Order]', 'Optional[Order]');")
    con.execute("INSERT INTO symbols VALUES ('s2', 'render_view', 'sym:render_view', 'function', 'src/view.py', 10, '() -> None', 'None');")
    con.execute("INSERT INTO framework_routes VALUES ('ep1', 'fastapi', 'GET', '/orders', '/orders', 'get_order', 'sym:get_order', 'src/orders.py', 1);")
    con.execute("INSERT INTO calls VALUES ('src/view.py', 'get_order', 12, 's2');")
    con.execute("INSERT INTO imports VALUES ('src/view.py', 'db.models', 'Order', 'db.models', 2);")
    con.commit()

    # Reachability with framework_routes
    reach_rep = compute_di_aware_reachability(tmp_path, con)
    assert reach_rep.reachable_count >= 1

    # Dataflow with source_symbol_id
    df_rep = propagate_interprocedural_dataflow(con, "get_order")
    assert df_rep.is_nullable is True
    assert len(df_rep.nullability_warnings) == 1
    assert df_rep.nullability_warnings[0].caller_symbol == "render_view"

    # Architecture rules with source_path
    rules = [{"name": "no-db-in-view", "source_pattern": "src/view.*", "cannot_import": ["db.models*"], "message": "View cannot import models"}]
    arch_rep = evaluate_architecture_rules(tmp_path, con, rules=rules)
    assert arch_rep.violations_count == 1
    assert arch_rep.violations[0].source_file == "src/view.py"

    con.close()
