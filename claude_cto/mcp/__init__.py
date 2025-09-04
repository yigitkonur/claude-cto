"""
MCP (Model Context Protocol) server implementations for claude-cto.
Provides both standalone and proxy modes.
"""

from .standalone import create_standalone_server
from .proxy import create_proxy_server
from .enhanced_proxy import create_enhanced_proxy_server

# Import factory conditionally to avoid runpy warnings
def create_mcp_server(*args, **kwargs):
    """Create MCP server (lazy import to avoid runpy warnings)."""
    from .factory import create_mcp_server as _create_mcp_server
    return _create_mcp_server(*args, **kwargs)

__all__ = [
    "create_standalone_server",
    "create_proxy_server", 
    "create_enhanced_proxy_server",
    "create_mcp_server",
]
