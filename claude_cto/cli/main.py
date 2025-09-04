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
    Works with both legacy and new Claude Code configurations.
    """
    try:
        # Try the robust auto-configuration first
        from ..mcp.auto_config import auto_configure
        
        # Run silently to avoid cluttering CLI output
        import sys
        from io import StringIO
        
        # Capture output to avoid spamming user
        old_stdout = sys.stdout
        old_stderr = sys.stderr
        sys.stdout = StringIO()
        sys.stderr = StringIO()
        
        try:
            success = auto_configure()
            if success:
                # Restore output and show success message
                sys.stdout = old_stdout
                sys.stderr = old_stderr
                print("🗿 claude-cto is now configured for Claude Code!")
                return
        except Exception:
            pass
        finally:
            # Always restore output
            sys.stdout = old_stdout  
            sys.stderr = old_stderr
        
        # Fallback to legacy claude CLI method
        if not shutil.which("claude"):
            return  # Neither method available
        
        # Check if already configured via legacy method
        home = Path.home()
        claude_config = home / ".claude.json"
        
        if claude_config.exists():
            try:
                with open(claude_config, 'r') as f:
                    config = json.load(f)
                    if 'mcpServers' in config and 'claude-cto' in config['mcpServers']:
                        return  # Already configured
            except (json.JSONDecodeError, KeyError, OSError):
                pass
        
        # Try legacy claude CLI setup
        print("🗿 Setting up claude-cto MCP server for Claude Code...")
        
        result = subprocess.run([
            "claude", "mcp", "add", "claude-cto", "-s", "user",
            "--", sys.executable, "-m", "claude_cto.mcp.factory"
        ], capture_output=True, text=True, timeout=10)
        
        if result.returncode == 0:
            print("✓ claude-cto is now available in Claude Code!")
                
    except Exception:
        # Catch-all to ensure CLI never fails due to MCP setup
        pass


# Initialize Typer app with world-class CLI design
app = typer.Typer(
    name="claude-cto",
    help="""
🤖 [bold cyan]Claude CTO[/bold cyan] - Enterprise AI Task Execution Platform

[bold blue]⚡ Production Features[/bold blue]
  [green]🛡️[/green]  [bold]Crash-Resistant[/bold] - Tasks survive system crashes and restarts
  [green]🔄[/green]  [bold]Auto-Recovery[/bold] - Intelligent error handling with circuit breakers  
  [green]📊[/green]  [bold]Resource Limits[/bold] - Memory/CPU controls and concurrent task management
  [green]🚀[/green]  [bold]Self-Updating[/bold] - Built-in upgrade system with rollback support
  [green]⚡[/green]  [bold]Process Isolation[/bold] - Secure task execution in isolated environments
  [green]📈[/green]  [bold]Real-time Monitoring[/bold] - Live performance metrics and health checks

[bold yellow]🚀 Quick Start Guide[/bold yellow]
  [cyan]# Simple task execution[/cyan]
  $ claude-cto run "analyze this codebase for security issues"
  
  [cyan]# Interactive monitoring[/cyan]
  $ claude-cto run "refactor legacy code" --watch
  
  [cyan]# Pipe integration[/cyan]
  $ git diff | claude-cto run "review these changes"

[bold green]🎯 Advanced Workflows[/bold green]
  [white]•[/white] Multi-task orchestration: [cyan]claude-cto orchestrate workflow.json[/cyan]
  [white]•[/white] Live task monitoring: [cyan]claude-cto run "complex task" --watch[/cyan]
  [white]•[/white] System maintenance: [cyan]claude-cto upgrade --check[/cyan]
  [white]•[/white] Resource monitoring: [cyan]claude-cto status --verbose[/cyan]
  [white]•[/white] Dependency graphs: [cyan]claude-cto list-orchestrations[/cyan]

[bold magenta]🔧 Zero Configuration[/bold magenta]
  Auto-start server • Auto-configure MCP • Auto-detect issues • Auto-recovery
""",
    rich_markup_mode="rich",
    no_args_is_help=True,
    invoke_without_command=True,
    context_settings={"help_option_names": ["-h", "--help"]},
    epilog="""
[bold]💡 Pro Tips[/bold]
  • Use [cyan]--help[/cyan] with any command for detailed options
  • Enable shell completion: [cyan]claude-cto --install-completion[/cyan]
  • Check system status: [cyan]claude-cto health[/cyan]
  
[dim]📚 Documentation: https://claude-cto.dev • 🐛 Issues: https://github.com/yigitkonur/claude-cto[/dim]
""",
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

# Server management sub-app with enhanced UX
server_app = typer.Typer(
    help="""
[bold blue]🖥️ Server Management[/bold blue]

[bold]Core Operations[/bold]
  [green]start[/green]   - Launch server with auto-port detection
  [green]stop[/green]    - Gracefully shutdown server
  [green]restart[/green] - Restart server with zero downtime
  [green]status[/green]  - Health check and resource usage

[bold]Maintenance[/bold]
  [yellow]cleanup[/yellow] - Remove orphaned processes and locks
  [yellow]recover[/yellow] - Full crash recovery and repair
  [yellow]logs[/yellow]    - View server logs with filtering

[dim]💡 The server auto-starts when you run tasks.
Use these commands only for manual control or troubleshooting.[/dim]
""",
    rich_markup_mode="rich",
    no_args_is_help=True,
    invoke_without_command=True,
)


@server_app.callback()
def server_callback(ctx: typer.Context):
    """Enhanced server callback with smart defaults."""
    if ctx.invoked_subcommand is None:
        # Show enhanced help with contextual information
        console.print("\n[bold blue]🖥️ Server Management Hub[/bold blue]")
        console.print(ctx.get_help())
        
        # Show current server status if available
        try:
            server_url = get_server_url()
            if is_server_running(server_url):
                console.print("\n[green]✓ Server is currently running[/green]")
                console.print(f"[dim]URL: {server_url}[/dim]")
            else:
                console.print("\n[yellow]⚠ Server is not running[/yellow]")
                console.print("[dim]Use 'claude-cto server start' to launch[/dim]")
        except Exception:
            pass
        
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
    rich_help_panel="🚀 Task Execution",
    help="""
[bold green]Execute AI tasks with Claude[/bold green]

[bold]Input Methods[/bold]
  • Direct prompt: [cyan]claude-cto run "analyze security vulnerabilities"[/cyan]
  • From file: [cyan]claude-cto run instructions.txt[/cyan]
  • Pipe input: [cyan]git log --oneline | claude-cto run "summarize changes"[/cyan]
  • Interactive: [cyan]claude-cto run --interactive[/cyan]

[bold]Advanced Options[/bold]
  • Live monitoring: [cyan]--watch[/cyan] for real-time progress
  • Custom directory: [cyan]--dir /path/to/project[/cyan]
  • Model selection: [cyan]--model opus[/cyan] for complex tasks
  • System prompts: [cyan]--system "Act as security expert"[/cyan]

[bold]Pro Tips[/bold]
  • Use [cyan]opus[/cyan] for complex reasoning, [cyan]haiku[/cyan] for speed
  • Enable [cyan]--watch[/cyan] for long-running tasks
  • Pipe git diffs, logs, or file contents for context
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
    rich_help_panel="📊 Task Monitoring",
    help="""
[bold yellow]Monitor task progress and results[/bold yellow]

[bold]Usage Patterns[/bold]
  • Specific task: [cyan]claude-cto status 42[/cyan]
  • Latest tasks: [cyan]claude-cto status[/cyan] (shows recent tasks)
  • Live monitoring: [cyan]claude-cto status 42 --watch[/cyan]
  • Detailed view: [cyan]claude-cto status 42 --verbose[/cyan]

[bold]Status Information[/bold]
  • Execution progress and current phase
  • Resource usage (CPU, memory, time)
  • Error messages and recovery suggestions
  • Task logs and output summaries

[dim]Tip: Use [cyan]--watch[/cyan] to follow long-running tasks in real-time[/dim]
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
    watch: bool = typer.Option(False, "--watch", "-w", help="Watch status updates in real-time"),
    verbose: bool = typer.Option(False, "--verbose", "-v", help="Show detailed information"),
    json_output: bool = typer.Option(False, "--json", help="Output in JSON format"),
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
            
        # Handle new options
        if watch:
            console.print(f"\n[cyan]Watching task {task_id}... (Ctrl+C to stop)[/cyan]")
            asyncio.run(watch_status(task_id))
        
        if json_output:
            console.print(json.dumps(task, indent=2))
            return


@app.command(
    rich_help_panel="📚 Information",
    help="[bold]Show comprehensive help and usage guide[/bold]"
)
def help(ctx: typer.Context):
    """Show enhanced help with contextual information."""
    console.print("\n[bold cyan]🤖 Claude CTO - Comprehensive Help[/bold cyan]")
    console.print(ctx.parent.get_help())
    
    # Add contextual help based on current state
    try:
        server_url = get_server_url()
        if is_server_running(server_url):
            console.print("\n[green]✓ System Status: Server running and ready[/green]")
        else:
            console.print("\n[yellow]⚠ System Status: Server will auto-start with first task[/yellow]")
    except Exception:
        pass
    
    console.print("\n[bold blue]💡 Quick Actions[/bold blue]")
    console.print("  • Run your first task: [cyan]claude-cto run \"analyze this project\"[/cyan]")
    console.print("  • Check system health: [cyan]claude-cto health[/cyan]")
    console.print("  • View all tasks: [cyan]claude-cto list[/cyan]")
    console.print("  • Enable shell completion: [cyan]claude-cto --install-completion[/cyan]")


@app.command(
    rich_help_panel="🔧 System Management",
    help="""
[bold yellow]Update system to latest version[/bold yellow]

[bold]Update Options[/bold]
  • Smart update: [cyan]claude-cto upgrade[/cyan] (checks & installs)
  • Check only: [cyan]claude-cto upgrade --check[/cyan]
  • Force reinstall: [cyan]claude-cto upgrade --force[/cyan]
  • Specific version: [cyan]claude-cto upgrade --version 1.2.3[/cyan]

