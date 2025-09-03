"""
SOLE RESPONSIBILITY: Handle system signals for graceful server shutdown.
Ensures tasks are properly saved and resources cleaned up on termination.
"""

import signal
import asyncio
import logging
from typing import Optional, Set
import sys

logger = logging.getLogger(__name__)


class SignalHandler:
    """
    Manages graceful shutdown on system signals (SIGTERM, SIGINT).
    Ensures running tasks are saved and resources properly released.
    """
    
    def __init__(self):
        self.shutdown_event = asyncio.Event()
        self.handlers_installed = False
        self.original_handlers = {}
        self.shutdown_callbacks = []
        self.running_tasks: Set[int] = set()
        
    def add_shutdown_callback(self, callback):
        """Add a callback to run during shutdown."""
        self.shutdown_callbacks.append(callback)
        
    def register_task(self, task_id: int):
        """Register a running task."""
        self.running_tasks.add(task_id)
        
    def unregister_task(self, task_id: int):
        """Unregister a completed task."""
        self.running_tasks.discard(task_id)
        
    def install_handlers(self):
        """Install signal handlers for graceful shutdown."""
        if self.handlers_installed:
            return
            
        # Store original handlers
        self.original_handlers[signal.SIGTERM] = signal.signal(signal.SIGTERM, self._handle_signal)
        self.original_handlers[signal.SIGINT] = signal.signal(signal.SIGINT, self._handle_signal)
        
        # Handle Windows if needed
        if sys.platform == "win32":
            self.original_handlers[signal.SIGBREAK] = signal.signal(signal.SIGBREAK, self._handle_signal)
        
        self.handlers_installed = True
        logger.info("Signal handlers installed for graceful shutdown")
        
    def restore_handlers(self):
        """Restore original signal handlers."""
        for sig, handler in self.original_handlers.items():
            signal.signal(sig, handler)
        self.handlers_installed = False
        
    def _handle_signal(self, signum, frame):
        """Handle shutdown signal."""
        sig_name = signal.Signals(signum).name
        logger.warning(f"Received {sig_name} signal, initiating graceful shutdown...")
        
        # Set shutdown event
        self.shutdown_event.set()
        
        # Log running tasks
        if self.running_tasks:
            logger.info(f"Saving state for {len(self.running_tasks)} running tasks: {self.running_tasks}")
        
        # Schedule async shutdown
        asyncio.create_task(self._async_shutdown())
        
    async def _async_shutdown(self):
        """Perform async shutdown tasks."""
        try:
            # Run shutdown callbacks
            for callback in self.shutdown_callbacks:
                try:
                    if asyncio.iscoroutinefunction(callback):
                        await callback()
                    else:
                        callback()
                except Exception as e:
                    logger.error(f"Error in shutdown callback: {e}")
                    
            # Give tasks a moment to save state
            logger.info("Waiting for tasks to save state...")
            await asyncio.sleep(2)
            
        except Exception as e:
            logger.error(f"Error during graceful shutdown: {e}")
        finally:
            # Force exit after grace period
            logger.info("Graceful shutdown complete")
            sys.exit(0)
            
    async def wait_for_shutdown(self):
        """Wait for shutdown signal."""
        await self.shutdown_event.wait()
        
    def is_shutting_down(self) -> bool:
        """Check if shutdown has been initiated."""
        return self.shutdown_event.is_set()


# Global singleton
_signal_handler: Optional[SignalHandler] = None


def get_signal_handler() -> SignalHandler:
    """Get global signal handler instance."""
    global _signal_handler
    if _signal_handler is None:
        _signal_handler = SignalHandler()
    return _signal_handler


def install_signal_handlers():
    """Install global signal handlers."""
    handler = get_signal_handler()
    handler.install_handlers()
    

def is_shutting_down() -> bool:
    """Check if server is shutting down."""
    handler = get_signal_handler()
    return handler.is_shutting_down()