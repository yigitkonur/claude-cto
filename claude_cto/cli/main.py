"""
SOLE RESPONSIBILITY: Defines all Typer CLI commands (e.g., run, status, logs),
handles user input, and makes HTTP requests to the server's REST API.
"""

import sys
import os
import asyncio
import subprocess
import json
import time
import shutil
from pathlib import Path
from typing import Optional, Annotated

import typer
import httpx
from rich.console import Console
from rich.table import Table
from rich.live import Live
from rich.panel import Panel
from rich.text import Text
from rich.progress import Progress, SpinnerColumn, TextColumn, TimeElapsedColumn

from .config import get_server_url


def auto_configure_mcp():
    """
    Auto-configure claude-cto as an MCP server for Claude Code on first run.
    Works for pip, uv, and other Python-based installations.
    """
    try:
        # Check if claude CLI is available
        if not shutil.which("claude"):
            return  # Claude CLI not installed, skip auto-config
        
        # Get cross-platform config file path
        home = Path.home()
        claude_config = home / ".claude.json"
        
        # Check if config file exists and already contains claude-cto
        claude_cto_configured = False
        if claude_config.exists():
            try:
                with open(claude_config, 'r') as f:
                    config = json.load(f)
                    if 'mcpServers' in config and 'claude-cto' in config['mcpServers']:
                        claude_cto_configured = True
            except (json.JSONDecodeError, KeyError, OSError):
                pass  # If config is invalid, proceed with auto-config
        
        # If not configured, add it
        if not claude_cto_configured:
            try:
                print("🗿 Setting up claude-cto MCP server for Claude Code...")
                
                # Use sys.executable to get the correct Python interpreter
                # Works with virtualenv, conda, pyenv, etc.
                python_path = sys.executable
                
                # Run claude mcp add command
                result = subprocess.run([
                    "claude", "mcp", "add", "claude-cto", "-s", "user",
                    "--", python_path, "-m", "claude_cto.mcp.factory"
                ], capture_output=True, text=True, timeout=10)
                
                if result.returncode == 0:
                    print("✓ claude-cto is now available in Claude Code!")
                
            except (subprocess.TimeoutExpired, subprocess.SubprocessError, OSError):
                # Silently fail if MCP setup doesn't work
                # The CLI should still function normally
                pass
                
    except Exception:
        # Catch-all to ensure CLI never fails due to MCP setup
        pass


# Initialize Typer app
app = typer.Typer(
    name="claude-cto",
    help="""
🤖 [bold cyan]Claude CTO[/bold cyan] - Run Claude Code SDK tasks in the background

Delegate long-running AI tasks to Claude without blocking your terminal.
Perfect for code refactoring, analysis, and automation tasks.

[bold yellow]Quick Start:[/bold yellow]
  $ claude-cto run "analyze this codebase and suggest improvements"
  $ claude-cto run "refactor all Python files to use type hints" --watch
  $ echo "review this code" | claude-cto run

[bold green]Examples:[/bold green]
  • Simple task:     claude-cto run "create a README.md file"
  • From file:       claude-cto run instructions.txt
  • With monitoring: claude-cto run "complex task" --watch
  • Check progress:  claude-cto status 1
  • View all tasks:  claude-cto list

[dim]The server starts automatically when needed. No setup required![/dim]
""",
    rich_markup_mode="rich",
    no_args_is_help=True,  # Show help when no args provided
    invoke_without_command=True,  # CRITICAL: Allow callback to run with commands
    epilog="[dim]For detailed help on any command: claude-cto [COMMAND] --help[/dim]",
)


@app.callback()
def main():
    """
    Main callback that runs before any command.
    Handles auto-MCP configuration on first run.
    """
    # The auto_configure_mcp() is also called in individual commands
    # as a fallback in case the callback doesn't work
    auto_configure_mcp()

# Server management sub-app
server_app = typer.Typer(
    help="""[bold]Server management commands[/bold]
    
[dim]Note: The server starts automatically when you run tasks.
You only need these commands for manual control.[/dim]
""",
    rich_markup_mode="rich",
    no_args_is_help=True,
    invoke_without_command=True,
)


@server_app.callback()
def server_callback(ctx: typer.Context):
    """Show help when no server subcommand is provided."""
    if ctx.invoked_subcommand is None:
        console.print(ctx.get_help())
        raise typer.Exit()


app.add_typer(server_app, name="server")

# Console for rich output
console = Console()


def version_callback(value: bool):
    """Version callback function for --version flag."""
    if value:
        from claude_cto import __version__
        console.print(f"[bold green]Claude CTO[/bold green] v{__version__}")
        raise typer.Exit()


@app.callback()
def main(
    ctx: typer.Context,
    version: Annotated[
        Optional[bool], 
        typer.Option("--version", "-v", callback=version_callback, help="Show version and exit")
    ] = None
):
    """
    Show help when no command is provided.
    """
    if ctx.invoked_subcommand is None:
        # No subcommand was invoked, show help
        print(ctx.get_help())
        raise typer.Exit()


def is_server_running(server_url: str) -> bool:
    """
    Health check to determine if API server is running and responsive.
    Critical for auto-start logic - prevents duplicate server processes.
    """
    try:
        # Fast health check with short timeout to avoid blocking CLI
        with httpx.Client() as client:
            response = client.get(f"{server_url}/health", timeout=1.0)
            return response.status_code == 200
    except (httpx.ConnectError, httpx.TimeoutException):
        return False


