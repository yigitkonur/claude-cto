"""
MCP tool for creating task orchestrations with dependencies.
This extends the MCP interface to support the full orchestration capabilities.
"""

from typing import List, Dict, Any
import httpx
from claude_cto.cli.config import get_server_url


async def create_mcp_orchestration(tasks: List[Dict[str, Any]]) -> Dict[str, Any]:
    """
    Create a task orchestration through MCP with dependency management.

    Args:
        tasks: List of task dictionaries, each containing:
            - identifier: Unique task identifier within orchestration
            - execution_prompt: The prompt to execute
            - working_directory: Directory to run the task in
            - system_prompt: System prompt (must contain "John Carmack")
            - model: Optional, defaults to "sonnet"
            - depends_on: Optional list of identifier strings this task depends on
            - initial_delay: Optional delay in seconds after dependencies complete

    Returns:
        Orchestration details including orchestration_id and task mappings

    Example:
        tasks = [
            {
                "identifier": "analyze",
                "execution_prompt": "Analyze the codebase structure in /project",
                "working_directory": "/project",
                "system_prompt": "You are following John Carmack's principles...",
                "model": "sonnet"
            },
            {
                "identifier": "refactor",
                "execution_prompt": "Refactor based on analysis in /project",
                "working_directory": "/project",
                "system_prompt": "You are following John Carmack's principles...",
                "model": "opus",
                "depends_on": ["analyze"],
                "initial_delay": 2.0
            }
        ]
    """
    # Validate all tasks have required fields
    for task in tasks:
        if not all(
            k in task
            for k in [
                "identifier",
                "execution_prompt",
                "working_directory",
                "system_prompt",
            ]
        ):
            raise ValueError(f"Task {task.get('identifier', 'unknown')} missing required fields")

        # Validate system prompt contains "John Carmack" (MCP requirement)
        if "John Carmack" not in task["system_prompt"]:
            raise ValueError(f"Task {task['identifier']} system_prompt must contain 'John Carmack'")

        # Validate execution prompt contains path-like string (MCP requirement)
        if "/" not in task["execution_prompt"] and "\\" not in task["execution_prompt"]:
            raise ValueError(f"Task {task['identifier']} execution_prompt must contain a path-like string")

    # Check for duplicate identifiers
    identifiers = [t["identifier"] for t in tasks]
    if len(identifiers) != len(set(identifiers)):
        raise ValueError("Task identifiers must be unique within orchestration")

    # Format for orchestration API
    orchestration_data = {
        "tasks": [
            {
                "identifier": task["identifier"],
                "execution_prompt": task["execution_prompt"],
                "working_directory": task["working_directory"],
                "system_prompt": task["system_prompt"],
                "model": task.get("model", "sonnet"),
                "depends_on": task.get("depends_on"),
                "initial_delay": task.get("initial_delay"),
            }
            for task in tasks
        ]
    }

    # Submit to orchestration API
    server_url = get_server_url()
    async with httpx.AsyncClient() as client:
        response = await client.post(f"{server_url}/api/v1/orchestrations", json=orchestration_data, timeout=30.0)
        response.raise_for_status()
        result = response.json()

    # Format response for MCP
    return {
        "orchestration_id": result["orchestration_id"],
        "status": result["status"],
        "total_tasks": result["total_tasks"],
        "task_mappings": {task["identifier"]: task["task_id"] for task in result["tasks"]},
        "message": f"Orchestration {result['orchestration_id']} created with {result['total_tasks']} tasks",
    }


async def get_mcp_orchestration_status(orchestration_id: int) -> Dict[str, Any]:
    """
    Get the status of an orchestration through MCP.

    Args:
        orchestration_id: The ID of the orchestration to check

    Returns:
        Current orchestration status and task details
    """
    server_url = get_server_url()
    async with httpx.AsyncClient() as client:
        response = await client.get(f"{server_url}/api/v1/orchestrations/{orchestration_id}", timeout=10.0)
        response.raise_for_status()
        return response.json()
