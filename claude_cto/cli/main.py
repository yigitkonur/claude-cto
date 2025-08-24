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
    invoke_without_command=True,  # Allow callback to run without subcommand
    epilog="[dim]For detailed help on any command: claude-cto [COMMAND] --help[/dim]",
)

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


@app.callback()
def main(ctx: typer.Context):
    """
    Show help when no command is provided.
    """
    if ctx.invoked_subcommand is None:
        # No subcommand was invoked, show help
        print(ctx.get_help())
        raise typer.Exit()


def is_server_running(server_url: str) -> bool:
    """Check if the server is running by making a health check request."""
    try:
        with httpx.Client() as client:
            response = client.get(f"{server_url}/health", timeout=1.0)
            return response.status_code == 200
    except (httpx.ConnectError, httpx.TimeoutException):
        return False


def start_server_in_background() -> bool:
    """
    Start the server in the background automatically.
    Returns True if successfully started, False otherwise.
    """
    import socket
    import time

    console.print("[yellow]⚠️  Server not running. Starting Claude CTO server...[/yellow]")

    # Find available port
    def is_port_available(host: str, port: int) -> bool:
        try:
            with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
                s.bind((host, port))
                return True
        except OSError:
            return False

    host = "0.0.0.0"
    port = 8000

    # Find available port
    for attempt in range(10):
        if is_port_available(host, port):
            break
        port += 1
    else:
        return False

    # Start server
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
        process = subprocess.Popen(
            cmd,
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
            start_new_session=True,
        )

        # Wait for server to start
        time.sleep(2)

        # Check if process is still running
        if process.poll() is None:
            console.print(f"[green]✓ Server started on port {port} (PID: {process.pid})[/green]")

            # Update environment variable for this session if using non-default port
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
    Submit a new task to Claude CTO.

    Prompt can be provided as:
    - Command line argument
    - File path (if argument is a readable file)
    - Piped from stdin
    """
    # Determine prompt source
    execution_prompt = None

    # Check if data is being piped from stdin
    if not sys.stdin.isatty():
        execution_prompt = sys.stdin.read().strip()
    elif prompt:
        # Check if it's a file path
        prompt_path = Path(prompt)
        if prompt_path.exists() and prompt_path.is_file():
            with open(prompt_path, "r") as f:
                execution_prompt = f.read().strip()
        else:
            # Treat as raw prompt string
            execution_prompt = prompt
    else:
        console.print("[red]Error: No prompt provided[/red]")
        raise typer.Exit(1)

    # Prepare request data
    task_data = {
        "execution_prompt": execution_prompt,
        "working_directory": str(Path(working_dir).resolve()),
    }
    if system_prompt:
        task_data["system_prompt"] = system_prompt

    # Validate and add model
    model_lower = model.lower()
    if model_lower not in ["sonnet", "opus", "haiku"]:
        console.print(f"[red]❌ Invalid model: {model}. Must be one of: sonnet, opus, haiku[/red]")
        raise typer.Exit(1)
    task_data["model"] = model_lower

    # Get server URL and check if server is running
    server_url = get_server_url()

    # Auto-start server if not running
    if not is_server_running(server_url):
        if not start_server_in_background():
            console.print("\n[red]❌ Could not start the server automatically.[/red]\n")
            console.print("[bold yellow]To fix this, try:[/bold yellow]")
            console.print("  1. Start the server manually:")
            console.print("     [bright_white]$ claude-cto server start[/bright_white]\n")
            console.print("  2. Check if port 8000-8010 are available:")
            console.print("     [bright_white]$ lsof -i :8000[/bright_white]\n")
            console.print("  3. Kill any existing servers:")
            console.print("     [bright_white]$ pkill -f claude_cto.server[/bright_white]\n")
            raise typer.Exit(1)

        # Update server_url if it changed
        server_url = get_server_url()

    # Submit task to server
    with httpx.Client() as client:
        try:
            response = client.post(f"{server_url}/api/v1/tasks", json=task_data, timeout=30.0)
            response.raise_for_status()
            result = response.json()

            # Display task info
            console.print(f"\n[green]✓[/green] Task created with ID: [bold cyan]{result['id']}[/bold cyan]")
            console.print(f"Status: [yellow]{result['status']}[/yellow]")

            if not watch:
                console.print(
                    f"\n[dim]💡 Tip: Check progress with:[/dim] [bright_white]claude-cto status {result['id']}[/bright_white]"
                )
                console.print(
                    '[dim]    Or watch live with:[/dim] [bright_white]claude-cto run "your task" --watch[/bright_white]'
                )

            # Watch if requested
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
            console.print("  2. Check if port 8000-8010 are available:")
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
    server_url = get_server_url()

    # Auto-start server if not running
    if not is_server_running(server_url):
        if not start_server_in_background():
            console.print("\n[red]❌ Could not start the server automatically.[/red]\n")
            console.print("[bold yellow]To fix this, try:[/bold yellow]")
            console.print("  1. Start the server manually:")
            console.print("     [bright_white]$ claude-cto server start[/bright_white]\n")
            console.print("  2. Check if port 8000-8010 are available:")
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
    Create and execute a task orchestration from a JSON file.

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
    # Load orchestration from file
    if not tasks_file.exists():
        console.print(f"[red]File not found: {tasks_file}[/red]")
        raise typer.Exit(1)

    try:
        with open(tasks_file) as f:
            orchestration_data = json.load(f)
    except json.JSONDecodeError as e:
        console.print(f"[red]Invalid JSON: {e}[/red]")
        raise typer.Exit(1)

    # Validate structure
    if "tasks" not in orchestration_data:
        console.print("[red]JSON must contain 'tasks' array[/red]")
        raise typer.Exit(1)

    # Use provided server URL or default
    url = server_url or get_server_url()

    # Auto-start server if needed
    if not is_server_running(url):
        start_server_in_background()
        time.sleep(2)  # Give server time to start

    # Create orchestration
    try:
        response = httpx.post(f"{url}/api/v1/orchestrations", json=orchestration_data, timeout=30.0)
        response.raise_for_status()
        result = response.json()

        orch_id = result["orchestration_id"]
        console.print(f"[green]✓ Orchestration created with ID: {orch_id}[/green]")

        # Display task graph
        console.print("\n[bold cyan]Task Dependency Graph:[/bold cyan]")
        for task in result["tasks"]:
            deps = task.get("depends_on", [])
            delay = task.get("initial_delay", 0)
            dep_str = f" <- {deps}" if deps else ""
            delay_str = f" (delay: {delay}s)" if delay else ""
            console.print(f"  • {task['identifier']} (#{task['task_id']}){dep_str}{delay_str}")

        # Wait for completion if requested
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

                    # Check status
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
        max_attempts = 10
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

    if reload:
        cmd.append("--reload")

    # Start server as background process
    try:
        process = subprocess.Popen(
            cmd,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            start_new_session=True,  # Detach from parent process group
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


# Entry point for the CLI
if __name__ == "__main__":
    app()