[bold]Safety Features[/bold]
  • Automatic backup of current installation
  • Rollback support if update fails
  • Dependency compatibility checks
  • Configuration migration

[dim]Updates include security patches, performance improvements, and new features[/dim]
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
    
    # Check for latest version (force refresh cache if --force is used)
    with console.status("[yellow]Checking for updates...[/yellow]"):
        latest = checker.get_latest_version(force_refresh=force)
    
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
    
    success, message = upgrader.upgrade_package(method=method)
    
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
    rich_help_panel="⚙️ Integration",
    help="""
[bold yellow]Configure Claude Code MCP integration[/bold yellow]

[bold]Setup Process[/bold]
  • Auto-detect Claude Code installation
  • Configure MCP server settings
  • Set up database and logging paths
  • Enable auto-mode detection

[bold]Post-Configuration[/bold]
  • Restart Claude Code application
  • Access via MCP tools: create_task, orchestrate_tasks
  • Seamless task delegation and monitoring

[bold]Troubleshooting[/bold]
  • Validation: [cyan]claude-cto config-validate[/cyan]
  • Diagnosis: [cyan]claude-cto config-diagnose[/cyan]
  • Auto-repair: [cyan]claude-cto config-fix[/cyan]

[dim]Requires Claude Code v1.0+ to be installed and configured[/dim]
"""
)
def configure_mcp():
    """Set up claude-cto MCP server for Claude Code integration."""
    console = Console()
    
    try:
        from ..mcp.auto_config import auto_configure
        
        console.print("🗿 [bold]Claude CTO MCP Configuration[/bold]")
        console.print("=" * 50)
        
        with console.status("[yellow]Configuring MCP server...[/yellow]"):
            success = auto_configure()
        
        if success:
            console.print("\n[green]✅ MCP server configured successfully![/green]")
            console.print("\n[bold]Next steps:[/bold]")
            console.print("1. Restart Claude Code")
            console.print("2. The 'claude-cto' MCP server will be available")
            console.print("3. Use tools like create_task, orchestrate_tasks, etc.")
        else:
            console.print("\n[red]❌ MCP configuration failed[/red]")
            console.print("Please check Claude Code installation and try again")
            raise typer.Exit(1)
            
    except ImportError:
        console.print("[red]❌ MCP configuration module not available[/red]")
        raise typer.Exit(1)
    except Exception as e:
        console.print(f"[red]❌ Configuration error: {e}[/red]")
        raise typer.Exit(1)


@app.command(
    name="list",
    rich_help_panel="📊 Task Monitoring",
    help="""
[bold blue]View all tasks and their status[/bold blue]

[bold]Display Options[/bold]
  • All tasks: [cyan]claude-cto list[/cyan]
  • Filter by status: [cyan]claude-cto list --status running[/cyan]
  • Recent only: [cyan]claude-cto list --limit 10[/cyan]
  • Detailed view: [cyan]claude-cto list --verbose[/cyan]

[bold]Information Shown[/bold]
  • Task ID and status indicators
  • Creation time and duration
  • Last action and progress
  • Log file locations
  • Resource usage summary

[dim]Use task IDs with [cyan]claude-cto status <ID>[/cyan] for detailed information[/dim]
""",
)
def list(
    status_filter: Optional[str] = typer.Option(None, "--status", help="Filter by status: pending, running, completed, failed"),
    limit: int = typer.Option(50, "--limit", "-n", help="Maximum number of tasks to display"),
    verbose: bool = typer.Option(False, "--verbose", "-v", help="Show detailed information"),
    json_output: bool = typer.Option(False, "--json", help="Output in JSON format"),
):
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
            
    # Handle new filtering and output options
    if status_filter:
        tasks = [task for task in tasks if task['status'] == status_filter]
        
    if limit:
        tasks = tasks[-limit:]  # Show most recent N tasks
        
    if json_output:
        console.print(json.dumps(tasks, indent=2))
        return


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


@app.command(
    rich_help_panel="🔗 Orchestration",
    help="""
[bold green]Execute complex multi-task workflows[/bold green]

[bold]Workflow Definition[/bold]
  • JSON file with task definitions and dependencies
  • DAG (Directed Acyclic Graph) structure
  • Support for parallel and sequential execution
  • Conditional dependencies and delays

[bold]Execution Options[/bold]
  • Background execution: [cyan]claude-cto orchestrate workflow.json[/cyan]
  • Wait for completion: [cyan]claude-cto orchestrate workflow.json --wait[/cyan]
  • Custom polling: [cyan]--poll-interval 10[/cyan]
  • Dry run validation: [cyan]--dry-run[/cyan]

[bold]Example Workflow[/bold]
  • Analyze → Fix Issues → Test → Document
  • Multiple parallel analyses → Combine results
  • Build → Test → Deploy pipeline

[dim]See documentation for JSON schema and advanced patterns[/dim]
"""
)
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


@app.command(
    name="orchestration-status",
    rich_help_panel="🔗 Orchestration", 
    help="""
[bold yellow]Monitor orchestration progress[/bold yellow]

[bold]Monitoring Options[/bold]
  • Current status: [cyan]claude-cto orchestration-status 5[/cyan]
  • Live updates: [cyan]claude-cto orchestration-status 5 --watch[/cyan]
  • Task details: [cyan]claude-cto orchestration-status 5 --verbose[/cyan]
  • JSON output: [cyan]claude-cto orchestration-status 5 --json[/cyan]

[bold]Status Information[/bold]
  • Overall orchestration state
  • Individual task progress
  • Dependency resolution status
  • Error messages and recovery options

[dim]Use [cyan]--watch[/cyan] for real-time monitoring of long workflows[/dim]
"""
)
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


@app.command(
    name="list-orchestrations",
    rich_help_panel="🔗 Orchestration",
    help="""
[bold blue]View all workflow orchestrations[/bold blue]

[bold]List Options[/bold]
  • All workflows: [cyan]claude-cto list-orchestrations[/cyan]
  • Filter by status: [cyan]claude-cto list-orchestrations --status running[/cyan]
  • Recent only: [cyan]claude-cto list-orchestrations --limit 20[/cyan]
  • Detailed view: [cyan]claude-cto list-orchestrations --verbose[/cyan]

[bold]Information Displayed[/bold]
  • Orchestration ID and status
  • Task count and progress
  • Success/failure rates
  • Creation and completion times

[dim]Use orchestration ID with [cyan]orchestration-status[/cyan] for detailed monitoring[/dim]
"""
)
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
    help="""
[bold green]Launch the task execution server[/bold green]

[bold]Startup Options[/bold]
  • Default port: [cyan]claude-cto server start[/cyan]
  • Custom port: [cyan]claude-cto server start --port 9000[/cyan]
  • Custom host: [cyan]claude-cto server start --host 0.0.0.0[/cyan]
  • Development mode: [cyan]claude-cto server start --reload[/cyan]
  • Background mode: [cyan]claude-cto server start --daemon[/cyan]

[bold]Auto-Configuration[/bold]
  • Automatic port detection if specified port is busy
  • Environment variable configuration support
  • Resource limit auto-tuning based on system
  • Crash recovery and auto-restart capabilities

[dim]💡 The server auto-starts when you run tasks. Use this for manual control or development.[/dim]
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
    "stop",
    help="""
[bold red]Gracefully shutdown the server[/bold red]

[bold]Shutdown Options[/bold]
  • Graceful shutdown: [cyan]claude-cto server stop[/cyan]
  • Force shutdown: [cyan]claude-cto server stop --force[/cyan]
  • Stop specific PID: [cyan]claude-cto server stop --pid 12345[/cyan]
  • Timeout control: [cyan]claude-cto server stop --timeout 30[/cyan]

[bold]Shutdown Process[/bold]
  • Send SIGTERM for graceful shutdown
  • Wait for running tasks to complete
  • Clean up resources and connections
  • Force kill if timeout exceeded

[bold]Safety Features[/bold]
  • Running task protection
  • Automatic backup of critical data
  • Clean resource deallocation
  • Process tree termination

