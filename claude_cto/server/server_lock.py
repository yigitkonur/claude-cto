"""
SOLE RESPONSIBILITY: Ensure single server instance per port using PID file locks.
Prevents multiple servers from running on the same port and handles stale locks.
"""

import os
import signal
import psutil
from pathlib import Path
from typing import Optional
import logging
import time

logger = logging.getLogger(__name__)


class ServerLock:
    """
    Server instance lock manager: ensures only one server runs per port.
    Uses PID files for cross-process synchronization and crash recovery.
    """
    
    # Lock directory - using /tmp for cross-platform compatibility
    LOCK_DIR = Path("/tmp/claude-cto-locks")
    
    def __init__(self, port: int):
        """Initialize lock manager for specific port."""
        self.port = port
        self.LOCK_DIR.mkdir(exist_ok=True, parents=True)
        self.lock_file = self.LOCK_DIR / f"server-{port}.pid"
        self.pid = os.getpid()
    
    def is_server_running(self) -> tuple[bool, Optional[int]]:
        """
        Check if a server is already running on this port.
        Returns (is_running, pid) tuple.
        """
        if not self.lock_file.exists():
            return False, None
        
        try:
            # Read PID from lock file
            old_pid = int(self.lock_file.read_text().strip())
            
            # Check if process exists
            if not psutil.pid_exists(old_pid):
                # Stale lock file
                logger.info(f"Found stale lock file for port {self.port} (PID {old_pid} dead)")
                return False, old_pid
            
            # Verify it's actually a claude-cto server
            try:
                proc = psutil.Process(old_pid)
                cmdline = ' '.join(proc.cmdline()).lower()
                
                if 'claude_cto.server' in cmdline and str(self.port) in ' '.join(proc.cmdline()):
                    # Server is actually running
                    return True, old_pid
                else:
                    # Different process has taken this PID
                    logger.warning(f"PID {old_pid} exists but is not a claude-cto server")
                    return False, old_pid
                    
            except (psutil.NoSuchProcess, psutil.AccessDenied):
                return False, old_pid
                
        except (ValueError, OSError) as e:
            logger.error(f"Error reading lock file: {e}")
            return False, None
    
    def acquire(self, force: bool = False, kill_existing: bool = False) -> bool:
        """
        Acquire server lock for this port.
        
        Args:
            force: Remove stale locks automatically
            kill_existing: Kill existing server if running
            
        Returns:
            True if lock acquired, False otherwise
        """
        is_running, existing_pid = self.is_server_running()
        
        if is_running and existing_pid:
            if kill_existing:
                # Kill existing server
                logger.warning(f"Killing existing server {existing_pid} on port {self.port}")
                try:
                    os.kill(existing_pid, signal.SIGTERM)
                    # Wait for process to die
                    for _ in range(10):
                        if not psutil.pid_exists(existing_pid):
                            break
                        time.sleep(0.5)
                    else:
                        # Force kill if still alive
                        os.kill(existing_pid, signal.SIGKILL)
                        time.sleep(0.5)
                except (ProcessLookupError, PermissionError) as e:
                    logger.error(f"Failed to kill existing server: {e}")
                    return False
            else:
                # Server already running, cannot acquire lock
                logger.error(f"Server already running on port {self.port} (PID {existing_pid})")
                return False
        
        # Remove stale lock if exists
        if self.lock_file.exists() and (force or not is_running):
            try:
                self.lock_file.unlink()
                logger.info(f"Removed stale lock file for port {self.port}")
            except OSError as e:
                logger.error(f"Failed to remove lock file: {e}")
                return False
        
        # Create new lock file
        try:
            # Write PID atomically
            temp_file = self.lock_file.with_suffix('.tmp')
            temp_file.write_text(str(self.pid))
            temp_file.replace(self.lock_file)
            
            logger.info(f"Acquired lock for port {self.port} (PID {self.pid})")
            return True
            
        except OSError as e:
            logger.error(f"Failed to create lock file: {e}")
            return False
    
    def release(self) -> None:
        """Release server lock on shutdown."""
        if self.lock_file.exists():
            try:
                # Verify we own the lock
                stored_pid = int(self.lock_file.read_text().strip())
                if stored_pid == self.pid:
                    self.lock_file.unlink()
                    logger.info(f"Released lock for port {self.port}")
                else:
                    logger.warning(f"Lock file contains different PID {stored_pid}, not removing")
            except (ValueError, OSError) as e:
                logger.error(f"Error releasing lock: {e}")
    
    def __enter__(self):
        """Context manager entry - acquire lock."""
        if not self.acquire(force=True):
            raise RuntimeError(f"Could not acquire lock for port {self.port}")
        return self
    
    def __exit__(self, exc_type, exc_val, exc_tb):
        """Context manager exit - release lock."""
        self.release()
    
    @classmethod
    def cleanup_all_locks(cls) -> int:
        """
        Clean up all stale lock files.
        Returns count of locks cleaned.
        """
        if not cls.LOCK_DIR.exists():
            return 0
        
        cleaned = 0
        for lock_file in cls.LOCK_DIR.glob("server-*.pid"):
            try:
                pid = int(lock_file.read_text().strip())
                if not psutil.pid_exists(pid):
                    lock_file.unlink()
                    cleaned += 1
                    logger.info(f"Cleaned up stale lock {lock_file.name}")
            except (ValueError, OSError) as e:
                logger.warning(f"Error cleaning lock {lock_file}: {e}")
        
        return cleaned
    
    @classmethod
    def get_all_running_servers(cls) -> list[tuple[int, int]]:
        """
        Get all running servers.
        Returns list of (port, pid) tuples.
        """
        if not cls.LOCK_DIR.exists():
            return []
        
        servers = []
        for lock_file in cls.LOCK_DIR.glob("server-*.pid"):
            try:
                port = int(lock_file.stem.split('-')[1])
                pid = int(lock_file.read_text().strip())
                
                # Verify process is alive
                if psutil.pid_exists(pid):
                    proc = psutil.Process(pid)
                    if 'claude_cto' in ' '.join(proc.cmdline()).lower():
                        servers.append((port, pid))
            except (ValueError, OSError, psutil.NoSuchProcess):
                continue
        
        return servers