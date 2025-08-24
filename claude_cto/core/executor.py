"""
Shared task executor functionality for claude-cto.
Handles actual Claude Code SDK execution.
"""

import asyncio
import logging
from pathlib import Path
from datetime import datetime
from typing import Optional, Dict, Any

from claude_code_sdk import query, ClaudeCodeOptions
from sqlmodel import Session

from claude_cto.server.models import TaskStatus
from .database import get_task_by_id, update_task_status


logger = logging.getLogger(__name__)


class TaskExecutor:
    """Encapsulates direct task execution with Claude SDK."""

    def __init__(self, task_id: int, session: Session, log_dir: Optional[Path] = None):
        """Initializes with dependencies for task execution."""
        self.task_id = task_id
        self.session = session
        self.log_dir = log_dir or Path.home() / ".claude-cto" / "logs"
        self.log_dir.mkdir(parents=True, exist_ok=True)

    async def run(self) -> Dict[str, Any]:
        """Execute the task and return results."""
        task = get_task_by_id(self.session, self.task_id)
        if not task:
            return {"error": f"Task {self.task_id} not found"}

        # Setup logging
        log_file = self.log_dir / f"task_{self.task_id}.log"
        file_handler = logging.FileHandler(log_file)
        file_handler.setFormatter(logging.Formatter("%(asctime)s - %(levelname)s - %(message)s"))
        task_logger = logging.getLogger(f"task_{self.task_id}")
        task_logger.addHandler(file_handler)
        task_logger.setLevel(logging.INFO)

        try:
            # Update status to running and set PID
            update_task_status(
                self.session,
                self.task_id,
                TaskStatus.RUNNING,
                started_at=datetime.utcnow(),
                log_file_path=str(log_file),
            )

            task_logger.info(f"Starting task {self.task_id}")
            task_logger.info(f"Working directory: {task.working_directory}")
            task_logger.info(f"System prompt: {task.system_prompt}")
            task_logger.info(f"Execution prompt: {task.execution_prompt}")
            task_logger.info(f"Model: {task.model}")

            # Configure Claude Code SDK options
            options = ClaudeCodeOptions(
                cwd=task.working_directory,
                system_prompt=task.system_prompt,
                model=task.model,
            )

            # Execute with Claude Code SDK
            last_message = None
            message_count = 0

            async for message in query(prompt=task.execution_prompt, options=options):
                message_count += 1
                last_message = message

                # Process message from SDK stream
                task_logger.info(f"Message {message_count}: {message}")

                # Update last action cache periodically
                if message_count % 5 == 0:
                    update_task_status(
                        self.session,
                        self.task_id,
                        TaskStatus.RUNNING,
                        last_action_cache=str(message)[:500],
                    )

            # Task completed successfully - finalize status
            final_summary = f"Task completed. Processed {message_count} messages."
            if last_message:
                final_summary += f" Last: {str(last_message)[:200]}"

            task_logger.info(f"Task completed successfully: {final_summary}")

            update_task_status(
                self.session,
                self.task_id,
                TaskStatus.COMPLETED,
                ended_at=datetime.utcnow(),
                final_summary=final_summary,
                last_action_cache=str(last_message)[:500] if last_message else None,
            )

            return {
                "status": "completed",
                "message_count": message_count,
                "final_summary": final_summary,
            }

        except Exception as e:
            # Capture failures and format error message
            error_type = type(e).__name__
            error_msg = f"Task failed [{error_type}]: {str(e)}"

            # Extract error details based on error type
            if hasattr(e, "exit_code"):
                error_msg += f" | exit_code: {e.exit_code}"
            if hasattr(e, "stderr") and e.stderr:
                error_msg += f" | stderr: {e.stderr[:200]}"
            if hasattr(e, "line"):  # CLIJSONDecodeError
                error_msg += f" | problematic_line: {e.line[:100]}"
            if hasattr(e, "data"):  # MessageParseError
                error_msg += f" | parse_data: {str(e.data)[:100]}"

            task_logger.error(f"Task failed: {error_msg}", exc_info=True)

            update_task_status(
                self.session,
                self.task_id,
                TaskStatus.FAILED,
                ended_at=datetime.utcnow(),
                error_message=error_msg,
            )

            return {"status": "failed", "error": error_msg}
        finally:
            # Clean up logger
            task_logger.removeHandler(file_handler)
            file_handler.close()


async def execute_task_async(task_id: int, session: Session, log_dir: Optional[Path] = None) -> Dict[str, Any]:
    """Async wrapper for TaskExecutor."""
    executor = TaskExecutor(task_id, session, log_dir)
    return await executor.run()


def execute_task_sync(task_id: int, session: Session, log_dir: Optional[Path] = None) -> Dict[str, Any]:
    """Sync wrapper for process pool usage."""
    return asyncio.run(execute_task_async(task_id, session, log_dir))
