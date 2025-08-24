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
    """
    Multi-level task logging system: creates structured, comprehensive logs for task execution.
    Critical for debugging, monitoring, and audit trails - must be properly closed to prevent resource leaks.
    Generates summary (concise) and detailed (verbose) logs plus global aggregation for system monitoring.
    """

    def __init__(self, task_id: int, working_directory: str, timestamp: Optional[datetime] = None):
        # Task identification: establishes logging context and resource tracking
        self.task_id = task_id
        self.working_directory = working_directory
        self.timestamp = timestamp or datetime.now()  # Execution timestamp for log organization
        self.log_dir = self._setup_log_directory()  # Base directory for all task logs

        # Log file path generation: creates unique, collision-free filenames with context
        # Pattern: task_{id}_{dir_hash}_{timestamp}_{level}.log
        summary_filename = generate_log_filename(task_id, working_directory, "summary", self.timestamp)
        detailed_filename = generate_log_filename(task_id, working_directory, "detailed", self.timestamp)

        self.summary_log_path = self.log_dir / summary_filename  # Concise progress log
        self.detailed_log_path = self.log_dir / detailed_filename  # Verbose debugging log

        # Logger instance creation: unique names prevent cross-task interference
        # Time suffix ensures logger uniqueness across rapid task creation
        logger_suffix = f"{task_id}_{self.timestamp.strftime('%H%M%S')}"
        self.summary_logger = self._create_logger(f"summary_{logger_suffix}", self.summary_log_path)
        self.detailed_logger = self._create_logger(f"detailed_{logger_suffix}", self.detailed_log_path)

        # System-wide aggregation logger: consolidates all task events for monitoring
        self.global_logger = self._get_global_logger()

    def _setup_log_directory(self) -> Path:
        """
        Log directory initialization: ensures .claude-cto directory exists with proper permissions.
        Critical for task isolation and log organization across system operations.
        """
        return get_safe_log_directory()  # Cross-platform directory creation with safety checks

    def _create_logger(self, name: str, log_file: Path) -> logging.Logger:
        """
        Logger factory: creates isolated file loggers with cleanup to prevent resource leaks.
        Critical - removes existing handlers to prevent duplicate logging and file handle accumulation.
        """
        # Existing logger cleanup: prevents handler accumulation from previous task executions
        if name in logging.Logger.manager.loggerDict:
            existing_logger = logging.getLogger(name)
            # Handler cleanup: closes file handles and removes references
            for handler in existing_logger.handlers[:]:
                handler.close()  # Critical: releases file system resources
                existing_logger.removeHandler(handler)

        # Fresh logger creation: establishes clean logging instance
        logger = logging.getLogger(name)
        logger.setLevel(logging.INFO)  # Standard logging level for task operations

        # Handler deduplication: ensures no duplicate file writing
        for handler in logger.handlers[:]:
            handler.close()  # Resource cleanup before removal
            logger.removeHandler(handler)

        # File handler setup: creates new log file with structured formatting
        handler = logging.FileHandler(log_file, mode="w")  # Overwrite mode for fresh logs
        # Rich formatting: timestamp │ level │ message for easy parsing
        formatter = logging.Formatter("%(asctime)s │ %(levelname)-8s │ %(message)s", datefmt="%Y-%m-%d %H:%M:%S")
        handler.setFormatter(formatter)
        logger.addHandler(handler)
        logger.propagate = False  # Prevents duplicate logging to parent loggers

        return logger

    def _get_global_logger(self) -> logging.Logger:
        """
        Global logger acquisition: creates or reuses system-wide aggregation logger.
        Consolidates all task events into single log file for monitoring and alerting systems.
        Critical for system observability and troubleshooting across multiple tasks.
        """
        # Global log file: central aggregation point for all task activity
        global_log_file = Path.home() / ".claude-cto" / "claude-cto.log"

        # Singleton logger pattern: reuses existing global logger instance
        logger = logging.getLogger("claude_cto_global")

        # Handler validation: ensures global logger points to correct file
        # Prevents stale handlers from pointing to moved or deleted files
        needs_handler = True
        for handler in logger.handlers[:]:
            if isinstance(handler, logging.FileHandler):
                # File path validation: confirms handler targets correct global log
                if hasattr(handler, "baseFilename") and handler.baseFilename == str(global_log_file):
                    needs_handler = False  # Valid handler found - reuse it
                else:
                    # Stale handler cleanup: removes handlers pointing to wrong files
                    handler.close()  # Release file system resources
                    logger.removeHandler(handler)

        # Handler creation: establishes new global log handler if needed
        if needs_handler:
            logger.setLevel(logging.INFO)

            # Append mode: preserves historical log data across server restarts
            handler = logging.FileHandler(global_log_file, mode="a")
            # Task-aware formatting: includes task ID for multi-task correlation
            formatter = logging.Formatter(
                "%(asctime)s │ TASK-%(extra_task_id)-3s │ %(levelname)-8s │ %(message)s",
                datefmt="%Y-%m-%d %H:%M:%S",
            )
            handler.setFormatter(formatter)
            logger.addHandler(handler)
            logger.propagate = False  # Prevents duplicate system logging

        return logger

    def log_task_start(self, execution_prompt: str, model: str, system_prompt: str = None):
        """
        Task initialization logging: captures complete execution context for debugging and audit.
        Critical for understanding task configuration and troubleshooting failed executions.
        """
        start_time = datetime.now()

        # Summary log: concise task startup information for quick scanning
        self.summary_logger.info(f"🚀 Task {self.task_id} STARTED")
        self.summary_logger.info(f"📁 Working Directory: {self.working_directory}")
        self.summary_logger.info(f"🤖 Model: {model}")
        # Prompt preview: truncated for summary readability
        self.summary_logger.info(f"📝 Prompt: {execution_prompt[:100]}{'...' if len(execution_prompt) > 100 else ''}")

        # Detailed log: comprehensive task configuration for deep debugging
        self.detailed_logger.info("=" * 80)
        self.detailed_logger.info(f"TASK {self.task_id} EXECUTION LOG")
        self.detailed_logger.info("=" * 80)
        self.detailed_logger.info(f"Start Time: {start_time.isoformat()}")
        self.detailed_logger.info(f"Working Directory: {self.working_directory}")
        self.detailed_logger.info(f"Model: {model}")
        self.detailed_logger.info(f"System Prompt: {system_prompt or 'Default'}")
        # Full prompt: complete text for exact reproduction
        self.detailed_logger.info(f"Execution Prompt:\n{execution_prompt}")
        self.detailed_logger.info("-" * 80)

        # Global aggregation: system-wide task tracking for monitoring dashboards
        self._log_global("STARTED", f"Model: {model} | Dir: {Path(self.working_directory).name}")

    def log_task_progress(self, message: str, action_type: str = "ACTION"):
        """Log task progress with structured format."""
        timestamp = datetime.now().strftime("%H:%M:%S")

        # Summary log (concise)
        self.summary_logger.info(f"⚡ [{timestamp}] {action_type}: {message[:80]}{'...' if len(message) > 80 else ''}")

        # Detailed log (full content)
        self.detailed_logger.info(f"[{action_type}] {message}")

    def log_tool_usage(self, tool_name: str, tool_input: Dict[str, Any], success: bool = True):
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
        self.detailed_logger.info(f"TOOL: {tool_name} | INPUT: {json.dumps(tool_input, indent=2)}")

    def log_task_completion(self, success: bool, final_message: str, duration: Optional[float] = None):
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
    def task_context(self, execution_prompt: str, model: str, system_prompt: str = None):
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
        CRITICAL RESOURCE CLEANUP: Prevents file handle leaks and logger accumulation.
        MUST be called when task completes to avoid system resource exhaustion.
        Failure to call leads to: file handle exhaustion, memory leaks, logging conflicts.
        """
        self._cleanup_loggers()  # Immediate resource cleanup to prevent system degradation

    def _cleanup_loggers(self):
        """
        Logger resource cleanup: prevents critical system resource leaks in long-running servers.
        Three-phase cleanup: flush data → close file handles → remove logger registry entries.
        CRITICAL for system stability - prevents file handle exhaustion and memory accumulation.
        """
        # Phase 1: File system resource cleanup for each task-specific logger
        for logger in [self.summary_logger, self.detailed_logger]:
            # Handler cleanup loop: ensures all file handles are properly closed
            for handler in logger.handlers[:]:
                handler.flush()  # Force pending data to disk before closing
                handler.close()  # Release file system resources (file handles)
                logger.removeHandler(handler)  # Remove handler reference from logger

            # Handler list cleanup: prevents stale handler references
            logger.handlers.clear()

        # Phase 2: Logger registry cleanup - prevents memory leaks in long-running processes
        # Critical: removes logger entries from Python's global logger dictionary
        logger_names = [self.summary_logger.name, self.detailed_logger.name]
        for name in logger_names:
            # Registry entry removal: prevents logger accumulation over multiple tasks
            if name in logging.Logger.manager.loggerDict:
                del logging.Logger.manager.loggerDict[name]


def create_task_logger(task_id: int, working_directory: str, timestamp: Optional[datetime] = None) -> TaskLogger:
    """
    TaskLogger factory: creates properly configured logger instance for task execution.
    Critical entry point - ensures consistent logger setup across all task executions.
    """
    return TaskLogger(task_id, working_directory, timestamp)  # Standard logger instantiation


def get_log_directory() -> Path:
    """
    Log directory accessor: returns standardized logging directory path.
    Central location for all claude-cto system logs and configuration.
    """
    return Path.home() / ".claude-cto"  # User home-based logging directory


def get_task_logs(task_id: int) -> Optional[Dict[str, str]]:
    """
    Task log discovery: locates log files for specific task ID across log directory.
    Returns all log levels (summary, detailed, global) for comprehensive task analysis.
    Critical for debugging failed tasks and retrieving execution history.
    """
    # Log directory scanning: searches for task-specific log files
    log_dir = get_safe_log_directory()

    # Log pair discovery: finds matching summary and detailed logs for task
    task_logs = {"summary": None, "detailed": None}

    # Summary log scanning: searches for task's concise progress log
    for log_file in log_dir.glob(f"task_{task_id}_*_summary.log"):
        if not task_logs["summary"]:  # First match wins - handles multiple executions
            task_logs["summary"] = str(log_file)

            # Paired detailed log discovery: finds corresponding verbose log
            detailed_pattern = log_file.name.replace("_summary.log", "_detailed.log")
            detailed_path = log_dir / detailed_pattern
            if detailed_path.exists():
                task_logs["detailed"] = str(detailed_path)
            break  # Stop after finding first valid log pair

    # Global log inclusion: adds system-wide log for complete task context
    if task_logs["summary"]:
        task_logs["global"] = str(get_log_directory() / "claude-cto.log")
        return task_logs

    return None  # No logs found for this task ID


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
