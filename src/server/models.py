"""
SOLE RESPONSIBILITY: Defines all Pydantic and SQLModel data contracts for the entire system, 
serving as the single source of truth for data shapes.
"""

from datetime import datetime
from typing import Optional
from enum import Enum
from sqlmodel import SQLModel, Field
from pydantic import BaseModel, field_validator


class TaskStatus(str, Enum):
    """Task status enumeration."""
    PENDING = "pending"
    RUNNING = "running"
    COMPLETED = "completed"
    FAILED = "failed"


class TaskDB(SQLModel, table=True):
    """Database model representing the tasks table schema."""
    __tablename__ = "tasks"
    
    id: Optional[int] = Field(default=None, primary_key=True)
    status: TaskStatus = Field(index=True, default=TaskStatus.PENDING)
    pid: Optional[int] = None
    working_directory: str
    system_prompt: str
    execution_prompt: str
    log_file_path: Optional[str] = None  # Combined log path
    last_action_cache: Optional[str] = None
    final_summary: Optional[str] = None
    error_message: Optional[str] = None
    created_at: datetime = Field(default_factory=datetime.utcnow)
    started_at: Optional[datetime] = None
    ended_at: Optional[datetime] = None


class TaskCreate(BaseModel):
    """Lenient input model for human-friendly REST API."""
    execution_prompt: str
    working_directory: str
    system_prompt: Optional[str] = None


class MCPCreateTaskPayload(BaseModel):
    """Strict input model for machine-facing MCP API with validation."""
    system_prompt: str = Field(..., min_length=75, max_length=500)
    execution_prompt: str = Field(..., min_length=150)
    working_directory: str
    
    @field_validator('system_prompt')
    @classmethod
    def validate_system_prompt(cls, v: str) -> str:
        if "John Carmack" not in v:
            raise ValueError('System prompt must contain "John Carmack"')
        return v
    
    @field_validator('execution_prompt')
    @classmethod
    def validate_execution_prompt(cls, v: str) -> str:
        if '/' not in v and '\\' not in v:
            raise ValueError('Execution prompt must contain a path-like string')
        return v


class TaskRead(BaseModel):
    """Public-facing task representation for API responses."""
    id: int
    status: str
    created_at: datetime
    started_at: Optional[datetime] = None
    ended_at: Optional[datetime] = None
    last_action_cache: Optional[str] = None
    final_summary: Optional[str] = None
    error_message: Optional[str] = None