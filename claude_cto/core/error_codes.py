"""
SOLE RESPONSIBILITY: Centralized error codes and categories for claude-cto.
Provides structured error classification, correlation, and monitoring hooks.
"""

from enum import Enum
from typing import Dict, Any, Optional
import uuid
from datetime import datetime


class ErrorCategory(Enum):
    """High-level error classification for monitoring."""

    # User errors (4xx equivalent)
    USER_INPUT = "user_input"  # Invalid user input
    AUTHENTICATION = "authentication"  # Auth failures
    VALIDATION = "validation"  # Validation errors
    NOT_FOUND = "not_found"  # Resource not found

    # System errors (5xx equivalent)
    SYSTEM = "system"  # Internal system errors
    INTEGRATION = "integration"  # External service errors
    INFRASTRUCTURE = "infrastructure"  # Infrastructure issues
    TEMPORARY = "temporary"  # Transient errors

    # Claude-specific
    SDK = "sdk"  # Claude SDK errors
    CLI = "cli"  # Claude CLI errors
    PROCESS = "process"  # Process execution errors


class ErrorSeverity(Enum):
    """Priority levels for error alerting."""

    DEBUG = "debug"  # Development only
    INFO = "info"  # Informational
    WARNING = "warning"  # Warning, may need attention
    ERROR = "error"  # Error, needs attention
    CRITICAL = "critical"  # Critical, immediate attention


class ErrorCode(Enum):
    """Trackable error identifiers for consistent error handling."""

    # Authentication & Authorization (1xxx)
    AUTH_API_KEY_INVALID = 1001
    AUTH_OAUTH_EXPIRED = 1002
    AUTH_NO_CREDENTIALS = 1003

    # Validation Errors (2xxx)
    VALIDATION_PROMPT_TOO_SHORT = 2001
    VALIDATION_NO_PATH_IN_PROMPT = 2002
    VALIDATION_SYSTEM_PROMPT_INVALID = 2003
    VALIDATION_MODEL_INVALID = 2004

    # Task Errors (3xxx)
    TASK_NOT_FOUND = 3001
    TASK_ALREADY_RUNNING = 3002
    TASK_TIMEOUT = 3003
    TASK_CANCELLED = 3004

    # Claude SDK Errors (4xxx)
    SDK_CLI_NOT_FOUND = 4001
    SDK_CLI_CONNECTION = 4002
    SDK_PROCESS_ERROR = 4003
    SDK_JSON_DECODE = 4004
    SDK_MESSAGE_PARSE = 4005
    SDK_GENERIC = 4006

    # System Errors (5xxx)
    SYSTEM_DATABASE_LOCK = 5001
    SYSTEM_DISK_FULL = 5002
    SYSTEM_MEMORY_LIMIT = 5003
    SYSTEM_PROCESS_LIMIT = 5004

    # Network Errors (6xxx)
    NETWORK_TIMEOUT = 6001
    NETWORK_CONNECTION = 6002
    NETWORK_DNS = 6003

    # Rate Limiting (7xxx)
    RATE_LIMIT_EXCEEDED = 7001
    RATE_LIMIT_DAILY = 7002

    # Unknown (9xxx)
    UNKNOWN_ERROR = 9999


class ErrorContext:
    """Context for error tracing across service boundaries."""

    def __init__(
        self,
        task_id: Optional[int] = None,
        correlation_id: Optional[str] = None,
        user_id: Optional[str] = None,
        session_id: Optional[str] = None,
        request_id: Optional[str] = None,
    ):
        self.task_id = task_id
        self.correlation_id = correlation_id or str(uuid.uuid4())  # Traces single logical operation across services
        self.user_id = user_id
        self.session_id = session_id
        self.request_id = request_id
        self.timestamp = datetime.utcnow()
        self.metadata: Dict[str, Any] = {}

    def add_metadata(self, key: str, value: Any) -> None:
        """Add metadata to error context."""
        self.metadata[key] = value

    def to_dict(self) -> Dict[str, Any]:
        """Convert context to dictionary for logging."""
        return {
            "task_id": self.task_id,
            "correlation_id": self.correlation_id,
            "user_id": self.user_id,
            "session_id": self.session_id,
            "request_id": self.request_id,
            "timestamp": self.timestamp.isoformat(),
            "metadata": self.metadata,
        }


