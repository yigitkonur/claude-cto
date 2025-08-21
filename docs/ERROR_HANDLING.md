# Claude Worker Error Handling Guide (Actual Implementation)

## Overview

This document describes the **actual error handling system** currently implemented in Claude Worker v0.4.0. The system provides comprehensive error handling for all Claude Code SDK error types with debugging information, recovery suggestions, and simple retry logic.

## Architecture

### Core Components

#### 1. `server/error_handler.py` - Central Error Handler
The heart of the error handling system. Provides:
- Transient vs permanent error classification
- Structured error information with debugging context
- Recovery suggestions for each error type
- HTTP status code mappings
- Diagnostic helpers (Node.js detection, auth status, PATH analysis)

#### 2. `server/executor.py` - Task Executor with Retry Logic
Implements a simple but effective retry mechanism:
- 3 attempts for transient errors
- Exponential backoff (1s, 2s, 4s)
- Special handling for rate limits (60s wait)
- Inline retry logic (no separate retry handler)

#### 3. `server/task_logger.py` - Structured Logging
Provides multi-level logging:
- Summary logs (concise, emoji-enhanced)
- Detailed logs (full content, stack traces)
- Global summary log
- Directory context in filenames

## Error Types and Handling

### 1. CLINotFoundError
**Classification:** Permanent (no retry)  
**HTTP Status:** 503 (Service Unavailable)  
**Debugging Information:**
- Node.js installation status
- NPM global path
- PATH directories
- CLI search location

**Recovery Suggestions:**
```
1. Install Claude CLI: npm install -g @anthropic-ai/claude-code
2. Verify installation: claude --version
3. Check PATH environment variable includes Claude CLI location
4. For local install: export PATH="$HOME/node_modules/.bin:$PATH"
```

### 2. CLIConnectionError
**Classification:** Transient (will retry)  
**HTTP Status:** 502 (Bad Gateway)  
**Debugging Information:**
- Authentication status
- Possible causes list

**Recovery Suggestions:**
```
1. Verify Claude CLI: claude --version
2. Check authentication: claude auth status
3. Re-authenticate: claude auth login
4. Check network connectivity
5. Restart Claude Worker server
```

### 3. ProcessError
**Classification:** Mixed (depends on exit code and stderr)  
**HTTP Status:** 500 (Internal Server Error)  
**Transient Conditions:**
- Exit codes: 124 (timeout), 137 (SIGKILL), 143 (SIGTERM)
- Stderr contains: "timeout", "connection", "network", "rate limit"

**Exit Code Meanings:**
- 0: Success
- 1: General error
- 2: Misuse of shell command
- 126: Permission denied
- 127: Command not found
- 128: Invalid exit argument
- 130: Script terminated by Ctrl+C
- 255: Exit status out of range

### 4. CLIJSONDecodeError
**Classification:** Mixed (can be transient)  
**HTTP Status:** 502 (Bad Gateway)  
**Transient Conditions:**
- Original error contains "timeout" or "connection"
- Message contains "incomplete" or "truncated"

**Recovery Suggestions:**
```
1. Retry the task (may be temporary)
2. Update Claude CLI: npm update -g @anthropic-ai/claude-code
3. Clear cache: rm -rf ~/.claude/cache
4. Report issue if persistent
```

### 5. MessageParseError
**Classification:** Permanent (no retry)  
**HTTP Status:** 502 (Bad Gateway)  
**Debugging Information:**
- Raw data that failed to parse
- Data type and keys (if dict)

**Recovery Suggestions:**
```
1. Update SDK: pip install --upgrade claude-code-sdk
2. Check SDK/CLI version compatibility
3. Review task logs for message format
4. Report incompatibility issue
```

### 6. ClaudeSDKError
**Classification:** Permanent (base class fallback)  
**HTTP Status:** 500 (Internal Server Error)  
**Recovery Suggestions:**
```
1. Review specific error message
2. Check Claude Code SDK documentation
3. Verify environment variables
4. Ensure task parameters are valid
```

## Retry Logic Implementation

### Current Implementation in `server/executor.py`