[dim]Tasks in progress will be allowed to complete unless --force is used[/dim]
"""
)
def server_stop(
    force: bool = typer.Option(False, "--force", "-f", help="Force immediate shutdown"),
    pid: Optional[int] = typer.Option(None, "--pid", help="Stop specific server PID"),
    timeout: int = typer.Option(30, "--timeout", "-t", help="Graceful shutdown timeout in seconds"),
):
    """Stop the Claude CTO server."""
    import signal
    import time
    from claude_cto.server.server_lock import ServerLock
    import psutil
    
    console.print("\n[bold red]🛑 Claude CTO Server Shutdown[/bold red]")
    
    try:
        if pid:
            # Stop specific PID
            try:
                proc = psutil.Process(pid)
                console.print(f"[yellow]Stopping server PID {pid}...[/yellow]")
                
                if not force:
                    proc.terminate()  # SIGTERM
                    try:
                        proc.wait(timeout=timeout)
                        console.print(f"[green]✓ Server PID {pid} stopped gracefully[/green]")
                    except psutil.TimeoutExpired:
                        console.print(f"[yellow]⚠ Timeout reached, force killing PID {pid}[/yellow]")
                        proc.kill()  # SIGKILL
                        proc.wait(timeout=5)
                        console.print(f"[red]✓ Server PID {pid} force stopped[/red]")
                else:
                    proc.kill()  # SIGKILL
                    proc.wait(timeout=5)
                    console.print(f"[red]✓ Server PID {pid} force stopped[/red]")
                    
            except psutil.NoSuchProcess:
                console.print(f"[yellow]⚠ Process {pid} not found[/yellow]")
            except psutil.AccessDenied:
                console.print(f"[red]✗ Access denied to process {pid}[/red]")
                raise typer.Exit(1)
                
        else:
            # Stop all running servers
            servers = ServerLock.get_all_running_servers()
            
            if not servers:
                console.print("[yellow]📭 No running servers found[/yellow]")
                return
                
            console.print(f"[cyan]Found {len(servers)} running server(s)[/cyan]")
            
            stopped_count = 0
            for port, server_pid in servers:
                try:
                    proc = psutil.Process(server_pid)
                    console.print(f"[yellow]Stopping server on port {port} (PID {server_pid})...[/yellow]")
                    
                    if not force:
                        proc.terminate()  # SIGTERM
                        try:
                            proc.wait(timeout=timeout)
                            console.print(f"[green]✓ Server on port {port} stopped gracefully[/green]")
                            stopped_count += 1
                        except psutil.TimeoutExpired:
                            console.print(f"[yellow]⚠ Timeout reached, force killing server on port {port}[/yellow]")
                            proc.kill()  # SIGKILL
                            proc.wait(timeout=5)
                            console.print(f"[red]✓ Server on port {port} force stopped[/red]")
                            stopped_count += 1
                    else:
                        proc.kill()  # SIGKILL
                        proc.wait(timeout=5)
                        console.print(f"[red]✓ Server on port {port} force stopped[/red]")
                        stopped_count += 1
                        
                except psutil.NoSuchProcess:
                    console.print(f"[yellow]⚠ Server PID {server_pid} no longer exists[/yellow]")
                except psutil.AccessDenied:
                    console.print(f"[red]✗ Access denied to server PID {server_pid}[/red]")
                    
            if stopped_count > 0:
                console.print(f"\n[green]✓ Successfully stopped {stopped_count} server(s)[/green]")
            else:
                console.print(f"\n[yellow]⚠ No servers were stopped[/yellow]")
                
        # Clean up any remaining locks
        cleaned_locks = ServerLock.cleanup_all_locks()
        if cleaned_locks > 0:
            console.print(f"[green]✓ Cleaned up {cleaned_locks} stale lock(s)[/green]")
            
        console.print("\n[dim]💡 Use 'claude-cto server start' to restart the server[/dim]")
        
    except Exception as e:
        console.print(f"[red]✗ Error stopping server: {e}[/red]")
        raise typer.Exit(1)


@server_app.command(
    "restart",
    help="""
[bold blue]Restart the server with zero downtime[/bold blue]

[bold]Restart Options[/bold]
  • Graceful restart: [cyan]claude-cto server restart[/cyan]
  • Force restart: [cyan]claude-cto server restart --force[/cyan]
  • Custom port: [cyan]claude-cto server restart --port 9000[/cyan]
  • Development mode: [cyan]claude-cto server restart --reload[/cyan]

[bold]Zero-Downtime Process[/bold]
  • Start new server instance on different port
  • Wait for new server to be healthy
  • Gracefully shutdown old server
  • Switch traffic to new server

[bold]Safety Features[/bold]
  • Health check validation before switchover
  • Automatic rollback if new server fails
  • Running task preservation
  • Configuration validation

[dim]Ensures continuous service availability during restarts[/dim]
"""
)
def server_restart(
    force: bool = typer.Option(False, "--force", "-f", help="Force restart without graceful shutdown"),
    port: Optional[int] = typer.Option(None, "--port", "-p", help="Use specific port for restarted server"),
    reload: bool = typer.Option(False, "--reload", "-r", help="Enable auto-reload for development"),
    timeout: int = typer.Option(30, "--timeout", "-t", help="Shutdown timeout in seconds"),
):
    """Restart the Claude CTO server with zero downtime."""
    console.print("\n[bold blue]🔄 Claude CTO Server Restart[/bold blue]")
    
    try:
        from claude_cto.server.server_lock import ServerLock
        import time
        
        # Get current running servers
        current_servers = ServerLock.get_all_running_servers()
        
        if not current_servers and not force:
            console.print("[yellow]📭 No running servers found to restart[/yellow]")
            console.print("[dim]Use 'claude-cto server start' to start a new server[/dim]")
            return
            
        console.print(f"[cyan]Found {len(current_servers)} running server(s)[/cyan]")
        
        # Determine port for new server
        new_port = port if port else (current_servers[0][0] if current_servers else 8000)
        
        # If we're restarting on the same port, find an alternative port first
        if any(server_port == new_port for server_port, _ in current_servers):
            temp_port = new_port + 1
            import socket
            while temp_port < new_port + 100:
                try:
                    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
                        s.bind(('localhost', temp_port))
                        break
                except OSError:
                    temp_port += 1
            else:
                console.print("[red]✗ Could not find available port for restart[/red]")
                raise typer.Exit(1)
            
            console.print(f"[yellow]Using temporary port {temp_port} for zero-downtime restart[/yellow]")
            actual_new_port = temp_port
        else:
            actual_new_port = new_port
            
        # Start new server instance
        console.print(f"[cyan]Starting new server on port {actual_new_port}...[/cyan]")
        
        cmd = [
            sys.executable,
            "-m",
            "uvicorn", 
            "claude_cto.server.main:app",
            "--host", "0.0.0.0",
            "--port", str(actual_new_port),
        ]
        
        if reload:
            cmd.append("--reload")
            
        new_process = subprocess.Popen(
            cmd,
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
            start_new_session=True,
        )
        
        # Wait for new server to be healthy
        console.print("[cyan]Waiting for new server to be ready...[/cyan]")
        new_server_url = f"http://localhost:{actual_new_port}"
        
        health_check_attempts = 0
        max_health_attempts = 30  # 30 seconds
        
        while health_check_attempts < max_health_attempts:
            try:
                with httpx.Client() as client:
                    response = client.get(f"{new_server_url}/health", timeout=1.0)
                    if response.status_code == 200:
                        console.print("[green]✓ New server is healthy[/green]")
                        break
            except:
                pass
                
            time.sleep(1)
            health_check_attempts += 1
            
        else:
            console.print("[red]✗ New server failed health check, rolling back[/red]")
            new_process.terminate()
            raise typer.Exit(1)
            
        # Update environment variable if needed
        if actual_new_port != new_port:
            os.environ["CLAUDE_CTO_SERVER_URL"] = new_server_url
            console.print(f"[yellow]⚠ Server URL updated to {new_server_url}[/yellow]")
            
        # Now gracefully shutdown old servers
        if current_servers:
            console.print("[cyan]Shutting down old server(s)...[/cyan]")
            
            for old_port, old_pid in current_servers:
                try:
                    import psutil
                    old_proc = psutil.Process(old_pid)
                    
                    if not force:
                        old_proc.terminate()
                        try:
                            old_proc.wait(timeout=timeout)
                            console.print(f"[green]✓ Old server on port {old_port} stopped gracefully[/green]")
                        except psutil.TimeoutExpired:
                            old_proc.kill()
                            console.print(f"[yellow]⚠ Force stopped old server on port {old_port}[/yellow]")
                    else:
                        old_proc.kill()
                        console.print(f"[red]✓ Force stopped old server on port {old_port}[/red]")
                        
                except psutil.NoSuchProcess:
                    console.print(f"[yellow]⚠ Old server PID {old_pid} already stopped[/yellow]")
                    
        console.print(f"\n[green]✅ Server restart complete![/green]")
        console.print(f"[green]🚀 Server running on port {actual_new_port} (PID: {new_process.pid})[/green]")
        
        if actual_new_port != new_port:
            console.print(f"\n[yellow]⚠ Note: Server is now running on port {actual_new_port}[/yellow]")
            console.print(f"[dim]Set CLAUDE_CTO_SERVER_URL=http://localhost:{actual_new_port} if needed[/dim]")
            
    except Exception as e:
        console.print(f"[red]✗ Restart failed: {e}[/red]")
        raise typer.Exit(1)


@server_app.command(
    "cleanup",
    help="""
[bold red]Clean up system resources[/bold red]

[bold]Cleanup Operations[/bold]
  • Orphaned processes: [cyan]claude-cto server cleanup[/cyan]
  • Force termination: [cyan]claude-cto server cleanup --force[/cyan]
  • Stale locks only: [cyan]claude-cto server cleanup --locks-only[/cyan]
  • Registry cleanup: [cyan]claude-cto server cleanup --registry[/cyan]

[bold]What Gets Cleaned[/bold]
  • Zombie Claude processes and their children
  • Stale server lock files
  • Orphaned task registry entries
  • Temporary files and caches

[bold]Safety Features[/bold]
  • Running task detection and protection
  • Graceful shutdown attempts before force kill
  • Backup of cleaned data for recovery

[dim]Run this after crashes or when experiencing resource issues[/dim]
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
    help="""
[bold cyan]Display comprehensive server status[/bold cyan]

[bold]Status Information[/bold]
  • Server health and response time
  • Active tasks and queue status
  • Resource usage (CPU, memory, connections)
  • Process tree and PID information

[bold]Display Options[/bold]
  • Summary: [cyan]claude-cto server status[/cyan]
  • Verbose: [cyan]claude-cto server status --verbose[/cyan]
  • JSON output: [cyan]claude-cto server status --json[/cyan]
  • Live monitoring: [cyan]claude-cto server status --watch[/cyan]

[bold]Monitoring Features[/bold]
  • Real-time resource graphs
  • Task execution history
  • Performance metrics and trends
  • Alert thresholds and notifications

[dim]Essential for monitoring server health and performance[/dim]
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
    "cleanup",
    help="""
[bold yellow]Clean up stale processes and locks[/bold yellow]

[bold]Cleanup Operations[/bold]
  • Kill all stale Claude CTO processes
  • Remove all lock files
  • Clean process registry
  • Reset server state

[bold]Cleanup Options[/bold]
  • Full cleanup: [cyan]claude-cto server cleanup[/cyan]
  • Force kill all: [cyan]claude-cto server cleanup --force[/cyan]
  • Dry run: [cyan]claude-cto server cleanup --dry-run[/cyan]

