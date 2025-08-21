"""
Example of how to add orchestration support to MCP.
This shows how the tool would be defined and used.
"""

# This would go in mcp/proxy.py or mcp/standalone.py:

@mcp.tool()
async def create_orchestration(
    tasks: List[Dict[str, Any]]
) -> Dict[str, Any]:
    """
    Create multiple tasks with dependencies - the ultimate delegation tool for complex workflows.
    
    This allows you to define a complete workflow where tasks can depend on each other.
    Tasks will automatically wait for their dependencies to complete before starting.
    
    Use this when:
    - You have multi-step workflows (analyze → fix → test → document)
    - Tasks must run in specific order
    - Some tasks can run in parallel while others must wait
    
    Parameters:
        tasks: List of task definitions, each containing:
            - identifier: Unique name for this task (used for dependencies)
            - execution_prompt: What the task should do (must mention files/paths)
            - working_directory: Where to run the task
            - system_prompt: Optional, defaults to Carmack principles
            - model: Optional, defaults to "sonnet" (can be "opus", "haiku")
            - depends_on: Optional list of task identifiers this task waits for
            - initial_delay: Optional seconds to wait after dependencies complete
    
    Example:
        tasks=[
            {
                "identifier": "analyze",
                "execution_prompt": "Analyze all Python files in /project for complexity",
                "working_directory": "/project",
                "model": "sonnet"
            },
            {
                "identifier": "refactor",
                "execution_prompt": "Refactor complex functions found in /project",
                "working_directory": "/project",
                "depends_on": ["analyze"],  # Waits for analyze to complete
                "model": "opus"
            },
            {
                "identifier": "test",
                "execution_prompt": "Write tests for refactored code in /project",
                "working_directory": "/project",
                "depends_on": ["refactor"],  # Waits for refactor to complete
                "initial_delay": 2.0,  # Extra 2 second delay
                "model": "sonnet"
            }
        ]
    
    Returns:
        Dictionary with orchestration_id and task details
    """
    # Implementation here (using the code from orchestration_tool.py)
    pass


# How Claude would use this tool internally when user asks for complex work:

# User says: "Refactor my codebase to use type hints and add tests"

# Claude would call:
result = await create_orchestration(tasks=[
    {
        "identifier": "analyze_types",
        "execution_prompt": "Analyze all Python files in /Users/john/project and identify missing type hints",
        "working_directory": "/Users/john/project",
        "model": "sonnet"
    },
    {
        "identifier": "add_types",
        "execution_prompt": "Add comprehensive type hints to all functions in /Users/john/project",
        "working_directory": "/Users/john/project",
        "depends_on": ["analyze_types"],
        "model": "opus"  # Using opus for complex refactoring
    },
    {
        "identifier": "validate_types",
        "execution_prompt": "Run mypy to validate all type hints in /Users/john/project",
        "working_directory": "/Users/john/project",
        "depends_on": ["add_types"],
        "model": "haiku"  # Simple validation task
    },
    {
        "identifier": "write_tests",
        "execution_prompt": "Write comprehensive pytest tests for all modules in /Users/john/project",
        "working_directory": "/Users/john/project",
        "depends_on": ["add_types"],  # Can run parallel with validate_types
        "model": "sonnet"
    },
    {
        "identifier": "run_tests",
        "execution_prompt": "Run pytest and ensure all tests pass in /Users/john/project",
        "working_directory": "/Users/john/project",
        "depends_on": ["write_tests", "validate_types"],  # Waits for both
        "initial_delay": 1.0,
        "model": "haiku"
    }
])

# Claude would then say:
# "I've created an orchestration with 5 tasks that will:
#  1. First analyze your code for missing type hints
#  2. Add type hints based on the analysis
#  3. Then in parallel: validate the types with mypy AND write tests
#  4. Finally run all tests to ensure everything works
#
# The orchestration ID is 7. Tasks will run automatically as their dependencies complete."