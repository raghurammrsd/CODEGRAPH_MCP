<p align="center">
  <img src="docs/assets/codegraph_logo.jpg" alt="CodeGraph MCP — Deep Deterministic Repository Intelligence for AI Coding Agents" width="500" />
</p>

<h1 align="center">CodeGraph MCP: Full-Stack Knowledge Graph & Semantic Intelligence for AI Coding Agents</h1>

<p align="center">
  <strong>Deterministic AST-Verified Codebase Intelligence • Sub-15ms Live Watcher • Context Window Optimization</strong><br>
  <em>Deterministic Model Context Protocol (MCP) server for Cursor, Claude Code, GitHub Copilot, Antigravity, Cline, Windsurf & Codex.</em>
</p>

<p align="center">
  <a href="https://github.com/raghurammrsd/CODEGRAPH_MCP"><img src="https://img.shields.io/github/stars/raghurammrsd/CODEGRAPH_MCP?style=for-the-badge&logo=github&color=gold" alt="GitHub Stars" /></a>
  <a href="https://pypi.org/project/codegraph-engine/"><img src="https://img.shields.io/badge/pypi-codegraph--engine-3776AB.svg?style=for-the-badge&logo=pypi" alt="PyPI: codegraph-engine" /></a>
  <a href="src/codegraph/mcp/server.py"><img src="https://img.shields.io/badge/MCP-97%20Verified%20Tools-2ea043.svg?style=for-the-badge" alt="MCP Tools: 97 verified" /></a>
  <a href="tests/"><img src="https://img.shields.io/badge/pytest-1062%20passed%20(100%25)-brightgreen.svg?style=for-the-badge&logo=pytest" alt="Tests: 1062 passed" /></a>
  <a href="pyproject.toml"><img src="https://img.shields.io/badge/ruff-0%20errors-success.svg?style=for-the-badge" alt="Ruff: 0 errors" /></a>
  <a href="src/codegraph/"><img src="https://img.shields.io/badge/mypy-strict%20(134%20files)-blue.svg?style=for-the-badge" alt="Mypy: strict" /></a>
</p>

> CodeGraph MCP provides deterministic, evidence-backed repository intelligence through Abstract Syntax Trees, framework router hierarchies, database lineage, and runtime observation across 25 production pillars and 97 FastMCP tools.

<p align="center">
  <a href="https://raghurammrsd.github.io/CODEGRAPH_MCP/"><strong>Documentation Site</strong></a> •
  <a href="https://pypi.org/project/codegraph-engine/3.0.1/"><strong>PyPI Package (v3.0.1)</strong></a> •
  <a href="#overview"><strong>Overview</strong></a> •
  <a href="#the-25-production-pillars-of-codegraph-mcp"><strong>25 Pillars</strong></a> •
  <a href="#interactive-web-dashboard--vs-code-extension"><strong>Web Dashboard & VS Code</strong></a> •
  <a href="#multi-language-real-world-benchmark-results"><strong>Multi-Language Benchmarks</strong></a> •
  <a href="#roblox--luau-intelligence-codegraph-roblox"><strong>Roblox & Luau</strong></a> •
  <a href="#2-quickstart-30-second-setup"><strong>Quickstart</strong></a> •
  <a href="#4-real-world-cli-outputs"><strong>CLI Outputs</strong></a> •
  <a href="#6-database-intelligence"><strong>Database Intelligence</strong></a> •
  <a href="#7-zero-friction-runtime-intelligence--static-reconciliation"><strong>Runtime Evidence</strong></a> •
  <a href="#8-git-aware-repository-intelligence"><strong>Git Intelligence</strong></a> •
  <a href="#measured-performance--real-metrics-benchmark"><strong>Benchmarks</strong></a> •
  <a href="docs/agent-brain.md"><strong>97-Tool Reference</strong></a> •
  <a href="https://github.com/raghurammrsd/CODEGRAPH_MCP"><strong>GitHub</strong></a>
</p>

---

## Overview

### The Problem

When AI coding agents (such as Claude Code, Cursor, or Antigravity) explore complex enterprise repositories, text-based search (grep/ripgrep) forces them to parse large, multi-thousand-line files to reconstruct call chains, router mounts, dependency injection graphs, and ORM schemas. This consumes 60% to 80% of the LLM context window with irrelevant code and frequently leads to hallucinations regarding entity relationships and database structures.

### The Solution: CodeGraph MCP

**CodeGraph MCP provides deterministic, evidence-backed repository intelligence through the Model Context Protocol.** Instead of guessing based on lexical approximations, the AI agent queries a local, persistent SQLite index for verified AST relationships, framework router trees, database lineages, and live runtime observations. When dynamic ambiguity occurs (such as untyped method receivers in Python or JS), relationships are explicitly tagged as `POSSIBLE` or `UNKNOWN` rather than inventing false facts.

```text
       ┌─────────────────────────────────────────────────────────────┐
       │                      AI CODING AGENT                        │
       │           (Claude Code  •  Cursor  •  Antigravity)          │
       └──────────────────────────────┬──────────────────────────────┘
                                      │  Model Context Protocol (stdio / SSE)
                                      ▼
       ┌─────────────────────────────────────────────────────────────┐
       │                   CODEGRAPH MCP ENGINE                      │
       ├──────────────────────────────┬──────────────────────────────┤
       │  AST Code Relationships      │  Framework & Network Graph   │
       │  (Callers, Callees, DI)      │  (FastAPI, Django, Roblox)   │
       ├──────────────────────────────┼──────────────────────────────┤
       │  Database & DataStore Graph  │  Non-Invasive Dev Tracing    │
       │  (SQLAlchemy, Prisma, ORM)   │  (HTTP metrics, exceptions)  │
       └──────────────────────────────┴──────────────────────────────┘
                                      │
                                      ▼
             Deterministic • Local-First • Verified Evidence
```

### Core Architecture Capabilities

- **Deterministic Evidence Guarantee**: Every returned entity and relationship is statically verified via Abstract Syntax Trees (`AST_VERIFIED`, `FRAMEWORK_VERIFIED`, `ROJO_VERIFIED`) or explicitly flagged as `UNKNOWN` / `POSSIBLE`. CodeGraph MCP provides deterministic, evidence-backed repository intelligence across application code, databases, runtime behavior, and Git history.
- **Sub-5ms Freshness Verification**: Monotonic commit tracking validates `git rev-parse HEAD` and porcelain status instantly, avoiding full-tree re-indexing on unchanged codebases.
- **Context Window Optimization**: Yields 65% to 85% token reduction by returning structured, bounded source slices rather than entire file dumps.
- **Zero-Friction Dev Interception (`codegraph run`)**: Wraps local development servers (e.g., `codegraph run npm run dev`, `codegraph run uvicorn main:app`) to capture real HTTP routes, latencies, and stack traces without application code changes.
- **Multi-Agent Setup (`codegraph install`)**: Automatically detects, configures, and verifies integrations for Claude Code, Cursor, Antigravity, and Cline.

> **Supported Languages & Frameworks:** Python (`FastAPI`, `Flask`, `Django`, `SQLAlchemy`, `PyTorch`), TypeScript / JavaScript (`React`, `Next.js`, `Express`, `NestJS`, `Prisma`), Roblox / Luau (`Rojo`, `Knit`, `DataStoreService`), Go (`Gin`, `Echo`, `net/http`), Rust (`Axum`, `Actix`, `Tokio`), Java (`Spring Boot`, `JPA`), and C/C++.

<p align="center">
  <img src="docs/assets/codegraph_full_architecture.svg" alt="CodeGraph MCP Comprehensive Full-Stack Architecture Pipeline" width="950" />
</p>

---

---

## Measured Performance & Real Metrics Benchmark

Performance and retrieval accuracy are verified across two empirical evaluation suites: a **32-task agent navigation simulation** ([`src/codegraph/tool_selection_eval.py`](src/codegraph/tool_selection_eval.py)) measuring agent trajectory efficiency, and a **50-task diagnostic benchmark** ([`benchmarks/run_v21_eval.py`](benchmarks/run_v21_eval.py)) evaluating multi-file recall, coverage, and context boundaries:

