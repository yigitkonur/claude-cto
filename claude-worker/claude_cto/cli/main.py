#!/usr/bin/env python3
from typing import Optional

import typer
import uvicorn
import httpx
import asyncio
import sys
import os

from claude_cto.cli.config import Settings
from claude_cto.server.main import app as server_app
from claude_cto.mcp.factory import start_mcp_server

# Create a Typer app for the CLI
app = typer.Typer(
    name="claude-cto",
    help="Claude CTO: An intelligent task management and execution platform.",
    no_args_is_help=True,
)

settings = Settings()

@app.command()
def server(
    host: str = typer.Option("127.0.0.1", help="Host to bind the server"),
    port: int = typer.Option(8000, help="Port to bind the server"),
    reload: bool = typer.Option(False, help="Enable auto-reload for development"),
    log_level: str = typer.Option("info", help="Logging level"),
):
    """
    Start the claude-cto server.
    
    This command launches the main REST API server for claude-cto.
    """
    uvicorn.run(
        "claude_cto.server.main:app",
        host=host,
        port=port,
        reload=reload,
        log_level=log_level,
    )

@app.command()
def mcp(
    host: str = typer.Option("127.0.0.1", help="Host to bind the MCP server"),
    port: int = typer.Option(8001, help="Port to bind the MCP server"),
):
    """
    Start the Machine Control Protocol (MCP) server.
    
    This command launches the MCP server for claude-cto.
    """
    start_mcp_server(host, port)

@app.command()
def auto_start():
    """
    Automatically start both the server and MCP in the background.
    
    This command ensures the claude-cto server and MCP are running.
    """
    import subprocess
    import sys
    import time

    server_process = subprocess.Popen(
        [sys.executable, "-m", "claude_cto.cli.main", "server"],
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
    )
    
    time.sleep(2)  # Give server time to start
    
    mcp_process = subprocess.Popen(
        [sys.executable, "-m", "claude_cto.cli.main", "mcp"],
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
    )
    
    print(f"Server PID: {server_process.pid}")
    print(f"MCP Server PID: {mcp_process.pid}")

@app.command()
def task(
    task_file: Optional[str] = typer.Argument(None, help="Path to task file"),
    prompt: Optional[str] = typer.Option(None, help="Task execution prompt"),
):
    """
    Execute a task using claude-cto.
    
    You can either provide a task file or an inline prompt.
    """
    async def run_task():
        async with httpx.AsyncClient() as client:
            try:
                # Placeholder for task submission logic
                # This would be replaced with actual API call to submit task
                response = await client.post(
                    f"{settings.server_url}/api/v1/tasks",
                    json={
                        "task_file": task_file,
                        "prompt": prompt,
                    }
                )
                response.raise_for_status()
                task_info = response.json()
                print(f"Task submitted: {task_info.get('task_id')}")
            except httpx.RequestError as e:
                print(f"Error submitting task: {e}")
                sys.exit(1)

    asyncio.run(run_task())

def main():
    """
    Main entry point for the claude-cto CLI.
    """
    app()

if __name__ == "__main__":
    main()