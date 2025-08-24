"""
SOLE RESPONSIBILITY: Advanced retry logic with exponential backoff and circuit breaker.
Handles transient errors intelligently with configurable retry strategies.
"""

import asyncio
import random
import time
from typing import Optional, Callable, Any, Dict, TypeVar, Coroutine
from dataclasses import dataclass
from enum import Enum
from datetime import datetime
import logging

from .circuit_breaker_persistence import (
    get_circuit_breaker_persistence,
)

logger = logging.getLogger(__name__)

T = TypeVar("T")


class RetryStrategy(Enum):
    """Retry strategy types."""
    # Defines available backoff algorithms
    EXPONENTIAL = "exponential"  # Exponential backoff
    LINEAR = "linear"  # Linear backoff
    FIBONACCI = "fibonacci"  # Fibonacci backoff
    FIXED = "fixed"  # Fixed delay


@dataclass
class RetryConfig:
    """Configuration for retry behavior."""

    max_attempts: int = 3
    initial_delay: float = 1.0  # seconds
    max_delay: float = 60.0  # seconds
    exponential_base: float = 2.0  # for exponential backoff
    jitter: bool = True  # add randomization
    strategy: RetryStrategy = RetryStrategy.EXPONENTIAL

    # Circuit breaker settings
    circuit_breaker_threshold: int = 5  # failures before opening
    circuit_breaker_timeout: float = 60.0  # seconds before half-open
    circuit_breaker_enabled: bool = True

    # Rate limit specific
    rate_limit_initial_delay: float = 60.0  # longer initial delay for rate limits

    # Error-specific overrides
    error_configs: Dict[str, Dict[str, Any]] = None

    def __post_init__(self):
        if self.error_configs is None:
            self.error_configs = {
                "rate_limit": {
                    "initial_delay": 60.0,
                    "max_attempts": 5,
                    "exponential_base": 1.5,
                },
                "connection": {
                    "initial_delay": 2.0,
                    "max_attempts": 4,
                    "exponential_base": 2.0,
                },
                "timeout": {
                    "initial_delay": 5.0,
                    "max_attempts": 3,
                    "exponential_base": 2.0,
                },
            }


class CircuitState(Enum):
    """Circuit breaker states."""
    # Represents the three states of the circuit breaker FSM
    CLOSED = "closed"  # Normal operation: requests flow through normally
    OPEN = "open"  # Failing state: reject all requests to prevent cascading failures
    HALF_OPEN = "half_open"  # Testing state: allow limited requests to test recovery


class CircuitBreaker:
    """Circuit breaker to prevent cascading failures."""

    def __init__(self, config: RetryConfig, key: str = "default"):
        self.config = config
        self.key = key
        self.persistence = get_circuit_breaker_persistence()

        # Try to load persisted state
        persisted_state = self.persistence.get_state(key)
        if persisted_state:
            self.state = CircuitState(persisted_state.state)
            self.failure_count = persisted_state.failure_count
            self.success_count = persisted_state.success_count
            if persisted_state.last_failure_time:
                try:
                    self.last_failure_time = datetime.fromisoformat(persisted_state.last_failure_time)
                except (ValueError, TypeError):
                    self.last_failure_time = None
            else:
                self.last_failure_time = None
            logger.info(f"Loaded circuit breaker state for {key}: {self.state.value}")
        else:
            self.state = CircuitState.CLOSED
            self.failure_count = 0
            self.last_failure_time: Optional[datetime] = None
            self.success_count = 0

    def record_success(self) -> None:
        """Record a successful operation."""
        if self.state == CircuitState.HALF_OPEN:
            # Logic: transition from HALF_OPEN back to CLOSED after 2 consecutive successes
            self.success_count += 1
            if self.success_count >= 2:  # Need 2 successes to close
                logger.info("Circuit breaker closing after successful recovery")
                self.state = CircuitState.CLOSED
                self.failure_count = 0
                self.success_count = 0
        elif self.state == CircuitState.CLOSED:
            # Reset failure count on success
            if self.failure_count > 0:
                self.failure_count = max(0, self.failure_count - 1)

        # Save state to persistence
        self._save_state()

    def record_failure(self) -> None:
        """Record a failed operation."""
        self.failure_count += 1
        self.last_failure_time = datetime.now()
        self.success_count = 0

        if self.state == CircuitState.CLOSED:
            # Logic: trip circuit to OPEN when failure threshold is exceeded
            if self.failure_count >= self.config.circuit_breaker_threshold:
                logger.warning(f"Circuit breaker opening after {self.failure_count} failures")
                self.state = CircuitState.OPEN
        elif self.state == CircuitState.HALF_OPEN:
            # Failed while testing, go back to open
            logger.warning("Circuit breaker reopening after failure in half-open state")
            self.state = CircuitState.OPEN

        # Save state to persistence
        self._save_state()

    def should_attempt(self) -> bool:
        """Check if we should attempt the operation."""
        if not self.config.circuit_breaker_enabled:
            return True

        if self.state == CircuitState.CLOSED:
            return True

        if self.state == CircuitState.OPEN:
            # Critical state transition: OPEN to HALF_OPEN based on timeout to test recovery
            # Check if enough time has passed to try again
            if self.last_failure_time:
                elapsed = (datetime.now() - self.last_failure_time).total_seconds()
                if elapsed >= self.config.circuit_breaker_timeout:
                    logger.info("Circuit breaker entering half-open state")
                    self.state = CircuitState.HALF_OPEN
                    self._save_state()  # Save state transition
                    return True
            return False

        # HALF_OPEN - allow attempt
        return True

    def _save_state(self) -> None:
        """Save current state to persistence."""
        self.persistence.save_state(
            key=self.key,
            state=self.state.value,
            failure_count=self.failure_count,
            success_count=self.success_count,
            last_failure_time=self.last_failure_time,
        )

    def get_status(self) -> Dict[str, Any]:
        """Get circuit breaker status."""
        return {
            "state": self.state.value,
            "failure_count": self.failure_count,
            "success_count": self.success_count,
            "last_failure": (self.last_failure_time.isoformat() if self.last_failure_time else None),
        }


