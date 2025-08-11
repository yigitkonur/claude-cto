"""
SOLE RESPONSIBILITY: The system's central hub. Initializes the FastAPI and FastMCP apps, 
defines all API endpoints, manages the ProcessPoolExecutor, and orchestrates the overall server lifecycle.
"""

import asyncio
from pathlib import Path
from contextlib import asynccontextmanager
from concurrent.futures import ProcessPoolExecutor
from typing import List

from fastapi import FastAPI, Depends, HTTPException
from fastapi.responses import JSONResponse
from sqlmodel import Session

from .database import create_db_and_tables, get_session, app_dir
from . import models, crud
from .executor import TaskExecutor


# Initialize process pool for task execution
executor_pool = ProcessPoolExecutor(max_workers=4)


# Worker process entry point (must be top-level for pickling)
def run_task_in_worker(task_id: int):
    """
    Entry point for worker processes.
    Creates TaskExecutor and runs the async task.
    """
    executor = TaskExecutor(task_id)
    asyncio.run(executor.run())


# Async task runner for main process execution
async def run_task_async(task_id: int):
    """
    Run task in the main process as an async task.
    This is needed because Claude SDK OAuth authentication
    doesn't work properly in subprocess/ProcessPoolExecutor.
    """
    try:
        executor = TaskExecutor(task_id)
        await executor.run()
    except Exception as e:
        # Log error but don't crash the server
        print(f"Task {task_id} failed: {e}")


@asynccontextmanager
async def lifespan(app: FastAPI):
    """
    Manage application lifecycle.
    Setup: Initialize database
    Teardown: Shutdown process pool
    """
    # Startup
    create_db_and_tables()
    
    # Create log directory if it doesn't exist
    log_dir = app_dir / "logs"
    log_dir.mkdir(exist_ok=True)
    
    yield
    
    # Shutdown
    executor_pool.shutdown(wait=True)


# Initialize FastAPI app
app = FastAPI(
    title="Claude Worker Server",
    description="Fire-and-forget task execution for Claude Code SDK",
    version="0.1.0",
    lifespan=lifespan
)


# REST API Endpoints

@app.post("/api/v1/tasks", response_model=models.TaskRead)
async def create_task(
    task_in: models.TaskCreate,
    session: Session = Depends(get_session)
):
    """
    Create and execute a new task (human-friendly API).
    Lenient validation, applies defaults if needed.
    """
    # Apply default system prompt if not provided
    if not task_in.system_prompt:
        task_in.system_prompt = (
            "You are a helpful assistant following John Carmack's principles "
            "of simplicity and minimalism in software development."
        )
    
    # Create task in database
    log_dir = app_dir / "logs"
    db_task = crud.create_task(session, task_in, log_dir)
    
    # Submit to process pool for execution
    # Note: Using asyncio.create_task instead of ProcessPoolExecutor
    # because Claude SDK needs to run in the main process for OAuth auth
    asyncio.create_task(run_task_async(db_task.id))
    
    # Return task info (fire-and-forget)
    return models.TaskRead(
        id=db_task.id,
        status=db_task.status,
        created_at=db_task.created_at,
        started_at=db_task.started_at,
        ended_at=db_task.ended_at,
        last_action_cache=db_task.last_action_cache,
        final_summary=db_task.final_summary,
        error_message=db_task.error_message
    )


@app.get("/api/v1/tasks/{task_id}", response_model=models.TaskRead)
def get_task(
    task_id: int,
    session: Session = Depends(get_session)
):
    """Get task status and details."""
    task = crud.get_task(session, task_id)
    if not task:
        raise HTTPException(status_code=404, detail="Task not found")
    
    return models.TaskRead(
        id=task.id,
        status=task.status,
        created_at=task.created_at,
        started_at=task.started_at,
        ended_at=task.ended_at,
        last_action_cache=task.last_action_cache,
        final_summary=task.final_summary,
        error_message=task.error_message
    )


@app.get("/api/v1/tasks", response_model=List[models.TaskRead])
def list_tasks(session: Session = Depends(get_session)):
    """List all tasks."""
    tasks = crud.get_all_tasks(session)
    return [
        models.TaskRead(
            id=task.id,
            status=task.status,
            created_at=task.created_at,
            started_at=task.started_at,
            ended_at=task.ended_at,
            last_action_cache=task.last_action_cache,
            final_summary=task.final_summary,
            error_message=task.error_message
        )
        for task in tasks
    ]


# MCP-compatible endpoints (using strict validation)

@app.post("/api/v1/mcp/tasks", response_model=models.TaskRead)
async def create_mcp_task(
    payload: models.MCPCreateTaskPayload,
    session: Session = Depends(get_session)
):
    """
    Create and execute a new task (machine-friendly API).
    Strict validation enforced by Pydantic.
    """
    # Convert strict MCP payload to common TaskCreate model
    task_in = models.TaskCreate(
        execution_prompt=payload.execution_prompt,
        working_directory=payload.working_directory,
        system_prompt=payload.system_prompt
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
        created_at=db_task.created_at,
        started_at=db_task.started_at,
        ended_at=db_task.ended_at,
        last_action_cache=db_task.last_action_cache,
        final_summary=db_task.final_summary,
        error_message=db_task.error_message
    )


# Health check endpoint
@app.get("/health")
def health_check():
    """Simple health check endpoint."""
    return {"status": "healthy", "service": "claude-worker"}