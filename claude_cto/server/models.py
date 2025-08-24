"""
SOLE RESPONSIBILITY: Defines all Pydantic and SQLModel data contracts for the entire system,
serving as the single source of truth for data shapes.
"""

from datetime import datetime
from typing import Optional, List
from enum import Enum
from sqlmodel import SQLModel, Field
from pydantic import BaseModel, field_validator


class TaskStatus(str, Enum):
    """Task status enumeration."""

    PENDING = "pending"
    WAITING = "waiting"  # Waiting for dependencies to complete
    RUNNING = "running"
    COMPLETED = "completed"
    FAILED = "failed"
    SKIPPED = "skipped"  # Skipped due to dependency failure


class ClaudeModel(str, Enum):
    """Claude model selection for task execution."""

    SONNET = "sonnet"
    OPUS = "opus"
    HAIKU = "haiku"


class TaskDB(SQLModel, table=True):
    """Database model representing the tasks table schema."""

    __tablename__ = "tasks"

    id: Optional[int] = Field(default=None, primary_key=True)
    status: TaskStatus = Field(index=True, default=TaskStatus.PENDING)
    pid: Optional[int] = None
    working_directory: str
    system_prompt: str
    execution_prompt: str
    model: ClaudeModel = Field(default=ClaudeModel.SONNET)
    log_file_path: Optional[str] = None  # Combined log path
    last_action_cache: Optional[str] = None
    final_summary: Optional[str] = None
    error_message: Optional[str] = None
    created_at: datetime = Field(default_factory=datetime.utcnow)
    started_at: Optional[datetime] = None
    ended_at: Optional[datetime] = None
    updated_at: Optional[datetime] = Field(default=None, sa_column_kwargs={"onupdate": datetime.utcnow})

    # Orchestration fields
    orchestration_id: Optional[int] = Field(default=None, index=True)
    identifier: Optional[str] = Field(default=None, index=True)  # User-defined identifier within orchestration
    depends_on: Optional[str] = None  # JSON array of task identifiers
    initial_delay: Optional[float] = None  # Seconds to wait after dependencies complete
    dependency_failed_at: Optional[datetime] = None  # When marked as skipped


class OrchestrationDB(SQLModel, table=True):
    """Database model for orchestrations."""

    __tablename__ = "orchestrations"

    id: Optional[int] = Field(default=None, primary_key=True)
    status: str = Field(default="pending", index=True)  # pending, running, completed, failed, cancelled
    created_at: datetime = Field(default_factory=datetime.utcnow)
    started_at: Optional[datetime] = None
    ended_at: Optional[datetime] = None
    total_tasks: int = 0
    completed_tasks: int = 0
    failed_tasks: int = 0
    skipped_tasks: int = 0


class TaskCreate(BaseModel):
    """Input model for human-friendly REST API with reasonable validation."""

    execution_prompt: str = Field(..., min_length=10)  # More lenient than MCP
    working_directory: str = Field(..., min_length=1)
    system_prompt: Optional[str] = Field(None, max_length=1000)  # More lenient
    model: Optional[ClaudeModel] = ClaudeModel.SONNET

    @field_validator("execution_prompt")
    @classmethod
    def validate_execution_prompt(cls, v: str) -> str:
        if len(v.strip()) < 10:
            raise ValueError("Execution prompt must be at least 10 characters")
        return v.strip()

    @field_validator("working_directory")
    @classmethod
    def validate_working_directory(cls, v: str) -> str:
        if not v or not v.strip():
            raise ValueError("Working directory cannot be empty")
        # Normalize path separators
        return v.replace("\\", "/").strip()


class MCPCreateTaskPayload(BaseModel):
    """Strict input model for machine-facing MCP API with validation."""

    system_prompt: str = Field(..., min_length=75, max_length=500)
    execution_prompt: str = Field(..., min_length=150)
    working_directory: str
    model: Optional[ClaudeModel] = ClaudeModel.SONNET

    @field_validator("system_prompt")
    @classmethod
    def validate_system_prompt(cls, v: str) -> str:
        if "John Carmack" not in v:
            raise ValueError('System prompt must contain "John Carmack"')
        return v

    @field_validator("execution_prompt")
    @classmethod
    def validate_execution_prompt(cls, v: str) -> str:
        if "/" not in v and "\\" not in v:
            raise ValueError("Execution prompt must contain a path-like string")
        return v


class TaskRead(BaseModel):
    """Public-facing task representation for API responses."""

    id: int
    status: str
    working_directory: str
    created_at: datetime
    started_at: Optional[datetime] = None
    ended_at: Optional[datetime] = None
    last_action_cache: Optional[str] = None
    final_summary: Optional[str] = None
    error_message: Optional[str] = None
    orchestration_id: Optional[int] = None
    identifier: Optional[str] = None
    depends_on: Optional[List[str]] = None
    initial_delay: Optional[float] = None


class TaskOrchestrationItem(BaseModel):
    """Single task definition within an orchestration."""

    identifier: str = Field(..., min_length=1, max_length=100)  # User-defined task identifier
    execution_prompt: str = Field(..., min_length=10)
    working_directory: str = Field(..., min_length=1)
    system_prompt: Optional[str] = Field(None, max_length=1000)
    model: Optional[ClaudeModel] = ClaudeModel.SONNET
    depends_on: Optional[List[str]] = None  # List of identifiers
    initial_delay: Optional[float] = Field(None, ge=0, le=3600)  # 0-3600 seconds (1 hour max)

    @field_validator("identifier")
    @classmethod
    def validate_identifier(cls, v: str) -> str:
        if not v or not v.strip():
            raise ValueError("Identifier cannot be empty")
        # Only allow alphanumeric, underscore, and hyphen
        import re

        if not re.match(r"^[a-zA-Z0-9_-]+$", v):
            raise ValueError("Identifier can only contain letters, numbers, underscore, and hyphen")
        return v.strip()

    @field_validator("execution_prompt")
    @classmethod
    def validate_execution_prompt(cls, v: str) -> str:
        if len(v.strip()) < 10:
            raise ValueError("Execution prompt must be at least 10 characters")
        return v.strip()

    @field_validator("working_directory")
    @classmethod
    def validate_working_directory(cls, v: str) -> str:
        if not v or not v.strip():
            raise ValueError("Working directory cannot be empty")
        return v.replace("\\", "/").strip()


class OrchestrationCreate(BaseModel):
    """Input model for creating an orchestration."""

    tasks: List[TaskOrchestrationItem]

    @field_validator("tasks")
    @classmethod
    def validate_tasks(cls, v: List[TaskOrchestrationItem]) -> List[TaskOrchestrationItem]:
        if not v:
            raise ValueError("At least one task is required")

        # Check for duplicate identifiers
        identifiers = [task.identifier for task in v]
        if len(identifiers) != len(set(identifiers)):
            raise ValueError("Task identifiers must be unique")

        return v