def start_server_in_background() -> bool:
    """
    Auto-starts API server when not running - enables zero-config CLI usage.
    Handles port conflicts and process management automatically.
    Returns True if successfully started, False otherwise.
    """
    import socket
    import time

    console.print("[yellow]⚠️  Server not running. Starting Claude CTO server...[/yellow]")

    # Port discovery logic: finds next available port starting from 8000
    def is_port_available(host: str, port: int) -> bool:
        try:
            with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
                s.bind((host, port))
                return True
        except OSError:
            return False

    host = "0.0.0.0"
    port = 8000

    # Scan for available port (prevents conflicts with existing services)
    for attempt in range(100):
        if is_port_available(host, port):
            break
        port += 1
    else:
        return False

    # Background process creation: spawns detached uvicorn server with suppressed output
    cmd = [
        sys.executable,
        "-m",
        "uvicorn",
        "claude_cto.server.main:app",
        "--host",
        host,
        "--port",
        str(port),
    ]

    try:
        # Detached subprocess: continues running after CLI exits
        process = subprocess.Popen(
            cmd,
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
            start_new_session=True,
        )

        # Server startup wait: allows FastAPI to initialize before health checks
        time.sleep(2)

        # Process health verification: ensures server didn't crash during startup
        if process.poll() is None:
            console.print(f"[green]✓ Server started on port {port} (PID: {process.pid})[/green]")

            # Dynamic URL configuration: updates config when using non-default port
            if port != 8000:
                os.environ["CLAUDE_CTO_SERVER_URL"] = f"http://localhost:{port}"

            return True
        else:
            return False

    except Exception:
        return False


@app.command(
    help="""[bold green]Submit a task to Claude[/bold green] 🚀
    
Runs your task in the background using Claude Code SDK.
The server starts automatically if not already running.

[bold]Examples:[/bold]
  [cyan]# Simple task[/cyan]
  $ claude-cto run "write a Python hello world script"
  
  [cyan]# From a file with instructions[/cyan]
  $ claude-cto run requirements.txt
  
  [cyan]# Watch the task progress live[/cyan]
  $ claude-cto run "refactor this codebase" --watch
  
  [cyan]# Pipe input from another command[/cyan]
  $ git diff | claude-cto run "review these changes"
  
  [cyan]# Specify working directory[/cyan]
  $ claude-cto run "organize files here" --dir /path/to/project
"""
)
def run(
    prompt: Annotated[
        Optional[str],
        typer.Argument(help="Task prompt or path to file with instructions", metavar="PROMPT"),
    ] = None,
    working_dir: Annotated[
        str,
        typer.Option(
            "--dir",
            "-d",
            help="Working directory for the task",
            rich_help_panel="Task Options",
        ),
    ] = ".",
    system_prompt: Annotated[
        Optional[str],
        typer.Option(
            "--system",
            "-s",
            help="Custom system prompt for Claude",
            rich_help_panel="Task Options",
        ),
    ] = None,
    model: Annotated[
        str,
        typer.Option(
            "--model",
            "-m",
            help="Claude model to use: sonnet (default - balanced intelligence for most tasks), opus (highest intelligence for complex planning), haiku (fastest for simple tasks)",
            rich_help_panel="Task Options",
        ),
    ] = "sonnet",
    watch: Annotated[
        bool,
        typer.Option(
            "--watch",
            "-w",
            help="Watch task progress in real-time",
            rich_help_panel="Display Options",
        ),
    ] = False,
):
    """
    Main CLI command: creates and executes Claude Code SDK tasks via REST API.
    Handles multiple input sources (args, files, stdin) and auto-starts server.
    
    Prompt can be provided as:
    - Command line argument
    - File path (if argument is a readable file)
    - Piped from stdin
    """
    # Input source resolution: prioritizes prompt argument > stdin > error
    execution_prompt = None

    if prompt:
        # File vs string disambiguation: checks if argument is readable file
        prompt_path = Path(prompt)
        if prompt_path.exists() and prompt_path.is_file():
            with open(prompt_path, "r") as f:
                execution_prompt = f.read().strip()
        else:
            # Direct prompt string
            execution_prompt = prompt
    elif not sys.stdin.isatty():
        # Stdin detection: handles piped input from other commands
        execution_prompt = sys.stdin.read().strip()
    else:
        console.print("[red]Error: No prompt provided[/red]")
        raise typer.Exit(1)

    # API request payload construction: builds task creation data
    task_data = {
        "execution_prompt": execution_prompt,
        "working_directory": str(Path(working_dir).resolve()),
    }
    if system_prompt:
        task_data["system_prompt"] = system_prompt

    # Model validation: ensures valid Claude model selection
    model_lower = model.lower()
    if model_lower not in ["sonnet", "opus", "haiku"]:
        console.print(f"[red]❌ Invalid model: {model}. Must be one of: sonnet, opus, haiku[/red]")
        raise typer.Exit(1)
    task_data["model"] = model_lower

    # Server connectivity check: determines if API server is accessible
    server_url = get_server_url()

    # Zero-config server management: automatically starts server if needed
    if not is_server_running(server_url):
        if not start_server_in_background():
            console.print("\n[red]❌ Could not start the server automatically.[/red]\n")
            console.print("[bold yellow]To fix this, try:[/bold yellow]")
            console.print("  1. Start the server manually:")
            console.print("     [bright_white]$ claude-cto server start[/bright_white]\n")
            console.print("  2. Check if port 8000-8099 are available:")
            console.print("     [bright_white]$ lsof -i :8000[/bright_white]\n")
            console.print("  3. Kill any existing servers:")
            console.print("     [bright_white]$ pkill -f claude_cto.server[/bright_white]\n")
            raise typer.Exit(1)

        # URL refresh: updates server_url after dynamic port assignment
        server_url = get_server_url()

    # HTTP API request: submits task to /api/v1/tasks endpoint with timeout
    with httpx.Client() as client:
        try:
            response = client.post(f"{server_url}/api/v1/tasks", json=task_data, timeout=30.0)
            response.raise_for_status()
            result = response.json()

            # Success feedback: displays task ID and status to user
            console.print(f"\n[green]✓[/green] Task created with ID: [bold cyan]{result['id']}[/bold cyan]")
            console.print(f"Status: [yellow]{result['status']}[/yellow]")

            if not watch:
                console.print(
                    f"\n[dim]💡 Tip: Check progress with:[/dim] [bright_white]claude-cto status {result['id']}[/bright_white]"
                )
                console.print(
                    '[dim]    Or watch live with:[/dim] [bright_white]claude-cto run "your task" --watch[/bright_white]'
                )

            # Live monitoring: starts real-time progress watching if requested
            if watch:
                asyncio.run(watch_status(result["id"]))

        except httpx.HTTPError as e:
            console.print(f"[red]Error submitting task: {e}[/red]")
            raise typer.Exit(1)


