"""
Standalone MCP server that runs independently without REST API.
Uses embedded database and direct task execution.
"""

import asyncio
from pathlib import Path
from datetime import datetime
from concurrent.futures import ProcessPoolExecutor
from typing import Optional, Dict, Any

from fastmcp import FastMCP

from claude_cto.core import (
    init_database,
    create_session_maker,
    create_task_record,
    get_task_by_id,
    execute_task_async,
)
from claude_cto.server.models import TaskCreate, TaskStatus


# Process pool for task execution (module level for pickling)
executor_pool = ProcessPoolExecutor(max_workers=2)


def create_standalone_server(db_path: Optional[str] = None, log_dir: Optional[str] = None) -> FastMCP:
    """
    Create a standalone MCP server with embedded database.

    Args:
        db_path: Optional path to SQLite database
        log_dir: Optional directory for task logs

    Returns:
        FastMCP server instance
    """

    # Embedded database initialization: creates local SQLite with all tables and migrations
    engine = init_database(db_path)
    SessionLocal = create_session_maker(engine)

    # Log directory setup: creates filesystem structure for task output storage
    if log_dir:
        log_path = Path(log_dir)
    else:
        log_path = Path.home() / ".claude-cto" / "logs"
    log_path.mkdir(parents=True, exist_ok=True)

    # Self-contained MCP server: no external API dependencies, direct SDK integration
    mcp = FastMCP(
        name="claude-cto-standalone",
        dependencies=["claude-code-sdk>=0.0.19", "sqlmodel>=0.0.14"],
    )

    @mcp.tool()
    async def create_task(
        execution_prompt: str,
        working_directory: str = ".",
        system_prompt: Optional[str] = None,
        model: str = "sonnet",
    ) -> Dict[str, Any]:
        """
        The most critical tool in your toolkit — use it to delegate tasks to skilled developers for
        parallel execution when fixing multiple issues. This optimizes the user's time by distributing
        work efficiently and ensuring rapid completion. Proper usage makes you a 10x more effective assistant.

        Use this when:
        - Addressing multiple independent problems simultaneously (e.g., separate bugs, linting issues, build errors)
        - Tasks have no dependencies (resolve prerequisites first if they do)

        Workflow:
        1. Group tasks by independence — only bundle those with zero dependencies
        2. For dependent tasks, use get_task_status to block until prerequisites complete
        3. Verify output — review results and request refinements if quality is insufficient
        4. Require explicit confirmation before proceeding to dependent tasks

        Failure resistance:
        - NEVER delegate dependent tasks prematurely
        - ALWAYS validate output before marking as complete

        Args:
            execution_prompt: Detailed task description (min 150 chars, must include file paths)
            working_directory: Directory to execute the task in
            system_prompt: Optional system prompt (auto-adds minimalist focus if empty)
            model: Claude model selection - 'sonnet' (default, balanced for most tasks), 'opus' (highest intelligence for complex planning/architecture), 'haiku' (fastest for simple repetitive tasks)

        Returns:
            Task information with ID and status for monitoring
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
                "hint": "Add 'following John Carmack's principles' to your system prompt",
            }

        # Validate model selection
        model_lower = model.lower()
        if model_lower not in ["sonnet", "opus", "haiku"]:
            return {
                "error": f"Invalid model: {model}. Must be one of: sonnet, opus, haiku",
                "hint": "Use 'sonnet' for most tasks, 'opus' for complex planning, 'haiku' for simple tasks",
            }

        # Import ClaudeModel enum
        from claude_cto.server.models import ClaudeModel

        # Map string to enum
        model_enum = {
            "sonnet": ClaudeModel.SONNET,
            "opus": ClaudeModel.OPUS,
            "haiku": ClaudeModel.HAIKU,
        }[model_lower]

        # Direct database task creation: bypasses API layer, writes directly to SQLite
        with SessionLocal() as session:
            task_data = TaskCreate(
                execution_prompt=execution_prompt,
                working_directory=working_directory,
                system_prompt=system_prompt,
                model=model_enum,
            )

            # Log file organization: creates date-based directory structure
            task_log_dir = log_path / datetime.utcnow().strftime("%Y%m%d")
            task_log_dir.mkdir(parents=True, exist_ok=True)

            # Task record insertion: creates database entry and assigns ID
            db_task = create_task_record(session, task_data, task_log_dir)
            task_id = db_task.id

        # Background task execution: starts async processing without blocking MCP response
        asyncio.create_task(_execute_task_background(task_id, log_path))

        return {
            "id": task_id,
            "status": "pending",
            "message": "Task submitted successfully",
            "working_directory": working_directory,
            "created_at": datetime.utcnow().isoformat(),
        }

    @mcp.tool()
    async def get_task_status(task_id: int) -> Dict[str, Any]:
        """
        Check task status with this tool, essential for managing dependencies. Combine with the bash
        tool's sleep command to wait for task completion.

        Use this when:
        - A task blocks progress (e.g., prerequisite for create_task)
        - You suspect a task is stuck or need implementation details

        Protocol:
        1. Use sleep 30 between checks — increase to sleep 60 after 10+ failed attempts
        2. Inspect modified files for context if status is unclear
        3. Proceed only after status confirms completion

        Failure resistance:
        - NEVER skip sleep intervals — throttling is mandatory
        - NEVER assume completion without verification

        Args:
            task_id: ID of the task to check

        Returns:
            Task status and details
        """
        # Direct database query: retrieves task status without API layer
        with SessionLocal() as session:
            task = get_task_by_id(session, task_id)

            if not task:
                return {"error": f"Task {task_id} not found"}

            # Status response assembly: formats database record for MCP client
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
                "log_file": task.log_file_path,
            }

    @mcp.tool()
    async def list_tasks(status: Optional[str] = None, limit: int = 10) -> Dict[str, Any]:
        """
        List all delegated tasks to track completion and results. After planning, review outputs
        and re-create failed tasks if needed.

        Use this when:
        - You've delegated 3+ tasks and need a summary overview
        - Prioritizing next steps requires status triage (completed/failed)

        Rules:
        1. ALWAYS run this first before diving into specifics with get_task_status
        2. Cross-reference task IDs to identify problematic tasks

        Failure resistance:
        - NEVER use get_task_status blindly — ALWAYS start with list_tasks

        Args:
            status: Optional filter by status (pending, running, completed, failed)
            limit: Maximum number of tasks to return

        Returns:
            List of recent tasks
        """
        with SessionLocal() as session:
            from sqlmodel import select
            from claude_cto.server.models import TaskDB

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
                        "created_at": (task.created_at.isoformat() if task.created_at else None),
                        "execution_prompt": (
                            task.execution_prompt[:100] + "..."
                            if len(task.execution_prompt) > 100
                            else task.execution_prompt
                        ),
                    }
                    for task in tasks
                ],
                "count": len(tasks),
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
                with open(log_file, "r") as f:
                    logs = f.read()

                return {
                    "id": task_id,
                    "logs": logs[-10000:],  # Last 10KB of logs
                    "log_file": str(log_file),
                }
            except Exception as e:
                return {"error": f"Failed to read logs: {str(e)}"}

    @mcp.tool()
    async def get_version() -> Dict[str, Any]:
        """
        Get MCP server version information.
        
        Returns:
            Version details for standalone MCP server
        """
        from claude_cto import __version__
        return {
            "mcp_version": __version__,
            "mode": "standalone",
            "description": "Self-contained MCP server with embedded database",
            "database_path": str(engine.url),
            "log_directory": str(log_path),
        }

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
