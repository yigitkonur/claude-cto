# Claude Worker Error Handling Guide

## Overview

Claude Worker implements a comprehensive error handling system that provides detailed diagnostics, recovery suggestions, and debugging information for all Claude Code SDK error types. The new `ErrorHandler` class centralizes all error processing logic.

## Architecture

### Error Handler Module
The `claude_worker/server/error_handler.py` module provides:
- Centralized error handling for all SDK exceptions
- Structured error information with debugging context
- Recovery suggestions for each error type
- HTTP status code mappings
- Diagnostic helpers (Node.js detection, auth status, etc.)

### Error Flow
```
SDK Error → ErrorHandler.handle_error() → Structured Error Info
                                         ↓
                                    Log to File
                                         ↓
                                    Format Message
                                         ↓
                                    Store in Database
```

## Error Types and Examples

### 1. ProcessError
**When Occurs:** Claude CLI process exits with non-zero code

**Example Error:**
```
[ProcessError] Command failed (exit code: 127) | exit_code: 127 | meaning: Command not found | stderr: /bin/sh: claude: command not found | suggestion: Command not found - verify Claude CLI is in PATH
```

**Exit Codes:**
- `0` - Success
- `1` - General error
- `2` - Misuse of shell command
- `126` - Permission denied
- `127` - Command not found
- `128` - Invalid exit argument
- `130` - Terminated by Ctrl+C
- `255` - Exit status out of range

**Recovery Suggestions:**
- Exit 1: Check task logs for details
- Exit 2: Verify syntax and parameters
- Exit 126: Check file permissions
- Exit 127: Verify Claude CLI is in PATH
- Exit 130: Script was interrupted
- Others: Check task logs for detailed error information

### 2. CLINotFoundError
**When Occurs:** Claude CLI is not installed or not found in PATH

**Example Error:**
```
[CLINotFoundError] Claude Code not found: /usr/local/bin/claude | searched at: /usr/local/bin/claude | suggestion: Install Claude CLI: npm install -g @anthropic-ai/claude-code
```

**Debugging Information:**
- Node.js installation status
- NPM global path
- PATH directories
- Searched locations

**Recovery Suggestions:**
1. Install Claude CLI: `npm install -g @anthropic-ai/claude-code`
2. Verify installation: `claude --version`
3. Check PATH includes Claude CLI location
4. For local install: `export PATH="$HOME/node_modules/.bin:$PATH"`

### 3. CLIConnectionError
**When Occurs:** Cannot connect to Claude CLI process

**Example Error:**
```
[CLIConnectionError] Failed to connect to Claude Code | suggestion: Verify Claude CLI is working: claude --version
```

**Debugging Information:**
- Authentication status check
- Possible causes list
- Network connectivity hints

**Recovery Suggestions:**
1. Verify Claude CLI: `claude --version`
2. Check authentication: `claude auth status`
3. Re-authenticate: `claude auth login`
4. Check network connectivity
5. Restart Claude Worker server

### 4. CLIJSONDecodeError
**When Occurs:** Claude CLI returns malformed JSON

**Example Error:**
```
[CLIJSONDecodeError] Failed to decode JSON: {"incomplete":... | failed to parse: {"incomplete":... | suggestion: This may be a temporary issue - retry the task
```

**Debugging Information:**
- Problematic line preview (first 100 chars)
- Original JSON parsing error type
- Full line content in logs

**Recovery Suggestions:**
1. Retry the task (may be temporary)
2. Update Claude CLI: `npm update -g @anthropic-ai/claude-code`
3. Clear cache: `rm -rf ~/.claude/cache`
4. Report issue if persistent

### 5. MessageParseError
**When Occurs:** Cannot parse message structure from CLI

**Example Error:**
```
[MessageParseError] Failed to parse CLI message: Unknown message type: invalid_type | suggestion: Update Claude Code SDK: pip install --upgrade claude-code-sdk
```

**Debugging Information:**
- Raw data that failed to parse
- Data type information
- Message keys (if dict)

