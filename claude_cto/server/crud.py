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


def create_task(session: Session, task_in: models.TaskCreate, log_dir: Optional[Path] = None) -> models.TaskDB:
    """
    Task creation with log file generation: creates database record and establishes file paths.
    Critical database entry point - generates unique IDs and sets up logging infrastructure.
    Two-phase commit: creates record to get ID → generates log path → updates with path.
    """
    # Log directory resolution: ensures structured file organization for task outputs
    # CRITICAL: Uses safe directory creation to prevent path injection attacks
    if not log_dir:
        log_dir = get_safe_log_directory()

    # Task record initialization: establishes database entity with default values
    db_task = models.TaskDB(
        status=models.TaskStatus.PENDING,
        working_directory=task_in.working_directory,
        system_prompt=task_in.system_prompt
        or "You are a helpful assistant following John Carmack's principles of simplicity.",
        execution_prompt=task_in.execution_prompt,
        model=task_in.model or models.ClaudeModel.SONNET,
    )

    # Phase 1: Database insertion to generate unique task ID (required for log naming)
    session.add(db_task)
    session.commit()
    session.refresh(db_task)

    # Log path construction: generates unique, collision-free filename using task ID
    # CRITICAL: Includes working directory context for debugging and file organization
    timestamp = datetime.utcnow()
    summary_filename = generate_log_filename(db_task.id, task_in.working_directory, "summary", timestamp)
    db_task.log_file_path = str(log_dir / summary_filename)

    # Phase 2: Path persistence to complete task creation with logging infrastructure
    session.add(db_task)
    session.commit()
    session.refresh(db_task)

    return db_task


def get_task(session: Session, task_id: int) -> Optional[models.TaskDB]:
    """
    Primary key lookup: retrieves task record by ID with full relationship data.
    Core query method used throughout system for status checks and updates.
    """
    return session.get(models.TaskDB, task_id)


def get_all_tasks(session: Session) -> List[models.TaskDB]:
    """
    Full table scan: retrieves all task records for admin interface and bulk operations.
    WARNING: Can return large datasets - consider pagination for production systems.
    """
    # Unbounded query: loads entire task table into memory (acceptable for current scale)
    statement = select(models.TaskDB)
    results = session.exec(statement)
    return list(results)


def update_task_status(session: Session, task_id: int, status: models.TaskStatus) -> models.TaskDB:
    """
    Status transition with timestamp tracking: updates task lifecycle state atomically.
    Critical for orchestration dependency resolution and monitoring systems.
    Automatically sets execution timestamp when transitioning to RUNNING status.
    """
    # Record retrieval: uses primary key for fast, direct access
    task = session.get(models.TaskDB, task_id)
    if task:
        task.status = status

        # Lifecycle timestamp management: tracks execution start for duration metrics
        # CRITICAL: Only sets started_at once to prevent timestamp corruption
        if status == models.TaskStatus.RUNNING and not task.started_at:
            task.started_at = datetime.utcnow()

        # Atomic commit: ensures status and timestamp are updated together
        session.add(task)
        session.commit()
        session.refresh(task)
    return task


def mark_task_skipped(
    session: Session,
    task_id: int,
    error_message: str = "Skipped due to dependency failure",
) -> models.TaskDB:
    """
    Dependency failure handling: marks task as skipped with failure context.
    Critical for orchestration - prevents dependent tasks from executing after prerequisite failures.
    Records both dependency failure timestamp and task end timestamp for analytics.
    """
    # Task retrieval for skip processing
    task = session.get(models.TaskDB, task_id)
    if task:
        task.status = models.TaskStatus.SKIPPED
        # Dual timestamp tracking: dependency failure time vs task completion time
        task.dependency_failed_at = datetime.utcnow()  # When dependency failed
        task.error_message = error_message
        task.ended_at = datetime.utcnow()  # When task was marked complete (skipped)
        
        # Atomic skip finalization: ensures all fields are updated together
        session.add(task)
        session.commit()
        session.refresh(task)
    return task


def mark_task_failed(session: Session, task_id: int, error_message: str) -> models.TaskDB:
    """
    Task failure finalization: records error details and completion timestamp.
    Critical for error reporting and retry logic - preserves failure context for analysis.
    Used by TaskExecutor when SDK calls fail permanently (vs transient retries).
    """
    # Task retrieval for failure processing
    task = session.get(models.TaskDB, task_id)
    if task:
        task.status = models.TaskStatus.FAILED
        task.error_message = error_message  # Detailed failure description from ErrorHandler
        task.ended_at = datetime.utcnow()  # Task completion timestamp
        
        # Atomic failure finalization: ensures status and error details are persisted together
        session.add(task)
        session.commit()
        session.refresh(task)
    return task


def append_to_summary_log(session: Session, task_id: int, summary_line: str):
    """
    Real-time progress logging: appends SDK messages to file and database cache.
    Critical for task monitoring - enables progress tracking during long-running executions.
    Dual write: file persistence for debugging + database cache for API responses.
    """
    # Task and log path validation: ensures log file exists before writing
    task = session.get(models.TaskDB, task_id)
    if task and task.log_file_path:
        # File system logging: appends progress line to persistent log file
        # CRITICAL: Uses append mode to prevent overwriting previous progress
        with open(task.log_file_path, "a") as f:
            f.write(summary_line + "\n")

        # Database cache update: stores latest progress for fast API access
        # Used by status endpoints to show current task activity without file I/O
        task.last_action_cache = summary_line
        session.add(task)
        session.commit()


