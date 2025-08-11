"""
SOLE RESPONSIBILITY: Defines all Typer CLI commands (e.g., run, status, logs), 
handles user input, and makes HTTP requests to the server's REST API.
"""

import sys
import os
import asyncio
import subprocess
import json
from pathlib import Path
from typing import Optional, Annotated
from datetime import datetime

import typer
import httpx
from rich.console import Console
from rich.table import Table
from rich.live import Live
from rich import print as rprint
from rich.panel import Panel
from rich.text import Text

from .config import get_server_url


# Initialize Typer app
app = typer.Typer(
    name="claude-worker",
    help="""
🤖 [bold cyan]Claude Worker[/bold cyan] - Run Claude Code SDK tasks in the background

Delegate long-running AI tasks to Claude without blocking your terminal.
Perfect for code refactoring, analysis, and automation tasks.

[bold yellow]Quick Start:[/bold yellow]
  $ claude-worker run "analyze this codebase and suggest improvements"
  $ claude-worker run "refactor all Python files to use type hints" --watch
  $ echo "review this code" | claude-worker run

[bold green]Examples:[/bold green]
  • Simple task:     claude-worker run "create a README.md file"
  • From file:       claude-worker run instructions.txt
  • With monitoring: claude-worker run "complex task" --watch
  • Check progress:  claude-worker status 1
  • View all tasks:  claude-worker list

[dim]The server starts automatically when needed. No setup required![/dim]
""",
    rich_markup_mode="rich",
    no_args_is_help=True,  # Show help when no args provided
    invoke_without_command=True,  # Allow callback to run without subcommand
    epilog="[dim]For detailed help on any command: claude-worker [COMMAND] --help[/dim]"
)

# Server management sub-app
server_app = typer.Typer(
    help="""[bold]Server management commands[/bold]
    
[dim]Note: The server starts automatically when you run tasks.
You only need these commands for manual control.[/dim]
""",
    rich_markup_mode="rich"
)
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
    
    console.print("[yellow]⚠️  Server not running. Starting Claude Worker server...[/yellow]")
    
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
        sys.executable, "-m", "uvicorn",
        "claude_worker.server.main:app",
        "--host", host,
        "--port", str(port)
    ]
    
    try:
        process = subprocess.Popen(
            cmd,
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
            start_new_session=True
        )
        
        # Wait for server to start
        time.sleep(2)
        
        # Check if process is still running
        if process.poll() is None:
            console.print(f"[green]✓ Server started on port {port} (PID: {process.pid})[/green]")
            
            # Update environment variable for this session if using non-default port
            if port != 8000:
                os.environ["CLAUDE_WORKER_SERVER_URL"] = f"http://localhost:{port}"
            
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
  $ claude-worker run "write a Python hello world script"
  
  [cyan]# From a file with instructions[/cyan]
  $ claude-worker run requirements.txt
  
  [cyan]# Watch the task progress live[/cyan]
  $ claude-worker run "refactor this codebase" --watch
  
  [cyan]# Pipe input from another command[/cyan]
  $ git diff | claude-worker run "review these changes"
  
  [cyan]# Specify working directory[/cyan]
  $ claude-worker run "organize files here" --dir /path/to/project
