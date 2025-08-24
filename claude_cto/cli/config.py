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
    Determines API server URL using three-tier configuration priority.
    Critical for CLI-to-server communication - must resolve to active server.
    Priority: Environment variable > Config file > Default localhost
    """
    # Layer 1: Environment variable override (highest priority for deployment flexibility)
    env_url = os.environ.get("CLAUDE_CTO_SERVER_URL")
    if env_url:
        return env_url

    # Layer 2: JSON config file in user app directory (persistent user preference)
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

    # Layer 3: Default localhost fallback (development mode)
    return "http://localhost:8000"
