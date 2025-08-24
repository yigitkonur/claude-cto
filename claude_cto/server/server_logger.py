"""
Comprehensive server logging infrastructure for Claude CTO.
Captures crashes, errors, requests, and important events.
"""

import os
import sys
import json
import logging
import traceback
from pathlib import Path
from datetime import datetime, timezone
from typing import Optional, Dict, Any
from logging.handlers import RotatingFileHandler
from contextlib import asynccontextmanager


# Create logs directory structure
def get_log_directory() -> Path:
    """Get or create the server logs directory."""
    log_base = Path.home() / ".claude-cto" / "logs"
    server_logs = log_base / "server"
    server_logs.mkdir(parents=True, exist_ok=True)
    return server_logs


def get_crash_log_directory() -> Path:
    """Get or create the crash logs directory."""
    log_base = Path.home() / ".claude-cto" / "logs"
    crash_logs = log_base / "crashes"
    crash_logs.mkdir(parents=True, exist_ok=True)
    return crash_logs


# Configure server logger
def setup_server_logger(debug: bool = False) -> logging.Logger:
    """
    Set up comprehensive server logging with rotation.

    Creates multiple log files:
    - server.log: Main server operations
    - error.log: Errors and exceptions
    - access.log: HTTP requests/responses
    - crash.log: Fatal crashes and unhandled exceptions
    """
    log_dir = get_log_directory()

    # Create main server logger
    logger = logging.getLogger("claude_cto.server")
    logger.setLevel(logging.DEBUG if debug else logging.INFO)

    # Remove existing handlers to avoid duplicates
    for handler in logger.handlers[:]:
        handler.flush()
        handler.close()
        logger.removeHandler(handler)

    # Main server log (10MB max, keep 5 backups)
    server_handler = RotatingFileHandler(log_dir / "server.log", maxBytes=10 * 1024 * 1024, backupCount=5)  # 10MB
    server_handler.setLevel(logging.INFO)
    server_formatter = logging.Formatter(
        "%(asctime)s - %(name)s - %(levelname)s - %(message)s",
        datefmt="%Y-%m-%d %H:%M:%S",
    )
    server_handler.setFormatter(server_formatter)
    logger.addHandler(server_handler)

    # Error log (5MB max, keep 10 backups)
    error_handler = RotatingFileHandler(log_dir / "error.log", maxBytes=5 * 1024 * 1024, backupCount=10)  # 5MB
    error_handler.setLevel(logging.ERROR)
    error_formatter = logging.Formatter(
        "%(asctime)s - %(name)s - %(levelname)s - %(filename)s:%(lineno)d - %(message)s\n%(exc_info)s",
        datefmt="%Y-%m-%d %H:%M:%S",
    )
    error_handler.setFormatter(error_formatter)
    logger.addHandler(error_handler)

    # Console handler for development
    if debug or os.getenv("CLAUDE_CTO_DEBUG"):
        console_handler = logging.StreamHandler()
        console_handler.setLevel(logging.DEBUG)
        console_handler.setFormatter(server_formatter)
        logger.addHandler(console_handler)

    return logger


# Access logger for HTTP requests
def setup_access_logger() -> logging.Logger:
    """Set up HTTP access logging."""
    log_dir = get_log_directory()

    logger = logging.getLogger("claude_cto.access")
    logger.setLevel(logging.INFO)

    # Remove existing handlers to avoid duplicates
    for handler in logger.handlers[:]:
        handler.flush()
        handler.close()
        logger.removeHandler(handler)

    # Access log (20MB max, keep 3 backups)
    access_handler = RotatingFileHandler(log_dir / "access.log", maxBytes=20 * 1024 * 1024, backupCount=3)  # 20MB
    access_formatter = logging.Formatter("%(asctime)s - %(message)s", datefmt="%Y-%m-%d %H:%M:%S")
    access_handler.setFormatter(access_formatter)
    logger.addHandler(access_handler)

    return logger


# Crash logger for fatal errors
def log_crash(error: Exception, context: Optional[Dict[str, Any]] = None):
    """
    Log a crash with full context and stack trace.
    Writes to both crash log and creates a crash report file.
    """
    crash_dir = get_crash_log_directory()
    timestamp = datetime.now(timezone.utc)

    # Create crash report filename
    crash_id = timestamp.strftime("%Y%m%d_%H%M%S")
    crash_file = crash_dir / f"crash_{crash_id}.json"

    # Collect crash information
    crash_info = {
        "timestamp": timestamp.isoformat(),
        "error_type": type(error).__name__,
        "error_message": str(error),
        "stack_trace": traceback.format_exc(),
        "python_version": sys.version,
        "platform": sys.platform,
        "context": context or {},
        "environment": {k: v for k, v in os.environ.items() if k.startswith("CLAUDE_") or k == "ANTHROPIC_API_KEY"},
    }

    # Sanitize sensitive data
    if "ANTHROPIC_API_KEY" in crash_info["environment"]:
        crash_info["environment"]["ANTHROPIC_API_KEY"] = "***REDACTED***"

    # Write crash report
    with open(crash_file, "w") as f:
        json.dump(crash_info, f, indent=2, default=str)

    # Also log to error.log
    logger = logging.getLogger("claude_cto.server")
    logger.critical(f"CRASH: {error}", exc_info=True, extra={"crash_id": crash_id})

    return crash_id


