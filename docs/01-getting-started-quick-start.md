# Quick Start

This guide walks you through the "happy path" of starting Claude Worker and submitting your first task. You'll experience the core "fire-and-forget" workflow in under 5 minutes.

> **⚡ Prerequisites:** Ensure you've completed the [Installation Guide](./01-getting-started-installation.md) first.

## Step 1: Start the Server

Claude Worker has two main components: a **server** (manages tasks) and a **CLI client** (submits tasks). Let's start the server first.

```bash
# Make sure you're in the project directory with Poetry shell active
cd claude-worker
poetry shell

# Start the server (runs in background)
claude-worker server start
```

**Expected Output:**
```
🚀 Starting Claude Worker server on 0.0.0.0:8000...
✓ Server started successfully (PID: 12345)
Server URL: http://0.0.0.0:8000

To stop the server, use: kill 12345
```

### 🔍 What Just Happened?

The server launched as a **background daemon process** using `uvicorn`. Key points:
- **Independent Process**: Server runs separately from your terminal
- **REST API**: Now listening on `http://localhost:8000`
- **Process Pool**: Ready to handle up to 4 concurrent tasks
- **Persistent Storage**: Uses SQLite database at `~/.claude-worker/tasks.db`

**Verify it's running:**
```bash
claude-worker server health
# Expected: {"status": "healthy", "workers": 4}

```

## Step 2: Submit Your First Task

Now let's submit a task! You can use the same terminal or open a new one.

```bash
# Submit a simple task
claude-worker run "Create a Python file named 'hello.py' that prints 'Hello, Claude Worker!' and explain what you did."
```

**Instant Response:**
```
✓ Task created with ID: 1
Status: queued
Working Directory: /Users/you/claude-worker
```

### 🔥 The "Fire-and-Forget" Magic

Notice what just happened:
- ✅ **Instant return**: Got your terminal back immediately
- ✅ **Background execution**: Task runs in isolated process
- ✅ **Unique ID**: Task #1 assigned for tracking
- ✅ **No blocking**: Continue working while Claude codes

## Step 3: Monitor Task Progress

The task is executing in the background. You can check progress anytime using the task ID:

```bash
# Check task status
claude-worker status 1
```

**While Running:**
```
┏━━━━━━━━━━━━━┳━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━┓
┃ Field       ┃ Value                                          ┃
┡━━━━━━━━━━━━━╇━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━┩
│ Status      │ running                                        │
│ Created     │ 2024-01-15T10:30:00.123456                     │
│ Started     │ 2024-01-15T10:30:01.654321                     │
│ Last Action │ [tool:write] hello.py                          │
└─────────────┴────────────────────────────────────────────────┘
```

**When Complete:**
```
┏━━━━━━━━━━━━━┳━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━┓
┃ Field       ┃ Value                                                ┃
┡━━━━━━━━━━━━━╇━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━┩
│ Status      │ completed                                            │
│ Created     │ 2024-01-15T10:30:00.123456                           │
│ Started     │ 2024-01-15T10:30:01.654321                           │
│ Ended       │ 2024-01-15T10:30:15.987654                           │
│ Summary     │ Created hello.py file successfully. The file...     │
└─────────────┴──────────────────────────────────────────────────────┘
```

**💡 Pro Tip:** Use the `--watch` flag for live monitoring:
```bash
claude-worker run "Analyze this codebase structure" --watch
# Automatically shows progress until completion
```

## Step 4: Verify the Results

Let's check what Claude Worker accomplished:

```bash
# Check if the file was created
ls hello.py
# Should show: hello.py

# View the file contents
cat hello.py
```

**Expected Output:**
```python
print("Hello, Claude Worker!")
```

```bash
# Run the created file
python hello.py
# Should print: Hello, Claude Worker!
```

## Step 5: Explore More Commands

Now try these additional commands to get familiar with the system:

```bash
# List all tasks
claude-worker list

# Check server health
claude-worker server health

# View detailed help
claude-worker --help
```

## 🎉 Congratulations!

You've successfully experienced Claude Worker's core workflow:

✅ **Server Management**: Started background server  
✅ **Task Submission**: Fire-and-forget execution  
✅ **Progress Monitoring**: Real-time status checking  
✅ **Result Verification**: Confirmed task completion  

## Next Steps

**Ready for more advanced usage?**

- 📖 **[Advanced Task Submission](./02-user-guide-task-submission.md)**: Learn about file inputs, system prompts, and directory control
- 🔍 **[Monitoring & Logs](./02-user-guide-monitoring-and-logs.md)**: Deep dive into debugging and log inspection  
- ⚙️ **[CLI Reference](./02-user-guide-cli-reference.md)**: Complete command reference  
- 🏗️ **[Architecture](./03-concepts-architecture.md)**: Understand how it all works under the hood

**Having Issues?**
- Check the [Configuration Guide](./05-administration-configuration.md) for environment setup
- Review [Security Considerations](./05-administration-security.md) for production use