def finalize_task(session: Session, task_id: int, status: models.TaskStatus, result_message: str):
    """
    Task completion finalization: records final outcome with appropriate result field.
    Critical endpoint for TaskExecutor - marks task as definitively complete or failed.
    Smart field routing: success messages go to final_summary, failures to error_message.
    """
    # Task retrieval for finalization processing
    task = session.get(models.TaskDB, task_id)
    if task:
        task.status = status
        task.ended_at = datetime.utcnow()  # Task completion timestamp for duration calculations

        # Result field routing: success vs failure messages use different database columns
        # CRITICAL: Separates successful outcomes from error conditions for proper API responses
        if status == models.TaskStatus.COMPLETED:
            task.final_summary = result_message  # Success message with task results
        else:  # FAILED, SKIPPED, or other non-success status
            task.error_message = result_message  # Error details for troubleshooting

        # Atomic finalization: ensures status, timestamp, and result message are committed together
        session.add(task)
        session.commit()
        session.refresh(task)

    return task


def get_task_logs(task_id: int) -> Optional[dict]:
    """
    Log file discovery: retrieves file paths for task debugging and monitoring.
    Delegates to TaskLogger for consistent path resolution across system.
    Returns structured dictionary with summary and detailed log paths.
    """
    from .task_logger import get_task_logs as get_logs

    return get_logs(task_id)


def get_tasks_by_orchestration(session: Session, orchestration_id: int) -> List[models.TaskDB]:
    """
    Orchestration task query: retrieves all tasks in a dependency group.
    Critical for TaskOrchestrator - loads complete task set for DAG execution.
    Uses indexed foreign key for efficient orchestration-based filtering.
    """
    # Foreign key query: uses orchestration_id index for fast task group retrieval
    statement = select(models.TaskDB).where(models.TaskDB.orchestration_id == orchestration_id)
    results = session.exec(statement)
    return list(results)


def create_orchestration(session: Session, total_tasks: int) -> models.OrchestrationDB:
    """
    Orchestration initialization: creates parent record for task dependency groups.
    Critical for DAG execution - establishes container for coordinated task execution.
    Records expected task count for completion tracking and progress monitoring.
    """
    # Orchestration record creation with task count for progress calculation
    orch = models.OrchestrationDB(status="pending", total_tasks=total_tasks)
    
    # Immediate persistence to generate orchestration ID for task association
    session.add(orch)
    session.commit()
    session.refresh(orch)
    return orch


def update_orchestration_status(
    session: Session, orchestration_id: int, status: str, **kwargs
) -> models.OrchestrationDB:
    """
    Orchestration status management: updates DAG execution state with statistics.
    Critical for TaskOrchestrator progress tracking - records task completion counts.
    Flexible field update system allows completion metrics (completed_tasks, failed_tasks, etc).
    """
    # Orchestration record retrieval for status update
    orch = session.get(models.OrchestrationDB, orchestration_id)
    if orch:
        orch.status = status

        # Dynamic field updates: handles completion statistics and metadata
        # Used for completed_tasks, failed_tasks, skipped_tasks from TaskOrchestrator
        for key, value in kwargs.items():
            if hasattr(orch, key):
                setattr(orch, key, value)

        # Lifecycle timestamp management: tracks orchestration execution phases
        if status == "running" and not orch.started_at:
            orch.started_at = datetime.utcnow()  # DAG execution start
        elif status in ["completed", "failed", "cancelled"]:
            orch.ended_at = datetime.utcnow()  # DAG execution end

        # Atomic status update: ensures status, metrics, and timestamps are committed together
        session.add(orch)
        session.commit()
        session.refresh(orch)
    return orch


def get_orchestration(session: Session, orchestration_id: int) -> Optional[models.OrchestrationDB]:
    """
    Orchestration lookup: retrieves DAG execution record by ID.
    Used for status checks and completion validation during task orchestration.
    """
    return session.get(models.OrchestrationDB, orchestration_id)


def get_all_orchestrations(
    session: Session, status: Optional[str] = None, limit: int = 100
) -> List[models.OrchestrationDB]:
    """
    Orchestration listing with filtering: retrieves DAG records for admin interface.
    Supports status-based filtering for monitoring active, completed, or failed orchestrations.
    Ordered by creation time (newest first) with pagination for performance.
    """
    # Base query: selects all orchestration records
    statement = select(models.OrchestrationDB)

    # Optional status filtering: enables queries like "show all running orchestrations"
    if status:
        statement = statement.where(models.OrchestrationDB.status == status)

    # Result ordering and pagination: newest first with configurable limit
    statement = statement.order_by(models.OrchestrationDB.created_at.desc()).limit(limit)
    results = session.exec(statement)
    return list(results)


def clear_completed_tasks(session: Session) -> int:
    """
    Clear all completed and failed tasks from the database.
    Returns the number of tasks deleted.
    
    Follows Carmack's principle: simple, effective, no unnecessary complexity.
    Only removes tasks that are in terminal states (COMPLETED or FAILED).
    """
    # Query for tasks in terminal states
    statement = select(models.TaskDB).where(
        models.TaskDB.status.in_([models.TaskStatus.COMPLETED, models.TaskStatus.FAILED])
    )
    tasks = session.exec(statement).all()
    
    # Count and delete
    count = len(tasks)
    for task in tasks:
        session.delete(task)
    
    session.commit()
    return count


def delete_task(session: Session, task_id: int) -> bool:
    """
    Delete a single non-running task.
    Returns True if deleted, False if not found or still running.
    
    Safety check: prevents deletion of RUNNING or PENDING tasks.
    """
    task = get_task(session, task_id)
    
    if not task:
        return False
    
    # Safety: don't delete running tasks
    if task.status in [models.TaskStatus.RUNNING, models.TaskStatus.PENDING]:
        return False
    
    session.delete(task)
    session.commit()
    return True
