FROM python:3.10-slim-bullseye

# Install system dependencies
RUN apt-get update && apt-get install -y \
    build-essential \
    curl \
    git \
    && rm -rf /var/lib/apt/lists/*

# Set working directory
WORKDIR /app/claude-cto

# Copy project files
COPY pyproject.toml poetry.lock* ./

# Install Python dependencies
RUN pip install poetry \
    && poetry config virtualenvs.create false \
    && poetry install --no-interaction --no-ansi

# Copy the rest of the project
COPY claude_cto ./claude_cto

# Set environment variables
ENV PYTHONUNBUFFERED=1 \
    PYTHONDONTWRITEBYTECODE=1 \
    POETRY_VIRTUALENVS_CREATE=false

# Expose any necessary ports (adjust as needed)
EXPOSE 8000

# Default command (adjust to match your project's entry point)
CMD ["claude-cto", "server", "start"]