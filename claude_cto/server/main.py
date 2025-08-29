"""
SOLE RESPONSIBILITY: The system's central hub. Initializes the FastAPI and FastMCP apps,
defines all API endpoints, and orchestrates the overall server lifecycle.
"""

import asyncio
import json
from contextlib import asynccontextmanager
from datetime import datetime
from typing import List, Optional

from fastapi import FastAPI, Depends, HTTPException, Request
from fastapi.middleware.cors import CORSMiddleware
from sqlmodel import Session

from .database import create_db_and_tables, get_session, app_dir
from . import models, crud
from .executor import TaskExecutor
from .orchestrator import TaskOrchestrator, CycleDetectedError, InvalidDependencyError
from .server_logger import (
    initialize_logging,
    log_lifecycle,
    log_crash,
    log_task_event,
    log_request_response,
)


# Global logging setup for the entire server
logger = initialize_logging(debug=False)


# Core task execution wrapper: manages TaskExecutor lifecycle within server process
# CRITICAL: Runs in main process due to Claude SDK OAuth requirements
async def run_task_async(task_id: int):
    """
    Task execution orchestration: delegates to TaskExecutor while handling server integration.
    MUST run in main process - Claude SDK OAuth authentication fails in subprocesses.
    Provides comprehensive logging and error handling for server stability.
    """
    try:
        # Task execution lifecycle logging: tracks execution phases for monitoring
        log_task_event(task_id, "execution_started")
        # Core task delegation: TaskExecutor handles SDK interaction and task lifecycle
        executor = TaskExecutor(task_id)
        await executor.run()  # Complete task execution with full error handling
        log_task_event(task_id, "execution_completed")
    except Exception as e:
        # Server resilience: logs errors without crashing main server process
        logger.error(f"Task {task_id} failed: {e}", exc_info=True)
        log_task_event(task_id, "execution_failed", {"error": str(e), "type": type(e).__name__})

        # Crash reporting: differentiates expected vs unexpected errors for alerting
        if not isinstance(e, (KeyboardInterrupt, SystemExit, asyncio.CancelledError)):
            log_crash(e, {"task_id": task_id, "phase": "task_execution"})


async def _periodic_circuit_breaker_cleanup():
    """
    Background maintenance: prevents disk space accumulation from stale circuit breaker data.
    CRITICAL: Runs continuously to prevent unbounded disk growth in long-running servers.
    Cleans up circuit breaker state files older than 7 days to maintain system health.
    """
    from .circuit_breaker_persistence import get_circuit_breaker_persistence

    while True:  # Continuous background maintenance loop
        try:
            await asyncio.sleep(3600)  # Hourly cleanup cycle - balances freshness vs overhead
            # Disk cleanup: removes old circuit breaker state files
            persistence = get_circuit_breaker_persistence()
            removed = persistence.cleanup_old_states(max_age_days=7)  # 7-day retention policy
            if removed > 0:
                logger.info(f"Cleaned up {removed} old circuit breaker states")
        except Exception as e:
            # Cleanup resilience: logs errors but continues cleanup loop
            logger.error(f"Circuit breaker cleanup failed: {e}")


