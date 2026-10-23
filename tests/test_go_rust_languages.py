"""Tests for deep Python-level Go and Rust language support."""
from __future__ import annotations

from pathlib import Path

from codegraph.indexing.indexer import Indexer
from codegraph.indexing.languages.go import parse_go
from codegraph.indexing.languages.rust import parse_rust


def test_deep_go_parsing_capabilities() -> None:
    code = """package server

import (
    "fmt"
    "github.com/gin-gonic/gin"
)

// BaseUser represents a basic user identity.
type BaseUser struct {
    ID int
}

// User represents an authenticated account extending BaseUser.
type User struct {
    BaseUser
    Name string
}

// FullName returns the formatted user name.
func (u *User) FullName(prefix string) string {
    return prefix + u.Name
}

// SetupRouter initializes the API route group.
func SetupRouter(r *gin.Engine) {
    client := NewHttpClient()
    client.DoRequest()

    v1 := r.Group("/api/v1")
    v1.GET("/users", listUsersHandler)
}

func listUsersHandler(c *gin.Context) {}
"""
    res = parse_go(code, "pkg/server/server.go")
    assert res.language == "go"
    assert not res.parse_failed

    # 1. Symbols & Docstrings
    sym_map = {s.name: s for s in res.symbols}
    assert "BaseUser" in sym_map
    assert sym_map["BaseUser"].documentation == "BaseUser represents a basic user identity."
    assert sym_map["BaseUser"].visibility == "public"
    assert "User" in sym_map
    assert sym_map["User"].documentation == "User represents an authenticated account extending BaseUser."

    # Method details
    fn = sym_map["FullName"]
    assert fn.parameter_count == 1
    assert fn.return_type == "string"
    assert fn.visibility == "public"

    # 2. Inheritance (Embedded Struct)
    assert len(res.inheritance) >= 1
    inh = res.inheritance[0]
    assert inh.source_symbol == "User"
    assert inh.base_name == "BaseUser"
    assert inh.relationship == "EXTENDS"

    # 3. Router Mount & Composed Routes
    assert len(res.mounts) >= 1
    mount = res.mounts[0]
    assert mount.prefix == "/api/v1"

    assert len(res.routes) >= 1
    route = res.routes[0]
    assert route.route_path == "/api/v1/users"
    assert route.framework == "gin"

    # 4. Local Bindings
    assert len(res.bindings) >= 1
    b = res.bindings[0]
    assert b.target_name == "client"
    assert b.source_expr == "NewHttpClient"

    # 5. Enclosing Caller Linkage
    assert len(res.calls) >= 1
    c = [call for call in res.calls if call.callee == "DoRequest"][0]
    assert c.caller_symbol == "SetupRouter"
    assert c.caller_canonical_id == "go:server:SetupRouter"
    assert c.receiver == "client"


def test_deep_rust_parsing_capabilities() -> None:
    code = """use actix_web::{get, post, web, HttpResponse, Responder};

/// Order represents a customer order transaction.
pub struct Order {
    pub id: u64,
}

pub trait Auditable {
    fn audit(&self) -> bool;
}

impl Auditable for Order {
    fn audit(&self) -> bool {
        true
    }
}

impl Order {
    /// Creates a new order instance.
    pub fn new(id: u64, note: &str) -> Self {
        Order { id }
    }
}

#[get("/api/v1/orders")]
pub async fn get_orders() -> impl Responder {
    let client = ServiceClient::new();
    client.fetch_all();
    HttpResponse::Ok().body("orders")
}
"""
    res = parse_rust(code, "src/handlers/orders.rs")
    assert res.language == "rust"
    assert not res.parse_failed

    # 1. Symbols & Docstrings
    sym_map = {s.name: s for s in res.symbols}
    assert "Order" in sym_map
    assert sym_map["Order"].documentation == "Order represents a customer order transaction."
    assert sym_map["Order"].visibility == "public"

    new_fn = sym_map["new"]
    assert new_fn.documentation == "Creates a new order instance."
    assert new_fn.parameter_count == 2
    assert new_fn.return_type == "Self"
    assert new_fn.visibility == "public"

    # 2. Trait Implementation (InheritanceRef)
    assert len(res.inheritance) >= 1
    inh = res.inheritance[0]
    assert inh.source_symbol == "Order"
    assert inh.base_name == "Auditable"
    assert inh.relationship == "IMPLEMENTS"

    # 3. Route Detection
    assert len(res.routes) >= 1
    r = res.routes[0]
    assert r.route_path == "/api/v1/orders"
    assert r.http_method == "GET"
    assert r.handler_name == "get_orders"

    # 4. Local Bindings
    assert len(res.bindings) >= 1
    b = res.bindings[0]
    assert b.target_name == "client"
    assert b.source_expr == "ServiceClient::new"

    # 5. Enclosing Caller Linkage
    assert len(res.calls) >= 1
    c = [call for call in res.calls if call.callee == "fetch_all"][0]
    assert c.caller_symbol == "get_orders"
    assert c.receiver == "client"
    assert "get_orders" in (c.caller_canonical_id or "")


