"""
Comprehensive error handler for Claude SDK errors.
Maps SDK exceptions to appropriate responses with debugging info and recovery suggestions.
"""

import traceback
from typing import Dict, Any, Optional
from datetime import datetime, timezone
from pathlib import Path

from claude_code_sdk._errors import (
    ClaudeSDKError,
    ProcessError,
    CLINotFoundError,
    CLIConnectionError,
    CLIJSONDecodeError,
    MessageParseError,
)


class ErrorHandler:
    """Centralized error handling for Claude CTO tasks."""

    @classmethod
    def is_transient_error(cls, error: Exception) -> bool:
        """
        Critical error classification: determines retry-worthiness to prevent infinite loops.
        Follows Carmack's philosophy - simple, explicit categorization with clear boundaries.
        Enhanced with better error classification logic.
        """
        import asyncio

        # Network connectivity errors: always transient, worth retrying with backoff
        if isinstance(
            error,
            (CLIConnectionError, ConnectionError, TimeoutError, asyncio.TimeoutError),
        ):
            return True

        # Rate limiting detection: API quota exceeded, should retry with longer delay
        error_msg = str(error).lower()
        if "rate limit" in error_msg or "429" in error_msg:
            return True

        # JSON parsing failure analysis: distinguishes corruption vs malformed data
        if isinstance(error, CLIJSONDecodeError):
            # Network-induced corruption: likely transient stream interruption
            if hasattr(error, "original_error"):
                orig_msg = str(error.original_error).lower()
                if "timeout" in orig_msg or "connection" in orig_msg:
                    return True
            # Data truncation indicators: often caused by network interruptions
            if "incomplete" in error_msg or "truncated" in error_msg:
                return True
            # Structural JSON errors: permanent parsing issues, don't retry
            return False

        # Process execution failure analysis: examines exit codes and stderr patterns
        if isinstance(error, ProcessError):
            exit_code = getattr(error, "exit_code", None)
            # System signal exit codes: process killed by timeout or system resource limits
            if exit_code in [124, 137, 143]:  # timeout, SIGKILL, SIGTERM
                return True
            # Error message pattern matching: identifies transient system conditions
            stderr = getattr(error, "stderr", "")
            if stderr:
                stderr_lower = stderr.lower()
                if any(
                    word in stderr_lower
                    for word in [
                        "timeout",
                        "connection",
                        "network",
                        "rate limit",
                        "temporary",
                    ]
                ):
                    return True
            # Most ProcessErrors are permanent code/environment issues
            return False

        # Explicitly permanent errors
        if isinstance(error, (CLINotFoundError, MessageParseError)):
            return False

        # Network/connection issues in error messages
        if any(word in error_msg for word in ["connection", "network", "timeout", "temporary", "unavailable"]):
            return True

        # Everything else is permanent (auth errors, parse errors, etc.)
        return False

    # Map specific exceptions to HTTP status codes
    ERROR_STATUS_CODES = {
        CLINotFoundError: 503,  # Service Unavailable - CLI not installed
        CLIConnectionError: 502,  # Bad Gateway - Can't connect to CLI
        ProcessError: 500,  # Internal Server Error - Process failed
        CLIJSONDecodeError: 502,  # Bad Gateway - Invalid response from CLI
        MessageParseError: 502,  # Bad Gateway - Can't parse CLI message
        ClaudeSDKError: 500,  # Internal Server Error - Generic SDK error
    }

    # Provide actionable, human-readable recovery steps for users
    RECOVERY_SUGGESTIONS = {
        CLINotFoundError: [
            "Install Claude CLI: npm install -g @anthropic-ai/claude-code",
            "Verify installation: claude --version",
            "Check PATH environment variable includes Claude CLI location",
            'For local install, add to PATH: export PATH="$HOME/node_modules/.bin:$PATH"',
        ],
        CLIConnectionError: [
            "Verify Claude CLI is working: claude --version",
            "Check if you're authenticated: claude auth status",
            "Try re-authenticating: claude auth login",
            "Check network connectivity and firewall settings",
            "Restart the Claude CTO server",
        ],
        ProcessError: {
            # Exit code specific suggestions
            1: ["General error - check task logs for details"],
            2: ["CLI command failed - verify syntax and parameters"],
            126: ["Permission denied - check file permissions"],
            127: ["Command not found - verify Claude CLI is in PATH"],
            128: ["Invalid exit argument"],
            130: ["Script terminated by Ctrl+C"],
            255: ["Exit status out of range"],
            # Default for unknown exit codes
            "default": ["Check task logs for detailed error information"],
        },
        CLIJSONDecodeError: [
            "This may be a temporary issue - retry the task",
            "Check if Claude CLI version is up to date: npm update -g @anthropic-ai/claude-code",
            "Clear any corrupted cache: rm -rf ~/.claude/cache",
            "Report issue if persistent: https://github.com/anthropics/claude-code/issues",
        ],
        MessageParseError: [
            "Update Claude Code SDK: pip install --upgrade claude-code-sdk",
            "Check compatibility between SDK and CLI versions",
            "Review task logs for the problematic message format",
            "Report incompatibility issue with message data included",
        ],
        ClaudeSDKError: [
            "Review the specific error message for details",
            "Check Claude Code SDK documentation",
            "Verify all required environment variables are set",
            "Ensure task parameters are valid",
        ],
    }

    @classmethod
    def handle_error(cls, error: Exception, task_id: int, log_file_path: Optional[str] = None) -> Dict[str, Any]:
        """
        Handle an error and return structured error information.

        Args:
            error: The exception that occurred
            task_id: ID of the failed task
            log_file_path: Path to task log file

        Returns:
            Dictionary with error details, debugging info, and recovery suggestions
        """
        error_type = type(error).__name__
        error_class = type(error)

        # Build base error info
        error_info = {
            "task_id": task_id,
            "error_type": error_type,
            "error_message": str(error),
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "status_code": cls.ERROR_STATUS_CODES.get(error_class, 500),
        }

        # Add specific error attributes based on type
        if isinstance(error, ProcessError):
            error_info.update(
                {
                    "exit_code": error.exit_code,
                    "stderr": error.stderr,
                    "debugging": {
                        "exit_code_meaning": cls._get_exit_code_meaning(error.exit_code),
                        "likely_cause": cls._analyze_process_error(error),
                    },
                }
            )

        elif isinstance(error, CLINotFoundError):
            error_info.update(
                {
                    "cli_path": getattr(error, "cli_path", None),
                    "debugging": {
                        "node_installed": cls._check_node_installed(),
                        "npm_global_path": cls._get_npm_global_path(),
                        "path_env": cls._get_path_directories(),
                    },
                }
            )

        elif isinstance(error, CLIConnectionError):
            error_info.update(
                {
                    "debugging": {
                        "possible_causes": [
                            "Claude CLI not running or crashed",
                            "Authentication expired or invalid",
                            "Network connectivity issues",
                            "Firewall blocking connection",
                        ],
                        "auth_status": cls._check_auth_status(),
                    }
                }
            )

        elif isinstance(error, CLIJSONDecodeError):
            error_info.update(
                {
                    "problematic_line": (error.line[:500] if hasattr(error, "line") else None),
                    "original_error": (str(error.original_error) if hasattr(error, "original_error") else None),
                    "debugging": {
                        "line_preview": (
                            error.line[:100] + "..."
                            if hasattr(error, "line") and len(error.line) > 100
                            else error.line if hasattr(error, "line") else None
                        ),
                        "json_error_type": (
                            type(error.original_error).__name__ if hasattr(error, "original_error") else None
                        ),
                    },
                }
            )

        elif isinstance(error, MessageParseError):
            error_info.update(
                {
                    "parse_data": error.data if hasattr(error, "data") else None,
                    "debugging": {
                        "data_type": (type(error.data).__name__ if hasattr(error, "data") else None),
                        "data_keys": (
                            list(error.data.keys()) if hasattr(error, "data") and isinstance(error.data, dict) else None
                        ),
                    },
                }
            )

        # Add recovery suggestions
        error_info["recovery_suggestions"] = cls._get_recovery_suggestions(error)

        # Add log file info if available
        if log_file_path:
            error_info["log_file"] = log_file_path
            error_info["log_tail"] = cls._get_log_tail(log_file_path, lines=20)

        # Add stack trace for unexpected errors
        if not isinstance(error, tuple(cls.ERROR_STATUS_CODES.keys())):
            error_info["stack_trace"] = traceback.format_exc()

        return error_info

    @classmethod
    def format_error_message(cls, error_info: Dict[str, Any]) -> str:
        """
        Format error info into a human-readable error message.

        Args:
            error_info: Error information dictionary

        Returns:
            Formatted error message string
        """
        parts = [f"[{error_info['error_type']}] {error_info['error_message']}"]

        # Add specific details based on error type
        if "exit_code" in error_info:
            parts.append(f"exit_code: {error_info['exit_code']}")
            if "exit_code_meaning" in error_info.get("debugging", {}):
                parts.append(f"meaning: {error_info['debugging']['exit_code_meaning']}")

        if "stderr" in error_info and error_info["stderr"]:
            stderr_preview = error_info["stderr"][:200]
            if len(error_info["stderr"]) > 200:
                stderr_preview += "..."
            parts.append(f"stderr: {stderr_preview}")

        if "cli_path" in error_info and error_info["cli_path"]:
            parts.append(f"searched at: {error_info['cli_path']}")

        if "problematic_line" in error_info and error_info["problematic_line"]:
            parts.append(f"failed to parse: {error_info['problematic_line'][:100]}...")

        # Add first recovery suggestion
        if "recovery_suggestions" in error_info and error_info["recovery_suggestions"]:
            parts.append(f"suggestion: {error_info['recovery_suggestions'][0]}")

        return " | ".join(parts)

    @classmethod
    def log_error(cls, error_info: Dict[str, Any], log_file_path: str) -> None:
        """
        Write detailed error information to log file.

        Args:
            error_info: Error information dictionary
            log_file_path: Path to log file
        """
        with open(log_file_path, "a") as f:
            f.write(f"\n{'='*60}\n")
            f.write(f"[ERROR] {error_info['timestamp']}\n")
            f.write(f"Type: {error_info['error_type']}\n")
            f.write(f"Message: {error_info['error_message']}\n")

            # Write debugging info
            if "debugging" in error_info:
                f.write("\nDebugging Information:\n")
                for key, value in error_info["debugging"].items():
                    f.write(f"  {key}: {value}\n")

            # Write recovery suggestions
            if "recovery_suggestions" in error_info:
                f.write("\nRecovery Suggestions:\n")
                for i, suggestion in enumerate(error_info["recovery_suggestions"], 1):
                    f.write(f"  {i}. {suggestion}\n")

            # Write stack trace if present
            if "stack_trace" in error_info:
                f.write("\nStack Trace:\n")
                f.write(error_info["stack_trace"])

            f.write(f"{'='*60}\n\n")

    @staticmethod
    def _get_exit_code_meaning(exit_code: Optional[int]) -> str:
        """Get human-readable meaning of exit code."""
        if exit_code is None:
            return "No exit code available"

        exit_code_meanings = {
            0: "Success",
            1: "General error",
            2: "Misuse of shell command",
            126: "Command cannot execute (permission problem)",
            127: "Command not found",
            128: "Invalid exit argument",
            130: "Script terminated by Ctrl+C",
            255: "Exit status out of range",
        }

        if exit_code in exit_code_meanings:
            return exit_code_meanings[exit_code]
        elif exit_code > 128:
            return f"Terminated by signal {exit_code - 128}"
        else:
            return f"Unknown exit code: {exit_code}"

    @staticmethod
    def _analyze_process_error(error: ProcessError) -> str:
        """Analyze ProcessError to determine likely cause."""
        if error.exit_code == 127:
            return "Claude CLI command not found in PATH"
        elif error.exit_code == 126:
            return "Permission denied - check file permissions"
        elif error.stderr and "ANTHROPIC_API_KEY" in error.stderr:
            return "API key issue - check ANTHROPIC_API_KEY environment variable"
        elif error.stderr and "authentication" in error.stderr.lower():
            return "Authentication issue - try 'claude auth login'"
        elif error.stderr and "network" in error.stderr.lower():
            return "Network connectivity issue"
        elif error.stderr and "rate limit" in error.stderr.lower():
            return "Rate limit exceeded - wait before retrying"
        else:
            return "Process failed - check stderr for details"

    @staticmethod
    def _check_node_installed() -> bool:
        """Check if Node.js is installed."""
        import shutil

        return shutil.which("node") is not None

    @staticmethod
    def _get_npm_global_path() -> Optional[str]:
        """Get npm global installation path."""
        import subprocess

        try:
            result = subprocess.run(
                ["npm", "config", "get", "prefix"],
                capture_output=True,
                text=True,
                timeout=2,
            )
            if result.returncode == 0:
                return result.stdout.strip()
        except Exception:
            pass
        return None

    @staticmethod
    def _get_path_directories() -> list:
        """Get directories in PATH environment variable."""
        import os

        path = os.environ.get("PATH", "")
        return path.split(os.pathsep) if path else []

    @staticmethod
    def _check_auth_status() -> str:
        """Check Claude CLI authentication status."""
        import subprocess

        try:
            result = subprocess.run(["claude", "auth", "status"], capture_output=True, text=True, timeout=2)
            if result.returncode == 0:
                return "Authenticated"
            else:
                return "Not authenticated"
        except FileNotFoundError:
            return "Claude CLI not found"
        except Exception:
            return "Unable to check"

    @classmethod
    def _get_recovery_suggestions(cls, error: Exception) -> list:
        """Get recovery suggestions for the error type."""
        error_class = type(error)

        if error_class in cls.RECOVERY_SUGGESTIONS:
            suggestions = cls.RECOVERY_SUGGESTIONS[error_class]

            # Special handling for ProcessError with exit codes
            if isinstance(error, ProcessError) and isinstance(suggestions, dict):
                exit_code = error.exit_code
                if exit_code in suggestions:
                    return suggestions[exit_code]
                else:
                    return suggestions.get("default", [])

            return suggestions if isinstance(suggestions, list) else []

        # Default suggestions for unknown errors
        return [
            "Check task logs for details",
            "Retry the task",
            "Contact support if issue persists",
        ]

    @staticmethod
    def _get_log_tail(log_file_path: str, lines: int = 20) -> Optional[str]:
        """Get last N lines from log file."""
        try:
            log_path = Path(log_file_path)
            if log_path.exists():
                with open(log_path, "r") as f:
                    all_lines = f.readlines()
                    return "".join(all_lines[-lines:])
        except Exception:
            pass
        return None
