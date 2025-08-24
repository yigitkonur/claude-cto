"""
Mock objects and factories for testing.
"""

import asyncio
import json
from datetime import datetime
from typing import Dict, List, Any, Optional, Union
from unittest.mock import Mock, AsyncMock, MagicMock

from claude_code_sdk._errors import (
    ClaudeSDKError, ProcessError, CLINotFoundError, 
    CLIConnectionError, CLIJSONDecodeError, MessageParseError
)


class MockClaudeSDK:
    """Mock Claude Code SDK for testing."""
    
    def __init__(self):
        self.query_calls = []
        self.responses = []
        self.current_response_index = 0
        self.should_raise = None
        
    def set_response(self, response: Dict[str, Any]):
        """Set a single response for the next query call."""
        self.responses = [response]
        self.current_response_index = 0
    
    def set_responses(self, responses: List[Dict[str, Any]]):
        """Set multiple responses for sequential query calls."""
        self.responses = responses
        self.current_response_index = 0
    
    def set_error(self, error: Exception):
        """Set an error to be raised on the next query call."""
        self.should_raise = error
    
    async def query(self, **kwargs) -> Mock:
        """Mock query method that returns configured responses or raises errors."""
        self.query_calls.append(kwargs)
        
        if self.should_raise:
            error = self.should_raise
            self.should_raise = None
            raise error
        
        if self.current_response_index < len(self.responses):
            response_data = self.responses[self.current_response_index]
            self.current_response_index += 1
        else:
            # Default response
            response_data = {
                "messages": [{"type": "assistant", "content": "Mock response"}],
                "final_summary": "Mock task completed successfully"
            }
        
        # Create mock response object
        response = Mock()
        response.messages = response_data.get("messages", [])
        response.final_summary = response_data.get("final_summary", "")
        
        return response
    
    def reset(self):
        """Reset the mock to initial state."""
        self.query_calls.clear()
        self.responses.clear()
        self.current_response_index = 0
        self.should_raise = None


class MockTaskLogger:
    """Mock task logger for testing."""
    
    def __init__(self, log_path: str = "/tmp/test.log"):
        self.log_path = log_path
        self.logged_events = []
        
    def log_task_start(self, task_id: int, **kwargs):
        """Mock log task start."""
        self.logged_events.append({
            "type": "start",
            "task_id": task_id,
            "timestamp": datetime.utcnow(),
            **kwargs
        })
    
    def log_task_progress(self, task_id: int, message: str, **kwargs):
        """Mock log task progress."""
        self.logged_events.append({
            "type": "progress", 
            "task_id": task_id,
            "message": message,
            "timestamp": datetime.utcnow(),
            **kwargs
        })
    
    def log_task_completion(self, task_id: int, success: bool, **kwargs):
        """Mock log task completion."""
        self.logged_events.append({
            "type": "completion",
            "task_id": task_id,
            "success": success,
            "timestamp": datetime.utcnow(),
            **kwargs
        })
    
    def log_error(self, task_id: int, error: str, **kwargs):
        """Mock log error."""
        self.logged_events.append({
            "type": "error",
            "task_id": task_id,
            "error": error,
            "timestamp": datetime.utcnow(),
            **kwargs
        })
    
    def get_log_path(self) -> str:
        """Return the log path."""
        return self.log_path
    
    def get_events(self, event_type: Optional[str] = None) -> List[Dict[str, Any]]:
        """Get logged events, optionally filtered by type."""
        if event_type:
            return [e for e in self.logged_events if e["type"] == event_type]
        return self.logged_events.copy()


class MockHTTPClient:
    """Mock HTTP client for testing REST API calls."""
    
    def __init__(self):
        self.requests = []
        self.responses = {}
        self.default_response = {
            "status_code": 200,
            "json_data": {"status": "success"},
            "raise_for_status": None
        }
    
    def set_response(self, method: str, url: str, response_data: Dict[str, Any]):
        """Set response for specific method and URL."""
        key = f"{method.upper()}:{url}"
        self.responses[key] = response_data
    
    def _create_response(self, response_data: Dict[str, Any]) -> Mock:
        """Create a mock response object."""
        response = Mock()
        response.status_code = response_data.get("status_code", 200)
        response.json = Mock(return_value=response_data.get("json_data", {}))
        
        if response_data.get("raise_for_status"):
            response.raise_for_status = Mock(side_effect=response_data["raise_for_status"])
        else:
            response.raise_for_status = Mock()
        
        return response
    
    def post(self, url: str, **kwargs) -> Mock:
        """Mock POST request."""
        self.requests.append({"method": "POST", "url": url, "kwargs": kwargs})
        key = f"POST:{url}"
        response_data = self.responses.get(key, self.default_response)
        return self._create_response(response_data)
    
    def get(self, url: str, **kwargs) -> Mock:
        """Mock GET request."""
        self.requests.append({"method": "GET", "url": url, "kwargs": kwargs})
        key = f"GET:{url}"
        response_data = self.responses.get(key, self.default_response)
        return self._create_response(response_data)
    
    def put(self, url: str, **kwargs) -> Mock:
        """Mock PUT request."""
        self.requests.append({"method": "PUT", "url": url, "kwargs": kwargs})
        key = f"PUT:{url}"
        response_data = self.responses.get(key, self.default_response)
        return self._create_response(response_data)
    
    def delete(self, url: str, **kwargs) -> Mock:
        """Mock DELETE request."""
        self.requests.append({"method": "DELETE", "url": url, "kwargs": kwargs})
        key = f"DELETE:{url}"
        response_data = self.responses.get(key, self.default_response)
        return self._create_response(response_data)


