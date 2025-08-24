# Multi-stage Dockerfile for Claude CTO
# Supports both MCP (Smithery) and REST API server modes
# Uses multi-stage build for optimal size and security

# Builder stage - compile dependencies
FROM python:3.11-alpine as builder

# Install build dependencies
RUN apk add --no-cache \
    gcc \
    musl-dev \
    linux-headers \
    libffi-dev \
    openssl-dev \
    postgresql-dev \
    cargo \
    rust

# Set working directory
WORKDIR /build

# Copy dependency files and README for poetry
COPY pyproject.toml poetry.lock* README.md ./

# Copy application code now for installation
COPY claude_cto/ ./claude_cto/

# Install Poetry and dependencies with all extras
RUN pip install --no-cache-dir poetry==1.7.1 && \
    poetry config virtualenvs.create false && \
    poetry install --no-interaction --no-ansi --extras full

# Production stage - minimal runtime
FROM python:3.11-alpine

# Install runtime dependencies only
RUN apk add --no-cache \
    sqlite \
    libpq \
    bash \
    curl \
    && adduser -D -u 1000 claude

# Set environment variables
ENV PYTHONUNBUFFERED=1 \
    PYTHONDONTWRITEBYTECODE=1 \
    PATH="/home/claude/.local/bin:${PATH}" \
    CLAUDE_CTO_DB=/data/tasks.db \
    CLAUDE_CTO_LOG_DIR=/data/logs \
    PORT=8000

# Set working directory
WORKDIR /app

# Copy Python packages from builder
COPY --from=builder /usr/local/lib/python3.11/site-packages /usr/local/lib/python3.11/site-packages
COPY --from=builder /usr/local/bin /usr/local/bin

# Copy application code
COPY --chown=claude:claude claude_cto/ ./claude_cto/
COPY --chown=claude:claude README.md pyproject.toml ./

# Copy and setup entrypoint script
COPY docker-entrypoint.sh /usr/local/bin/docker-entrypoint.sh
RUN chmod +x /usr/local/bin/docker-entrypoint.sh

# Create CLI wrapper for direct command execution
RUN echo '#!/bin/sh\nexec python -m claude_cto.cli.main "$@"' > /usr/local/bin/claude-cto && \
    chmod +x /usr/local/bin/claude-cto

# Create data directories with proper permissions
RUN mkdir -p /data/logs /home/claude/.claude-cto && \
    chown -R claude:claude /data /home/claude/.claude-cto && \
    chown claude:claude /usr/local/bin/claude-cto

# Switch to non-root user
USER claude

# Volume mount points for persistence
VOLUME ["/data", "/home/claude/.claude-cto"]

# Expose REST API port
EXPOSE 8000

# Health check for REST API mode
HEALTHCHECK --interval=30s --timeout=10s --start-period=5s --retries=3 \
    CMD curl -f http://localhost:8000/health || exit 1

# Use the entrypoint script
ENTRYPOINT ["/usr/local/bin/docker-entrypoint.sh"]

# Default to server mode
CMD ["server"]

# Labels for container registries
LABEL org.opencontainers.image.source="https://github.com/yigitkonur/claude-cto" \
      org.opencontainers.image.description="Fire-and-forget task execution system for Claude Code SDK" \
      org.opencontainers.image.licenses="MIT" \
      org.opencontainers.image.authors="Yigit Konur <yigit@thinkbuddy.ai>" \
      org.opencontainers.image.title="Claude CTO" \
      org.opencontainers.image.documentation="https://github.com/yigitkonur/claude-cto/blob/main/README.md"