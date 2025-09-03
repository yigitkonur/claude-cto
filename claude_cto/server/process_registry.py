"""
SOLE RESPONSIBILITY: Track and manage all spawned processes (server, tasks, Claude subprocesses).
Provides recovery mechanisms for orphaned processes and ensures clean shutdown.
"""

import os
import signal
import psutil
import asyncio
from typing import Optional, List, Dict, Any
from datetime import datetime, timedelta
from pathlib import Path
import json
import logging

logger = logging.getLogger(__name__)


class ProcessRegistry:
    """
    Central process tracking system: maintains registry of all spawned processes.
    Critical for recovery after crashes and preventing process leaks.
    """
    
    # Registry file location for persistence across restarts
    REGISTRY_FILE = Path.home() / ".claude-cto" / "process_registry.json"
    
    def __init__(self):
        """Initialize process registry with persistent storage."""
        self.REGISTRY_FILE.parent.mkdir(exist_ok=True)
        self._registry: Dict[int, Dict[str, Any]] = {}
        self._load_registry()
    
    def _load_registry(self) -> None:
        """Load persisted registry from disk."""
        if self.REGISTRY_FILE.exists():
            try:
                with open(self.REGISTRY_FILE, 'r') as f:
                    data = json.load(f)
                    # Convert string keys back to integers
                    self._registry = {int(k): v for k, v in data.items()}
                logger.info(f"Loaded {len(self._registry)} entries from process registry")
            except Exception as e:
                logger.error(f"Failed to load process registry: {e}")
                self._registry = {}
    
    def _save_registry(self) -> None:
        """Persist registry to disk for recovery after crashes."""
        try:
            with open(self.REGISTRY_FILE, 'w') as f:
                # Convert integer keys to strings for JSON serialization
                data = {str(k): v for k, v in self._registry.items()}
                json.dump(data, f, indent=2, default=str)
        except Exception as e:
            logger.error(f"Failed to save process registry: {e}")
    
    def register_server(self, port: int) -> None:
        """Register the main server process."""
        pid = os.getpid()
        self._registry[pid] = {
            "type": "server",
            "port": port,
            "pid": pid,
            "started_at": datetime.utcnow().isoformat(),
            "status": "running"
        }
        self._save_registry()
        logger.info(f"Registered server process {pid} on port {port}")
    
    def register_task(self, task_id: int, task_pid: int) -> None:
        """Register a task execution process."""
        self._registry[task_pid] = {
            "type": "task",
            "task_id": task_id,
            "pid": task_pid,
            "parent_pid": os.getpid(),
            "started_at": datetime.utcnow().isoformat(),
            "status": "running",
            "claude_pids": []  # Will be populated when Claude subprocess starts
        }
        self._save_registry()
        logger.info(f"Registered task {task_id} with PID {task_pid}")
    
    async def register_claude_subprocess(self, task_id: int, timeout: float = 5.0) -> Optional[int]:
        """
        Detect and register Claude subprocess spawned by SDK.
        Uses psutil to find child processes matching Claude CLI pattern.
        """
        task_entry = None
        for entry in self._registry.values():
            if entry.get("type") == "task" and entry.get("task_id") == task_id:
                task_entry = entry
                break
        
        if not task_entry:
            logger.warning(f"Task {task_id} not found in registry")
            return None
        
        parent_pid = task_entry["pid"]
        start_time = datetime.utcnow()
        
        while (datetime.utcnow() - start_time).total_seconds() < timeout:
            try:
                parent_proc = psutil.Process(parent_pid)
                
                # Recursively find all child processes
                for child in parent_proc.children(recursive=True):
                    try:
                        # Check if this is a Claude CLI process
                        cmdline = ' '.join(child.cmdline()).lower()
                        if 'claude' in cmdline or 'node' in child.name().lower():
                            # Found Claude subprocess!
                            claude_pid = child.pid
                            
                            if claude_pid not in task_entry["claude_pids"]:
                                task_entry["claude_pids"].append(claude_pid)
                                self._save_registry()
                                logger.info(f"Registered Claude subprocess {claude_pid} for task {task_id}")
                                return claude_pid
                    except (psutil.NoSuchProcess, psutil.AccessDenied):
                        continue
            
            except psutil.NoSuchProcess:
                logger.warning(f"Parent process {parent_pid} no longer exists")
                return None
            
            # Brief wait before retry
            await asyncio.sleep(0.5)
        
        logger.warning(f"Could not find Claude subprocess for task {task_id} within {timeout}s")
        return None
    
    def get_orphaned_processes(self) -> List[Dict[str, Any]]:
        """
        Find processes that are still running but their parent server/task is dead.
        Critical for cleanup after server crashes.
        """
        orphaned = []
        
        for pid, entry in list(self._registry.items()):
            try:
                # Check if process is still running
                proc = psutil.Process(pid)
                
                if entry["type"] == "task":
                    # Check if parent server is still alive
                    parent_pid = entry.get("parent_pid")
                    if parent_pid and not psutil.pid_exists(parent_pid):
                        orphaned.append(entry)
                        logger.info(f"Found orphaned task process {pid}")
                    
                    # Check Claude subprocesses
                    for claude_pid in entry.get("claude_pids", []):
                        if psutil.pid_exists(claude_pid):
                            if not psutil.pid_exists(pid):  # Task dead but Claude alive
                                orphaned.append({
                                    "type": "claude_subprocess",
                                    "pid": claude_pid,
                                    "task_id": entry["task_id"],
                                    "task_pid": pid
                                })
                                logger.info(f"Found orphaned Claude subprocess {claude_pid}")
                
            except psutil.NoSuchProcess:
                # Process no longer exists, can be removed from registry
                if entry["status"] == "running":
                    entry["status"] = "dead"
                    entry["ended_at"] = datetime.utcnow().isoformat()
        
        self._save_registry()
        return orphaned
    
    def cleanup_orphaned_processes(self, force: bool = False) -> int:
        """
        Kill orphaned processes and clean up registry.
        Returns count of processes cleaned up.
        """
        orphaned = self.get_orphaned_processes()
        cleaned = 0
        
        for entry in orphaned:
            pid = entry["pid"]
            try:
                if force:
                    # Force kill
                    os.kill(pid, signal.SIGKILL)
                    logger.info(f"Force killed orphaned process {pid}")
                else:
                    # Graceful termination
                    os.kill(pid, signal.SIGTERM)
                    logger.info(f"Sent SIGTERM to orphaned process {pid}")
                
                cleaned += 1
                
                # Update registry
                if pid in self._registry:
                    self._registry[pid]["status"] = "terminated"
                    self._registry[pid]["ended_at"] = datetime.utcnow().isoformat()
                    
            except (ProcessLookupError, PermissionError) as e:
                logger.warning(f"Could not kill process {pid}: {e}")
        
        self._save_registry()
        return cleaned
    
    def cleanup_old_entries(self, max_age_days: int = 7) -> int:
        """Remove old entries from registry to prevent unbounded growth."""
        cutoff = datetime.utcnow() - timedelta(days=max_age_days)
        removed = 0
        
        for pid in list(self._registry.keys()):
            entry = self._registry[pid]
            if entry["status"] != "running":
                started_at = datetime.fromisoformat(entry["started_at"])
                if started_at < cutoff:
                    del self._registry[pid]
                    removed += 1
        
        if removed > 0:
            self._save_registry()
            logger.info(f"Removed {removed} old entries from process registry")
        
        return removed
    
    def mark_task_completed(self, task_id: int) -> None:
        """Mark a task and its subprocesses as completed."""
        for entry in self._registry.values():
            if entry.get("type") == "task" and entry.get("task_id") == task_id:
                entry["status"] = "completed"
                entry["ended_at"] = datetime.utcnow().isoformat()
                self._save_registry()
                logger.info(f"Marked task {task_id} as completed in registry")
                break
    
    def get_running_tasks(self) -> List[Dict[str, Any]]:
        """Get all currently running tasks."""
        running = []
        for entry in self._registry.values():
            if entry.get("type") == "task" and entry.get("status") == "running":
                running.append(entry)
        return running
    
    def is_server_running(self, port: int) -> bool:
        """Check if a server is already running on the specified port."""
        for entry in self._registry.values():
            if (entry.get("type") == "server" and 
                entry.get("port") == port and 
                entry.get("status") == "running"):
                
                # Verify process is actually alive
                pid = entry["pid"]
                if psutil.pid_exists(pid):
                    try:
                        proc = psutil.Process(pid)
                        # Double-check it's actually a claude-cto server
                        if 'claude_cto' in ' '.join(proc.cmdline()).lower():
                            return True
                    except (psutil.NoSuchProcess, psutil.AccessDenied):
                        pass
                
                # Process dead, update registry
                entry["status"] = "dead"
                entry["ended_at"] = datetime.utcnow().isoformat()
                self._save_registry()
        
        return False


# Global singleton instance
_registry_instance: Optional[ProcessRegistry] = None


def get_process_registry() -> ProcessRegistry:
    """Get or create the global process registry instance."""
    global _registry_instance
    if _registry_instance is None:
        _registry_instance = ProcessRegistry()
    return _registry_instance