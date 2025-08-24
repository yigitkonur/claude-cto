"""
SOLE RESPONSIBILITY: Persist and restore circuit breaker state across server restarts.
Uses JSON file storage for simplicity and portability.
"""

import json
import logging
from pathlib import Path
from datetime import datetime
from typing import Dict, Optional
from dataclasses import dataclass, asdict

logger = logging.getLogger(__name__)


@dataclass
class CircuitBreakerState:
    """Persistent state for a circuit breaker."""

    key: str
    state: str  # "closed", "open", "half_open"
    failure_count: int
    success_count: int
    last_failure_time: Optional[str] = None  # ISO format
    last_updated: Optional[str] = None  # ISO format

    def to_dict(self) -> dict:
        """Convert to dictionary for JSON serialization."""
        data = asdict(self)
        data["last_updated"] = datetime.now().isoformat()
        return data

    @classmethod
    def from_dict(cls, data: dict) -> "CircuitBreakerState":
        """Create from dictionary."""
        return cls(**data)


class CircuitBreakerPersistence:
    """Manages persistent storage of circuit breaker states.

    🔴 CRITICAL: The cleanup_old_states() method MUST be called periodically
    to prevent unbounded disk space growth. Without cleanup, circuit breaker
    states will accumulate indefinitely leading to disk space exhaustion.
    """

    def __init__(self, storage_path: Optional[Path] = None):
        """
        Initialize persistence manager.

        ⚠️ CRITICAL: After initialization, ensure that:
        1. cleanup_old_states() is called periodically (e.g., hourly)
        2. This is handled by _periodic_circuit_breaker_cleanup() in server/main.py
        3. Without cleanup, disk space will grow unbounded

        Args:
            storage_path: Path to store circuit breaker state file
        """
        if storage_path is None:
            storage_path = Path.home() / ".claude-cto" / "circuit_breakers.json"

        self.storage_path = storage_path
        self.storage_path.parent.mkdir(parents=True, exist_ok=True)

        # Load existing state on initialization
        self.states: Dict[str, CircuitBreakerState] = self._load_states()

    def _load_states(self) -> Dict[str, CircuitBreakerState]:
        """Load circuit breaker states from disk."""
        if not self.storage_path.exists():
            return {}

        try:
            with open(self.storage_path, "r") as f:
                data = json.load(f)

            states = {}
            for key, state_data in data.items():
                try:
                    states[key] = CircuitBreakerState.from_dict(state_data)
                except Exception as e:
                    logger.warning(f"Failed to load circuit breaker state for {key}: {e}")

            logger.info(f"Loaded {len(states)} circuit breaker states from disk")
            return states

        except Exception as e:
            logger.error(f"Failed to load circuit breaker states: {e}")
            return {}

    def _save_states(self) -> None:
        """Save circuit breaker states to disk."""
        try:
            data = {key: state.to_dict() for key, state in self.states.items()}

            # Write to temp file first for atomicity
            temp_path = self.storage_path.with_suffix(".tmp")
            with open(temp_path, "w") as f:
                json.dump(data, f, indent=2, default=str)

            # Atomic rename
            temp_path.replace(self.storage_path)

            logger.debug(f"Saved {len(data)} circuit breaker states to disk")

        except Exception as e:
            logger.error(f"Failed to save circuit breaker states: {e}")

    def save_state(
        self,
        key: str,
        state: str,
        failure_count: int,
        success_count: int,
        last_failure_time: Optional[datetime] = None,
    ) -> None:
        """
        Save the state of a circuit breaker.

        Args:
            key: Circuit breaker identifier
            state: Current state (closed/open/half_open)
            failure_count: Number of failures
            success_count: Number of successes
            last_failure_time: Time of last failure
        """
        cb_state = CircuitBreakerState(
            key=key,
            state=state,
            failure_count=failure_count,
            success_count=success_count,
            last_failure_time=(last_failure_time.isoformat() if last_failure_time else None),
        )

        self.states[key] = cb_state
        self._save_states()

    def get_state(self, key: str) -> Optional[CircuitBreakerState]:
        """
        Get the persisted state of a circuit breaker.

        Args:
            key: Circuit breaker identifier

        Returns:
            CircuitBreakerState if found, None otherwise
        """
        return self.states.get(key)

    def remove_state(self, key: str) -> None:
        """
        Remove a circuit breaker state.

        Args:
            key: Circuit breaker identifier
        """
        if key in self.states:
            del self.states[key]
            self._save_states()

    def cleanup_old_states(self, max_age_days: int = 7) -> int:
        """
        Remove circuit breaker states older than specified days.

        Args:
            max_age_days: Maximum age in days

        Returns:
            Number of states removed
        """
        from datetime import timedelta

        cutoff = datetime.now() - timedelta(days=max_age_days)
        removed = 0

        keys_to_remove = []
        for key, state in self.states.items():
            if state.last_updated:
                try:
                    last_updated = datetime.fromisoformat(state.last_updated)
                    if last_updated < cutoff:
                        keys_to_remove.append(key)
                except (ValueError, TypeError, KeyError):
                    pass

        for key in keys_to_remove:
            del self.states[key]
            removed += 1

        if removed > 0:
            self._save_states()
            logger.info(f"Cleaned up {removed} old circuit breaker states")

        return removed

    def get_all_states(self) -> Dict[str, dict]:
        """
        Get all circuit breaker states as a dictionary.

        Returns:
            Dictionary of all states
        """
        return {key: state.to_dict() for key, state in self.states.items()}

    def reset_all(self) -> None:
        """Reset all circuit breaker states."""
        self.states.clear()
        self._save_states()
        logger.info("Reset all circuit breaker states")


# Global persistence instance
_persistence = None


def get_circuit_breaker_persistence() -> CircuitBreakerPersistence:
    """Get the global circuit breaker persistence instance."""
    global _persistence
    if _persistence is None:
        _persistence = CircuitBreakerPersistence()
    return _persistence