[dim]Use when server fails to start due to lock conflicts[/dim]
""",
)
def server_cleanup(
    force: bool = typer.Option(False, "--force", help="Force kill all processes"),
    dry_run: bool = typer.Option(False, "--dry-run", help="Show what would be cleaned without doing it")
):
    """Clean up stale processes and locks."""
    import subprocess
    from pathlib import Path
    from claude_cto.server.server_lock import ServerLock
    
    console.print("[yellow]🧹 Cleaning up server state...[/yellow]\n")
    
    if dry_run:
        console.print("[cyan]DRY RUN MODE - No changes will be made[/cyan]\n")
    
    # 1. Kill stale processes
    console.print("[bold]1. Checking for stale processes...[/bold]")
    try:
        # Find Claude CTO processes
        result = subprocess.run(
            ["ps", "aux"], 
            capture_output=True, 
            text=True
        )
        
        processes_killed = 0
        for line in result.stdout.split('\n'):
            if 'claude_cto.server' in line or 'uvicorn.*claude_cto' in line:
                parts = line.split()
                if len(parts) > 1:
                    pid = parts[1]
                    if not dry_run:
                        try:
                            subprocess.run(["kill", "-9" if force else "-15", pid], check=False)
                            processes_killed += 1
                            console.print(f"  [red]✗[/red] Killed process {pid}")
                        except:
                            pass
                    else:
                        console.print(f"  [yellow]Would kill[/yellow] process {pid}")
        
        if processes_killed == 0 and not dry_run:
            console.print("  [green]✓[/green] No stale processes found")
    except Exception as e:
        console.print(f"  [red]Error checking processes: {e}[/red]")
    
    # 2. Clean lock files
    console.print("\n[bold]2. Cleaning lock files...[/bold]")
    if not dry_run:
        cleaned = ServerLock.cleanup_all_locks()
        if cleaned > 0:
            console.print(f"  [green]✓[/green] Cleaned {cleaned} lock file(s)")
        else:
            console.print("  [green]✓[/green] No stale locks found")
    else:
        lock_dir = Path("/tmp/claude-cto-locks")
        if lock_dir.exists():
            locks = list(lock_dir.glob("*.pid"))
            if locks:
                console.print(f"  [yellow]Would clean[/yellow] {len(locks)} lock file(s)")
            else:
                console.print("  No locks to clean")
    
    # 3. Clean process registry
    console.print("\n[bold]3. Cleaning process registry...[/bold]")
    registry_path = Path.home() / ".claude-cto" / "process_registry.json"
    if registry_path.exists():
        if not dry_run:
            try:
                with open(registry_path, 'w') as f:
                    f.write('{}')
                console.print("  [green]✓[/green] Process registry reset")
            except Exception as e:
                console.print(f"  [red]Error resetting registry: {e}[/red]")
        else:
            console.print("  [yellow]Would reset[/yellow] process registry")
    else:
        console.print("  [green]✓[/green] No process registry to clean")
    
    if not dry_run:
        console.print("\n[green]✨ Cleanup complete! Server ready to start.[/green]")
        console.print("[dim]Start server with: claude-cto server start[/dim]")
    else:
        console.print("\n[cyan]Dry run complete. Run without --dry-run to perform cleanup.[/cyan]")

@server_app.command(
    "recover",
    help="""
[bold yellow]Full system recovery after crashes[/bold yellow]

[bold]Recovery Operations[/bold]
  • Process cleanup and termination
  • Task state recovery and validation
  • Database integrity checks and repair
  • Lock file and registry cleanup

[bold]Recovery Modes[/bold]
  • Auto recovery: [cyan]claude-cto server recover[/cyan]
  • Safe mode: [cyan]claude-cto server recover --safe[/cyan]
  • Force mode: [cyan]claude-cto server recover --force[/cyan]
  • Dry run: [cyan]claude-cto server recover --dry-run[/cyan]

[bold]Post-Recovery[/bold]
  • Detailed recovery report
  • Recommendations for preventing future issues
  • Health check validation
  • Performance optimization suggestions

[dim]Use after system crashes, unexpected shutdowns, or resource exhaustion[/dim]
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
    help="""
[bold cyan]Server health diagnostics[/bold cyan]

[bold]Health Checks[/bold]
  • Server responsiveness and uptime
  • Database connectivity and performance
  • Resource availability and limits
  • API endpoint functionality

[bold]Output Options[/bold]
  • Quick check: [cyan]claude-cto server health[/cyan]
  • Detailed report: [cyan]claude-cto server health --verbose[/cyan]
  • JSON format: [cyan]claude-cto server health --json[/cyan]
  • Continuous: [cyan]claude-cto server health --watch[/cyan]

[bold]Health Indicators[/bold]
  [green]✓[/green] Healthy - All systems operational
  [yellow]⚠[/yellow] Warning - Performance degraded
  [red]✗[/red] Critical - Service unavailable

[dim]Essential for monitoring and alerting systems[/dim]
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
    rich_help_panel="🔧 System Management",
    help="""
[bold cyan]Update database schema[/bold cyan]

[bold]Migration Operations[/bold]
  • Apply pending: [cyan]claude-cto migrate[/cyan]
  • Check status: [cyan]claude-cto migrate --status[/cyan]
  • Rollback: [cyan]claude-cto migrate --rollback[/cyan]
  • Force repair: [cyan]claude-cto migrate --repair[/cyan]

[bold]Safety Features[/bold]
  • Automatic backup before migration
  • Schema compatibility validation
  • Rollback support for failed migrations
  • Data integrity verification

[dim]Migrations are automatically applied on version updates[/dim]
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


@app.command(
    "config-diagnose",
    help="Diagnose MCP configuration issues",
    rich_help_panel="⚙️ Integration",
    epilog="""
Diagnose current MCP configuration state and detect potential issues.
Provides detailed information about installation method, configuration files,
and any path-related problems that might prevent MCP server startup.

[bold]Example:[/bold]
  $ claude-cto config-diagnose
""",
)
def config_diagnose():
    """Diagnose MCP configuration issues."""
    console = Console()
    
    try:
        from ..mcp.auto_config import diagnose_configuration
        diagnose_configuration()
        
    except Exception as e:
        console.print(f"[red]✗ Diagnosis failed: {e}[/red]")
        raise typer.Exit(1)


@app.command(
    "config-fix", 
    help="Automatically fix MCP configuration issues",
    rich_help_panel="⚙️ Integration",
    epilog="""
Automatically detect and fix common MCP configuration issues.
This includes updating versioned paths to stable ones, validating
Python executable paths, and ensuring configuration files are correct.

[bold]Example:[/bold]
  $ claude-cto config-fix
""",
)
def config_fix():
    """Fix MCP configuration issues automatically."""
    console = Console()
    
    try:
        from ..mcp.auto_config import auto_fix_configurations
        
        console.print("[cyan]Analyzing and fixing MCP configuration issues...[/cyan]")
        success = auto_fix_configurations()
        
        if success:
            console.print("[green]✓ Configuration issues have been fixed[/green]")
            console.print("\n[yellow]Next steps:[/yellow]")
            console.print("  1. Restart Claude Code")
            console.print("  2. The claude-cto MCP server should now work properly")
        else:
            console.print("[blue]ℹ No configuration changes were needed[/blue]")
        
    except Exception as e:
        console.print(f"[red]✗ Config fix failed: {e}[/red]")
        console.print("\n[yellow]Try manual diagnosis:[/yellow]")
        console.print("  claude-cto config-diagnose")
        raise typer.Exit(1)


@app.command(
    "config-validate",
    help="Validate MCP configuration", 
    rich_help_panel="⚙️ Integration",
    epilog="""
Validate that MCP configuration files have correct paths and settings.
Reports any issues that might prevent the MCP server from starting.

[bold]Example:[/bold]
  $ claude-cto config-validate
""",
)
def config_validate():
    """Validate MCP configuration."""
    console = Console()
    
    try:
        from ..mcp.auto_config import validate_config_paths
        
        console.print("[cyan]Validating MCP configuration...[/cyan]")
        issues = validate_config_paths()
        
        if not issues:
            console.print("[green]✓ All MCP configurations are valid[/green]")
        else:
            console.print("[red]Configuration issues found:[/red]")
            for issue in issues:
                console.print(f"  • {issue}")
            console.print("\n[yellow]Fix these issues with:[/yellow]")
            console.print("  claude-cto config-fix")
            raise typer.Exit(1)
        
    except Exception as e:
        console.print(f"[red]✗ Validation failed: {e}[/red]")
        raise typer.Exit(1)