class MockNotificationSystem:
    """Mock notification system for testing."""
    
    def __init__(self):
        self.notifications = []
    
    def notify_task_started(self, task_id: int, **kwargs):
        """Mock task started notification."""
        self.notifications.append({
            "type": "task_started",
            "task_id": task_id,
            "timestamp": datetime.utcnow(),
            **kwargs
        })
    
    def notify_task_completed(self, task_id: int, success: bool, **kwargs):
        """Mock task completed notification."""
        self.notifications.append({
            "type": "task_completed",
            "task_id": task_id,
            "success": success,
            "timestamp": datetime.utcnow(),
            **kwargs
        })
    
    def play_sound(self, sound_type: str):
        """Mock sound notification."""
        self.notifications.append({
            "type": "sound",
            "sound_type": sound_type,
            "timestamp": datetime.utcnow()
        })


class MockMemoryMonitor:
    """Mock memory monitor for testing."""
    
    def __init__(self):
        self.monitoring = False
        self.metrics = []
    
    def start_monitoring(self):
        """Start monitoring."""
        self.monitoring = True
    
    def stop_monitoring(self):
        """Stop monitoring."""
        self.monitoring = False
    
    def get_current_usage(self) -> Dict[str, float]:
        """Get current resource usage."""
        return {
            "memory_mb": 512.0,
            "cpu_percent": 25.0,
            "disk_usage_percent": 60.0
        }
    
    def get_metrics_history(self) -> List[Dict[str, Any]]:
        """Get metrics history."""
        return self.metrics.copy()


class ErrorScenarioMock:
    """Mock for testing different error scenarios."""
    
    @staticmethod
    def create_transient_errors() -> List[Exception]:
        """Create a list of transient errors for testing."""
        return [
            CLIConnectionError("Connection timed out"),
            ConnectionError("Network unreachable"),
            TimeoutError("Operation timed out"),
            Exception("Rate limit exceeded"),
            Exception("Error 429: Too many requests"),
            ProcessError("Temporary failure", exit_code=1, stderr="retry later")
        ]
    
    @staticmethod
    def create_permanent_errors() -> List[Exception]:
        """Create a list of permanent errors for testing."""
        return [
            CLINotFoundError("Claude CLI not found"),
            ProcessError("Authentication failed", exit_code=1, stderr="unauthorized"),
            CLIJSONDecodeError("Invalid JSON", ValueError("Bad JSON")),
            MessageParseError("Parse error"),
            ValueError("Invalid input"),
            PermissionError("Access denied")
        ]
    
    @staticmethod
    def create_process_errors() -> List[ProcessError]:
        """Create ProcessError instances with various exit codes."""
        return [
            ProcessError("General error", exit_code=1, stderr="general failure"),
            ProcessError("Command not found", exit_code=127, stderr="claude: command not found"),
            ProcessError("Permission denied", exit_code=126, stderr="permission denied"),
            ProcessError("Interrupted", exit_code=130, stderr="interrupted by signal"),
            ProcessError("Out of range", exit_code=255, stderr="exit code out of range")
        ]


class MockOrchestrator:
    """Mock orchestrator for testing dependency resolution."""
    
    def __init__(self):
        self.orchestration_id = None
        self.task_map = {}
        self.dependency_graph = {}
        self.task_events = {}
        self.task_statuses = {}
        self.executed_tasks = []
    
    def set_orchestration(self, orchestration_id: int, tasks: List[Dict[str, Any]]):
        """Set up an orchestration for testing."""
        self.orchestration_id = orchestration_id
        self.task_map = {task["identifier"]: task["id"] for task in tasks}
        
        # Build dependency graph
        for task in tasks:
            identifier = task["identifier"]
            depends_on = task.get("depends_on", [])
            self.dependency_graph[identifier] = depends_on
            self.task_events[identifier] = asyncio.Event()
            self.task_statuses[identifier] = "waiting"
    
    async def mark_task_completed(self, identifier: str):
        """Mark a task as completed."""
        self.task_statuses[identifier] = "completed"
        self.task_events[identifier].set()
        self.executed_tasks.append(identifier)
    
    async def mark_task_failed(self, identifier: str):
        """Mark a task as failed."""
        self.task_statuses[identifier] = "failed"
        self.task_events[identifier].set()
    
    def get_ready_tasks(self) -> List[str]:
        """Get tasks that are ready to execute."""
        ready = []
        for identifier, dependencies in self.dependency_graph.items():
            if self.task_statuses[identifier] == "waiting":
                if all(self.task_statuses.get(dep) == "completed" for dep in dependencies):
                    ready.append(identifier)
        return ready


class MockRetryHandler:
    """Mock retry handler for testing retry logic."""
    
    def __init__(self):
        self.retry_attempts = []
        self.circuit_breaker_state = "closed"  # closed, open, half_open
        self.failure_count = 0
    
    async def execute_with_retry(self, func, *args, **kwargs):
        """Mock retry execution."""
        max_retries = kwargs.get("max_retries", 3)
        
        for attempt in range(max_retries + 1):
            try:
                self.retry_attempts.append({
                    "attempt": attempt,
                    "timestamp": datetime.utcnow()
                })
                
                if self.circuit_breaker_state == "open":
                    raise Exception("Circuit breaker is open")
                
                result = await func(*args, **kwargs)
                self.failure_count = 0
                return result
                
            except Exception as e:
                self.failure_count += 1
                if self.failure_count >= 5:
                    self.circuit_breaker_state = "open"
                
                if attempt == max_retries:
                    raise
                
                # Exponential backoff delay
                delay = 2 ** attempt
                await asyncio.sleep(0.01)  # Short delay for testing
    
    def reset_circuit_breaker(self):
        """Reset the circuit breaker."""
        self.circuit_breaker_state = "closed"
        self.failure_count = 0