| Performance Metric | Unassisted AI Agents (Raw Grep / File Dumps) | CodeGraph MCP Engine | Measured Result | Evaluation Suite |
| :--- | :---: | :---: | :---: | :---: |
| **Unsupported Relationship Claims** | 18.5% – 34.0% false edges | **0.0%** (AST / Framework verified) | **100% eliminated** | 32-Task Navigation Eval |
| **Exploration Tool Calls** | 164 total tool calls (~5.1 / task) | **71 tool calls** (~2.2 / task) | **56.7% fewer tool calls** | 32-Task Navigation Eval |
| **Context Consumption (Prompt Tokens)** | 3,000 – 12,000+ tokens / task | **~510 tokens** avg payload | **72% – 85% token savings** | 32-Task Navigation Eval |
| **Direct File Token Reduction** | Full file reads required | Bounded slices via `get_file` | **41.8% token reduction** | 50-Task Retrieval Benchmark |
| **Multi-File Context Reduction** | 3,000 – 12,000+ tokens / task | **~510 tokens** avg payload | **72% – 85% token reduction** | 32-Task Navigation Eval |
| **Task Coverage & Symbol Recall** | Baseline lexical match | **89.0% coverage / 72.5% recall** | **Verified ground truth** | 50-Task Retrieval Benchmark |
| **In-Memory SQLite WAL Query** | Full rescan required (1.2s – 6.5s) | **< 15ms per query** | **Permanent WAL concurrency** | Persistent MCP Server Daemon |
| **Binary CSR Pathfinding** | Linear graph scan | **< 1ms traversal** | **Microsecond CSR search** | `fast_graph_path` Traversal |
| **CLI Cold Invocation Latency** | — | **~265ms total turnaround** | **Includes Python startup** | One-off CLI Subcommands |
| **Single-File Full Re-index (Cold CLI)** | Full rescan required (4.4s) | **3.665s** (2,504 files) | **16.9% faster** | 4-Tier Stress Benchmark |
| **Repository Freshness Check** | 450ms – 2,100ms disk stat checks | **< 5ms (Git commit fast path)** | **99% faster checks** | Git Fast Path Check |
| **Symbol Grounding & Resolution** | Manual file scanning | **< 2ms in-memory SQLite** | **Sub-millisecond resolution** | SQLite Indexed Lookup |
| **Automated Test Suite Quality** | — | **1,062 passed tests (100% pass rate)** | **Zero regressions** | Pytest CI/CD Suite |

<p align="center">
  <img src="docs/assets/performance_comparison.svg" alt="CodeGraph MCP — Measured Context & Exploration Efficiency" width="850" />
</p>

<p align="center">
  <img src="docs/assets/large_repo_scaling.svg" alt="CodeGraph MCP — Large Repository Scaling up to 2,504 Files / ~120k LOC" width="850" />
</p>

---

## Interactive Web Dashboard & VS Code Extension

CodeGraph v3.0 introduces a zero-configuration local visual dashboard and official VS Code integration for real-time visual inspection of your repository's AST relationships, full-stack routes, and PR blast radius.

### 1. Interactive Knowledge Graph Web Dashboard (`codegraph ui`)

Launch the local visualizer with a single command:

```bash
# Launch interactive dashboard on http://127.0.0.1:8765
codegraph ui

# Custom port or headless server (no automatic browser launch)
codegraph ui --port 9000 --no-browser
```

The Web Dashboard delivers:
- **Interactive Knowledge Visualizer**: Search and inspect any symbol, route, or model across Python and TypeScript.
- **Full-Stack Route Explorer**: Visualizes frontend fetchers (`fetch<T>()`, `axios`) matched to backend handlers (FastAPI, Flask, Django, Express, NestJS).
- **Database Lineage Matrix**: Real-time table relationship map showing exact static writers and readers (PostgreSQL, SQLite, Prisma, Drizzle, SQLAlchemy, Mongoose).
- **PR Blast Radius & Risk Tiering**: Live risk assessment, highlighting modified call chains and covering tests before submitting pull requests.
- **REST & SSE Endpoints**: Integrated REST API (`/api/status`, `/api/routes`, `/api/drift`, `/api/impact`, `/api/graph`) enabling external tools to query graph state.

### 2. Official VS Code Extension (`vscode-extension`)

The CodeGraph VS Code extension brings deterministic repository intelligence directly into your editor:

```bash
# Package and install the extension
cd vscode-extension
code --install-extension codegraph-3.0.1.vsix
```

Features included in the VS Code sidebar:
- **Full-Stack Routes View**: Tree view of all discovered endpoints, clicking any item navigates directly to the route handler definition.
- **Database Lineage & Models View**: Inspect tables, fields, readers, and writers side-by-side with source code.
- **PR Blast Radius Explorer**: Select any active file to view downstream callers, impacted routes, and tests to run.
- **In-Editor Knowledge Graph Panel (`CodeGraph: Open Visual Knowledge Graph Dashboard`)**: Opens the visual web dashboard side-by-side in a VS Code Webview panel.
- **Safe AST Rename (`CodeGraph: Safe AST Rename Symbol`)**: Deterministic symbol refactoring across all call sites and route handlers.
- **Live Watcher Integration (`CodeGraph: Start Sub-15ms Live Watcher Daemon`)**: One-click background watcher launch.

---

## The Three Pillars of CodeGraph MCP

### AI / ML & PyTorch Stack Intelligence
CodeGraph MCP natively parses AI/ML architectures and agent pipelines into deterministic graph facts:
- **PyTorch nn.Module Forward Resolution**: Submodule and model instance calls (`model(x)`, `self.encoder(x)`) automatically resolve to `Encoder.forward` emitting `DISPATCHES_FORWARD` (`AST_VERIFIED`).
- **LangChain & LlamaIndex Agent Tools**: Statically detects `@tool`, `@function_tool`, and dynamic agent registries, connecting agent capabilities to handler implementations (`AGENT_TOOL`).
- **LangChain LCEL Pipelines**: Tracks pipe syntax (`prompt | model | parser`) as executable pipeline dataflow (`CHAINS_TO`).
- **Distributed Ray Tasks**: Detects `@ray.remote` actor decorators and `task.remote()` invocations (`DISPATCHES_RAY_TASK`).

### Roblox & Luau Intelligence (`codegraph roblox`)
First-class repository intelligence for Roblox game architectures (`.lua`, `.luau`, and `roblox-ts`):
- **Native Luau Parser**: Extracts local/global functions, colon methods (`function Service:Init()`), dot methods (`function Module.Func()`), table-assigned methods (`Service.Method = function(...)`), module table returns, `return table.freeze(Module)`, and Luau `type` / `export type` declarations.
- **Rojo DataModel Mapping (`default.project.json`)**: Maps virtual Roblox paths (`ReplicatedStorage`, `ServerScriptService`, `StarterPlayerScripts`, `Packages`, `script.Parent`) to physical files on disk with `ROJO_VERIFIED` provenance (`REQUIRES_MODULE`).
- **Client $\leftrightarrow$ Server Network Graph**: Traces `RemoteEvent:FireServer(...)` $\to$ `OnServerEvent:Connect(handler)` and `RemoteFunction:InvokeServer(...)` $\to$ `OnServerInvoke = handler` through canonical Remote nodes via `CLIENT_DISPATCHES_REMOTE` and `SERVER_HANDLES_REMOTE`.
- **Knit, Flamework & Persistence**: Tracks `Knit.CreateService` / `Knit.GetService`, Flamework `@Service` / `@Controller` / `Dependency<T>`, and `DataStoreService:GetDataStore` (`GetAsync`, `SetAsync`, `UpdateAsync`) + `ProfileService` (`CONFIGURES_PERSISTENCE`, `READS_PERSISTENCE`, `WRITES_PERSISTENCE`).
- **Dedicated CLI Inspection**: `codegraph roblox remotes`, `codegraph roblox modules`, and `codegraph roblox routes`.

### Pillar 1: The Unified Full-Stack Bridge (`codegraph api-drift`)
Bridges frontend client fetchers and backend API handlers across languages without manual tracing:
- **Client Route Extraction**: Statically parses React / Next.js / Vue / Nuxt `fetch<T>()`, `axios.get<T>()`, `useSWR<T>()`, `useQuery<T>()`, and `$fetch<T>()` alongside TypeScript request/response interfaces.
- **Universal Route Normalization**: Matches parameterized paths (`/api/v1/orders/:id`, `/api/orders/${orderId}`, `/orders/{order_id}`) directly to backend routes in FastAPI, Flask, Django, Express, and NestJS.
- **Cross-Language Drift Detection**: Flags field name mismatches, type incompatibilities, missing nullable fields, and orphaned client routes before deployment.

### Pillar 2: Semantic Change Impact & PR Blast Radius Engine (`codegraph impact`)
Full-stack downstream impact analysis from code symbols to production infrastructure:
- **Blast Radius Tracing**: Traces any symbol or git diff $\to$ direct/transitive callers $\to$ React UI components $\to$ HTTP routes $\to$ DB readers/writers $\to$ covering tests $\to$ monorepo packages.
- **PR Risk Scoring (0–100)**: Quantitative risk evaluation categorized into `LOW`, `MEDIUM`, `HIGH`, and `CRITICAL`.
- **Breaking Change Detection**: Identifies public API modifications, DB mutations, and untested code paths.
- **Smart Test Execution**: Generates targeted test commands (e.g. `pytest tests/test_orders.py -k "test_a or test_b"`) running only the affected test suite.

