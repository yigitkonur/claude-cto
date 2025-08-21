"""
Factory functions for creating MCP servers with mode detection.
Automatically selects standalone or proxy mode based on environment.
"""

import os
import httpx
from typing import Optional, Literal

from fastmcp import FastMCP
from .standalone import create_standalone_server
from .proxy import create_proxy_server
from .enhanced_proxy import create_enhanced_proxy_server


def is_rest_api_available(api_url: str = None) -> bool:
    """
    Check if REST API server is available.

    Args:
        api_url: URL to check (defaults to environment or localhost)

    Returns:
        True if API is available, False otherwise
    """
    if not api_url:
        api_url = os.getenv("CLAUDE_CTO_API_URL", "http://localhost:8000")

    try:
        response = httpx.get(f"{api_url}/health", timeout=2.0)
        return response.status_code == 200
    except Exception:
        return False


def create_mcp_server(
    mode: Literal["auto", "standalone", "proxy"] = "auto",
    api_url: Optional[str] = None,
    db_path: Optional[str] = None,
    log_dir: Optional[str] = None,
) -> FastMCP:
    """
    Create MCP server with intelligent mode detection.

    Args:
        mode: Server mode - "auto" (detect), "standalone", or "proxy"
        api_url: REST API URL for proxy mode
        db_path: Database path for standalone mode
        log_dir: Log directory for standalone mode

    Returns:
        FastMCP server instance

    Environment Variables:
        CLAUDE_CTO_MODE: Override mode (standalone/proxy/auto)
        CLAUDE_CTO_API_URL: REST API URL for proxy mode
        CLAUDE_CTO_DB: Database path for standalone mode
        CLAUDE_CTO_LOG_DIR: Log directory for standalone mode
    """

    # Check environment for mode override
    env_mode = os.getenv("CLAUDE_CTO_MODE", "").lower()
    if env_mode in ["standalone", "proxy"]:
        mode = env_mode

    # Auto-detect mode if needed
    if mode == "auto":
        # Check if REST API is available
        if is_rest_api_available(api_url):
            mode = "proxy"
            # Silent mode - MCP servers should not print to stdout
        else:
            mode = "standalone"
            # Silent mode - MCP servers should not print to stdout

    # Create appropriate server
    if mode == "proxy":
        # Use enhanced proxy with dependency support
        return create_enhanced_proxy_server(api_url)
    else:  # standalone
        # Get paths from environment if not provided
        if not db_path:
            db_path = os.getenv("CLAUDE_CTO_DB")
        if not log_dir:
            log_dir = os.getenv("CLAUDE_CTO_LOG_DIR")

        return create_standalone_server(db_path, log_dir)


# Default server instance for module-level import
mcp = create_mcp_server()


# Alternative named exports for explicit mode selection
def create_auto_server(**kwargs) -> FastMCP:
    """Create MCP server with auto-detection."""
    return create_mcp_server(mode="auto", **kwargs)


def create_standalone(**kwargs) -> FastMCP:
    """Create standalone MCP server."""
    return create_mcp_server(mode="standalone", **kwargs)


def create_proxy(**kwargs) -> FastMCP:
    """Create proxy MCP server."""
    return create_mcp_server(mode="proxy", **kwargs)


def run_stdio():
    """Entry point for claude-cto-mcp command."""
    import asyncio

    server = create_mcp_server()
    asyncio.run(server.run_stdio_async())


if __name__ == "__main__":
    # Run with auto-detection when executed directly
    run_stdio()
