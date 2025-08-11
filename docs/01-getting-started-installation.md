# Installation Guide

This guide provides a comprehensive, step-by-step process for installing Claude Worker and its dependencies.

## Prerequisites

Before installing, ensure you have the following prerequisites installed on your system.

### 1. Python (3.10+)

Claude Worker requires Python 3.10 or newer (supports Python 3.10, 3.11, and 3.12). You can verify your Python version with:

```bash
python3 --version
```

If you don't have a compatible version, we recommend:
- **macOS**: `brew install python` or use [pyenv](https://github.com/pyenv/pyenv)
- **Ubuntu/Debian**: `sudo apt install python3.10 python3.10-pip`
- **Windows**: Download from [python.org](https://python.org/downloads/)

### 2. Poetry (for Source Installation)

We use [Poetry](https://python-poetry.org/) for dependency management and packaging. **Only required if installing from source.**

```bash
# Install Poetry
curl -sSL https://install.python-poetry.org | python3 -
# Or use pip (alternative method)
pip install poetry
```

### 3. Authentication Setup

**Choose one authentication method** - Claude Worker supports both automatically:

#### Option A: API Key Authentication 🔑
```bash
export ANTHROPIC_API_KEY="your-api-key-here"
```
Get your API key from the [Anthropic Console](https://console.anthropic.com/).

**Best for:** Teams, CI/CD, granular billing control

#### Option B: Claude Max/Pro Subscription (OAuth) 🎯
```bash
# Install Claude CLI if not already installed
npm install -g @anthropic-ai/claude-code

# Authenticate (one-time setup)
claude setup-token
```

**Best for:** Individual users with Claude subscription. No API key needed!

> 💡 **Smart Authentication:** Claude Worker automatically tries API key first, then falls back to your Claude subscription. You can use either method without changing any configuration!

### 4. Node.js and npm

**Why Node.js for a Python project?** The underlying `@anthropic-ai/claude-code-sdk` that Claude Worker uses is a Node.js application.

**Check if installed:**
```bash
node --version  # Should be 16+ 
npm --version
```

**Install if needed:**
- **macOS**: `brew install node`
- **Ubuntu/Debian**: `sudo apt install nodejs npm` 
- **Windows**: Download from [nodejs.org](https://nodejs.org/)

## Installation from Source (Recommended)

This is the recommended method for getting started, as it gives you the full codebase.

### Step 1: Clone the Repository

Clone the project from GitHub to your local machine:

```bash
git clone https://github.com/yigitkonur/claude-worker.git
cd claude-worker
```

### Step 2: Install Dependencies with Poetry

Poetry will read the `pyproject.toml` file, create a virtual environment, and install all required Python packages.

```bash
poetry install
```

This command installs everything needed to run the server, CLI, and MCP interfaces.

### Step 3: Activate the Virtual Environment

To use the `claude-worker` command directly, activate the virtual environment created by Poetry:

```bash
poetry shell
```

You should now see the virtual environment's name in your shell prompt.

## Installation from PyPI

> **📦 PyPI Status:** Package publishing is in progress. Use source installation for now.

Once published, you'll be able to install with different "extras" depending on your needs:

*   **`[full]` (Recommended):** Everything—server, CLI, and MCP components.
    ```bash
    pip install "claude-worker[full]"
    ```
*   **`[server]`:** Only REST API server and CLI.
    ```bash
    pip install "claude-worker[server]"
    ```
*   **`[mcp]`:** Only MCP server components.
    ```bash
    pip install "claude-worker[mcp]"
    ```

**For now, please use the source installation method above.**

## Verify Installation

After installation, verify that everything is working:

```bash
# Check Claude Worker CLI
claude-worker --version

# Check authentication setup
echo $ANTHROPIC_API_KEY    # Should show API key (if using Option A)
claude --version           # Should show Claude CLI (if using Option B)

# Check Node.js availability 
node --version
```

**Expected Output:**
```
claude-worker 0.1.0
sk-ant-...  (your API key, if using Option A)
1.0.72 (Claude Code)    (if using Option B)
v18.17.0    (or similar Node version)
```

## Next Steps

✅ You're now ready for the [Quick Start Guide](./01-getting-started-quick-start.md)!

**Having Issues?** Common solutions:
- **Command not found**: Make sure you're in the Poetry shell (`poetry shell`)
- **Authentication failed**: Choose Option A (API key) or Option B (Claude CLI)
- **Claude CLI not found**: Install with `npm install -g @anthropic-ai/claude-code`
- **Node.js issues**: Ensure Node.js 16+ is installed and in PATH