"""
)
def run(
    prompt: Annotated[Optional[str], typer.Argument(
        help="Task prompt or path to file with instructions",
        metavar="PROMPT"
    )] = None,
    working_dir: Annotated[str, typer.Option(
        "--dir", "-d",
        help="Working directory for the task",
        rich_help_panel="Task Options"
    )] = ".",
    system_prompt: Annotated[Optional[str], typer.Option(
        "--system", "-s",
        help="Custom system prompt for Claude",
        rich_help_panel="Task Options"
    )] = None,
    watch: Annotated[bool, typer.Option(
        "--watch", "-w",
        help="Watch task progress in real-time",
        rich_help_panel="Display Options"
    )] = False
):
    """
    Submit a new task to Claude Worker.
    
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
            with open(prompt_path, 'r') as f:
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
        "working_directory": str(Path(working_dir).resolve())
    }
    if system_prompt:
        task_data["system_prompt"] = system_prompt
    
    # Get server URL and check if server is running
    server_url = get_server_url()
    
    # Auto-start server if not running
    if not is_server_running(server_url):
        if not start_server_in_background():
            console.print("\n[red]❌ Could not start the server automatically.[/red]\n")
            console.print("[bold yellow]To fix this, try:[/bold yellow]")
            console.print("  1. Start the server manually:")
            console.print("     [bright_white]$ claude-worker server start[/bright_white]\n")
            console.print("  2. Check if port 8000-8010 are available:")
            console.print("     [bright_white]$ lsof -i :8000[/bright_white]\n")
            console.print("  3. Kill any existing servers:")
            console.print("     [bright_white]$ pkill -f claude_worker.server[/bright_white]\n")
            raise typer.Exit(1)
        
        # Update server_url if it changed
        server_url = get_server_url()
    
    # Submit task to server
    with httpx.Client() as client:
        try:
            response = client.post(
                f"{server_url}/api/v1/tasks",
                json=task_data,
                timeout=30.0
            )
            response.raise_for_status()
            result = response.json()
            
            # Display task info
            console.print(f"\n[green]✓[/green] Task created with ID: [bold cyan]{result['id']}[/bold cyan]")
            console.print(f"Status: [yellow]{result['status']}[/yellow]")
            
            if not watch:
                console.print(f"\n[dim]💡 Tip: Check progress with:[/dim] [bright_white]claude-worker status {result['id']}[/bright_white]")
                console.print(f"[dim]    Or watch live with:[/dim] [bright_white]claude-worker run \"your task\" --watch[/bright_white]")
            
            # Watch if requested
            if watch:
                asyncio.run(watch_status(result['id']))
            
        except httpx.HTTPError as e:
            console.print(f"[red]Error submitting task: {e}[/red]")
            raise typer.Exit(1)


@app.command(
    help="""[bold yellow]Check task status[/bold yellow] 📊
    
View detailed information about a specific task.

[bold]Example:[/bold]
  $ claude-worker status 1
  
Shows the task's current status, progress, and any errors.
"""
)
def status(
    task_id: Annotated[int, typer.Argument(
        help="The ID of the task to check",
        metavar="TASK_ID"
    )]
):
    """Get the status of a specific task."""
    server_url = get_server_url()
    
    # Auto-start server if not running
    if not is_server_running(server_url):
        if not start_server_in_background():
            console.print("\n[red]❌ Could not start the server automatically.[/red]\n")
            console.print("[bold yellow]To fix this, try:[/bold yellow]")
            console.print("  1. Start the server manually:")
            console.print("     [bright_white]$ claude-worker server start[/bright_white]\n")
            console.print("  2. Check if port 8000-8010 are available:")
            console.print("     [bright_white]$ lsof -i :8000[/bright_white]\n")
            console.print("  3. Kill any existing servers:")
            console.print("     [bright_white]$ pkill -f claude_worker.server[/bright_white]\n")
            raise typer.Exit(1)
        
        # Update server_url if it changed
        server_url = get_server_url()
    
    with httpx.Client() as client:
        try:
            response = client.get(
                f"{server_url}/api/v1/tasks/{task_id}",
                timeout=10.0
            )
            response.raise_for_status()
            task = response.json()
            
            # Create status table
            table = Table(title=f"Task {task_id} Status")
            table.add_column("Field", style="cyan")
            table.add_column("Value", style="green")
            
            table.add_row("Status", task['status'])
            table.add_row("Created", task['created_at'])
            
            if task.get('started_at'):
                table.add_row("Started", task['started_at'])
            
            if task.get('ended_at'):
                table.add_row("Ended", task['ended_at'])
            
            if task.get('last_action_cache'):
                table.add_row("Last Action", task['last_action_cache'])
            
            if task.get('final_summary'):
                table.add_row("Summary", task['final_summary'])
            
            if task.get('error_message'):
                table.add_row("Error", task['error_message'])
            
            console.print(table)
            
        except httpx.HTTPError as e:
            console.print(f"[red]Error fetching task status: {e}[/red]")
            raise typer.Exit(1)


@app.command(
    help="[bold]Show this help message[/bold] 📚"
)
def help(ctx: typer.Context):
    """Show help information."""
    console.print(ctx.parent.get_help())


