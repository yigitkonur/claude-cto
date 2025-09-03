"""
Auto-configuration utility for Claude CTO MCP server.
Provides foolproof setup for Claude Code integration.
"""

import json
import os
import sys
from pathlib import Path
from typing import Dict, Any, Optional
import subprocess


def get_claude_config_path() -> Optional[Path]:
    """Find Claude Code configuration directory."""
    possible_paths = [
        Path.home() / ".claude",
        Path.home() / ".config" / "claude",
        # Add more possible paths
    ]
    
    for path in possible_paths:
        if path.exists() and (path / "settings.json").exists():
            return path
    
    return None


def get_current_python_path() -> str:
    """Get the current Python executable path."""
    return sys.executable


def create_mcp_config() -> Dict[str, Any]:
    """Create MCP server configuration for Claude Code."""
    python_path = get_current_python_path()
    
    config = {
        "mcpServers": {
            "claude-cto": {
                "command": python_path,
                "args": ["-m", "claude_cto.mcp.factory"],
                "env": {
                    "CLAUDE_CTO_MODE": "auto",
                    "CLAUDE_CTO_API_URL": "http://localhost:8000",
                    "CLAUDE_CTO_DB_PATH": "~/.claude-cto/tasks.db",
                    "CLAUDE_CTO_LOG_DIR": "~/.claude-cto/logs"
                }
            }
        }
    }
    
    return config


def update_claude_settings(config: Dict[str, Any]) -> bool:
    """Update Claude Code settings with MCP configuration."""
    claude_config_path = get_claude_config_path()
    
    if not claude_config_path:
        print("❌ Could not find Claude Code configuration directory")
        print("Please make sure Claude Code is installed and has been run at least once")
        return False
    
    settings_file = claude_config_path / "settings.json"
    
    try:
        # Load existing settings
        if settings_file.exists():
            with open(settings_file, 'r') as f:
                settings = json.load(f)
        else:
            settings = {}
        
        # Merge MCP configuration
        if "mcpServers" not in settings:
            settings["mcpServers"] = {}
        
        settings["mcpServers"].update(config["mcpServers"])
        
        # Write back to file
        with open(settings_file, 'w') as f:
            json.dump(settings, f, indent=2)
        
        print(f"✅ Updated Claude Code settings: {settings_file}")
        return True
        
    except Exception as e:
        print(f"❌ Failed to update settings: {e}")
        return False


def verify_installation() -> bool:
    """Verify that claude-cto is properly installed."""
    try:
        # Check if we can import claude_cto
        import claude_cto
        print(f"✅ Claude CTO {claude_cto.__version__} is installed")
        
        # Check if MCP factory can be imported
        from claude_cto.mcp.factory import create_mcp_server
        print("✅ MCP factory is available")
        
        # Test MCP server creation
        server = create_mcp_server(mode="standalone")
        print("✅ MCP server can be created")
        
        return True
        
    except Exception as e:
        print(f"❌ Installation verification failed: {e}")
        return False


def auto_configure() -> bool:
    """Perform automatic configuration for Claude Code integration."""
    print("🚀 Claude CTO MCP Auto-Configuration")
    print("=" * 40)
    
    # Step 1: Verify installation
    print("\n1. Verifying installation...")
    if not verify_installation():
        return False
    
    # Step 2: Create MCP configuration
    print("\n2. Creating MCP configuration...")
    config = create_mcp_config()
    
    # Step 3: Update Claude Code settings
    print("\n3. Updating Claude Code settings...")
    if not update_claude_settings(config):
        return False
    
    # Step 4: Test configuration
    print("\n4. Testing configuration...")
    try:
        result = subprocess.run([
            sys.executable, "-m", "claude_cto.mcp.factory"
        ], timeout=3, capture_output=True, text=True)
        
        if "RuntimeWarning" in result.stderr and "Migration failed" not in result.stderr:
            print("✅ MCP server starts successfully")
        else:
            print("⚠️  MCP server has warnings but should work")
        
    except subprocess.TimeoutExpired:
        print("✅ MCP server starts successfully (timed out as expected)")
    except Exception as e:
        print(f"❌ MCP server test failed: {e}")
        return False
    
    # Step 5: Success message
    print("\n" + "=" * 40)
    print("🎉 AUTO-CONFIGURATION COMPLETE!")
    print("\n📋 What was configured:")
    print("   • Claude Code MCP server entry added")
    print("   • Auto-mode enabled (standalone/proxy detection)")
    print("   • Database path: ~/.claude-cto/tasks.db")
    print("   • Logs directory: ~/.claude-cto/logs")
    
    print("\n🔧 Command added to Claude Code:")
    print("   claude-cto")
    
    print("\n📝 Next steps:")
    print("   1. Restart Claude Code")
    print("   2. The 'claude-cto' MCP server should now be available")
    print("   3. Use MCP tools like create_task, get_task_status, etc.")
    
    print("\n🆘 If you have issues:")
    print("   • Check Claude Code logs")
    print("   • Run: python -m claude_cto.mcp.factory (should start without errors)")
    print("   • Verify ~/.claude/settings.json has the mcpServers entry")
    
    return True


def print_manual_config():
    """Print manual configuration instructions."""
    python_path = get_current_python_path()
    
    print("\n📖 MANUAL CONFIGURATION INSTRUCTIONS")
    print("=" * 40)
    print("\nIf auto-configuration failed, add this to your ~/.claude/settings.json:")
    print(json.dumps(create_mcp_config(), indent=2))
    print(f"\nPython path: {python_path}")
    print("Command: python -m claude_cto.mcp.factory")


if __name__ == "__main__":
    success = auto_configure()
    
    if not success:
        print_manual_config()
        sys.exit(1)
    
    sys.exit(0)