@asynccontextmanager
async def lifespan(app: FastAPI):
    """
    Server lifecycle orchestration: manages startup initialization and graceful shutdown.
    CRITICAL: Initializes monitoring systems and ensures clean resource cleanup.
    Failure in startup phases prevents server from accepting requests.
    """
    # Structured lifecycle logging: enables monitoring of server health transitions
    async with log_lifecycle("claude-cto"):
        try:
            # Phase 1: Database initialization - establishes data persistence layer
            logger.info("Initializing database...")
            create_db_and_tables()  # Creates SQLite database and applies migrations
            logger.info("Database initialized successfully")

            # Phase 2: File system setup - ensures log directory exists for task outputs
            log_dir = app_dir / "logs"
            log_dir.mkdir(exist_ok=True)  # Idempotent directory creation
            logger.info(f"Task log directory: {log_dir}")

            # Phase 3: Memory monitoring activation - prevents resource leaks in long-running server
            logger.info("Starting memory monitoring...")
            from .memory_monitor import start_global_monitoring
            # Background monitoring: tracks system resources and task performance
            asyncio.create_task(start_global_monitoring())
            logger.info("Memory monitoring started")

            # Phase 4: Circuit breaker maintenance - prevents disk space accumulation
            logger.info("Starting circuit breaker cleanup...")
            # Background cleanup: maintains circuit breaker state file hygiene
            asyncio.create_task(_periodic_circuit_breaker_cleanup())
            logger.info("Circuit breaker cleanup started")

            logger.info("Server startup complete - ready to accept requests")

            # Server operation phase: yields control to FastAPI for request handling
            yield  # Server runs here - handles HTTP requests until shutdown

        except Exception as e:
            # Startup failure handling: logs errors and prevents incomplete server initialization
            logger.error(f"Startup failed: {e}", exc_info=True)
            log_crash(e, {"phase": "startup"})
            raise  # Propagate error to prevent server start with incomplete initialization
        finally:
            # Graceful shutdown sequence: ensures clean resource cleanup
            logger.info("Beginning shutdown sequence...")

            # Resource cleanup: stops background monitoring to prevent resource leaks
            from .memory_monitor import stop_global_monitoring
            await stop_global_monitoring()  # Gracefully stops monitoring background task

            logger.info("Server shutdown complete")


# Main FastAPI application instance: central HTTP server with lifecycle management
app = FastAPI(
    title="Claude CTO Server",
    description="Fire-and-forget task execution for Claude Code SDK",  # Async task delegation pattern
    version="0.1.0",
    lifespan=lifespan,  # Server startup/shutdown orchestration
)


# HTTP request/response logging middleware: captures all API interactions for monitoring
@app.middleware("http")
async def logging_middleware(request: Request, call_next):
    """
    Request/response logging: captures API usage patterns and performance metrics.
    Critical for debugging, monitoring, and security audit trails.
    """
    return await log_request_response(request, call_next)  # Structured logging wrapper


# CORS middleware: enables browser-based clients to access the API
# Configured for development - should be restricted in production environments
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],      # Development setting - restrict in production
    allow_credentials=True,    # Supports authenticated requests
    allow_methods=["*"],      # Allows all HTTP methods
    allow_headers=["*"],      # Allows all request headers
)


# REST API Endpoints


@app.post("/api/v1/tasks", response_model=models.TaskRead)
async def create_task(task_in: models.TaskCreate, session: Session = Depends(get_session)):
    """
    Task creation endpoint: creates database record and starts asynchronous execution.
    Fire-and-forget pattern: returns immediately while task executes in background.
    Core API endpoint for single task execution without dependencies.
    """
    try:
        # Default system prompt injection: ensures consistent AI behavior across tasks
        if not task_in.system_prompt:
            task_in.system_prompt = (
                "You are a helpful assistant following John Carmack's principles "
                "of simplicity and minimalism in software development."
            )

        # Database persistence: creates task record with initial state
        log_dir = app_dir / "logs"
        db_task = crud.create_task(session, task_in, log_dir)  # CRUD layer maintains SOLE principle

        # Task creation logging: records task parameters for monitoring and debugging
        logger.info(f"Created task {db_task.id} with model {db_task.model}")
        log_task_event(
            db_task.id,
            "task_created",
            {"model": db_task.model, "working_directory": db_task.working_directory},
        )

        # Background task execution: starts async execution without blocking HTTP response
        # CRITICAL: Uses asyncio.create_task (not ProcessPoolExecutor) due to Claude SDK OAuth requirements
        asyncio.create_task(run_task_async(db_task.id))

        # Immediate response: fire-and-forget pattern returns task info without waiting for completion
        return models.TaskRead(
            id=db_task.id,
            status=db_task.status,                    # Initial status (PENDING)
            working_directory=db_task.working_directory,
            created_at=db_task.created_at,
            started_at=db_task.started_at,            # Will be None initially
            ended_at=db_task.ended_at,                # Will be None initially
            last_action_cache=db_task.last_action_cache,
            final_summary=db_task.final_summary,
            error_message=db_task.error_message,
        )
    except Exception as e:
        # Error handling: logs errors and converts to HTTP exceptions
        logger.error(f"Failed to create task: {e}", exc_info=True)
        if not isinstance(e, HTTPException):
            log_crash(e, {"endpoint": "/api/v1/tasks", "method": "POST"})  # Unexpected error reporting
        raise HTTPException(status_code=500, detail=f"Failed to create task: {str(e)}")