@app.command(
    help="""[bold yellow]Check task status[/bold yellow] 📊
    
View detailed information about a specific task.

[bold]Examples:[/bold]
  $ claude-cto status 1
  $ claude-cto status     [dim]# Shows available task IDs[/dim]
  
Shows the task's current status, progress, and any errors.
"""
)
def status(
    task_id: Annotated[
        Optional[int],
        typer.Argument(
            help="The ID of the task to check (optional - shows available IDs if not provided)",
            metavar="TASK_ID",
        ),
    ] = None,
):
    """Get the status of a specific task."""
    server_url = get_server_url()

    # Auto-start server if not running
    if not is_server_running(server_url):
        if not start_server_in_background():
            console.print("\n[red]❌ Could not start the server automatically.[/red]\n")
            console.print("[bold yellow]To fix this, try:[/bold yellow]")
            console.print("  1. Start the server manually:")
            console.print("     [bright_white]$ claude-cto server start[/bright_white]\n")
            console.print("  2. Check if port 8000-8099 are available:")
            console.print("     [bright_white]$ lsof -i :8000[/bright_white]\n")
            console.print("  3. Kill any existing servers:")
            console.print("     [bright_white]$ pkill -f claude_cto.server[/bright_white]\n")
            raise typer.Exit(1)

        # Update server_url if it changed
        server_url = get_server_url()

    # If no task_id provided, show available tasks
    if task_id is None:
        with httpx.Client() as client:
            try:
                response = client.get(f"{server_url}/api/v1/tasks", timeout=10.0)
                response.raise_for_status()
                tasks = response.json()

                if not tasks:
                    console.print("\n[yellow]📭 No tasks found yet![/yellow]\n")
                    console.print("[bold]Create your first task with:[/bold]")
                    console.print('  $ claude-cto run "your task description"\n')
                    return

                console.print("\n[bold blue]📋 Available Tasks:[/bold blue]\n")

                # Create a simple table of tasks
                table = Table()
                table.add_column("ID", style="bold cyan")
                table.add_column("Status", style="yellow")
                table.add_column("Created", style="green")
                table.add_column("Description", style="white")

                for task in tasks[-10:]:  # Show last 10 tasks
                    description = task.get("last_action_cache", "No description")
                    if description:
                        description = description[:60] + "..." if len(description) > 60 else description
                    else:
                        description = "-"

                    table.add_row(
                        str(task["id"]),
                        task["status"],
                        task["created_at"][:19],
                        description,
                    )

                console.print(table)

                # Show helpful guidance
                console.print("\n[bold]💡 To check a specific task:[/bold]")
                console.print("  $ claude-cto status [cyan]<TASK_ID>[/cyan]")
                console.print("\n[dim]Example:[/dim]")
                if tasks:
                    latest_id = tasks[-1]["id"]
                    console.print(f"  $ claude-cto status [cyan]{latest_id}[/cyan]")
                console.print()

                return

            except httpx.HTTPError as e:
                console.print(f"[red]Error fetching tasks: {e}[/red]")
                raise typer.Exit(1)

    # Show specific task status
    with httpx.Client() as client:
        try:
            response = client.get(f"{server_url}/api/v1/tasks/{task_id}", timeout=10.0)
            response.raise_for_status()
            task = response.json()

            # Create status table
            table = Table(title=f"Task {task_id} Status")
            table.add_column("Field", style="cyan")
            table.add_column("Value", style="green")

            table.add_row("Status", task["status"])
            table.add_row("Created", task["created_at"])

            if task.get("started_at"):
                table.add_row("Started", task["started_at"])

            if task.get("ended_at"):
                table.add_row("Ended", task["ended_at"])

            if task.get("last_action_cache"):
                table.add_row("Last Action", task["last_action_cache"])

            if task.get("final_summary"):
                table.add_row("Summary", task["final_summary"])

            if task.get("error_message"):
                table.add_row("Error", task["error_message"])

            console.print(table)

        except httpx.HTTPError as e:
            if "404" in str(e):
                console.print(f"\n[red]❌ Task ID {task_id} not found.[/red]")
                console.print("\n[bold]💡 Check available task IDs with:[/bold]")
                console.print("  $ claude-cto status")
                console.print("  $ claude-cto list\n")
            else:
                console.print(f"[red]Error fetching task status: {e}[/red]")
            raise typer.Exit(1)


@app.command(help="[bold]Show this help message[/bold] 📚")
def help(ctx: typer.Context):
    """Show help information."""
    console.print(ctx.parent.get_help())


@app.command(
    help="""[bold yellow]Upgrade to the latest version[/bold yellow] ⬆️
    
Check for updates and upgrade claude-cto to the latest version.

[bold]Usage:[/bold]
  $ claude-cto upgrade          # Check and install updates
  $ claude-cto upgrade --check  # Only check for updates
  
[bold]Examples:[/bold]
  • Auto-upgrade:    claude-cto upgrade
  • Check only:      claude-cto upgrade --check
  • Force reinstall: claude-cto upgrade --force
""",
)
def upgrade(
    check_only: bool = typer.Option(False, "--check", help="Only check for updates without installing"),
    force: bool = typer.Option(False, "--force", help="Force reinstall even if already up-to-date"),
    method: Optional[str] = typer.Option(None, "--method", help="Installation method (auto-detect if not specified)")
):
    """Check for updates and upgrade claude-cto."""
    from claude_cto.core.updater import VersionChecker, PackageUpgrader
    from packaging import version as pkg_version
    
    checker = VersionChecker()
    upgrader = PackageUpgrader()
    
    # Get current and latest versions
    current = checker.get_current_version()
    console.print(f"[cyan]Current version:[/cyan] {current}")
    
    # Check for latest version
    with console.status("[yellow]Checking for updates...[/yellow]"):
        latest = checker.get_latest_version()
    
    if latest is None:
        console.print("[red]❌ Could not check for updates (network error)[/red]")
        raise typer.Exit(1)
    
    if latest == current and not force:
        console.print(f"[green]✅ You're already on the latest version ({current})[/green]")
        raise typer.Exit(0)
    
    if pkg_version.parse(latest) > pkg_version.parse(current):
        console.print(f"[yellow]🆕 New version available:[/yellow] {latest}")
        
        if check_only:
            console.print("\n[cyan]Run 'claude-cto upgrade' to install the update[/cyan]")
            raise typer.Exit(0)
    elif not force:
        console.print(f"[green]✅ You're already on the latest version ({current})[/green]")
        raise typer.Exit(0)
    
    # Detect installation method if not specified
    if not method:
        method = upgrader.detect_installation_method()
        if not method:
            console.print("[red]❌ Could not detect installation method[/red]")
            console.print("[yellow]Try specifying --method (pip, uv, or poetry)[/yellow]")
            raise typer.Exit(1)
        console.print(f"[cyan]Detected installation method:[/cyan] {method}")
    
    # Perform upgrade
    console.print(f"\n[yellow]Upgrading to version {latest}...[/yellow]")
    
    success, message = upgrader.upgrade(target_version=latest if not force else None, method=method)
    
    if success:
        console.print(f"[green]✅ {message}[/green]")
        
        # Verify upgrade
        from importlib import reload
        import claude_cto
        reload(claude_cto)
        new_version = claude_cto.__version__
        
        if new_version != current:
            console.print(f"[green]Successfully upgraded from {current} to {new_version}![/green]")
        else:
            console.print(f"[green]Package reinstalled successfully![/green]")
    else:
        console.print(f"[red]❌ Upgrade failed: {message}[/red]")
        raise typer.Exit(1)