# Request/Response logging middleware
async def log_request_response(request, call_next):
    """Middleware to log all HTTP requests and responses."""
    access_logger = logging.getLogger("claude_cto.access")
    server_logger = logging.getLogger("claude_cto.server")

    # Log request
    start_time = datetime.now(timezone.utc)
    request_id = start_time.strftime("%Y%m%d%H%M%S") + str(id(request))[-4:]

    access_logger.info(
        f"REQUEST [{request_id}] {request.method} {request.url.path} "
        f"from {request.client.host if request.client else 'unknown'}"
    )

    try:
        # Process request
        response = await call_next(request)

        # Log response
        duration = (datetime.now(timezone.utc) - start_time).total_seconds()
        access_logger.info(f"RESPONSE [{request_id}] {response.status_code} " f"in {duration:.3f}s")

        # Log errors
        if response.status_code >= 500:
            server_logger.error(
                f"Server error on {request.method} {request.url.path}: " f"Status {response.status_code}"
            )
        elif response.status_code >= 400:
            server_logger.warning(
                f"Client error on {request.method} {request.url.path}: " f"Status {response.status_code}"
            )

        return response

    except Exception as e:
        # Log unhandled exception
        duration = (datetime.now(timezone.utc) - start_time).total_seconds()
        crash_id = log_crash(
            e,
            {
                "request_id": request_id,
                "method": request.method,
                "path": str(request.url.path),
                "duration": duration,
            },
        )

        access_logger.error(
            f"CRASH [{request_id}] 500 Internal Server Error " f"(crash_id: {crash_id}) in {duration:.3f}s"
        )

        raise


# Exception handler for unhandled exceptions
def setup_exception_handler():
    """Set up global exception handler for uncaught exceptions."""

    def handle_exception(exc_type, exc_value, exc_traceback):
        if issubclass(exc_type, KeyboardInterrupt):
            sys.__excepthook__(exc_type, exc_value, exc_traceback)
            return

        logger = logging.getLogger("claude_cto.server")
        logger.critical("Uncaught exception", exc_info=(exc_type, exc_value, exc_traceback))

        # Log crash
        log_crash(exc_value, {"type": "uncaught_exception"})

    sys.excepthook = handle_exception


# Startup/shutdown logging
@asynccontextmanager
async def log_lifecycle(app_name: str = "claude-cto"):
    """Context manager for logging server lifecycle events."""
    logger = logging.getLogger("claude_cto.server")

    # Startup
    startup_time = datetime.now(timezone.utc)
    logger.info(f"{'='*60}")
    logger.info(f"Starting {app_name} server")
    logger.info(f"Timestamp: {startup_time.isoformat()}")
    logger.info(f"Python: {sys.version}")
    logger.info(f"Platform: {sys.platform}")
    logger.info(f"PID: {os.getpid()}")
    logger.info(f"Log directory: {get_log_directory()}")
    logger.info(f"{'='*60}")

    try:
        yield
    finally:
        # Shutdown
        shutdown_time = datetime.now(timezone.utc)
        uptime = (shutdown_time - startup_time).total_seconds()

        logger.info(f"{'='*60}")
        logger.info(f"Shutting down {app_name} server")
        logger.info(f"Uptime: {uptime:.2f} seconds")
        logger.info(f"Shutdown time: {shutdown_time.isoformat()}")
        logger.info(f"{'='*60}")


# Database operation logging
def log_database_operation(operation: str, details: Dict[str, Any], error: Optional[Exception] = None):
    """Log database operations for debugging."""
    logger = logging.getLogger("claude_cto.server.db")

    if error:
        logger.error(
            f"Database {operation} failed: {error}",
            extra={"operation": operation, "details": details},
        )
    else:
        logger.debug(
            f"Database {operation} completed",
            extra={"operation": operation, "details": details},
        )


# Task execution logging
def log_task_event(task_id: int, event: str, details: Optional[Dict[str, Any]] = None):
    """Log task lifecycle events."""
    logger = logging.getLogger("claude_cto.server.tasks")

    log_message = f"Task {task_id}: {event}"
    if details:
        log_message += f" - {json.dumps(details, default=str)}"

    logger.info(log_message)


# Initialize all loggers
def initialize_logging(debug: bool = False):
    """Initialize all logging systems."""
    # Set up loggers
    setup_server_logger(debug)
    setup_access_logger()
    setup_exception_handler()

    # Create task logger
    task_logger = logging.getLogger("claude_cto.server.tasks")
    task_logger.setLevel(logging.INFO)

    # Create database logger
    db_logger = logging.getLogger("claude_cto.server.db")
    db_logger.setLevel(logging.DEBUG if debug else logging.INFO)

    # Log initialization
    logger = logging.getLogger("claude_cto.server")
    logger.info("Logging system initialized")

    return logger
