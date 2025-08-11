## 🚀 High Priority / Short-Term

These are foundational features to improve usability and reliability.

### 1. Core CLI Enhancements

*   **`claude-worker server stop` Command**
    *   **Description:** Implement a reliable command to stop the background server process started with `server start`.
    *   **User Benefit:** Provides a complete, managed lifecycle for the server directly from the command line, avoiding manual process killing.
    *   **Implementation:** The `server start` command could write the Process ID (PID) to a file (e.g., `~/.claude-worker/server.pid`), which `server stop` would then read and use to terminate the process.

*   **`claude-worker logs` Command**
    *   **Description:** Add a command to easily view the logs for a specific task without needing to know the full file path.
    *   **User Benefit:** Massively improves debugging and monitoring by making task-specific logs instantly accessible.
    *   **Implementation:** `claude-worker logs <task_id>` would fetch the log file path from the database and stream its contents to the console.

### 2. Full Configuration via CLI & Environment

*   **Description:** Remove all hardcoded settings (like `max_workers`) and make them configurable via environment variables and CLI flags.
*   **User Benefit:** Gives users complete control over their worker's performance and resource usage, directly addressing a major inaccuracy in the current documentation.
*   **Implementation:** Create a unified, server-side configuration loader that respects environment variables (e.g., `CLAUDE_WORKER_MAX_WORKERS`) and CLI options (`--workers`) to set runtime parameters.

### 3. Comprehensive Test Suite

*   **Description:** This is the **highest impact** area for contributions. Create a full test suite using `pytest` to ensure the reliability of all CLI and MCP functions.
*   **User Benefit:** A well-tested tool is a reliable tool. This increases user trust and stability.
*   **Implementation:** Add unit tests for core logic and integration tests for CLI commands and MCP tool interactions.

---

## 🌱 Medium Priority / Mid-Term

Features to add more powerful control and extensibility.

### 1. Advanced Task Control (CLI & MCP)

*   **Task Cancellation**
    *   **Description:** Implement a `claude-worker cancel <task_id>` command and a corresponding `cancel_task` MCP tool to gracefully terminate a running task.
    *   **User Benefit:** Allows users and agents to stop long-running or incorrect tasks without shutting down the entire worker.

*   **Task Prioritization**
    *   **Description:** Allow tasks to be submitted with a priority level (e.g., `claude-worker run "..." --priority high`) and have the worker pool execute higher-priority tasks first.
    *   **User Benefit:** Enables more sophisticated workflows where urgent tasks can jump the queue.

### 2. Plugin System for Custom MCP Tools

*   **Description:** Allow users to define their own Python functions and expose them as new tools to the Claude agent through MCP.
*   **User Benefit:** This is the ultimate extensibility feature, transforming Claude Worker from a generic executor into a specialized assistant that can use the user's own codebase as its toolset.
*   **Implementation:** Develop a mechanism for the server to discover and register "plugin" files or modules from a user-defined directory.

### 3. Production-Ready Database Support

*   **Description:** Abstract the database logic to allow for backends other than SQLite, such as PostgreSQL.
*   **User Benefit:** Enables scaling Claude Worker for team-wide or production use cases that require a more robust, concurrent database.

---

## 💡 Low Priority / Long-Term Ideas

"Nice-to-have" features for added robustness and security.

### 1. Task Resiliency Features

*   **Task Retries:** Automatically retry failed tasks a configurable number of times.
*   **Task Timeouts:** Automatically fail tasks that run longer than a specified duration.
*   **User Benefit:** Makes the worker system more robust against transient failures and runaway processes.

### 2. Optional Secure Access for Remote Servers

*   **Description:** Implement a simple, optional token-based security mechanism for users who run the worker server on a publicly accessible machine.
*   **User Benefit:** Provides a basic layer of security to prevent unauthorized task submission on remote deployments.
*   **Implementation:** An optional `CLAUDE_WORKER_ACCESS_TOKEN` could be configured. If set, the server would require a matching `X-API-Token` header on incoming requests.