class RetryHandler:
    """Advanced retry handler with exponential backoff and circuit breaker."""

    def __init__(self, config: Optional[RetryConfig] = None):
        self.config = config or RetryConfig()
        self.circuit_breakers: Dict[str, CircuitBreaker] = {}

    def _get_circuit_breaker(self, key: str) -> CircuitBreaker:
        """Get or create circuit breaker for a key."""
        if key not in self.circuit_breakers:
            self.circuit_breakers[key] = CircuitBreaker(self.config, key)
        return self.circuit_breakers[key]

    def _calculate_delay(self, attempt: int, error_type: Optional[str] = None) -> float:
        """Calculate delay for next retry attempt."""
        # Get error-specific config if available
        config = self.config
        if error_type and error_type in config.error_configs:
            error_config = config.error_configs[error_type]
            initial_delay = error_config.get("initial_delay", config.initial_delay)
            exponential_base = error_config.get("exponential_base", config.exponential_base)
        else:
            initial_delay = config.initial_delay
            exponential_base = config.exponential_base

        # Calculate base delay based on strategy
        if config.strategy == RetryStrategy.EXPONENTIAL:
            # Exponential backoff: delay grows exponentially (1x, 2x, 4x, 8x, ...)
            delay = initial_delay * (exponential_base**attempt)
        elif config.strategy == RetryStrategy.LINEAR:
            # Linear backoff: delay grows linearly (1x, 2x, 3x, 4x, ...)
            delay = initial_delay * attempt
        elif config.strategy == RetryStrategy.FIBONACCI:
            # Fibonacci backoff: delay follows Fibonacci sequence for smoother progression
            # Fibonacci sequence: 1, 1, 2, 3, 5, 8, 13...
            fib = [1, 1]
            for _ in range(attempt):
                fib.append(fib[-1] + fib[-2])
            delay = initial_delay * fib[min(attempt, len(fib) - 1)]
        else:  # FIXED
            # Fixed backoff: consistent delay between all retry attempts
            delay = initial_delay

        # Cap at max delay
        delay = min(delay, config.max_delay)

        # Jitter application: add randomization (±25%) to prevent thundering herd
        if config.jitter:
            jitter_range = delay * 0.25
            delay += random.uniform(-jitter_range, jitter_range)

        return max(0.1, delay)  # Minimum 100ms

    def _classify_error(self, error: Exception) -> Optional[str]:
        """Classify error type for specific retry strategies."""
        error_msg = str(error).lower()

        if "rate limit" in error_msg or "429" in error_msg:
            return "rate_limit"
        elif isinstance(error, (ConnectionError, ConnectionRefusedError, ConnectionResetError)):
            return "connection"
        elif isinstance(error, (TimeoutError, asyncio.TimeoutError)):
            return "timeout"

        # Check Claude SDK errors
        try:
            from claude_code_sdk._errors import CLIConnectionError

            if isinstance(error, CLIConnectionError):
                return "connection"
        except ImportError:
            pass

        return None

    def should_retry(self, error: Exception, attempt: int) -> bool:
        """Determine if error should be retried."""
        from claude_cto.server.error_handler import ErrorHandler

        # Check if error is transient
        if not ErrorHandler.is_transient_error(error):
            return False

        # Check attempt limit
        error_type = self._classify_error(error)
        if error_type and error_type in self.config.error_configs:
            max_attempts = self.config.error_configs[error_type].get("max_attempts", self.config.max_attempts)
        else:
            max_attempts = self.config.max_attempts

        return attempt < max_attempts

    async def execute_with_retry(
        self,
        func: Callable[..., Coroutine[Any, Any, T]],
        *args,
        circuit_key: Optional[str] = None,
        on_retry: Optional[Callable[[Exception, int, float], None]] = None,
        **kwargs,
    ) -> T:
        """
        Execute async function with retry logic.

        Args:
            func: Async function to execute
            circuit_key: Key for circuit breaker (e.g., "task_123")
            on_retry: Callback for retry events
            *args, **kwargs: Arguments for func

        Returns:
            Result from successful execution

        Raises:
            Last exception if all retries exhausted
        """
        circuit_breaker = self._get_circuit_breaker(circuit_key or "default")
        last_error = None

        for attempt in range(self.config.max_attempts):
            # Initial circuit breaker check: prevent execution if circuit is open
            if not circuit_breaker.should_attempt():
                logger.warning(f"Circuit breaker open for {circuit_key}, skipping attempt")
                raise RuntimeError(f"Circuit breaker open for {circuit_key}")

            # try block: successful execution path with circuit breaker success recording
            try:
                # Execute function
                result = await func(*args, **kwargs)

                # Success - record and return
                circuit_breaker.record_success()
                if attempt > 0:
                    logger.info(f"Retry successful after {attempt + 1} attempts")
                return result

            # except block: failure path with delay calculation and retry decision
            except Exception as e:
                last_error = e
                circuit_breaker.record_failure()

                # Check if we should retry
                if not self.should_retry(e, attempt + 1):
                    logger.error(f"Error is not retryable: {e}")
                    raise

                if attempt + 1 >= self.config.max_attempts:
                    logger.error(f"Max retry attempts ({self.config.max_attempts}) exhausted")
                    raise

                # Calculate delay
                error_type = self._classify_error(e)
                delay = self._calculate_delay(attempt, error_type)

                # Log retry attempt
                logger.warning(
                    f"Attempt {attempt + 1}/{self.config.max_attempts} failed: {e}. " f"Retrying in {delay:.1f}s..."
                )

                # Call retry callback if provided
                if on_retry:
                    on_retry(e, attempt + 1, delay)

                # Wait before retry
                await asyncio.sleep(delay)

        # Should not reach here, but for safety
        raise last_error or RuntimeError("Retry failed with no error")

    def execute_with_retry_sync(
        self,
        func: Callable[..., T],
        *args,
        circuit_key: Optional[str] = None,
        on_retry: Optional[Callable[[Exception, int, float], None]] = None,
        **kwargs,
    ) -> T:
        """
        Execute sync function with retry logic.

        Similar to execute_with_retry but for synchronous functions.
        """
        circuit_breaker = self._get_circuit_breaker(circuit_key or "default")
        last_error = None

        for attempt in range(self.config.max_attempts):
            # Check circuit breaker
            if not circuit_breaker.should_attempt():
                logger.warning(f"Circuit breaker open for {circuit_key}, skipping attempt")
                raise RuntimeError(f"Circuit breaker open for {circuit_key}")

            try:
                # Execute function
                result = func(*args, **kwargs)

                # Success - record and return
                circuit_breaker.record_success()
                if attempt > 0:
                    logger.info(f"Retry successful after {attempt + 1} attempts")
                return result

            # except block: failure path with delay calculation and retry decision
            except Exception as e:
                last_error = e
                circuit_breaker.record_failure()

                # Check if we should retry
                if not self.should_retry(e, attempt + 1):
                    logger.error(f"Error is not retryable: {e}")
                    raise

                if attempt + 1 >= self.config.max_attempts:
                    logger.error(f"Max retry attempts ({self.config.max_attempts}) exhausted")
                    raise

                # Calculate delay
                error_type = self._classify_error(e)
                delay = self._calculate_delay(attempt, error_type)

                # Log retry attempt
                logger.warning(
                    f"Attempt {attempt + 1}/{self.config.max_attempts} failed: {e}. " f"Retrying in {delay:.1f}s..."
                )

                # Call retry callback if provided
                if on_retry:
                    on_retry(e, attempt + 1, delay)

                # Wait before retry
                time.sleep(delay)

        # Should not reach here, but for safety
        raise last_error or RuntimeError("Retry failed with no error")

    def get_status(self) -> Dict[str, Any]:
        """Get retry handler status including all circuit breakers."""
        return {
            "config": {
                "max_attempts": self.config.max_attempts,
                "strategy": self.config.strategy.value,
                "initial_delay": self.config.initial_delay,
                "max_delay": self.config.max_delay,
            },
            "circuit_breakers": {key: cb.get_status() for key, cb in self.circuit_breakers.items()},
        }


# Global retry handler instance
_retry_handler = RetryHandler()


def get_retry_handler() -> RetryHandler:
    """Get the global retry handler instance."""
    return _retry_handler


def configure_retry_handler(config: RetryConfig) -> None:
    """Configure the global retry handler."""
    global _retry_handler
    _retry_handler = RetryHandler(config)
