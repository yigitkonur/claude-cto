"""
SOLE RESPONSIBILITY: Contains all database Create, Read, Update, Delete (CRUD) logic.
Functions in this module are pure, stateless, and accept a database session and data models as arguments.
"""

from pathlib import Path
from datetime import datetime
from typing import Optional, List
from sqlmodel import Session, select
from . import models
from .path_utils import generate_log_filename, get_safe_log_directory


def create_task(
    session: Session, task_in: models.TaskCreate, log_dir: Optional[Path] = None
) -> models.TaskDB:
    """
    Create a new task in the database.
    Sets initial status to 'pending' and generates structured log file paths.
    """
    # Use the new logging directory structure
    if not log_dir:
        log_dir = get_safe_log_directory()

    # Create new task database object
    db_task = models.TaskDB(
        status=models.TaskStatus.PENDING,
        working_directory=task_in.working_directory,
        system_prompt=task_in.system_prompt
        or "You are a helpful assistant following John Carmack's principles of simplicity.",
        execution_prompt=task_in.execution_prompt,
        model=task_in.model or models.ClaudeModel.SONNET,
    )

    # Add to session to generate ID
    session.add(db_task)
    session.commit()
    session.refresh(db_task)

    # Generate enhanced log file path with directory context
    timestamp = datetime.utcnow()
    summary_filename = generate_log_filename(
        db_task.id, task_in.working_directory, "summary", timestamp
    )
    db_task.log_file_path = str(log_dir / summary_filename)

    # Update with log path
    session.add(db_task)
    session.commit()
    session.refresh(db_task)

    return db_task


def get_task(session: Session, task_id: int) -> Optional[models.TaskDB]:
    """Retrieve a single task by ID."""
    return session.get(models.TaskDB, task_id)


def get_all_tasks(session: Session) -> List[models.TaskDB]:
    """Retrieve all tasks from the database."""
    statement = select(models.TaskDB)
    results = session.exec(statement)
    return list(results)


def update_task_status(
    session: Session, task_id: int, status: models.TaskStatus
) -> models.TaskDB:
    """Update the status of a task."""
    task = session.get(models.TaskDB, task_id)
    if task:
        task.status = status

        # Set timestamps
        if status == models.TaskStatus.RUNNING and not task.started_at:
            task.started_at = datetime.utcnow()

        session.add(task)
        session.commit()
        session.refresh(task)
    return task


def mark_task_skipped(
    session: Session, task_id: int, error_message: str = "Skipped due to dependency failure"
) -> models.TaskDB:
    """Mark a task as skipped due to dependency failure."""
    task = session.get(models.TaskDB, task_id)
    if task:
        task.status = models.TaskStatus.SKIPPED
        task.dependency_failed_at = datetime.utcnow()
        task.error_message = error_message
        task.ended_at = datetime.utcnow()
        session.add(task)
        session.commit()
        session.refresh(task)
    return task


def mark_task_failed(
    session: Session, task_id: int, error_message: str
) -> models.TaskDB:
    """Mark a task as failed with error message."""
    task = session.get(models.TaskDB, task_id)
    if task:
        task.status = models.TaskStatus.FAILED
        task.error_message = error_message
        task.ended_at = datetime.utcnow()
        session.add(task)
        session.commit()
        session.refresh(task)
    return task


def append_to_summary_log(session: Session, task_id: int, summary_line: str):
    """
    Append a line to the task's log file and update last_action_cache.
    Transactional update operation.
    """
    task = session.get(models.TaskDB, task_id)
    if task and task.log_file_path:
        # Append to log file
        with open(task.log_file_path, "a") as f:
            f.write(summary_line + "\n")

        # Update last action cache
        task.last_action_cache = summary_line
        session.add(task)
        session.commit()


def finalize_task(
    session: Session, task_id: int, status: models.TaskStatus, result_message: str
):
    """
    Finalize a task with a final status and result message.
    Sets ended_at timestamp and populates either final_summary or error_message.
    """
    task = session.get(models.TaskDB, task_id)
    if task:
        task.status = status
        task.ended_at = datetime.utcnow()

        # Set appropriate result field
        if status == models.TaskStatus.COMPLETED:
            task.final_summary = result_message
        else:  # error or other failure status
            task.error_message = result_message

        session.add(task)
        session.commit()
        session.refresh(task)

    return task


def get_task_logs(task_id: int) -> Optional[dict]:
    """
    Get log file paths for a specific task.
    Returns dictionary with log file paths or None if task doesn't exist.
    """
    from .task_logger import get_task_logs as get_logs

    return get_logs(task_id)


def get_tasks_by_orchestration(
    session: Session, orchestration_id: int
) -> List[models.TaskDB]:
    """Get all tasks belonging to an orchestration."""
    statement = select(models.TaskDB).where(
        models.TaskDB.orchestration_id == orchestration_id
    )
    results = session.exec(statement)
    return list(results)


def create_orchestration(session: Session, total_tasks: int) -> models.OrchestrationDB:
    """Create a new orchestration record."""
    orch = models.OrchestrationDB(status="pending", total_tasks=total_tasks)
    session.add(orch)
    session.commit()
    session.refresh(orch)
    return orch


def update_orchestration_status(
    session: Session, orchestration_id: int, status: str, **kwargs
) -> models.OrchestrationDB:
    """Update orchestration status and optional fields."""
    orch = session.get(models.OrchestrationDB, orchestration_id)
    if orch:
        orch.status = status

        # Update optional fields
        for key, value in kwargs.items():
            if hasattr(orch, key):
                setattr(orch, key, value)

        # Set timestamps
        if status == "running" and not orch.started_at:
            orch.started_at = datetime.utcnow()
        elif status in ["completed", "failed", "cancelled"]:
            orch.ended_at = datetime.utcnow()

        session.add(orch)
        session.commit()
        session.refresh(orch)
    return orch


def get_orchestration(
    session: Session, orchestration_id: int
) -> Optional[models.OrchestrationDB]:
    """Get a single orchestration by ID."""
    return session.get(models.OrchestrationDB, orchestration_id)


def get_all_orchestrations(
    session: Session, status: Optional[str] = None, limit: int = 100
) -> List[models.OrchestrationDB]:
    """Get all orchestrations, optionally filtered by status."""
    statement = select(models.OrchestrationDB)

    if status:
        statement = statement.where(models.OrchestrationDB.status == status)

    statement = statement.order_by(models.OrchestrationDB.created_at.desc()).limit(
        limit
    )
    results = session.exec(statement)
    return list(results)