@app.command(
    name="list",
    help="""[bold blue]View all tasks[/bold blue] 📋
    
Display a table of all submitted tasks with their status.

[bold]Example:[/bold]
  $ claude-cto list
  
Shows task IDs, status, creation time, and last actions.
""",
)
def list():
    """List all tasks."""
    # Ensure MCP is configured on first run
    auto_configure_mcp()
    
    server_url = get_server_url()

    # Auto-start server if not running
    if not is_server_running(server_url):
        if not start_server_in_background():
            console.print("\n[red]❌ Could not start the server automatically.[/red]\n")
            console.print("[bold yellow]To fix this, try:[/bold yellow]")
            console.print("  1. Start the server manually:")
            console.print("     [bright_white]$ claude-cto server start[/bright_white]\n")
            console.print("  2. Check if port 8000-8099 are available:")
            console.print("     [bright_white]$ lsof -i :8000[/bright_white]\n")
            console.print("  3. Kill any existing servers:")
            console.print("     [bright_white]$ pkill -f claude_cto.server[/bright_white]\n")
            raise typer.Exit(1)

        # Update server_url if it changed
        server_url = get_server_url()

    with httpx.Client() as client:
        try:
            response = client.get(f"{server_url}/api/v1/tasks", timeout=10.0)
            response.raise_for_status()
            tasks = response.json()

            if not tasks:
                console.print("\n[yellow]📭 No tasks found yet![/yellow]\n")
                console.print("[bold]Get started with:[/bold]")
                console.print('  $ claude-cto run "your first task"\n')
                console.print("[dim]Examples:[/dim]")
                console.print('  • claude-cto run "create a Python script that sorts files by date"')
                console.print('  • claude-cto run "analyze this codebase and find bugs"')
                console.print('  • claude-cto run "write unit tests for all functions"\n')
                return

            # Create tasks table
            table = Table(title="All Tasks")
            table.add_column("ID", style="cyan")
            table.add_column("Status", style="yellow")
            table.add_column("Created", style="green")
            table.add_column("Last Action", style="white")
            table.add_column("Logs", style="dim blue")

            for task in tasks:
                last_action = task.get("last_action_cache", "-")

                # Generate enhanced log info with directory context
                task_id = task["id"]

                # Try to get actual log files info from server or construct pattern
                try:
                    # Get working directory from task (if available)
                    working_dir = task.get("working_directory", "unknown")

                    # Create a short directory context for display
                    from pathlib import Path

                    dir_name = Path(working_dir).name if working_dir != "unknown" else "unknown"
                    if len(dir_name) > 15:
                        dir_name = dir_name[:12] + "..."

                    # Enhanced log info showing directory context
                    log_info = f"task_{task_id}_{dir_name}_*.log"

                except Exception:
                    # Fallback to simple pattern
                    log_info = f"task_{task_id}_*.log"

                table.add_row(
                    str(task["id"]),
                    task["status"],
                    task["created_at"][:19],  # Truncate to remove microseconds
                    last_action[:50] if last_action else "-",  # Truncate long actions
                    log_info,
                )

            console.print(table)

            # Show helpful guidance about logs
            console.print("\n[bold blue]📋 Log Files:[/bold blue]")
            console.print("  [dim]Summary logs:[/dim]   ~/.claude-cto/tasks/task_<ID>_<context>_*_summary.log")
            console.print("  [dim]Detailed logs:[/dim]  ~/.claude-cto/tasks/task_<ID>_<context>_*_detailed.log")
            console.print("  [dim]Global log:[/dim]     ~/.claude-cto/claude-cto.log")
            console.print("\n[bold]💡 View logs with:[/bold]")
            console.print("  $ ls ~/.claude-cto/tasks/task_<ID>_*")
            console.print("  $ tail -f ~/.claude-cto/tasks/task_<ID>_*_summary.log")
            console.print("  $ tail -f ~/.claude-cto/claude-cto.log")
            console.print("\n[dim]Note: Log filenames now include directory context for parallel instances[/dim]")

        except httpx.HTTPError as e:
            console.print(f"[red]Error fetching tasks: {e}[/red]")
            raise typer.Exit(1)