def test_indexer_indexes_polyglot_repository(tmp_path: Path) -> None:
    repo = tmp_path / "polyglot_repo"
    repo.mkdir()

    src = repo / "src"
    src.mkdir()

    go_file = src / "main.go"
    go_file.write_text(
        "package main\n\n"
        "// ServerConfig holds port configuration.\n"
        "type ServerConfig struct { Port int }\n\n"
        "func StartServer(cfg ServerConfig) error {\n"
        "    return nil\n"
        "}\n"
    )

    rs_file = src / "lib.rs"
    rs_file.write_text(
        "/// AppConfig configuration.\n"
        "pub struct AppConfig { pub port: u16 }\n\n"
        "pub fn init_runtime() -> bool { true }\n"
    )

    indexer = Indexer(repo)
    result = indexer.index()
    assert result["indexed"] >= 2

    with indexer.session() as con:
        # Verify Go symbols and docstrings in database
        go_syms = con.execute("SELECT name, kind, documentation FROM symbols WHERE language = 'go'").fetchall()
        assert len(go_syms) >= 2
        names = {s[0]: s[2] for s in go_syms}
        assert "ServerConfig" in names
        assert "ServerConfig holds port configuration." in (names["ServerConfig"] or "")

        # Verify Rust symbols and docstrings in database
        rs_syms = con.execute("SELECT name, kind, documentation FROM symbols WHERE language = 'rust'").fetchall()
        assert len(rs_syms) >= 2
        names_rs = {s[0]: s[2] for s in rs_syms}
        assert "AppConfig" in names_rs
        assert "AppConfig configuration." in (names_rs["AppConfig"] or "")


def test_rust_multiline_fn_and_axum_chained_routes() -> None:
    code_handlers = """use serde::Deserialize;

pub struct CustomerQuery {
    pub customer_id: Option<String>,
}

pub async fn list_orders(
    params: CustomerQuery,
) -> String {
    "orders".to_string()
}

pub async fn create_order(
    payload: String,
) -> String {
    "created".to_string()
}
"""
    res_h = parse_rust(code_handlers, "src/handlers/orders.rs")
    sym_names = [s.name for s in res_h.symbols]
    assert "list_orders" in sym_names
    assert "create_order" in sym_names

    list_sym = next(s for s in res_h.symbols if s.name == "list_orders")
    assert list_sym.canonical_id == "rust:handlers::orders::list_orders"

    code_main = """use axum::{routing::{get, post}, Router};
use handlers::orders::{create_order, list_orders};

pub fn build_app() -> Router {
    Router::new()
        .route("/api/orders", get(list_orders).post(create_order))
}
"""
    res_m = parse_rust(code_main, "src/main.rs")
    assert len(res_m.routes) == 2
    r_get = next(r for r in res_m.routes if r.http_method == "GET")
    assert r_get.handler_canonical_id == "rust:handlers::orders::list_orders"

    r_post = next(r for r in res_m.routes if r.http_method == "POST")
    assert r_post.handler_canonical_id == "rust:handlers::orders::create_order"