**Recovery Suggestions:**
1. Update SDK: `pip install --upgrade claude-code-sdk`
2. Check SDK/CLI version compatibility
3. Review task logs for message format
4. Report incompatibility issue

### 6. ClaudeSDKError
**When Occurs:** Generic SDK error (base class)

**Example Error:**
```
[ClaudeSDKError] SDK operation failed: Connection timeout | suggestion: Review the specific error message for details
```

**Recovery Suggestions:**
1. Review specific error message
2. Check Claude Code SDK documentation
3. Verify environment variables
4. Ensure task parameters are valid

## Error Information Structure

Each error handled by `ErrorHandler` returns a structured dictionary:

```python
{
    "task_id": 123,
    "error_type": "ProcessError",
    "error_message": "Command failed",
    "timestamp": "2024-01-20T10:30:00",
    "status_code": 500,  # HTTP status code
    
    # Type-specific fields
    "exit_code": 127,     # ProcessError only
    "stderr": "...",       # ProcessError only
    "cli_path": "...",     # CLINotFoundError only
    
    # Debugging information
    "debugging": {
        "exit_code_meaning": "Command not found",
        "likely_cause": "Claude CLI not in PATH",
        "node_installed": true,
        "npm_global_path": "/usr/local",
        "path_env": ["/usr/local/bin", ...],
        "auth_status": "Authenticated"
    },
    
    # Recovery guidance
    "recovery_suggestions": [
        "Install Claude CLI: npm install -g @anthropic-ai/claude-code",
        "Verify installation: claude --version",
        ...
    ],
    
    # Log information
    "log_file": "/path/to/task.log",
    "log_tail": "Last 20 lines of log...",
    "stack_trace": "..."  # For unexpected errors
}
```

## Log File Format

Error details are written to task log files with structured format:

```
============================================================
[ERROR] 2024-01-20T10:30:00
Type: ProcessError
Message: Command failed (exit code: 127)

Debugging Information:
  exit_code_meaning: Command not found
  likely_cause: Claude CLI command not found in PATH

Recovery Suggestions:
  1. Command not found - verify Claude CLI is in PATH
  2. Install with: npm install -g @anthropic-ai/claude-code

Stack Trace:
  (if available for unexpected errors)
============================================================
```

## Diagnostic Helpers

The ErrorHandler includes several diagnostic methods:

### Check Node.js Installation
```python
ErrorHandler._check_node_installed()  # Returns: bool
```

### Get NPM Global Path
```python
ErrorHandler._get_npm_global_path()  # Returns: "/usr/local" or None
```

### Check Authentication Status
```python
ErrorHandler._check_auth_status()  # Returns: "Authenticated" | "Not authenticated" | "Claude CLI not found"
```

### Get PATH Directories
```python
ErrorHandler._get_path_directories()  # Returns: ["/usr/local/bin", ...]
```

## Usage in Code

### Basic Error Handling
```python
from claude_worker.server.error_handler import ErrorHandler

try:
    # Task execution code
    async for message in query(prompt=prompt, options=options):
        # Process messages
        pass
        
except (ProcessError, CLINotFoundError, CLIConnectionError, 
        CLIJSONDecodeError, MessageParseError, ClaudeSDKError) as e:
    # Handle SDK errors with ErrorHandler
    error_info = ErrorHandler.handle_error(e, task_id, log_file_path)
    
    # Log detailed error information
    ErrorHandler.log_error(error_info, log_file_path)
    
    # Format error message for database
    error_msg = ErrorHandler.format_error_message(error_info)
    
    # Store in database
    crud.finalize_task(session, task_id, TaskStatus.FAILED, error_msg)
```

### Custom Error Processing
```python
# Get structured error information
error_info = ErrorHandler.handle_error(error, task_id)

# Access specific fields
if error_info['error_type'] == 'ProcessError':
    exit_code = error_info.get('exit_code')
    stderr = error_info.get('stderr')
    
# Use debugging information
debugging = error_info.get('debugging', {})
if not debugging.get('node_installed'):
    print("Node.js is required but not installed")

# Display recovery suggestions
for suggestion in error_info['recovery_suggestions']:
    print(f"• {suggestion}")
```

