"""
SOLE RESPONSIBILITY: Provides a pure function for transforming structured log messages 
from the SDK (e.g., ToolUseBlock) into human-readable strings.
"""

from claude_code_sdk.types import ToolUseBlock


def format_tool_use(block: ToolUseBlock) -> str:
    """
    Transform a ToolUseBlock into a minimalist, human-readable log string.
    Uses pattern matching for clarity and extensibility.
    """
    match block.name:
        case "Bash":
            command = block.input.get("command", "N/A")
            return f"[tool:bash] {command}"
        
        case "Edit":
            file_path = block.input.get("file_path", "N/A")
            return f"[tool:edit] {file_path}"
        
        case "Write":
            file_path = block.input.get("file_path", "N/A")
            return f"[tool:write] {file_path}"
        
        case "Read":
            file_path = block.input.get("file_path", "N/A")
            return f"[tool:read] {file_path}"
        
        case "Search":
            query = block.input.get("query", "N/A")
            return f"[tool:search] {query}"
        
        case "List":
            path = block.input.get("path", "N/A")
            return f"[tool:list] {path}"
        
        case _:
            # Default case for unknown tools
            return f"[tool:{block.name}] {str(block.input)[:100]}"