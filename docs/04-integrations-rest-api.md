# REST API Reference

The Claude Worker server exposes a formal REST API for programmatic interaction. This allows you to integrate Claude Worker into your own applications, scripts, and workflows. The API is built with FastAPI and uses Pydantic for data validation and serialization.

## API Base URL

The default base URL for the API is `http://localhost:8000`.

## Data Models

These Pydantic models define the shapes of the data sent to and received from the API.

### `TaskCreate` (Request)

Used for the human-friendly task creation endpoint.

```json
{
  "execution_prompt": "string",
  "working_directory": "string",
  "system_prompt": "string (optional)"
}
```

### `MCPCreateTaskPayload` (Request)

Used for the strict, machine-friendly MCP endpoint.

```json
{
  "system_prompt": "string (75-500 chars, must contain 'John Carmack')",
  "execution_prompt": "string (150+ chars, must contain a path-like string)",
  "working_directory": "string"
}
```

### `TaskRead` (Response)

The standard response object for any request that returns task data.

```json
{
  "id": "integer",
  "status": "string",
  "created_at": "string (ISO 8601 datetime)",
  "started_at": "string (ISO 8601 datetime, optional)",
  "ended_at": "string (ISO 8601 datetime, optional)",
  "last_action_cache": "string (optional)",
  "final_summary": "string (optional)",
  "error_message": "string (optional)"
}
```

---

## Endpoints

### 1. Create a Task

*   **Endpoint:** `POST /api/v1/tasks`
*   **Description:** Submits a new task for execution. This is the primary endpoint for human-driven integrations. It has lenient validation and applies defaults where needed.
*   **Request Body:** `TaskCreate`
*   **Response:** `200 OK` with a `TaskRead` object representing the newly created task.

**Example `curl`:**
```bash
curl -X POST "http://localhost:8000/api/v1/tasks" \
-H "Content-Type: application/json" \
-d '{
  "execution_prompt": "Analyze this code.",
  "working_directory": "/app/src"
}'
```

### 2. Get Task Status

*   **Endpoint:** `GET /api/v1/tasks/{task_id}`
*   **Description:** Retrieves the detailed status and information for a single task.
*   **Response:** `200 OK` with a `TaskRead` object. `404 Not Found` if the task ID does not exist.

**Example `curl`:**
```bash
curl "http://localhost:8000/api/v1/tasks/42"
```

### 3. List All Tasks

*   **Endpoint:** `GET /api/v1/tasks`
*   **Description:** Retrieves a list of all tasks in the system.
*   **Response:** `200 OK` with a JSON array of `TaskRead` objects.

**Example `curl`:**
```bash
curl "http://localhost:8000/api/v1/tasks"
```

### 4. Create an MCP Task

*   **Endpoint:** `POST /api/v1/mcp/tasks`
*   **Description:** Submits a new task with strict validation rules, intended for consumption by AI agents or other automated systems.
*   **Request Body:** `MCPCreateTaskPayload`
*   **Response:** `200 OK` with a `TaskRead` object. `422 Unprocessable Entity` if validation fails.

**Example `curl`:**
```bash
curl -X POST "http://localhost:8000/api/v1/mcp/tasks" \
-H "Content-Type: application/json" \
-d '{
  "system_prompt": "You are an expert developer who follows the design principles of John Carmack. Be direct and concise, focusing on robust and simple solutions.",
  "execution_prompt": "Please review the entire codebase located at /home/user/project/src and identify potential performance bottlenecks. Write your findings to analysis.md.",
  "working_directory": "/home/user/project"
}'
```

### 5. Health Check

*   **Endpoint:** `GET /health`
*   **Description:** A simple endpoint to verify that the server is running and responsive.
*   **Response:** `200 OK` with a JSON object: `{"status": "healthy", "service": "claude-worker"}`.

**Example `curl`:**
```bash
curl "http://localhost:8000/health"
```