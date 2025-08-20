"""
SOLE RESPONSIBILITY: Defines the TaskExecutor class, which encapsulates the logic 
for running a single agentic task using the Claude Code SDK's query() function.
"""

import os
import asyncio
from datetime import datetime
from claude_code_sdk import query, ClaudeCodeOptions
from claude_code_sdk._errors import (
    ProcessError, 
    ClaudeSDKError, 
    CLIConnectionError, 
    CLINotFoundError,
    CLIJSONDecodeError,
    MessageParseError
)
from .database import get_session
from . import crud, models
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
        # Set SDK environment variable for subprocess
        os.environ["CLAUDE_CODE_ENTRYPOINT"] = "sdk-py"
        
        # Note: Claude CLI automatically handles authentication priority:
        # 1. Uses ANTHROPIC_API_KEY if set and valid
        # 2. Falls back to OAuth (Claude Max subscription) if API key fails/missing
        # No additional configuration needed - the CLI handles both methods
        
        # Get initial task info and mark as running
        for session in get_session():
            task_record = crud.get_task(session, self.task_id)
            if not task_record:
                return
            
            # Update status to running and set PID
            task_record.status = models.TaskStatus.RUNNING
            task_record.pid = os.getpid()
            task_record.started_at = datetime.utcnow()
            session.add(task_record)
            session.commit()
            
            # Store task data for use outside session
            working_directory = task_record.working_directory
            system_prompt = task_record.system_prompt
            execution_prompt = task_record.execution_prompt
            log_file_path = task_record.log_file_path
            model = task_record.model  # Get the model from task record
        
        # Configure SDK options
        options = ClaudeCodeOptions(
            cwd=working_directory,
            system_prompt=system_prompt,
            model=model,  # Pass the model to Claude SDK
            permission_mode='bypassPermissions'  # Required for automated execution
        )
        
        # Execute task using SDK
        try:
            # Open log file for writing
            with open(log_file_path, 'w') as raw_log:
                raw_log.write(f"[INFO] Starting task {self.task_id}\n")
                raw_log.write(f"[INFO] Working directory: {working_directory}\n")
                raw_log.write(f"[INFO] Prompt: {execution_prompt}\n")
                raw_log.write(f"[INFO] System prompt: {system_prompt}\n")
                raw_log.flush()
                
                # Use the stateless query() function for fire-and-forget execution
                message_count = 0
                async for message in query(prompt=execution_prompt, options=options):
                    message_count += 1
                    # Write raw message to log
                    raw_log.write(f"[{datetime.utcnow().isoformat()}] Message {message_count}: {type(message).__name__}\n")
                    raw_log.flush()
                    
                    # Process message for summary and database updates
                    await self._process_message(message)
            
                raw_log.write(f"[INFO] Task completed with {message_count} messages\n")
                raw_log.flush()
            
            # Task completed successfully
            for session in get_session():
                crud.finalize_task(
                    session, 
                    self.task_id, 
                    models.TaskStatus.COMPLETED,
                    f'Task completed successfully ({message_count} messages)'
                )
        
        except ProcessError as e:
            # Handle SDK process errors with detailed information
            # ProcessError has: exit_code, stderr attributes from SDK
            error_details = []
            error_details.append(f"Process error: {str(e)}")
            
            # Use actual ProcessError attributes from SDK
            if e.exit_code is not None:
                error_details.append(f"exit_code: {e.exit_code}")
            
            if e.stderr:
                error_details.append(f"stderr: {e.stderr}")
            
            error_msg = " | ".join(error_details)
            
            # Also write to raw log
            with open(log_file_path, 'a') as f:
                f.write(f"[ERROR] ProcessError - exit_code: {e.exit_code}, stderr: {e.stderr}\n")
                f.write(f"[ERROR] Full message: {error_msg}\n")
            
            for session in get_session():
                crud.finalize_task(
                    session,
                    self.task_id,
                    models.TaskStatus.FAILED,
                    error_msg
                )
        
        except CLINotFoundError as e:
            # Handle CLI not found - critical error that needs user action
            error_msg = f"Claude CLI not found: {str(e)}. Please install Claude CLI and ensure it's in your PATH."
            
            with open(log_file_path, 'a') as f:
                f.write(f"[ERROR] CLINotFoundError: {error_msg}\n")
                f.write("[ERROR] Installation guide: https://docs.anthropic.com/en/docs/claude-cli\n")
                
            for session in get_session():
                crud.finalize_task(
                    session,
                    self.task_id,
                    models.TaskStatus.FAILED,
                    error_msg
                )
        
        except CLIConnectionError as e:
            # Handle CLI connection errors - might be transient, attempt brief retry
            error_msg = f"Failed to connect to Claude CLI: {str(e)}. Check if Claude CLI is working with 'claude --version'."
            
            # Log the attempt
            with open(log_file_path, 'a') as f:
                f.write(f"[ERROR] CLIConnectionError: {error_msg}\n")
                f.write("[INFO] Connection errors can be transient - this is a critical failure\n")
                
            # For connection errors, fail immediately as they usually indicate CLI issues
            for session in get_session():
                crud.finalize_task(
                    session,
                    self.task_id,
                    models.TaskStatus.FAILED,
                    error_msg + " | Suggestion: Run 'claude --version' to verify CLI installation"
                )
        
        except CLIJSONDecodeError as e:
            # Handle JSON decode errors from CLI output
            error_msg = f"Failed to parse CLI JSON output: {str(e)}. Line: '{e.line[:100]}...'"
            
            with open(log_file_path, 'a') as f:
                f.write(f"[ERROR] CLIJSONDecodeError: {error_msg}\n")
                f.write(f"[ERROR] Original error: {e.original_error}\n")
                f.write(f"[ERROR] Problematic line: {e.line}\n")
                
            for session in get_session():
                crud.finalize_task(
                    session,
                    self.task_id,
                    models.TaskStatus.FAILED,
                    error_msg
                )
        
        except MessageParseError as e:
            # Handle message parsing errors
            error_msg = f"Failed to parse CLI message: {str(e)}"
            if e.data:
                error_msg += f" | Data: {e.data}"
            
            with open(log_file_path, 'a') as f:
                f.write(f"[ERROR] MessageParseError: {error_msg}\n")
                f.write(f"[ERROR] Raw data: {e.data}\n")
                
            for session in get_session():
                crud.finalize_task(
                    session,
                    self.task_id,
                    models.TaskStatus.FAILED,
                    error_msg
                )
        
        except ClaudeSDKError as e:
            # Handle other SDK errors with details
            error_msg = f"SDK error: {str(e)} | Type: {type(e).__name__}"
            
            # Also write to raw log
            with open(log_file_path, 'a') as f:
                f.write(f"[ERROR] {error_msg}\n")
                
            for session in get_session():
                crud.finalize_task(
                    session,
                    self.task_id,
                    models.TaskStatus.FAILED,
                    error_msg
                )
        
        except Exception as e:
            # Handle unexpected errors with stack trace
            import traceback
            error_msg = f"Unexpected error: {str(e)} | Type: {type(e).__name__} | Traceback: {traceback.format_exc()}"
            
            # Also write to raw log
            with open(log_file_path, 'a') as f:
                f.write(f"[ERROR] {error_msg}\n")
                f.write(f"[ERROR] Full traceback:\n{traceback.format_exc()}\n")
                
            for session in get_session():
                crud.finalize_task(
                    session,
                    self.task_id,
                    models.TaskStatus.FAILED,
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