"""
Global pytest configuration and fixtures for Claude CTO testing.
"""

import asyncio
import json
import os
import tempfile
import pytest
from datetime import datetime
from pathlib import Path
from typing import Optional, Generator, List, Dict, Any
from unittest.mock import Mock, AsyncMock, MagicMock, patch
from sqlmodel import Session, SQLModel, create_engine, select

# Add the project root to sys.path for imports
import sys
project_root = Path(__file__).parent.parent
sys.path.insert(0, str(project_root))

from claude_cto.server.models import TaskDB, OrchestrationDB, TaskStatus, ClaudeModel


# Test configuration
TEST_DB_URL = "sqlite:///:memory:"
TEST_LOG_DIR = Path(tempfile.gettempdir()) / "claude-cto-tests"


@pytest.fixture(scope="session")
def event_loop():
    """Create an instance of the default event loop for the test session."""
    loop = asyncio.get_event_loop_policy().new_event_loop()
    yield loop
    loop.close()


@pytest.fixture(scope="function")
def test_engine():
    """Create a test database engine with in-memory SQLite."""
    engine = create_engine(TEST_DB_URL, echo=False)
    SQLModel.metadata.create_all(engine)
    yield engine
    engine.dispose()


@pytest.fixture(scope="function")
def test_session(test_engine):
    """Create a test database session with automatic rollback."""
    with Session(test_engine) as session:
        yield session


@pytest.fixture(scope="function")
def mock_session():
    """Create a mock database session for unit tests."""
    session = Mock(spec=Session)
    session.add = Mock()
    session.commit = Mock()
    session.refresh = Mock()
    session.exec = Mock()
    session.get = Mock()
    session.merge = Mock()
    session.delete = Mock()
    return session


@pytest.fixture(scope="function")
def test_log_dir():
    """Create a temporary directory for test logs."""
    log_dir = TEST_LOG_DIR / f"test_{datetime.utcnow().strftime('%Y%m%d_%H%M%S_%f')}"
    log_dir.mkdir(parents=True, exist_ok=True)
    yield log_dir
    # Cleanup
    import shutil
    if log_dir.exists():
        shutil.rmtree(log_dir, ignore_errors=True)


@pytest.fixture(scope="function")
def sample_task_data():
    """Sample task data for testing."""
    return {
        "execution_prompt": "Analyze the codebase in /test/project and create a comprehensive test suite",
        "working_directory": "/test/project",
        "system_prompt": "You are John Carmack, a legendary programmer known for clean, efficient code.",
        "model": ClaudeModel.SONNET
    }


@pytest.fixture(scope="function")
def sample_task_db(test_session, sample_task_data):
    """Create a sample TaskDB instance in the test database."""
    task = TaskDB(
        id=1,
        status=TaskStatus.PENDING,
        **sample_task_data,
        created_at=datetime.utcnow()
    )
    test_session.add(task)
    test_session.commit()
    test_session.refresh(task)
    return task


@pytest.fixture(scope="function")
def sample_orchestration_db(test_session):
    """Create a sample OrchestrationDB instance."""
    orchestration = OrchestrationDB(
        id=1,
        status="pending",
        total_tasks=3,
        created_at=datetime.utcnow()
    )
    test_session.add(orchestration)
    test_session.commit()
    test_session.refresh(orchestration)
    return orchestration


@pytest.fixture(scope="function")
def mock_claude_sdk():
    """Mock the Claude Code SDK with realistic responses."""
    mock_sdk = Mock()
    
    # Mock successful query response
    mock_response = AsyncMock()
    mock_response.messages = [
        {"type": "assistant", "content": "Task completed successfully"},
        {"type": "tool_use", "name": "bash", "input": {"command": "ls -la"}},
        {"type": "tool_result", "output": "total 0\ndrwxr-xr-x  2 user  staff   64 Jan  1 10:00 ."}
    ]
    mock_response.final_summary = "Successfully analyzed the project structure"
    
    mock_sdk.query = AsyncMock(return_value=mock_response)
    return mock_sdk


@pytest.fixture(scope="function")
def mock_claude_sdk_errors():
    """Mock Claude SDK with various error types for testing."""
    from claude_code_sdk._errors import (
        CLINotFoundError, CLIConnectionError, ProcessError, 
        CLIJSONDecodeError, MessageParseError
    )
    
    return {
        "cli_not_found": CLINotFoundError("Claude CLI not found in PATH"),
        "connection_error": CLIConnectionError("Failed to connect to Claude CLI"),
        "process_error": ProcessError("Command failed", exit_code=127, stderr="command not found"),
        "json_decode_error": CLIJSONDecodeError("Invalid JSON response", ValueError("Invalid JSON")),
        "message_parse_error": MessageParseError("Failed to parse message")
    }


