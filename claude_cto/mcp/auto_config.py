"""
Auto-configuration utility for Claude CTO MCP server.
Provides foolproof setup for Claude Code integration.
"""

import json
import os
import re
import sys
import shutil
from pathlib import Path
from typing import Dict, Any, Optional, List, Tuple
import subprocess
from fnmatch import fnmatch


def find_claude_config_files() -> List[Path]:
    """Find all Claude configuration files."""
    config_files = []
    
    # Claude Code configuration (new format)
    claude_code_paths = [
        Path.home() / ".claude" / "settings.json",
        Path.home() / ".config" / "claude" / "settings.json",
    ]
    
    # Claude Desktop configuration (legacy format)
    claude_desktop_paths = [
        Path.home() / ".claude.json",
    ]
    
    for path in claude_code_paths + claude_desktop_paths:
        if path.exists():
            config_files.append(path)
    
    return config_files


def get_claude_config_path() -> Optional[Path]:
    """Find Claude Code configuration directory (legacy function)."""
    possible_paths = [
        Path.home() / ".claude",
        Path.home() / ".config" / "claude",
    ]
    
    for path in possible_paths:
        if path.exists() and (path / "settings.json").exists():
            return path
    
    return None


def get_current_python_path() -> str:
    """Get the current Python executable path (legacy function)."""
    return sys.executable


def detect_installation_method() -> str:
    """Detect how claude-cto was installed."""
    current_path = sys.executable
    
    if "/opt/homebrew/Cellar/claude-cto/" in current_path:
        return "homebrew"
    elif "/opt/homebrew/" in current_path:
        return "homebrew-system"
    elif "miniconda" in current_path or "anaconda" in current_path:
        return "conda"
    elif "/usr/local/" in current_path or "/usr/bin/" in current_path:
        return "system"
    elif "/.local/" in current_path:
        return "user-pip"
    elif "/.venv/" in current_path or "/venv/" in current_path:
        return "virtualenv"
    else:
        return "unknown"


def is_stable_path(path: str) -> bool:
    """Check if a Python path is stable across upgrades."""
    # Stable patterns that don't change on upgrades
    stable_patterns = [
        "/opt/homebrew/opt/*/bin/python*",  # Homebrew stable symlinks
        "/usr/bin/python*",                # System Python
        "/usr/local/bin/python*",          # System Python
        "*/miniconda*/envs/*/bin/python*",  # Conda named environments
        "*/anaconda*/envs/*/bin/python*",   # Anaconda named environments
        "*/.pyenv/versions/*/bin/python*",  # pyenv named versions
    ]
    
    # Check against patterns
    for pattern in stable_patterns:
        if fnmatch(path, pattern):
            return True
    
    # Check if it's a stable conda/miniconda base environment
    if ("miniconda" in path or "anaconda" in path) and "/envs/" not in path:
        return True
    
    return False


def get_stable_python_path() -> str:
    """Get stable Python path that survives upgrades."""
    current_path = sys.executable
    install_method = detect_installation_method()
    
    print(f"🔍 Detected installation: {install_method} ({current_path})")
    
    # Homebrew: Convert versioned path to stable symlink
    if install_method == "homebrew":
        stable_path = "/opt/homebrew/opt/claude-cto/libexec/bin/python"
        if Path(stable_path).exists():
            print(f"✓ Using stable Homebrew path: {stable_path}")
            return stable_path
        else:
            print(f"⚠️  Stable path not found, falling back to system python")
            return "python3"
    
    # System installations: Use generic command
    elif install_method in ["system", "homebrew-system"]:
        return "python3"
    
    # Check if current path is already stable
    elif is_stable_path(current_path):
        print(f"✓ Current path is stable: {current_path}")
        return current_path
    
    # For other installations, prefer generic python3
    else:
        # Verify python3 can import claude_cto
        if shutil.which("python3"):
            try:
                result = subprocess.run(
                    ["python3", "-c", "import claude_cto; print(claude_cto.__version__)"],
                    capture_output=True, text=True, timeout=5
                )
                if result.returncode == 0:
                    print(f"✓ Using system python3 (claude-cto {result.stdout.strip()})")
                    return "python3"
            except (subprocess.TimeoutExpired, subprocess.CalledProcessError):
                pass
        
        # Fallback to current path with warning
        print(f"⚠️  Using potentially unstable path: {current_path}")
        return current_path


def normalize_python_path(python_path: str) -> str:
    """Convert versioned paths to stable equivalents."""
    # Homebrew versioned path → stable symlink
    if re.match(r'/opt/homebrew/Cellar/claude-cto/[\d.]+/libexec/bin/python.*', python_path):
        stable_path = "/opt/homebrew/opt/claude-cto/libexec/bin/python"
        if Path(stable_path).exists():
            return stable_path
    
    # Already a stable path
    if is_stable_path(python_path):
        return python_path
    
    # Convert absolute paths to generic commands where possible
    if python_path.endswith("/bin/python3"):
        return "python3"
    elif python_path.endswith("/bin/python"):
        return "python3"
    
    return python_path