@app.get("/api/v1/tasks/{task_id}", response_model=models.TaskRead)
def get_task(task_id: int, session: Session = Depends(get_session)):
    """
    Task status retrieval: returns current task state and execution details.
    Primary endpoint for monitoring task progress and retrieving final results.
    """
    # Database query: retrieves task record through CRUD layer
    task = crud.get_task(session, task_id)
    if not task:
        raise HTTPException(status_code=404, detail="Task not found")

    # Task state serialization: converts database record to API response format
    return models.TaskRead(
        id=task.id,
        status=task.status,                    # Current execution status
        working_directory=task.working_directory,
        created_at=task.created_at,
        started_at=task.started_at,            # When execution began (if started)
        ended_at=task.ended_at,                # When execution completed (if finished)
        last_action_cache=task.last_action_cache,  # Latest progress summary
        final_summary=task.final_summary,      # Completion summary
        error_message=task.error_message,      # Error details (if failed)
    )


@app.get("/api/v1/tasks", response_model=List[models.TaskRead])
def list_tasks(session: Session = Depends(get_session)):
    """
    Task list endpoint: returns all tasks with current status and metadata.
    Used for dashboard views, bulk monitoring, and task history analysis.
    """
    # Database query: retrieves all task records through CRUD layer
    tasks = crud.get_all_tasks(session)
    # Bulk serialization: converts all task records to API response format
    return [
        models.TaskRead(
            id=task.id,
            status=task.status,                    # Current status for each task
            working_directory=task.working_directory,
            created_at=task.created_at,
            started_at=task.started_at,
            ended_at=task.ended_at,
            last_action_cache=task.last_action_cache,
            final_summary=task.final_summary,
            error_message=task.error_message,
        )
        for task in tasks  # List comprehension for efficient serialization
    ]


@app.delete("/api/v1/tasks/{task_id}")
async def delete_task(task_id: int, session: Session = Depends(get_session)):
    """
    Delete a single non-running task.
    Safety: prevents deletion of running/pending tasks.
    
    Returns:
        Success status
    """
    success = crud.delete_task(session, task_id)
    if success:
        return {"success": True, "message": f"Task {task_id} deleted"}
    else:
        raise HTTPException(
            status_code=400,
            detail="Task not found or still running"
        )


@app.post("/api/v1/tasks/clear", status_code=200)
async def clear_completed_tasks(session: Session = Depends(get_session)):
    """
    Clear all completed and failed tasks.
    Alternative endpoint for bulk cleanup (POST for compatibility).
    
    Returns:
        Count of tasks deleted
    """
    count = crud.clear_completed_tasks(session)
    return {"deleted": count, "message": f"Cleared {count} completed/failed tasks"}


# MCP-compatible endpoints (using strict validation)


