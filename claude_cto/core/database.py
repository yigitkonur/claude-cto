"""
Shared database functionality for claude-cto.
Used by both REST API server and standalone MCP server.
"""

import os
from pathlib import Path
from typing import Optional
from datetime import datetime

from sqlmodel import SQLModel, Session, create_engine, select

from claude_cto.server.models import TaskDB, TaskCreate, TaskStatus


def get_database_url(db_path: Optional[str] = None) -> str:
    """
    Get database URL, with priority:
    1. Provided db_path
    2. CLAUDE_CTO_DB environment variable
    3. Default location
    """
    if db_path:
        return f"sqlite:///{db_path}"

    env_db = os.getenv("CLAUDE_CTO_DB")
    if env_db:
        return f"sqlite:///{env_db}"

    # Default location
    default_dir = Path.home() / ".claude-cto"
    default_dir.mkdir(parents=True, exist_ok=True)
    default_db = default_dir / "tasks.db"
    return f"sqlite:///{default_db}"


def create_engine_for_db(db_url: str):
    """Create SQLAlchemy engine for database."""
    return create_engine(
        db_url, echo=False, connect_args={"check_same_thread": False}  # SQLite specific
    )


def create_session_maker(engine):
    """Create session maker for database operations."""
    # Return a lambda that creates SQLModel sessions
    return lambda: Session(engine)


def init_database(db_path: Optional[str] = None):
    """Initialize database with tables."""
    db_url = get_database_url(db_path)
    engine = create_engine_for_db(db_url)
    SQLModel.metadata.create_all(engine)
    return engine


def get_task_by_id(session: Session, task_id: int) -> Optional[TaskDB]:
    """Get task by ID from database."""
    statement = select(TaskDB).where(TaskDB.id == task_id)
    return session.exec(statement).first()


def create_task_record(
    session: Session, task_data: TaskCreate, log_file_path: Optional[Path] = None
) -> TaskDB:
    """Create a new task record in database."""
    db_task = TaskDB(
        execution_prompt=task_data.execution_prompt,
        working_directory=task_data.working_directory or ".",
        system_prompt=task_data.system_prompt or "You are a helpful assistant.",
        status=TaskStatus.PENDING,
        log_file_path=str(log_file_path) if log_file_path else None,
        created_at=datetime.utcnow(),
    )
    session.add(db_task)
    session.commit()
    session.refresh(db_task)
    return db_task


def update_task_status(
    session: Session, task_id: int, status: TaskStatus, **kwargs
) -> Optional[TaskDB]:
    """Update task status and optional fields."""
    task = get_task_by_id(session, task_id)
    if not task:
        return None

    task.status = status

    # Update optional fields if provided
    for key, value in kwargs.items():
        if hasattr(task, key):
            setattr(task, key, value)

    session.add(task)
    session.commit()
    session.refresh(task)
    return task