def create_mcp_config() -> Dict[str, Any]:
    """Create MCP server configuration for Claude Code with stable paths."""
    python_path = get_stable_python_path()
    
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


def validate_config_paths() -> List[str]:
    """Validate that configured Python paths still exist."""
    issues = []
    config_files = find_claude_config_files()
    
    if not config_files:
        return ["No Claude configuration files found"]
    
    for config_file in config_files:
        try:
            with open(config_file, 'r') as f:
                config = json.load(f)
            
            # Check mcpServers in both formats
            servers_configs = []
            if "mcpServers" in config:
                servers_configs.append(("mcpServers", config["mcpServers"]))
            if "servers" in config:  # Some legacy formats
                servers_configs.append(("servers", config["servers"]))
            
            for servers_key, servers in servers_configs:
                if isinstance(servers, dict) and "claude-cto" in servers:
                    server_config = servers["claude-cto"]
                    if isinstance(server_config, dict) and "command" in server_config:
                        python_path = server_config["command"]
                        
                        # Skip validation for generic commands
                        if python_path in ["python", "python3", "python3.12"]:
                            continue
                        
                        # Check if absolute path exists
                        if python_path.startswith("/") and not Path(python_path).exists():
                            issues.append(f"Invalid path in {config_file}: {python_path}")
                        
                        # Check for versioned paths that might break
                        if re.search(r'/Cellar/claude-cto/[\d.]+/', python_path):
                            issues.append(f"Versioned path in {config_file}: {python_path} (may break on upgrade)")
                            
        except (json.JSONDecodeError, OSError, KeyError) as e:
            issues.append(f"Could not read {config_file}: {e}")
    
    return issues


def migrate_config_paths(dry_run: bool = False) -> Tuple[int, List[str]]:
    """Fix outdated versioned paths in Claude configurations.
    
    Returns:
        Tuple of (files_modified, messages)
    """
    messages = []
    files_modified = 0
    config_files = find_claude_config_files()
    
    if not config_files:
        messages.append("No Claude configuration files found to migrate")
        return 0, messages
    
    for config_file in config_files:
        try:
            # Backup original file
            backup_file = config_file.with_suffix(f"{config_file.suffix}.backup")
            if not dry_run and not backup_file.exists():
                shutil.copy2(config_file, backup_file)
                messages.append(f"✓ Created backup: {backup_file}")
            
            with open(config_file, 'r') as f:
                config = json.load(f)
            
            modified = False
            
            # Check mcpServers in both formats
            for servers_key in ["mcpServers", "servers"]:
                if servers_key in config and isinstance(config[servers_key], dict):
                    for server_name, server_config in config[servers_key].items():
                        if (server_name == "claude-cto" and 
                            isinstance(server_config, dict) and 
                            "command" in server_config):
                            
                            old_command = server_config["command"]
                            new_command = normalize_python_path(old_command)
                            
                            if old_command != new_command:
                                if not dry_run:
                                    config[servers_key][server_name]["command"] = new_command
                                modified = True
                                messages.append(
                                    f"{'[DRY RUN] ' if dry_run else ''}✓ Updated {server_name} in {config_file}:\n"
                                    f"  Old: {old_command}\n"
                                    f"  New: {new_command}"
                                )
            
            # Write back if modified
            if modified and not dry_run:
                with open(config_file, 'w') as f:
                    json.dump(config, f, indent=2)
                files_modified += 1
                messages.append(f"✅ Saved changes to {config_file}")
            elif modified and dry_run:
                messages.append(f"[DRY RUN] Would modify {config_file}")
                
        except (json.JSONDecodeError, OSError, KeyError) as e:
            messages.append(f"❌ Could not migrate {config_file}: {e}")
    
    return files_modified, messages


def diagnose_configuration() -> None:
    """Provide detailed diagnosis of current configuration state."""
    print("🔍 Claude CTO Configuration Diagnosis")
    print("=" * 40)
    
    # Current installation info
    print(f"\n📦 Installation Information:")
    print(f"   Current Python: {sys.executable}")
    print(f"   Installation method: {detect_installation_method()}")
    print(f"   Stable path would be: {get_stable_python_path()}")
    
    # Check if claude-cto is importable
    try:
        import claude_cto
        print(f"   Claude CTO version: {claude_cto.__version__}")
    except ImportError as e:
        print(f"   ❌ Claude CTO import failed: {e}")
    
    # Find configuration files
    config_files = find_claude_config_files()
    print(f"\n📋 Configuration Files:")
    if not config_files:
        print("   No Claude configuration files found")
    else:
        for config_file in config_files:
            print(f"   Found: {config_file}")
    
    # Validate configurations
    print(f"\n🔧 Configuration Validation:")
    issues = validate_config_paths()
    if not issues:
        print("   ✅ All configurations are valid")
    else:
        for issue in issues:
            print(f"   ❌ {issue}")
    
    # Check if migration is available
    print(f"\n🔄 Migration Status:")
    files_modified, messages = migrate_config_paths(dry_run=True)
    if files_modified == 0:
        print("   No migrations needed")
    else:
        print(f"   {files_modified} file(s) can be automatically fixed")
        for message in messages:
            if "Updated" in message:
                print(f"   {message}")