@pytest.fixture(scope="function")
def mock_file_system():
    """Mock file system operations for testing."""
    with patch('pathlib.Path.exists', return_value=True), \
         patch('pathlib.Path.mkdir'), \
         patch('pathlib.Path.write_text'), \
         patch('pathlib.Path.read_text', return_value="mock file content"):
        yield


@pytest.fixture(scope="function")
def orchestration_sample_data():
    """Sample orchestration data for testing."""
    return {
        "tasks": [
            {
                "identifier": "setup",
                "execution_prompt": "Initialize the development environment",
                "working_directory": "/project",
                "system_prompt": "You are John Carmack, focused on clean setup",
                "model": "sonnet"
            },
            {
                "identifier": "test",
                "execution_prompt": "Run the test suite",
                "working_directory": "/project",
                "depends_on": ["setup"],
                "initial_delay": 2.0
            },
            {
                "identifier": "deploy",
                "execution_prompt": "Deploy the application",
                "working_directory": "/project",
                "depends_on": ["test"],
                "initial_delay": 1.0
            }
        ]
    }


@pytest.fixture(scope="function")
def mock_httpx_client():
    """Mock httpx client for testing REST API calls."""
    client = Mock()
    
    # Mock successful responses
    mock_response = Mock()
    mock_response.status_code = 200
    mock_response.json.return_value = {"status": "success", "data": {}}
    mock_response.raise_for_status = Mock()
    
    client.post = Mock(return_value=mock_response)
    client.get = Mock(return_value=mock_response)
    client.put = Mock(return_value=mock_response)
    client.delete = Mock(return_value=mock_response)
    
    return client


@pytest.fixture(scope="function")
def mock_environment():
    """Mock environment variables for testing."""
    env_vars = {
        "ANTHROPIC_API_KEY": "sk-ant-test-key-123",
        "CLAUDE_CTO_SERVER_URL": "http://localhost:8000",
        "CLAUDE_CTO_DB": ":memory:",
        "CLAUDE_CTO_LOG_DIR": str(TEST_LOG_DIR)
    }
    
    with patch.dict(os.environ, env_vars):
        yield env_vars


@pytest.fixture(scope="function")
def mock_task_logger():
    """Mock task logger for testing."""
    logger = Mock()
    logger.log_task_start = Mock()
    logger.log_task_progress = Mock()
    logger.log_task_completion = Mock()
    logger.log_error = Mock()
    logger.get_log_path = Mock(return_value="/tmp/test.log")
    return logger


@pytest.fixture(scope="function")
def mock_notification_system():
    """Mock notification system for testing."""
    with patch('claude_cto.server.notification.notify_task_started') as mock_start, \
         patch('claude_cto.server.notification.notify_task_completed') as mock_complete:
        yield {
            "start": mock_start,
            "complete": mock_complete
        }


@pytest.fixture(scope="function") 
def sample_error_scenarios():
    """Sample error scenarios for testing error handling."""
    return {
        "transient_errors": [
            "Connection timed out",
            "Rate limit exceeded", 
            "Server temporarily unavailable",
            "Error 429: Too many requests",
            "Network error occurred"
        ],
        "permanent_errors": [
            "Invalid API key",
            "Authentication failed",
            "Permission denied",
            "File not found",
            "Invalid JSON syntax"
        ],
        "recoverable_errors": [
            "Disk space temporarily full",
            "Memory limit exceeded",
            "Process interrupted"
        ]
    }


@pytest.fixture(scope="function")
def mock_asyncio_events():
    """Mock asyncio events for testing orchestration."""
    events = {}
    
    def create_event():
        event = asyncio.Event()
        return event
    
    events["task_completed"] = create_event()
    events["task_failed"] = create_event()
    events["dependency_ready"] = create_event()
    
    return events


@pytest.fixture(scope="function")
def performance_metrics():
    """Performance metrics tracking for load testing."""
    metrics = {
        "start_time": datetime.utcnow(),
        "request_count": 0,
        "error_count": 0,
        "response_times": [],
        "memory_usage": [],
        "cpu_usage": []
    }
    
    def add_request(response_time: float, success: bool = True):
        metrics["request_count"] += 1
        metrics["response_times"].append(response_time)
        if not success:
            metrics["error_count"] += 1
    
    metrics["add_request"] = add_request
    return metrics


