"""
SOLE RESPONSIBILITY: Advanced logging system for claude-cto tasks.
Creates structured, multi-level logging with summary and detailed logs.
"""

import json
import logging
from pathlib import Path
from datetime import datetime
from typing import Optional, Dict, Any
from contextlib import contextmanager
from .path_utils import generate_log_filename, get_safe_log_directory


class TaskLogger:
    """Advanced logger for individual tasks with multiple log levels."""

    def __init__(
        self, task_id: int, working_directory: str, timestamp: Optional[datetime] = None
    ):
        self.task_id = task_id
        self.working_directory = working_directory
        self.timestamp = timestamp or datetime.now()
        self.log_dir = self._setup_log_directory()

        # Create enhanced log file paths with directory context
        summary_filename = generate_log_filename(
            task_id, working_directory, "summary", self.timestamp
        )
        detailed_filename = generate_log_filename(
            task_id, working_directory, "detailed", self.timestamp
        )

        self.summary_log_path = self.log_dir / summary_filename
        self.detailed_log_path = self.log_dir / detailed_filename

        # Setup loggers with unique names to avoid conflicts
        logger_suffix = f"{task_id}_{self.timestamp.strftime('%H%M%S')}"
        self.summary_logger = self._create_logger(
            f"summary_{logger_suffix}", self.summary_log_path
        )
        self.detailed_logger = self._create_logger(
            f"detailed_{logger_suffix}", self.detailed_log_path
        )

        # Global summary logger
        self.global_logger = self._get_global_logger()

    def _setup_log_directory(self) -> Path:
        """Create and return the .claude-cto directory structure."""
        return get_safe_log_directory()

    def _create_logger(self, name: str, log_file: Path) -> logging.Logger:
        """Create a logger with rich formatting."""
        # Check if logger already exists and clean it up
        if name in logging.Logger.manager.loggerDict:
            existing_logger = logging.getLogger(name)
            # Remove all existing handlers
            for handler in existing_logger.handlers[:]:
                handler.close()
                existing_logger.removeHandler(handler)
        
        logger = logging.getLogger(name)
        logger.setLevel(logging.INFO)

        # Remove any remaining handlers to avoid duplicates
        for handler in logger.handlers[:]:
            handler.close()
            logger.removeHandler(handler)

        # File handler with rich formatting
        handler = logging.FileHandler(log_file, mode="w")
        formatter = logging.Formatter(
            "%(asctime)s │ %(levelname)-8s │ %(message)s", datefmt="%Y-%m-%d %H:%M:%S"
        )
        handler.setFormatter(formatter)
        logger.addHandler(handler)
        logger.propagate = False

        return logger

    def _get_global_logger(self) -> logging.Logger:
        """Get or create the global claude-cto summary logger."""
        global_log_file = Path.home() / ".claude-cto" / "claude-cto.log"

        logger = logging.getLogger("claude_cto_global")
        
        # Always check for and remove stale handlers
        needs_handler = True
        for handler in logger.handlers[:]:
            if isinstance(handler, logging.FileHandler):
                # Check if handler is still valid and pointing to the right file
                if hasattr(handler, 'baseFilename') and handler.baseFilename == str(global_log_file):
                    needs_handler = False
                else:
                    # Remove stale handler
                    handler.close()
                    logger.removeHandler(handler)
        
        if needs_handler:
            logger.setLevel(logging.INFO)

            handler = logging.FileHandler(global_log_file, mode="a")
            formatter = logging.Formatter(
                "%(asctime)s │ TASK-%(extra_task_id)-3s │ %(levelname)-8s │ %(message)s",
                datefmt="%Y-%m-%d %H:%M:%S",
            )
            handler.setFormatter(formatter)
            logger.addHandler(handler)
            logger.propagate = False

        return logger

    def log_task_start(
        self, execution_prompt: str, model: str, system_prompt: str = None
    ):
        """Log task initialization with full context."""
        start_time = datetime.now()

        # Summary log
        self.summary_logger.info(f"🚀 Task {self.task_id} STARTED")
        self.summary_logger.info(f"📁 Working Directory: {self.working_directory}")
        self.summary_logger.info(f"🤖 Model: {model}")
        self.summary_logger.info(
            f"📝 Prompt: {execution_prompt[:100]}{'...' if len(execution_prompt) > 100 else ''}"
        )

        # Detailed log
        self.detailed_logger.info("=" * 80)
        self.detailed_logger.info(f"TASK {self.task_id} EXECUTION LOG")
        self.detailed_logger.info("=" * 80)
        self.detailed_logger.info(f"Start Time: {start_time.isoformat()}")
        self.detailed_logger.info(f"Working Directory: {self.working_directory}")
        self.detailed_logger.info(f"Model: {model}")
        self.detailed_logger.info(f"System Prompt: {system_prompt or 'Default'}")
        self.detailed_logger.info(f"Execution Prompt:\n{execution_prompt}")
        self.detailed_logger.info("-" * 80)

        # Global log
        self._log_global(
            "STARTED", f"Model: {model} | Dir: {Path(self.working_directory).name}"
        )

    def log_task_progress(self, message: str, action_type: str = "ACTION"):
        """Log task progress with structured format."""
        timestamp = datetime.now().strftime("%H:%M:%S")

        # Summary log (concise)
        self.summary_logger.info(
            f"⚡ [{timestamp}] {action_type}: {message[:80]}{'...' if len(message) > 80 else ''}"
        )

        # Detailed log (full content)
        self.detailed_logger.info(f"[{action_type}] {message}")

    def log_tool_usage(
        self, tool_name: str, tool_input: Dict[str, Any], success: bool = True
    ):
        """Log tool usage with structured data."""
        status = "✅" if success else "❌"

        # Format tool input for display
        if tool_name == "Bash":
            display = tool_input.get("command", "N/A")
        elif tool_name in ["Edit", "Write", "Read"]:
            display = tool_input.get("file_path", "N/A")
        elif tool_name in ["Grep", "Glob"]:
            display = tool_input.get("pattern", "N/A")
        else:
            display = str(tool_input)[:50]

        self.summary_logger.info(f"{status} {tool_name}: {display}")
        self.detailed_logger.info(
            f"TOOL: {tool_name} | INPUT: {json.dumps(tool_input, indent=2)}"
        )

    def log_task_completion(
        self, success: bool, final_message: str, duration: Optional[float] = None
    ):
        """Log task completion with summary statistics."""
        end_time = datetime.now()
        status = "✅ COMPLETED" if success else "❌ FAILED"

        # Summary log
        self.summary_logger.info(f"🏁 Task {self.task_id} {status}")
        if duration:
            self.summary_logger.info(f"⏱️  Duration: {duration:.1f}s")
        self.summary_logger.info(f"📋 Result: {final_message}")

        # Detailed log
        self.detailed_logger.info("-" * 80)
        self.detailed_logger.info(f"TASK COMPLETION: {status}")
        self.detailed_logger.info(f"End Time: {end_time.isoformat()}")
        if duration:
            self.detailed_logger.info(f"Duration: {duration:.1f} seconds")
        self.detailed_logger.info(f"Final Message: {final_message}")
        self.detailed_logger.info("=" * 80)

        # Global log
        duration_str = f" ({duration:.1f}s)" if duration else ""
        self._log_global(
            "COMPLETED" if success else "FAILED",
            f"{final_message[:60]}{'...' if len(final_message) > 60 else ''}{duration_str}",
        )

    def log_error(self, error: Exception, context: str = ""):
        """Log errors with full context and stack traces."""
        error_type = type(error).__name__
        error_msg = str(error)

        # Summary log
        self.summary_logger.error(f"💥 ERROR: {error_type}: {error_msg}")
        if context:
            self.summary_logger.error(f"🔍 Context: {context}")

        # Detailed log (with stack trace)
        self.detailed_logger.error(f"ERROR: {error_type}")
        self.detailed_logger.error(f"Message: {error_msg}")
        if context:
            self.detailed_logger.error(f"Context: {context}")

        # Add specific error details if available
        if hasattr(error, "exit_code"):
            self.detailed_logger.error(f"Exit Code: {error.exit_code}")
        if hasattr(error, "stderr"):
            self.detailed_logger.error(f"STDERR: {error.stderr}")

        # Stack trace
        import traceback

        self.detailed_logger.error("Stack Trace:")
        self.detailed_logger.error(traceback.format_exc())

        # Global log
        self._log_global(
            "ERROR",
            f"{error_type}: {error_msg[:50]}{'...' if len(error_msg) > 50 else ''}",
        )

    def _log_global(self, level: str, message: str):
        """Log to global summary with task ID context."""
        # Create a custom log record with task ID
        record = logging.LogRecord(
            name="claude_cto_global",
            level=logging.INFO,
            pathname="",
            lineno=0,
            msg=message,
            args=(),
            exc_info=None,
        )
        record.extra_task_id = str(self.task_id)
        self.global_logger.handle(record)

    def get_log_files(self) -> Dict[str, str]:
        """Return paths to all log files for this task."""
        return {
            "summary": str(self.summary_log_path),
            "detailed": str(self.detailed_log_path),
            "global": str(Path.home() / ".claude-cto" / "claude-cto.log"),
        }

    @contextmanager
    def task_context(
        self, execution_prompt: str, model: str, system_prompt: str = None
    ):
        """Context manager for complete task logging lifecycle."""
        start_time = datetime.now()

        try:
            self.log_task_start(execution_prompt, model, system_prompt)
            yield self

            # If we get here, task succeeded
            duration = (datetime.now() - start_time).total_seconds()
            self.log_task_completion(True, "Task completed successfully", duration)

        except Exception as e:
            # Task failed
            duration = (datetime.now() - start_time).total_seconds()
            self.log_error(e, "During task execution")
            self.log_task_completion(False, f"Task failed: {str(e)}", duration)
            raise
        finally:
            # Clean up loggers
            self._cleanup_loggers()

    def close(self):
        """
        CRITICAL: Close and clean up the task logger to prevent memory leaks.
        Must be called when the task completes to free resources.
        """
        self._cleanup_loggers()
    
    def _cleanup_loggers(self):
        """Clean up logger handlers and remove loggers to prevent resource leaks."""
        for logger in [self.summary_logger, self.detailed_logger]:
            # Close and remove all handlers
            for handler in logger.handlers[:]:
                handler.flush()
                handler.close()
                logger.removeHandler(handler)
            
            # Clear the logger reference
            logger.handlers.clear()
            
        # Remove loggers from the registry to prevent accumulation
        logger_names = [self.summary_logger.name, self.detailed_logger.name]
        for name in logger_names:
            if name in logging.Logger.manager.loggerDict:
                del logging.Logger.manager.loggerDict[name]


