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
    Core task execution engine: orchestrates complete lifecycle from SDK call to database finalization.
    Bridges the gap between HTTP requests and Claude SDK with robust error handling and status tracking.
    Critical for system reliability - handles transient errors, resource cleanup, and monitoring integration.
    """

    def __init__(self, task_id: int):
        """
        Lightweight constructor: stores task ID without heavyweight resource acquisition.
        Defers database sessions and file handles until execution to support async context switching.
        """
        # Task identifier: primary key for status tracking and resource association
        self.task_id = task_id

    async def run(self) -> None:
        """
        Complete task execution orchestration: SDK call → status tracking → resource cleanup.
        Implements retry logic for transient failures while maintaining database state consistency.
        Critical path that determines task success/failure and triggers dependent task scheduling.
        """
        # SDK process identification: marks subprocess calls for telemetry and debugging
        os.environ["CLAUDE_CODE_ENTRYPOINT"] = "sdk-py"

        # Database state transition: PENDING → RUNNING with process tracking
        # Critical for orchestration dependency resolution and monitoring systems
        for session in get_session():
            task_record = crud.get_task(session, self.task_id)
            if not task_record:
                return  # Task deleted or corrupted - abort silently

            # Atomic status transition: marks task as actively executing with process metadata
            task_record.status = models.TaskStatus.RUNNING
            task_record.pid = os.getpid()  # Process tracking for kill operations
            task_record.started_at = datetime.utcnow()  # Execution timestamp for duration calculations
            session.add(task_record)
            session.commit()

            # Task parameter extraction: copies data out of session scope for async processing
            working_directory = task_record.working_directory
            system_prompt = task_record.system_prompt
            execution_prompt = task_record.execution_prompt
            log_file_path = task_record.log_file_path
            model = task_record.model

        # Claude SDK configuration: assembles execution context with security bypass
        # bypassPermissions: eliminates user prompts for autonomous task execution
        options = ClaudeCodeOptions(
            cwd=working_directory,  # File system sandbox boundary
            system_prompt=system_prompt,  # Behavioral constraints and persona
            model=model,  # AI model selection (haiku/sonnet/opus)
            permission_mode="bypassPermissions",  # Critical: enables headless execution
        )

        # Model-specific timeout matrix: prevents hung tasks while accommodating model complexity
        # Higher intelligence models get longer timeouts for complex reasoning tasks
        timeout_seconds = {
            "haiku": 600,   # 10 minutes - fast model, simple tasks
            "sonnet": 1800, # 30 minutes - balanced model, standard timeout
            "opus": 3600,   # 60 minutes - complex model, extended reasoning
        }.get(model.value, 1800)  # Default to sonnet timeout for unknown models

        # Resource initialization: establishes monitoring and logging infrastructure
        # Critical for debugging failed tasks and preventing resource leaks
        task_logger = create_task_logger(self.task_id, working_directory)  # Structured logging
        memory_monitor = get_memory_monitor()  # System resource tracking
        memory_monitor.start_task_monitoring(self.task_id)  # Begin resource monitoring

        # Retry orchestration: implements exponential backoff for transient failures only
        # Distinguishes between recoverable network issues and permanent configuration errors
        max_attempts = 3  # Conservative retry count to prevent infinite loops
        attempt = 0
        last_error = None
        start_time = datetime.utcnow()  # Execution duration tracking
        
        # Open raw log file once for entire execution lifetime
        # Critical: Must remain open throughout all retry attempts and async operations
        raw_log = None
        try:
            raw_log = open(log_file_path, "a")
            
            while attempt < max_attempts:
                attempt += 1

                try:
                    # Structured logging initialization: captures task parameters for debugging
                    if attempt == 1:
                        # First attempt: log complete task context for troubleshooting
                        task_logger.log_task_start(
                            execution_prompt=execution_prompt,
                            model=model.value,
                            system_prompt=system_prompt,
                        )
                    else:
                        # Retry attempt: log error context and retry progression
                        task_logger.log_task_progress(
                            f"Retry attempt {attempt}/{max_attempts} after error: {last_error}",
                            "RETRY",
                        )

                    # Legacy log compatibility: maintains backward compatibility with existing log parsing
                    # Raw log format preserved for external monitoring tools and manual debugging
                    if attempt > 1:
                        # Retry header: clearly marks retry attempts for log analysis
                        raw_log.write(f"[RETRY] Attempt {attempt}/{max_attempts}\n")
                    else:
                        # Initial execution metadata: comprehensive context for debugging
                        raw_log.write(f"[INFO] Starting task {self.task_id}\n")
                        raw_log.write(f"[INFO] Working directory: {working_directory}\n")
                        raw_log.write(f"[INFO] Prompt: {execution_prompt}\n")
                        raw_log.write(f"[INFO] System prompt: {system_prompt}\n")
                        raw_log.write(f"[INFO] Timeout: {timeout_seconds}s\n")
                    raw_log.flush()  # Immediate disk write for crash resilience

                    # Core SDK execution: streams messages from Claude with real-time processing
                    # Message processing maintains database state and structured logs throughout execution
                    message_count = 0  # Conversation turn counter for completion metrics

                    async def execute_query():
                        """Async generator wrapper: processes SDK message stream with logging and state updates"""
                        nonlocal message_count
                        # Claude SDK query: main AI interaction with streaming response processing
                        async for message in query(prompt=execution_prompt, options=options):
                            message_count += 1
                            # Real-time progress logging: timestamps each message for performance analysis
                            raw_log.write(
                                f"[{datetime.utcnow().isoformat()}] Message {message_count}: {type(message).__name__}\n"
                            )
                            raw_log.flush()

                            # Message processing pipeline: extracts actionable data and updates task state
                            await self._process_message(message, task_logger)
                        return message_count

                    # Timeout enforcement: prevents hung tasks from consuming resources indefinitely
                    # Critical for system stability - terminates runaway AI interactions
                    try:
                        await asyncio.wait_for(execute_query(), timeout=timeout_seconds)
                    except asyncio.TimeoutError:
                        # Transform asyncio timeout to standard timeout for consistent error handling
                        raise TimeoutError(f"Task exceeded {timeout_seconds}s timeout")

                    # Successful completion logging: records final metrics and status
                    raw_log.write(f"[INFO] Task completed with {message_count} messages\n")
                    if attempt > 1:
                        raw_log.write(f"[INFO] Succeeded after {attempt} attempts\n")
                    raw_log.flush()

                    # Success metrics calculation: duration and message count for performance analysis
                    duration = (datetime.utcnow() - start_time).total_seconds()
                    success_msg = f"Task completed successfully ({message_count} messages)"
                    if attempt > 1:
                        success_msg += f" after {attempt} attempts"  # Retry success indicator

                    # Completion logging: structured format for monitoring and analytics
                    task_logger.log_task_completion(True, success_msg, duration)

                    # Database finalization: atomic status transition to COMPLETED with summary
                    for session in get_session():
                        crud.finalize_task(session, self.task_id, models.TaskStatus.COMPLETED, success_msg)

                    # Resource cleanup: stops monitoring and releases task-specific resources
                    memory_monitor.end_task_monitoring(self.task_id, success=True)
                    return  # Success path: exit retry loop and complete execution

                except (CLIConnectionError, ConnectionError, TimeoutError) as e:
                    # Transient error recovery: network issues and timeouts warrant retry with backoff
                    # Prevents cascading failures from temporary service disruptions
                    last_error = e

                    if attempt < max_attempts:
                        # Rate limiting detection: API quota errors need extended delay
                        if "rate limit" in str(e).lower() or "429" in str(e).lower():
                            wait_time = 60  # Rate limit recovery: longer wait for quota reset
                        else:
                            wait_time = 2 ** (attempt - 1)  # Exponential backoff: 1s, 2s, 4s

                        # Retry logging: records attempt progression for debugging
                        raw_log.write(f"[RETRY] {type(e).__name__}: {e}. Waiting {wait_time}s before retry...\n")
                        raw_log.flush()

                        # Database retry tracking: maintains retry history for monitoring
                        for session in get_session():
                            crud.append_to_summary_log(
                                session,
                                self.task_id,
                                f"[retry] Attempt {attempt} failed, retrying in {wait_time}s",
                            )

                        # Backoff delay: prevents overwhelming failing services
                        await asyncio.sleep(wait_time)
                        continue  # Retry loop continuation
                    else:
                        # Retry exhaustion: all attempts failed, proceed to error handling
                        break

                except (
                    ProcessError,
                    CLINotFoundError,
                    CLIJSONDecodeError,
                    MessageParseError,
                    ClaudeSDKError,
                ) as e:
                    # Permanent error identification: configuration and parsing issues are non-recoverable
                    # Prevents infinite retry loops on systematic problems (missing CLI, auth failures, etc.)
                    last_error = e
                    break  # Immediate failure path - no retry attempts

                except Exception as e:
                    # Unknown error classification: treats unexpected exceptions as permanent failures
                    # Conservative approach prevents retry storms on unknown error conditions
                    last_error = e
                    break  # Safety break - unknown errors are not retried

            # Failure path execution: processes all error conditions with comprehensive logging
            # Critical for debugging, monitoring, and user feedback on task failures
            if last_error:
                duration = (datetime.utcnow() - start_time).total_seconds()

                # Error logging: structured format for automated analysis and debugging
                task_logger.log_error(last_error, "Task execution failed")

                # Comprehensive error processing: generates debugging information and recovery suggestions
                error_info = ErrorHandler.handle_error(last_error, self.task_id, log_file_path)
                
                # Write error info through existing raw_log handle to avoid file conflicts
                raw_log.write(f"\n{'='*60}\n")
                raw_log.write(f"[ERROR] {error_info['timestamp']}\n")
                raw_log.write(f"Type: {error_info['error_type']}\n")
                raw_log.write(f"Message: {error_info['error_message']}\n")
                raw_log.write(f"\nRecovery Suggestions:\n")
                for i, suggestion in enumerate(error_info['recovery_suggestions'], 1):
                    raw_log.write(f"  {i}. {suggestion}\n")
                if error_info.get('stack_trace'):
                    raw_log.write(f"\nStack Trace:\n{error_info['stack_trace']}\n")
                raw_log.write(f"{'='*60}\n\n")
                raw_log.flush()
                
                error_msg = ErrorHandler.format_error_message(error_info)  # User-friendly summary

                # Retry exhaustion indicator: clarifies failure after multiple attempts
                if attempt >= max_attempts and isinstance(
                    last_error, (CLIConnectionError, ConnectionError, TimeoutError)
                ):
                    error_msg += f" | Failed after {max_attempts} attempts"

                # Failure completion logging: records final status with error details
                task_logger.log_task_completion(False, error_msg, duration)

                # Database failure finalization: atomic status transition to FAILED with error message
                for session in get_session():
                    crud.finalize_task(session, self.task_id, models.TaskStatus.FAILED, error_msg)

                # Failed task cleanup: stops monitoring and releases resources
                memory_monitor.end_task_monitoring(self.task_id, success=False)
        finally:
            # Critical resource cleanup: prevents file handle leaks and memory accumulation
            # MUST execute regardless of success/failure to maintain system stability
            if raw_log:
                raw_log.close()  # Close raw log file handle to prevent resource leak
            task_logger.close()  # Closes file handlers and releases structured logging resources

    async def _process_message(self, message: Message, task_logger) -> None:
        """
        Message stream processor: extracts actionable data from Claude SDK responses.
        Maintains real-time status updates and structured logging throughout task execution.
        Critical for progress tracking and debugging failed or stuck tasks.
        """
        summary_line = None

        # AssistantMessage processing: extracts meaningful content from AI responses
        # Content blocks contain tool usage, text responses, and system interactions
        if isinstance(message, AssistantMessage) and message.content:
            for block in message.content:
                # Content formatting: converts SDK blocks to human-readable strings
                formatted = format_content_block(block)
                if formatted:
                    summary_line = formatted

                    # Tool usage tracking: monitors AI agent actions for debugging and metrics
                    if isinstance(block, ToolUseBlock):
                        task_logger.log_tool_usage(
                            tool_name=block.name,  # Tool identifier (bash, edit, read, etc.)
                            tool_input=block.input,  # Tool parameters for debugging
                            success=True,  # Optimistic success (updated on tool response)
                        )
                    else:
                        # General progress logging: captures AI reasoning and status updates
                        task_logger.log_task_progress(formatted, "SDK_MESSAGE")

                    break  # First significant block: prevents log spam from verbose responses

        # Legacy database integration: maintains backward compatibility with existing log consumers
        # Real-time status updates enable progress tracking and dependency resolution
        if summary_line:
            for session in get_session():
                # Summary log update: appends latest progress to database for external monitoring
                crud.append_to_summary_log(session, self.task_id, summary_line)
