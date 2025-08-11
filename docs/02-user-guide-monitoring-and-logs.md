# Monitoring Tasks and Inspecting Logs

Once you've submitted a task, Claude Worker provides several tools to monitor its progress, view its history, and debug any issues by inspecting its logs.

## Listing All Tasks

To get a high-level overview of all tasks in the system, use the `list` command:

```bash
claude-worker list
```

This will display a table with key information about each task:

```
┏━━━━┳━━━━━━━━━━━┳━━━━━━━━━━━━━━━━━━━━━━┳━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━┓
┃ ID ┃ Status    ┃ Created              ┃ Last Action                  ┃
┡━━━━╇━━━━━━━━━━━╇━━━━━━━━━━━━━━━━━━━━━━╇━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━┩
│ 1  │ completed │ 2023-10-27 10:30:15  │ [tool:write] app.py          │
│ 2  │ running   │ 2023-10-27 10:35:01  │ [tool:read] requirements.txt │
│ 3  │ failed    │ 2023-10-27 10:40:22  │ -                            │
│ 4  │ queued    │ 2023-10-27 10:45:10  │ -                            │
└────┴───────────┴──────────────────────┴──────────────────────────────┘
```

The `Last Action` column is a cache of the most recent operation performed by the AI, giving you a quick glimpse into what a running task is doing.

## Checking a Specific Task

To get detailed information about a single task, use the `status` command with the task ID:

```bash
claude-worker status 2
```

This provides a comprehensive summary, including timestamps, final results, or error messages.

## Real-time Monitoring with `--watch`

For long-running tasks, you can use the `--watch` flag when submitting a task to get a live-updating view of its status.

```bash
claude-worker run "Build a complex web application" --watch
```

The terminal will display a status table that refreshes automatically until the task is complete, showing the latest action performed by the AI. This is the most convenient way to monitor an active task.

## Inspecting Logs for Debugging

Every task generates two distinct log files, which are essential for debugging. The log paths are generated in `server/crud.py` and are stored in your home directory at `~/.claude-worker/logs/`.

You can find the exact paths for a task by looking at the database or, more easily, by inferring them from the task ID. For a task with ID `42`, the logs would be:

*   `~/.claude-worker/logs/task_42_raw.log`
*   `~/.claude-worker/logs/task_42_summary.log`

### `raw_log_path` vs. `summary_log_path`

It is critical to understand the difference between the two log files:

1.  **`task_[id]_raw.log` (Raw Log):**
    *   **Content:** Contains the complete, verbose, and unfiltered JSON output directly from the Claude Code SDK stream.
    *   **Purpose:** Deep debugging. If a task fails unexpectedly or you suspect an issue with the underlying SDK, this file is your primary source of truth. It shows every single message exchanged with the AI.
    *   **When to check:** When a task fails with a cryptic error, or when it's behaving in a way you don't understand.

2.  **`task_[id]_summary.log` (Summary Log):**
    *   **Content:** A clean, human-readable summary of the key actions (tool uses) performed by the AI during the task.
    *   **Purpose:** High-level progress tracking and understanding the task's history. This log answers the question, "What did the AI actually *do*?"
    *   **When to check:** When you want to review the steps a completed task took or see the sequence of operations for a running task. The `last_action_cache` field displayed by the `status` command is sourced from this log.

**Example Debugging Workflow:**

1.  A task with ID `3` fails. `claude-worker status 3` shows an error.
2.  First, check the summary log to see the last successful action: `tail ~/.claude-worker/logs/task_3_summary.log`.
3.  This might give you a clue. If not, dive into the raw log to see the exact SDK message that preceded the failure: `tail -n 50 ~/.claude-worker/logs/task_3_raw.log`.