"""
Enhanced MCP proxy server with dependency and delay support.
Uses identifier-based task management for better tracking and dependency resolution.
"""

import os
import json
from typing import Optional, Dict, Any, List
from datetime import datetime

import httpx
from fastmcp import FastMCP


# Global orchestration tracker (in-memory for this session)
_active_orchestrations: Dict[str, Dict[str, Any]] = {}


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
        api_url = os.getenv("CLAUDE_WORKER_API_URL", "http://localhost:8000")
    
    # Ensure URL doesn't have trailing slash
    api_url = api_url.rstrip("/")
    
    # Create MCP server
    mcp = FastMCP(
        name="claude-worker-enhanced", 
        dependencies=["httpx>=0.25.0"]
    )
    
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
        
        # Check if this is part of an orchestration or standalone
        if depends_on or orchestration_group:
            # This task has dependencies or is part of a group - use orchestration
            
            # Get or create orchestration group
            if not orchestration_group:
                orchestration_group = f"auto_group_{datetime.utcnow().isoformat()}"
            
            if orchestration_group not in _active_orchestrations:
                _active_orchestrations[orchestration_group] = {
                    "tasks": [],
                    "identifier_map": {}
                }
            
            # Add this task to the orchestration
            task_def = {
                "identifier": task_identifier,
                "execution_prompt": execution_prompt,
                "working_directory": working_directory,
                "system_prompt": system_prompt,
                "model": model,
                "depends_on": depends_on,
                "initial_delay": wait_after_dependencies
            }
            
            _active_orchestrations[orchestration_group]["tasks"].append(task_def)
            
            # Check if we should submit the orchestration
            # (This is a simplified version - in production you'd want more sophisticated logic)
            if len(_active_orchestrations[orchestration_group]["tasks"]) >= 1:
                # Submit orchestration to API
                orchestration_data = {
                    "tasks": _active_orchestrations[orchestration_group]["tasks"]
                }
                
                async with httpx.AsyncClient() as client:
                    response = await client.post(
                        f"{api_url}/api/v1/orchestrations",
                        json=orchestration_data,
                        timeout=30.0,
                    )
                    
                    if response.status_code == 200:
                        result = response.json()
                        
                        # Store task ID mappings
                        for task in result["tasks"]:
                            _active_orchestrations[orchestration_group]["identifier_map"][
                                task["identifier"]
                            ] = task["task_id"]
                        
                        # Return info about this specific task
                        task_id = _active_orchestrations[orchestration_group]["identifier_map"][task_identifier]
                        
                        return {
                            "status": "created",
                            "task_identifier": task_identifier,
                            "task_id": task_id,
                            "orchestration_id": result["orchestration_id"],
                            "orchestration_group": orchestration_group,
                            "depends_on": depends_on,
                            "wait_after_dependencies": wait_after_dependencies,
                            "message": f"Task '{task_identifier}' created with dependencies {depends_on}" if depends_on else f"Task '{task_identifier}' created"
                        }
                    else:
                        return {
                            "error": f"Failed to create orchestration: {response.status_code}",
                            "details": response.text
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
                            "standalone": True
                        }
                    
                    return {
                        "status": "created",
                        "task_identifier": task_identifier,
                        "task_id": result["id"],
                        "working_directory": result["working_directory"],
                        "model": model,
                        "message": f"Independent task '{task_identifier}' created and running"
                    }
                else:
                    return {
                        "error": f"Failed to create task: {response.status_code}",
                        "details": response.text,
                    }
    
    @mcp.tool()
    async def get_task_status(
        task_identifier: str
    ) -> Dict[str, Any]:
        """
        Check task status using its identifier.
        
        Args:
            task_identifier: The identifier you used when creating the task
        
        Returns:
            Task status and details
        """
        # Look up task ID from identifier
        if task_identifier in _active_orchestrations:
            if isinstance(_active_orchestrations[task_identifier], dict):
                if "task_id" in _active_orchestrations[task_identifier]:
                    task_id = _active_orchestrations[task_identifier]["task_id"]
                else:
                    # Check in orchestration groups
                    for group_name, group_data in _active_orchestrations.items():
                        if "identifier_map" in group_data:
                            if task_identifier in group_data["identifier_map"]:
                                task_id = group_data["identifier_map"][task_identifier]
                                break
                    else:
                        return {
                            "error": f"Task identifier '{task_identifier}' not found",
                            "hint": "Check the identifier you used when creating the task"
                        }
        else:
            return {
                "error": f"Task identifier '{task_identifier}' not found",
                "hint": "Check the identifier you used when creating the task"
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
                    "task_identifier": task_identifier
                }
    
    @mcp.tool()
    async def submit_orchestration(
        orchestration_group: str
    ) -> Dict[str, Any]:
        """
        Submit all tasks in an orchestration group for execution.
        
        Use this after adding all tasks with the same orchestration_group.
        
        Args:
            orchestration_group: The group identifier used when creating tasks
        
        Returns:
            Orchestration details with all task mappings
        """
        if orchestration_group not in _active_orchestrations:
            return {
                "error": f"Orchestration group '{orchestration_group}' not found",
                "hint": "Create tasks with this orchestration_group first"
            }
        
        orchestration_data = {
            "tasks": _active_orchestrations[orchestration_group]["tasks"]
        }
        
        async with httpx.AsyncClient() as client:
            response = await client.post(
                f"{api_url}/api/v1/orchestrations",
                json=orchestration_data,
                timeout=30.0,
            )
            
            if response.status_code == 200:
                result = response.json()
                
                # Store task ID mappings
                for task in result["tasks"]:
                    _active_orchestrations[orchestration_group]["identifier_map"][
                        task["identifier"]
                    ] = task["task_id"]
                
                return {
                    "status": "submitted",
                    "orchestration_id": result["orchestration_id"],
                    "orchestration_group": orchestration_group,
                    "total_tasks": len(result["tasks"]),
                    "task_mappings": _active_orchestrations[orchestration_group]["identifier_map"],
                    "message": f"Orchestration submitted with {len(result['tasks'])} tasks"
                }
            else:
                return {
                    "error": f"Failed to submit orchestration: {response.status_code}",
                    "details": response.text
                }
    
    @mcp.tool()
    async def list_tasks(
        limit: int = 10
    ) -> Dict[str, Any]:
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
                
                return {
                    "tasks": tasks,
                    "count": len(tasks)
                }
            else:
                return {
                    "error": f"Failed to list tasks: {response.status_code}"
                }
    
    return mcp


# For backwards compatibility
def create_proxy_server(api_url: Optional[str] = None) -> FastMCP:
    """Alias for enhanced proxy server."""
    return create_enhanced_proxy_server(api_url)