## Troubleshooting Guide

### Quick Diagnosis Steps

1. **Check Task Status:**
   ```bash
   claude-worker status <task_id>
   ```

2. **View Task Logs:**
   ```bash
   cat ~/.claude-worker/logs/task_<id>_raw.log
   ```

3. **Verify Claude CLI:**
   ```bash
   claude --version
   which claude
   ```

4. **Check Authentication:**
   ```bash
   # API Key method
   echo $ANTHROPIC_API_KEY
   
   # OAuth method
   claude auth status
   ```

5. **Test Claude CLI:**
   ```bash
   claude "Hello, test message"
   ```

### Common Issues and Solutions

| Issue | Error Type | Solution |
|-------|------------|----------|
| Claude CLI not found | CLINotFoundError | `npm install -g @anthropic-ai/claude-code` |
| Authentication failed | ProcessError (exit 2) | Set `ANTHROPIC_API_KEY` or run `claude auth login` |
| Permission denied | ProcessError (exit 126) | Check file permissions: `chmod +x <file>` |
| Command not found | ProcessError (exit 127) | Add Claude to PATH: `export PATH="$PATH:/path/to/claude"` |
| Network issues | CLIConnectionError | Check connectivity, firewall settings |
| JSON parsing failed | CLIJSONDecodeError | Update CLI: `npm update -g @anthropic-ai/claude-code` |
| Message format error | MessageParseError | Update SDK: `pip install --upgrade claude-code-sdk` |

### Environment Variables

```bash
# Authentication (choose one)
export ANTHROPIC_API_KEY="sk-ant-..."     # API Key method
# OR use OAuth (no env var needed)         # claude auth login

# Optional
export CLAUDE_WORKER_DB="~/.claude-worker/tasks.db"
export CLAUDE_WORKER_SERVER_URL="http://localhost:8000"
export CLAUDE_WORKER_LOG_DIR="~/.claude-worker/logs"
```

## Testing Error Handling

### Manual Testing
```python
# Test ProcessError
from claude_code_sdk._errors import ProcessError
error = ProcessError("Test", exit_code=127, stderr="not found")
info = ErrorHandler.handle_error(error, task_id=1)
print(info['recovery_suggestions'])

# Test CLINotFoundError
from claude_code_sdk._errors import CLINotFoundError
error = CLINotFoundError("Claude Code not found", cli_path="/usr/bin/claude")
info = ErrorHandler.handle_error(error, task_id=2)
print(info['debugging'])
```

### Verify Error Handling
```python
# Run this to test all error types
from claude_worker.server.error_handler import ErrorHandler
from claude_code_sdk._errors import *

errors = [
    ProcessError('Test', exit_code=1),
    CLINotFoundError('Not found'),
    CLIConnectionError('Connection failed'),
    CLIJSONDecodeError('Bad JSON', ValueError()),
    MessageParseError('Parse failed'),
    ClaudeSDKError('Generic error')
]

for error in errors:
    info = ErrorHandler.handle_error(error, task_id=1)
    print(f"{info['error_type']}: {info['recovery_suggestions'][0]}")
```

## Best Practices

1. **Always use ErrorHandler for SDK errors** - Don't handle errors manually
2. **Log to both file and database** - Ensures visibility in UI and logs
3. **Include context in error messages** - Task ID, timestamp, etc.
4. **Provide actionable recovery suggestions** - Tell users exactly what to do
5. **Preserve debugging information** - Include all available error attributes
6. **Use appropriate HTTP status codes** - 502 for gateway errors, 503 for service unavailable
7. **Test error scenarios** - Verify error handling works as expected

## See Also

- [Error Handler Source Code](../claude_worker/server/error_handler.py)
- [Task Executor Implementation](../claude_worker/server/executor.py)
- [Claude Code SDK Documentation](https://github.com/anthropics/claude-code-sdk-python)
- [Claude CLI Documentation](https://docs.anthropic.com/en/docs/claude-cli)