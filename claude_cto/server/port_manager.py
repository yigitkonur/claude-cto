"""
SOLE RESPONSIBILITY: Manage server ports and prevent port proliferation.
Ensures only one primary server runs, kills duplicates on other ports.
"""

import os
import signal
import psutil
from pathlib import Path
from typing import Optional, List, Tuple
import logging
import time

logger = logging.getLogger(__name__)


class PortManager:
    """
    Manages server ports to prevent proliferation.
    Ensures only one primary server instance is running.
    """
    
    # Default port and fallback sequence
    DEFAULT_PORT = 8000
    FALLBACK_PORTS = [8001, 8002, 8003, 8004, 8888, 9999, 7777, 7778, 7779]
    
    @classmethod
    def find_claude_cto_servers(cls) -> List[Tuple[int, int]]:
        """
        Find all running claude-cto servers.
        Returns list of (pid, port) tuples.
        """
        servers = []
        
        for proc in psutil.process_iter(['pid', 'cmdline']):
            try:
                cmdline = proc.info.get('cmdline', [])
                if not cmdline:
                    continue
                    
                cmdline_str = ' '.join(cmdline)
                
                # Check if it's a claude-cto server
                if 'claude_cto.server.main' in cmdline_str or 'claude-cto server' in cmdline_str:
                    # Extract port from command line
                    port = None
                    for i, arg in enumerate(cmdline):
                        if arg == '--port' and i + 1 < len(cmdline):
                            try:
                                port = int(cmdline[i + 1])
                            except ValueError:
                                pass
                    
                    if port:
                        servers.append((proc.info['pid'], port))
                        
            except (psutil.NoSuchProcess, psutil.AccessDenied):
                continue
        
        return servers
    
    @classmethod
    def cleanup_duplicate_servers(cls, keep_port: Optional[int] = None) -> int:
        """
        Kill all duplicate servers except the one on keep_port.
        If keep_port is None, keeps the server on DEFAULT_PORT or the first one found.
        Returns number of servers killed.
        """
        servers = cls.find_claude_cto_servers()
        
        if not servers:
            return 0
        
        # Determine which server to keep
        if keep_port is None:
            # Prefer DEFAULT_PORT if available
            default_server = next((s for s in servers if s[1] == cls.DEFAULT_PORT), None)
            if default_server:
                keep_port = cls.DEFAULT_PORT
            else:
                # Keep the first server found
                keep_port = servers[0][1]
        
        killed = 0
        for pid, port in servers:
            if port != keep_port:
                try:
                    logger.warning(f"Killing duplicate server PID {pid} on port {port}")
                    os.kill(pid, signal.SIGTERM)
                    
                    # Wait for graceful shutdown
                    for _ in range(5):
                        if not psutil.pid_exists(pid):
                            break
                        time.sleep(0.2)
                    else:
                        # Force kill if still alive
                        os.kill(pid, signal.SIGKILL)
                    
                    killed += 1
                    logger.info(f"Killed duplicate server on port {port}")
                    
                except (ProcessLookupError, PermissionError) as e:
                    logger.error(f"Failed to kill server PID {pid}: {e}")
        
        return killed
    
    @classmethod
    def get_next_available_port(cls, start_port: int = None) -> int:
        """
        Find next available port for server.
        Checks if port is free and not used by another claude-cto server.
        """
        import socket
        
        if start_port is None:
            start_port = cls.DEFAULT_PORT
        
        ports_to_try = [start_port] + cls.FALLBACK_PORTS
        
        for port in ports_to_try:
            # Check if port is free
            sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
            try:
                sock.bind(('127.0.0.1', port))
                sock.close()
                
                # Also check no claude-cto server is using it
                servers = cls.find_claude_cto_servers()
                if not any(s[1] == port for s in servers):
                    return port
                    
            except OSError:
                continue
            finally:
                sock.close()
        
        # If all ports are taken, find a random free port
        sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        sock.bind(('127.0.0.1', 0))
        port = sock.getsockname()[1]
        sock.close()
        return port
    
    @classmethod
    def ensure_single_server(cls, target_port: int = None) -> Tuple[bool, str]:
        """
        Ensure only one server is running on target_port.
        Kills all others if found.
        Returns (success, message) tuple.
        """
        if target_port is None:
            target_port = cls.DEFAULT_PORT
        
        servers = cls.find_claude_cto_servers()
        
        # Check if target port is already in use
        target_server = next((s for s in servers if s[1] == target_port), None)
        
        if target_server:
            # Kill all other servers
            killed = cls.cleanup_duplicate_servers(keep_port=target_port)
            if killed > 0:
                return True, f"Kept server on port {target_port}, killed {killed} duplicates"
            else:
                return True, f"Server already running on port {target_port}"
        else:
            # No server on target port, kill all servers
            killed = 0
            for pid, port in servers:
                try:
                    logger.info(f"Killing server PID {pid} on port {port}")
                    os.kill(pid, signal.SIGTERM)
                    time.sleep(0.5)
                    killed += 1
                except (ProcessLookupError, PermissionError):
                    pass
            
            if killed > 0:
                return True, f"Killed {killed} servers, port {target_port} is now free"
            else:
                return True, f"No servers running, port {target_port} is free"