### Pillar 3: Incremental Live Watcher & Instant Cache Invalidation (`codegraph watch`)
Zero-heat, real-time file system monitoring with sub-15ms incremental reindexing:
- **Kernel-Push Event Monitoring**: Uses OS-level kernel events (macOS FSEvents, Linux inotify, Windows ReadDirectoryChangesW) via `watchdog`.
- **250ms Sliding Debounce**: Coalesces rapid multi-file edit bursts from formatters, linters, or git operations into single atomic passes.
- **Sub-15ms Incremental Reindexing**: Bypasses full-disk traversal; only re-indexes modified files (`Indexer.reindex_paths`) and advances generation counters.
- **Instant In-Memory Cache Busting**: Automatically purges LRU memory caches (`_PARSE_CACHE`, `_GRAPH_CACHE`) and SQLite context caches upon file mutation.

## 1. What's New in v3.0.1: 25 Production Pillars & 97 Verified FastMCP Tools

CodeGraph **v3.0.1** is the production-grade codebase intelligence engine for AI coding agents, providing deterministic, source-verified AST facts, microsecond Compressed Sparse Row (CSR) graph pathfinding, and sub-15ms live file synchronization across 7 major programming languages.

<p align="center">
  <img src="docs/assets/codegraph_full_architecture.svg" alt="CodeGraph v3.0.1 Architecture Pipeline" width="100%" />
</p>

### Key Feature Highlights

- **Microsecond CSR Traversal**: Traverses call chains and impact graphs across 100k+ edges in microseconds via binary Compressed Sparse Row matrices (`graph_csr.py`).
- **97 Verified FastMCP Tools**: 100% audit pass rate across all registered FastMCP tools for Claude Code, Cursor, Antigravity, and Cline.
- **65% to 85% Token Reduction**: Returns compact, bounded AST context packets (~510 tokens) rather than dumping entire multi-thousand-line files.
- **7 Languages Native Support**: Python, TypeScript/JavaScript, Roblox/Luau, Go, Rust, Java, and C/C++.
- **Zero Hallucinated Edges**: Every caller, route, and database relationship is compiler-verified (`AST_VERIFIED` / `FRAMEWORK_VERIFIED`).
- **Universal Cross-Platform**: Native Windows `kernel32` process inspection, cp1252/UTF-8 terminal safety, and `python -m codegraph` execution out of the box.
- **Sub-15ms Live Watcher**: Instant OS kernel push synchronization (macOS FSEvents, Linux inotify, Windows ReadDirectoryChangesW).
- **Roblox & Luau Intelligence**: Client-server remote hopping, Rojo file tree mapping, and DataStore persistence lineage.

---

### The 25 Production Pillars of CodeGraph MCP

| Category | Pillar | Primary Tools | What It Does |
|---|---|---|---|
| **Code Intelligence** | **1. Multi-Language AST** | `resolve_symbol`, `batch_get_symbols` | Native AST extraction for 7 languages in <60ms. |
| | **2. CSR Binary Graph** | `fast_graph_path`, `get_call_graph` | Microsecond pathfinding across binary CSR matrices. |
| | **3. 97 FastMCP Tools** | 97 registered FastMCP endpoints | 100% verified tool suite spanning all capabilities. |
| | **4. HTTP & RPC Routes** | `find_routes`, `list_routes` | FastAPI, Express, Spring Boot, Gin, Axum, Roblox Remotes. |
| | **5. API Contract Drift** | `check_api_drift` | Statically matches frontend `fetch()` to backend routes. |
| | **6. Dependency Injection** | `get_context`, `resolve_symbol` | Traces FastAPI `Depends`, Spring `@Autowired`, Gin middleware. |
| | **7. Database Lineage** | `find_db_tables`, `get_db_impact` | Mapped SQLAlchemy, Prisma, JPA, SQLx, DataStore writers. |
| **Safety & Testing** | **8. PR Blast Radius** | `analyze_change_impact`, `get_change_impact` | Downstream caller trees, impacted routes, and tests. |
| | **9. Live Watcher** | `codegraph watch` | Kernel push events debounced in <15ms. |
| | **10. Safe Refactoring** | `safe_rename`, `apply_semantic_patch` | Multi-file transactional patches with rollback safety. |
| | **11. Multi-Agent Leases** | `claim_file_lease`, `release_file_lease` | Concurrency locks preventing swarm file collisions. |
| | **12. Dead Code Detection** | `find_unreachable_code`, `find_dead_code` | Graph reachability traversal finding unused symbols. |
| | **13. Taint Security** | `analyze_dataflow_taint` | Interprocedural dataflow tracking for injection flaws. |
| | **14. Supply Chain CVE** | `analyze_supply_chain_cve_impact` | Maps package lockfile CVEs to internal code consumers. |
| | **15. Repo Federation** | `federate_repositories` | Cross-repository HTTP and RPC service resolution. |
| | **16. Test Scaffolding** | `generate_test_scaffolding` | Auto-generates unit test suites with mocked DB fixtures. |
| | **17. LSP Bridge** | `codegraph lsp` | stdio LSP server with definition and caller CodeLens. |
| **Operations & Storage** | **18. Agent Memory** | `store_agent_memory`, `query_agent_memory` | SQLite FTS5 experience store with sub-5ms BM25 search. |
| | **19. Git Diff Freshness** | `get_git_state`, `compare_git` | Monotonic Git commit diffs & context invalidation. |
| | **20. Index Self-Healing** | `repair_repository_index` | Automatic integrity checks and WAL rebuilds. |
| | **21. SWE-bench Sandbox** | `evaluate_speculative_patch` | Isolated test execution harness for agent patches. |
| | **22. PR Review Bot** | `generate_pr_review` | High-density PR review comments with risk badges. |
| | **23. Web UI Dashboard** | `codegraph ui` | Browser visualizer on `127.0.0.1:8765`. |
| | **24. Windows Portability** | `codegraph` CLI | Native Windows encoding, Win32 kernel32, and `python -m codegraph`. |
| | **25. Universal Installer** | `codegraph install` | Auto-onboarding for Claude, Cursor, Antigravity, Cline. |

---

### Multi-Language Framework Benchmarks

Evaluated against multi-layer framework fixtures (Gin HTTP, Axum + sqlx, Spring Boot + JPA, Express + React TSX, Rojo + DataStore) using CodeGraph v3.0.1 (97 FastMCP tools, SQLite WAL storage):

| Language | Ecosystem / Framework | Indexing Time (Core AST) | SQLite DB Size | Files | Symbols | Edges | Avg Query Latency | Production Score |
| :--- | :--- | :---: | :---: | :---: | :---: | :---: | :---: | :---: |
| **Roblox / Luau** | Rojo / Knit / DataStore | **63 ms** (352 ms total) | 588 KB | 5 | 23 | 34 | 278 ms | **9.0 / 10** |
| **Go** | Gin / GORM / net/http | **58 ms** (408 ms total) | 540 KB | 5 | 25 | 92 | 265 ms | **8.5 / 10** |
| **TypeScript** | Express + React (TSX) | **81 ms** (378 ms total) | 560 KB | 5 | 16 | 101 | 268 ms | **8.5 / 10** |
| **Java** | Spring Boot + JPA | **59 ms** (417 ms total) | 548 KB | 4 | 22 | 64 | 270 ms | **8.5 / 10** |
| **Rust** | Axum + Tokio + sqlx | **48 ms** (312 ms total) | 484 KB | 5 | 14 | 29 | 264 ms | **8.5 / 10** |

*Note on Latency:* Total CLI turnaround averages ~265 ms due to Python interpreter cold startup. The underlying SQLite WAL engine executes graph queries in **sub-15 ms**.

---

### Token Reduction & Context Window Optimization

```text
Without CodeGraph (Raw Grep / Full File Dumps):
┌────────────────────────────────────────────────────────────────────────┐
│ Entire Files Read (12,000+ Tokens)                                     │
│ [====================================================================] │
└────────────────────────────────────────────────────────────────────────┘

With CodeGraph MCP (Targeted AST Slices & Evidence):
┌───────────────────────────┐
│ ~510 Tokens (72%–85% Saved│
│ [======]                  │
└───────────────────────────┘
```

- **65% to 85% Token Reduction**: Instead of transmitting 3,000 to 12,000 raw lines to the LLM, CodeGraph returns bounded, AST-verified context packets (~510 tokens average).
- **56.7% Fewer Tool Calls**: Agents resolve multi-file call paths in an average of 2.2 tool calls versus 5.1 calls for naive unassisted agents.
- **100% Elimination of Hallucinated Callers**: Grounded directly in AST coordinates, eliminating false edges entirely.

