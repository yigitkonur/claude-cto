"""
SOLE RESPONSIBILITY: Manages all client-side configuration logic,
primarily discovering the server URL from environment variables or a local config file.
"""

import os
import json
from pathlib import Path
import typer


def get_server_url() -> str:
    """
    Discover server URL using layered configuration.
    Priority: Environment variable > Config file > Default
    """
    # 1. Check environment variable (highest priority)
    env_url = os.environ.get("CLAUDE_CTO_SERVER_URL")
    if env_url:
        return env_url

    # 2. Check config file
    config_dir = Path(typer.get_app_dir("claude-cto"))
    config_file = config_dir / "config.json"

    if config_file.exists():
        try:
            with open(config_file, "r") as f:
                config = json.load(f)
                if "server_url" in config:
                    return config["server_url"]
        except (json.JSONDecodeError, IOError):
            pass  # Fall through to default

    # 3. Return default value
    return "http://localhost:8000"
