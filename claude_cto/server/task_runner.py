"""
SOLE RESPONSIBILITY: Isolated task execution using subprocess for process independence.
Tasks run in separate process groups and survive server crashes.
"""

import os
import sys
import subprocess
import asyncio
import json
import signal
from pathlib import Path
from typing import Optional
from datetime import datetime, timedelta
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
import signal
import time
from datetime import datetime, timedelta

# Add parent directory to path to import claude_cto modules
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from claude_cto.server.executor import TaskExecutor

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)

# Task timeout (default: 2 hours)
TASK_TIMEOUT = int(os.environ.get('TASK_TIMEOUT', '7200'))
# Task started time
start_time = datetime.now()

def timeout_handler(signum, frame):
    '''Handle timeout signal'''
    duration = (datetime.now() - start_time).total_seconds()
    logging.error(f"Task {task_id} timed out after {{duration:.0f}} seconds")
    sys.exit(124)  # Standard timeout exit code

# Set up timeout
if TASK_TIMEOUT > 0:
    signal.signal(signal.SIGALRM, timeout_handler)
    signal.alarm(TASK_TIMEOUT)

async def main():
    task_id = {task_id}
    try:
        # CRITICAL: Force new database connection in subprocess
        # Reset any existing engine to prevent connection sharing
        from claude_cto.server import database
        database._engine = None
        database._SessionLocal = None
        
        executor = TaskExecutor(task_id)
        await executor.run()
    except Exception as e:
        logging.error(f"Task {{task_id}} failed: {{e}}", exc_info=True)
        sys.exit(1)
    finally:
        # Cancel timeout if task completed
        if TASK_TIMEOUT > 0:
            signal.alarm(0)

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
        - Resource limits and timeout protection
        - Automatic cleanup of old files
        """
        try:
            # Get application directory for script storage
            app_dir = Path.home() / ".claude-cto"
            runner_dir = app_dir / "runners"
            runner_dir.mkdir(exist_ok=True)
            
            # Load configuration
            from .config import get_config
            config = get_config()
            
            # Cleanup old runner files
            IsolatedTaskRunner._cleanup_old_files(
                runner_dir, 
                days=config.task.cleanup_interval_days
            )
            
            # Check concurrent task limit
            running_count = len(TaskProcessManager.list_running_tasks())
            if running_count >= config.task.max_concurrent_tasks:
                raise RuntimeError(
                    f"Too many concurrent tasks ({running_count}/{config.task.max_concurrent_tasks})"
                )
            
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
                # Prepare resource-limited command
                memory_limit_mb = config.task.task_memory_limit_mb
                timeout_seconds = config.task.task_timeout_seconds
                
                # Use ulimit to set resource limits on Unix systems
                if sys.platform != "win32":
                    # Memory limit in KB for ulimit
                    memory_limit_kb = memory_limit_mb * 1024
                    cmd = [
                        'bash', '-c', 
                        f'ulimit -v {memory_limit_kb}; exec {sys.executable} {script_path}'
                    ]
                else:
                    cmd = [sys.executable, str(script_path)]
                
                process = subprocess.Popen(
                    cmd,
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
                        "TASK_TIMEOUT": str(timeout_seconds),
                        "TASK_MEMORY_LIMIT_MB": str(memory_limit_mb),
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
    
    @staticmethod
    def _cleanup_old_files(directory: Path, days: int = 7):
        """
        Clean up old files in directory older than specified days.
        """
        try:
            cutoff = datetime.now() - timedelta(days=days)
            cleaned = 0
            
            for file_path in directory.glob("task_*"):
                if file_path.stat().st_mtime < cutoff.timestamp():
                    file_path.unlink()
                    cleaned += 1
            
            if cleaned > 0:
                logger.info(f"Cleaned up {cleaned} old files from {directory}")
        except Exception as e:
            logger.warning(f"Error cleaning old files: {e}")


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
    
    @staticmethod
    def kill_task(task_id: int, force: bool = False) -> bool:
        """
        Kill an isolated task by ID.
        
        Args:
            task_id: The task ID to kill
            force: Use SIGKILL instead of SIGTERM
            
        Returns:
            True if task was killed, False if not found
        """
        app_dir = Path.home() / ".claude-cto"
        info_file = app_dir / "runners" / f"task_{task_id}_info.json"
        
        if not info_file.exists():
            return False
        
        try:
            info = json.loads(info_file.read_text())
            pid = info["pid"]
            
            # Try to kill the process
            try:
                if force:
                    os.kill(pid, signal.SIGKILL)
                    logger.warning(f"Force killed task {task_id} (PID {pid})")
                else:
                    os.kill(pid, signal.SIGTERM)
                    logger.info(f"Sent SIGTERM to task {task_id} (PID {pid})")
                
                # Clean up info file
                info_file.unlink()
                
                # Clean up script file
                script_path = Path(info.get("script_path", ""))
                if script_path.exists():
                    script_path.unlink()
                
                return True
                
            except ProcessLookupError:
                # Process already dead
                info_file.unlink()
                return False
                
        except Exception as e:
            logger.error(f"Error killing task {task_id}: {e}")
            return False
    
    @staticmethod
    def kill_all_tasks() -> int:
        """
        Kill all running isolated tasks.
        Returns number of tasks killed.
        """
        tasks = TaskProcessManager.list_running_tasks()
        killed = 0
        
        for task_info in tasks:
            if TaskProcessManager.kill_task(task_info["task_id"]):
                killed += 1
        
        return killed