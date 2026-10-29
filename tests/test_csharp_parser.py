from __future__ import annotations

from codegraph.indexing.languages.csharp import parse_csharp


def test_csharp_parser_types_and_methods() -> None:
    code = """
    using System;
    using System.Threading.Tasks;
    using Microsoft.AspNetCore.Mvc;

    namespace Enterprise.Services;

    public interface IUserService
    {
        Task<UserDto> GetUserAsync(int id);
    }

    [ApiController]
    [Route("api/[controller]")]
    public class UsersController : ControllerBase
    {
        private readonly IUserService _service;

        public UsersController(IUserService service)
        {
            _service = service;
        }

        [HttpGet("{id}")]
        public async Task<IActionResult> GetUser(int id)
        {
            var user = await _service.GetUserAsync(id);
            return Ok(user);
        }

        [HttpPost]
        public async Task<IActionResult> CreateUser([FromBody] CreateUserDto dto)
        {
            return CreatedAtAction(nameof(GetUser), new { id = 1 });
        }
    }
    """

    res = parse_csharp(code, "Controllers/UsersController.cs")

    assert res.language == "csharp"
    assert not res.parse_failed

    # Check symbols
    sym_names = [s.name for s in res.symbols]
    assert "IUserService" in sym_names
    assert "UsersController" in sym_names
    assert "GetUser" in sym_names
    assert "CreateUser" in sym_names

    # Check routes
    assert len(res.routes) == 2
    get_route = next(r for r in res.routes if r.http_method == "GET")
    assert get_route.route_path == "/api/users/{id}"
    assert get_route.handler_name == "GetUser"
    assert get_route.framework == "aspnetcore"

    post_route = next(r for r in res.routes if r.http_method == "POST")
    assert post_route.route_path == "/api/users"
    assert post_route.handler_name == "CreateUser"

    # Check imports
    imp_mods = [i.module for i in res.imports]
    assert "System" in imp_mods
    assert "Microsoft.AspNetCore.Mvc" in imp_mods

    # Check inheritance
    assert any(inh.base_name == "ControllerBase" for inh in res.inheritance)


def test_csharp_parser_entity_framework_dbset() -> None:
    code = """
    using Microsoft.EntityFrameworkCore;

    namespace Enterprise.Data;

    public class AppDbContext : DbContext
    {
        public DbSet<Customer> Customers { get; set; }
        public DbSet<Order> Orders { get; set; }
    }
    """

    res = parse_csharp(code, "Data/AppDbContext.cs")
    sym_names = [s.name for s in res.symbols]
    assert "AppDbContext" in sym_names
    assert "Customers" in sym_names
    assert "Orders" in sym_names

    customers_sym = next(s for s in res.symbols if s.name == "Customers")
    assert customers_sym.return_type == "DbSet<Customer>"
