"""
SOLE RESPONSIBILITY: Manage subprocess execution with timeouts and notifications.
Provides centralized subprocess handling with proper error reporting.
"""

import subprocess
import logging
import sys
from typing import Optional, List, Tuple, Union

logger = logging.getLogger(__name__)


class SubprocessManager:
    """Manage subprocess execution with consistent timeout and error handling."""

    def __init__(self, default_timeout: int = 30, notify_on_timeout: bool = True):
        """
        Initialize subprocess manager.

        Args:
            default_timeout: Default timeout in seconds for subprocess calls
            notify_on_timeout: Whether to send notifications on timeout
        """
        self.default_timeout = default_timeout
        self.notify_on_timeout = notify_on_timeout
        self.timeout_count = 0
        self.error_count = 0

    def run_command(
        self,
        command: Union[str, List[str]],
        timeout: Optional[int] = None,
        capture_output: bool = True,
        check: bool = False,
        cwd: Optional[str] = None,
        shell: bool = False,
        description: Optional[str] = None,
    ) -> Tuple[int, str, str]:
        """
        Run a command with timeout and error handling.

        Args:
            command: Command to run (string or list)
            timeout: Timeout in seconds (uses default if None)
            capture_output: Whether to capture stdout/stderr
            check: Whether to raise on non-zero exit code
            cwd: Working directory for the command
            shell: Whether to use shell execution
            description: Human-readable description for logging

        Returns:
            Tuple of (return_code, stdout, stderr)

        Raises:
            subprocess.CalledProcessError: If check=True and command fails
        """
        if timeout is None:
            timeout = self.default_timeout

        if description is None:
            description = command if isinstance(command, str) else " ".join(command)

        logger.debug(f"Running command: {description} (timeout={timeout}s)")

        try:
            result = subprocess.run(
                command,
                capture_output=capture_output,
                text=True,
                timeout=timeout,
                check=check,
                cwd=cwd,
                shell=shell,
            )

            logger.debug(f"Command completed: {description} (rc={result.returncode})")
            return result.returncode, result.stdout, result.stderr

        # timeout enforcement and process cleanup: prevents hung processes by force-killing after TimeoutExpired
        except subprocess.TimeoutExpired as e:
            self.timeout_count += 1
            logger.warning(f"Command timed out after {timeout}s: {description}")

            if self.notify_on_timeout:
                self._send_timeout_notification(description, timeout)

            # Try to kill the process
            if hasattr(e, "kill"):
                try:
                    e.kill()
                    logger.info(f"Killed timed-out process: {description}")
                except Exception:
                    pass

            return -1, "", f"Command timed out after {timeout} seconds"

        except subprocess.CalledProcessError as e:
            self.error_count += 1
            logger.error(f"Command failed: {description} (rc={e.returncode})")

            if check:
                raise

            return e.returncode, e.stdout or "", e.stderr or ""

        except FileNotFoundError as e:
            self.error_count += 1
            logger.error(f"Command not found: {description}")
            return -1, "", f"Command not found: {str(e)}"

        except Exception as e:
            self.error_count += 1
            logger.error(f"Unexpected error running command: {description} - {e}")
            return -1, "", str(e)

    def run_with_retry(
        self,
        command: Union[str, List[str]],
        max_retries: int = 3,
        retry_delay: int = 1,
        **kwargs,
    ) -> Tuple[int, str, str]:
        """
        Run a command with automatic retry on failure.

        Args:
            command: Command to run
            max_retries: Maximum number of retry attempts
            retry_delay: Delay between retries in seconds
            **kwargs: Additional arguments for run_command

        Returns:
            Tuple of (return_code, stdout, stderr)
        """
        import time

        for attempt in range(max_retries + 1):
            rc, stdout, stderr = self.run_command(command, **kwargs)

            if rc == 0:
                return rc, stdout, stderr

            if attempt < max_retries:
                logger.info(f"Retrying command (attempt {attempt + 2}/{max_retries + 1})")
                # exponential backoff retry logic: doubles delay each attempt to handle transient failures gracefully
                time.sleep(retry_delay * (2**attempt))  # Exponential backoff

        return rc, stdout, stderr

    def check_command_exists(self, command: str) -> bool:
        """
        Check if a command exists in the system PATH.

        Args:
            command: Command name to check

        Returns:
            True if command exists, False otherwise
        """
        # cross-platform command detection: Unix 'which' vs Windows 'where' for PATH lookup
        check_cmd = ["which", command] if sys.platform != "win32" else ["where", command]
        rc, _, _ = self.run_command(check_cmd, timeout=2, capture_output=True)
        return rc == 0

    def _send_timeout_notification(self, command: str, timeout: int) -> None:
        """Send a notification when a command times out."""
        try:
            # Try to use the notification system if available
            from .notification import NotificationManager

            notifier = NotificationManager()
            notifier.notify_error(f"Subprocess timeout: {command[:50]}... (after {timeout}s)")
        except ImportError:
            # Fallback to logging
            logger.warning(f"Subprocess timeout notification: {command} after {timeout}s")

    def get_stats(self) -> dict:
        """
        Get statistics about subprocess execution.

        Returns:
            Dictionary with timeout and error counts
        """
        return {
            "timeout_count": self.timeout_count,
            "error_count": self.error_count,
            "total_issues": self.timeout_count + self.error_count,
        }

    def reset_stats(self) -> None:
        """Reset statistics counters."""
        self.timeout_count = 0
        self.error_count = 0


# Global subprocess manager instance
_subprocess_manager = None


def get_subprocess_manager(default_timeout: int = 30, notify_on_timeout: bool = True) -> SubprocessManager:
    """
    Get the global subprocess manager instance.

    Args:
        default_timeout: Default timeout for commands
        notify_on_timeout: Whether to notify on timeouts

    Returns:
        SubprocessManager instance
    """
    # singleton instance for consistent timeout policies: ensures all subprocess calls use same configuration
    global _subprocess_manager
    if _subprocess_manager is None:
        _subprocess_manager = SubprocessManager(default_timeout, notify_on_timeout)
    return _subprocess_manager


def run_safe_command(
    command: Union[str, List[str]],
    timeout: int = 30,
    description: Optional[str] = None,
) -> Tuple[bool, str]:
    """
    Convenience function to run a command safely with timeout.

    Args:
        command: Command to run
        timeout: Timeout in seconds
        description: Description for logging

    Returns:
        Tuple of (success, output_or_error)
    """
    manager = get_subprocess_manager()
    rc, stdout, stderr = manager.run_command(command, timeout=timeout, description=description)

    if rc == 0:
        return True, stdout
    else:
        return False, stderr or f"Command failed with return code {rc}"
