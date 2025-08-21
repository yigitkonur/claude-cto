"""
SOLE RESPONSIBILITY: The system's central hub. Initializes the FastAPI and FastMCP apps,
defines all API endpoints, manages the ProcessPoolExecutor, and orchestrates the overall server lifecycle.
"""

import asyncio
import json
import os
from contextlib import asynccontextmanager
from concurrent.futures import ProcessPoolExecutor
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


# Initialize comprehensive logging
logger = initialize_logging(debug=False)


# Initialize process pool for task execution
executor_pool = ProcessPoolExecutor(max_workers=4)


# Worker process entry point (must be top-level for pickling)
def run_task_in_worker(task_id: int):
    """
    Entry point for worker processes.
    Creates TaskExecutor and runs the async task.
    """
    try:
        log_task_event(task_id, "worker_started", {"pid": os.getpid()})
        executor = TaskExecutor(task_id)
        asyncio.run(executor.run())
        log_task_event(task_id, "worker_completed")
    except Exception as e:
        logger.error(f"Worker process failed for task {task_id}: {e}", exc_info=True)
        log_task_event(task_id, "worker_failed", {"error": str(e)})
        raise


# Async task runner for main process execution
async def run_task_async(task_id: int):
    """
    Run task in the main process as an async task.
    This is needed because Claude SDK OAuth authentication
    doesn't work properly in subprocess/ProcessPoolExecutor.
    """
    try:
        log_task_event(task_id, "execution_started")
        executor = TaskExecutor(task_id)
        await executor.run()
        log_task_event(task_id, "execution_completed")
    except Exception as e:
        # Log error but don't crash the server
        logger.error(f"Task {task_id} failed: {e}", exc_info=True)
        log_task_event(
            task_id, "execution_failed", {"error": str(e), "type": type(e).__name__}
        )

        # Log crash if it's an unexpected error
        if not isinstance(e, (KeyboardInterrupt, SystemExit, asyncio.CancelledError)):
            log_crash(e, {"task_id": task_id, "phase": "task_execution"})


@asynccontextmanager
async def lifespan(app: FastAPI):
    """
    Manage application lifecycle with comprehensive logging.
    Setup: Initialize database and logging
    Teardown: Shutdown process pool and finalize logs
    """
    async with log_lifecycle("claude-cto"):
        try:
            # Startup
            logger.info("Initializing database...")
            create_db_and_tables()
            logger.info("Database initialized successfully")

            # Create log directory if it doesn't exist
            log_dir = app_dir / "logs"
            log_dir.mkdir(exist_ok=True)
            logger.info(f"Task log directory: {log_dir}")

            logger.info("Server startup complete - ready to accept requests")

            yield

        except Exception as e:
            logger.error(f"Startup failed: {e}", exc_info=True)
            log_crash(e, {"phase": "startup"})
            raise
        finally:
            # Shutdown
            logger.info("Beginning shutdown sequence...")
            try:
                executor_pool.shutdown(wait=True)
                logger.info("Process pool shutdown complete")
            except Exception as e:
                logger.error(f"Shutdown error: {e}", exc_info=True)
                log_crash(e, {"phase": "shutdown"})


# Initialize FastAPI app
app = FastAPI(
    title="Claude CTO Server",
    description="Fire-and-forget task execution for Claude Code SDK",
    version="0.1.0",
    lifespan=lifespan,
)


# Add middleware for request/response logging
@app.middleware("http")
async def logging_middleware(request: Request, call_next):
    """Log all HTTP requests and responses."""
    return await log_request_response(request, call_next)


# Add CORS middleware for cross-origin requests
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


# REST API Endpoints


