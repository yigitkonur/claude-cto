"""
Enhanced MCP proxy server with dependency and delay support.
Uses identifier-based task management for better tracking and dependency resolution.
"""

import os
from typing import Optional, Dict, Any, List
from datetime import datetime, timedelta

import httpx
from fastmcp import FastMCP


# In-memory orchestration staging: tracks task groups before submission to API server
_active_orchestrations: Dict[str, Dict[str, Any]] = {}
# Cleanup timer: tracks last memory cleanup to prevent resource leaks
_last_cleanup: datetime = datetime.utcnow()


def _cleanup_old_orchestrations(max_age_hours: int = 24) -> None:
    """
    Periodic memory cleanup to prevent orchestration data accumulation.
    Critical for long-running MCP sessions - removes orchestrations older than max_age_hours.
    """
    global _active_orchestrations, _last_cleanup

    current_time = datetime.utcnow()

    # Rate limiting: only cleanup once per hour to avoid excessive processing
    if (current_time - _last_cleanup).total_seconds() < 3600:
        return

    _last_cleanup = current_time
    cutoff_time = current_time - timedelta(hours=max_age_hours)

    # Timestamp-based pruning: identifies stale orchestration entries for removal
    to_remove = []
    for key, value in _active_orchestrations.items():
        if isinstance(value, dict):
            # Check if it has a timestamp
            if "created_at" in value:
                created_at = datetime.fromisoformat(value["created_at"])
                if created_at < cutoff_time:
                    to_remove.append(key)
            # For legacy entries without timestamp, check if submitted
            elif "identifier_map" in value and len(value.get("identifier_map", {})) > 0:
                # Assume submitted orchestrations older than 24h can be cleaned
                to_remove.append(key)

    # Memory reclamation: removes stale entries from global dictionary
    for key in to_remove:
        del _active_orchestrations[key]