@app.command(
    name="list",
    help="""[bold blue]View all tasks[/bold blue] 📋
    
Display a table of all submitted tasks with their status.

[bold]Example:[/bold]
  $ claude-worker list
  
Shows task IDs, status, creation time, and last actions.
"""
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
            console.print("     [bright_white]$ claude-worker server start[/bright_white]\n")
            console.print("  2. Check if port 8000-8010 are available:")
            console.print("     [bright_white]$ lsof -i :8000[/bright_white]\n")
            console.print("  3. Kill any existing servers:")
            console.print("     [bright_white]$ pkill -f claude_worker.server[/bright_white]\n")
            raise typer.Exit(1)
        
        # Update server_url if it changed
        server_url = get_server_url()
    
    with httpx.Client() as client:
        try:
            response = client.get(
                f"{server_url}/api/v1/tasks",
                timeout=10.0
            )
            response.raise_for_status()
            tasks = response.json()
            
            if not tasks:
                console.print("\n[yellow]📭 No tasks found yet![/yellow]\n")
                console.print("[bold]Get started with:[/bold]")
                console.print('  $ claude-worker run "your first task"\n')
                console.print("[dim]Examples:[/dim]")
                console.print('  • claude-worker run "create a Python script that sorts files by date"')
                console.print('  • claude-worker run "analyze this codebase and find bugs"')
                console.print('  • claude-worker run "write unit tests for all functions"\n')
                return
            
            # Create tasks table
            table = Table(title="All Tasks")
            table.add_column("ID", style="cyan")
            table.add_column("Status", style="yellow")
            table.add_column("Created", style="green")
            table.add_column("Last Action", style="white")
            
            for task in tasks:
                last_action = task.get('last_action_cache', '-')
                table.add_row(
                    str(task['id']),
                    task['status'],
                    task['created_at'][:19],  # Truncate to remove microseconds
                    last_action[:50] if last_action else '-'  # Truncate long actions
                )
            
            console.print(table)
            
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
                    response = await client.get(
                        f"{server_url}/api/v1/tasks/{task_id}",
                        timeout=10.0
                    )
                    response.raise_for_status()
                    task = response.json()
                    
                    # Create live status table
                    table = Table(title=f"Task {task_id} - Live Status")
                    table.add_column("Field", style="cyan")
                    table.add_column("Value", style="green")
                    
                    # Add status with color coding
                    status_color = "yellow"
                    if task['status'] == 'completed':
                        status_color = "green"
                    elif task['status'] == 'error':
                        status_color = "red"
                    
                    table.add_row("Status", f"[{status_color}]{task['status']}[/{status_color}]")
                    table.add_row("Created", task['created_at'])
                    
                    if task.get('started_at'):
                        table.add_row("Started", task['started_at'])
                    
                    if task.get('last_action_cache'):
                        table.add_row("Last Action", task['last_action_cache'])
                    
                    if task.get('final_summary'):
                        table.add_row("Summary", task['final_summary'])
                    
                    if task.get('error_message'):
                        table.add_row("Error", f"[red]{task['error_message']}[/red]")
                    
                    # Update display
                    live.update(table)
                    
                    # Check if task is done
                    if task['status'] in ['completed', 'error']:
                        break
                    
                    # Wait before next update
                    await asyncio.sleep(2)
                    
                except httpx.HTTPError as e:
                    console.print(f"[red]Error fetching task status: {e}[/red]")
                    break


@server_app.command(
    "start",
    help="""[bold green]Start the server manually[/bold green] 🚀
    
[dim]Note: The server starts automatically when you run tasks.
Use this command only if you need manual control.[/dim]

[bold]Examples:[/bold]
  [cyan]# Start with default settings[/cyan]
  $ claude-worker server start
  
  [cyan]# Use a specific port[/cyan]
  $ claude-worker server start --port 9000
  
  [cyan]# Enable auto-reload for development[/cyan]
  $ claude-worker server start --reload
"""
)
def server_start(
    host: Annotated[str, typer.Option("--host", "-h", help="Server host")] = "0.0.0.0",
    port: Annotated[int, typer.Option("--port", "-p", help="Server port")] = 8000,
    reload: Annotated[bool, typer.Option("--reload", "-r", help="Enable auto-reload")] = False,
    auto_port: Annotated[bool, typer.Option("--auto-port/--no-auto-port", help="Automatically find available port if default is in use")] = True
):
    """
    Start the Claude Worker server in the background.
    Uses subprocess.Popen to launch Uvicorn as a daemon.
    Automatically tries alternative ports if the specified port is occupied.
    """
    import socket
    
    console.print("\n[bold cyan]🚀 Claude Worker Server[/bold cyan]")
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
            console.print(f"[red]❌ Could not find available port in range {original_port}-{original_port + max_attempts - 1}[/red]")
            console.print("[dim]Tip: Try specifying a different port with --port or stop the process using port 8000[/dim]")
            raise typer.Exit(1)
    
    if port != original_port:
        console.print(f"[green]✓ Found available port: {port}[/green]")
    
    console.print(f"[yellow]Starting server on {host}:{port}...[/yellow]")
    
    # Build uvicorn command
    cmd = [
        sys.executable, "-m", "uvicorn",
        "claude_worker.server.main:app",
        "--host", host,
        "--port", str(port)
    ]
    
    if reload:
        cmd.append("--reload")
    
    # Start server as background process
    try:
        process = subprocess.Popen(
            cmd,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            start_new_session=True  # Detach from parent process group
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
            info_text.append("   Run long Claude Code SDK tasks without blocking your terminal.\n", style="dim")
            info_text.append("   Tasks run in isolated processes and persist through interruptions.\n\n", style="dim")
            
            info_text.append("📝 How to submit tasks:\n", style="bold cyan")
            info_text.append("   Quick task:     ", style="dim")
            info_text.append("claude-worker run \"Your prompt here\"\n", style="bright_white")
            info_text.append("   From file:      ", style="dim")
            info_text.append("claude-worker run prompt.txt\n", style="bright_white")
            info_text.append("   With watching:  ", style="dim")
            info_text.append("claude-worker run \"Your prompt\" --watch\n", style="bright_white")
            info_text.append("   From pipe:      ", style="dim")
            info_text.append("git diff | claude-worker run \"Review these changes\"\n\n", style="bright_white")
            
            info_text.append("🔍 Monitor your tasks:\n", style="bold green")
            info_text.append("   List all:       ", style="dim")
            info_text.append("claude-worker list\n", style="bright_white")
            info_text.append("   Check status:   ", style="dim")
            info_text.append("claude-worker status <task-id>\n\n", style="bright_white")
            
            info_text.append("💡 When to use:\n", style="bold magenta")
            info_text.append("   • Complex refactoring or code generation tasks\n", style="dim")
            info_text.append("   • Running multiple tasks in parallel\n", style="dim")
            info_text.append("   • Tasks that might take 5+ minutes\n", style="dim")
            info_text.append("   • When you need to preserve work through interruptions\n", style="dim")
            
            console.print(Panel(
                info_text,
                title="[bold]🚀 Claude Worker Ready![/bold]",
                border_style="green",
                padding=(1, 2)
            ))
            
            console.print(f"\n[dim]To stop server: kill {process.pid} or Ctrl+C in the terminal[/dim]")
            console.print(f"[dim]Server logs: Check your terminal or ~/.claude-worker/logs/[/dim]")
            
            # If using a non-default port, suggest setting environment variable
            if port != 8000:
                console.print(f"\n[yellow]⚠️  Note: Server running on non-default port {port}[/yellow]")
                console.print(f"[dim]Set CLAUDE_WORKER_SERVER_URL=http://localhost:{port} to use this server with the CLI[/dim]")
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
    
Verify if the Claude Worker server is running and healthy.

[bold]Example:[/bold]
  $ claude-worker server health
"""
)
def server_health():
    """Check if the server is healthy."""
    server_url = get_server_url()
    
    with httpx.Client() as client:
        try:
            response = client.get(
                f"{server_url}/health",
                timeout=5.0
            )
            response.raise_for_status()
            data = response.json()
            
            console.print(f"[green]✓[/green] Server is {data['status']}")
            console.print(f"Service: {data['service']}")
            
        except httpx.HTTPError:
            console.print(f"[red]✗[/red] Server is not responding at {server_url}")
            raise typer.Exit(1)


# Entry point for the CLI
if __name__ == "__main__":
    app()