@app.post("/api/v1/tasks", response_model=models.TaskRead)
async def create_task(
    task_in: models.TaskCreate, session: Session = Depends(get_session)
):
    """
    Create and execute a new task (human-friendly API).
    Lenient validation, applies defaults if needed.
    """
    try:
        # Apply default system prompt if not provided
        if not task_in.system_prompt:
            task_in.system_prompt = (
                "You are a helpful assistant following John Carmack's principles "
                "of simplicity and minimalism in software development."
            )

        # Create task in database
        log_dir = app_dir / "logs"
        db_task = crud.create_task(session, task_in, log_dir)

        logger.info(f"Created task {db_task.id} with model {db_task.model}")
        log_task_event(
            db_task.id,
            "task_created",
            {"model": db_task.model, "working_directory": db_task.working_directory},
        )

        # Submit to process pool for execution
        # Note: Using asyncio.create_task instead of ProcessPoolExecutor
        # because Claude SDK needs to run in the main process for OAuth auth
        asyncio.create_task(run_task_async(db_task.id))

        # Return task info (fire-and-forget)
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
    except Exception as e:
        logger.error(f"Failed to create task: {e}", exc_info=True)
        if not isinstance(e, HTTPException):
            log_crash(e, {"endpoint": "/api/v1/tasks", "method": "POST"})
        raise HTTPException(status_code=500, detail=f"Failed to create task: {str(e)}")


@app.get("/api/v1/tasks/{task_id}", response_model=models.TaskRead)
def get_task(task_id: int, session: Session = Depends(get_session)):
    """Get task status and details."""
    task = crud.get_task(session, task_id)
    if not task:
        raise HTTPException(status_code=404, detail="Task not found")

    return models.TaskRead(
        id=task.id,
        status=task.status,
        working_directory=task.working_directory,
        created_at=task.created_at,
        started_at=task.started_at,
        ended_at=task.ended_at,
        last_action_cache=task.last_action_cache,
        final_summary=task.final_summary,
        error_message=task.error_message,
    )


@app.get("/api/v1/tasks", response_model=List[models.TaskRead])
def list_tasks(session: Session = Depends(get_session)):
    """List all tasks."""
    tasks = crud.get_all_tasks(session)
    return [
        models.TaskRead(
            id=task.id,
            status=task.status,
            working_directory=task.working_directory,
            created_at=task.created_at,
            started_at=task.started_at,
            ended_at=task.ended_at,
            last_action_cache=task.last_action_cache,
            final_summary=task.final_summary,
            error_message=task.error_message,
        )
        for task in tasks
    ]


# MCP-compatible endpoints (using strict validation)


@app.post("/api/v1/mcp/tasks", response_model=models.TaskRead)
async def create_mcp_task(
    payload: models.MCPCreateTaskPayload, session: Session = Depends(get_session)
):
    """
    Create and execute a new task (machine-friendly API).
    Strict validation enforced by Pydantic.
    """
    # Convert strict MCP payload to common TaskCreate model
    task_in = models.TaskCreate(
        execution_prompt=payload.execution_prompt,
        working_directory=payload.working_directory,
        system_prompt=payload.system_prompt,
    )

    # Create task in database (same logic as REST API)
    log_dir = app_dir / "logs"
    db_task = crud.create_task(session, task_in, log_dir)

    # Submit to process pool for execution
    # Note: Using asyncio.create_task instead of ProcessPoolExecutor
    # because Claude SDK needs to run in the main process for OAuth auth
    asyncio.create_task(run_task_async(db_task.id))

    # Return task info
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
    """Simple health check endpoint."""
    return {"status": "healthy", "service": "claude-cto"}


# Orchestration endpoints


async def run_orchestration_async(orchestration_id: int):
    """Run an orchestration asynchronously."""
    try:
        log_task_event(
            orchestration_id, "orchestration_started", {"type": "orchestration"}
        )
        orchestrator = TaskOrchestrator(orchestration_id)
        await orchestrator.run()
        log_task_event(
            orchestration_id, "orchestration_completed", {"type": "orchestration"}
        )
    except Exception as e:
        logger.error(f"Orchestration {orchestration_id} failed: {e}", exc_info=True)
        log_task_event(
            orchestration_id,
            "orchestration_failed",
            {"type": "orchestration", "error": str(e), "error_type": type(e).__name__},
        )


@app.post("/api/v1/orchestrations", response_model=dict)
async def create_orchestration(
    orchestration: models.OrchestrationCreate, session: Session = Depends(get_session)
):
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
async def get_orchestration_status(
    orchestration_id: int, session: Session = Depends(get_session)
):
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
async def cancel_orchestration(
    orchestration_id: int, session: Session = Depends(get_session)
):
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
