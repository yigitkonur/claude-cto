# Claude Worker 🚀

**Fire-and-forget task execution for Claude Code SDK with dependency orchestration.**  
Run complex AI-powered workflows without blocking your terminal. Define task dependencies, run in parallel, and get instant audio feedback.

[![Python 3.10+](https://img.shields.io/badge/python-3.10%2B-blue.svg)](https://www.python.org/downloads/)
[![PyPI](https://img.shields.io/pypi/v/claude-worker.svg)](https://pypi.org/project/claude-worker/)
[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](LICENSE)

## 🎯 Key Features

- **🔗 Task Orchestration** - Define complex workflows with dependencies, automatic parallel execution, and failure propagation
- **🚀 Fire & Forget** - Submit tasks and continue working while Claude handles them in the background
- **💾 Persistent** - SQLite storage survives crashes and restarts
- **🔊 Audio Feedback** - Get notified with sounds when tasks start, complete, or fail
- **📊 Rich Logging** - Structured, emoji-enhanced logs with multiple verbosity levels
- **🔄 Auto-Retry** - Intelligent retry logic with exponential backoff for transient failures
- **🎛️ Multiple Interfaces** - CLI, REST API, and MCP (Claude Desktop) support

## 📦 Installation

```bash
# Everything (recommended)
pip install "claude-worker[full]"

# Just CLI and REST API
pip install "claude-worker[server]"

# Just MCP for Claude Desktop
pip install "claude-worker[mcp]"
```

**Prerequisites:** 
- Python 3.10+
- Node.js 16+ (for Claude CLI)
- `ANTHROPIC_API_KEY` or Claude CLI OAuth

## 🚀 Quick Start

### 1. Basic Task Execution

```bash
# Single task - server auto-starts
claude-worker run "Create a Python web scraper for news articles"

# With options
claude-worker run "Refactor auth.py" --dir ./src --model opus --watch

# From file or stdin
claude-worker run instructions.txt
git diff | claude-worker run "Review these changes"
```

### 2. Task Orchestration (NEW!)

Create `workflow.json`:
```json
{
  "tasks": [
    {
      "identifier": "fetch_data",
      "execution_prompt": "Download dataset from S3 to /data/raw/"
    },
    {
      "identifier": "process_data",
      "execution_prompt": "Clean and transform data in /data/raw/",
      "depends_on": ["fetch_data"],
      "initial_delay": 2.0
    },
    {
      "identifier": "train_model",
      "execution_prompt": "Train ML model on processed data",
      "depends_on": ["process_data"],
      "model": "opus"
    }
  ]
}
```

Execute workflow:
```bash
# Submit and continue
claude-worker orchestrate workflow.json

# Submit and wait for completion
claude-worker orchestrate workflow.json --wait

# Check progress
claude-worker orchestration-status 1
```

### 3. MCP Integration (Claude Desktop)

Setup once:
```bash
pip install "claude-worker[mcp]"
claude mcp add claude-worker -s user -- python -m claude_worker.mcp.factory
```

Now Claude can create dependent tasks:
```python
# Claude automatically manages orchestrations
await create_task(
    task_identifier="setup_db",
    execution_prompt="Initialize PostgreSQL database"
)

await create_task(
    task_identifier="migrate_schema",
    execution_prompt="Run database migrations",
    depends_on=["setup_db"],
    wait_after_dependencies=2.0
)

await create_task(
    task_identifier="seed_data",
    execution_prompt="Populate test data",
    depends_on=["migrate_schema"]
)
```

## 📊 Real-World Examples

### Example 1: Full-Stack App Development

```json
{
  "tasks": [
    {
      "identifier": "design_api",
      "execution_prompt": "Design REST API specification for todo app",
      "model": "opus"
    },
    {
      "identifier": "create_backend",
      "execution_prompt": "Implement FastAPI backend based on API spec",
      "depends_on": ["design_api"],
      "working_directory": "./backend"
    },
    {
      "identifier": "create_frontend",
      "execution_prompt": "Build React frontend with TypeScript",
      "depends_on": ["design_api"],
      "working_directory": "./frontend"
    },
    {
      "identifier": "add_tests",
      "execution_prompt": "Write comprehensive test suites",
      "depends_on": ["create_backend", "create_frontend"]
    },
    {
      "identifier": "create_docker",
      "execution_prompt": "Create Docker Compose configuration",
      "depends_on": ["add_tests"]
    }
  ]
}
```

### Example 2: Codebase Refactoring

```bash
# Create refactoring pipeline
cat > refactor.json << EOF
{
  "tasks": [
    {
      "identifier": "analyze",
      "execution_prompt": "Analyze codebase for code smells and technical debt",
      "model": "opus"
    },
    {
      "identifier": "plan_refactor",
      "execution_prompt": "Create detailed refactoring plan",
      "depends_on": ["analyze"],
      "model": "opus"
    },
    {
      "identifier": "refactor_auth",
      "execution_prompt": "Refactor authentication module",
      "depends_on": ["plan_refactor"]
    },
    {
      "identifier": "refactor_api",
      "execution_prompt": "Refactor API endpoints",
      "depends_on": ["plan_refactor"]
    },
    {
      "identifier": "refactor_db",
      "execution_prompt": "Refactor database layer",
      "depends_on": ["plan_refactor"]
    },
    {
      "identifier": "run_tests",
      "execution_prompt": "Run all tests and fix any issues",
      "depends_on": ["refactor_auth", "refactor_api", "refactor_db"]
    }
  ]
}
EOF

# Execute with progress monitoring
claude-worker orchestrate refactor.json --wait
```

### Example 3: Data Pipeline

```python
# Programmatic orchestration via REST API
import httpx

client = httpx.Client(base_url="http://localhost:8000")

# Define ETL pipeline
pipeline = {
    "tasks": [
        # Extract (parallel)
        {"identifier": "extract_sales", "execution_prompt": "Extract sales data from PostgreSQL"},
        {"identifier": "extract_inventory", "execution_prompt": "Extract inventory from MongoDB"},
        {"identifier": "extract_customers", "execution_prompt": "Extract customer data from API"},
        
        # Transform (depends on all extracts)
        {
            "identifier": "transform",
            "execution_prompt": "Clean, normalize, and join all datasets",
            "depends_on": ["extract_sales", "extract_inventory", "extract_customers"],
            "initial_delay": 2.0
        },
        
        # Load
        {
            "identifier": "load_warehouse",
            "execution_prompt": "Load transformed data into Snowflake",
            "depends_on": ["transform"]
        },
        
        # Report
        {
            "identifier": "generate_report",
            "execution_prompt": "Create executive dashboard",
            "depends_on": ["load_warehouse"],
            "model": "opus"
        }
    ]
}

# Submit pipeline
response = client.post("/api/v1/orchestrations", json=pipeline)
orch_id = response.json()["orchestration_id"]

# Monitor progress
import time
while True:
    status = client.get(f"/api/v1/orchestrations/{orch_id}").json()
    print(f"Progress: {status['completed_tasks']}/{status['total_tasks']}")
    if status['status'] in ['completed', 'failed']:
        break
    time.sleep(5)
```

## 🎯 Model Selection Strategy

```bash
# Fast, simple tasks (file operations, basic analysis)
--model haiku    # ~$0.001 per task

# Balanced performance (default)
--model sonnet   # ~$0.01 per task

# Complex reasoning (architecture, refactoring)
--model opus     # ~$0.05 per task
```

## 🔊 Sound Notifications

Get audio feedback for task events:

```bash
# Customize sounds
export CLAUDE_WORKER_START_SOUND=/path/to/start.wav
export CLAUDE_WORKER_SUCCESS_SOUND=/path/to/success.wav
export CLAUDE_WORKER_FAILURE_SOUND=/path/to/failure.wav

# Disable if needed
export CLAUDE_WORKER_ENABLE_SOUNDS=false
```

**Platform Support:**
- **macOS**: Native `afplay`
- **Linux**: PulseAudio or ALSA
- **Windows**: PowerShell SoundPlayer
- **Universal**: `mpv` or `ffplay`

## 📁 Logging & Monitoring

```bash
# View all tasks
claude-worker list

# Check specific task
claude-worker status 42

# Monitor logs
tail -f ~/.claude-worker/claude-worker.log         # Global
tail -f ~/.claude-worker/tasks/task_*_summary.log  # Task summary
tail -f ~/.claude-worker/tasks/task_*_detailed.log # Full details

# List orchestrations
claude-worker list-orchestrations --status running
```

## 🔧 Configuration

### Environment Variables

```bash
# Authentication
export ANTHROPIC_API_KEY="sk-ant-..."

# Server
export CLAUDE_WORKER_HOST="0.0.0.0"
export CLAUDE_WORKER_PORT="8000"

# Storage
export CLAUDE_WORKER_DB="~/.claude-worker/tasks.db"
export CLAUDE_WORKER_LOG_DIR="~/.claude-worker/logs"

# Orchestration limits
export MAX_TASKS_PER_ORCHESTRATION="100"
export ORCHESTRATION_TIMEOUT="3600"

# Sound notifications
export CLAUDE_WORKER_ENABLE_SOUNDS="true"
```

## 🚀 Production Deployment

### Docker Compose

```yaml
version: '3.8'
services:
  claude-worker:
    image: claude-worker:latest
    ports:
      - "8000:8000"
    environment:
      - ANTHROPIC_API_KEY=${ANTHROPIC_API_KEY}
    volumes:
      - ./data:/data
    restart: unless-stopped
```

### Systemd Service

```bash
# /etc/systemd/system/claude-worker.service
[Unit]
Description=Claude Worker Server
After=network.target

[Service]
Type=simple
User=claude
ExecStart=/usr/local/bin/claude-worker server start
Restart=on-failure
Environment="ANTHROPIC_API_KEY=sk-ant-..."

[Install]
WantedBy=multi-user.target
```

## 🆙 Upgrading

### From Pre-Orchestration Versions

```bash
# 1. Upgrade package
pip install --upgrade "claude-worker[full]"

# 2. Backup database
cp ~/.claude-worker/tasks.db ~/.claude-worker/tasks.db.backup

# 3. Run migration
python -m claude_worker.scripts.migrate_db --migrate

# 4. Verify
python -m claude_worker.scripts.migrate_db
# Should show: ✓ Orchestration support: Yes
```

## 🐛 Troubleshooting

### Quick Fixes

```bash
# Check health
curl http://localhost:8000/health

# Reset stuck orchestration
claude-worker cancel-orchestration <id>

# Fix "database locked"
pkill -f claude-worker
rm ~/.claude-worker/tasks.db-journal

# Test sounds
python -c "from claude_worker.server.notification import test_sounds; test_sounds()"

# Full reset
pkill -f claude-worker
rm -rf ~/.claude-worker
claude-worker server start
```

### Common Issues

| Issue | Solution |
|-------|----------|
| Circular dependency | Review task dependencies, ensure DAG |
| Tasks not parallel | Remove unnecessary `depends_on` |
| Database locked | Kill stuck processes, remove lock files |
| No orchestration support | Run migration script |
| Sound not working | Check platform tools (afplay/paplay/mpv) |

## 🛠️ Development

```bash
# Setup
git clone https://github.com/yigitkonur/claude-worker
cd claude-worker
poetry install
poetry shell

# Run with auto-reload
claude-worker server start --reload

# Tests
pytest
black claude_worker/
ruff check claude_worker/

# Build
poetry build
```

## 📚 Documentation

- [Orchestration Guide](HANDOFF_DOCS_TO_NEXT_DEVELOPER/DOC_PACK_02-TASK_ORCHESTRATION_AND_DEPENDENCIES/01_ORCHESTRATION_OVERVIEW.md)
- [CLI Reference](HANDOFF_DOCS_TO_NEXT_DEVELOPER/DOC_PACK_02-TASK_ORCHESTRATION_AND_DEPENDENCIES/03_CLI_USAGE_GUIDE.md)
- [MCP Integration](HANDOFF_DOCS_TO_NEXT_DEVELOPER/DOC_PACK_02-TASK_ORCHESTRATION_AND_DEPENDENCIES/04_MCP_INTEGRATION.md)
- [API Documentation](docs/api.md)
- [Architecture](HANDOFF_DOCS_TO_NEXT_DEVELOPER/DOC_PACK_02-TASK_ORCHESTRATION_AND_DEPENDENCIES/02_IMPLEMENTATION_ARCHITECTURE.md)

## 🤝 Contributing

Contributions welcome! Please read [CONTRIBUTING.md](CONTRIBUTING.md) and follow the SOLE principle:
- Each module has Single, Overarching, Lucidly-stated Expertise
- Maintain backward compatibility
- Add tests for new features
- Update documentation

## 📄 License

MIT - see [LICENSE](LICENSE) file.

## 🔗 Links

- [PyPI Package](https://pypi.org/project/claude-worker/)
- [GitHub Repository](https://github.com/yigitkonur/claude-worker)
- [Issue Tracker](https://github.com/yigitkonur/claude-worker/issues)
- [Discussions](https://github.com/yigitkonur/claude-worker/discussions)

---

**Built with ❤️ for developers who value their time.**  
Stop waiting for Claude. Start orchestrating.