@app.post("/api/v1/mcp/tasks", response_model=models.TaskRead)
async def create_mcp_task(payload: models.MCPCreateTaskPayload, session: Session = Depends(get_session)):
    """
    MCP task creation endpoint: machine-to-machine API with strict validation.
    Used by MCP proxy servers - enforces stricter input validation than standard REST API.
    Identical execution logic to create_task but with enhanced input constraints.
    """
    # Payload transformation: converts MCP-specific payload to standard task format
    task_in = models.TaskCreate(
        execution_prompt=payload.execution_prompt,
        working_directory=payload.working_directory,
        system_prompt=payload.system_prompt,  # Required in MCP payload
    )

    # Database persistence: uses same logic as standard REST API for consistency
    log_dir = app_dir / "logs"
    db_task = crud.create_task(session, task_in, log_dir)

    # Background execution: identical async task pattern
    # CRITICAL: Main process execution required for Claude SDK OAuth
    asyncio.create_task(run_task_async(db_task.id))

    # Response formatting: identical structure to standard endpoint
    return models.TaskRead(
        id=db_task.id,
        status=db_task.status,
        working_directory=db_task.working_directory,
        created_at=db_task.created_at,
        started_at=db_task.started_at,
        ended_at=db_task.ended_at,
        last_action_cache=db_task.last_action_cache,
        final_summary=db_task.final_summary,
        error_message=db_task.error_message,
    )


# Health check endpoint
@app.get("/health")
def health_check():
    """Simple health check endpoint with version info."""
    from claude_cto import __version__
    return {"status": "healthy", "service": "claude-cto", "version": __version__}


# Orchestration endpoints


async def run_orchestration_async(orchestration_id: int):
    """Run an orchestration asynchronously."""
    try:
        log_task_event(orchestration_id, "orchestration_started", {"type": "orchestration"})
        orchestrator = TaskOrchestrator(orchestration_id)
        await orchestrator.run()
        log_task_event(orchestration_id, "orchestration_completed", {"type": "orchestration"})
    except Exception as e:
        logger.error(f"Orchestration {orchestration_id} failed: {e}", exc_info=True)
        log_task_event(
            orchestration_id,
            "orchestration_failed",
            {"type": "orchestration", "error": str(e), "error_type": type(e).__name__},
        )


@app.post("/api/v1/orchestrations", response_model=dict)
async def create_orchestration(orchestration: models.OrchestrationCreate, session: Session = Depends(get_session)):
    """
    Create and execute a task orchestration with dependencies.
    Validates the DAG, creates all tasks, and starts the orchestrator.
    """
    try:
        # Create orchestration record
        orch_db = crud.create_orchestration(session, len(orchestration.tasks))

        # Create task records with dependencies
        identifier_to_task_id = {}
        for task_item in orchestration.tasks:
            # Create the task
            task_create = models.TaskCreate(
                execution_prompt=task_item.execution_prompt,
                working_directory=task_item.working_directory,
                system_prompt=task_item.system_prompt,
                model=task_item.model,
            )

            db_task = crud.create_task(session, task_create)

            # Add orchestration-specific fields
            db_task.orchestration_id = orch_db.id
            db_task.identifier = task_item.identifier
            db_task.initial_delay = task_item.initial_delay
            db_task.status = models.TaskStatus.WAITING  # Start in waiting state

            # Store mapping for dependency resolution
            identifier_to_task_id[task_item.identifier] = db_task.id

            session.add(db_task)

        session.commit()

        # Resolve dependencies (convert identifiers to task IDs)
        for task_item in orchestration.tasks:
            if task_item.depends_on:
                task_id = identifier_to_task_id[task_item.identifier]
                task = crud.get_task(session, task_id)
                if task:
                    # Validate dependencies exist
                    for dep_identifier in task_item.depends_on:
                        if dep_identifier not in identifier_to_task_id:
                            raise HTTPException(
                                status_code=400,
                                detail=f"Task '{task_item.identifier}' depends on non-existent task '{dep_identifier}'",
                            )

                    # Store dependencies as JSON array of identifiers
                    task.depends_on = json.dumps(task_item.depends_on)
                    session.add(task)

        session.commit()

        # Pre-validate for circular dependencies
        try:
            orchestrator = TaskOrchestrator(orch_db.id)
            await orchestrator._load_orchestration()
            orchestrator._validate_graph()
        except (CycleDetectedError, InvalidDependencyError) as e:
            # Mark orchestration as failed
            orch_db.status = "failed"
            orch_db.ended_at = datetime.utcnow()
            session.add(orch_db)
            session.commit()

            raise HTTPException(status_code=400, detail=str(e))

        # Start orchestration asynchronously
        asyncio.create_task(run_orchestration_async(orch_db.id))

        # Return orchestration info with task details
        return {
            "orchestration_id": orch_db.id,
            "status": "pending",
            "total_tasks": len(orchestration.tasks),
            "tasks": [
                {
                    "identifier": task.identifier,
                    "task_id": identifier_to_task_id[task.identifier],
                    "depends_on": task.depends_on,
                    "initial_delay": task.initial_delay,
                }
                for task in orchestration.tasks
            ],
            "message": "Orchestration created and execution started",
        }

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Failed to create orchestration: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=str(e))