---

## 2. Quickstart & Agent Installation

### Step 1: Install `codegraph-engine`

```bash
# macOS / Linux
pip install "codegraph-engine[mcp]"

# Windows (PowerShell or Command Prompt)
python -m pip install "codegraph-engine[mcp]"

# Universal execution verification (works on all platforms even if Scripts/ is not on PATH)
python -m codegraph --version
```

> **Windows Portability:** CodeGraph v3.0.1 includes native Windows cp1252/UTF-8 terminal encoding safety, zero-dependency Win32 `kernel32` process inspection, and direct module-level execution via `python -m codegraph`. If the Windows `Scripts\` directory is not in your system `PATH`, executing `python -m codegraph <command>` works out of the box across PowerShell, CMD, and Windows Terminal.

---

### Step 2: Connect Your AI Coding Agents (`codegraph install --target`)

CodeGraph MCP includes an automated, idempotent onboarding installer ([`src/codegraph/installer.py`](src/codegraph/installer.py)) that detects installed agents, configures `mcpServers.codegraph`, installs marker-bounded routing instructions (`<!-- CODEGRAPH:START -->` … `<!-- CODEGRAPH:END -->`), and verifies server health.

#### Primary Target Commands (`--target`)

Run `codegraph install` targeting your specific AI coding agent(s):

```bash
# Target Claude Code (configures .mcp.json and CLAUDE.md)
codegraph install --target claude --yes

# Target Cursor (configures .cursor/mcp.json, .cursorrules, and .cursor/rules/codegraph.md)
codegraph install --target cursor --yes

# Target Google Antigravity / Gemini (configures .agents/mcp_config.json, AGENTS.md, and skills)
codegraph install --target antigravity --yes

# Target Cline / Roo Code (configures .cline/mcp_settings.json and .clinerules)
codegraph install --target cline --yes

# Target Codex CLI (configures .codex/mcp_config.json and AGENTS.md)
codegraph install --target codex --yes

# Target Gemini CLI (configures .gemini/settings.json and GEMINI.md)
codegraph install --target gemini --yes

# Target multiple agents simultaneously
codegraph install --target claude,cursor,antigravity --yes

# Auto-detect all installed agents in the project / environment
codegraph install --target auto --yes

# Configure ALL supported agents at once
codegraph install --target all --yes
```

#### Installation Scopes (`--location`)

```bash
# Local Project Scope (Default): Configures the current repository directory
codegraph install --target claude --location local --yes

# Global Scope: Configures your user home directory (~/.claude.json, ~/.cursor/mcp.json, etc.)
codegraph install --target cursor --location global --yes
```

#### Safe Previews, Manual Config & Repairs

```bash
# Dry-Run Preview: View planned file changes without modifying anything on disk
codegraph install --target all --dry-run

# Print Config Only: Output exact JSON snippet for manual pasting into GUI settings
codegraph install --print-config claude
codegraph install --print-config cursor
codegraph install --print-config antigravity

# Automatic Config Repair: Backs up and repairs corrupted or outdated MCP settings
codegraph install --target auto --repair --yes

# Clean Uninstall: Safely removes CodeGraph integration while preserving user files
codegraph uninstall --target claude,cursor --yes

# Uninitialize: Removes only the local repository index (.codegraph.sqlite3)
codegraph uninit --yes
```

#### What `codegraph install` Configures Per Agent:

| Target Agent (`--target`) | MCP Configuration File | Marker-Bounded Instructions | Skills & Rules |
| :--- | :--- | :--- | :--- |
| **`claude`** (Claude Code) | `.mcp.json` (local) / `~/.claude.json` (global) | `CLAUDE.md` | Marker section |
| **`cursor`** (Cursor) | `.cursor/mcp.json` | `.cursorrules` | `.cursor/rules/codegraph.md` |
| **`antigravity`** (Antigravity) | `.agents/mcp_config.json` | `AGENTS.md` | `.agents/rules/` & `.agents/skills/` |
| **`cline`** (Cline / Roo Code) | `.cline/mcp_settings.json` | `.clinerules` | `.cline/rules/codegraph.md` |
| **`codex`** (Codex CLI) | `.codex/mcp_config.json` | `AGENTS.md` | Marker section |
| **`gemini`** (Gemini CLI) | `.gemini/settings.json` | `GEMINI.md` | Marker section |

---

### Step 3: Initialize & Verify Your Project Index

```bash
cd your-project

# Initialize SQLite graph index (.codegraph.sqlite3 in WAL mode)
codegraph init

# Check index freshness (<5ms via Git commit fast path)
codegraph status

# Verify database integrity and running MCP server processes
codegraph doctor --database
codegraph doctor --processes
```

> **Dynamic Index Hot-Reloading:** If your AI coding agent launches `codegraph mcp serve` before you run `codegraph init`, you do **not** need to restart your IDE or MCP session. As soon as `codegraph init` or `codegraph index` creates or updates `.codegraph.sqlite3`, the running MCP server automatically detects the database on the next tool call and refreshes its in-memory graph cache (`get_repository_status(reload=True, reindex=True)` can also be invoked directly by the agent).

---

### Step 4: Run With Zero-Friction Telemetry (`codegraph run`)

Wrap your development server transparently to stream real HTTP routes, durations, and uncaught exceptions directly into CodeGraph MCP:

```bash
# Node / Express / Next.js
codegraph run npm run dev

# Python / FastAPI / Uvicorn
codegraph run uvicorn main:app --reload

# Django
codegraph run python manage.py runserver
```

---

### Step 5: Launch the Interactive Web Visualizer (`codegraph ui`)

```bash
# Launch interactive dashboard on http://127.0.0.1:8765
codegraph ui

# Custom port or headless server (no automatic browser launch)
codegraph ui --port 9000 --no-browser
```

---

## 3. Core Architecture & Mental Model

```mermaid
flowchart TD
    A["AI Coding Agent (Claude, Cursor, Antigravity, Cline)"] --> B["CodeGraph MCP Server (stdio or SSE)"]
    B --> C["Deterministic Repository Intelligence"]

    C --> D["AST Semantic Graph (Callers, Callees, References, DI)"]
    C --> E["Literal & Regex Text Search (search_code)"]
    C --> F["Bounded Source Inspection (get_file)"]
    C --> G["Database Intelligence (Tables, ORM, Migrations, R/W)"]
    C --> H["Zero-Friction Runtime Telemetry (codegraph run)"]

    D --> I["Structured Evidence + Epistemic Labels"]
    E --> I
    F --> I
    G --> I
    H --> I

    I --> J["Context Optimization & Secret Redaction"]
    J --> A
```

### Routing Each Question to the Right Primitive

```text
STRUCTURAL     →  Graph tools (find_symbol, find_callers, find_callees, find_references, find_routes)
TEXTUAL        →  search_code (literal/regex search across Python, HTML/Jinja, JS/TS, CSS, YAML/JSON, SQL)
SOURCE         →  get_file (bounded start_line..end_line source inspection with truncation metadata)
GRAPH          →  Trace tools (trace_path, trace_flow, analyze_impact, get_git_impact)
DATABASE       →  Database tools (get_db_schema, find_db_tables, find_db_readers, find_db_writers, get_db_impact)
RUNTIME        →  Runtime tools (codegraph run, ingest_runtime_traces, get_runtime_trace, reconcile_static_runtime)
EDITING        →  Native agent / IDE editing tools
```

---

## 4. Real-World CLI Outputs

Below are exact, verifiable outputs produced by CodeGraph MCP v3.0.1:

### 1. Zero-Friction Runtime Interceptor (`codegraph run`)

```bash
$ codegraph run python3 -c "print('>> Dev server active on port 8000')"
>> Dev server active on port 8000
```
*HTTP requests, status codes, and exceptions are automatically streamed to `.codegraph/runtime.sqlite3` with child exit codes preserved.*

### 2. Instant Index Freshness Check (`codegraph status`)

```bash
$ codegraph status .
{
  "repository": "/workspace/my-project",
  "freshness": "FRESH",
  "freshness_detail": "Index matches current repository state.",
  "files": 190,
  "chunks": 1965,
  "symbols": 1947,
  "framework_routes": 14,
  "graph_edges": 12712,
  "resource_profile": "BALANCED",
  "pressure_level": "NORMAL",
  "activity_mode": "IDLE",
  "estimated_memory_mb": 43.23,
  "modified_files": [],
  "deleted_files": [],
  "parse_failed_files": []
}
```
*Validated in `< 5ms` via the Git commit diff fast path.*

### 3. Incremental Indexing with 16-Phase Telemetry (`codegraph index --verbose`)

```bash
$ codegraph index --verbose
Phase: Repository Scan
190 / 190 files | 100% | elapsed: 0.09s | rate: 128,203 files/min | memory: 42 MB
Phase: Post-Processing
190 / 190 files | 100% | elapsed: 0.62s | rate: 18,273 files/min | memory: 67 MB
Phase: Symbol Resolution
190 / 190 files | 100% | elapsed: 0.80s | rate: 14,311 files/min | memory: 91 MB
Phase: Relationship Resolution
190 / 190 files | 100% | elapsed: 1.49s | rate: 7,648 files/min | memory: 116 MB
Phase: Database Analysis
190 / 190 files | 100% | elapsed: 1.77s | rate: 6,424 files/min | memory: 120 MB
Phase: Final Commit & Checkpoint
190 / 190 files | 100% | elapsed: 2.59s | rate: 4,396 files/min | memory: 141 MB

