"""
Standalone MCP server that runs independently without REST API.
Uses embedded database and direct task execution.
"""

import os
import asyncio
from pathlib import Path
from datetime import datetime
from concurrent.futures import ProcessPoolExecutor
from typing import Optional, Dict, Any

from fastmcp import FastMCP
from sqlmodel import Session

from claude_worker.core import (
    init_database,
    create_session_maker,
    create_task_record,
    get_task_by_id,
    execute_task_async
)
from claude_worker.server.models import TaskCreate, TaskStatus


# Process pool for task execution (module level for pickling)
executor_pool = ProcessPoolExecutor(max_workers=2)


def create_standalone_server(
    db_path: Optional[str] = None,
    log_dir: Optional[str] = None
) -> FastMCP:
    """
    Create a standalone MCP server with embedded database.
    
    Args:
        db_path: Optional path to SQLite database
        log_dir: Optional directory for task logs
    
    Returns:
        FastMCP server instance
    """
    
    # Initialize database
    engine = init_database(db_path)
    SessionLocal = create_session_maker(engine)
    
    # Setup log directory
    if log_dir:
        log_path = Path(log_dir)
    else:
        log_path = Path.home() / ".claude-worker" / "logs"
    log_path.mkdir(parents=True, exist_ok=True)
    
    # Create MCP server
    mcp = FastMCP(
        name="claude-worker-standalone",
        dependencies=[
            "claude-code-sdk>=0.0.19",
            "sqlmodel>=0.0.14"
        ]
    )
    
    @mcp.tool()
    async def create_task(
        execution_prompt: str,
        working_directory: str = ".",
        system_prompt: Optional[str] = None
    ) -> Dict[str, Any]:
        """
        Submit a new Claude Code task for execution.
        
        Args:
            execution_prompt: The task prompt to execute
            working_directory: Directory to run the task in
            system_prompt: Optional system prompt (defaults to John Carmack principles)
        
        Returns:
            Task information including ID and status
        """
        
        # Apply default system prompt if not provided
        if not system_prompt:
            system_prompt = (
                "You are a helpful assistant following John Carmack's principles "
                "of simplicity and minimalism in software development. "
                "Focus on clear, efficient solutions."
            )
        
        # Validate system prompt contains "John Carmack" for MCP compatibility
        if "John Carmack" not in system_prompt:
            return {
                "error": "System prompt must contain 'John Carmack' for MCP compliance",
                "hint": "Add 'following John Carmack's principles' to your system prompt"
            }
        
        # Create task in database
        with SessionLocal() as session:
            task_data = TaskCreate(
                execution_prompt=execution_prompt,
                working_directory=working_directory,
                system_prompt=system_prompt
            )
            
            # Create log file path
            task_log_dir = log_path / datetime.utcnow().strftime("%Y%m%d")
            task_log_dir.mkdir(parents=True, exist_ok=True)
            
            db_task = create_task_record(session, task_data, task_log_dir)
            task_id = db_task.id
        
        # Submit task for async execution
        asyncio.create_task(_execute_task_background(task_id, log_path))
        
        return {
            "id": task_id,
            "status": "pending",
            "message": "Task submitted successfully",
            "working_directory": working_directory,
            "created_at": datetime.utcnow().isoformat()
        }
    
    @mcp.tool()
    async def get_task_status(task_id: int) -> Dict[str, Any]:
        """
        Get the status of a submitted task.
        
        Args:
            task_id: ID of the task to check
            
        Returns:
            Task status and details
        """
        with SessionLocal() as session:
            task = get_task_by_id(session, task_id)
            
            if not task:
                return {"error": f"Task {task_id} not found"}
            
            return {
                "id": task.id,
                "status": task.status.value,
                "created_at": task.created_at.isoformat() if task.created_at else None,
                "started_at": task.started_at.isoformat() if task.started_at else None,
                "ended_at": task.ended_at.isoformat() if task.ended_at else None,
                "last_action": task.last_action_cache,
                "final_summary": task.final_summary,
                "error_message": task.error_message,
                "working_directory": task.working_directory,
                "log_file": task.log_file_path
            }
    
    @mcp.tool()
    async def list_tasks(
        status: Optional[str] = None,
        limit: int = 10
    ) -> Dict[str, Any]:
        """
        List recent tasks.
        
        Args:
            status: Optional filter by status (pending, running, completed, failed)
            limit: Maximum number of tasks to return
            
        Returns:
            List of recent tasks
        """
        with SessionLocal() as session:
            from sqlmodel import select
            from claude_worker.server.models import TaskDB
            
            statement = select(TaskDB)
            
            if status:
                try:
                    status_enum = TaskStatus(status)
                    statement = statement.where(TaskDB.status == status_enum)
                except ValueError:
                    return {"error": f"Invalid status: {status}"}
            
            statement = statement.order_by(TaskDB.created_at.desc()).limit(limit)
            tasks = session.exec(statement).all()
            
            return {
                "tasks": [
                    {
                        "id": task.id,
                        "status": task.status.value,
                        "created_at": task.created_at.isoformat() if task.created_at else None,
                        "execution_prompt": task.execution_prompt[:100] + "..." 
                            if len(task.execution_prompt) > 100 else task.execution_prompt
                    }
                    for task in tasks
                ],
                "count": len(tasks)
            }
    
    @mcp.tool()
    async def get_task_logs(task_id: int) -> Dict[str, Any]:
        """
        Get the logs for a specific task.
        
        Args:
            task_id: ID of the task
            
        Returns:
            Task log contents or error
        """
        with SessionLocal() as session:
            task = get_task_by_id(session, task_id)
            
            if not task:
                return {"error": f"Task {task_id} not found"}
            
            if not task.log_file_path:
                return {"error": "No log file available yet"}
            
            log_file = Path(task.log_file_path)
            if not log_file.exists():
                return {"error": "Log file not found"}
            
            try:
                with open(log_file, 'r') as f:
                    logs = f.read()
                
                return {
                    "id": task_id,
                    "logs": logs[-10000:],  # Last 10KB of logs
                    "log_file": str(log_file)
                }
            except Exception as e:
                return {"error": f"Failed to read logs: {str(e)}"}
    
    async def _execute_task_background(task_id: int, log_dir: Path):
        """Background task execution."""
        with SessionLocal() as session:
            await execute_task_async(task_id, session, log_dir)
    
    return mcp


# Module-level server instance for fastmcp CLI
mcp = create_standalone_server()

if __name__ == "__main__":
    # Run as stdio server
    import asyncio
    asyncio.run(mcp.run_stdio_async())