@pytest.fixture(scope="function")
def mock_server_lifecycle():
    """Mock server lifecycle management for testing."""
    server_state = {"running": False, "port": 8000}
    
    def start_server():
        server_state["running"] = True
        return True
    
    def stop_server():
        server_state["running"] = False
        return True
    
    def is_running():
        return server_state["running"]
    
    return {
        "start": start_server,
        "stop": stop_server,
        "is_running": is_running,
        "state": server_state
    }


# Utility functions for tests
def create_test_tasks(session: Session, count: int = 3) -> List[TaskDB]:
    """Create multiple test tasks in the database."""
    tasks = []
    for i in range(count):
        task = TaskDB(
            status=TaskStatus.PENDING,
            working_directory=f"/test/project{i}",
            system_prompt="Test system prompt",
            execution_prompt=f"Test task {i}",
            model=ClaudeModel.SONNET,
            created_at=datetime.utcnow()
        )
        session.add(task)
        tasks.append(task)
    
    session.commit()
    for task in tasks:
        session.refresh(task)
    
    return tasks


def create_orchestration_with_tasks(
    session: Session, 
    task_count: int = 3,
    with_dependencies: bool = True
) -> tuple[OrchestrationDB, List[TaskDB]]:
    """Create an orchestration with associated tasks."""
    # Create orchestration
    orchestration = OrchestrationDB(
        status="pending",
        total_tasks=task_count,
        created_at=datetime.utcnow()
    )
    session.add(orchestration)
    session.commit()
    session.refresh(orchestration)
    
    # Create tasks
    tasks = []
    for i in range(task_count):
        depends_on = None
        if with_dependencies and i > 0:
            depends_on = json.dumps([f"task{j}" for j in range(i)])
        
        task = TaskDB(
            status=TaskStatus.WAITING if depends_on else TaskStatus.PENDING,
            working_directory=f"/test/project{i}",
            system_prompt="Test system prompt",
            execution_prompt=f"Test task {i}",
            model=ClaudeModel.SONNET,
            orchestration_id=orchestration.id,
            identifier=f"task{i}",
            depends_on=depends_on,
            created_at=datetime.utcnow()
        )
        session.add(task)
        tasks.append(task)
    
    session.commit()
    for task in tasks:
        session.refresh(task)
    
    return orchestration, tasks


# Custom assertions for testing
def assert_task_status(task: TaskDB, expected_status: TaskStatus):
    """Assert task has expected status."""
    assert task.status == expected_status, f"Expected {expected_status}, got {task.status}"


def assert_task_completed_successfully(task: TaskDB):
    """Assert task completed successfully."""
    assert task.status == TaskStatus.COMPLETED
    assert task.ended_at is not None
    assert task.started_at is not None
    assert task.error_message is None


def assert_orchestration_completed(orchestration: OrchestrationDB):
    """Assert orchestration completed successfully."""
    assert orchestration.status in ["completed", "failed"]
    assert orchestration.ended_at is not None
    assert orchestration.completed_tasks + orchestration.failed_tasks + orchestration.skipped_tasks == orchestration.total_tasks


# Test data generators
def generate_large_orchestration(task_count: int = 50) -> Dict[str, Any]:
    """Generate a large orchestration for load testing."""
    tasks = []
    for i in range(task_count):
        depends_on = []
        if i > 0:
            # Create some dependencies
            depends_on = [f"task{j}" for j in range(max(0, i-3), i)]
        
        task = {
            "identifier": f"task{i}",
            "execution_prompt": f"Execute task {i} in the workflow",
            "working_directory": f"/project/module{i % 10}",
            "depends_on": depends_on if depends_on else None,
            "initial_delay": 0.1 if i % 5 == 0 else None
        }
        tasks.append(task)
    
    return {"tasks": tasks}


def generate_complex_dag() -> Dict[str, Any]:
    """Generate a complex DAG for testing."""
    return {
        "tasks": [
            {"identifier": "init", "execution_prompt": "Initialize", "working_directory": "/project"},
            {"identifier": "build_a", "execution_prompt": "Build A", "working_directory": "/project", "depends_on": ["init"]},
            {"identifier": "build_b", "execution_prompt": "Build B", "working_directory": "/project", "depends_on": ["init"]},
            {"identifier": "test_a", "execution_prompt": "Test A", "working_directory": "/project", "depends_on": ["build_a"]},
            {"identifier": "test_b", "execution_prompt": "Test B", "working_directory": "/project", "depends_on": ["build_b"]},
            {"identifier": "integration", "execution_prompt": "Integration test", "working_directory": "/project", "depends_on": ["test_a", "test_b"]},
            {"identifier": "deploy", "execution_prompt": "Deploy", "working_directory": "/project", "depends_on": ["integration"], "initial_delay": 5.0}
        ]
    }