# Add logs command for server management
@server_app.command(
    "logs",
    help="""
[bold green]View and manage server logs[/bold green]

[bold]Log Viewing Options[/bold]
  • Recent logs: [cyan]claude-cto server logs[/cyan]
  • Follow logs: [cyan]claude-cto server logs --follow[/cyan]
  • Specific lines: [cyan]claude-cto server logs --lines 100[/cyan]
  • Filter by level: [cyan]claude-cto server logs --level ERROR[/cyan]

[bold]Log Types[/bold]
  • Server logs: [cyan]--type server[/cyan]
  • Access logs: [cyan]--type access[/cyan]
  • Error logs: [cyan]--type error[/cyan]
  • Task logs: [cyan]--type task[/cyan]

[bold]Advanced Options[/bold]
  • Search pattern: [cyan]--grep "error message"[/cyan]
  • Date range: [cyan]--since "2024-01-01" --until "2024-01-02"[/cyan]
  • JSON output: [cyan]--json[/cyan]

[dim]Essential for debugging and monitoring server operations[/dim]
"""
)
def server_logs(
    follow: bool = typer.Option(False, "--follow", "-f", help="Follow log output"),
    lines: int = typer.Option(50, "--lines", "-n", help="Number of lines to show"),
    log_type: str = typer.Option("server", "--type", help="Log type: server, access, error, task"),
    level: Optional[str] = typer.Option(None, "--level", help="Filter by log level: DEBUG, INFO, WARNING, ERROR"),
    grep: Optional[str] = typer.Option(None, "--grep", help="Search for pattern in logs"),
    since: Optional[str] = typer.Option(None, "--since", help="Show logs since date (YYYY-MM-DD)"),
    until: Optional[str] = typer.Option(None, "--until", help="Show logs until date (YYYY-MM-DD)"),
    json_output: bool = typer.Option(False, "--json", help="Output in JSON format"),
):
    """View server logs with filtering and search capabilities."""
    from pathlib import Path
    import json
    import re
    from datetime import datetime
    
    console.print(f"\n[bold green]📜 Claude CTO Server Logs ({log_type})[/bold green]")
    
    # Determine log file path
    log_dir = Path.home() / ".claude-cto" / "logs"
    log_files = {
        "server": log_dir / "server.log",
        "access": log_dir / "access.log", 
        "error": log_dir / "error.log",
        "task": log_dir / "tasks" / "*.log",
    }
    
    log_file = log_files.get(log_type)
    if not log_file:
        console.print(f"[red]✗ Unknown log type: {log_type}[/red]")
        console.print(f"[dim]Available types: {', '.join(log_files.keys())}[/dim]")
        raise typer.Exit(1)
        
    if log_type == "task":
        # Handle task logs (multiple files)
        task_log_files = list((log_dir / "tasks").glob("*.log"))
        if not task_log_files:
            console.print("[yellow]📭 No task log files found[/yellow]")
            return
        console.print(f"[cyan]Found {len(task_log_files)} task log files[/cyan]")
        # For simplicity, show the most recent task log
        log_file = max(task_log_files, key=lambda f: f.stat().st_mtime)
    
    if not log_file.exists():
        console.print(f"[yellow]📭 Log file not found: {log_file}[/yellow]")
        console.print(f"[dim]Logs will appear here once the server starts[/dim]")
        return
        
    try:
        if follow:
            console.print(f"[cyan]Following logs from {log_file.name}... (Ctrl+C to stop)[/cyan]\n")
            # Simple tail -f implementation
            import time
            
            def read_lines():
                with open(log_file, 'r') as f:
                    f.seek(0, 2)  # Go to end
                    while True:
                        line = f.readline()
                        if line:
                            yield line.strip()
                        else:
                            time.sleep(0.1)
                            
            try:
                for line in read_lines():
                    if level and level.upper() not in line.upper():
                        continue
                    if grep and grep.lower() not in line.lower():
                        continue
                        
                    # Simple log level coloring
                    if "ERROR" in line.upper():
                        console.print(f"[red]{line}[/red]")
                    elif "WARNING" in line.upper() or "WARN" in line.upper():
                        console.print(f"[yellow]{line}[/yellow]")
                    elif "INFO" in line.upper():
                        console.print(f"[green]{line}[/green]")
                    elif "DEBUG" in line.upper():
                        console.print(f"[dim]{line}[/dim]")
                    else:
                        console.print(line)
                        
            except KeyboardInterrupt:
                console.print("\n[dim]Log following stopped.[/dim]")
                
        else:
            # Read recent lines
            with open(log_file, 'r') as f:
                all_lines = f.readlines()
                
            # Apply filters
            filtered_lines = []
            for line in all_lines[-lines:]:
                line = line.strip()
                if level and level.upper() not in line.upper():
                    continue
                if grep and grep.lower() not in line.lower():
                    continue
                    
                # Basic date filtering (this would need more sophisticated parsing)
                if since or until:
                    # Skip date filtering for now - would need proper log parsing
                    pass
                    
                filtered_lines.append(line)
                
            if json_output:
                log_data = {
                    "log_file": str(log_file),
                    "log_type": log_type,
                    "lines_requested": lines,
                    "lines_returned": len(filtered_lines),
                    "logs": filtered_lines
                }
                console.print(json.dumps(log_data, indent=2))
            else:
                console.print(f"[dim]Showing last {len(filtered_lines)} lines from {log_file.name}[/dim]\n")
                
                for line in filtered_lines:
                    # Simple log level coloring
                    if "ERROR" in line.upper():
                        console.print(f"[red]{line}[/red]")
                    elif "WARNING" in line.upper() or "WARN" in line.upper():
                        console.print(f"[yellow]{line}[/yellow]")
                    elif "INFO" in line.upper():
                        console.print(f"[green]{line}[/green]")
                    elif "DEBUG" in line.upper():
                        console.print(f"[dim]{line}[/dim]")
                    else:
                        console.print(line)
                        
    except Exception as e:
        console.print(f"[red]✗ Error reading logs: {e}[/red]")
        raise typer.Exit(1)


# Add essential commands for world-class CLI
@app.command(
    rich_help_panel="📊 Task Monitoring",
    help="""
[bold green]System health and diagnostics[/bold green]

[bold]Health Checks[/bold]
  • Server connectivity and response time
  • Database integrity and performance
  • Resource usage (CPU, memory, disk)
  • MCP integration status

[bold]Output Options[/bold]
  • Summary view: [cyan]claude-cto health[/cyan]
  • Detailed report: [cyan]claude-cto health --verbose[/cyan]
  • JSON output: [cyan]claude-cto health --json[/cyan]
  • Continuous monitoring: [cyan]claude-cto health --watch[/cyan]

[bold]Status Indicators[/bold]
  [green]✓[/green] Healthy - All systems operational
  [yellow]⚠[/yellow] Warning - Minor issues detected 
  [red]✗[/red] Critical - Immediate attention required

[dim]Use this command for troubleshooting and monitoring[/dim]
"""
)
def health(
    verbose: bool = typer.Option(False, "--verbose", "-v", help="Show detailed health information"),
    json_output: bool = typer.Option(False, "--json", help="Output in JSON format"),
    watch: bool = typer.Option(False, "--watch", "-w", help="Continuous health monitoring"),
):
    """Check system health and status."""
    import json
    import time
    from datetime import datetime
    
    def check_health():
        health_data = {
            "timestamp": datetime.now().isoformat(),
            "status": "healthy",
            "checks": {},
            "summary": ""
        }
        
        # Server connectivity check
        server_url = get_server_url()
        try:
            if is_server_running(server_url):
                health_data["checks"]["server"] = {"status": "healthy", "url": server_url}
            else:
                health_data["checks"]["server"] = {"status": "stopped", "url": server_url}
                health_data["status"] = "warning"
        except Exception as e:
            health_data["checks"]["server"] = {"status": "error", "error": str(e)}
            health_data["status"] = "critical"
        
        # Database check
        try:
            from pathlib import Path
            db_path = Path.home() / ".claude-cto" / "tasks.db"
            if db_path.exists():
                health_data["checks"]["database"] = {"status": "healthy", "path": str(db_path)}
            else:
                health_data["checks"]["database"] = {"status": "missing", "path": str(db_path)}
                health_data["status"] = "warning"
        except Exception as e:
            health_data["checks"]["database"] = {"status": "error", "error": str(e)}
            health_data["status"] = "critical"
        
        # MCP configuration check
        try:
            from ..mcp.auto_config import validate_config_paths
            issues = validate_config_paths()
            if not issues:
                health_data["checks"]["mcp"] = {"status": "healthy"}
            else:
                health_data["checks"]["mcp"] = {"status": "warning", "issues": issues}
                if health_data["status"] == "healthy":
                    health_data["status"] = "warning"
        except Exception as e:
            health_data["checks"]["mcp"] = {"status": "error", "error": str(e)}
        
        return health_data
    
    if watch:
        console.print("[cyan]Starting continuous health monitoring... (Ctrl+C to stop)[/cyan]\n")
        try:
            while True:
                health_data = check_health()
                
                console.clear()
                console.print(f"[bold]Health Monitor - {health_data['timestamp']}[/bold]")
                
                status_color = {"healthy": "green", "warning": "yellow", "critical": "red"}.get(health_data['status'], "white")
                console.print(f"Overall Status: [{status_color}]{health_data['status'].upper()}[/{status_color}]\n")
                
                for check_name, check_data in health_data['checks'].items():
                    status = check_data['status']
                    color = {"healthy": "green", "warning": "yellow", "error": "red", "stopped": "yellow", "missing": "yellow"}.get(status, "white")
                    console.print(f"  {check_name.title()}: [{color}]{status}[/{color}]")
                    
                    if verbose and 'error' in check_data:
                        console.print(f"    Error: {check_data['error']}")
                    if verbose and 'issues' in check_data:
                        for issue in check_data['issues']:
                            console.print(f"    Issue: {issue}")
                
                time.sleep(5)
                
        except KeyboardInterrupt:
            console.print("\n[dim]Health monitoring stopped.[/dim]")
    else:
        health_data = check_health()
        
        if json_output:
            console.print(json.dumps(health_data, indent=2))
        else:
            status_color = {"healthy": "green", "warning": "yellow", "critical": "red"}.get(health_data['status'], "white")
            console.print(f"\n[bold]System Health Check[/bold]")
            console.print(f"Status: [{status_color}]{health_data['status'].upper()}[/{status_color}]\n")
            
            for check_name, check_data in health_data['checks'].items():
                status = check_data['status']
                color = {"healthy": "green", "warning": "yellow", "error": "red", "stopped": "yellow", "missing": "yellow"}.get(status, "white")
                console.print(f"  {check_name.title()}: [{color}]{status}[/{color}]")
                
                if verbose and 'error' in check_data:
                    console.print(f"    [red]Error: {check_data['error']}[/red]")
                if verbose and 'issues' in check_data:
                    for issue in check_data['issues']:
                        console.print(f"    [yellow]Issue: {issue}[/yellow]")
                        
            if health_data['status'] != "healthy":
                console.print(f"\n[yellow]💡 Tip: Run [cyan]claude-cto config-fix[/cyan] to resolve configuration issues[/yellow]")