```python
# Simple retry logic with exponential backoff
max_attempts = 3
attempt = 0
last_error = None

while attempt < max_attempts:
    attempt += 1
    
    try:
        # Execute query
        async for message in query(prompt=execution_prompt, options=options):
            # Process messages
            pass
        return  # Success
        
    except (CLIConnectionError, ConnectionError, TimeoutError) as e:
        # Transient errors - retry with backoff
        last_error = e
        
        if attempt < max_attempts:
            # Special handling for rate limits
            if "rate limit" in str(e).lower():
                wait_time = 60  # Longer wait for rate limits
            else:
                wait_time = 2 ** (attempt - 1)  # Exponential: 1s, 2s, 4s
            
            await asyncio.sleep(wait_time)
            continue
        else:
            break  # Max attempts reached
            
    except (ProcessError, CLINotFoundError, CLIJSONDecodeError, 
            MessageParseError, ClaudeSDKError) as e:
        # Permanent errors - don't retry
        last_error = e
        break
```

### Transient Error Detection

The `ErrorHandler.is_transient_error()` method uses sophisticated logic:

```python
@classmethod
def is_transient_error(cls, error: Exception) -> bool:
    # Connection/timeout errors are transient
    if isinstance(error, (CLIConnectionError, ConnectionError, 
                          TimeoutError, asyncio.TimeoutError)):
        return True
    
    # Rate limiting is transient
    if "rate limit" in str(error).lower() or "429" in str(error).lower():
        return True
    
    # CLIJSONDecodeError can be transient (network corruption)
    if isinstance(error, CLIJSONDecodeError):
        if "incomplete" in str(error).lower():
            return True
    
    # ProcessError - check exit codes and stderr
    if isinstance(error, ProcessError):
        if error.exit_code in [124, 137, 143]:  # Timeout/kill signals
            return True
        if error.stderr and any(word in error.stderr.lower() 
                               for word in ["timeout", "network"]):
            return True
        return False  # Most ProcessErrors are permanent
    
    # Explicitly permanent errors
    if isinstance(error, (CLINotFoundError, MessageParseError)):
        return False
    
    return False  # Default to permanent
```

## Error Information Structure

Each error handled by `ErrorHandler.handle_error()` returns:

```python
{
    "task_id": 123,
    "error_type": "ProcessError",
    "error_message": "Command failed",
    "timestamp": "2024-01-20T10:30:00Z",
    "status_code": 500,
    
    # Type-specific fields
    "exit_code": 127,           # ProcessError only
    "stderr": "command not found",  # ProcessError only
    "cli_path": "/usr/bin/claude",  # CLINotFoundError only
    "problematic_line": "...",      # CLIJSONDecodeError only
    "parse_data": {...},             # MessageParseError only
    
    # Debugging information
    "debugging": {
        "exit_code_meaning": "Command not found",
        "likely_cause": "Claude CLI not in PATH",
        "node_installed": true,
        "npm_global_path": "/usr/local",
        "path_env": ["/usr/bin", "/usr/local/bin"],
        "auth_status": "Authenticated"
    },
    
    # Recovery guidance
    "recovery_suggestions": [
        "Install Claude CLI...",
        "Verify installation...",
    ],
    
    # Log information
    "log_file": "/path/to/task.log",
    "log_tail": "Last 20 lines..."
}
```

## Logging System

### Dual Logging Approach (Current)

The system currently uses **both** structured and raw logging:

1. **Structured Logs** (`TaskLogger`):
   - `~/.claude-worker/tasks/task_<id>_<context>_<timestamp>_summary.log`
   - `~/.claude-worker/tasks/task_<id>_<context>_<timestamp>_detailed.log`
   - `~/.claude-worker/claude-worker.log` (global)

2. **Raw Logs** (Legacy):
   - Direct writes to `log_file_path` in executor
   - Simple text format
   - Includes retry attempts and timing

### Log File Naming

Files include directory context for clarity:
```
task_1_myproject_20250821_1429_summary.log
task_2_webapp_src_20250821_1430_detailed.log
```

## Diagnostic Helpers

The `ErrorHandler` includes several diagnostic methods:

### `_check_node_installed()`
Checks if Node.js is available in the system.

### `_get_npm_global_path()`
Returns the npm global installation path.

### `_check_auth_status()`
Runs `claude auth status` to check authentication.

### `_get_path_directories()`
Returns all directories in the system PATH.

### `_get_log_tail()`
Extracts the last N lines from a log file for error context.

## Error Handling Flow

```
Task Execution
    ↓
Try Query Execution
    ↓
Exception Caught
    ↓
Check if Transient (ErrorHandler.is_transient_error)
    ├─ Yes: Retry with exponential backoff
    │   └─ Max attempts? → Fail
    └─ No: Immediate failure
        ↓
ErrorHandler.handle_error()
    ├─ Extract error details
    ├─ Add debugging info
    ├─ Generate recovery suggestions
    └─ Log to file
        ↓
Store in Database with error_message
```