@app.get("/api/v1/orchestrations/{orchestration_id}")
async def get_orchestration_status(orchestration_id: int, session: Session = Depends(get_session)):
    """Get the status and details of an orchestration."""
    orch = crud.get_orchestration(session, orchestration_id)
    if not orch:
        raise HTTPException(status_code=404, detail="Orchestration not found")

    # Get all tasks in the orchestration
    tasks = crud.get_tasks_by_orchestration(session, orchestration_id)

    # Build task status summary
    task_summary = []
    for task in tasks:
        task_summary.append(
            {
                "task_id": task.id,
                "identifier": task.identifier,
                "status": task.status,
                "depends_on": json.loads(task.depends_on) if task.depends_on else [],
                "initial_delay": task.initial_delay,
                "started_at": task.started_at,
                "ended_at": task.ended_at,
                "error_message": task.error_message,
            }
        )

    return {
        "orchestration_id": orch.id,
        "status": orch.status,
        "created_at": orch.created_at,
        "started_at": orch.started_at,
        "ended_at": orch.ended_at,
        "total_tasks": orch.total_tasks,
        "completed_tasks": orch.completed_tasks,
        "failed_tasks": orch.failed_tasks,
        "skipped_tasks": orch.skipped_tasks,
        "tasks": task_summary,
    }


@app.delete("/api/v1/orchestrations/{orchestration_id}/cancel")
async def cancel_orchestration(orchestration_id: int, session: Session = Depends(get_session)):
    """Cancel a running orchestration and all its pending tasks."""
    orch = crud.get_orchestration(session, orchestration_id)
    if not orch:
        raise HTTPException(status_code=404, detail="Orchestration not found")

    if orch.status not in ["pending", "running"]:
        raise HTTPException(
            status_code=400,
            detail=f"Cannot cancel orchestration in {orch.status} state",
        )

    # Get all tasks in the orchestration
    tasks = crud.get_tasks_by_orchestration(session, orchestration_id)

    # Cancel all pending/waiting tasks
    cancelled_count = 0
    for task in tasks:
        if task.status in [models.TaskStatus.PENDING, models.TaskStatus.WAITING]:
            task.status = models.TaskStatus.SKIPPED
            task.error_message = "Cancelled by user"
            task.ended_at = datetime.utcnow()
            session.add(task)
            cancelled_count += 1

    # Update orchestration status
    orch.status = "cancelled"
    orch.ended_at = datetime.utcnow()
    session.add(orch)
    session.commit()

    return {
        "message": f"Orchestration cancelled. {cancelled_count} tasks were cancelled.",
        "orchestration_id": orchestration_id,
    }


@app.get("/api/v1/orchestrations")
async def list_orchestrations(
    status: Optional[str] = None,
    limit: int = 100,
    session: Session = Depends(get_session),
):
    """List all orchestrations, optionally filtered by status."""
    orchestrations = crud.get_all_orchestrations(session, status, limit)

    results = []
    for orch in orchestrations:
        results.append(
            {
                "id": orch.id,
                "status": orch.status,
                "created_at": orch.created_at,
                "started_at": orch.started_at,
                "ended_at": orch.ended_at,
                "total_tasks": orch.total_tasks,
                "completed_tasks": orch.completed_tasks,
                "failed_tasks": orch.failed_tasks,
                "skipped_tasks": orch.skipped_tasks,
            }
        )

    return results
