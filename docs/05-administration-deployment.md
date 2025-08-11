# Production Deployment

While `claude-worker server start` is great for development, it launches a simple daemon process that is not ideal for production. For a robust, production-ready deployment, you should run the server as a true system service using a process manager. This ensures the server automatically restarts on failure or after a system reboot.

## Stopping the Development Server

The `server start` command from `cli/main.py` uses `subprocess.Popen` to create a background process. To stop it, you'll need to find its Process ID (PID) and use the `kill` command. A common way to do this is with `pkill`.

```bash
# Find and kill any running uvicorn process for claude-worker
pkill -f "claude_worker.server.main:app"
```

## Recommended: Deployment with a Process Manager

We recommend using a process manager like `systemd` (common on modern Linux) or `supervisor` to manage the Claude Worker server in production.

### Using `systemd`

1.  **Create a service file:**
    Create the file `/etc/systemd/system/claude-worker.service` and add the following content. Adjust paths and user/group as necessary.

    ```ini
    [Unit]
    Description=Claude Worker Server
    After=network.target

    [Service]
    User=your_user          # The user to run the service as
    Group=your_group        # The group to run the service as
    WorkingDirectory=/path/to/claude-worker  # The project's root directory
    
    # Set required environment variables
    Environment="ANTHROPIC_API_KEY=your-key-here"
    Environment="CLAUDE_WORKER_SERVER_URL=http://127.0.0.1:8000"
    
    # Command to start the server
    ExecStart=/path/to/your/venv/bin/uvicorn claude_worker.server.main:app --host 0.0.0.0 --port 8000

    Restart=on-failure
    RestartSec=5s

    [Install]
    WantedBy=multi-user.target
    ```

2.  **Enable and start the service:**

    ```bash
    # Reload systemd to recognize the new service
    sudo systemctl daemon-reload

    # Start the service now
    sudo systemctl start claude-worker

    # Enable the service to start on boot
    sudo systemctl enable claude-worker

    # Check the status of the service
    sudo systemctl status claude-worker
    ```

## Alternative: Deployment with Docker

Using Docker is another excellent way to package and run Claude Worker in a consistent environment.

1.  **Create a `Dockerfile`:**

    ```dockerfile
    FROM python:3.11-slim

    WORKDIR /app

    # Install poetry and dependencies
    RUN pip install poetry
    COPY pyproject.toml poetry.lock ./
    RUN poetry config virtualenvs.create false && \
        poetry install --no-dev --extras full

    # Copy application code
    COPY src ./src

    # Create data directory within the container
    ENV CLAUDE_WORKER_DATA_DIR=/data
    RUN mkdir -p /data/logs

    # Expose the server port
    EXPOSE 8000

    # Command to run the server
    CMD ["uvicorn", "src.server.main:app", "--host", "0.0.0.0", "--port", "8000"]
    ```

2.  **Build and run the container:**

    ```bash
    # Build the Docker image
    docker build -t claude-worker .

    # Run the container
    docker run -d \
      --name claude-worker-container \
      -p 8000:8000 \
      -v claude_worker_data:/data \
      -e ANTHROPIC_API_KEY="your-key-here" \
      --restart=unless-stopped \
      claude-worker
    ```
    This command runs the container in detached mode, maps port 8000, mounts a volume to persist data, sets the API key, and ensures the container restarts automatically.