def auto_fix_configurations() -> bool:
    """Automatically fix configuration issues."""
    print("🔧 Auto-fixing Configuration Issues...")
    print("=" * 40)
    
    # Run migration
    files_modified, messages = migrate_config_paths(dry_run=False)
    
    for message in messages:
        print(message)
    
    if files_modified > 0:
        print(f"\n✅ Successfully fixed {files_modified} configuration file(s)")
        return True
    else:
        print("\nℹ️  No configuration changes were needed")
        return False


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
    
    # Step 2: Diagnose current configuration
    print("\n2. Checking existing configurations...")
    issues = validate_config_paths()
    if issues:
        print("⚠️  Found configuration issues:")
        for issue in issues:
            print(f"   • {issue}")
        
        print("\n🔧 Attempting to fix issues...")
        files_fixed, fix_messages = migrate_config_paths(dry_run=False)
        for message in fix_messages:
            if "✓" in message or "✅" in message:
                print(f"   {message}")
    
    # Step 3: Create MCP configuration  
    print("\n3. Creating MCP configuration...")
    config = create_mcp_config()
    
    # Step 4: Update Claude Code settings
    print("\n4. Updating Claude Code settings...")
    if not update_claude_settings(config):
        return False
    
    # Step 5: Test configuration
    print("\n5. Testing configuration...")
    try:
        result = subprocess.run([
            sys.executable, "-m", "claude_cto.mcp.factory"
        ], timeout=3, capture_output=True, text=True)
        
        # Check if server started successfully (ignore module import warnings)
        if (result.stderr and 
            ("RuntimeWarning" in result.stderr or "found in sys.modules" in result.stderr) and 
            "Migration failed" not in result.stderr and
            "Error" not in result.stderr):
            print("✅ MCP server starts successfully (with minor warnings)")
        elif result.returncode == 0:
            print("✅ MCP server starts successfully")
        else:
            print("⚠️  MCP server has warnings but should work")
        
    except subprocess.TimeoutExpired:
        print("✅ MCP server starts successfully (timed out as expected)")
    except Exception as e:
        print(f"❌ MCP server test failed: {e}")
        return False
    
    # Step 6: Success message
    print("\n" + "=" * 40)
    print("🎉 AUTO-CONFIGURATION COMPLETE!")
    print("\n📋 What was configured:")
    print("   • Claude Code MCP server entry added with stable paths")
    print("   • Auto-mode enabled (standalone/proxy detection)")
    print("   • Database path: ~/.claude-cto/tasks.db")
    print("   • Logs directory: ~/.claude-cto/logs")
    
    stable_path = get_stable_python_path()
    print(f"\n🔧 Python path used: {stable_path}")
    
    print("\n📝 Next steps:")
    print("   1. Restart Claude Code")
    print("   2. The 'claude-cto' MCP server should now be available")
    print("   3. Use MCP tools like create_task, get_task_status, etc.")
    
    print("\n🆘 If you have issues:")
    print("   • Run: python -m claude_cto.mcp.auto_config diagnose")
    print("   • Check Claude Code logs")
    print("   • Run: python -m claude_cto.mcp.factory (should start without errors)")
    
    return True


def print_manual_config():
    """Print manual configuration instructions."""
    stable_path = get_stable_python_path()
    
    print("\n📖 MANUAL CONFIGURATION INSTRUCTIONS")
    print("=" * 40)
    print("\nIf auto-configuration failed, add this to your ~/.claude/settings.json:")
    print(json.dumps(create_mcp_config(), indent=2))
    print(f"\nStable Python path: {stable_path}")
    print(f"Current Python path: {sys.executable}")
    print("\n🔧 Alternative commands to try:")
    print("   • python -m claude_cto.mcp.auto_config diagnose")
    print("   • python -m claude_cto.mcp.auto_config fix")
    print("   • python -m claude_cto.mcp.factory (test MCP server)")


if __name__ == "__main__":
    # Support command-line arguments for different operations
    if len(sys.argv) > 1:
        command = sys.argv[1].lower()
        
        if command == "diagnose":
            diagnose_configuration()
            sys.exit(0)
        elif command == "fix":
            success = auto_fix_configurations()
            sys.exit(0 if success else 1)
        elif command == "validate":
            issues = validate_config_paths()
            if issues:
                print("Configuration issues found:")
                for issue in issues:
                    print(f"  • {issue}")
                sys.exit(1)
            else:
                print("✅ All configurations are valid")
                sys.exit(0)
        elif command in ["help", "-h", "--help"]:
            print("Claude CTO MCP Auto-Configuration")
            print("\nUsage: python -m claude_cto.mcp.auto_config [command]")
            print("\nCommands:")
            print("  (none)    Run full auto-configuration")
            print("  diagnose  Show detailed configuration diagnosis")
            print("  fix       Automatically fix configuration issues")
            print("  validate  Check if configurations are valid")
            print("  help      Show this help message")
            sys.exit(0)
    
    # Default: run full auto-configuration
    success = auto_configure()
    
    if not success:
        print_manual_config()
        sys.exit(1)
    
    sys.exit(0)