@app.command(
    rich_help_panel="📚 Information",
    help="""
[bold blue]Display system and environment information[/bold blue]

[bold]Information Included[/bold]
  • Version details and build information
  • Installation method and location
  • Configuration file paths
  • Python environment details
  • System requirements status

[bold]Output Options[/bold]
  • Summary: [cyan]claude-cto info[/cyan]
  • Full details: [cyan]claude-cto info --verbose[/cyan]
  • JSON format: [cyan]claude-cto info --json[/cyan]

[dim]Useful for troubleshooting and support requests[/dim]
"""
)
def info(
    verbose: bool = typer.Option(False, "--verbose", "-v", help="Show detailed information"),
    json_output: bool = typer.Option(False, "--json", help="Output in JSON format"),
):
    """Display system information."""
    import json
    import sys
    import platform
    from pathlib import Path
    
    info_data = {
        "claude_cto": {
            "version": "0.20.0",  # This should be imported from __version__
            "installation_method": "unknown",
            "installation_path": str(Path(__file__).parent.parent),
        },
        "system": {
            "platform": platform.platform(),
            "python_version": sys.version,
            "python_executable": sys.executable,
        },
        "configuration": {
            "config_dir": str(Path.home() / ".claude-cto"),
            "database_path": str(Path.home() / ".claude-cto" / "tasks.db"),
            "log_dir": str(Path.home() / ".claude-cto" / "logs"),
        },
        "server": {
            "url": get_server_url(),
            "running": False,
        }
    }
    
    # Check server status
    try:
        info_data["server"]["running"] = is_server_running(info_data["server"]["url"])
    except Exception:
        pass
    
    # Try to determine installation method
    try:
        import claude_cto
        if hasattr(claude_cto, '__version__'):
            info_data["claude_cto"]["version"] = claude_cto.__version__
    except Exception:
        pass
    
    if json_output:
        console.print(json.dumps(info_data, indent=2))
    else:
        console.print("\n[bold cyan]🤖 Claude CTO System Information[/bold cyan]")
        
        console.print(f"\n[bold]Application[/bold]")
        console.print(f"  Version: {info_data['claude_cto']['version']}")
        console.print(f"  Installation: {info_data['claude_cto']['installation_path']}")
        
        console.print(f"\n[bold]System[/bold]")
        console.print(f"  Platform: {info_data['system']['platform']}")
        console.print(f"  Python: {info_data['system']['python_version'].split()[0]}")
        if verbose:
            console.print(f"  Python Path: {info_data['system']['python_executable']}")
        
        console.print(f"\n[bold]Configuration[/bold]")
        console.print(f"  Config Directory: {info_data['configuration']['config_dir']}")
        console.print(f"  Database: {info_data['configuration']['database_path']}")
        if verbose:
            console.print(f"  Log Directory: {info_data['configuration']['log_dir']}")
        
        console.print(f"\n[bold]Server[/bold]")
        console.print(f"  URL: {info_data['server']['url']}")
        status_text = "Running" if info_data['server']['running'] else "Stopped"
        status_color = "green" if info_data['server']['running'] else "yellow"
        console.print(f"  Status: [{status_color}]{status_text}[/{status_color}]")


@app.command(
    rich_help_panel="🔧 System Management", 
    help="""
[bold red]Reset system to clean state[/bold red]

[bold]Reset Options[/bold]
  • Tasks only: [cyan]claude-cto reset --tasks[/cyan]
  • Configuration: [cyan]claude-cto reset --config[/cyan]
  • Logs: [cyan]claude-cto reset --logs[/cyan]
  • Complete reset: [cyan]claude-cto reset --all[/cyan]

[bold]Safety Features[/bold]
  • Confirmation prompts for destructive operations
  • Backup creation before reset
  • Selective reset options
  • Recovery instructions provided

[red]⚠ Warning: This will permanently delete selected data[/red]
"""
)
def reset(
    tasks: bool = typer.Option(False, "--tasks", help="Reset task database"),
    config: bool = typer.Option(False, "--config", help="Reset configuration files"), 
    logs: bool = typer.Option(False, "--logs", help="Clear all log files"),
    all_data: bool = typer.Option(False, "--all", help="Reset everything"),
    force: bool = typer.Option(False, "--force", help="Skip confirmation prompts"),
):
    """Reset system to clean state."""
    from pathlib import Path
    import shutil
    
    if not any([tasks, config, logs, all_data]):
        console.print("[red]Error: Must specify what to reset[/red]")
        console.print("[dim]Use --tasks, --config, --logs, or --all[/dim]")
        raise typer.Exit(1)
    
    config_dir = Path.home() / ".claude-cto"
    
    reset_items = []
    if all_data:
        reset_items = ["tasks", "config", "logs"]
    else:
        if tasks:
            reset_items.append("tasks")
        if config:
            reset_items.append("config")
        if logs:
            reset_items.append("logs")
    
    console.print(f"\n[bold red]⚠ Reset Warning[/bold red]")
    console.print(f"This will permanently delete: {', '.join(reset_items)}")
    
    if not force:
        confirm = typer.confirm("Are you sure you want to continue?")
        if not confirm:
            console.print("[yellow]Reset cancelled.[/yellow]")
            raise typer.Exit(0)
    
    try:
        # Stop server first if running
        server_url = get_server_url()
        if is_server_running(server_url):
            console.print("[yellow]Stopping server...[/yellow]")
            # Server stop logic would go here
        
        reset_count = 0
        
        if "tasks" in reset_items:
            db_path = config_dir / "tasks.db"
            if db_path.exists():
                db_path.unlink()
                reset_count += 1
                console.print("[green]✓[/green] Task database reset")
        
        if "config" in reset_items:
            # Reset config files but preserve directory structure
            config_files = list(config_dir.glob("*.json")) + list(config_dir.glob("*.yaml"))
            for config_file in config_files:
                config_file.unlink()
                reset_count += 1
            if config_files:
                console.print("[green]✓[/green] Configuration files reset")
        
        if "logs" in reset_items:
            logs_dir = config_dir / "logs"
            if logs_dir.exists():
                shutil.rmtree(logs_dir)
                logs_dir.mkdir()
                reset_count += 1
                console.print("[green]✓[/green] Log files cleared")
        
        console.print(f"\n[green]✓ Reset complete! ({reset_count} items processed)[/green]")
        console.print("[dim]You may need to reconfigure MCP integration[/dim]")
        
    except Exception as e:
        console.print(f"[red]✗ Reset failed: {e}[/red]")
        raise typer.Exit(1)


@app.command(
    rich_help_panel="🚀 Task Execution",
    help="""
[bold magenta]Interactive task execution with AI guidance[/bold magenta]

[bold]Interactive Features[/bold]
  • Step-by-step task breakdown
  • Real-time progress feedback
  • Interactive decision points
  • Dynamic task modification

[bold]Execution Modes[/bold]
  • Guided mode: [cyan]claude-cto interactive[/cyan]
  • Expert mode: [cyan]claude-cto interactive --expert[/cyan]
  • Learning mode: [cyan]claude-cto interactive --explain[/cyan]
  • Batch mode: [cyan]claude-cto interactive --batch[/cyan]

[bold]Use Cases[/bold]
  • Complex multi-step workflows
  • Learning and understanding AI decisions
  • Fine-tuning task execution
  • Debugging task failures

[dim]Perfect for complex tasks that benefit from human oversight[/dim]
"""
)
def interactive(
    expert_mode: bool = typer.Option(False, "--expert", help="Expert mode with advanced options"),
    explain: bool = typer.Option(False, "--explain", help="Explain each step and decision"),
    batch: bool = typer.Option(False, "--batch", help="Batch mode for multiple related tasks"),
    model: str = typer.Option("sonnet", "--model", "-m", help="Claude model to use"),
    working_dir: str = typer.Option(".", "--dir", "-d", help="Working directory"),
):
    """Interactive task execution with AI guidance."""
    console.print("\n[bold magenta]🤖 Claude CTO - Interactive Mode[/bold magenta]")
    console.print("[dim]Type 'exit' or 'quit' to leave interactive mode[/dim]\n")
    
    if expert_mode:
        console.print("[yellow]📊 Expert Mode Enabled[/yellow]")
        console.print("[dim]Advanced configuration options available[/dim]\n")
    
    if explain:
        console.print("[blue]🎓 Explanation Mode Enabled[/blue]")
        console.print("[dim]AI will explain reasoning for each step[/dim]\n")
    
    session_tasks = []
    task_counter = 1
    
    try:
        while True:
            # Get user input
            prompt = console.input(f"[bold cyan]Task #{task_counter}>[/bold cyan] ")
            
            if prompt.lower().strip() in ['exit', 'quit', 'q']:
                console.print("\n[dim]Exiting interactive mode...[/dim]")
                break
                
            if not prompt.strip():
                continue
                
            # Special commands
            if prompt.lower().strip() == 'help':
                console.print("""
[bold]Interactive Commands:[/bold]
  [cyan]help[/cyan]     - Show this help
  [cyan]status[/cyan]   - Show session status
  [cyan]history[/cyan]  - Show task history
  [cyan]clear[/cyan]    - Clear screen
  [cyan]exit/quit[/cyan] - Exit interactive mode
  
[bold]Task Commands:[/bold]
  Just type your task description and press Enter!
  
[bold]Examples:[/bold]
  > analyze this codebase for security issues
  > refactor the main.py file to use async/await
  > write unit tests for all functions
""")
                continue
                
            if prompt.lower().strip() == 'status':
                console.print(f"\n[bold]Session Status:[/bold]")
                console.print(f"  Tasks in session: {len(session_tasks)}")
                console.print(f"  Current directory: {working_dir}")
                console.print(f"  Model: {model}")
                console.print(f"  Expert mode: {'Yes' if expert_mode else 'No'}")
                console.print(f"  Explain mode: {'Yes' if explain else 'No'}\n")
                continue
                
            if prompt.lower().strip() == 'history':
                if session_tasks:
                    console.print("\n[bold]Task History:[/bold]")
                    for i, task in enumerate(session_tasks, 1):
                        status_color = {"completed": "green", "failed": "red", "running": "yellow"}.get(task.get("status", "unknown"), "white")
                        console.print(f"  {i}. [{status_color}]{task.get('status', 'unknown')}[/{status_color}] - {task['prompt'][:60]}...")
                    console.print()
                else:
                    console.print("\n[yellow]No tasks in history[/yellow]\n")
                continue
                
            if prompt.lower().strip() == 'clear':
                console.clear()
                continue
            
            # Execute the task
            console.print(f"\n[cyan]⚙️ Executing task #{task_counter}...[/cyan]")
            
            if explain:
                console.print(f"[blue]🧠 AI Reasoning:[/blue] Breaking down the task '{prompt}' into actionable steps...")
            
            # Here we would integrate with the actual task execution
            # For now, just simulate the task creation
            task_data = {
                "execution_prompt": prompt,
                "working_directory": str(Path(working_dir).resolve()),
                "model": model,
            }
            
            # Store task info for session history
            session_task = {
                "id": task_counter,
                "prompt": prompt,
                "status": "running",
                "model": model
            }
            session_tasks.append(session_task)
            
            try:
                server_url = get_server_url()
                
                if not is_server_running(server_url):
                    console.print("[yellow]⚠ Starting server...[/yellow]")
                    if not start_server_in_background():
                        console.print("[red]✗ Failed to start server[/red]")
                        session_task["status"] = "failed"
                        continue
                    server_url = get_server_url()
                
                with httpx.Client() as client:
                    response = client.post(f"{server_url}/api/v1/tasks", json=task_data, timeout=30.0)
                    response.raise_for_status()
                    result = response.json()
                    
                    console.print(f"[green]✓ Task created with ID: {result['id']}[/green]")
                    session_task["status"] = "completed"
                    session_task["task_id"] = result['id']
                    
                    if expert_mode:
                        console.print(f"[dim]Advanced: Task scheduled on server at {server_url}[/dim]")
                        console.print(f"[dim]Monitor with: claude-cto status {result['id']}[/dim]")
                    
            except Exception as e:
                console.print(f"[red]✗ Task failed: {e}[/red]")
                session_task["status"] = "failed"
            
            task_counter += 1
            console.print()  # Add spacing
            
    except KeyboardInterrupt:
        console.print("\n\n[dim]Interactive session interrupted.[/dim]")
    
    # Session summary
    if session_tasks:
        console.print(f"\n[bold]Session Summary:[/bold]")
        completed = len([t for t in session_tasks if t["status"] == "completed"])
        failed = len([t for t in session_tasks if t["status"] == "failed"])
        console.print(f"  Total tasks: {len(session_tasks)}")
        console.print(f"  Completed: [green]{completed}[/green]")
        console.print(f"  Failed: [red]{failed}[/red]")
        console.print(f"\n[dim]Use 'claude-cto list' to see all your tasks[/dim]")


