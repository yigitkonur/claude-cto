"""
SOLE RESPONSIBILITY: Defines all Typer CLI commands (e.g., run, status, logs), 
handles user input, and makes HTTP requests to the server's REST API.
"""

import sys
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

from .config import get_server_url


# Initialize Typer app
app = typer.Typer(
    name="claude-worker",
    help="Fire-and-forget task execution for Claude Code SDK",
    rich_markup_mode="rich"
)

# Server management sub-app
server_app = typer.Typer(help="Server management commands")
app.add_typer(server_app, name="server")

# Console for rich output
console = Console()


@app.command()
def run(
    prompt: Annotated[Optional[str], typer.Argument()] = None,
    working_dir: Annotated[str, typer.Option("--dir", "-d", help="Working directory")] = ".",
    system_prompt: Annotated[Optional[str], typer.Option("--system", "-s", help="System prompt")] = None,
    watch: Annotated[bool, typer.Option("--watch", "-w", help="Watch task status")] = False
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
    
    # Submit task to server
    server_url = get_server_url()
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
            console.print(f"[green]✓[/green] Task created with ID: [bold]{result['id']}[/bold]")
            console.print(f"Status: {result['status']}")
            
            # Watch if requested
            if watch:
                asyncio.run(watch_status(result['id']))
            
        except httpx.HTTPError as e:
            console.print(f"[red]Error submitting task: {e}[/red]")
            raise typer.Exit(1)


@app.command()
def status(
    task_id: Annotated[int, typer.Argument(help="Task ID to check")]
):
    """Get the status of a specific task."""
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


@app.command()
def list():
    """List all tasks."""
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
                console.print("No tasks found.")
                return
            
            # Create tasks table
            table = Table(title="All Tasks")
            table.add_column("ID", style="cyan")
            table.add_column("Status", style="yellow")
            table.add_column("Created", style="green")
            table.add_column("Last Action", style="white")
            
            for task in tasks:
                table.add_row(
                    str(task['id']),
                    task['status'],
                    task['created_at'][:19],  # Truncate to remove microseconds
                    task.get('last_action_cache', '-')[:50]  # Truncate long actions
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


@server_app.command("start")
def server_start(
    host: Annotated[str, typer.Option("--host", "-h", help="Server host")] = "0.0.0.0",
    port: Annotated[int, typer.Option("--port", "-p", help="Server port")] = 8000,
    reload: Annotated[bool, typer.Option("--reload", "-r", help="Enable auto-reload")] = False
):
    """
    Start the Claude Worker server in the background.
    Uses subprocess.Popen to launch Uvicorn as a daemon.
    """
    console.print(f"[green]Starting Claude Worker server on {host}:{port}...[/green]")
    
    # Build uvicorn command
    cmd = [
        sys.executable, "-m", "uvicorn",
        "src.server.main:app",
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
            console.print(f"[green]✓[/green] Server started successfully (PID: {process.pid})")
            console.print(f"Server URL: http://{host}:{port}")
            console.print("\nTo stop the server, use your system's process manager or kill the PID.")
        else:
            stderr = process.stderr.read().decode() if process.stderr else "Unknown error"
            console.print(f"[red]Failed to start server: {stderr}[/red]")
            raise typer.Exit(1)
            
    except Exception as e:
        console.print(f"[red]Error starting server: {e}[/red]")
        raise typer.Exit(1)


@server_app.command("health")
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