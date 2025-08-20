# Smithery-compatible Dockerfile for Claude Worker MCP Server
# Uses Python Alpine for minimal container size

FROM python:3.11-alpine

# Install system dependencies
RUN apk add --no-cache \
    gcc \
    musl-dev \
    linux-headers \
    libffi-dev \
    openssl-dev \
    sqlite \
    bash

# Set working directory
WORKDIR /app

# Copy dependency files first for better caching
COPY pyproject.toml poetry.lock ./

# Install Poetry and dependencies
RUN pip install --no-cache-dir poetry && \
    poetry config virtualenvs.create false && \
    poetry install --only main --no-interaction --no-ansi --no-root -E mcp

# Copy the application code
COPY claude_worker/ ./claude_worker/
COPY README.md CHANGELOG.md LICENSE ./

# Create data directories for database and logs
RUN mkdir -p /data/claude-worker/logs && \
    chmod -R 755 /data

# Set environment variables for MCP server
ENV PYTHONUNBUFFERED=1
ENV CLAUDE_WORKER_DB=/data/claude-worker/tasks.db
ENV CLAUDE_WORKER_LOG_DIR=/data/claude-worker/logs
ENV CLAUDE_WORKER_MODE=standalone

# Health check (optional but recommended)
HEALTHCHECK --interval=30s --timeout=10s --start-period=5s --retries=3 \
    CMD python -c "import claude_worker; print('healthy')" || exit 1

# Run the MCP server in stdio mode
# This is the entry point for Smithery MCP servers
CMD ["python", "-m", "claude_worker.mcp.factory"]