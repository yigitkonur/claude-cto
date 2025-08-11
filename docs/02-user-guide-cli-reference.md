# CLI Command Reference

The `claude-worker` command-line interface (CLI) is your primary tool for interacting with the server. This document provides a complete reference for all available commands, arguments, and options.

Under the hood, every command is making a REST API call to the server. Understanding this connection helps you know what the CLI is *actually doing*.

---

## Task Management Commands

These commands are for submitting and monitoring tasks.

### `claude-worker run`

Submits a new task to the server. This command makes a `POST` request to the `/api/v1/tasks` endpoint.

**Usage:**

```bash
claude-worker run [PROMPT] [OPTIONS]
```

**Arguments:**

*   `PROMPT` (optional): The execution prompt for the task. Can be a string, a file path, or piped from stdin. See the [Advanced Task Submission](./02-user-guide-task-submission.md) guide for more details.

**Options:**

*   `--dir, -d PATH`: The working directory where the task should be executed. Defaults to the current directory.
*   `--system, -s TEXT`: A system prompt to guide the AI's behavior.
*   `--watch, -w`: After submitting the task, continuously poll and display its status in real-time until it completes or fails.

**Example:**

```bash
claude-worker run "Refactor the main.py file" --dir ./src --system "You are an expert Python developer" --watch
```

### `claude-worker status`

Retrieves the detailed status of a single task. This command makes a `GET` request to `/api/v1/tasks/{task_id}`.

**Usage:**

```bash
claude-worker status <TASK_ID>
```

**Arguments:**

*   `TASK_ID` (required): The integer ID of the task to inspect.

**Example:**

```bash
claude-worker status 42
```

### `claude-worker list`

Retrieves a list of all tasks known to the server. This command makes a `GET` request to `/api/v1/tasks`.

**Usage:**

```bash
claude-worker list
```

**Example:**

```bash
claude-worker list
```

---

## Server Management Commands

These commands are for managing the Claude Worker server process itself. They are available under the `server` subcommand.

### `claude-worker server start`

Launches the `uvicorn` server as a background (daemon) process. This command does **not** make an API call; it directly starts the server on your local machine.

**Usage:**

```bash
claude-worker server start [OPTIONS]
```

**Options:**

*   `--host, -h TEXT`: The host address to bind the server to. (Default: `0.0.0.0`)
*   `--port, -p INTEGER`: The port to run the server on. (Default: `8000`)
*   `--reload, -r`: Enable auto-reload mode. The server will restart automatically when code changes are detected. Ideal for development.

**Example:**

```bash
# Start in production mode on port 9000
claude-worker server start --port 9000

# Start in development mode
claude-worker server start --reload
```

### `claude-worker server health`

Checks the health of the running server. This command makes a `GET` request to the `/health` endpoint.

**Usage:**

```bash
claude-worker server health
```

**Example:**

```bash
claude-worker server health
```

This is a useful command to verify that the server started correctly and is responsive.