class ErrorMetrics:
    """Counters for application observability."""

    def __init__(self):
        self.error_counts: Dict[ErrorCode, int] = {}
        self.category_counts: Dict[ErrorCategory, int] = {}
        self.recovery_success: Dict[ErrorCode, int] = {}
        self.recovery_failure: Dict[ErrorCode, int] = {}
        self.last_errors: Dict[ErrorCode, datetime] = {}

    def record_error(self, code: ErrorCode, category: ErrorCategory, recovered: bool = False) -> None:
        """Record an error occurrence."""
        # Increment counters
        self.error_counts[code] = self.error_counts.get(code, 0) + 1
        self.category_counts[category] = self.category_counts.get(category, 0) + 1

        # Track recovery
        if recovered:
            self.recovery_success[code] = self.recovery_success.get(code, 0) + 1
        else:
            self.recovery_failure[code] = self.recovery_failure.get(code, 0) + 1

        # Track timing
        self.last_errors[code] = datetime.utcnow()

    def get_error_rate(self, code: ErrorCode) -> float:
        """Get error rate for a specific code."""
        total = self.error_counts.get(code, 0)
        if total == 0:
            return 0.0

        failures = self.recovery_failure.get(code, 0)
        return failures / total

    def get_stats(self) -> Dict[str, Any]:
        """Get current error statistics."""
        return {
            "error_counts": {k.name: v for k, v in self.error_counts.items()},
            "category_counts": {k.value: v for k, v in self.category_counts.items()},
            "recovery_rates": {
                k.name: {
                    "success": self.recovery_success.get(k, 0),
                    "failure": self.recovery_failure.get(k, 0),
                    "rate": self.get_error_rate(k),
                }
                for k in self.error_counts.keys()
            },
            "last_errors": {k.name: v.isoformat() for k, v in self.last_errors.items()},
        }


# Global metrics instance
_metrics = ErrorMetrics()


def get_metrics() -> ErrorMetrics:
    """Get the global error metrics instance."""
    return _metrics


def map_sdk_error_to_code(error: Exception) -> ErrorCode:
    """Map Claude SDK error to error code."""
    from claude_code_sdk._errors import (
        CLINotFoundError,
        CLIConnectionError,
        ProcessError,
        CLIJSONDecodeError,
        MessageParseError,
        ClaudeSDKError,
    )

    # Translates SDK exceptions to internal codes
    error_map = {
        CLINotFoundError: ErrorCode.SDK_CLI_NOT_FOUND,
        CLIConnectionError: ErrorCode.SDK_CLI_CONNECTION,
        ProcessError: ErrorCode.SDK_PROCESS_ERROR,
        CLIJSONDecodeError: ErrorCode.SDK_JSON_DECODE,
        MessageParseError: ErrorCode.SDK_MESSAGE_PARSE,
        ClaudeSDKError: ErrorCode.SDK_GENERIC,
    }

    for error_type, code in error_map.items():
        if isinstance(error, error_type):
            return code

    return ErrorCode.UNKNOWN_ERROR


def categorize_error(error: Exception) -> ErrorCategory:
    """Determines broad category through pattern matching."""
    from claude_code_sdk._errors import (
        CLINotFoundError,
        CLIConnectionError,
        ProcessError,
        CLIJSONDecodeError,
        MessageParseError,
    )

    # Authentication errors
    error_msg = str(error).lower()
    if "auth" in error_msg or "api_key" in error_msg or "401" in error_msg:
        return ErrorCategory.AUTHENTICATION

    # Validation errors
    if "validation" in error_msg or "invalid" in error_msg:
        return ErrorCategory.VALIDATION

    # SDK/CLI errors
    if isinstance(error, (CLINotFoundError, CLIJSONDecodeError, MessageParseError)):
        return ErrorCategory.SDK

    # Process errors
    if isinstance(error, ProcessError):
        return ErrorCategory.PROCESS

    # Connection/Network errors
    if isinstance(error, (CLIConnectionError, ConnectionError, TimeoutError)):
        return ErrorCategory.TEMPORARY

    # Rate limiting
    if "rate limit" in error_msg or "429" in error_msg:
        return ErrorCategory.TEMPORARY

    # Default to system error
    return ErrorCategory.SYSTEM


def get_severity(error: Exception) -> ErrorSeverity:
    """Assigns priority level based on exception type."""
    from claude_code_sdk._errors import CLINotFoundError, ProcessError

    # Critical errors - need immediate attention
    if isinstance(error, CLINotFoundError):
        return ErrorSeverity.CRITICAL

    # Errors - need attention
    if isinstance(error, ProcessError):
        exit_code = getattr(error, "exit_code", None)
        if exit_code == 127:  # Command not found
            return ErrorSeverity.CRITICAL
        elif exit_code in [126, 1]:  # Permission or general error
            return ErrorSeverity.ERROR
        else:
            return ErrorSeverity.WARNING

    # Warnings - may need attention
    error_msg = str(error).lower()
    if "rate limit" in error_msg:
        return ErrorSeverity.WARNING

    # Default to error
    return ErrorSeverity.ERROR
