"""
Database fixtures and utilities for testing.
"""

import tempfile
from pathlib import Path
from sqlmodel import SQLModel, create_engine, Session
from typing import Generator

from claude_cto.server.models import TaskDB, OrchestrationDB


class MockDatabase:
    """Mock database for testing with in-memory SQLite."""
    
    def __init__(self):
        self.engine = create_engine("sqlite:///:memory:", echo=False)
        SQLModel.metadata.create_all(self.engine)
    
    def get_session(self) -> Session:
        """Get a database session."""
        return Session(self.engine)
    
    def create_tables(self):
        """Create all database tables."""
        SQLModel.metadata.create_all(self.engine)
    
    def drop_tables(self):
        """Drop all database tables."""
        SQLModel.metadata.drop_all(self.engine)
    
    def reset(self):
        """Reset the database by dropping and recreating tables."""
        self.drop_tables()
        self.create_tables()


class TestDataManager:
    """Manages test data creation and cleanup."""
    
    def __init__(self, session: Session):
        self.session = session
        self._created_tasks = []
        self._created_orchestrations = []
    
    def create_task(self, **kwargs) -> TaskDB:
        """Create a test task with default values."""
        defaults = {
            "working_directory": "/test/project",
            "system_prompt": "Test system prompt",
            "execution_prompt": "Test execution prompt",
            "model": "sonnet"
        }
        defaults.update(kwargs)
        
        task = TaskDB(**defaults)
        self.session.add(task)
        self.session.commit()
        self.session.refresh(task)
        
        self._created_tasks.append(task.id)
        return task
    
    def create_orchestration(self, **kwargs) -> OrchestrationDB:
        """Create a test orchestration with default values."""
        defaults = {
            "status": "pending",
            "total_tasks": 1
        }
        defaults.update(kwargs)
        
        orchestration = OrchestrationDB(**defaults)
        self.session.add(orchestration)
        self.session.commit()
        self.session.refresh(orchestration)
        
        self._created_orchestrations.append(orchestration.id)
        return orchestration
    
    def cleanup(self):
        """Clean up all created test data."""
        # Delete tasks
        for task_id in self._created_tasks:
            task = self.session.get(TaskDB, task_id)
            if task:
                self.session.delete(task)
        
        # Delete orchestrations
        for orch_id in self._created_orchestrations:
            orch = self.session.get(OrchestrationDB, orch_id)
            if orch:
                self.session.delete(orch)
        
        self.session.commit()
        self._created_tasks.clear()
        self._created_orchestrations.clear()


class TransactionalTest:
    """Context manager for transactional tests with automatic rollback."""
    
    def __init__(self, session: Session):
        self.session = session
        self.transaction = None
    
    def __enter__(self):
        self.transaction = self.session.begin()
        return self.session
    
    def __exit__(self, exc_type, exc_val, exc_tb):
        if self.transaction:
            self.transaction.rollback()


def create_temp_db_file() -> Path:
    """Create a temporary database file for testing."""
    temp_file = tempfile.NamedTemporaryFile(suffix='.db', delete=False)
    temp_file.close()
    return Path(temp_file.name)


def create_test_log_directory() -> Path:
    """Create a temporary log directory for testing."""
    temp_dir = Path(tempfile.mkdtemp(prefix="claude_cto_test_logs_"))
    return temp_dir