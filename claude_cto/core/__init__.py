"""
Core shared functionality for claude-cto.
This module contains the essential logic used by both REST API and MCP servers.
"""

from .database import (
    get_database_url,
    create_engine_for_db,
    create_session_maker,
    init_database,
    get_task_by_id,
    create_task_record,
    update_task_status,
)

from .executor import TaskExecutor, execute_task_async, execute_task_sync

__all__ = [
    # Database functions
    "get_database_url",
    "create_engine_for_db",
    "create_session_maker",
    "init_database",
    "get_task_by_id",
    "create_task_record",
    "update_task_status",
    # Executor functions
    "TaskExecutor",
    "execute_task_async",
    "execute_task_sync",
]