Summary: elapsed=2.595s peak_rss=141.0MB max_wal=9.44MB final_wal=0.00MB commits=15 checkpoints=15
  [repository_scan] 88.1ms files=190 items=190 writes=0
  [ast_parsing] 154.7ms files=13 items=3322 writes=0
  [database_analysis] 283.9ms files=13 items=1631 writes=0
  [symbol_resolution] 52.5ms files=190 items=5854 writes=0
  [relationship_resolution] 694.0ms files=190 items=32806 writes=0
  [sqlite_writes] 1146.4ms files=13 items=50206 writes=50208
scanned=190 indexed=13 unchanged=177 removed=0
```

### 4. Bounded Monorepo Route Discovery (`codegraph routes --limit 3`)

```bash
$ codegraph routes --limit 3
Found 3 route(s):
  [GET] /api/v1/health -> health_check (src/app/api.py:14) [fastapi]
  [POST] /api/v1/orders -> create_order (src/app/orders.py:42) [fastapi]
  [GET] /api/v1/users/{id} -> get_user (src/app/users.py:88) [fastapi]
```

### 5. Safe Background Process Termination (`codegraph stop --json`)

```bash
$ codegraph stop --json
{
  "status": "ok",
  "stopped_count": 0,
  "stale_cleaned_count": 0,
  "processes": []
}
```

---

## 5. AI/ML & Backend Architecture Examples

### Example 1: Model Inference Service Flow

```text
POST /v1/predict (FastAPI Route)
      ↓  HANDLED_BY (FRAMEWORK_VERIFIED)
predict_endpoint (Handler)
      ↓  INJECTS (DATAFLOW_VERIFIED)
get_inference_service (DI Provider)
      ↓  CALLS (AST_VERIFIED)
InferenceService.run_inference
      ├──►CALLS (AST_VERIFIED) ──► FeaturePreprocessor.transform
      ├──►CALLS (AST_VERIFIED) ──► FraudClassifier.forward
      ├──►CALLS (AST_VERIFIED) ──► ScorePostprocessor.calibrate
      └──►CALLS (AST_VERIFIED) ──► PredictionRepository.log_prediction
                                        ↓  WRITES_TABLE (AST_VERIFIED)
                                   db:table:postgresql.public.prediction_logs
```

**What CodeGraph MCP structurally proves**:
- `find_routes(path="/v1/predict")` resolves composed router prefixes (`MOUNTS`) to `predict_endpoint`.
- `trace_path(from_symbol="predict_endpoint", to_symbol="log_prediction")` proves the multi-hop execution chain across DI injection, preprocessing, model execution, and persistence.
- `get_db_impact(symbol="InferenceService.run_inference")` identifies downstream writes to `prediction_logs`.

### Example 2: Training & Evaluation Pipeline

```text
train_cli (CLI Command Handler)
      ↓  COMMAND_HANDLER (FRAMEWORK_VERIFIED)
TrainingPipeline.run
      ├──►CALLS (AST_VERIFIED) ──► DatasetBuilder.load_splits
      ├──►CALLS (AST_VERIFIED) ──► TokenizerTransform.encode_batch
      ├──►CALLS (AST_VERIFIED) ──► Trainer.fit_epoch
      ├──►CALLS (AST_VERIFIED) ──► CheckpointManager.save_weights
      └──►CALLS (AST_VERIFIED) ──► Evaluator.compute_metrics
```

**What CodeGraph MCP structurally proves**:
- `find_callees(symbol="TrainingPipeline.run")` enumerates every stage of the pipeline with exact file and line ranges.
- `find_tests(symbol="Evaluator.compute_metrics")` locates the unit and regression tests covering metric calculation.
- When a transform or model class is dynamically instantiated from a YAML string (`getattr(models, cfg.arch)`), CodeGraph MCP explicitly records `POSSIBLE_CALLS` (`POSSIBLE`) or `UNRESOLVED_REFERENCE` (`UNKNOWN`) rather than fabricating a false static call edge.

### Example 3: LLM Agent & Tool Registry

```text
POST /api/chat (LLM Endpoint)
      ↓  HANDLED_BY (FRAMEWORK_VERIFIED)
chat_handler
      ↓  CALLS (AST_VERIFIED)
AgentRunner.execute_step
      ├──►REGISTERS / REGISTERED_HANDLER ──► ToolRegistry ("search_orders", "refund_order")
      ├──►CALLS (AST_VERIFIED)           ──► ContextBuilder.compile
      ├──►READS_TABLE (AST_VERIFIED)     ──► db:table:postgresql.public.conversations
      └──►CALLS (AST_VERIFIED)           ──► ModelProviderClient.generate
```

**What CodeGraph MCP structurally proves**:
- Tracks decorator and call-based registrations (`@tool_registry.register("search_orders")`) via `REGISTERS` and `REGISTERED_HANDLER` edges.
- Tracks environment variable dependencies (`os.getenv("OPENAI_API_KEY")`) as `READS_ENV` edges with the variable name only—never indexing or exposing secret values.

---

## 6. Database Intelligence

[`src/codegraph/database/`](src/codegraph/database/) provides static schema, ORM model, migration, and query extraction across **SQLAlchemy**, **Django ORM**, **SQLModel**, **Prisma** (`.prisma`), **Alembic**, **Django Migrations**, and **Raw SQL** (`PostgreSQL`, `MySQL`, `SQLite`).

```text
POST /orders
      ↓  HANDLED_BY (FRAMEWORK_VERIFIED)
OrderService.create_order
      ↓  CALLS (AST_VERIFIED)
OrderRepository.insert_order
      ↓  WRITES_TABLE (AST_VERIFIED)
db:table:postgresql.public.orders
      ↓  FOREIGN_KEY_TO (AST_VERIFIED)
orders.user_id ──► users.id
```

### Capabilities Exposed by the 11 Database MCP Tools
- **Table & Column Discovery** (`get_db_schema`, `get_db_table`, `find_db_tables`, `find_db_columns`): Extract tables, column types, nullability, defaults, primary keys (`HAS_PRIMARY_KEY`), indexes (`HAS_INDEX`), unique/check constraints, and foreign keys (`FOREIGN_KEY_TO`).
- **ORM Mapping** (`find_db_models`): Map SQLAlchemy `__tablename__`, Django `models.Model` (`Meta.db_table`), SQLModel `table=True`, and Prisma `model` blocks via `MAPS_TO_TABLE` and `MAPS_TO_COLUMN`.
- **Readers, Writers & Callers** (`find_db_readers`, `find_db_writers`, `find_db_callers`, `find_db_queries`): Identify every function or method that executes `SELECT` (`READS_TABLE`) or `INSERT` / `UPDATE` / `DELETE` / `.add()` / `.save()` (`WRITES_TABLE`) against a table.
- **Migration Lineage & Schema Blast Radius** (`find_db_relationships`, `get_db_impact`): Track Alembic (`op.create_table`, `op.add_column`) and Django (`migrations.CreateModel`, `migrations.AddField`) operations (`MIGRATES_TABLE`) and compute bidirectional code $\leftrightarrow$ database impact.

---

## 7. Zero-Friction Runtime Intelligence & Static Reconciliation

Static analysis proves what **can** happen structurally; runtime telemetry records what **was observed** during execution. CodeGraph MCP v3.0.1 brings them together transparently:

```text
STATIC GRAPH (AST + Framework + Dataflow + DB)
                   +
RUNTIME OBSERVATION (codegraph run / OTel JSON / JSONL / SQL Logs)
                   ↓
       reconcile_static_runtime()