async def watch_status(task_id: int):
    """
    Watch task status with live updates.
    Uses rich's Live display for flicker-free updates.
    """
    server_url = get_server_url()

    with Live(console=console, refresh_per_second=2) as live:
        while True:
            async with httpx.AsyncClient() as client:
                try:
                    response = await client.get(f"{server_url}/api/v1/tasks/{task_id}", timeout=10.0)
                    response.raise_for_status()
                    task = response.json()

                    # Create live status table
                    table = Table(title=f"Task {task_id} - Live Status")
                    table.add_column("Field", style="cyan")
                    table.add_column("Value", style="green")

                    # Add status with color coding
                    status_color = "yellow"
                    if task["status"] == "completed":
                        status_color = "green"
                    elif task["status"] == "error":
                        status_color = "red"

                    table.add_row("Status", f"[{status_color}]{task['status']}[/{status_color}]")
                    table.add_row("Created", task["created_at"])

                    if task.get("started_at"):
                        table.add_row("Started", task["started_at"])

                    if task.get("last_action_cache"):
                        table.add_row("Last Action", task["last_action_cache"])

                    if task.get("final_summary"):
                        table.add_row("Summary", task["final_summary"])

                    if task.get("error_message"):
                        table.add_row("Error", f"[red]{task['error_message']}[/red]")

                    # Update display
                    live.update(table)

                    # Check if task is done
                    if task["status"] in ["completed", "error"]:
                        break

                    # Wait before next update
                    await asyncio.sleep(2)

                except httpx.HTTPError as e:
                    console.print(f"[red]Error fetching task status: {e}[/red]")
                    break


# Orchestration commands


@app.command()
def orchestrate(
    tasks_file: Path = typer.Argument(..., help="Path to JSON file containing task orchestration definition"),
    server_url: str = typer.Option(None, "--server-url", help="Override the default server URL"),
    wait: bool = typer.Option(False, "--wait", "-w", help="Wait for orchestration to complete"),
    poll_interval: int = typer.Option(5, "--poll-interval", help="Polling interval in seconds when waiting"),
):
    """
    Complex multi-task orchestration from JSON file with dependency management.
    Creates DAG of interconnected tasks with automatic execution ordering.

    Example JSON structure:
    {
      "tasks": [
        {
          "identifier": "fetch_data",
          "execution_prompt": "Fetch data from API",
          "working_directory": "/path/to/project",
          "model": "haiku"
        },
        {
          "identifier": "process_data",
          "execution_prompt": "Process the fetched data",
          "working_directory": "/path/to/project",
          "depends_on": ["fetch_data"],
          "initial_delay": 2.0
        },
        {
          "identifier": "generate_report",
          "execution_prompt": "Generate final report",
          "working_directory": "/path/to/project",
          "depends_on": ["process_data"],
          "model": "sonnet"
        }
      ]
    }
    """
    # JSON file loading: reads and validates orchestration definition
    if not tasks_file.exists():
        console.print(f"[red]File not found: {tasks_file}[/red]")
        raise typer.Exit(1)

    try:
        with open(tasks_file) as f:
            orchestration_data = json.load(f)
    except json.JSONDecodeError as e:
        console.print(f"[red]Invalid JSON: {e}[/red]")
        raise typer.Exit(1)

    # Schema validation: ensures required 'tasks' array exists
    if "tasks" not in orchestration_data:
        console.print("[red]JSON must contain 'tasks' array[/red]")
        raise typer.Exit(1)

    # Server resolution: uses override URL or discovers default
    url = server_url or get_server_url()

    # Auto-server management: ensures API is available for orchestration
    if not is_server_running(url):
        start_server_in_background()
        time.sleep(2)  # Give server time to start

    # Orchestration API request: submits entire DAG to /api/v1/orchestrations
    try:
        response = httpx.post(f"{url}/api/v1/orchestrations", json=orchestration_data, timeout=30.0)
        response.raise_for_status()
        result = response.json()

        orch_id = result["orchestration_id"]
        console.print(f"[green]✓ Orchestration created with ID: {orch_id}[/green]")

        # Dependency visualization: displays task execution graph to user
        console.print("\n[bold cyan]Task Dependency Graph:[/bold cyan]")
        for task in result["tasks"]:
            deps = task.get("depends_on", [])
            delay = task.get("initial_delay", 0)
            dep_str = f" <- {deps}" if deps else ""
            delay_str = f" (delay: {delay}s)" if delay else ""
            console.print(f"  • {task['identifier']} (#{task['task_id']}){dep_str}{delay_str}")

        # Live progress monitoring: optional polling loop with Rich progress bar
        if wait:
            console.print("\n[yellow]Waiting for orchestration to complete...[/yellow]")

            with Progress(
                SpinnerColumn(),
                TextColumn("[progress.description]{task.description}"),
                TimeElapsedColumn(),
            ) as progress:
                task = progress.add_task("Running orchestration...", total=None)

                while True:
                    time.sleep(poll_interval)

                    # Status polling: checks orchestration completion via API
                    status_response = httpx.get(f"{url}/api/v1/orchestrations/{orch_id}")
                    if status_response.status_code == 200:
                        status_data = status_response.json()

                        # Update progress description
                        desc = (
                            f"Status: {status_data['status']} | "
                            f"Completed: {status_data['completed_tasks']}/{status_data['total_tasks']} | "
                            f"Failed: {status_data['failed_tasks']} | "
                            f"Skipped: {status_data['skipped_tasks']}"
                        )
                        progress.update(task, description=desc)

                        # Check if done
                        if status_data["status"] in [
                            "completed",
                            "failed",
                            "cancelled",
                        ]:
                            progress.stop()

                            # Display final results
                            if status_data["status"] == "completed":
                                console.print("\n[green]✓ Orchestration completed successfully![/green]")
                            else:
                                console.print(f"\n[red]✗ Orchestration {status_data['status']}[/red]")

                            # Show task summary
                            console.print("\n[bold cyan]Task Summary:[/bold cyan]")
                            for task_info in status_data["tasks"]:
                                status_color = {
                                    "completed": "green",
                                    "failed": "red",
                                    "skipped": "yellow",
                                    "running": "blue",
                                    "waiting": "magenta",
                                    "pending": "white",
                                }.get(task_info["status"], "white")

                                console.print(
                                    f"  • {task_info['identifier']} (#{task_info['task_id']}): [{status_color}]{task_info['status']}[/{status_color}]"
                                )

                                if task_info.get("error_message"):
                                    console.print(f"    Error: {task_info['error_message']}")

                            break

    except httpx.HTTPError as e:
        console.print(f"[red]Failed to create orchestration: {e}[/red]")
        raise typer.Exit(1)