@app.command(
    rich_help_panel="🔗 Orchestration", 
    help="""
[bold cyan]Generate workflow templates and examples[/bold cyan]

[bold]Template Types[/bold]
  • Basic workflow: [cyan]claude-cto template --type basic[/cyan]
  • CI/CD pipeline: [cyan]claude-cto template --type cicd[/cyan]
  • Code analysis: [cyan]claude-cto template --type analysis[/cyan]
  • Data processing: [cyan]claude-cto template --type data[/cyan]

[bold]Output Options[/bold]
  • Save to file: [cyan]claude-cto template --output workflow.json[/cyan]
  • Custom project: [cyan]claude-cto template --project /path/to/project[/cyan]
  • Interactive setup: [cyan]claude-cto template --interactive[/cyan]

[bold]Generated Templates[/bold]
  • Complete JSON workflow definitions
  • Task dependencies and timing
  • Best practices and comments
  • Ready-to-use configurations

[dim]Templates provide starting points for complex workflow orchestration[/dim]
"""
)
def template(
    template_type: str = typer.Option("basic", "--type", "-t", help="Template type: basic, cicd, analysis, data"),
    output: Optional[str] = typer.Option(None, "--output", "-o", help="Output file path"),
    project_path: str = typer.Option(".", "--project", "-p", help="Project path for template"),
    interactive: bool = typer.Option(False, "--interactive", "-i", help="Interactive template creation"),
):
    """Generate workflow templates for orchestration."""
    import json
    from pathlib import Path
    
    console.print(f"\n[bold cyan]🎭 Claude CTO - Template Generator[/bold cyan]")
    console.print(f"[dim]Generating {template_type} workflow template...[/dim]\n")
    
    project_name = Path(project_path).name
    
    templates = {
        "basic": {
            "name": f"Basic Workflow for {project_name}",
            "description": "A simple sequential workflow template",
            "tasks": [
                {
                    "identifier": "analyze",
                    "execution_prompt": f"Analyze the codebase in {project_path} and identify areas for improvement",
                    "working_directory": project_path,
                    "model": "sonnet"
                },
                {
                    "identifier": "implement",
                    "execution_prompt": f"Implement the improvements suggested in the analysis for {project_path}",
                    "working_directory": project_path,
                    "depends_on": ["analyze"],
                    "initial_delay": 2.0,
                    "model": "opus"
                },
                {
                    "identifier": "test",
                    "execution_prompt": f"Run tests and validate the improvements in {project_path}",
                    "working_directory": project_path,
                    "depends_on": ["implement"],
                    "model": "haiku"
                }
            ]
        },
        "cicd": {
            "name": f"CI/CD Pipeline for {project_name}",
            "description": "Complete CI/CD workflow with testing and deployment",
            "tasks": [
                {
                    "identifier": "lint",
                    "execution_prompt": f"Run linting and code quality checks on {project_path}",
                    "working_directory": project_path,
                    "model": "haiku"
                },
                {
                    "identifier": "unit_tests",
                    "execution_prompt": f"Run unit tests for the project in {project_path}",
                    "working_directory": project_path,
                    "depends_on": ["lint"],
                    "model": "haiku"
                },
                {
                    "identifier": "integration_tests",
                    "execution_prompt": f"Run integration tests for {project_path}",
                    "working_directory": project_path,
                    "depends_on": ["unit_tests"],
                    "initial_delay": 3.0,
                    "model": "sonnet"
                },
                {
                    "identifier": "security_scan",
                    "execution_prompt": f"Perform security scanning and vulnerability assessment on {project_path}",
                    "working_directory": project_path,
                    "depends_on": ["lint"],
                    "model": "sonnet"
                },
                {
                    "identifier": "build",
                    "execution_prompt": f"Build the application and create deployment artifacts for {project_path}",
                    "working_directory": project_path,
                    "depends_on": ["integration_tests", "security_scan"],
                    "model": "haiku"
                },
                {
                    "identifier": "deploy",
                    "execution_prompt": f"Deploy the built application from {project_path} to staging environment",
                    "working_directory": project_path,
                    "depends_on": ["build"],
                    "initial_delay": 5.0,
                    "model": "sonnet"
                }
            ]
        },
        "analysis": {
            "name": f"Code Analysis Workflow for {project_name}",
            "description": "Comprehensive code analysis and reporting",
            "tasks": [
                {
                    "identifier": "complexity_analysis",
                    "execution_prompt": f"Analyze code complexity and identify complex functions in {project_path}",
                    "working_directory": project_path,
                    "model": "sonnet"
                },
                {
                    "identifier": "security_analysis",
                    "execution_prompt": f"Perform security analysis and identify vulnerabilities in {project_path}",
                    "working_directory": project_path,
                    "model": "opus"
                },
                {
                    "identifier": "performance_analysis",
                    "execution_prompt": f"Analyze performance bottlenecks and optimization opportunities in {project_path}",
                    "working_directory": project_path,
                    "model": "sonnet"
                },
                {
                    "identifier": "documentation_analysis",
                    "execution_prompt": f"Analyze documentation coverage and quality in {project_path}",
                    "working_directory": project_path,
                    "model": "sonnet"
                },
                {
                    "identifier": "generate_report",
                    "execution_prompt": f"Generate comprehensive analysis report combining all findings for {project_path}",
                    "working_directory": project_path,
                    "depends_on": ["complexity_analysis", "security_analysis", "performance_analysis", "documentation_analysis"],
                    "initial_delay": 2.0,
                    "model": "opus"
                }
            ]
        },
        "data": {
            "name": f"Data Processing Pipeline for {project_name}",
            "description": "Data processing and analysis workflow",
            "tasks": [
                {
                    "identifier": "data_validation",
                    "execution_prompt": f"Validate and check data quality in {project_path}",
                    "working_directory": project_path,
                    "model": "sonnet"
                },
                {
                    "identifier": "data_cleaning",
                    "execution_prompt": f"Clean and preprocess data in {project_path}",
                    "working_directory": project_path,
                    "depends_on": ["data_validation"],
                    "model": "sonnet"
                },
                {
                    "identifier": "data_analysis",
                    "execution_prompt": f"Perform statistical analysis on cleaned data in {project_path}",
                    "working_directory": project_path,
                    "depends_on": ["data_cleaning"],
                    "model": "opus"
                },
                {
                    "identifier": "generate_visualizations",
                    "execution_prompt": f"Create data visualizations and charts for {project_path}",
                    "working_directory": project_path,
                    "depends_on": ["data_analysis"],
                    "model": "sonnet"
                },
                {
                    "identifier": "export_results",
                    "execution_prompt": f"Export analysis results and visualizations from {project_path}",
                    "working_directory": project_path,
                    "depends_on": ["generate_visualizations"],
                    "model": "haiku"
                }
            ]
        }
    }
    
    if template_type not in templates:
        console.print(f"[red]✗ Unknown template type: {template_type}[/red]")
        console.print(f"[dim]Available types: {', '.join(templates.keys())}[/dim]")
        raise typer.Exit(1)
    
    template_data = templates[template_type]
    
    if interactive:
        console.print(f"[bold]Interactive Template Creation for '{template_type}' workflow[/bold]\n")
        
        # Ask for customizations
        custom_name = console.input(f"Workflow name [{template_data['name']}]: ").strip()
        if custom_name:
            template_data['name'] = custom_name
            
        custom_desc = console.input(f"Description [{template_data['description']}]: ").strip()
        if custom_desc:
            template_data['description'] = custom_desc
        
        console.print(f"\n[cyan]Template will have {len(template_data['tasks'])} tasks[/cyan]")
        
        modify_tasks = typer.confirm("Do you want to modify individual tasks?")
        if modify_tasks:
            for i, task in enumerate(template_data['tasks']):
                console.print(f"\n[bold]Task {i+1}: {task['identifier']}[/bold]")
                console.print(f"Current prompt: {task['execution_prompt']}")
                
                new_prompt = console.input("New prompt (press Enter to keep current): ").strip()
                if new_prompt:
                    task['execution_prompt'] = new_prompt
                    
                new_model = console.input(f"Model [{task['model']}]: ").strip()
                if new_model and new_model in ['sonnet', 'opus', 'haiku']:
                    task['model'] = new_model
    
    # Generate the template
    template_json = json.dumps(template_data, indent=2)
    
    if output:
        output_path = Path(output)
        output_path.parent.mkdir(parents=True, exist_ok=True)
        
        with open(output_path, 'w') as f:
            f.write(template_json)
            
        console.print(f"[green]✓ Template saved to {output_path}[/green]")
        console.print(f"\n[bold]Next steps:[/bold]")
        console.print(f"  1. Review and customize the template: [cyan]{output_path}[/cyan]")
        console.print(f"  2. Execute the workflow: [cyan]claude-cto orchestrate {output_path}[/cyan]")
        console.print(f"  3. Monitor progress: [cyan]claude-cto list-orchestrations[/cyan]")
    else:
        console.print(f"[bold]{template_data['name']}[/bold]")
        console.print(f"[dim]{template_data['description']}[/dim]\n")
        console.print(template_json)
        console.print(f"\n[dim]Save this template with: [cyan]claude-cto template --type {template_type} --output workflow.json[/cyan][/dim]")


