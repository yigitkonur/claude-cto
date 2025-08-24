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
    MessageParseError,
)
from claude_code_sdk.types import Message, AssistantMessage, ToolUseBlock
from .database import get_session
from . import crud, models
from .log_formatter import format_content_block
from .error_handler import ErrorHandler
from .task_logger import create_task_logger
from .memory_monitor import get_memory_monitor


class TaskExecutor:
    """
    Executes a single claude-cto task in an isolated process.
    Manages the entire lifecycle: status updates, SDK communication, and result finalization.
    """

    def __init__(self, task_id: int):
        """
        Minimal constructor - only stores task ID.
        Does NOT acquire database session (object will be pickled for worker process).
        """
        self.task_id = task_id

    async def run(self) -> None:
        """
        Main execution method for the task with simple retry logic for transient errors.
        """
        # Set SDK environment variable for subprocess
        os.environ["CLAUDE_CODE_ENTRYPOINT"] = "sdk-py"

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
            model = task_record.model

        # Configure SDK options
        options = ClaudeCodeOptions(
            cwd=working_directory,
            system_prompt=system_prompt,
            model=model,
            permission_mode="bypassPermissions",
        )

        # Simple timeout based on model
        timeout_seconds = {
            "haiku": 600,  # 10 minutes
            "sonnet": 1800,  # 30 minutes
            "opus": 3600,  # 60 minutes
        }.get(model.value, 1800)

        # Create task logger for structured logging
        task_logger = create_task_logger(self.task_id, working_directory)

        # CRITICAL FIX: Start memory monitoring for this task
        memory_monitor = get_memory_monitor()
        memory_monitor.start_task_monitoring(self.task_id)

        # Execute with simple retry logic (3 attempts for transient errors only)
        max_attempts = 3
        attempt = 0
        last_error = None
        start_time = datetime.utcnow()
        
        try:
            while attempt < max_attempts:
                attempt += 1

                try:
                    # Initialize structured logging on first attempt
                    if attempt == 1:
                        task_logger.log_task_start(
                            execution_prompt=execution_prompt,
                            model=model.value,
                            system_prompt=system_prompt,
                        )
                    else:
                        task_logger.log_task_progress(
                            f"Retry attempt {attempt}/{max_attempts} after error: {last_error}",
                            "RETRY",
                        )

                    # Open legacy log file for backward compatibility
                    with open(log_file_path, "a") as raw_log:
                        if attempt > 1:
                            raw_log.write(f"[RETRY] Attempt {attempt}/{max_attempts}\n")
                        else:
                            raw_log.write(f"[INFO] Starting task {self.task_id}\n")
                            raw_log.write(
                                f"[INFO] Working directory: {working_directory}\n"
                            )
                            raw_log.write(f"[INFO] Prompt: {execution_prompt}\n")
                            raw_log.write(f"[INFO] System prompt: {system_prompt}\n")
                            raw_log.write(f"[INFO] Timeout: {timeout_seconds}s\n")
                        raw_log.flush()

                    # Execute with timeout
                    message_count = 0

                    async def execute_query():
                        nonlocal message_count
                        async for message in query(
                            prompt=execution_prompt, options=options
                        ):
                            message_count += 1
                            raw_log.write(
                                f"[{datetime.utcnow().isoformat()}] Message {message_count}: {type(message).__name__}\n"
                            )
                            raw_log.flush()

                            # Process message for summary and database updates
                            await self._process_message(message, task_logger)
                        return message_count

                    # Run with timeout
                    try:
                        await asyncio.wait_for(execute_query(), timeout=timeout_seconds)
                    except asyncio.TimeoutError:
                        raise TimeoutError(f"Task exceeded {timeout_seconds}s timeout")

                    raw_log.write(
                        f"[INFO] Task completed with {message_count} messages\n"
                    )
                    if attempt > 1:
                        raw_log.write(f"[INFO] Succeeded after {attempt} attempts\n")
                    raw_log.flush()

                    # Task completed successfully
                    duration = (datetime.utcnow() - start_time).total_seconds()
                    success_msg = f"Task completed successfully ({message_count} messages)"
                    if attempt > 1:
                        success_msg += f" after {attempt} attempts"

                    # Log completion with structured logger
                    task_logger.log_task_completion(True, success_msg, duration)

                    for session in get_session():
                        crud.finalize_task(
                            session, self.task_id, models.TaskStatus.COMPLETED, success_msg
                        )
                        
                    # CRITICAL FIX: End memory monitoring for successful task
                    memory_monitor.end_task_monitoring(self.task_id, success=True)
                    return  # Success - exit retry loop

                except (CLIConnectionError, ConnectionError, TimeoutError) as e:
                    # These are transient errors - retry with exponential backoff
                    last_error = e

                if attempt < max_attempts:
                    # Check if it's a rate limit error (special handling)
                    if "rate limit" in str(e).lower() or "429" in str(e).lower():
                        wait_time = 60  # Rate limit gets longer wait
                    else:
                        wait_time = 2 ** (attempt - 1)  # Exponential: 1s, 2s, 4s

                    # Log retry attempt
                    with open(log_file_path, "a") as raw_log:
                        raw_log.write(
                            f"[RETRY] {type(e).__name__}: {e}. Waiting {wait_time}s before retry...\n"
                        )

                    for session in get_session():
                        crud.append_to_summary_log(
                            session,
                            self.task_id,
                            f"[retry] Attempt {attempt} failed, retrying in {wait_time}s",
                        )

                    await asyncio.sleep(wait_time)
                    continue
                else:
                    # Max attempts reached - fall through to error handling
                    break

                except (
                    ProcessError,
                    CLINotFoundError,
                    CLIJSONDecodeError,
                    MessageParseError,
                    ClaudeSDKError,
                ) as e:
                # These are permanent errors - don't retry
                last_error = e
                break

                except Exception as e:
                    # Unexpected error - don't retry
                    last_error = e
                    break

            # If we get here, task failed
            if last_error:
                duration = (datetime.utcnow() - start_time).total_seconds()

                # Log error with structured logger
                task_logger.log_error(last_error, "Task execution failed")

                # Handle error with ErrorHandler
                error_info = ErrorHandler.handle_error(
                    last_error, self.task_id, log_file_path
                )
                ErrorHandler.log_error(error_info, log_file_path)
                error_msg = ErrorHandler.format_error_message(error_info)

                if attempt >= max_attempts and isinstance(
                    last_error, (CLIConnectionError, ConnectionError, TimeoutError)
                ):
                    error_msg += f" | Failed after {max_attempts} attempts"

                # Log completion with failure status
                task_logger.log_task_completion(False, error_msg, duration)

                for session in get_session():
                    crud.finalize_task(
                        session, self.task_id, models.TaskStatus.FAILED, error_msg
                    )
                
                # CRITICAL FIX: End memory monitoring for failed task
                memory_monitor.end_task_monitoring(self.task_id, success=False)
        finally:
            # CRITICAL FIX: Always clean up task logger to prevent memory leak
            task_logger.close()

    async def _process_message(self, message: Message, task_logger) -> None:
        """
        Process individual messages from the SDK stream.
        Extracts relevant information and updates both structured and legacy logs.
        """
        summary_line = None

        # Process AssistantMessage with content blocks
        if isinstance(message, AssistantMessage) and message.content:
            for block in message.content:
                formatted = format_content_block(block)
                if formatted:
                    summary_line = formatted

                    # Enhanced logging for tool usage
                    if isinstance(block, ToolUseBlock):
                        task_logger.log_tool_usage(
                            tool_name=block.name,
                            tool_input=block.input,
                            success=True,  # We'll update this when we get the result
                        )
                    else:
                        # Log other types of progress
                        task_logger.log_task_progress(formatted, "SDK_MESSAGE")

                    break  # Log the first significant block

        # If we have something to log, update the database (legacy)
        if summary_line:
            for session in get_session():
                crud.append_to_summary_log(session, self.task_id, summary_line)
