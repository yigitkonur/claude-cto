"""
SOLE RESPONSIBILITY: Provides pure functions for transforming structured log messages
from the SDK (e.g., ContentBlocks) into human-readable strings.
"""

from typing import Optional
from claude_code_sdk.types import ContentBlock, ToolUseBlock, TextBlock, ToolResultBlock

# ThinkingBlock is available in SDK 0.0.20+
# For compatibility with older versions, we'll check dynamically
try:
    from claude_code_sdk.types import ThinkingBlock

    HAS_THINKING_BLOCK = True
except ImportError:
    HAS_THINKING_BLOCK = False
    ThinkingBlock = None


def format_content_block(block: ContentBlock) -> Optional[str]:
    """
    Transform any ContentBlock into a human-readable log string.
    Returns None for blocks that shouldn't be logged.
    """
    if isinstance(block, ToolUseBlock):
        return format_tool_use(block)
    elif HAS_THINKING_BLOCK and ThinkingBlock and isinstance(block, ThinkingBlock):
        # Log thinking blocks with a preview (SDK 0.0.20+)
        preview = block.thinking[:100] + "..." if len(block.thinking) > 100 else block.thinking
        return f"[thinking] {preview}"
    elif isinstance(block, TextBlock):
        # Log text responses with a preview
        preview = block.text[:100] + "..." if len(block.text) > 100 else block.text
        return f"[text] {preview}"
    elif isinstance(block, ToolResultBlock):
        # Log tool results
        if block.is_error:
            return f"[tool:result:error] Tool {block.tool_use_id} failed"
        else:
            return f"[tool:result:success] Tool {block.tool_use_id} completed"
    return None


def format_tool_use(block: ToolUseBlock) -> str:
    """
    Transform a ToolUseBlock into a minimalist, human-readable log string.
    Uses pattern matching for clarity and extensibility.
    """
    match block.name:
        case "Bash":
            command = block.input.get("command", "N/A")
            return f"[tool:bash] {command}"

        case "Edit" | "MultiEdit":
            file_path = block.input.get("file_path", "N/A")
            return f"[tool:edit] {file_path}"

        case "Write":
            file_path = block.input.get("file_path", "N/A")
            return f"[tool:write] {file_path}"

        case "Read":
            file_path = block.input.get("file_path", "N/A")
            return f"[tool:read] {file_path}"

        case "Grep":
            pattern = block.input.get("pattern", "N/A")
            return f"[tool:grep] {pattern}"

        case "Glob":
            pattern = block.input.get("pattern", "N/A")
            return f"[tool:glob] {pattern}"

        case "LS":
            path = block.input.get("path", "N/A")
            return f"[tool:ls] {path}"

        case "WebSearch":
            query = block.input.get("query", "N/A")
            return f"[tool:websearch] {query}"

        case "WebFetch":
            url = block.input.get("url", "N/A")
            return f"[tool:webfetch] {url}"

        case "TodoWrite":
            todos = block.input.get("todos", [])
            return f"[tool:todo] Managing {len(todos)} tasks"

        case "Task":
            description = block.input.get("description", "N/A")
            return f"[tool:task] {description}"

        case _:
            # Default case for unknown tools
            return f"[tool:{block.name}] {str(block.input)[:100]}"