@app.command()
def orchestration_status(
    orchestration_id: int = typer.Argument(..., help="Orchestration ID"),
    server_url: str = typer.Option(None, "--server-url", help="Override the default server URL"),
    watch: bool = typer.Option(False, "--watch", "-w", help="Watch status until completion"),
):
    """Check the status of an orchestration."""
    url = server_url or get_server_url()

    if not is_server_running(url):
        console.print("[red]Server is not running[/red]")
        raise typer.Exit(1)

    try:
        if watch:
            # Watch mode - refresh every 2 seconds
            while True:
                response = httpx.get(f"{url}/api/v1/orchestrations/{orchestration_id}")
                response.raise_for_status()
                data = response.json()

                # Clear screen (works on most terminals)
                console.clear()

                # Display header
                console.print(f"[bold cyan]Orchestration #{orchestration_id}[/bold cyan]")
                console.print("=" * 50)

                # Display summary
                console.print(f"Status: {data['status']}")
                console.print(f"Created: {data['created_at']}")
                if data["started_at"]:
                    console.print(f"Started: {data['started_at']}")
                if data["ended_at"]:
                    console.print(f"Ended: {data['ended_at']}")

                # Display progress
                console.print("\n[bold cyan]Progress:[/bold cyan]")
                console.print(f"  Total: {data['total_tasks']}")
                console.print(f"  Completed: {data['completed_tasks']}")
                console.print(f"  Failed: {data['failed_tasks']}")
                console.print(f"  Skipped: {data['skipped_tasks']}")

                # Display task details
                console.print("\n[bold cyan]Tasks:[/bold cyan]")
                for task in data["tasks"]:
                    status_icon = {
                        "completed": "✓",
                        "failed": "✗",
                        "skipped": "⊘",
                        "running": "⟳",
                        "waiting": "⏸",
                        "pending": "○",
                    }.get(task["status"], "?")

                    console.print(f"  {status_icon} {task['identifier']} (#{task['task_id']}): {task['status']}")

                    if task["depends_on"]:
                        console.print(f"    Dependencies: {', '.join(task['depends_on'])}")
                    if task["error_message"]:
                        console.print(f"    Error: {task['error_message']}")

                # Check if done
                if data["status"] in ["completed", "failed", "cancelled"]:
                    break

                # Wait before refresh
                time.sleep(2)
        else:
            # Single status check
            response = httpx.get(f"{url}/api/v1/orchestrations/{orchestration_id}")
            response.raise_for_status()
            data = response.json()

            # Display as formatted JSON
            console.print(json.dumps(data, indent=2))

    except httpx.HTTPStatusError as e:
        if e.response.status_code == 404:
            console.print(f"[red]Orchestration {orchestration_id} not found[/red]")
        else:
            console.print(f"[red]Error: {e}[/red]")
        raise typer.Exit(1)


@app.command()
def list_orchestrations(
    status: Optional[str] = typer.Option(
        None,
        "--status",
        help="Filter by status (pending, running, completed, failed, cancelled)",
    ),
    limit: int = typer.Option(10, "--limit", help="Maximum number of orchestrations to display"),
    server_url: str = typer.Option(None, "--server-url", help="Override the default server URL"),
):
    """List all orchestrations."""
    url = server_url or get_server_url()

    if not is_server_running(url):
        console.print("[red]Server is not running[/red]")
        raise typer.Exit(1)

    try:
        # Note: This endpoint would need to be added to the API
        params = {"limit": limit}
        if status:
            params["status"] = status

        response = httpx.get(f"{url}/api/v1/orchestrations", params=params)
        response.raise_for_status()
        orchestrations = response.json()

        if not orchestrations:
            console.print("[yellow]No orchestrations found[/yellow]")
            return

        # Display table
        table = Table(title="Orchestrations")
        table.add_column("ID", style="cyan", no_wrap=True)
        table.add_column("Status", style="magenta")
        table.add_column("Tasks", justify="right")
        table.add_column("Completed", justify="right", style="green")
        table.add_column("Failed", justify="right", style="red")
        table.add_column("Created", style="yellow")

        for orch in orchestrations:
            table.add_row(
                str(orch["id"]),
                orch["status"],
                str(orch["total_tasks"]),
                str(orch.get("completed_tasks", 0)),
                str(orch.get("failed_tasks", 0)),
                orch["created_at"][:19],  # Truncate microseconds
            )

        console.print(table)

    except httpx.HTTPError as e:
        console.print(f"[red]Failed to list orchestrations: {e}[/red]")
        raise typer.Exit(1)


