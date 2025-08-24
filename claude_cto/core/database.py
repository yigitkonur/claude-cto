"""
Shared database functionality for claude-cto.
Used by both REST API server and standalone MCP server.
"""

import os
import logging
from pathlib import Path
from typing import Optional
from datetime import datetime

from sqlmodel import SQLModel, Session, create_engine, select
from sqlalchemy.pool import NullPool

from claude_cto.server.models import TaskDB, TaskCreate, TaskStatus
from claude_cto.migrations.manager import run_migrations

logger = logging.getLogger(__name__)


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
    """Create SQLAlchemy engine for database.

    CRITICAL: Uses NullPool to avoid SQLite thread-safety issues.
    Each request gets a new connection - safer for concurrent access.
    """
    return create_engine(
        db_url,
        echo=False,
        poolclass=NullPool,  # CRITICAL: Use NullPool for SQLite thread safety
        connect_args={
            "check_same_thread": False,  # SQLite thread safety
            "timeout": 30,  # 30 second timeout for locks
            "isolation_level": None,  # Use SQLite's autocommit mode
        },
    )


def create_session_maker(engine):
    """Create session maker for database operations."""
    # Return a lambda that creates SQLModel sessions
    return lambda: Session(engine)


def init_database(db_path: Optional[str] = None):
    """Initialize database with tables and run migrations."""
    db_url = get_database_url(db_path)
    engine = create_engine_for_db(db_url)

    # Run migrations to ensure schema is up to date
    try:
        run_migrations(db_url)
        logger.info("Database migrations completed successfully")
    except Exception as e:
        logger.error(f"Migration failed: {e}")
        # Fall back to simple schema creation for new databases
        SQLModel.metadata.create_all(engine)
        logger.info("Created database schema without migrations")

    return engine


def get_task_by_id(session: Session, task_id: int) -> Optional[TaskDB]:
    """Get task by ID from database."""
    statement = select(TaskDB).where(TaskDB.id == task_id)
    return session.exec(statement).first()


def create_task_record(session: Session, task_data: TaskCreate, log_file_path: Optional[Path] = None) -> TaskDB:
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


def update_task_status(session: Session, task_id: int, status: TaskStatus, **kwargs) -> Optional[TaskDB]:
    """Updates task model using dynamic attribute setting."""
    task = get_task_by_id(session, task_id)
    if not task:
        return None

    task.status = status

    # Dynamic field updates using **kwargs
    for key, value in kwargs.items():
        if hasattr(task, key):
            setattr(task, key, value)

    session.add(task)
    session.commit()
    session.refresh(task)
    return task
