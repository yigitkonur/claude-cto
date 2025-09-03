"""
SOLE RESPONSIBILITY: Isolated task execution using subprocess for process independence.
Tasks run in separate process groups and survive server crashes.
"""

import os
import sys
import subprocess
import asyncio
import json
from pathlib import Path
from typing import Optional
import logging

logger = logging.getLogger(__name__)


class IsolatedTaskRunner:
    """
    Runs tasks in isolated subprocess that survives server crashes.
    Uses subprocess with new session to decouple from parent process lifecycle.
    """
    
    @staticmethod
    def create_runner_script(task_id: int) -> str:
        """
        Create a Python script that runs a task independently.
        This script will be executed in a subprocess that survives server restarts.
        """
        runner_script = f"""
import sys
import os
import asyncio
import logging

# Add parent directory to path to import claude_cto modules
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from claude_cto.server.executor import TaskExecutor

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)

async def main():
    task_id = {task_id}
    executor = TaskExecutor(task_id)
    await executor.run()

if __name__ == "__main__":
    asyncio.run(main())
"""
        return runner_script
    
    @staticmethod
    async def run_task_isolated(task_id: int) -> None:
        """
        Run a task in an isolated subprocess that survives server crashes.
        
        Key features:
        - Runs in new session (setsid) to prevent signal propagation
        - Detached from parent process group
        - Survives if parent (server) process dies
        - Logs output to task-specific file
        """
        try:
            # Get application directory for script storage
            app_dir = Path.home() / ".claude-cto"
            runner_dir = app_dir / "runners"
            runner_dir.mkdir(exist_ok=True)
            
            # Create runner script file
            script_path = runner_dir / f"task_{task_id}_runner.py"
            script_content = IsolatedTaskRunner.create_runner_script(task_id)
            script_path.write_text(script_content)
            
            # Create log file for subprocess output
            log_dir = app_dir / "logs" / "runners"
            log_dir.mkdir(exist_ok=True)
            log_file = log_dir / f"task_{task_id}_subprocess.log"
            
            logger.info(f"Starting isolated task {task_id} with script {script_path}")
            
            # Start subprocess with proper isolation
            with open(log_file, "w") as log_handle:
                process = subprocess.Popen(
                    [sys.executable, str(script_path)],
                    stdout=log_handle,
                    stderr=subprocess.STDOUT,
                    # Critical: start new session to prevent signal propagation
                    start_new_session=True,
                    # Run in background
                    stdin=subprocess.DEVNULL,
                    # Set working directory
                    cwd=str(app_dir),
                    # Pass environment variables
                    env={
                        **os.environ,
                        "CLAUDE_CODE_ENTRYPOINT": "sdk-py",
                        "TASK_ID": str(task_id),
                        "PYTHONPATH": os.pathsep.join(sys.path)
                    }
                )
            
            # Store process info for monitoring
            process_info = {
                "task_id": task_id,
                "pid": process.pid,
                "script_path": str(script_path),
                "log_file": str(log_file)
            }
            
            # Save process info for recovery
            info_file = runner_dir / f"task_{task_id}_info.json"
            info_file.write_text(json.dumps(process_info, indent=2))
            
            logger.info(f"Task {task_id} started with PID {process.pid} in isolated process")
            
            # Don't wait for completion - let it run independently
            # The process will continue even if this server crashes
            
        except Exception as e:
            logger.error(f"Failed to start isolated task {task_id}: {e}", exc_info=True)
            raise


class TaskProcessManager:
    """
    Manages isolated task processes and provides recovery capabilities.
    """
    
    @staticmethod
    def list_running_tasks() -> list:
        """
        List all running isolated tasks by checking runner info files.
        """
        app_dir = Path.home() / ".claude-cto"
        runner_dir = app_dir / "runners"
        
        if not runner_dir.exists():
            return []
        
        running_tasks = []
        for info_file in runner_dir.glob("task_*_info.json"):
            try:
                info = json.loads(info_file.read_text())
                # Check if process is still running
                try:
                    os.kill(info["pid"], 0)  # Signal 0 just checks if process exists
                    running_tasks.append(info)
                except ProcessLookupError:
                    # Process is dead, clean up info file
                    info_file.unlink()
            except Exception as e:
                logger.warning(f"Error checking task info {info_file}: {e}")
        
        return running_tasks
    
    @staticmethod
    def cleanup_completed_tasks() -> int:
        """
        Clean up info files and scripts for completed tasks.
        Returns number of cleaned up tasks.
        """
        app_dir = Path.home() / ".claude-cto"
        runner_dir = app_dir / "runners"
        
        if not runner_dir.exists():
            return 0
        
        cleaned = 0
        for info_file in runner_dir.glob("task_*_info.json"):
            try:
                info = json.loads(info_file.read_text())
                # Check if process is still running
                try:
                    os.kill(info["pid"], 0)
                except ProcessLookupError:
                    # Process is dead, clean up files
                    info_file.unlink()
                    script_path = Path(info.get("script_path", ""))
                    if script_path.exists():
                        script_path.unlink()
                    cleaned += 1
            except Exception as e:
                logger.warning(f"Error cleaning up task info {info_file}: {e}")
        
        return cleaned