@server_app.command(
    "start",
    help="""[bold green]Start the server manually[/bold green] 🚀
    
[dim]Note: The server starts automatically when you run tasks.
Use this command only if you need manual control.[/dim]

[bold]Examples:[/bold]
  [cyan]# Start with default settings[/cyan]
  $ claude-cto server start
  
  [cyan]# Use a specific port[/cyan]
  $ claude-cto server start --port 9000
  
  [cyan]# Enable auto-reload for development[/cyan]
  $ claude-cto server start --reload
""",
)
def server_start(
    host: Annotated[str, typer.Option("--host", "-h", help="Server host")] = "0.0.0.0",
    port: Annotated[int, typer.Option("--port", "-p", help="Server port")] = 8000,
    reload: Annotated[bool, typer.Option("--reload", "-r", help="Enable auto-reload")] = False,
    auto_port: Annotated[
        bool,
        typer.Option(
            "--auto-port/--no-auto-port",
            help="Automatically find available port if default is in use",
        ),
    ] = True,
):
    """
    Start the Claude CTO server in the background.
    Uses subprocess.Popen to launch Uvicorn as a daemon.
    Automatically tries alternative ports if the specified port is occupied.
    """
    import socket

    console.print("\n[bold cyan]🚀 Claude CTO Server[/bold cyan]")
    console.print("[dim]Fire-and-forget task execution for Claude Code SDK[/dim]\n")

    # Function to check if port is available
    def is_port_available(host: str, port: int) -> bool:
        try:
            with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
                s.bind((host, port))
                return True
        except OSError:
            return False

    # Find available port if auto_port is enabled
    original_port = port
    if auto_port:
        max_attempts = 100
        for attempt in range(max_attempts):
            if is_port_available(host, port):
                break
            if attempt == 0:
                console.print(f"[yellow]⚠️  Port {port} is in use, trying alternatives...[/yellow]")
            port += 1
        else:
            console.print(
                f"[red]❌ Could not find available port in range {original_port}-{original_port + max_attempts - 1}[/red]"
            )
            console.print(
                "[dim]Tip: Try specifying a different port with --port or stop the process using port 8000[/dim]"
            )
            raise typer.Exit(1)

    if port != original_port:
        console.print(f"[green]✓ Found available port: {port}[/green]")

    console.print(f"[yellow]Starting server on {host}:{port}...[/yellow]")

    # Build uvicorn command
    cmd = [
        sys.executable,
        "-m",
        "uvicorn",
        "claude_cto.server.main:app",
        "--host",
        host,
        "--port",
        str(port),
    ]
    
    # Set environment variable for server to know its port
    env = os.environ.copy()
    env["SERVER_PORT"] = str(port)

    if reload:
        cmd.append("--reload")

    # Start server as background process
    try:
        process = subprocess.Popen(
            cmd,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            start_new_session=True,  # Detach from parent process group
            env=env,  # Pass environment with SERVER_PORT
        )

        # Give it a moment to start
        import time

        time.sleep(2)

        # Check if process is still running
        if process.poll() is None:
            console.print(f"\n[green]✓ Server started successfully![/green] (PID: {process.pid})")
            console.print(f"[green]✓ API ready at:[/green] http://{host}:{port}\n")

            # Create informative panel about what this server does
            info_text = Text()
            info_text.append("🎯 Why this server?\n", style="bold yellow")
            info_text.append(
                "   Run long Claude Code SDK tasks without blocking your terminal.\n",
                style="dim",
            )
            info_text.append(
                "   Tasks run in isolated processes and persist through interruptions.\n\n",
                style="dim",
            )

            info_text.append("📝 How to submit tasks:\n", style="bold cyan")
            info_text.append("   Quick task:     ", style="dim")
            info_text.append('claude-cto run "Your prompt here"\n', style="bright_white")
            info_text.append("   From file:      ", style="dim")
            info_text.append("claude-cto run prompt.txt\n", style="bright_white")
            info_text.append("   With watching:  ", style="dim")
            info_text.append('claude-cto run "Your prompt" --watch\n', style="bright_white")
            info_text.append("   From pipe:      ", style="dim")
            info_text.append(
                'git diff | claude-cto run "Review these changes"\n\n',
                style="bright_white",
            )

            info_text.append("🔍 Monitor your tasks:\n", style="bold green")
            info_text.append("   List all:       ", style="dim")
            info_text.append("claude-cto list\n", style="bright_white")
            info_text.append("   Check status:   ", style="dim")
            info_text.append("claude-cto status <task-id>\n\n", style="bright_white")

            info_text.append("💡 When to use:\n", style="bold magenta")
            info_text.append("   • Complex refactoring or code generation tasks\n", style="dim")
            info_text.append("   • Running multiple tasks in parallel\n", style="dim")
            info_text.append("   • Tasks that might take 5+ minutes\n", style="dim")
            info_text.append(
                "   • When you need to preserve work through interruptions\n",
                style="dim",
            )

            console.print(
                Panel(
                    info_text,
                    title="[bold]🚀 Claude CTO Ready![/bold]",
                    border_style="green",
                    padding=(1, 2),
                )
            )

            console.print(f"\n[dim]To stop server: kill {process.pid} or Ctrl+C in the terminal[/dim]")
            console.print("[dim]Server logs: Check your terminal or ~/.claude-cto/logs/[/dim]")

            # If using a non-default port, suggest setting environment variable
            if port != 8000:
                console.print(f"\n[yellow]⚠️  Note: Server running on non-default port {port}[/yellow]")
                console.print(
                    f"[dim]Set CLAUDE_CTO_SERVER_URL=http://localhost:{port} to use this server with the CLI[/dim]"
                )
            console.print()
        else:
            stderr = process.stderr.read().decode() if process.stderr else "Unknown error"
            console.print(f"[red]Failed to start server: {stderr}[/red]")
            raise typer.Exit(1)

    except Exception as e:
        console.print(f"[red]Error starting server: {e}[/red]")
        raise typer.Exit(1)


@server_app.command(
    "cleanup",
    help="""[bold red]Clean up orphaned processes[/bold red] 🧹
    
Kill all orphaned Claude processes and clean up stale locks.
Use this after a server crash to clean up resources.

[bold]Example:[/bold]
  $ claude-cto server cleanup
  $ claude-cto server cleanup --force  # Force kill processes
""",
)
def server_cleanup(
    force: Annotated[bool, typer.Option("--force", "-f", help="Force kill processes")] = False,
):
    """Clean up orphaned processes and locks."""
    from claude_cto.server.process_registry import get_process_registry
    from claude_cto.server.server_lock import ServerLock
    import psutil
    
    console.print("[yellow]🧹 Cleaning up orphaned processes and locks...[/yellow]\n")
    
    # Clean up stale server locks
    locks_cleaned = ServerLock.cleanup_all_locks()
    console.print(f"[green]✓[/green] Cleaned {locks_cleaned} stale server locks")
    
    # Clean up orphaned processes
    registry = get_process_registry()
    processes_cleaned = registry.cleanup_orphaned_processes(force=force)
    console.print(f"[green]✓[/green] Terminated {processes_cleaned} orphaned processes")
    
    # Clean old registry entries
    entries_cleaned = registry.cleanup_old_entries(max_age_days=7)
    console.print(f"[green]✓[/green] Removed {entries_cleaned} old registry entries")
    
    # Find and report any remaining Claude processes
    claude_count = 0
    for proc in psutil.process_iter(['name', 'cmdline']):
        try:
            if 'claude' in proc.info['name'].lower() or 'claude' in ' '.join(proc.info.get('cmdline', [])).lower():
                claude_count += 1
        except (psutil.NoSuchProcess, psutil.AccessDenied):
            continue
    
    if claude_count > 0:
        console.print(f"\n[yellow]⚠️  {claude_count} Claude processes still running[/yellow]")
        console.print("[dim]Use --force flag to kill them[/dim]")
    else:
        console.print("\n[green]✨ All clean![/green]")


