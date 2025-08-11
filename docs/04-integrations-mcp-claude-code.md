# MCP Integration with Claude Code

Claude Worker provides seamless integration with Claude Code through the Model Context Protocol (MCP), enabling a powerful "CTO + Development Team" workflow where Claude Code acts as the architect and Claude Worker handles parallel task execution.

## The Error-Driven Optimization System

Claude Worker's MCP integration uses **strategic validation errors** to train AI agents to write better, more actionable prompts. This isn't just validation—it's a prompt engineering training system.

### Why Strategic Errors Work

When Claude Code receives validation errors, it automatically refines its prompts to be more specific and actionable. This creates a feedback loop that improves task quality over time.

| Validation Rule | Purpose | Before → After |
|----------------|---------|----------------|
| **150+ characters** | Forces detailed context | "Fix bug" → "Fix JWT expiration bug in ./src/auth/login.js by updating token validation logic" |
| **Path requirement** | Ensures concrete actions | "Add tests" → "Add unit tests in ./tests/auth.test.js for login functionality" |
| **System prompt constraint*** | Enforces minimalist approach | Auto-adds focus on simple, surgical solutions |

> ***The "John Carmack" requirement is a [clever prompt engineering hack](https://x.mattshumer.ai/status/1921276852200477114) that works because LLMs associate this name with minimalist, elegant code. It's hardcoded behavior modification, not philosophy worship!**

## Installation

### One-Command Setup

```bash
# Install and register with Claude Code
pip install "claude-worker[mcp]" && \
claude mcp add claude-worker -s user -- python -m claude_worker.mcp.factory
```

### Verification

```bash
# Check installation
claude mcp list
# Should show: claude-worker ✓ Connected

# Test connection
claude mcp get claude-worker
```

## Available MCP Tools

### `create_task` - Task Delegation

Submit fire-and-forget tasks to the worker pool.

**Parameters:**
- `execution_prompt` (string, required): Task description (min 150 characters)
- `working_directory` (string, optional): Execution context (default: ".")
- `system_prompt` (string, optional): Custom system prompt (must contain minimalist keyword)

**Smart Validation:**
```python
# Enforces detailed prompts
if len(execution_prompt) < 150:
    return {"error": "Execution prompt must be at least 150 characters"}

# Requires path context  
if '/' not in execution_prompt and '\\' not in execution_prompt:
    return {"error": "Execution prompt must contain a path-like string"}
```

### `get_task_status` - Progress Monitor

Check real-time task status and progress.

**Parameters:**
- `task_id` (number, required): Task identifier

**Returns:**
```json
{
  "id": 4,
  "status": "completed",
  "started_at": "2025-08-11T09:16:11.231488",
  "ended_at": "2025-08-11T09:16:23.522729", 
  "last_action": "[tool:write] ./src/component.js",
  "final_summary": "Task completed successfully (6 messages)"
}
```

### `list_tasks` - Team Dashboard

View recent task history and status overview.

**Parameters:**
- `limit` (number, optional): Maximum results (default: 10)
- `status` (string, optional): Filter by status (standalone mode only)

### `check_api_health` - System Health

Verify backend connectivity and system status.

**Returns:**
```json
{
  "status": "healthy",
  "api_url": "http://localhost:8000",
  "service": "claude-worker"
}
```

### `get_task_logs` - Detailed Execution

Get full execution logs for debugging (standalone mode only).

**Parameters:**
- `task_id` (number, required): Task identifier

## Architecture Modes

Claude Worker automatically detects your environment and selects the optimal mode:

### 🪶 Lightweight Mode (Standalone)
- **When**: No REST API server running
- **Features**: Direct execution, embedded SQLite, single process
- **Best for**: Individual developers, simple workflows

### 🏢 Production Mode (Proxy) 
- **When**: REST API server available at localhost:8000
- **Features**: Process pool, shared database, horizontal scaling
- **Best for**: Teams, high-volume tasks, production deployments

**Auto-Detection Logic:**
```python
if is_rest_api_available():
    mode = "proxy"      # Use centralized server
else:
    mode = "standalone" # Direct execution
```

## Usage Patterns

### Pattern 1: Parallel Development

Use Claude Code as "CTO" for planning, Claude Worker as "dev team" for execution:

```javascript
// In Claude Code - coordinate multiple tasks
const auth = create_task(
  "Implement JWT authentication in ./src/auth/login.js with bcrypt hashing, token validation, and proper error handling for invalid credentials.",
  "./my-project"
);

const tests = create_task(
  "Create comprehensive unit tests in ./tests/auth.test.js covering login success, invalid credentials, token expiration, and edge cases.",
  "./my-project"  
);

const docs = create_task(
  "Generate API documentation in ./docs/auth.md explaining authentication endpoints, request/response formats, and security considerations.",
  "./my-project"
);

// Monitor progress
[auth, tests, docs].forEach(task => {
  console.log(`Task ${task.id}: ${get_task_status(task.id).status}`);
});
```

### Pattern 2: Error-Driven Learning

Watch the system train Claude Code to write better prompts:

```javascript
// ❌ Initial attempt (fails with helpful errors)
create_task("Add a function");
// Error: "Execution prompt must be at least 150 characters"  
// Error: "Execution prompt must contain a path-like string"

// ✅ Refined attempt (Claude Code learns)
create_task(
  "Create calculateTotal() function in ./src/utils/math.js that takes array of numbers and returns sum with tax calculation. Include JSDoc comments and export as named export.",
  "./my-project"
);
// Success: Detailed, actionable prompt with clear deliverables
```

### Pattern 3: Background Processing

Set long-running tasks and continue with other work:

```javascript
// Start background analysis
const analysis = create_task(
  "Analyze entire codebase in ./src/ directory and generate comprehensive report in ./ANALYSIS.md covering architecture patterns, code quality metrics, security issues, and refactoring recommendations.",
  "./large-project"
);

// Continue with immediate tasks while analysis runs
// Check periodically: get_task_status(analysis.id)
```

## Environment Configuration

### Optional Environment Variables

```bash
# Override auto-detection
export CLAUDE_WORKER_MODE=standalone    # Force lightweight mode
export CLAUDE_WORKER_MODE=proxy         # Force proxy mode

# Custom paths and URLs  
export CLAUDE_WORKER_DB=~/.claude-worker/tasks.db
export CLAUDE_WORKER_LOG_DIR=~/.claude-worker/logs
export CLAUDE_WORKER_API_URL=http://localhost:8000
```

## Troubleshooting

### Common Issues

| Problem | Solution | Prevention |
|---------|----------|------------|
| "MCP server not connected" | Restart Claude Code completely | Always verify with `claude mcp list` |
| "Execution prompt too short" | Add more detail and context | Aim for 200+ characters with specific requirements |
| "Must contain path-like string" | Include file paths like `./src/file.js` | Always mention specific files or directories |
| "System prompt validation failed" | Let system auto-add or include required keyword | Use default system prompt for simplicity |

### Health Check Commands

```bash
# Verify MCP registration
claude mcp list

# Test MCP connection
claude mcp get claude-worker

# Check API health (if using proxy mode)
curl http://localhost:8000/health

# Manual MCP server test
python -m claude_worker.mcp.factory
```

### Debug Mode

For detailed troubleshooting, check the logs:

```bash
# View task execution logs
tail -f ~/.claude-worker/logs/*.log

# Check MCP server output
CLAUDE_WORKER_MODE=standalone python -m claude_worker.mcp.factory
```

## Best Practices

### ✅ Writing Effective Prompts

```javascript
// Good: Specific, actionable, with clear deliverables
create_task(
  "Refactor the authentication middleware in ./src/middleware/auth.js to use async/await instead of callbacks. Add proper error handling for expired tokens and invalid credentials. Update corresponding tests in ./tests/middleware/auth.test.js to match the new async interface.",
  "./api-server"
);
```

### ✅ Monitoring Task Progress

```javascript
// Check status periodically
const task = create_task(/* ... */);
const checkStatus = setInterval(() => {
  const status = get_task_status(task.id);
  console.log(`Task ${task.id}: ${status.status}`);
  
  if (status.status === 'completed' || status.status === 'failed') {
    clearInterval(checkStatus);
    console.log('Final result:', status.final_summary || status.error_message);
  }
}, 5000);
```

### ✅ Managing Multiple Tasks

```javascript
// Use task IDs to coordinate work
const tasks = [
  create_task("Build component A in ./src/components/A.jsx...", "./project"),
  create_task("Build component B in ./src/components/B.jsx...", "./project"),  
  create_task("Create integration tests in ./tests/integration/...", "./project")
];

// Wait for all to complete
const allComplete = () => tasks.every(t => 
  ['completed', 'failed'].includes(get_task_status(t.id).status)
);
```

## Next Steps

- **Production Deployment**: See [Deployment Guide](./05-administration-deployment.md)
- **Advanced Configuration**: See [Configuration Guide](./05-administration-configuration.md)  
- **REST API Integration**: See [REST API Reference](./04-integrations-rest-api.md)