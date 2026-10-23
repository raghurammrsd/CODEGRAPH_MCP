"""Tests for JVM (Java/Kotlin) and C/C++ language parsers."""
from __future__ import annotations

from codegraph.indexing.languages.cpp import parse_cpp
from codegraph.indexing.languages.jvm import parse_jvm
from codegraph.indexing.parser import parse


def test_java_spring_boot_parsing() -> None:
    java_code = '''package com.example.analytics;

import java.util.List;
import org.springframework.web.bind.annotation.*;
import org.springframework.beans.factory.annotation.Autowired;
import jakarta.persistence.Entity;
import jakarta.persistence.Table;

/**
 * Controller managing customer records.
 */
@RestController
@RequestMapping("/api/v1/customers")
public class CustomerController extends BaseController implements ICustomerApi {

    @Autowired
    private CustomerService customerService;

    /**
     * Retrieve customer by UUID.
     */
    @GetMapping("/{id}")
    public Customer getCustomerById(@PathVariable("id") String id) {
        var customer = customerService.findCustomer(id);
        return customer;
    }

    @PostMapping
    public Customer createCustomer(@RequestBody CustomerDto dto) {
        return customerService.saveCustomer(dto);
    }
}
'''
    res = parse_jvm(java_code, "CustomerController.java")
    assert not res.parse_failed
    assert res.language == "java"

    # Symbols check
    sym_names = [s.name for s in res.symbols]
    assert "CustomerController" in sym_names
    assert "getCustomerById" in sym_names
    assert "createCustomer" in sym_names
    q_names = [s.qualified_name for s in res.symbols]
    assert "CustomerController.getCustomerById" in q_names

    # Inheritance
    supers = [inh.base_name for inh in res.inheritance]
    assert "BaseController" in supers
    assert "ICustomerApi" in supers

    # Routes check
    routes = res.routes
    assert len(routes) == 2
    r_get = next(r for r in routes if r.http_method == "GET")
    assert r_get.route_path == "/api/v1/customers/{id}"
    assert r_get.framework == "spring"

    r_post = next(r for r in routes if r.http_method == "POST")
    assert r_post.route_path == "/api/v1/customers"

    # Calls check
    callees = [c.callee for c in res.calls]
    assert "findCustomer" in callees
    assert "saveCustomer" in callees

    # Bindings check (Autowired & local vars)
    binding_targets = [b.target_name for b in res.bindings]
    assert "customerService" in binding_targets
    assert "customer" in binding_targets


def test_kotlin_jaxrs_parsing() -> None:
    kt_code = '''package com.example.orders

import com.example.orders.BaseService
import jakarta.ws.rs.*

class OrderService(val repo: OrderRepository) : BaseService(), IOrderService {

    @GET
    @Path("/orders/{orderId}")
    fun fetchOrder(orderId: String): OrderResponse {
        val result = repo.findById(orderId)
        return result
    }
}
'''
    res = parse_jvm(kt_code, "OrderService.kt")
    assert not res.parse_failed
    assert res.language == "kotlin"

    sym_names = [s.name for s in res.symbols]
    assert "OrderService" in sym_names
    assert "fetchOrder" in sym_names
    q_names = [s.qualified_name for s in res.symbols]
    assert "OrderService.fetchOrder" in q_names

    supers = [inh.base_name for inh in res.inheritance]
    assert "BaseService" in supers
    assert "IOrderService" in supers

    routes = res.routes
    assert len(routes) == 1
    assert routes[0].route_path == "/orders/{orderId}"
    assert routes[0].http_method == "GET"
    assert routes[0].framework == "jax-rs"

    callees = [c.callee for c in res.calls]
    assert "findById" in callees


def test_cpp_crow_pistache_parsing() -> None:
    cpp_code = '''#include <iostream>
#include <string>
#include "crow.h"
#include "service.h"

namespace api {

/**
 * High-performance order engine.
 */
class OrderEngine : public IEngine {
public:
    int process(int order_id) {
        auto logger = get_logger();
        logger->info(order_id);
        return order_id;
    }
};

void setup_routes(crow::SimpleApp& app) {
    CROW_ROUTE(app, "/api/orders")([]() {
        return "Orders";
    });
}

} // namespace api
'''
    res = parse_cpp(cpp_code, "order_engine.cpp")
    assert not res.parse_failed
    assert res.language == "cpp"

    sym_names = [s.name for s in res.symbols]
    assert "OrderEngine" in sym_names
    assert "process" in sym_names

    supers = [inh.base_name for inh in res.inheritance]
    assert "IEngine" in supers

    # Routes check
    routes = res.routes
    assert len(routes) == 1
    assert routes[0].route_path == "/api/orders"
    assert routes[0].framework == "crow"

    # Imports check
    import_mods = [imp.module for imp in res.imports]
    assert "iostream" in import_mods
    assert "service.h" in import_mods

    # Calls check
    callees = [c.callee for c in res.calls]
    assert "info" in callees


def test_parser_dispatcher_integration() -> None:
    java_res = parse("class Foo {}", "java", "Foo.java")
    assert java_res.language == "java"

    cpp_res = parse("int add(int a, int b) { return a + b; }", "cpp", "math.cpp")
    assert cpp_res.language == "cpp"


def test_java_multiline_and_all_mapping_verbs() -> None:
    code = '''package com.dundoo;

import org.springframework.http.ResponseEntity;
import org.springframework.web.bind.annotation.*;
import java.util.List;

@RestController
@RequestMapping("/api/v1/orders")
public class OrderController {

    @GetMapping
    public ResponseEntity<List<Order>> getAllOrders(
            @RequestParam(required = false) String customerId) {
        return null;
    }

    @GetMapping("/{id}")
    public ResponseEntity<Order> getOrder(@PathVariable Long id) {
        return null;
    }

    @PostMapping
    public ResponseEntity<Order> createOrder(@RequestBody Order order) {
        return null;
    }

    @PutMapping("/{id}/confirm")
    public ResponseEntity<Order> confirmOrder(@PathVariable Long id) {
        return null;
    }

    @DeleteMapping("/{id}")
    public ResponseEntity<Order> cancelOrder(
            @PathVariable Long id,
            @RequestParam String customerId) {
        return null;
    }
}
'''
    res = parse_jvm(code, "OrderController.java")
    assert not res.parse_failed
    assert len(res.routes) == 5

    methods_paths = [(r.http_method, r.route_path) for r in res.routes]
    assert ("GET", "/api/v1/orders") in methods_paths
    assert ("GET", "/api/v1/orders/{id}") in methods_paths
    assert ("POST", "/api/v1/orders") in methods_paths
    assert ("PUT", "/api/v1/orders/{id}/confirm") in methods_paths
    assert ("DELETE", "/api/v1/orders/{id}") in methods_paths