@server_app.command(
    "status",
    help="""[bold cyan]Show detailed server status[/bold cyan] 📊
    
Display server status, running tasks, and system resources.

[bold]Example:[/bold]
  $ claude-cto server status
  $ claude-cto server status -v  # Verbose with process tree
""",
)
def server_status(
    verbose: Annotated[bool, typer.Option("--verbose", "-v", help="Show detailed info")] = False,
):
    """Show detailed server status."""
    from claude_cto.server.process_registry import get_process_registry
    from claude_cto.server.server_lock import ServerLock
    import psutil
    from rich.table import Table
    
    # Check for running servers
    servers = ServerLock.get_all_running_servers()
    
    if not servers:
        console.print("[red]✗[/red] No servers running")
        console.print("[dim]Start a server with: claude-cto server start[/dim]")
        return
    
    # Display server table
    table = Table(title="Running Servers")
    table.add_column("Port", style="cyan")
    table.add_column("PID", style="green")
    table.add_column("Memory", style="yellow")
    table.add_column("CPU %", style="magenta")
    
    for port, pid in servers:
        try:
            proc = psutil.Process(pid)
            mem_mb = proc.memory_info().rss / 1024 / 1024
            cpu_pct = proc.cpu_percent(interval=0.1)
            table.add_row(str(port), str(pid), f"{mem_mb:.1f} MB", f"{cpu_pct:.1f}%")
        except psutil.NoSuchProcess:
            table.add_row(str(port), str(pid), "N/A", "N/A")
    
    console.print(table)
    
    # Show running tasks
    registry = get_process_registry()
    running_tasks = registry.get_running_tasks()
    
    if running_tasks:
        console.print(f"\n[cyan]📋 Running Tasks:[/cyan] {len(running_tasks)}")
        if verbose:
            for task in running_tasks:
                console.print(f"  Task {task['task_id']}: PID {task['pid']}")
                if task.get('claude_pids'):
                    console.print(f"    Claude PIDs: {', '.join(map(str, task['claude_pids']))}")
    
    # Show orphaned processes
    orphaned = registry.get_orphaned_processes()
    if orphaned:
        console.print(f"\n[yellow]⚠️  Orphaned Processes:[/yellow] {len(orphaned)}")
        console.print("[dim]Run 'claude-cto server cleanup' to clean them[/dim]")


@server_app.command(
    "recover",
    help="""[bold yellow]Recover from server crash[/bold yellow] 🔧
    
Perform full recovery after a server crash:
- Kill orphaned processes
- Mark stuck tasks as failed
- Clean up locks and registry

[bold]Example:[/bold]
  $ claude-cto server recover
""",
)
def server_recover():
    """Perform full recovery after server crash."""
    import asyncio
    from claude_cto.server.recovery import RecoveryService
    
    console.print("[yellow]🔧 Performing server recovery...[/yellow]\n")
    
    async def run_recovery():
        recovery = RecoveryService()
        stats = await recovery.recover_on_startup(8000)  # Default port
        return stats
    
    stats = asyncio.run(run_recovery())
    
    # Display recovery results
    console.print("[green]✓[/green] Recovery complete!\n")
    console.print(f"  Orphaned processes killed: {stats['orphaned_processes_killed']}")
    console.print(f"  Tasks marked as failed: {stats['tasks_marked_failed']}")
    console.print(f"  Claude processes terminated: {stats['claude_processes_terminated']}")
    console.print(f"  Stale locks cleaned: {stats['stale_locks_cleaned']}")
    console.print(f"  Registry entries cleaned: {stats['registry_entries_cleaned']}")
    
    console.print("\n[green]✨ Server ready to start![/green]")
    console.print("[dim]Start server with: claude-cto server start[/dim]")


@server_app.command(
    "health",
    help="""[bold cyan]Check server status[/bold cyan] 🏥
    
Verify if the Claude CTO server is running and healthy.

[bold]Example:[/bold]
  $ claude-cto server health
""",
)
def server_health():
    """Check if the server is healthy."""
    server_url = get_server_url()

    with httpx.Client() as client:
        try:
            response = client.get(f"{server_url}/health", timeout=5.0)
            response.raise_for_status()
            data = response.json()

            console.print(f"[green]✓[/green] Server is {data['status']}")
            console.print(f"Service: {data['service']}")

        except httpx.HTTPError:
            console.print(f"[red]✗[/red] Server is not responding at {server_url}")
            raise typer.Exit(1)


@app.command(
    "migrate",
    help="""[bold cyan]Run database migrations[/bold cyan] 🔄
    
Apply any pending database schema migrations.

[bold]Example:[/bold]
  $ claude-cto migrate
""",
)
def migrate():
    """Run database migrations."""
    from pathlib import Path
    from claude_cto.migrations.manager import MigrationManager

    console = Console()

    try:
        # Get database path
        app_dir = Path.home() / ".claude-cto"
        db_path = app_dir / "tasks.db"
        db_url = f"sqlite:///{db_path}"

        console.print("[cyan]Running database migrations...[/cyan]")

        # Create migration manager
        manager = MigrationManager(db_url)

        # Check current version
        current_version = manager.get_current_version()
        console.print(f"Current database version: {current_version}")

        # Run migrations
        applied = manager.run_migrations()

        if applied > 0:
            new_version = manager.get_current_version()
            console.print(f"[green]✓ Applied {applied} migration(s)[/green]")
            console.print(f"New database version: {new_version}")
        else:
            console.print("[green]✓ Database is up to date[/green]")

        # Check schema compatibility
        if manager.check_schema_compatibility():
            console.print("[green]✓ Schema compatibility check passed[/green]")
        else:
            console.print("[yellow]⚠ Schema compatibility check failed - manual intervention may be required[/yellow]")

    except Exception as e:
        console.print(f"[red]✗ Migration failed: {e}[/red]")
        raise typer.Exit(1)


# Entry point function for setuptools/pip
def cli_entry():
    """Entry point for the CLI executable."""
    app()

# Entry point for the CLI
if __name__ == "__main__":
    app()