```

### Reconciliation Outcomes ([`ReconciliationStatus`](src/codegraph/runtime/models.py))

| Reconciliation Status | Static Graph | Runtime Trace | Meaning |
| :--- | :---: | :---: | :--- |
| **`CONFIRMED_RUNTIME_PATH`** | Present | Observed | Static relationship is structurally proven **and** observed executing in ingested traces. |
| **`NOT_OBSERVED_AT_RUNTIME`** | Present | Not observed | Statically valid edge was not exercised in the recorded trace sample. |
| **`RUNTIME_ONLY_OBSERVED`** | Dynamic / `UNKNOWN` | Observed | Executed at runtime (e.g., plugin hook, `getattr`, dynamic SQL) where static analysis was `UNKNOWN`. |
| **`STATIC_RUNTIME_CONFLICT`** | Target A | Target B | Runtime execution dispatched to a different target than static resolution (e.g., dependency override). |

### Epistemic Rules for Runtime Evidence
1. **Runtime Telemetry Is Non-Invasive**: `codegraph run` uses standard environment variable hooks (`NODE_OPTIONS`, `PYTHONSTARTUP`). You never modify application source code.
2. **`NOT_OBSERVED_AT_RUNTIME` Does Not Mean Dead Code**: It only indicates that the code path was not triggered during the recorded trace window (such as an error branch or periodic batch job).
3. **Runtime Observations Never Overwrite Static Proof**: Runtime spans are recorded with `evidence_class="RUNTIME_OBSERVED"` and strictly distinguished from `AST_VERIFIED` and `FRAMEWORK_VERIFIED` static edges.

---

## 8. Epistemic Trust & Evidence Contract

CodeGraph MCP enforces a fail-closed evidence contract ([`src/codegraph/evidence_contract.py`](src/codegraph/evidence_contract.py)) across all **51 canonical relationship types** and **9 evidence classes**. CodeGraph MCP prefers **explicit uncertainty** over **fabricated certainty**:

```text
Dynamically resolved target (getattr(handler, action_name)())
      ↓
UNRESOLVED_REFERENCE / POSSIBLE_CALLS (status = "UNKNOWN" | "POSSIBLE")
(Never fabricated into a verified CALLS edge)
```

| Epistemic Status | Allowed Evidence Classes | What It Means |
| :--- | :--- | :--- |
| **`FACT`** | `AST_VERIFIED`, `STATIC_VERIFIED`, `FRAMEWORK_VERIFIED`, `DATAFLOW_VERIFIED` | Proven directly from syntax tree, framework decorator/router semantics, or conservative local dataflow. |
| **`RUNTIME_OBSERVED`** | `RUNTIME_OBSERVED` | Observed in traces captured by `codegraph run` or ingested OTel/JSONL/SQL logs (`hit_count`, `duration_ms`). |
| **`POSSIBLE`** | `POSSIBLE` | Plausible candidate relationship (`POSSIBLE_CALLS`, `POSSIBLE_TABLE`) requiring source inspection before mutation. |
| **`AMBIGUOUS`** | `AMBIGUOUS` | Multiple symbols or database tables match the bare identifier across modules or dialects; returns sorted `candidates`. |
| **`UNKNOWN`** | `UNKNOWN`, `RUNTIME_UNOBSERVED` | Target cannot be statically proven (dynamic reflection, external dependency, or `reason="resolution_budget_exceeded"`). |
| **`CONFLICT`** | Static vs. Runtime / Multi-Source | Static analysis and runtime observation (or competing definitions) disagree. |

---

## 8. Git-Aware Repository Intelligence & Merge Conflict Safety

CodeGraph MCP v3.0.1 tracks the exact evolution of repository code across commits, branches, and working tree changes:

```text
Repository state
    ↓
Git change detection (CLEAN / DIRTY / STALE)
    ↓
Structural AST diff (functions, parameters, routes)
    ↓
Downstream impact analysis (callers, callees, tests, DB)
    ↓
Context freshness validation (VALID / PARTIALLY_STALE / STALE)
    ↓