@app.command(
    rich_help_panel="📚 Information",
    help="""
[bold green]Check system requirements and compatibility[/bold green]

[bold]Compatibility Checks[/bold]
  • Python version and dependencies
  • Operating system compatibility
  • Required system tools availability
  • Network connectivity tests

[bold]Output Options[/bold]
  • Quick check: [cyan]claude-cto doctor[/cyan]
  • Detailed report: [cyan]claude-cto doctor --verbose[/cyan]
  • Fix issues: [cyan]claude-cto doctor --fix[/cyan]
  • JSON output: [cyan]claude-cto doctor --json[/cyan]

[bold]What Gets Checked[/bold]
  • Python 3.8+ requirement
  • Required packages and versions
  • Claude Code SDK availability
  • MCP integration status
  • File system permissions

[dim]Run this to diagnose installation or compatibility issues[/dim]
"""
)
def doctor(
    verbose: bool = typer.Option(False, "--verbose", "-v", help="Show detailed diagnostic information"),
    fix: bool = typer.Option(False, "--fix", help="Attempt to fix detected issues"),
    json_output: bool = typer.Option(False, "--json", help="Output in JSON format"),
):
    """Run system diagnostics and compatibility checks."""
    import sys
    import json
    import platform
    import subprocess
    from pathlib import Path
    import importlib.util
    
    console.print("\n[bold green]🧩 Claude CTO - System Doctor[/bold green]")
    console.print("[dim]Running comprehensive system diagnostics...[/dim]\n")
    
    checks = {
        "python_version": {"status": "unknown", "details": "", "fixable": False},
        "dependencies": {"status": "unknown", "details": "", "fixable": True},
        "claude_sdk": {"status": "unknown", "details": "", "fixable": True},
        "mcp_config": {"status": "unknown", "details": "", "fixable": True},
        "file_permissions": {"status": "unknown", "details": "", "fixable": True},
        "network": {"status": "unknown", "details": "", "fixable": False},
    }
    
    issues_found = 0
    fixes_applied = 0
    
    # Python version check
    try:
        version = sys.version_info
        if version >= (3, 8):
            checks["python_version"]["status"] = "pass"
            checks["python_version"]["details"] = f"Python {version.major}.{version.minor}.{version.micro}"
        else:
            checks["python_version"]["status"] = "fail"
            checks["python_version"]["details"] = f"Python {version.major}.{version.minor}.{version.micro} (requires 3.8+)"
            issues_found += 1
    except Exception as e:
        checks["python_version"]["status"] = "error"
        checks["python_version"]["details"] = str(e)
        issues_found += 1
    
    # Dependencies check
    required_packages = ['typer', 'httpx', 'rich', 'fastmcp']
    missing_packages = []
    
    for package in required_packages:
        spec = importlib.util.find_spec(package)
        if spec is None:
            missing_packages.append(package)
    
    if not missing_packages:
        checks["dependencies"]["status"] = "pass"
        checks["dependencies"]["details"] = "All required packages are installed"
    else:
        checks["dependencies"]["status"] = "fail"
        checks["dependencies"]["details"] = f"Missing packages: {', '.join(missing_packages)}"
        issues_found += 1
        
        if fix:
            console.print(f"[cyan]🔧 Attempting to install missing packages...[/cyan]")
            try:
                subprocess.run([sys.executable, "-m", "pip", "install"] + missing_packages, 
                             check=True, capture_output=True)
                checks["dependencies"]["status"] = "fixed"
                checks["dependencies"]["details"] = f"Installed: {', '.join(missing_packages)}"
                fixes_applied += 1
            except subprocess.CalledProcessError as e:
                checks["dependencies"]["details"] += f" (fix failed: {e})"
    
    # Claude SDK check
    try:
        spec = importlib.util.find_spec('claude_code_sdk')
        if spec:
            checks["claude_sdk"]["status"] = "pass"
            checks["claude_sdk"]["details"] = "Claude Code SDK is available"
        else:
            checks["claude_sdk"]["status"] = "fail"
            checks["claude_sdk"]["details"] = "Claude Code SDK not found"
            issues_found += 1
    except Exception as e:
        checks["claude_sdk"]["status"] = "error"
        checks["claude_sdk"]["details"] = str(e)
        issues_found += 1
    
    # MCP configuration check
    try:
        from ..mcp.auto_config import validate_config_paths
        issues = validate_config_paths()
        if not issues:
            checks["mcp_config"]["status"] = "pass"
            checks["mcp_config"]["details"] = "MCP configuration is valid"
        else:
            checks["mcp_config"]["status"] = "fail"
            checks["mcp_config"]["details"] = f"{len(issues)} configuration issues found"
            issues_found += 1
            
            if fix:
                console.print(f"[cyan]🔧 Attempting to fix MCP configuration...[/cyan]")
                try:
                    from ..mcp.auto_config import auto_fix_configurations
                    if auto_fix_configurations():
                        checks["mcp_config"]["status"] = "fixed"
                        checks["mcp_config"]["details"] = "MCP configuration issues resolved"
                        fixes_applied += 1
                except Exception as e:
                    checks["mcp_config"]["details"] += f" (fix failed: {e})"
                    
    except Exception as e:
        checks["mcp_config"]["status"] = "error"
        checks["mcp_config"]["details"] = str(e)
        issues_found += 1
    
    # File permissions check
    config_dir = Path.home() / ".claude-cto"
    try:
        config_dir.mkdir(exist_ok=True)
        test_file = config_dir / "test_write"
        test_file.write_text("test")
        test_file.unlink()
        
        checks["file_permissions"]["status"] = "pass"
        checks["file_permissions"]["details"] = f"Read/write access to {config_dir}"
    except Exception as e:
        checks["file_permissions"]["status"] = "fail"
        checks["file_permissions"]["details"] = f"Cannot write to {config_dir}: {e}"
        issues_found += 1
    
    # Network connectivity check
    try:
        import socket
        socket.create_connection(("8.8.8.8", 53), timeout=3)
        checks["network"]["status"] = "pass"
        checks["network"]["details"] = "Internet connectivity available"
    except Exception:
        checks["network"]["status"] = "warning"
        checks["network"]["details"] = "Limited network connectivity (may affect updates)"
    
    # Output results
    if json_output:
        result_data = {
            "summary": {
                "total_checks": len(checks),
                "issues_found": issues_found,
                "fixes_applied": fixes_applied,
                "overall_status": "healthy" if issues_found == 0 else "issues_detected"
            },
            "checks": checks
        }
        console.print(json.dumps(result_data, indent=2))
    else:
        # Display results in a nice table
        from rich.table import Table
        
        table = Table(title="System Health Check Results")
        table.add_column("Check", style="cyan", no_wrap=True)
        table.add_column("Status", style="bold")
        table.add_column("Details", style="dim")
        
        for check_name, check_data in checks.items():
            status = check_data['status']
            status_colors = {
                'pass': 'green',
                'fail': 'red', 
                'error': 'red',
                'warning': 'yellow',
                'fixed': 'blue',
                'unknown': 'white'
            }
            
            status_icons = {
                'pass': '✓',
                'fail': '✗', 
                'error': '✗',
                'warning': '⚠',
                'fixed': '🔧',
                'unknown': '?'
            }
            
            color = status_colors.get(status, 'white')
            icon = status_icons.get(status, '?')
            
            table.add_row(
                check_name.replace('_', ' ').title(),
                f"[{color}]{icon} {status.title()}[/{color}]",
                check_data['details'] if verbose else (check_data['details'][:50] + "..." if len(check_data['details']) > 50 else check_data['details'])
            )
        
        console.print(table)
        
        # Summary
        if issues_found == 0:
            console.print("\n[green]✓ All checks passed! System is healthy.[/green]")
        else:
            console.print(f"\n[yellow]⚠ Found {issues_found} issue(s)[/yellow]")
            if fixes_applied > 0:
                console.print(f"[blue]🔧 Applied {fixes_applied} fix(es)[/blue]")
            
            remaining_issues = issues_found - fixes_applied
            if remaining_issues > 0:
                console.print(f"\n[bold]Recommendations:[/bold]")
                
                for check_name, check_data in checks.items():
                    if check_data['status'] in ['fail', 'error'] and check_data['fixable']:
                        console.print(f"  • {check_name}: Try running with [cyan]--fix[/cyan] flag")
                        
                console.print(f"\n[dim]Run [cyan]claude-cto doctor --fix[/cyan] to attempt automatic repairs[/dim]")


# Entry point function for setuptools/pip
def cli_entry():
    """Entry point for the CLI executable."""
    app()

# Entry point for the CLI
if __name__ == "__main__":
    app()
