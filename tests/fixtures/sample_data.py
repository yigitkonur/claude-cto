"""
Sample data generators for testing.
"""

import json
import random
from datetime import datetime, timedelta
from typing import Dict, List, Any, Optional

from claude_cto.server.models import TaskStatus, ClaudeModel


class SampleDataGenerator:
    """Generates sample data for testing various scenarios."""
    
    @staticmethod
    def create_task_data(
        execution_prompt: str = "Analyze the project structure",
        working_directory: str = "/test/project",
        system_prompt: Optional[str] = None,
        model: ClaudeModel = ClaudeModel.SONNET
    ) -> Dict[str, Any]:
        """Create sample task data."""
        return {
            "execution_prompt": execution_prompt,
            "working_directory": working_directory,
            "system_prompt": system_prompt or "You are John Carmack, focused on clean code.",
            "model": model
        }
    
    @staticmethod
    def create_orchestration_data(
        task_count: int = 3,
        with_dependencies: bool = True,
        with_delays: bool = False
    ) -> Dict[str, Any]:
        """Create sample orchestration data."""
        tasks = []
        
        for i in range(task_count):
            task = {
                "identifier": f"task_{i}",
                "execution_prompt": f"Execute task {i} of the workflow",
                "working_directory": f"/project/module_{i}",
                "system_prompt": "You are John Carmack, building reliable systems.",
                "model": random.choice(list(ClaudeModel))
            }
            
            # Add dependencies
            if with_dependencies and i > 0:
                if i == 1:
                    task["depends_on"] = ["task_0"]
                elif i == 2:
                    task["depends_on"] = ["task_0", "task_1"]
                else:
                    # For larger orchestrations, depend on previous 1-2 tasks
                    deps = [f"task_{j}" for j in range(max(0, i-2), i)]
                    task["depends_on"] = deps
            
            # Add delays
            if with_delays and i > 0:
                task["initial_delay"] = random.uniform(0.5, 3.0)
            
            tasks.append(task)
        
        return {"tasks": tasks}
    
    @staticmethod
    def create_complex_dag() -> Dict[str, Any]:
        """Create a complex DAG with multiple paths and merge points."""
        return {
            "tasks": [
                # Initial setup tasks
                {
                    "identifier": "init_env",
                    "execution_prompt": "Initialize development environment",
                    "working_directory": "/project"
                },
                {
                    "identifier": "install_deps",
                    "execution_prompt": "Install dependencies",
                    "working_directory": "/project",
                    "depends_on": ["init_env"]
                },
                
                # Parallel build tasks
                {
                    "identifier": "build_frontend",
                    "execution_prompt": "Build frontend components",
                    "working_directory": "/project/frontend",
                    "depends_on": ["install_deps"]
                },
                {
                    "identifier": "build_backend",
                    "execution_prompt": "Build backend services",
                    "working_directory": "/project/backend",
                    "depends_on": ["install_deps"]
                },
                {
                    "identifier": "build_api",
                    "execution_prompt": "Build API layer",
                    "working_directory": "/project/api",
                    "depends_on": ["install_deps"]
                },
                
                # Parallel test tasks
                {
                    "identifier": "test_frontend",
                    "execution_prompt": "Run frontend tests",
                    "working_directory": "/project/frontend",
                    "depends_on": ["build_frontend"]
                },
                {
                    "identifier": "test_backend",
                    "execution_prompt": "Run backend tests",
                    "working_directory": "/project/backend",
                    "depends_on": ["build_backend"]
                },
                {
                    "identifier": "test_api",
                    "execution_prompt": "Run API tests",
                    "working_directory": "/project/api",
                    "depends_on": ["build_api"]
                },
                
                # Integration and deployment
                {
                    "identifier": "integration_test",
                    "execution_prompt": "Run integration tests",
                    "working_directory": "/project",
                    "depends_on": ["test_frontend", "test_backend", "test_api"],
                    "initial_delay": 2.0
                },
                {
                    "identifier": "deploy_staging",
                    "execution_prompt": "Deploy to staging environment",
                    "working_directory": "/project",
                    "depends_on": ["integration_test"],
                    "initial_delay": 5.0
                },
                {
                    "identifier": "smoke_test",
                    "execution_prompt": "Run smoke tests on staging",
                    "working_directory": "/project",
                    "depends_on": ["deploy_staging"]
                },
                {
                    "identifier": "deploy_production",
                    "execution_prompt": "Deploy to production",
                    "working_directory": "/project",
                    "depends_on": ["smoke_test"],
                    "initial_delay": 10.0
                }
            ]
        }
    
    @staticmethod
    def create_circular_dependency() -> Dict[str, Any]:
        """Create orchestration data with circular dependencies (for error testing)."""
        return {
            "tasks": [
                {
                    "identifier": "task_a",
                    "execution_prompt": "Task A",
                    "working_directory": "/project",
                    "depends_on": ["task_c"]
                },
                {
                    "identifier": "task_b", 
                    "execution_prompt": "Task B",
                    "working_directory": "/project",
                    "depends_on": ["task_a"]
                },
                {
                    "identifier": "task_c",
                    "execution_prompt": "Task C",
                    "working_directory": "/project",
                    "depends_on": ["task_b"]
                }
            ]
        }
    
    @staticmethod
    def create_invalid_dependencies() -> Dict[str, Any]:
        """Create orchestration data with invalid dependencies (for error testing)."""
        return {
            "tasks": [
                {
                    "identifier": "task_a",
                    "execution_prompt": "Task A",
                    "working_directory": "/project"
                },
                {
                    "identifier": "task_b",
                    "execution_prompt": "Task B", 
                    "working_directory": "/project",
                    "depends_on": ["task_a", "nonexistent_task"]
                }
            ]
        }
    
    @staticmethod
    def create_load_test_orchestration(size: int = 100) -> Dict[str, Any]:
        """Create a large orchestration for load testing."""
        tasks = []
        
        # Create root task
        tasks.append({
            "identifier": "root",
            "execution_prompt": "Initialize large workflow",
            "working_directory": "/project"
        })
        
        # Create layers of dependent tasks
        layer_size = 10
        for layer in range(1, size // layer_size + 1):
            for i in range(layer_size):
                task_id = f"layer_{layer}_task_{i}"
                
                # Tasks in first layer depend on root
                if layer == 1:
                    depends_on = ["root"]
                else:
                    # Tasks in later layers depend on previous layer
                    prev_layer_start = max(0, i - 2)
                    prev_layer_end = min(layer_size, i + 3)
                    depends_on = [f"layer_{layer-1}_task_{j}" for j in range(prev_layer_start, prev_layer_end)]
                
                task = {
                    "identifier": task_id,
                    "execution_prompt": f"Execute {task_id}",
                    "working_directory": f"/project/layer_{layer}",
                    "depends_on": depends_on,
                    "model": random.choice(["haiku", "sonnet"]) if i % 3 == 0 else "haiku"
                }
                
                tasks.append(task)
                
                if len(tasks) >= size:
                    break
            
            if len(tasks) >= size:
                break
        
        return {"tasks": tasks[:size]}
    
    @staticmethod
    def create_task_execution_data() -> Dict[str, Any]:
        """Create sample task execution data (messages, logs, etc.)."""
        return {
            "messages": [
                {
                    "type": "assistant",
                    "content": "I'll analyze the project structure and create a comprehensive test suite."
                },
                {
                    "type": "tool_use",
                    "name": "bash",
                    "input": {"command": "find /project -name '*.py' | head -10"}
                },
                {
                    "type": "tool_result", 
                    "output": "/project/main.py\n/project/models.py\n/project/utils.py"
                },
                {
                    "type": "assistant",
                    "content": "Based on the project structure, I'll create appropriate tests."
                }
            ],
            "final_summary": "Successfully analyzed project and created comprehensive test suite covering all modules.",
            "log_entries": [
                "Task started at 2024-01-01 10:00:00",
                "Analyzing project structure...",
                "Found 3 Python modules to test",
                "Creating test files...",
                "Task completed successfully"
            ]
        }
    
    @staticmethod
    def create_error_scenarios() -> Dict[str, Any]:
        """Create various error scenarios for testing."""
        return {
            "cli_not_found": {
                "error_type": "CLINotFoundError",
                "error_message": "Claude CLI not found in PATH",
                "recovery_suggestions": [
                    "Install Claude CLI: npm install -g @anthropic-ai/claude-code",
                    "Verify installation: claude --version"
                ]
            },
            "connection_error": {
                "error_type": "CLIConnectionError", 
                "error_message": "Failed to connect to Claude CLI",
                "recovery_suggestions": [
                    "Check if Claude CLI is running",
                    "Verify authentication: claude auth status"
                ]
            },
            "process_error": {
                "error_type": "ProcessError",
                "error_message": "Command execution failed",
                "exit_code": 127,
                "stderr": "command not found",
                "recovery_suggestions": [
                    "Check command syntax",
                    "Verify required tools are installed"
                ]
            },
            "json_decode_error": {
                "error_type": "CLIJSONDecodeError",
                "error_message": "Failed to parse JSON response",
                "recovery_suggestions": [
                    "Retry the operation",
                    "Update Claude CLI to latest version"
                ]
            }
        }
    
    @staticmethod
    def create_performance_test_data() -> Dict[str, Any]:
        """Create data for performance testing."""
        return {
            "concurrent_tasks": 50,
            "large_orchestration_size": 100,
            "stress_test_duration": 300,  # 5 minutes
            "memory_limit_mb": 1024,
            "expected_response_time_ms": 1000,
            "throughput_tasks_per_minute": 10
        }
    
    @staticmethod
    def create_mcp_test_data() -> Dict[str, Any]:
        """Create test data for MCP integration."""
        return {
            "create_task_payload": {
                "task_identifier": "test_task_1",
                "execution_prompt": "Test MCP task execution with proper identifier",
                "working_directory": "/test/mcp/project",
                "system_prompt": "You are John Carmack, implementing MCP integration tests.",
                "depends_on": [],
                "wait_after_dependencies": 1.0
            },
            "orchestration_payload": {
                "task_identifier": "orchestration_test",
                "execution_prompt": "Test orchestration through MCP interface",
                "working_directory": "/test/mcp/orchestration",
                "depends_on": ["test_task_1"],
                "wait_after_dependencies": 2.0
            },
            "standalone_payload": {
                "execution_prompt": "Test standalone MCP server functionality",
                "working_directory": "/test/mcp/standalone",
                "system_prompt": "You are John Carmack, testing standalone MCP functionality."
            }
        }


class PerformanceTestData:
    """Generates data for performance and load testing."""
    
    @staticmethod
    def generate_concurrent_task_data(count: int) -> List[Dict[str, Any]]:
        """Generate data for concurrent task testing."""
        tasks = []
        for i in range(count):
            tasks.append({
                "execution_prompt": f"Performance test task {i}",
                "working_directory": f"/test/perf/task_{i}",
                "system_prompt": "You are John Carmack, optimizing for performance.",
                "model": "haiku" if i % 3 == 0 else "sonnet"
            })
        return tasks
    
    @staticmethod
    def generate_memory_stress_data() -> Dict[str, Any]:
        """Generate data that could stress memory usage."""
        large_prompt = "Analyze this large codebase: " + "x" * 10000
        return {
            "execution_prompt": large_prompt,
            "working_directory": "/test/memory",
            "system_prompt": "You are John Carmack, handling large data efficiently."
        }
    
    @staticmethod
    def generate_network_stress_orchestration() -> Dict[str, Any]:
        """Generate orchestration that tests network resilience."""
        tasks = []
        for i in range(20):
            task = {
                "identifier": f"network_task_{i}",
                "execution_prompt": f"Network stress test task {i} - make multiple API calls",
                "working_directory": f"/test/network/task_{i}",
                "model": "haiku"  # Faster model for stress testing
            }
            
            if i > 0:
                task["depends_on"] = [f"network_task_{i-1}"]
                task["initial_delay"] = 0.1
            
            tasks.append(task)
        
        return {"tasks": tasks}