## Current Capabilities & Limitations

### ✅ Implemented Features
1. **Circuit Breaker** - Available in `retry_handler.py` (not yet integrated in executor)
2. **Memory Monitoring** - Available in `memory_monitor.py` (not yet integrated in server)
3. **Error Metrics** - Available in `error_codes.py` with `ErrorMetrics` class
4. **Advanced Retry Strategies** - Available in `retry_handler.py` (exponential, linear, fibonacci)
5. **Correlation IDs** - Available in `error_codes.py` with `ErrorContext` class

### ⚠️ Integration Pending
1. **Circuit Breaker Integration** - Code exists but executor uses simple retry
2. **Memory Monitor Integration** - Code exists but not in server lifespan
3. **Advanced Retry Integration** - Code exists but executor uses simple logic

### ❌ Not Yet Implemented
1. **Distributed Tracing** - No OpenTelemetry integration
2. **External Error Reporting** - No Sentry/Rollbar integration

## Areas for Improvement

### Short Term
1. **Unify Error Handling**: `core/executor.py` should use `ErrorHandler`
2. **Remove Dual Logging**: Consolidate on structured `TaskLogger`
3. **Add Error Metrics**: Track error rates and patterns

### Medium Term
1. **Circuit Breaker**: Prevent cascading failures
2. **Correlation IDs**: Enable request tracing
3. **Memory Monitoring**: Track resource usage

### Long Term
1. **Distributed Tracing**: OpenTelemetry integration
2. **Advanced Retry Strategies**: Per-error-type configurations
3. **Error Reporting**: Sentry/Rollbar integration

## Usage Examples

### Handling Errors in Code

```python
from claude_worker.server.error_handler import ErrorHandler

try:
    # Task execution
    async for message in query(prompt, options):
        process_message(message)
        
except Exception as e:
    # Use ErrorHandler for rich error info
    error_info = ErrorHandler.handle_error(e, task_id, log_file)
    
    # Log detailed error
    ErrorHandler.log_error(error_info, log_file)
    
    # Format for database
    error_msg = ErrorHandler.format_error_message(error_info)
    
    # Store in database
    crud.finalize_task(session, task_id, TaskStatus.FAILED, error_msg)
```

### Checking Transient Errors

```python
if ErrorHandler.is_transient_error(error):
    # Retry with backoff
    await asyncio.sleep(2 ** attempt)
else:
    # Fail immediately
    raise
```

## Testing Error Handling

### Test Transient Classification
```python
from claude_code_sdk._errors import CLIConnectionError, ProcessError

# Should be transient
assert ErrorHandler.is_transient_error(CLIConnectionError("test"))
assert ErrorHandler.is_transient_error(TimeoutError("test"))

# Should be permanent
assert not ErrorHandler.is_transient_error(CLINotFoundError("test"))
assert not ErrorHandler.is_transient_error(MessageParseError("test"))

# ProcessError depends on details
error = ProcessError("test", exit_code=124)  # Timeout
assert ErrorHandler.is_transient_error(error)

error = ProcessError("test", exit_code=1)  # General error
assert not ErrorHandler.is_transient_error(error)
```

## Environment Variables

```bash
# Authentication (choose one)
export ANTHROPIC_API_KEY="sk-ant-..."
# OR use OAuth: claude auth login

# Optional
export CLAUDE_WORKER_DB="~/.claude-worker/tasks.db"
export CLAUDE_WORKER_SERVER_URL="http://localhost:8000"
export CLAUDE_WORKER_LOG_DIR="~/.claude-worker/logs"
```

## Troubleshooting

### Common Issues

| Issue | Error Type | Solution |
|-------|------------|----------|
| Claude CLI not found | CLINotFoundError | Install: `npm install -g @anthropic-ai/claude-code` |
| Auth failed | ProcessError (exit 2) | Set `ANTHROPIC_API_KEY` or `claude auth login` |
| Permission denied | ProcessError (exit 126) | Check file permissions |
| Network issues | CLIConnectionError | Check connectivity, retry |
| JSON parsing | CLIJSONDecodeError | Update CLI, retry |

---

*This document reflects the actual implementation as of Claude Worker v0.4.0*
*Last Updated: 2025-08-21*