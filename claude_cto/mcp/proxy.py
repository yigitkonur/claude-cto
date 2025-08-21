"""
Proxy MCP server that connects to REST API server.
This mode is for users who want MCP interface but with centralized task management.
"""

import os
from typing import Optional, Dict, Any

import httpx
from fastmcp import FastMCP


def create_proxy_server(api_url: Optional[str] = None) -> FastMCP:
    """
    Create a proxy MCP server that connects to REST API.

    Args:
        api_url: URL of the REST API server (defaults to environment or localhost)

    Returns:
        FastMCP server instance
    """

    # Get API URL from parameter, environment, or default
    if not api_url:
        api_url = os.getenv("CLAUDE_CTO_API_URL", "http://localhost:8000")

    # Ensure URL doesn't have trailing slash
    api_url = api_url.rstrip("/")

    # Create MCP server
    mcp = FastMCP(name="claude-cto-proxy", dependencies=["httpx>=0.25.0"])

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
                "of simplicity and minimalism in software development."
            )

        # MCP strict validation: must contain "John Carmack"
        if "John Carmack" not in system_prompt:
            return {
                "error": "System prompt must contain 'John Carmack' for MCP compliance",
                "hint": "Add 'following John Carmack's principles' to your system prompt",
            }

        # Additional MCP validations
        if len(system_prompt) < 75 or len(system_prompt) > 500:
            return {
                "error": "System prompt must be between 75 and 500 characters",
                "current_length": len(system_prompt),
            }

        if len(execution_prompt) < 150:
            return {
                "error": "Execution prompt must be at least 150 characters",
                "current_length": len(execution_prompt),
                "hint": "Provide more detail about the task",
            }

        if "/" not in execution_prompt and "\\" not in execution_prompt:
            return {
                "error": "Execution prompt must contain a path-like string",
                "hint": "Mention a file path or directory in your prompt",
            }

        # Validate model selection
        model_lower = model.lower()
        if model_lower not in ["sonnet", "opus", "haiku"]:
            return {
                "error": f"Invalid model: {model}. Must be one of: sonnet, opus, haiku",
                "hint": "Use 'sonnet' for most tasks, 'opus' for complex planning, 'haiku' for simple tasks",
            }

        # Submit to REST API (using MCP endpoint for strict validation)
        async with httpx.AsyncClient() as client:
            try:
                response = await client.post(
                    f"{api_url}/api/v1/mcp/tasks",
                    json={
                        "execution_prompt": execution_prompt,
                        "working_directory": working_directory,
                        "system_prompt": system_prompt,
                        "model": model_lower,
                    },
                    timeout=30.0,
                )

                if response.status_code == 200:
                    data = response.json()
                    return {
                        "id": data["id"],
                        "status": data["status"],
                        "created_at": data["created_at"],
                        "message": "Task submitted successfully to REST API",
                    }
                else:
                    return {
                        "error": f"API error: {response.status_code}",
                        "detail": response.text,
                    }

            except httpx.ConnectError:
                return {
                    "error": "Cannot connect to REST API server",
                    "api_url": api_url,
                    "hint": "Ensure the server is running with: claude-cto server start",
                }
            except Exception as e:
                return {"error": f"Failed to submit task: {str(e)}", "api_url": api_url}

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
        async with httpx.AsyncClient() as client:
            try:
                response = await client.get(
                    f"{api_url}/api/v1/tasks/{task_id}", timeout=10.0
                )

                if response.status_code == 200:
                    data = response.json()
                    return {
                        "id": data["id"],
                        "status": data["status"],
                        "created_at": data.get("created_at"),
                        "started_at": data.get("started_at"),
                        "ended_at": data.get("ended_at"),
                        "last_action": data.get("last_action_cache"),
                        "final_summary": data.get("final_summary"),
                        "error_message": data.get("error_message"),
                    }
                elif response.status_code == 404:
                    return {"error": f"Task {task_id} not found"}
                else:
                    return {
                        "error": f"API error: {response.status_code}",
                        "detail": response.text,
                    }

            except httpx.ConnectError:
                return {
                    "error": "Cannot connect to REST API server",
                    "api_url": api_url,
                }
            except Exception as e:
                return {"error": f"Failed to get task status: {str(e)}"}

    @mcp.tool()
    async def list_tasks(limit: int = 10) -> Dict[str, Any]:
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
            limit: Maximum number of tasks to return

        Returns:
            List of recent tasks
        """
        async with httpx.AsyncClient() as client:
            try:
                response = await client.get(
                    f"{api_url}/api/v1/tasks", params={"limit": limit}, timeout=10.0
                )

                if response.status_code == 200:
                    tasks = response.json()
                    # Handle None or non-list responses
                    if not tasks or not isinstance(tasks, list):
                        tasks = []
                    return {
                        "tasks": [
                            {
                                "id": task["id"],
                                "status": task["status"],
                                "created_at": task.get("created_at"),
                                "last_action": (task.get("last_action_cache") or "")[
                                    :100
                                ],
                            }
                            for task in tasks[:limit]
                        ],
                        "count": len(tasks),
                        "api_url": api_url,
                    }
                else:
                    return {
                        "error": f"API error: {response.status_code}",
                        "detail": response.text,
                    }

            except httpx.ConnectError:
                return {
                    "error": "Cannot connect to REST API server",
                    "api_url": api_url,
                    "hint": "Ensure the server is running with: claude-cto server start",
                }
            except Exception as e:
                return {"error": f"Failed to list tasks: {str(e)}"}

    @mcp.tool()
    async def check_api_health() -> Dict[str, Any]:
        """
        Check if REST API server is available.

        Returns:
            API health status
        """
        async with httpx.AsyncClient() as client:
            try:
                response = await client.get(f"{api_url}/health", timeout=5.0)

                if response.status_code == 200:
                    data = response.json()
                    return {
                        "status": "healthy",
                        "api_url": api_url,
                        "service": data.get("service", "claude-cto"),
                    }
                else:
                    return {
                        "status": "unhealthy",
                        "api_url": api_url,
                        "status_code": response.status_code,
                    }

            except httpx.ConnectError:
                return {
                    "status": "offline",
                    "api_url": api_url,
                    "error": "Cannot connect to REST API server",
                    "hint": "Start server with: claude-cto server start",
                }
            except Exception as e:
                return {"status": "error", "api_url": api_url, "error": str(e)}

    return mcp


# Module-level server instance for fastmcp CLI
mcp = create_proxy_server()

if __name__ == "__main__":
    # Run as stdio server
    import asyncio

    asyncio.run(mcp.run_stdio_async())