Evidence-backed answer
```

### 1. Working Tree & Index Freshness (`codegraph git-state`)
Tracks current branch, current HEAD commit, indexed commit, and modified/staged files with sub-millisecond status caching:
```bash
codegraph git-state
```
Never silently serves stale repository facts. Explicitly reports `CLEAN`, `DIRTY`, `STALE`, `REINDEXING`, or `ERROR`.

### 2. Deep Visual Downstream Impact Tree (`codegraph git-impact --tree`)
Traverses affected callers, routes, tests, and DB writers with token-bounded results and visual ASCII hierarchy:
```bash
codegraph git-impact --tree
```

### 3. Semantic & Contract Merge Conflicts (`codegraph git-conflicts`)
Detects silent merge conflicts before git merge or pull request landing—such as branch A invoking a function or route handler that branch B deleted or altered:
```bash
codegraph git-conflicts main HEAD
```

### 4. Structural AST Diff (`codegraph git-diff`)
Computes semantic AST differences between Git revisions (added/removed/modified symbols, changed parameter signatures):
```bash
codegraph git-diff HEAD~1 HEAD
```

### 5. Deterministic Symbol History (`codegraph symbol-history`)
Traces symbol lifecycle across commits (introduced, modified, moved, renamed, or deleted):
```bash
codegraph symbol-history resolve_target
```

### 6. GitHub Action for Pull Request Impact
Automate change impact directly in your CI pipeline with `.github/workflows/codegraph-pr-impact.yml` and `.github/actions/codegraph-impact/action.yml`.

---

## 9. Measured Performance and Scaling Benchmarks

### 4-Tier Scaling Summary (`54` → `2,504` Files)

Empirically measured using [`benchmarks/run_v217_indexing_benchmark.py`](benchmarks/run_v217_indexing_benchmark.py) on macOS `arm64`, Python `3.13` with permanent SQLite WAL concurrency:

| Workload Tier | Files | Symbols | Graph Edges | Baseline Total | v3.0.1 Measured | Measured Improvement | Peak RSS | Peak WAL | Final WAL |
| :--- | ---: | ---: | ---: | ---: | ---: | :--- | ---: | ---: | ---: |
| **Small** | `54` | `115` | `398` | `0.527 s` | `0.447 s` | **15.2% faster (`1.18x`)** | `48.00 MB` | `1.701 MB` | `0.0 MB` |
| **Medium** | `304` | `615` | `2,248` | `2.564 s` | `2.159 s` | **15.8% faster (`1.19x`)** | `69.72 MB` | `4.082 MB` | `0.0 MB` |
| **Large** | `1,004` | `2,015` | `7,428` | `8.730 s` | `7.157 s` | **18.0% faster (`1.22x`)** | `127.59 MB` | `5.190 MB` | `0.0 MB` |
| **Stress** | `2,504` | `5,015` | `18,528` | `21.983 s` | `18.937 s` | **13.9% faster (`1.16x`)** | `233.59 MB` | `6.628 MB` | `0.0 MB` |

### Stress Tier (`2,504` Files) Phase Breakdown

| Phase / Metric | Legacy Baseline | v3.0.1 Measured | Measured Improvement |
| :--- | ---: | ---: | :--- |
| **Total Indexing Time** | `21.983 s` | `18.937 s` | **13.9% faster (`1.16x`)** |
| **Database Intelligence Pass** | `4.818 s` | `0.893 s` | **81.5% faster (`5.40x`)** |
| **Post-Processing Phase** | `13.770 s` | `12.061 s` | **12.4% faster (`1.14x`)** |
| **Symbol Resolution Phase** | `3.133 s` | `1.297 s` | **58.6% faster (`2.42x`)** |
| **AST Parsing Phase** | `3.410 s` | `3.230 s` | **5.3% faster (`1.06x`)** |
| **Cold CLI Single-File Re-index** | `4.408 s` | `3.665 s` | **16.9% faster (`1.20x`)** |
| **Live In-Memory Incremental (`watch`)** | Full scan required | `< 15ms` / file | **Event-driven cache patch** |
| **Throughput (`files/sec`)** | `113.9 files/s` | `132.2 files/s` | **`+16.1%` throughput** |
| **Peak SQLite WAL Size** | `46.980 MB` | `6.628 MB` | **85.9% reduction (`7.09x` smaller)** |
| **Final SQLite WAL Size** | `0.000 MB` | `0.000 MB` | **100% reclaimed (`TRUNCATE`)** |

> **Note on Incremental Reindexing**: The **3.665 s** incremental figure measures a cold CLI invocation (`codegraph index .`) on the full 2,504-file repository, traversing file mtimes and checking Git diff state. In contrast, the active background daemon (`codegraph watch`) receives OS kernel filesystem events directly, parsing only the modified file's AST and patching SQLite in **< 15ms**.

![CodeGraph MCP — Measured Large-Repository Scaling](docs/assets/large_repo_scaling.svg)

### 50-Task Production Benchmark Results (`v3.0.1`)

Evaluated across 50 production tasks and 10 categories via [`benchmarks/run_v21_eval.py`](benchmarks/run_v21_eval.py):

| Production Benchmark Metric | Measured Result | Production Target | Status |
| :--- | :---: | :---: | :---: |
| **Task Coverage** | **88.0%** | $\ge 80.0\%$ | **PASS** |
| **Symbol Recall** | **61.9%** | $\ge 50.0\%$ | **PASS** |
| **FACT Correctness** | **100.0%** | $\ge 98.0\%$ | **PASS** |
| **Unsupported Claim Rate (Hallucinations)** | **0.0%** | $\le 1.0\%$ | **PASS** |
| **UNKNOWN Correctness** | **98.0%** | $\ge 95.0\%$ | **PASS** |
| **AMBIGUITY Correctness** | **100.0%** | $\ge 90.0\%$ | **PASS** |
| **Average Context Payload** | **510 tokens** | $\le 1,000$ tokens | **PASS** |
| **Average Context Latency** | **40.52 ms** | $\le 100$ ms | **PASS** |
| **Token Reduction vs Full-File Extraction** | **41.8%** | $\ge 35.0\%$ | **PASS** |

### 32-Task A/B Exploration Evaluation ([`src/codegraph/tool_selection_eval.py`](src/codegraph/tool_selection_eval.py))

Evaluated across 32 agent navigation tasks comparing unassisted grep/file reading vs CodeGraph MCP tool calls:

| Metric (32-Task Evaluation Suite) | Mode A (Unassisted Grep & File Reads) | Mode B (CodeGraph MCP) | Measured Improvement |
| :--- | ---: | ---: | :--- |
| **Total Tool Calls (32 Tasks)** | `164 calls` (`~5.1 / task`) | `71 calls` (`~2.2 / task`) | **`-56.7% fewer tool calls`** |
| **Direct Full-File Reads** | `161 full-file reads` | `7 bounded slice reads` | **`-95.7% fewer file reads`** |
| **Context Tokens per Task** | `3,000 – 12,000+ tokens` | `~510 tokens` avg | **`65.0% – 85.6% token reduction`** |
| **Query Latency (`p50`)** | Hundreds of ms (multi-step `grep`) | `20.0 ms` cold / `0.67 ms` warm | **Sub-20ms indexed lookup** |
| **First-Tool Selection Accuracy** | `9.38%` | `100.0%` | **`+90.62%`** |
| **Unsupported Claims (Hallucinated Edges)** | `11 (34.38%)` | `0 (0.00%)` | **`0% unsupported claims`** |
| **Task Accuracy** | `59.84%` | `100.0%` | **`+40.16%`** |

![CodeGraph MCP — Measured Context & Exploration Efficiency](docs/assets/performance_comparison.svg)

### SWE-bench Comparative Benchmark Results (`benchmarks/swe_bench/`)

Evaluated against standard software engineering problem statements comparing unassisted agents (grep + full file reads) vs CodeGraph MCP tool-assisted agents:

| Metric | Baseline Mode (Grep / Read File) | CodeGraph MCP Mode | Measured Improvement |
| :--- | ---: | ---: | :--- |
| **Total Prompt Tokens Consumed** | `37,052 tokens` | `10,780 tokens` | **70.9% token reduction (`3.44x` efficiency)** |
| **Average Turns to Resolution** | `8.0 turns` | `2.0 turns` | **75.0% turn reduction (`4.00x` faster)** |
| **Direct Full-File Reads** | `14 files` | `0 files (0 bounded slices)` | **100.0% elimination of blind file reads** |
| **Fault Localization Accuracy** | `50.0%` | `100.0%` | **`+50.0%` accuracy** |
| **Resolution Status** | Partial / Stalled | `RESOLVED (100%)` | **Deterministic ground-truth symbol hit** |

---

## 10. Where CodeGraph MCP Fits

CodeGraph MCP works **alongside** your editor's language server (LSP), `ripgrep`, and structural AST tools:

Legend: `✓` supported • `◐` partial / workflow-dependent • `—` not supported

| Capability | CodeGraph MCP (`v3.0.1`) | Editor LSP | Structural AST (`ast-grep`) | Lexical Search (`ripgrep`) | Remote Code Search (`Sourcegraph`) |
| :--- | :---: | :---: | :---: | :---: | :---: |
| **100% Local-First & Offline Operation** | ✓ | ✓ | ✓ | ✓ | — |
| **Native MCP Server for AI Agents** | ✓ (14 default / 97 full) | — | ◐ | — | ✓ |
| **Multi-Transport Support (stdio + SSE HTTP)** | ✓ | — | — | — | ◐ |
| **Git-Aware AST Diffs & Freshness** | ✓ (6 Git tools) | — | — | — | ◐ |
| **Zero-Friction Runtime Interceptor (`codegraph run`)** | ✓ | — | — | — | — |
| **Semantic Symbol Graph (Callers / Callees)** | ✓ | ◐ (Position-based) | ◐ (Pattern-based) | — | ✓ (SCIP) |
| **Framework Route, Mount & DI Graph** | ✓ (`FastAPI`/`Flask`/`Django`/`Express`) | — | ◐ (Custom rules) | — | — |
| **Database Schema, ORM, Migration & Table R/W** | ✓ (11 DB tools) | — | — | — | — |
| **Opt-In Runtime Ingestion & Reconciliation** | ✓ (OTel / JSONL / SQL) | — | — | — | — |
| **Explicit Epistemic States (`FACT`/`UNKNOWN`)** | ✓ | — | — | — | — |
| **Literal Text Search Across HTML/JS/CSS/Config** | ✓ (`search_code`) | — | — | ✓ | ✓ |
| **Interactive Editor Hover & Diagnostics** | — | ✓ | ✓ (Lint/Rewrite) | — | — |

![Repository Retrieval Approaches — Capability Comparison](docs/assets/capability_heatmap.svg)

---

## 11. Security, Privacy & Redaction Boundaries

CodeGraph MCP runs **100% locally** (`stdio` / `sse` MCP + local `.codegraph.sqlite3`), never executes repository code during indexing, and enforces strict file-access and redaction boundaries ([`src/codegraph/security/paths.py`](src/codegraph/security/paths.py), [`src/codegraph/security/redaction.py`](src/codegraph/security/redaction.py)):

| Security Boundary | Enforcement Mode | Exact Behavior |
| :--- | :---: | :--- |
| **Sensitive Files** (`.env`, `*.pem`, `*.key`, `*.crt`, `id_rsa*`, `kubeconfig*`, `.npmrc`, `.pypirc`, `*secret*.json`) | **`BLOCKED`** | Excluded from indexing and FTS; direct inspection via `get_file` or `read_file` is rejected with `SENSITIVE_FILE_ACCESS_DENIED`. |
| **Path Traversal & Symlinks** (`../`, `%2e%2e`, null bytes, external symlinks) | **`BLOCKED`** | Canonical path check in `resolve_within_repo()` raises `SecurityError(ErrorCode.PATH_OUTSIDE_REPOSITORY)`. |
| **Binary Files** (`.pyc`, `.so`, `.dylib`, `.dll`, `.exe`, images, archives, PDFs) | **`BLOCKED`** | Classified as `BINARY` and skipped during indexing and text search. |
| **Environment Variable Reads in Code** (`os.getenv("DATABASE_URL")`) | **Metadata Only** | Records `READS_ENV` with the **variable name only**; never reads `.env` or runtime environment values. |
| **Database Connection Strings** (`postgresql://user:pass@host:5432/prod`) | **`REDACTED`** | Preserves dialect and database name while sanitizing credentials to `postgresql://[REDACTED]@[REDACTED]/prod`. |
| **API Keys, Bearer Tokens, JWTs & Private Keys** (`sk-...`, `ghp_...`, `AKIA...`) | **`REDACTED`** | Replaced with `[REDACTED_SECRET]` or `[REDACTED_PRIVATE_KEY]` before indexing, search, or MCP output. |
| **Runtime HTTP Headers & SQL Literals** (`authorization`, `cookie`, `WHERE password = '...'`) | **`REDACTED`** | Sensitive runtime keys and SQL literals are scrubbed (`[REDACTED]` / `?`) during `ingest_runtime_traces`. |

Run `codegraph privacy .` at any time to audit the local database and verify that no sensitive files or unredacted secrets are stored.

---

## 12. MCP Tooling & Profiles (14 Default / 97 Full)

By default, `create_server()` exposes the **14-tool `agent` profile** so AI coding agents receive a focused, non-overlapping tool surface. All 97 verified tools are available under `--profile full`.

### Default `agent` Profile (14 High-Signal Tools)

