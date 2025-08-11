# Overview

Welcome to the official documentation for **Claude Worker** v0.1.0, a flexible and robust fire-and-forget task execution system designed for the Claude Code SDK.

> **🚀 Current Status:** Beta - Production-ready for individual developers and small teams. See our [Roadmap](./ROADMAP.md) for upcoming enterprise features.

## What is Claude Worker?

Running long, complex tasks with the Claude Code SDK can be challenging. Your terminal is blocked, an interruption can lose hours of work, and managing multiple tasks is difficult. Claude Worker solves these problems by providing a persistent, scalable, and easy-to-integrate system.

### Core Features

*   **🔄 Fire-and-Forget Execution:** Submit a task and immediately get your terminal back. The server handles the execution in the background.
*   **💾 Persistent & Resilient:** Tasks are stored in a local SQLite database, so no work is lost even if the server restarts or crashes.
*   **🔒 Isolated & Scalable:** Each task runs in its own isolated process, preventing a single task failure from bringing down the entire system. Currently supports 4 concurrent workers (configurable in future releases).
*   **🔌 Flexible Integration:** Three ways to interact with the system:
    - **CLI**: Human-friendly `claude-worker` command-line interface
    - **REST API**: Formal HTTP endpoints for custom integrations
    - **MCP Server**: Machine-friendly interface for AI agents with built-in guardrails

### Quick Example

```bash
# Start the server (runs in background)
claude-worker server start

# Submit a task and continue working
claude-worker run "Refactor the authentication module in ./src/auth" --watch

# Check all tasks anytime
claude-worker list
```

## Documentation Layout

This documentation is structured to guide you from your first installation to advanced deployment and contribution. Here's a "Table of Contents" for the entire suite:

### 1. Getting Started

*   **[Installation](./01-getting-started-installation.md):** A comprehensive guide to setting up Claude Worker, including all prerequisites like Python and Node.js.
*   **[Quick Start](./01-getting-started-quick-start.md):** The "happy path" guide to starting the server and running your first task in minutes.

### 2. User Guide

*   **[CLI Reference](./02-user-guide-cli-reference.md):** A complete reference for every command and option available in the `claude-worker` command-line interface.
*   **[Advanced Task Submission](./02-user-guide-task-submission.md):** Learn how to submit tasks from files, command-line arguments, and piped `stdin` for powerful shell integration.
*   **[Monitoring & Logs](./02-user-guide-monitoring-and-logs.md):** Detailed instructions on how to check task status, list all tasks, watch progress in real-time, and inspect logs for debugging.

### 3. Core Concepts

*   **[Architecture](./03-concepts-architecture.md):** A high-level overview of the system's components and how they interact, from the API layer to the process pool.
*   **[Project Philosophy](./03-concepts-project-philosophy.md):** An explanation of the "Single Responsibility" design principle that guides the project's structure and makes it maintainable.
*   **[Process Isolation Model](./03-concepts-process-model.md):** A deep dive into how `ProcessPoolExecutor` is used to provide crash protection and concurrency.
*   **[Database Schema](./03-concepts-database-schema.md):** A guide to the `tasks` table schema, explaining the purpose of each field in the system's single source of truth.

### 4. Integrations

*   **[REST API Reference](./04-integrations-rest-api.md):** A formal, Swagger-like reference for the REST API, detailing every endpoint, method, and data model.
*   **[MCP for AI Agents](./04-integrations-mcp-for-agents.md):** A guide for integrating AI agents with the strict, machine-friendly MCP endpoint.

### 5. Administration

*   **[Deployment](./05-administration-deployment.md):** Best practices for running Claude Worker in a production environment using tools like `systemd` or Docker.
*   **[Configuration](./05-administration-configuration.md):** An exhaustive guide to configuring the system via environment variables and local files, including current limitations.
*   **[Security](./05-administration-security.md):** Critical security considerations and mitigation strategies for securing your Claude Worker instance.

### 6. Contributing

*   **[Contribution Guide](./06-contributing-guide.md):** The main guide for new contributors, explaining the development workflow and how to get started.
*   **[Development Setup](./06-contributing-development-setup.md):** Instructions for setting up a local development environment, including linters and formatters.
*   **[Project Roadmap](./ROADMAP.md):** The official public roadmap, highlighting planned features and areas where contributions are most needed.