def create_enhanced_proxy_server(api_url: Optional[str] = None) -> FastMCP:
    """
    Create an enhanced proxy MCP server with dependency support.

    Args:
        api_url: URL of the REST API server (defaults to environment or localhost)

    Returns:
        FastMCP server instance with enhanced capabilities
    """

    # Get API URL from parameter, environment, or default
    if not api_url:
        api_url = os.getenv("CLAUDE_CTO_API_URL", "http://localhost:8000")

    # Ensure URL doesn't have trailing slash
    api_url = api_url.rstrip("/")

    # Create MCP server
    mcp = FastMCP(name="claude-cto-enhanced", dependencies=["httpx>=0.25.0"])

    @mcp.tool()
    async def create_task(
        task_identifier: str,  # REQUIRED - unique identifier for this task
        execution_prompt: str,
        working_directory: str = ".",
        system_prompt: Optional[str] = None,
        model: str = "sonnet",
        depends_on: Optional[List[str]] = None,  # Optional task identifiers to wait for
        wait_after_dependencies: Optional[float] = None,  # Optional delay in seconds after deps complete
        orchestration_group: Optional[str] = None,  # Optional group identifier for related tasks
    ) -> Dict[str, Any]:
        """
        Create a task with optional dependencies and delays - the ultimate delegation tool.

        This enhanced version supports task dependencies, allowing you to create complex workflows
        where tasks automatically wait for other tasks to complete before starting.

        IDENTIFIER SYSTEM:
        - task_identifier (REQUIRED): A unique name you choose for this task (e.g., "analyze_code", "fix_bug_123")
        - Use descriptive identifiers that explain what the task does
        - Identifiers are used to reference tasks in dependencies

        DEPENDENCY SYSTEM (Optional):
        - depends_on: List of task_identifier strings this task should wait for
        - Tasks will only start after ALL dependencies complete successfully
        - If any dependency fails, this task will be skipped
        - Use for sequential workflows: analyze → fix → test → document

        DELAY SYSTEM (Optional):
        - wait_after_dependencies: Seconds to wait AFTER all dependencies complete
        - Useful for: giving time for file systems to sync, APIs to update, caches to clear
        - Only applies if dependencies are specified; otherwise ignored

        WHEN TO USE DEPENDENCIES:
        1. Multi-step workflows where order matters:
           - First task: analyze code (identifier: "analyze")
           - Second task: fix issues found (identifier: "fix", depends_on: ["analyze"])
           - Third task: run tests (identifier: "test", depends_on: ["fix"])

        2. Parallel work with a final aggregation:
           - Task A: analyze Python files (identifier: "python_analysis")
           - Task B: analyze JS files (identifier: "js_analysis")
           - Task C: combine reports (identifier: "report", depends_on: ["python_analysis", "js_analysis"])

        3. Ensuring prerequisites:
           - Task 1: install dependencies (identifier: "install")
           - Task 2: run build (identifier: "build", depends_on: ["install"])

        WHEN NOT TO USE DEPENDENCIES:
        - Tasks are truly independent (can run in any order)
        - You want maximum parallelization
        - Tasks operate on different codebases/directories

        Args:
            task_identifier: Unique identifier for this task (required, e.g., "refactor_auth")
            execution_prompt: Detailed task description (min 150 chars, must include file paths)
            working_directory: Directory to execute the task in
            system_prompt: Optional system prompt (auto-adds Carmack principles if empty)
            model: 'sonnet' (balanced), 'opus' (complex), 'haiku' (simple/fast)
            depends_on: Optional list of task_identifier strings to wait for
            wait_after_dependencies: Optional seconds to wait after dependencies complete
            orchestration_group: Optional group name to associate related tasks

        Returns:
            Task information with identifier, status, and dependency details

        Examples:
            # Independent task (no dependencies):
            create_task(
                task_identifier="analyze_project",
                execution_prompt="Analyze all Python files in /project for complexity",
                working_directory="/project"
            )

            # Dependent task (waits for analyze_project):
            create_task(
                task_identifier="fix_complexity",
                execution_prompt="Refactor complex functions identified in /project",
                working_directory="/project",
                depends_on=["analyze_project"],
                wait_after_dependencies=2.0  # Wait 2 seconds after analysis
            )
        """

        # Apply default system prompt if not provided
        if not system_prompt:
            system_prompt = (
                "You are a helpful assistant following John Carmack's principles "
                "of simplicity and minimalism in software development."
            )

        # MCP strict validation
        if "John Carmack" not in system_prompt:
            return {
                "error": "System prompt must contain 'John Carmack' for MCP compliance",
                "hint": "Add 'following John Carmack's principles' to your system prompt",
            }

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
                "hint": "Mention specific files or directories in your prompt",
            }

        # Proactive memory management: ensures long-running sessions don't leak memory
        _cleanup_old_orchestrations()

        # Orchestration vs standalone decision: determines whether task needs dependency management
        if depends_on or orchestration_group:
            # Complex workflow path: task has dependencies or belongs to a group

            # Auto-group generation: creates unique group ID if not specified
            if not orchestration_group:
                orchestration_group = f"auto_group_{datetime.utcnow().isoformat()}"

            # Group initialization: creates new orchestration entry if doesn't exist
            if orchestration_group not in _active_orchestrations:
                _active_orchestrations[orchestration_group] = {
                    "tasks": [],
                    "identifier_map": {},
                    "created_at": datetime.utcnow().isoformat(),
                }

            # Dependency validation: ensures all referenced tasks exist in same group
            if depends_on:
                existing_identifiers = [t["identifier"] for t in _active_orchestrations[orchestration_group]["tasks"]]
                for dep in depends_on:
                    if dep not in existing_identifiers:
                        return {
                            "error": f"Dependency '{dep}' not found in orchestration group '{orchestration_group}'",
                            "hint": f"Create task '{dep}' first or ensure it's in the same orchestration_group",
                            "existing_tasks": existing_identifiers,
                        }

            # Task definition assembly: builds complete task specification for orchestration
            task_def = {
                "identifier": task_identifier,
                "execution_prompt": execution_prompt,
                "working_directory": working_directory,
                "system_prompt": system_prompt,
                "model": model,
                "depends_on": depends_on,
                "initial_delay": wait_after_dependencies,
            }

            # In-memory staging: adds task to orchestration queue (not yet submitted to API)
            _active_orchestrations[orchestration_group]["tasks"].append(task_def)

            # Deferred submission strategy: waits for explicit submit_orchestration call
            return {
                "status": "queued",
                "task_identifier": task_identifier,
                "orchestration_group": orchestration_group,
                "depends_on": depends_on,
                "wait_after_dependencies": wait_after_dependencies,
                "message": f"Task '{task_identifier}' queued in orchestration group '{orchestration_group}'. Call submit_orchestration('{orchestration_group}') when ready to execute.",
            }

        else:
            # No dependencies - create as standalone task
            task_data = {
                "execution_prompt": execution_prompt,
                "working_directory": working_directory,
                "system_prompt": system_prompt,
                "model": model,
            }

            async with httpx.AsyncClient() as client:
                response = await client.post(
                    f"{api_url}/api/v1/tasks",
                    json=task_data,
                    timeout=30.0,
                )

                if response.status_code == 200:
                    result = response.json()

                    # Store identifier mapping for potential future dependencies
                    if task_identifier not in _active_orchestrations:
                        _active_orchestrations[task_identifier] = {
                            "task_id": result["id"],
                            "standalone": True,
                            "created_at": datetime.utcnow().isoformat(),
                        }

                    return {
                        "status": "created",
                        "task_identifier": task_identifier,
                        "task_id": result["id"],
                        "working_directory": result["working_directory"],
                        "model": model,
                        "message": f"Independent task '{task_identifier}' created and running",
                    }
                else:
                    return {
                        "error": f"Failed to create task: {response.status_code}",
                        "details": response.text,
                    }

    @mcp.tool()
    async def get_task_status(task_identifier: str) -> Dict[str, Any]:
        """
        Check task status using its identifier.

        Args:
            task_identifier: The identifier you used when creating the task

        Returns:
            Task status and details
        """
        # Look up task ID from identifier
        task_id = None

        # First check if it's a standalone task
        if task_identifier in _active_orchestrations:
            data = _active_orchestrations[task_identifier]
            if isinstance(data, dict) and "task_id" in data:
                task_id = data["task_id"]

        # If not found, check orchestration groups
        if task_id is None:
            for group_name, group_data in _active_orchestrations.items():
                if isinstance(group_data, dict) and "identifier_map" in group_data:
                    if task_identifier in group_data["identifier_map"]:
                        task_id = group_data["identifier_map"][task_identifier]
                        break

        # If still not found, check if it's a queued task not yet submitted
        if task_id is None:
            for group_name, group_data in _active_orchestrations.items():
                if isinstance(group_data, dict) and "tasks" in group_data:
                    for task in group_data["tasks"]:
                        if task.get("identifier") == task_identifier:
                            return {
                                "status": "queued",
                                "task_identifier": task_identifier,
                                "orchestration_group": group_name,
                                "message": f"Task is queued but not yet submitted. Call submit_orchestration('{group_name}') to start execution.",
                            }

        if task_id is None:
            return {
                "error": f"Task identifier '{task_identifier}' not found",
                "hint": "Check the identifier you used when creating the task",
            }

        async with httpx.AsyncClient() as client:
            response = await client.get(
                f"{api_url}/api/v1/tasks/{task_id}",
                timeout=10.0,
            )

            if response.status_code == 200:
                task_data = response.json()
                task_data["task_identifier"] = task_identifier
                return task_data
            else:
                return {
                    "error": f"Failed to get task status: {response.status_code}",
                    "task_identifier": task_identifier,
                }

    @mcp.tool()
    async def submit_orchestration(orchestration_group: str) -> Dict[str, Any]:
        """
        Batch submission: sends all staged tasks in group to API server as complete orchestration.
        Critical step that transitions from in-memory staging to active execution.

        Use this after adding all tasks with the same orchestration_group.

        Args:
            orchestration_group: The group identifier used when creating tasks

        Returns:
            Orchestration details with all task mappings
        """
        # Group existence validation: ensures orchestration was properly staged
        if orchestration_group not in _active_orchestrations:
            return {
                "error": f"Orchestration group '{orchestration_group}' not found",
                "hint": "Create tasks with this orchestration_group first",
            }

        # Orchestration payload preparation: formats staged tasks for API submission
        orchestration_data = {"tasks": _active_orchestrations[orchestration_group]["tasks"]}

        # HTTP orchestration submission: sends complete DAG to API server
        async with httpx.AsyncClient() as client:
            response = await client.post(
                f"{api_url}/api/v1/orchestrations",
                json=orchestration_data,
                timeout=30.0,
            )

            if response.status_code == 200:
                result = response.json()

                # Task ID mapping storage: stores server-assigned IDs for status tracking
                for task in result["tasks"]:
                    _active_orchestrations[orchestration_group]["identifier_map"][task["identifier"]] = task["task_id"]

                return {
                    "status": "submitted",
                    "orchestration_id": result["orchestration_id"],
                    "orchestration_group": orchestration_group,
                    "total_tasks": len(result["tasks"]),
                    "task_mappings": _active_orchestrations[orchestration_group]["identifier_map"],
                    "message": f"Orchestration submitted with {len(result['tasks'])} tasks",
                }
            else:
                return {
                    "error": f"Failed to submit orchestration: {response.status_code}",
                    "details": response.text,
                }

    @mcp.tool()
    async def list_tasks(limit: int = 10) -> Dict[str, Any]:
        """
        List recent tasks with their identifiers and statuses.

        Args:
            limit: Maximum number of tasks to return

        Returns:
            List of recent tasks
        """
        async with httpx.AsyncClient() as client:
            response = await client.get(
                f"{api_url}/api/v1/tasks",
                params={"limit": limit},
                timeout=10.0,
            )

            if response.status_code == 200:
                tasks = response.json()

                # Add identifier information if available
                for task in tasks:
                    task_id = task["id"]
                    # Search for identifier
                    for key, value in _active_orchestrations.items():
                        if isinstance(value, dict):
                            if value.get("task_id") == task_id:
                                task["task_identifier"] = key
                                break
                            elif "identifier_map" in value:
                                for ident, tid in value["identifier_map"].items():
                                    if tid == task_id:
                                        task["task_identifier"] = ident
                                        break

                return {"tasks": tasks, "count": len(tasks)}
            else:
                return {"error": f"Failed to list tasks: {response.status_code}"}

    @mcp.tool()
    async def clear_tasks() -> Dict[str, Any]:
        """
        Clear all completed and failed tasks from the system.
        Bulk cleanup operation following Carmack's minimalism.
        
        Use this when:
        - You have many completed tasks cluttering the list
        - Starting a fresh batch of work
        - Cleaning up after testing
        
        Safety: Only removes COMPLETED and FAILED tasks.
        Running and pending tasks are preserved.
        
        Returns:
            Number of tasks cleared
        """
        async with httpx.AsyncClient() as client:
            try:
                response = await client.post(f"{api_url}/api/v1/tasks/clear", timeout=10.0)
                
                if response.status_code == 200:
                    data = response.json()
                    return {
                        "success": True,
                        "deleted": data.get("deleted", 0),
                        "message": data.get("message", "Tasks cleared")
                    }
                else:
                    return {
                        "error": f"API error: {response.status_code}",
                        "detail": response.text
                    }
                    
            except httpx.ConnectError:
                return {
                    "error": "Cannot connect to REST API server",
                    "api_url": api_url,
                    "hint": "Ensure the server is running with: claude-cto server start"
                }
            except Exception as e:
                return {"error": f"Failed to clear tasks: {str(e)}"}

    @mcp.tool()
    async def delete_task(task_identifier: str) -> Dict[str, Any]:
        """
        Delete a single non-running task by identifier or ID.
        
        Use this when:
        - Removing a specific failed task
        - Cleaning up individual test tasks
        - Managing task list selectively
        
        Safety: Cannot delete RUNNING or PENDING tasks.
        
        Args:
            task_identifier: Task identifier or numeric ID
            
        Returns:
            Success status
        """
        # Check if identifier is a numeric ID or a string identifier
        task_id = None
        
        # First try to parse as numeric ID
        try:
            task_id = int(task_identifier)
        except ValueError:
            # Search in our identifier map
            for key, value in _active_orchestrations.items():
                if key == task_identifier:
                    if isinstance(value, dict):
                        task_id = value.get("task_id")
                        break
        
        if not task_id:
            return {
                "error": "Task not found",
                "identifier": task_identifier,
                "hint": "Provide a valid task ID or identifier"
            }
        
        async with httpx.AsyncClient() as client:
            try:
                response = await client.delete(f"{api_url}/api/v1/tasks/{task_id}", timeout=10.0)
                
                if response.status_code == 200:
                    data = response.json()
                    # Clean up from our identifier map if present
                    to_remove = []
                    for key, value in _active_orchestrations.items():
                        if isinstance(value, dict) and value.get("task_id") == task_id:
                            to_remove.append(key)
                    for key in to_remove:
                        del _active_orchestrations[key]
                    
                    return {
                        "success": True,
                        "message": data.get("message", f"Task {task_id} deleted")
                    }
                elif response.status_code == 400:
                    return {
                        "error": "Cannot delete task",
                        "reason": "Task not found or still running",
                        "task_id": task_id
                    }
                else:
                    return {
                        "error": f"API error: {response.status_code}",
                        "detail": response.text
                    }
                    
            except httpx.ConnectError:
                return {
                    "error": "Cannot connect to REST API server",
                    "api_url": api_url,
                    "hint": "Ensure the server is running with: claude-cto server start"
                }
            except Exception as e:
                return {"error": f"Failed to delete task: {str(e)}"}

    return mcp


# For backwards compatibility
def create_proxy_server(api_url: Optional[str] = None) -> FastMCP:
    """Alias for enhanced proxy server."""
    return create_enhanced_proxy_server(api_url)
