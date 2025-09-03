"""
SOLE RESPONSIBILITY: Server configuration management with defaults and validation.
Provides centralized configuration for all resource limits and behavior settings.
"""

import os
import json
from pathlib import Path
from dataclasses import dataclass
from typing import Optional
import logging

logger = logging.getLogger(__name__)


@dataclass
class TaskConfig:
    """Task execution configuration."""
    max_concurrent_tasks: int = 10
    task_timeout_seconds: int = 7200  # 2 hours
    task_memory_limit_mb: int = 4096  # 4 GB
    use_isolated_tasks: bool = True
    cleanup_interval_days: int = 7
    max_retries: int = 3
    retry_delay_seconds: int = 60


@dataclass
class ServerConfig:
    """Server configuration."""
    port: int = 8000
    host: str = "0.0.0.0"
    reload: bool = False
    workers: int = 1
    log_level: str = "INFO"
    cleanup_on_startup: bool = True
    kill_duplicate_servers: bool = True


@dataclass 
class DatabaseConfig:
    """Database configuration."""
    url: Optional[str] = None
    pool_size: int = 5
    pool_recycle: int = 3600
    echo: bool = False


@dataclass
class ResourceConfig:
    """Resource limits configuration."""
    memory_warning_threshold: float = 80.0  # Percentage
    memory_critical_threshold: float = 95.0  # Percentage
    cpu_limit_percent: float = 75.0
    disk_usage_limit_percent: float = 90.0
    max_log_file_size_mb: int = 100
    max_total_logs_gb: int = 10


@dataclass
class Config:
    """Complete configuration."""
    task: TaskConfig
    server: ServerConfig
    database: DatabaseConfig
    resources: ResourceConfig
    
    @classmethod
    def load(cls) -> "Config":
        """
        Load configuration from multiple sources in priority order:
        1. Environment variables (highest)
        2. Local config file (project)
        3. User config file (~/.claude-cto/config.json)
        4. Default values (lowest)
        """
        # Start with defaults
        config = cls(
            task=TaskConfig(),
            server=ServerConfig(),
            database=DatabaseConfig(),
            resources=ResourceConfig()
        )
        
        # Load user config file if exists
        user_config_path = Path.home() / ".claude-cto" / "config.json"
        if user_config_path.exists():
            try:
                with open(user_config_path) as f:
                    user_config = json.load(f)
                    config._merge_dict(user_config)
                logger.info(f"Loaded user config from {user_config_path}")
            except Exception as e:
                logger.warning(f"Error loading user config: {e}")
        
        # Load project config file if exists
        project_config_path = Path.cwd() / ".claude-cto.json"
        if project_config_path.exists():
            try:
                with open(project_config_path) as f:
                    project_config = json.load(f)
                    config._merge_dict(project_config)
                logger.info(f"Loaded project config from {project_config_path}")
            except Exception as e:
                logger.warning(f"Error loading project config: {e}")
        
        # Override with environment variables
        config._load_env_vars()
        
        return config
    
    def _merge_dict(self, config_dict: dict):
        """Merge dictionary into config."""
        if "task" in config_dict:
            for key, value in config_dict["task"].items():
                if hasattr(self.task, key):
                    setattr(self.task, key, value)
        
        if "server" in config_dict:
            for key, value in config_dict["server"].items():
                if hasattr(self.server, key):
                    setattr(self.server, key, value)
        
        if "database" in config_dict:
            for key, value in config_dict["database"].items():
                if hasattr(self.database, key):
                    setattr(self.database, key, value)
        
        if "resources" in config_dict:
            for key, value in config_dict["resources"].items():
                if hasattr(self.resources, key):
                    setattr(self.resources, key, value)
    
    def _load_env_vars(self):
        """Load configuration from environment variables."""
        # Task config
        if val := os.environ.get("MAX_CONCURRENT_TASKS"):
            self.task.max_concurrent_tasks = int(val)
        if val := os.environ.get("TASK_TIMEOUT"):
            self.task.task_timeout_seconds = int(val)
        if val := os.environ.get("TASK_MEMORY_LIMIT_MB"):
            self.task.task_memory_limit_mb = int(val)
        if val := os.environ.get("CLAUDE_CTO_ISOLATED_TASKS"):
            self.task.use_isolated_tasks = val.lower() == "true"
        
        # Server config
        if val := os.environ.get("SERVER_PORT"):
            self.server.port = int(val)
        if val := os.environ.get("SERVER_HOST"):
            self.server.host = val
        if val := os.environ.get("LOG_LEVEL"):
            self.server.log_level = val
        
        # Database config
        if val := os.environ.get("DATABASE_URL"):
            self.database.url = val
        
        # Resource config
        if val := os.environ.get("MEMORY_WARNING_THRESHOLD"):
            self.resources.memory_warning_threshold = float(val)
        if val := os.environ.get("MEMORY_CRITICAL_THRESHOLD"):
            self.resources.memory_critical_threshold = float(val)
    
    def save(self, path: Optional[Path] = None):
        """Save configuration to file."""
        if path is None:
            path = Path.home() / ".claude-cto" / "config.json"
        
        config_dict = {
            "task": {
                "max_concurrent_tasks": self.task.max_concurrent_tasks,
                "task_timeout_seconds": self.task.task_timeout_seconds,
                "task_memory_limit_mb": self.task.task_memory_limit_mb,
                "use_isolated_tasks": self.task.use_isolated_tasks,
                "cleanup_interval_days": self.task.cleanup_interval_days,
                "max_retries": self.task.max_retries,
                "retry_delay_seconds": self.task.retry_delay_seconds,
            },
            "server": {
                "port": self.server.port,
                "host": self.server.host,
                "reload": self.server.reload,
                "workers": self.server.workers,
                "log_level": self.server.log_level,
                "cleanup_on_startup": self.server.cleanup_on_startup,
                "kill_duplicate_servers": self.server.kill_duplicate_servers,
            },
            "database": {
                "pool_size": self.database.pool_size,
                "pool_recycle": self.database.pool_recycle,
                "echo": self.database.echo,
            },
            "resources": {
                "memory_warning_threshold": self.resources.memory_warning_threshold,
                "memory_critical_threshold": self.resources.memory_critical_threshold,
                "cpu_limit_percent": self.resources.cpu_limit_percent,
                "disk_usage_limit_percent": self.resources.disk_usage_limit_percent,
                "max_log_file_size_mb": self.resources.max_log_file_size_mb,
                "max_total_logs_gb": self.resources.max_total_logs_gb,
            }
        }
        
        path.parent.mkdir(parents=True, exist_ok=True)
        with open(path, "w") as f:
            json.dump(config_dict, f, indent=2)
        
        logger.info(f"Saved config to {path}")


# Global singleton
_config: Optional[Config] = None


def get_config() -> Config:
    """Get global configuration instance."""
    global _config
    if _config is None:
        _config = Config.load()
    return _config


def reload_config():
    """Reload configuration from sources."""
    global _config
    _config = Config.load()
    logger.info("Configuration reloaded")