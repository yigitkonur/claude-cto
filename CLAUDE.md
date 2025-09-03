# CLAUDE.md

Technical guidance for Claude Code when working with this repository.

## 1. System Architecture in 3 Rules

This is a decoupled, fire-and-forget task execution system. Memorize these non-negotiable rules:

1.  **The CLI is a Dumb Client.** The `cli/` directory contains a stateless HTTP client. Its ONLY job is to send commands to the Server via the REST API. It holds NO business logic.
2.  **The Server is the Stateful Engine.** The `server/` directory contains a stateful FastAPI application. It manages the task lifecycle, database state, and all background execution.
3.  **The CRUD Layer is the Sacred DB Gateway.** All database operations (`SELECT`, `INSERT`, `UPDATE`) MUST go through the `server/crud.py` module. No other module is permitted to touch the database directly.

```text
+------------------+     +-------------------------------+     +-----------------------------------+
| CLI Process      |     | Server Process (API Layer)    |     | Server Process (Execution Layer)  |
| (Dumb Client)    |     | (Stateful Dispatcher)         |     | (Background Worker)               |
|------------------| HTTP|-------------------------------| IPC |-----------------------------------|
| `cli/main.py`    |---->| `server/main.py` (Endpoints)  |---->| `asyncio` Event Loop              |
| - Parse user cmd |     | - Validates request           |     | - Runs `TaskExecutor`             |
| - Call API       |     | - Calls CRUD to create task   |     | - Calls Claude SDK                |
| - Display result |<----| - Schedules task via `asyncio`|     | - Calls CRUD to update status     |
+------------------+     | - Immediately returns Task ID |     | - Manages logging & resources     |
                         +-------------------------------+     +-----------------------------------+
```

## 2. Module Responsibilities (The SOLE Principle)

Each file has one **Single, Overarching, Lucidly-stated Expertise (SOLE)**. Before you modify a file, understand its role.

| File Path | SOLE: Single Responsibility | Implementation Rules & Anti-Patterns |
| :--- | :--- | :--- |
| **`cli/config.py`** | Resolve the server URL for the client. | **Rule:** Defines the priority for finding the server: `ENV_VAR` > `config.json` > `default`. |
| **`cli/main.py`** | Define all user-facing Typer CLI commands. | **Rule:** MUST act as a stateless HTTP client using `httpx`. <br> **Anti-Pattern:** Adding any business logic or state management here. |
| **`core/database.py`** | Provide shared DB utilities for standalone mode. | **Rule:** Mirrors `server/database.py`'s critical `NullPool` config for SQLite thread safety. |
| **`core/error_codes.py`** | Define standardized error codes and categories. | **Rule:** Provides a structured vocabulary for errors, enabling consistent monitoring and alerting. |
| **`core/executor.py`** | Provide shared SDK execution logic for standalone mode. | **Rule:** Performs a direct call to the Claude SDK, bypassing all server infrastructure. |
| **`mcp/factory.py`** | Auto-detect and select the correct MCP mode. | **Rule:** The primary entry point for MCP. Its only job is to perform a health check and instantiate either the `proxy` or `standalone` server. |
| **`mcp/proxy.py`** | Provide a basic MCP proxy to the REST API. | **Rule:** The "simple" mode. Translates MCP tool calls directly into `/api/v1/mcp/tasks` API requests. |
| **`mcp/enhanced_proxy.py`**| Provide an MCP proxy with orchestration support. | **Rule:** Uses **in-memory state** to queue tasks for an orchestration group. Requires an explicit `submit_orchestration` call. |
| **`mcp/standalone.py`** | Provide a self-contained, serverless MCP server. | **Rule:** Runs independently. Uses the `core` module for direct DB access and execution, bypassing the REST API. |
| **`migrations/manager.py`** | Manage database schema versioning. | **Rule:** Applies versioned SQL changes to the database. Ensures both fresh installs and upgrades result in a compatible schema. |
| **`server/main.py`** | Define FastAPI endpoints & manage server lifecycle. | **Rule:** The **central dispatcher**. Endpoints orchestrate calls to `crud.py` and start background tasks via `asyncio.create_task`. Manages startup/shutdown. |
| **`server/models.py`** | Define all SQLModel/Pydantic data contracts. | **Rule:** The **single source of truth for all data shapes**. Changes to data structures start here. |
| **`server/crud.py`** | Isolate all database operations (CRUD). | **Rule:** The **ONLY module that touches the database**. Contains all `session.commit()` calls. Functions MUST be pure and stateless. |
| **`server/database.py`** | Manage the server's database engine and sessions. | **Rule:** Initializes the server's primary DB connection. **CRITICAL:** Enforces `NullPool` for SQLite thread safety. |
| **`server/executor.py`** | Execute a single task using the Claude Code SDK. | **Rule:** The **bridge to the Claude SDK**. Wraps the `claude_code_sdk.query()` call and manages the full lifecycle (logging, error handling, status updates) for ONE task. |
| **`server/orchestrator.py`**| Manage DAG execution of dependent tasks. | **Rule:** A **DAG (Directed Acyclic Graph) runner**. MUST use `asyncio.Event` for efficient, non-polling dependency waits. Validates graphs for cycles. |
| **`server/error_handler.py`**| Classify SDK errors and provide recovery info. | **Rule:** All SDK exceptions from `TaskExecutor` MUST be processed here. Differentiates transient vs. permanent errors. |
| **`server/retry_handler.py`**| Implement retry logic and circuit breaking. | **Rule:** Wraps critical operations to handle transient errors. Prevents cascading failures. Persists state via `circuit_breaker_persistence.py`. |
| **`server/circuit_breaker_persistence.py`**| Persist circuit breaker states to disk. | **Rule:** Manages atomic, JSON-based persistence. **CRITICAL:** Its `cleanup_old_states()` method MUST be called periodically to prevent disk leaks. |
| **`server/subprocess_manager.py`**| Safely run external command-line processes. | **Rule:** All `subprocess` calls MUST go through this manager to ensure consistent timeout handling and prevent hung processes. |
| **`server/memory_monitor.py`** | Monitor system and task resource usage. | **Rule:** Runs as a background daemon. **CRITICAL:** Its `cleanup_old_metrics()` method MUST be called periodically to prevent memory leaks. |
| **`server/log_formatter.py`** | Provide pure functions to format SDK messages. | **Rule:** Translates structured `ContentBlock` objects from the SDK into human-readable log strings. |
| **`server/task_logger.py`** | Manage structured logging for individual tasks. | **Rule:** Generates `summary` and `detailed` logs. **CRITICAL:** Its `close()` method MUST be called after each task to release file handlers and prevent resource leaks. |
| **`server/path_utils.py`** | Generate safe, unique, cross-platform file paths. | **Rule:** All log filenames MUST be generated here to ensure consistency and prevent collisions. |
| **`server/notification.py`** | Provide non-blocking, cross-platform audio notifications. | **Rule:** Detects the host OS and uses the appropriate command-line tool to play sounds in a background thread. |
| **`server/server_logger.py`** | Configure the server's global logging infrastructure. | **Rule:** Sets up rotating file handlers for `server.log`, `error.log`, `access.log`, and handles crash reporting. |

