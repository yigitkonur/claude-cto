"""
SOLE RESPONSIBILITY: Recovery service for orphaned tasks and processes after server crashes.
Handles cleanup, task state reconciliation, and process termination.
"""

import os
import signal
import asyncio
import psutil
from datetime import datetime, timedelta
from typing import List, Optional, Dict, Any
import logging

from .database import get_session
from . import crud, models
from .process_registry import get_process_registry
from .server_lock import ServerLock

logger = logging.getLogger(__name__)


class RecoveryService:
    """
    Server recovery orchestration: handles cleanup and recovery after crashes.
    Critical for maintaining system consistency and preventing resource leaks.
    """
    
    def __init__(self):
        """Initialize recovery service."""
        self.registry = get_process_registry()
        self.recovered_tasks = []
        self.terminated_processes = []
    
    async def recover_on_startup(self, port: int) -> Dict[str, Any]:
        """
        Main recovery routine executed on server startup.
        Cleans up orphaned processes and reconciles task states.
        
        Returns:
            Recovery statistics and actions taken
        """
        logger.info("Starting server recovery process...")
        stats = {
            "orphaned_processes_killed": 0,
            "tasks_marked_failed": 0,
            "stale_locks_cleaned": 0,
            "registry_entries_cleaned": 0,
            "claude_processes_terminated": 0
        }
        
        # Step 1: Clean up stale server locks
        stats["stale_locks_cleaned"] = ServerLock.cleanup_all_locks()
        
        # Step 2: Find and kill orphaned Claude processes
        stats["claude_processes_terminated"] = await self._cleanup_orphaned_claude_processes()
        
        # Step 3: Clean up orphaned processes from registry
        stats["orphaned_processes_killed"] = self.registry.cleanup_orphaned_processes()
        
        # Step 4: Reconcile database task states
        stats["tasks_marked_failed"] = await self._reconcile_task_states()
        
        # Step 5: Clean old registry entries
        stats["registry_entries_cleaned"] = self.registry.cleanup_old_entries(max_age_days=7)
        
        # Step 6: Register this server instance
        self.registry.register_server(port)
        
        logger.info(f"Recovery complete: {stats}")
        return stats
    
    async def _cleanup_orphaned_claude_processes(self) -> int:
        """
        Find and terminate orphaned Claude CLI processes.
        These are processes that continue running after server crash.
        """
        terminated = 0
        
        try:
            # Find all Claude processes
            for proc in psutil.process_iter(['pid', 'name', 'cmdline', 'create_time']):
                try:
                    # Check if this is a Claude CLI process
                    if proc.info['name'] and 'claude' in proc.info['name'].lower():
                        cmdline = ' '.join(proc.info.get('cmdline', [])).lower()
                        
                        # Check if it's an SDK-spawned process (has CLAUDE_CODE_ENTRYPOINT)
                        proc_env = proc.environ()
                        if proc_env.get('CLAUDE_CODE_ENTRYPOINT') == 'sdk-py':
                            # This is an SDK-spawned Claude process
                            
                            # Check if it's orphaned (no parent Python process)
                            try:
                                parent = proc.parent()
                                is_orphaned = False
                                
                                if not parent or not parent.is_running():
                                    is_orphaned = True
                                else:
                                    # Check if parent is a claude-cto process
                                    parent_cmdline = ' '.join(parent.cmdline()).lower()
                                    if 'claude_cto' not in parent_cmdline and 'claude-cto' not in parent_cmdline:
                                        # Parent exists but is not a claude-cto process
                                        is_orphaned = True
                                
                                if is_orphaned:
                                    # Orphaned! Terminate it
                                    logger.warning(f"Found orphaned Claude process {proc.info['pid']}")
                                    proc.terminate()
                                    terminated += 1
                                    
                                    # Wait briefly for graceful termination
                                    try:
                                        proc.wait(timeout=5)
                                    except psutil.TimeoutExpired:
                                        # Force kill if still running
                                        proc.kill()
                                        
                            except (psutil.NoSuchProcess, psutil.AccessDenied):
                                continue
                                
                except (psutil.NoSuchProcess, psutil.AccessDenied) as e:
                    continue
                    
        except Exception as e:
            logger.error(f"Error during Claude process cleanup: {e}")
        
        if terminated > 0:
            logger.info(f"Terminated {terminated} orphaned Claude processes")
        
        return terminated
    
    async def _reconcile_task_states(self) -> int:
        """
        Reconcile task states in database with actual running processes.
        Marks orphaned RUNNING tasks as FAILED.
        """
        marked_failed = 0
        
        for session in get_session():
            # Find all tasks in RUNNING state
            running_tasks = crud.get_tasks_by_status(session, models.TaskStatus.RUNNING)
            
            for task in running_tasks:
                should_fail = False
                failure_reason = None
                
                # Check if task has been running for too long (>2 hours)
                if task.started_at:
                    runtime = datetime.utcnow() - task.started_at
                    if runtime > timedelta(hours=2):
                        should_fail = True
                        failure_reason = "Task exceeded maximum runtime (2 hours)"
                
                # Check if task process is still alive
                if task.pid:
                    if not psutil.pid_exists(task.pid):
                        should_fail = True
                        failure_reason = "Task process no longer exists"
                    else:
                        try:
                            proc = psutil.Process(task.pid)
                            # Verify it's actually a Python process
                            if 'python' not in proc.name().lower():
                                should_fail = True
                                failure_reason = "PID exists but is not a Python process"
                        except (psutil.NoSuchProcess, psutil.AccessDenied):
                            should_fail = True
                            failure_reason = "Cannot access task process"
                else:
                    # No PID recorded, check if task is too old
                    if task.created_at:
                        age = datetime.utcnow() - task.created_at
                        if age > timedelta(hours=1):
                            should_fail = True
                            failure_reason = "Old task with no PID recorded"
                
                if should_fail:
                    # Mark task as failed
                    task.status = models.TaskStatus.FAILED
                    task.ended_at = datetime.utcnow()
                    task.error_message = f"Recovery: {failure_reason}"
                    session.add(task)
                    marked_failed += 1
                    
                    # Update registry if needed
                    if task.id:
                        self.registry.mark_task_completed(task.id)
                    
                    logger.info(f"Marked task {task.id} as FAILED: {failure_reason}")
            
            session.commit()
        
        return marked_failed
    
    async def recover_task(self, task_id: int) -> bool:
        """
        Attempt to recover a specific orphaned task.
        This is for future enhancement - currently just marks as failed.
        
        Args:
            task_id: Task to recover
            
        Returns:
            True if recovered, False otherwise
        """
        # For now, we don't support resuming tasks
        # Future enhancement: reconnect to Claude subprocess if still running
        
        for session in get_session():
            task = crud.get_task(session, task_id)
            if task and task.status == models.TaskStatus.RUNNING:
                task.status = models.TaskStatus.FAILED
                task.error_message = "Task cannot be recovered - manual retry required"
                task.ended_at = datetime.utcnow()
                session.add(task)
                session.commit()
                
                logger.info(f"Marked unrecoverable task {task_id} as FAILED")
                return False
        
        return False
    
    def get_recovery_report(self) -> Dict[str, Any]:
        """
        Generate a recovery report for monitoring and debugging.
        """
        orphaned = self.registry.get_orphaned_processes()
        running_tasks = self.registry.get_running_tasks()
        running_servers = ServerLock.get_all_running_servers()
        
        return {
            "timestamp": datetime.utcnow().isoformat(),
            "orphaned_processes": len(orphaned),
            "running_tasks": len(running_tasks),
            "running_servers": len(running_servers),
            "server_ports": [port for port, _ in running_servers],
            "recovered_tasks": self.recovered_tasks,
            "terminated_processes": self.terminated_processes,
            "orphaned_details": orphaned[:10]  # Limit to first 10 for readability
        }


async def perform_startup_recovery(port: int) -> Dict[str, Any]:
    """
    Convenience function to perform full recovery on server startup.
    
    Args:
        port: Server port being started
        
    Returns:
        Recovery statistics
    """
    recovery = RecoveryService()
    return await recovery.recover_on_startup(port)