def create_task_logger(
    task_id: int, working_directory: str, timestamp: Optional[datetime] = None
) -> TaskLogger:
    """Factory function to create a task logger."""
    return TaskLogger(task_id, working_directory, timestamp)


def get_log_directory() -> Path:
    """Get the main logging directory."""
    return Path.home() / ".claude-cto"


def get_task_logs(task_id: int) -> Optional[Dict[str, str]]:
    """Get log file paths for a specific task (finds newest logs)."""

    log_dir = get_safe_log_directory()

    # Find all log files for this task ID
    task_logs = {"summary": None, "detailed": None}

    for log_file in log_dir.glob(f"task_{task_id}_*_summary.log"):
        if not task_logs["summary"]:  # Take the first one found
            task_logs["summary"] = str(log_file)

            # Look for corresponding detailed log
            detailed_pattern = log_file.name.replace("_summary.log", "_detailed.log")
            detailed_path = log_dir / detailed_pattern
            if detailed_path.exists():
                task_logs["detailed"] = str(detailed_path)
            break

    if task_logs["summary"]:
        task_logs["global"] = str(get_log_directory() / "claude-cto.log")
        return task_logs

    return None


def list_all_task_logs() -> Dict[int, Dict[str, str]]:
    """List all available task logs with enhanced naming."""
    from .path_utils import parse_log_filename

    log_dir = get_safe_log_directory()
    if not log_dir.exists():
        return {}

    task_logs = {}

    # Group logs by task ID
    for log_file in log_dir.glob("task_*_*_summary.log"):
        parsed = parse_log_filename(log_file.name)
        if parsed:
            task_id, dir_context, timestamp, log_type = parsed

            if task_id not in task_logs:
                task_logs[task_id] = {}

            # Store the most recent log for each task
            current_entry = task_logs[task_id]
            if not current_entry or timestamp > current_entry.get("timestamp", ""):
                detailed_name = log_file.name.replace("_summary.log", "_detailed.log")
                detailed_path = log_dir / detailed_name

                task_logs[task_id] = {
                    "summary": str(log_file),
                    "detailed": str(detailed_path) if detailed_path.exists() else None,
                    "dir_context": dir_context,
                    "timestamp": timestamp,
                    "exists": log_file.exists(),
                }

    return task_logs
