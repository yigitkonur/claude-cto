# Security Considerations

Security is a critical aspect of any networked service. The current version of Claude Worker is designed for simplicity and is intended to be run in a trusted, private network environment. **By default, it has no built-in authentication or authorization.**

This document outlines the potential risks and provides concrete mitigation strategies for securing your instance.

## The Core Risk: Unauthenticated Access

As seen in the FastAPI endpoint definitions in `server/main.py`, the API endpoints are open to anyone who can access the server's host and port.

```python
# src/server/main.py

@app.post("/api/v1/tasks", response_model=models.TaskRead)
def create_task(
    task_in: models.TaskCreate,
    session: Session = Depends(get_session) # This is for DB sessions, NOT security
):
    # ... no authentication check ...
```

This presents two primary security risks:

1.  **Unauthorized Task Execution:** Anyone on the network can submit tasks, potentially consuming your Anthropic API quota and server resources.
2.  **File System Access:** Because the Claude Code SDK can read and write files, a malicious actor could submit a task that reads sensitive files (`cat /etc/passwd`) or writes harmful scripts to your server's file system. The task runs with the same user permissions as the Claude Worker server process.

## Mitigation Strategies

It is **highly recommended** that you implement the following measures if you plan to expose Claude Worker to any network other than your local machine (`localhost`).

### 1. Run on a Private Network (Default Recommendation)

The simplest and most effective security measure is to not expose the server to the public internet. Run it on a private IP address and use firewall rules to restrict access.

**Using a Firewall (`ufw` on Ubuntu):**

If your server is running on port 8000, you can use `ufw` (Uncomplicated Firewall) to allow access only from specific, trusted IP addresses.

```bash
# Deny all incoming traffic by default
sudo ufw default deny incoming

# Allow SSH access so you don't lock yourself out
sudo ufw allow ssh

# Allow access to port 8000 ONLY from a trusted IP
sudo ufw allow from 192.168.1.50 to any port 8000

# Enable the firewall
sudo ufw enable
```

### 2. Use a Reverse Proxy for Authentication

For more robust security, you can place Claude Worker behind a reverse proxy like **Nginx** or **Caddy**. The reverse proxy can handle authentication before forwarding a request to the Claude Worker server.

**Example Nginx Configuration with Basic Auth:**

This configuration adds a username/password prompt to all API requests.

1.  Create a password file:
    ```bash
    # You will be prompted to create a password for 'admin'
    sudo htpasswd -c /etc/nginx/.htpasswd admin
    ```

2.  Configure your Nginx site (`/etc/nginx/sites-available/claude-worker`):
    ```nginx
    server {
        listen 80;
        server_name claude-worker.yourdomain.com;

        location / {
            # Add basic authentication
            auth_basic "Restricted Access";
            auth_basic_user_file /etc/nginx/.htpasswd;

            # Forward requests to the Claude Worker server
            proxy_pass http://localhost:8000;
            proxy_set_header Host $host;
            proxy_set_header X-Real-IP $remote_addr;
            proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;
        }
    }
    ```

With this setup, any API call (e.g., from `curl` or the CLI) would require authentication, effectively securing your instance.

> **Note:** Implementing proper authentication and authorization natively within the application is a high-priority item on our [Roadmap](./ROADMAP.md).