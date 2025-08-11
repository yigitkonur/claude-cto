# Project Philosophy

The design of Claude Worker is guided by a simple yet powerful principle: **Single Responsibility**. This is not just a vague guideline; it is an enforced convention reflected in the "SOLE RESPONSIBILITY" docstrings at the top of every major module in the `cli` and `server` directories.

This philosophy is based on the [Single Responsibility Principle (SRP)](https://en.wikipedia.org/wiki/Single-responsibility_principle), which states that every module, class, or function should have responsibility over a single part of the software's functionality.

## The "SOLE" Acronym

To make this principle memorable and explicit, we use the acronym **SOLE**:

**S**ingle, **O**verarching, **L**ucidly-stated **E**xpertise.

Each key module is an "expert" in one thing and one thing only.

### Examples in Practice

*   `src/server/main.py`:
    > **SOLE RESPONSIBILITY:** The system's central hub. Initializes the FastAPI and FastMCP apps, defines all API endpoints, manages the ProcessPoolExecutor, and orchestrates the overall server lifecycle.
    >
    > *It knows how to handle web requests, but not how to run a task.*

*   `src/server/executor.py`:
    > **SOLE RESPONSIBILITY:** Defines the TaskExecutor class, which encapsulates the logic for running a single agentic task using the Claude Code SDK's query() function.
    >
    > *It knows how to run a task, but not how it was requested or how its results are stored.*

*   `src/server/crud.py`:
    > **SOLE RESPONSIBILITY:** Contains all database Create, Read, Update, Delete (CRUD) logic.
    >
    > *It knows how to talk to the database, but not why it's being asked to.*

*   `src/server/models.py`:
    > **SOLE RESPONSIBILITY:** Defines all Pydantic and SQLModel data contracts for the entire system, serving as the single source of truth for data shapes.
    >
    > *It knows what data looks like, but not what to do with it.*

*   `src/cli/main.py`:
    > **SOLE RESPONSIBILITY:** Defines all Typer CLI commands (e.g., run, status, logs), handles user input, and makes HTTP requests to the server's REST API.
    >
    > *It knows how to be a command-line client, but has no knowledge of the server's internal workings.*

## Why This Matters: The Benefits

Adhering strictly to this philosophy provides significant, practical benefits for the project's long-term health and for its developers.

1.  **Improved Onboarding:** A new developer doesn't need to understand the entire system to fix a bug or add a feature. If the issue is with the database, they can go straight to `crud.py`. If a CLI command is broken, `cli/main.py` is the place to look. This drastically reduces the cognitive load required to contribute.

2.  **Enhanced Maintainability:** With clear boundaries, changes in one module are less likely to have unintended side effects in another. Refactoring the API layer in `server/main.py` won't break the task execution logic in `server/executor.py`, as long as the contract between them (submitting a task ID to the process pool) remains the same.

3.  **Increased Testability:** Each component can be tested in isolation. We can test the database logic in `crud.py` with a mock session, or test the `TaskExecutor` without needing a running web server. This leads to more reliable and focused tests.

4.  **Logical Code Organization:** The file structure naturally follows the application's logic. It's immediately clear where to find code related to the API, database, task execution, or data models, simply by looking at the filenames.

By making this design choice explicit, we are making a strong case for *why* the project is built this way, creating a codebase that is easier to understand, maintain, and contribute to.