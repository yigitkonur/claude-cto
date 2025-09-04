"""
Factory functions for creating MCP servers with mode detection.
Automatically selects standalone or proxy mode based on environment.
"""

import os
import sys
import logging
import asyncio
import httpx
from typing import Optional, Literal

from fastmcp import FastMCP
from .standalone import create_standalone_server
from .enhanced_proxy import create_enhanced_proxy_server

# Set up logging for better debugging
logging.basicConfig(level=logging.WARNING, format='%(asctime)s - %(levelname)s - %(message)s')


def is_rest_api_available(api_url: str = None) -> bool:
    """Simple health check to detect running server."""
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
    """Main factory with intelligent mode detection."""

    # Check environment for mode override
    env_mode = os.getenv("CLAUDE_CTO_MODE", "").lower()
    if env_mode in ["standalone", "proxy"]:
        mode = env_mode

    # Auto-detect mode if needed
    if mode == "auto":
        # Check if REST API is available
        if is_rest_api_available(api_url):
            mode = "proxy"
        else:
            mode = "standalone"

    # Create appropriate server
    if mode == "proxy":
        # Return enhanced proxy with dependency support
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


def validate_startup_config():
    """Validate configuration and provide auto-healing if needed."""
    try:
        from .auto_config import validate_config_paths, migrate_config_paths
        
        # Check for configuration issues
        issues = validate_config_paths()
        if issues:
            # Log issues but don't fail startup
            logging.warning("Configuration issues detected:")
            for issue in issues:
                logging.warning(f"  • {issue}")
            
            # Attempt automatic healing
            logging.info("Attempting automatic configuration repair...")
            try:
                files_fixed, messages = migrate_config_paths(dry_run=False)
                if files_fixed > 0:
                    logging.info(f"✓ Automatically fixed {files_fixed} configuration file(s)")
                    for message in messages:
                        if "✓" in message or "✅" in message:
                            logging.info(f"  {message}")
            except Exception as e:
                logging.warning(f"Auto-repair failed: {e}")
                
    except ImportError:
        # auto_config module not available, skip validation
        pass
    except Exception as e:
        # Don't let config validation break startup
        logging.warning(f"Config validation failed: {e}")


def run_stdio():
    """Entry point for claude-cto-mcp CLI command with robust error handling."""
    try:
        # Validate and potentially fix configuration issues
        validate_startup_config()
        
        # Initialize database and perform migrations
        from ..migrations.manager import run_migrations
        from pathlib import Path
        
        # Get database path (default to ~/.claude-cto/tasks.db)
        db_path = os.getenv("CLAUDE_CTO_DB_PATH", str(Path.home() / ".claude-cto" / "tasks.db"))
        db_url = f"sqlite:///{db_path}"
        
        run_migrations(db_url)
        
        # Create and run server
        server = create_mcp_server()
        asyncio.run(server.run_stdio_async())
        
    except Exception as e:
        logging.error(f"MCP server failed to start: {e}")
        
        # Try to provide helpful error information
        print(f"❌ Claude CTO MCP Server Error: {e}", file=sys.stderr)
        
        if "database" in str(e).lower() or "migration" in str(e).lower():
            print("🔧 Database issue detected. Try:", file=sys.stderr)
            print("   1. Delete ~/.claude-cto/tasks.db to recreate database", file=sys.stderr)
            print("   2. Check file permissions in ~/.claude-cto/", file=sys.stderr)
        
        if "import" in str(e).lower() or "module" in str(e).lower():
            print("🔧 Import issue detected. Try:", file=sys.stderr)
            print("   1. pip install --upgrade claude-cto", file=sys.stderr)
            print("   2. Check Python environment", file=sys.stderr)
        
        if "config" in str(e).lower() or "path" in str(e).lower():
            print("🔧 Configuration issue detected. Try:", file=sys.stderr)
            print("   1. python -m claude_cto.mcp.auto_config diagnose", file=sys.stderr)
            print("   2. python -m claude_cto.mcp.auto_config fix", file=sys.stderr)
            print("   3. Check if Python path still exists", file=sys.stderr)
        
        sys.exit(1)


def main():
    """Main entry point with argument parsing and auto-configuration."""
    import argparse
    
    parser = argparse.ArgumentParser(description="Claude CTO MCP Server")
    parser.add_argument("--mode", choices=["auto", "standalone", "proxy"], 
                       default="auto", help="Server mode")
    parser.add_argument("--api-url", help="REST API URL for proxy mode")
    parser.add_argument("--db-path", help="Database path for standalone mode") 
    parser.add_argument("--log-dir", help="Log directory for standalone mode")
    parser.add_argument("--configure", action="store_true", 
                       help="Run auto-configuration for Claude Code")
    parser.add_argument("--validate", action="store_true",
                       help="Validate configuration and exit")
    parser.add_argument("--fix-config", action="store_true",
                       help="Fix configuration issues and exit")
    
    args = parser.parse_args()
    
    if args.configure:
        from .auto_config import auto_configure
        success = auto_configure()
        sys.exit(0 if success else 1)
    
    if args.validate:
        from .auto_config import validate_config_paths
        issues = validate_config_paths()
        if issues:
            print("Configuration issues found:", file=sys.stderr)
            for issue in issues:
                print(f"  • {issue}", file=sys.stderr)
            sys.exit(1)
        else:
            print("✅ All configurations are valid")
            sys.exit(0)
    
    if args.fix_config:
        from .auto_config import auto_fix_configurations
        success = auto_fix_configurations()
        sys.exit(0 if success else 1)
    
    # Set environment variables from args
    if args.api_url:
        os.environ["CLAUDE_CTO_API_URL"] = args.api_url
    if args.db_path:
        os.environ["CLAUDE_CTO_DB_PATH"] = args.db_path
    if args.log_dir:
        os.environ["CLAUDE_CTO_LOG_DIR"] = args.log_dir
    
    run_stdio()


if __name__ == "__main__":
    # Run with auto-detection when executed directly
    if len(sys.argv) > 1:
        main()  # Use argument parsing
    else:
        run_stdio()  # Direct execution
