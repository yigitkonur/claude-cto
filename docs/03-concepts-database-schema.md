# Database Schema and State Management

Claude Worker uses a local SQLite database as its single source of truth for all task-related information. This ensures that no work is lost, even if the server is restarted. The database schema is defined using `SQLModel` in `server/models.py`, which combines the features of Pydantic and SQLAlchemy.

## The `tasks` Table

The core of the system is the `tasks` table, which is mapped to the `TaskDB` class. This table tracks the entire lifecycle of a task, from its initial submission to its final result.

### Schema Definition

Below is a detailed breakdown of each field in the `tasks` table and its purpose.

| Field Name          | Data Type            | Description                                                                                                                              |
| ------------------- | -------------------- | ---------------------------------------------------------------------------------------------------------------------------------------- |
| `id`                | `INTEGER` (Primary Key) | A unique, auto-incrementing identifier for the task.                                                                                     |
| `status`            | `VARCHAR`            | The current state of the task. Can be `pending`, `running`, `completed`, or `failed`. Indexed for efficient querying.                      |
| `pid`               | `INTEGER`            | The Process ID (PID) of the worker process executing this task. Useful for debugging and monitoring.                                       |
| `working_directory` | `VARCHAR`            | The absolute path to the directory where the task should be executed.                                                                    |
| `system_prompt`     | `TEXT`               | The system prompt provided to the AI to guide its behavior.                                                                              |
| `execution_prompt`  | `TEXT`               | The main user-provided prompt that defines the task.                                                                                     |
| `raw_log_path`      | `VARCHAR`            | The absolute path to the raw, verbose log file containing all SDK output.                                                                |
| `summary_log_path`  | `VARCHAR`            | The absolute path to the cleaned, human-readable summary log file.                                                                       |
| `last_action_cache` | `VARCHAR`            | **Data Lifecycle:** A cached copy of the last line written to the summary log. This allows the CLI's `status` and `list` commands to quickly display the most recent action without reading the log file, significantly improving performance. |
| `final_summary`     | `TEXT`               | **Data Lifecycle:** Stores the final success message or summary when a task's status becomes `completed`. This is the "result" of a successful task. |
| `error_message`     | `TEXT`               | **Data Lifecycle:** Stores the final error details if a task's status becomes `failed`.                                                    |
| `created_at`        | `DATETIME`           | The timestamp when the task was first created in the database.                                                                           |
| `started_at`        | `DATETIME`           | The timestamp when a worker process picked up the task and its status changed to `running`.                                              |
| `ended_at`          | `DATETIME`           | The timestamp when the task reached a terminal state (`completed` or `failed`).                                                          |

## The Data Lifecycle

The database acts as the definitive record of a task's journey:

1.  **Creation (`crud.create_task`):** A new row is inserted with `status='pending'`. The `id` is generated, which allows the `raw_log_path` and `summary_log_path` to be created with a unique name.
2.  **Execution (`TaskExecutor`):** A worker process picks up the task. It updates the `status` to `running`, sets the `pid` and `started_at` timestamp.
3.  **In-Progress (`crud.append_to_summary_log`):** As the task runs, each new tool use is appended to the summary log file, and the `last_action_cache` field is updated in the database with that same line.
4.  **Finalization (`crud.finalize_task`):** When the task finishes, its `status` is updated to `completed` or `failed`, the `ended_at` timestamp is set, and either `final_summary` or `error_message` is populated with the final result.

This approach ensures that the database always reflects the complete history and outcome of every task, providing a reliable and auditable record.