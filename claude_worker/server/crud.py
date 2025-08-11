"""
SOLE RESPONSIBILITY: Contains all database Create, Read, Update, Delete (CRUD) logic. 
Functions in this module are pure, stateless, and accept a database session and data models as arguments.
"""

from pathlib import Path
from datetime import datetime
from typing import Optional, List
from sqlmodel import Session, select
from . import models


def create_task(session: Session, task_in: models.TaskCreate, log_dir: Path) -> models.TaskDB:
    """
    Create a new task in the database.
    Sets initial status to 'queued' and generates log file paths.
    """
    # Create new task database object
    db_task = models.TaskDB(
        status='queued',
        working_directory=task_in.working_directory,
        system_prompt=task_in.system_prompt or "You are a helpful assistant following John Carmack's principles of simplicity.",
        execution_prompt=task_in.execution_prompt,
        raw_log_path="",  # Will be set after ID is generated
        summary_log_path=""  # Will be set after ID is generated
    )
    
    # Add to session to generate ID
    session.add(db_task)
    session.commit()
    session.refresh(db_task)
    
    # Generate log file paths with task ID
    db_task.raw_log_path = str(log_dir / f"task_{db_task.id}_raw.log")
    db_task.summary_log_path = str(log_dir / f"task_{db_task.id}_summary.log")
    
    # Update with log paths
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


def update_task_status(session: Session, task_id: int, status: str) -> models.TaskDB:
    """Update the status of a task."""
    task = session.get(models.TaskDB, task_id)
    if task:
        task.status = status
        if status == 'running' and not task.started_at:
            task.started_at = datetime.utcnow()
        session.add(task)
        session.commit()
        session.refresh(task)
    return task


def append_to_summary_log(session: Session, task_id: int, summary_line: str):
    """
    Append a line to the task's summary log file and update last_action_cache.
    Transactional update operation.
    """
    task = session.get(models.TaskDB, task_id)
    if task:
        # Append to summary log file
        with open(task.summary_log_path, 'a') as f:
            f.write(summary_line + '\n')
        
        # Update last action cache
        task.last_action_cache = summary_line
        session.add(task)
        session.commit()


def finalize_task(session: Session, task_id: int, status: str, result_message: str):
    """
    Finalize a task with a final status and result message.
    Sets ended_at timestamp and populates either final_summary or error_message.
    """
    task = session.get(models.TaskDB, task_id)
    if task:
        task.status = status
        task.ended_at = datetime.utcnow()
        
        if status == 'completed':
            task.final_summary = result_message
        else:  # error or other failure status
            task.error_message = result_message
        
        session.add(task)
        session.commit()
        session.refresh(task)
    return task