## 3. Critical System Constraints & Anti-Patterns

Violating these will cause deadlocks, resource leaks, or critical failures.

| Constraint / Anti-Pattern | Reason & Correct Implementation |
| :--- | :--- |
| **NEVER use `ProcessPoolExecutor` for tasks.** | The Claude SDK's OAuth authentication flow fails in subprocesses. <br> **CORRECT:** Always use `asyncio.create_task` to run tasks in the main server process's event loop. |
| **NEVER use `StaticPool` with SQLite.** | This causes "database is locked" errors and data corruption in multi-threaded applications. <br> **CORRECT:** The database engine `create_engine` call **MUST** use `poolclass=NullPool`. |
| **NEVER access the database directly.** | This violates the architecture and makes the system brittle. <br> **CORRECT:** All database interactions **MUST** be performed by calling functions in `server/crud.py`. |
| **MUST implement resource cleanup.** | Unclosed file handlers and ever-growing in-memory caches are the primary causes of leaks. <br> **CORRECT:** `TaskLogger` must be closed; `MemoryMonitor`, `CircuitBreakerPersistence`, and `mcp/enhanced_proxy` MUST have periodic cleanup routines. |
| **NEVER poll for dependency completion.** | This is inefficient and scales poorly. <br> **CORRECT:** The `TaskOrchestrator` **MUST** use `asyncio.Event` for efficient, event-driven waiting. |

## 4. Golden Path: How to Add a Feature

Follow this workflow: **Model → CRUD → Logic → API → CLI**

1.  **Model (`server/models.py`):** Define the data shape first. This is your contract.
2.  **CRUD (`server/crud.py`):** Create functions to interact with the new data model.
3.  **Business Logic (e.g., `server/executor.py`):** Implement the core functionality, using the CRUD layer.
4.  **API Endpoint (`server/main.py`):** Expose the logic via a new FastAPI endpoint.
5.  **CLI Command (`cli/main.py`):** Create a user-facing command to call the new API.

## 5. Development & Testing

```bash
# Run the main REST API server with live reload for development
claude-cto server start --reload

# Run the standalone MCP server for testing its interface
python -m claude_cto.mcp.factory

# Run reliable unit and integration tests before committing
./run_tests.sh
```

## 6. Version Management System

When implementing version bumping and release automation, follow these critical guidelines:

### Version Files Must Stay Synchronized
- **ALL version files must update atomically**: `pyproject.toml`, `__init__.py`, `smithery.yaml`
- **Never use `poetry version` alone** - it only updates `pyproject.toml`
- Add explicit `sed` commands or use `scripts/sync_versions.py` to update all locations

### GitHub Workflows Requirements
1. **Add concurrency control** to prevent simultaneous version bumps:
   ```yaml
   concurrency:
     group: version-management
     cancel-in-progress: false
   ```

2. **Verify version sync** after any bump:
   ```bash
   python -c "import claude_cto; assert claude_cto.__version__ == '$NEW_VERSION'"
   ```

3. **Commit all version files together**:
   ```bash
   git add pyproject.toml claude_cto/__init__.py smithery.yaml CHANGELOG.md
   ```

### Essential Scripts and Tools
- **`scripts/sync_versions.py`** - Detects and fixes version mismatches
- **`scripts/bump_version_enhanced.py`** - Safe version bumping with conflict detection
- **Git pre-push hook** - Blocks pushing if versions mismatch
- **Emergency recovery workflow** - `.github/workflows/emergency-version-fix.yml`

### Common Pitfalls to Avoid
- ❌ Don't rely on single tool (poetry/npm) to update all files
- ❌ Don't use complex regex in shell scripts - use `exec()` or simple parsing
- ❌ Don't allow concurrent workflow runs for version operations
- ✅ Always fetch remote tags before comparing versions
- ✅ Test version extraction locally before pushing workflow changes
- ✅ Use `[skip ci]` in auto-version commit messages to prevent loops