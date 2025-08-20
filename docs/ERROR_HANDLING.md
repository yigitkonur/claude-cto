# Claude Worker Error Handling Guide

## Overview

Claude Worker implements comprehensive error handling for all Claude Code SDK error types, providing detailed diagnostic information and actionable recovery suggestions.

## Error Types and Handling

### 1. CLINotFoundError

**When it occurs:** Claude CLI is not installed or not in PATH

**Error message format:**
```
Claude CLI not found: <details>. Please install Claude CLI and ensure it's in your PATH.
```

**Resolution:**
- Install Claude CLI from https://docs.anthropic.com/en/docs/claude-cli
- Ensure `claude` command is in your PATH
- Verify with: `claude --version`

### 2. CLIConnectionError

**When it occurs:** Unable to connect to Claude CLI process

**Error message format:**
```
Failed to connect to Claude CLI: <details>. Check if Claude CLI is working with 'claude --version'. | Suggestion: Run 'claude --version' to verify CLI installation
```

**Resolution:**
- Verify Claude CLI is working: `claude --version`
- Check authentication: `claude login` (for OAuth) or set `ANTHROPIC_API_KEY`
- Restart Claude Worker server if needed

### 3. ProcessError

**When it occurs:** Claude CLI process exits with non-zero code

**Error message format:**
```
Process error: <message> | exit_code: <code> | stderr: <error_output>
```

**Resolution:**
- Check the specific exit code and stderr output
- Common codes:
  - Exit 1: General CLI error
  - Exit 2: Authentication error
  - Exit 3: Permission denied

### 4. CLIJSONDecodeError

**When it occurs:** Claude CLI returns malformed JSON output

**Error message format:**
```
Failed to parse CLI JSON output: <details>. Line: '<problematic_content>...'
```

**Additional logging:**
- Original parsing error
- Full problematic line content

**Resolution:**
- Usually indicates CLI version mismatch
- Update Claude CLI to latest version
- Check if CLI output is corrupted

### 5. MessageParseError

**When it occurs:** Unable to parse message structure from CLI

**Error message format:**
```
Failed to parse CLI message: <details> | Data: <raw_data>
```

**Additional logging:**
- Raw message data that failed to parse

**Resolution:**
- Check CLI version compatibility
- Verify message format expectations
- Report issue if persistent

### 6. ClaudeSDKError (General)

**When it occurs:** Any other SDK-related error

**Error message format:**
```
SDK error: <details> | Type: <ErrorClassName>
```

**Resolution:**
- Check specific error type for targeted solution
- Verify Claude Code SDK version compatibility

## Error Logging

All errors are logged with comprehensive details:

### Database Storage
- Error message with full diagnostic information
- Error type classification
- Timestamp and task context

### Log Files
- Located in `~/.claude-worker/logs/`
- Individual task logs: `task_<id>_raw.log`
- Contains:
  - Full error messages
  - Stack traces (for unexpected errors)
  - Diagnostic suggestions
  - Raw error data

## Troubleshooting Steps

### For Authentication Errors
1. Check authentication method:
   ```bash
   # API Key method
   echo $ANTHROPIC_API_KEY
   
   # OAuth method  
   claude whoami
   ```

2. Re-authenticate if needed:
   ```bash
   # For OAuth
   claude login
   
   # For API Key
   export ANTHROPIC_API_KEY="your-key"
   ```

### For CLI Issues
1. Verify CLI installation:
   ```bash
   claude --version
   which claude
   ```

2. Test CLI functionality:
   ```bash
   claude "Hello, Claude!"
   ```

3. Check PATH configuration:
   ```bash
   echo $PATH | grep claude
   ```

### For Task Failures
1. Check task status with detailed error:
   ```bash
   claude-worker status <task_id>
   ```

2. Review task logs:
   ```bash
   cat ~/.claude-worker/logs/task_<id>_raw.log
   ```

3. Check server logs:
   ```bash
   claude-worker server health
   ```

## Error Recovery

### Automatic Recovery
- Connection errors are logged with diagnostic suggestions
- Transient errors include retry recommendations
- Critical errors provide installation guides

### Manual Recovery
1. **Authentication failures:** Re-authenticate and retry
2. **CLI not found:** Install Claude CLI and restart server
3. **JSON parsing errors:** Update CLI version
4. **Process errors:** Check specific exit code and stderr

## Development Notes

### Adding New Error Handling
1. Import error type from `claude_code_sdk._errors`
2. Add specific exception handler in executors
3. Include diagnostic information and suggestions
4. Update error logging with relevant details
5. Test error scenario and verify output

### Error Logging Format
```python
with open(log_file_path, 'a') as f:
    f.write(f"[ERROR] {ErrorType}: {detailed_message}\n")
    f.write(f"[ERROR] Additional context: {context_info}\n")
```

## See Also

- [Claude CLI Documentation](https://docs.anthropic.com/en/docs/claude-cli)
- [Claude Worker Configuration](05-administration-configuration.md)
- [Troubleshooting Guide](troubleshooting.md)