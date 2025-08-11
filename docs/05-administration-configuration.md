# Configuration Guide

Claude Worker can be configured through environment variables and local configuration files. This guide details the available settings, their priority, and the current limitations.

## Client-Side Configuration (CLI)

The `claude-worker` CLI needs to know the URL of the server to connect to. This is determined using a layered approach, defined in `cli/config.py`.

**Priority Order:**

1.  **Environment Variable (Highest Priority):**
    The `CLAUDE_WORKER_SERVER_URL` environment variable will always be used if it is set.
    ```bash
    export CLAUDE_WORKER_SERVER_URL="http://192.168.1.100:9000"
    claude-worker list
    ```

2.  **Configuration File:**
    If the environment variable is not set, the CLI will look for a `config.json` file in the application directory (`~/.config/claude-worker/config.json` on Linux).
    ```json
    {
      "server_url": "http://claude-worker.local:8000"
    }
    ```

3.  **Default Value (Lowest Priority):**
    If neither of the above is found, the CLI will fall back to the default URL: `http://localhost:8000`.

## Server-Side Configuration

Server-side settings control the behavior of the worker processes, database location, and more.

### Environment Variables

*   `ANTHROPIC_API_KEY`: **(Required)** Your API key for the Anthropic API, used by the Claude Code SDK.
*   `CLAUDE_WORKER_DB`: The path to the SQLite database file. (Default: `~/.claude-worker/tasks.db`)
*   `CLAUDE_WORKER_LOG_DIR`: The directory where task logs will be stored. (Default: `~/.claude-worker/logs`)

### Hardcoded Settings & Current Limitations

To maintain simplicity in the initial version, some important settings are currently hardcoded in the source. We plan to make these configurable in future releases. **This is an honest assessment of the current limitations.**

*   **Maximum Concurrent Workers (`max_workers`)**:
    *   **Location:** `src/server/main.py`
    *   **Current Value:** `4`
    *   **Description:** This controls the size of the `ProcessPoolExecutor`, limiting the number of tasks that can run simultaneously. To change this, you must edit the source file directly.
        ```python
        # src/server/main.py
        executor_pool = ProcessPoolExecutor(max_workers=4) 
        ```

*   **Database Path (Server-side default)**:
    *   **Location:** `src/server/database.py`
    *   **Current Value:** `~/.claude-worker/tasks.db`
    *   **Description:** While this can be overridden by the `CLAUDE_WORKER_DB` environment variable, the default path is defined here.

*   **Log Directory (Server-side default)**:
    *   **Location:** `src/server/main.py`
    *   **Current Value:** `~/.claude-worker/logs`
    *   **Description:** Similar to the database path, this can be overridden by the `CLAUDE_WORKER_LOG_DIR` environment variable.

We understand that hardcoded values are not ideal for production environments. Exposing these settings through a configuration file or environment variables is a high priority on our [Roadmap](./ROADMAP.md). Pointing this out helps prevent user frustration and directs those who need these features to the project's future plans.