"""
SOLE RESPONSIBILITY: Manages the database engine and session creation.
Contains no application logic.
"""

import logging
from pathlib import Path
from sqlmodel import SQLModel, Session, create_engine
from sqlalchemy import text
from sqlalchemy.pool import StaticPool
from sqlalchemy.exc import OperationalError

logger = logging.getLogger(__name__)

# Application data directory setup
app_dir = Path.home() / ".claude-cto"
app_dir.mkdir(parents=True, exist_ok=True)

# Database file path
db_path = app_dir / "tasks.db"

# Create SQLite engine with proper connection pooling for resilience
# Using StaticPool for SQLite to maintain persistent connections
engine = create_engine(
    f"sqlite:///{db_path}",
    echo=False,
    poolclass=StaticPool,  # Single connection reused across threads
    connect_args={
        "check_same_thread": False,  # SQLite thread safety
        "timeout": 30,  # 30 second timeout for locks
    },
)


def create_db_and_tables():
    """Initialize database schema. Called once at server startup."""
    SQLModel.metadata.create_all(engine)


def get_session():
    """
    Dependency provider for database sessions with retry logic.
    Implements context manager pattern for FastAPI dependency injection.
    Ensures sessions are always closed after use and handles connection drops.
    """
    max_retries = 3
    retry_delay = 0.5

    for attempt in range(max_retries):
        try:
            with Session(engine) as session:
                # Test connection is alive
                session.execute(text("SELECT 1"))
                yield session
                return
        except OperationalError as e:
            logger.warning(
                f"Database connection failed (attempt {attempt + 1}/{max_retries}): {e}"
            )
            if attempt < max_retries - 1:
                import time

                time.sleep(retry_delay * (2**attempt))  # Exponential backoff
                # Try to reconnect
                try:
                    engine.dispose()  # Close all connections
                    engine.connect()  # Reconnect
                except Exception:
                    pass
            else:
                logger.error("Database connection failed after all retries")
                raise