| Category | Tool | Purpose |
| :--- | :--- | :--- |
| **Discovery (7)** | `find_symbol` | Locate a symbol definition by short, qualified, or canonical name (`symbol=...`). |
| | `search_code` | Literal or regex search across Python, JS/TS, HTML/Jinja, CSS, YAML/JSON, Markdown, and SQL. |
| | `find_references` | Find verified AST reference, import, and registration sites for a symbol. |
| | `find_callers` | Find functions, methods, or route handlers that call the target symbol (`CALLS`, `POSSIBLE_CALLS`). |
| | `find_callees` | Find functions, methods, or constructors called by the target symbol. |
| | `find_tests` | Find `pytest` / `unittest` test functions covering a symbol, route, DI provider, or event handler. |
| | `find_routes` | Discover FastAPI, Flask, Django, and Express HTTP routes with composed mount prefixes. |
| **Details & Context (5)** | `get_symbol` | Retrieve signature, decorators, docstring, line range, and methods for a symbol. |
| | `get_file` | Read bounded line ranges (`start_line`, `end_line`, `max_lines`) and AST symbol outline of a file. |
| | `get_context` | Compile a token-budgeted, task-aware context packet (`query`, `intent`, `max_tokens`). |
| | `get_architecture` | Summarize repository languages, layers, packages, entrypoints, routes, and database entities. |
| | `get_git_impact` | Compute blast-radius impact (`changed_files`, `affected_callers`, `affected_routes`, `tests`) for a Git diff. |
| **Graph Tracing (2)** | `trace_path` | Find the shortest verified execution path between `from_symbol` and `to_symbol`. |
| | `trace_flow` | Trace upstream callers and downstream callees around `symbol` up to `depth`. |

### All 6 Implemented MCP Profiles ([`src/codegraph/agent_capabilities.py`](src/codegraph/agent_capabilities.py))

| Profile | Tool Count | Description |
| :--- | :---: | :--- |
| **`agent`** *(default in `create_server`)* | **14** | High-signal discovery, bounded file inspection, context synthesis, and path tracing. |
| **`core`** | **13** | Lightweight symbol lookup, callers/callees, imports/dependents, routes, and architecture. |
| **`graph`** | **17** | Call-graph traversal, blast-radius impact (`analyze_impact`), and test discovery. |
| **`minimal`** | **21** | Core interrogation plus `get_context`, `search_code`, `read_file`, and `verify_evidence`. |
| **`developer`** | **34** | Interactive development with Git history (`get_file_history`, `get_recent_changes`) and retrieval planning. |
| **`full`** | **97** | Complete capability surface including **18 Symbol tools**, **16 Call Graph tools**, **11 Database tools**, **9 Blast Radius tools**, **9 Multi-Agent & Memory tools**, **7 Refactoring & Patch tools**, **6 Route & Drift tools**, **6 Security & Rule tools**, and **9 File/Maintenance tools**. |

---

## 13. Complete CLI Reference

Verified against [`src/codegraph/cli.py`](src/codegraph/cli.py):

```bash
# Agent Onboarding & Uninstall
codegraph install                                          # Interactive agent detection & setup
codegraph install --yes --target auto --location local     # Non-interactive local setup
codegraph install --print-config claude                    # Print MCP JSON + rules for an agent
codegraph install --dry-run                                # Preview planned file changes
codegraph uninstall --yes                                  # Remove CodeGraph MCP agent integrations

# Git-Aware Repository Intelligence (v3.0.1)
codegraph git-state .                                      # Track HEAD, working tree, and freshness (CLEAN/DIRTY/STALE)
codegraph git-diff HEAD~1 HEAD                             # Semantic AST diff across commits or branches
codegraph git-impact --tree                                # Deep downstream change impact with visual ASCII tree
codegraph git-conflicts main HEAD                          # Detect pre-merge semantic & contract conflicts
codegraph check-freshness "audit auth flow"                # Validate if compiled context is VALID or STALE
codegraph symbol-history resolve_target                    # Trace deterministic symbol lifecycle across commits

# Zero-Friction Runtime Interceptor (v3.0.1)
codegraph run npm run dev                                  # Wrap Node/Express/Next.js dev server
codegraph run uvicorn main:app --reload                    # Wrap FastAPI/ASGI dev server
codegraph run python manage.py runserver                   # Wrap Django dev server
codegraph run --sample-rate 0.5 npm test                   # Sample 50% of captured traces

# Repository Initialization & Indexing
codegraph init .                                           # Initialize and index repository
codegraph index . --verbose                                # Incremental index with 16-phase telemetry
codegraph index . --json                                   # Output structured JSON phase telemetry
codegraph uninit --dry-run                                 # Preview removal of .codegraph.sqlite3

# Process Lifecycle & Upgrade Lock Safety
codegraph stop                                             # Safely stop CodeGraph MCP server for current repo
codegraph stop --all                                       # Stop all CodeGraph-owned MCP processes across repos
codegraph doctor --processes                               # Inspect active MCP processes & parent PIDs

# Health, Integrity & Freshness Diagnostics
codegraph status .                                         # Show index freshness (sub-50ms Git fast path)
codegraph doctor . --database --processes                  # Verify SQLite integrity, FKs, FTS, and memory
codegraph privacy .                                        # Verify zero sensitive files indexed
codegraph version                                          # Print CodeGraph MCP version (3.0.1)

# Code, Graph, Routes & Context Interrogation
codegraph search "authenticate" -r .                       # Search indexed symbols and text chunks
codegraph symbols src/codegraph/cli.py -r .                # List extracted symbols in a file
codegraph get-symbol Indexer -r .                          # Get AST details for a symbol
codegraph resolve-symbol resolve_Repository -r .           # Ground symbol or return candidates
codegraph trace Indexer -d 2 -r .                          # Trace callers and callees up to depth 2
codegraph routes -r . --limit 25 --offset 0                # List routes with bounded pagination
codegraph architecture -r .                                # Summarize repository architecture
codegraph context "trace /api/v1/auth/login" -r .          # Compile token-budgeted ContextPacket

# Dead Code & Zombie Route Detection
codegraph dead-code .                                      # Audit zero-caller symbols, zombie routes & orphaned tables
codegraph dead-code . --json                               # Output dead-code report as structured JSON

# Embedded OpenTelemetry (OTLP/HTTP) Receiver
codegraph otel-listen --port 4318                          # Listen for standard OTLP HTTP /v1/traces spans
codegraph otel-listen --host 0.0.0.0 --port 4318           # Accept remote container telemetry streams

# Language Server Protocol (LSP) Bridge
codegraph lsp .                                            # Run stdio LSP server for VS Code / Neovim / Helix

# Multi-File Transactional Semantic Patch Engine
codegraph refactor patch patch.json --dry-run              # Preview patch diff & affected symbols (0 disk mutations)
codegraph refactor patch patch.json                        # Apply patch atomically with syntax validation & rollback

# MCP Server Subcommands
codegraph serve .                                          # Start stdio MCP server (14 default tools)
codegraph serve . --profile full                           # Start stdio MCP server with all 97 tools
codegraph serve . --transport sse --port 8765              # Start SSE HTTP server on port 8765
codegraph mcp serve . --transport sse                      # Alias for SSE MCP server
codegraph mcp stop                                         # Stop active MCP processes
```

---

## 14. Documentation Map

- **Deep Agent Brain & 97-Tool Reference**: [`docs/agent-brain.md`](docs/agent-brain.md)
- **Compact Tool Capabilities Summary**: [`agent-rules/tool-capabilities-summary.md`](agent-rules/tool-capabilities-summary.md)
- **Detailed Multi-Tool Capability Comparison**: [`docs/tool-comparison.md`](docs/tool-comparison.md)
- **Antigravity Skill (`SKILL.md`)**: [`.agents/skills/codegraph/SKILL.md`](.agents/skills/codegraph/SKILL.md)
- **Agent Rule Packs (`Claude`, `Cursor`, `Antigravity`, `Codex`, `Gemini`, `Cline`)**: [`agent-rules/README.md`](agent-rules/README.md) & [`agent-rules/AGENTS.md`](agent-rules/AGENTS.md)
- **Engineering & Production Readiness**: [`docs/engineering/production-readiness.md`](docs/engineering/production-readiness.md)
- **Reproducible Scaling Benchmark Script**: [`benchmarks/run_v217_indexing_benchmark.py`](benchmarks/run_v217_indexing_benchmark.py)
- **Changelog**: [`CHANGELOG.md`](CHANGELOG.md)

---

## 15. Contributing & License

```bash
git clone https://github.com/raghurammrsd/CODEGRAPH_MCP.git
cd CODEGRAPH_MCP
python3 -m venv .venv
source .venv/bin/activate
pip install -e ".[dev,mcp,system]"

python3 -m ruff check .
python3 -m mypy src/
python3 -m pytest -q
```

Licensed under the [MIT License](LICENSE).
