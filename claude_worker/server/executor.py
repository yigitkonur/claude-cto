"""
SOLE RESPONSIBILITY: Defines the TaskExecutor class, which encapsulates the logic 
for running a single agentic task using the Claude Code SDK's query() function.
"""

import os
import asyncio
from datetime import datetime
from claude_code_sdk import query, ClaudeCodeOptions
from claude_code_sdk._errors import ProcessError, ClaudeSDKError
from .database import get_session
from . import crud
from .log_formatter import format_tool_use


class TaskExecutor:
    """
    Executes a single claude-worker task in an isolated process.
    Manages the entire lifecycle: status updates, SDK communication, and result finalization.
    """
    
    def __init__(self, task_id: int):
        """
        Minimal constructor - only stores task ID.
        Does NOT acquire database session (object will be pickled for worker process).
        """
        self.task_id = task_id
    
    async def run(self):
        """
        Main execution method for the task.
        Orchestrates SDK interaction and database updates.
        """
        # Get initial task info and mark as running
        for session in get_session():
            task_record = crud.get_task(session, self.task_id)
            if not task_record:
                return
            
            # Update status to running and set PID
            task_record.status = 'running'
            task_record.pid = os.getpid()
            task_record.started_at = datetime.utcnow()
            session.add(task_record)
            session.commit()
            
            # Store task data for use outside session
            working_directory = task_record.working_directory
            system_prompt = task_record.system_prompt
            execution_prompt = task_record.execution_prompt
            raw_log_path = task_record.raw_log_path
        
        # Configure SDK options
        options = ClaudeCodeOptions(
            cwd=working_directory,
            system_prompt=system_prompt
        )
        
        # Execute task using SDK
        try:
            # Open raw log file for writing
            with open(raw_log_path, 'w') as raw_log:
                # Use the stateless query() function for fire-and-forget execution
                async for message in query(prompt=execution_prompt, options=options):
                    # Write raw message to log
                    raw_log.write(f"[{datetime.utcnow().isoformat()}] {message}\n")
                    raw_log.flush()
                    
                    # Process message for summary and database updates
                    await self._process_message(message)
            
            # Task completed successfully
            for session in get_session():
                crud.finalize_task(
                    session, 
                    self.task_id, 
                    'completed',
                    'Task completed successfully'
                )
        
        except ProcessError as e:
            # Handle SDK process errors
            error_msg = f"Process error: {e.stderr if e.stderr else str(e)}"
            for session in get_session():
                crud.finalize_task(
                    session,
                    self.task_id,
                    'error',
                    error_msg
                )
        
        except ClaudeSDKError as e:
            # Handle other SDK errors
            error_msg = f"SDK error: {str(e)}"
            for session in get_session():
                crud.finalize_task(
                    session,
                    self.task_id,
                    'error',
                    error_msg
                )
        
        except Exception as e:
            # Handle unexpected errors
            error_msg = f"Unexpected error: {str(e)}"
            for session in get_session():
                crud.finalize_task(
                    session,
                    self.task_id,
                    'error',
                    error_msg
                )
    
    async def _process_message(self, message):
        """
        Process individual messages from the SDK stream.
        Extracts relevant information and updates summary log.
        """
        summary_line = None
        
        # Check if message has tool use blocks
        if hasattr(message, 'content') and message.content:
            for block in message.content:
                if hasattr(block, 'name'):  # ToolUseBlock
                    summary_line = format_tool_use(block)
                    break
        
        # If we have something to log, update the database
        if summary_line:
            for session in get_session():
                crud.append_to_summary_log(
                    session,
                    self.task_id,
                    summary_line
                )