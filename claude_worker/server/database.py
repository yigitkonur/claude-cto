"""
SOLE RESPONSIBILITY: Manages the database engine and session creation. 
Contains no application logic.
"""

from pathlib import Path
from sqlmodel import SQLModel, Session, create_engine

# Application data directory setup
app_dir = Path.home() / ".claude-worker"
app_dir.mkdir(parents=True, exist_ok=True)

# Database file path
db_path = app_dir / "tasks.db"

# Create SQLite engine with connection pool
engine = create_engine(f"sqlite:///{db_path}", echo=False)


def create_db_and_tables():
    """Initialize database schema. Called once at server startup."""
    SQLModel.metadata.create_all(engine)


def get_session():
    """
    Dependency provider for database sessions.
    Implements context manager pattern for FastAPI dependency injection.
    Ensures sessions are always closed after use.
    """
    with Session(engine) as session:
        yield session