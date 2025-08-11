# MCP Integration for AI Agents

Claude Worker provides a dedicated interface for AI agents and other automated systems through the **Model Context Protocol (MCP)**. This can be accessed either by running the MCP server directly or by calling a special REST API endpoint designed for machine clients.

This endpoint is intentionally less permissive than the human-facing API to act as a guardrail, ensuring that automated agents provide high-quality, actionable prompts.

## The Strict MCP Endpoint

The primary integration point is the `/api/v1/mcp/tasks` REST endpoint. It accepts a `MCPCreateTaskPayload` which enforces strict validation rules, defined in `server/models.py`.

### Validation Rules and Their Purpose

When an AI agent submits a task to this endpoint, the payload is validated against the following rules:

1.  **System Prompt (`system_prompt`)**
    *   **Rule:** Must be between 75 and 500 characters.
    *   **Rule:** Must contain the phrase `"John Carmack"` (case-sensitive).
    *   **Purpose:** This acts as a quality guardrail. It forces the agent to use a non-trivial, context-rich system prompt. The "John Carmack" requirement is a specific check to ensure the agent is using a persona known for promoting simplicity and robustness, which is the desired behavior for tasks run by this system.

2.  **Execution Prompt (`execution_prompt`)**
    *   **Rule:** Must be at least 150 characters long.
    *   **Rule:** Must contain a path-like string (containing either `/` or `\`).
    *   **Purpose:** This prevents agents from submitting trivial or vague prompts. The minimum length encourages detailed instructions, and the path requirement ensures the prompt is grounded in a specific file system context, making it more actionable for the underlying Claude Code SDK.

3.  **Working Directory (`working_directory`)**
    *   **Rule:** Must be a valid string.
    *   **Purpose:** Explicitly sets the execution context for the task.

### Why Are the Rules So Strict?

The human-facing API (`/api/v1/tasks`) is lenient, accepting simple prompts. The MCP endpoint is strict by design. This separation serves a critical purpose: it protects the system from low-quality, automated requests that could waste resources. By enforcing these constraints, we ensure that any AI agent integrated with Claude Worker has been thoughtfully configured to provide prompts that are specific, detailed, and aligned with the project's philosophy.

### Example MCP Request

Here is an example of a valid payload that an AI agent could send to the MCP endpoint.

**Request:** `POST /api/v1/mcp/tasks`

**Body (`MCPCreateTaskPayload`):**
```json
{
  "system_prompt": "As an AI assistant following John Carmack's principles, your goal is to write clean, simple, and maintainable code. Prioritize clarity over cleverness.",
  "execution_prompt": "Please analyze the Python project located in /app/src. Your task is to identify all modules that lack sufficient test coverage. Generate a report named 'test_coverage_report.txt' in the root of the working directory, listing each file and its recommended testing strategy.",
  "working_directory": "/app"
}
```

If any of the validation rules are not met, the API will return a `422 Unprocessable Entity` error with a detailed message explaining the failure, which the calling agent can use to correct its request.