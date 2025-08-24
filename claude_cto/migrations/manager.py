"""
Database migration manager for claude-cto.
Handles schema versioning and automatic migrations.
"""

import logging
from pathlib import Path
from typing import Optional
from datetime import datetime

from sqlalchemy import (
    create_engine,
    text,
    MetaData,
    Table,
    Column,
    Integer,
    String,
    DateTime,
)
from sqlalchemy.exc import OperationalError
from sqlmodel import SQLModel

logger = logging.getLogger(__name__)


class MigrationManager:
    """Manages database schema migrations."""

    def __init__(self, db_url: str, migrations_dir: Optional[Path] = None):
        """
        Initialize migration manager.

        Args:
            db_url: Database connection URL
            migrations_dir: Directory containing migration scripts
        """
        self.db_url = db_url
        self.engine = create_engine(db_url)
        self.migrations_dir = migrations_dir or Path(__file__).parent / "versions"
        self.migrations_dir.mkdir(parents=True, exist_ok=True)

        # Create migrations tracking table if it doesn't exist
        self._ensure_migration_table()

    def _ensure_migration_table(self) -> None:
        """
        Creates schema_migrations table for version tracking - essential for migration state management.
        This table serves as the single source of truth for applied database changes.
        """
        # Schema migration metadata: defines the version tracking table structure
        metadata = MetaData()

        Table(
            "schema_migrations",
            metadata,
            Column("version", Integer, primary_key=True),
            Column("description", String(255)),
            Column("applied_at", DateTime, default=datetime.utcnow),
        )

        # Table creation: idempotent operation that only creates if missing
        metadata.create_all(self.engine)

    def get_current_version(self) -> int:
        """
        Queries database for highest applied migration version - determines migration starting point.
        Returns 0 for fresh databases with no migrations applied yet.
        """
        try:
            # Version query: finds the most recent migration that was successfully applied
            with self.engine.connect() as conn:
                result = conn.execute(text("SELECT MAX(version) FROM schema_migrations")).scalar()
                return result or 0
        except OperationalError:
            # Fresh database: migration table doesn't exist yet, start from version 0
            return 0

    def apply_migration(self, version: int, description: str, upgrade_sql: str) -> bool:
        """
        Apply a single migration.

        Args:
            version: Migration version number
            description: Description of the migration
            upgrade_sql: SQL to execute for the upgrade

        Returns:
            True if migration was applied, False if already applied
        """
        current = self.get_current_version()

        if version <= current:
            logger.info(f"Migration {version} already applied, skipping")
            return False

        try:
            # Transactional migration execution: ensures atomicity of schema changes and version tracking
            with self.engine.begin() as conn:
                # Raw SQL execution: processes multi-statement migrations by splitting on semicolon
                for statement in upgrade_sql.split(";"):
                    statement = statement.strip()
                    if statement:
                        conn.execute(text(statement))

                # Migration record insertion: permanently tracks successful application in database
                conn.execute(
                    text(
                        """
                        INSERT INTO schema_migrations (version, description, applied_at)
                        VALUES (:version, :description, :applied_at)
                    """
                    ),
                    {
                        "version": version,
                        "description": description,
                        "applied_at": datetime.utcnow(),
                    },
                )

            logger.info(f"Applied migration {version}: {description}")
            return True

        except Exception as e:
            logger.error(f"Failed to apply migration {version}: {e}")
            raise

    def run_migrations(self) -> int:
        """
        Orchestrates complete database migration process from current version to latest.
        Handles both fresh installations and incremental upgrades seamlessly.

        Returns:
            Number of migrations applied
        """
        # Migration discovery: loads all available schema changes from hardcoded definitions
        migrations = self._get_migrations()
        current_version = self.get_current_version()
        applied = 0

        # Sequential migration application: processes versions in order to maintain consistency
        for version, description, upgrade_sql in migrations:
            if version > current_version:
                if self.apply_migration(version, description, upgrade_sql):
                    applied += 1

        if applied == 0:
            logger.info("Database is up to date")
        else:
            logger.info(f"Applied {applied} migration(s)")

        return applied

    def _get_migrations(self) -> list:
        """
        Hardcoded migration definitions - single source of truth for all database schema changes.
        Each migration is immutable once released to ensure consistent database evolution.

        Returns:
            List of (version, description, upgrade_sql) tuples
        """
        # Migration registry: chronologically ordered schema changes with DDL statements
        migrations = []

        # Migration 1: Add orchestration support
        migrations.append(
            (
                1,
                "Add orchestration support fields",
                """
            -- Add orchestration table
            CREATE TABLE IF NOT EXISTS orchestrationdb (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                status TEXT NOT NULL DEFAULT 'pending',
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                started_at TIMESTAMP,
                ended_at TIMESTAMP,
                total_tasks INTEGER DEFAULT 0,
                completed_tasks INTEGER DEFAULT 0,
                failed_tasks INTEGER DEFAULT 0,
                skipped_tasks INTEGER DEFAULT 0
            );
            
            -- Add orchestration fields to tasks
            ALTER TABLE taskdb ADD COLUMN orchestration_id INTEGER REFERENCES orchestrationdb(id);
            ALTER TABLE taskdb ADD COLUMN identifier TEXT;
            ALTER TABLE taskdb ADD COLUMN depends_on TEXT;
            ALTER TABLE taskdb ADD COLUMN initial_delay REAL DEFAULT 0;
            ALTER TABLE taskdb ADD COLUMN dependency_failed_at TIMESTAMP;
            
            -- Add index for orchestration queries
            CREATE INDEX IF NOT EXISTS idx_task_orchestration ON taskdb(orchestration_id);
            CREATE INDEX IF NOT EXISTS idx_task_identifier ON taskdb(identifier);
            """,
            )
        )

        # Migration 2: Add model field to tasks
        migrations.append(
            (
                2,
                "Add model field to tasks",
                """
            ALTER TABLE taskdb ADD COLUMN model TEXT DEFAULT 'sonnet';
            """,
            )
        )

        # Migration 3: Add performance indexes
        migrations.append(
            (
                3,
                "Add performance indexes",
                """
            CREATE INDEX IF NOT EXISTS idx_task_status ON taskdb(status);
            CREATE INDEX IF NOT EXISTS idx_task_created ON taskdb(created_at);
            CREATE INDEX IF NOT EXISTS idx_orch_status ON orchestrationdb(status);
            """,
            )
        )

        # Migration 4: Add retry tracking
        migrations.append(
            (
                4,
                "Add retry tracking fields",
                """
            ALTER TABLE taskdb ADD COLUMN retry_count INTEGER DEFAULT 0;
            ALTER TABLE taskdb ADD COLUMN max_retries INTEGER DEFAULT 3;
            ALTER TABLE taskdb ADD COLUMN last_retry_at TIMESTAMP;
            """,
            )
        )

        return migrations

    def check_schema_compatibility(self) -> bool:
        """
        Check if current schema is compatible with application models.

        Returns:
            True if schema is compatible
        """
        try:
            # Get current schema
            inspector = self.engine.inspect(self.engine)

            # Check for required tables
            required_tables = ["taskdb", "orchestrationdb", "schema_migrations"]
            existing_tables = inspector.get_table_names()

            for table in required_tables:
                if table not in existing_tables:
                    logger.warning(f"Missing required table: {table}")
                    return False

            # Check for required columns in taskdb
            task_columns = [col["name"] for col in inspector.get_columns("taskdb")]
            required_task_columns = [
                "id",
                "status",
                "working_directory",
                "execution_prompt",
                "model",
                "orchestration_id",
                "identifier",
                "depends_on",
            ]

            for col in required_task_columns:
                if col not in task_columns:
                    logger.warning(f"Missing required column in taskdb: {col}")
                    return False

            return True

        except Exception as e:
            logger.error(f"Schema compatibility check failed: {e}")
            return False

    def initialize_fresh_database(self) -> None:
        """Initialize a fresh database with the latest schema."""
        # Create all tables using SQLModel
        SQLModel.metadata.create_all(self.engine)

        # Mark all migrations as applied
        migrations = self._get_migrations()
        if migrations:
            latest_version = max(m[0] for m in migrations)
            with self.engine.begin() as conn:
                conn.execute(
                    text(
                        """
                        INSERT INTO schema_migrations (version, description, applied_at)
                        VALUES (:version, :description, :applied_at)
                    """
                    ),
                    {
                        "version": latest_version,
                        "description": "Initial schema",
                        "applied_at": datetime.utcnow(),
                    },
                )
            logger.info(f"Initialized fresh database at version {latest_version}")


def run_migrations(db_url: str) -> None:
    """
    Run database migrations for the given database.

    Args:
        db_url: Database connection URL
    """
    manager = MigrationManager(db_url)

    # Check if this is a fresh database
    current_version = manager.get_current_version()

    if current_version == 0:
        # Check if tables already exist (legacy database)
        inspector = manager.engine.inspect(manager.engine)
        if "taskdb" in inspector.get_table_names():
            logger.info("Detected existing database without migration tracking")
            # Run migrations to update schema
            manager.run_migrations()
        else:
            logger.info("Initializing fresh database")
            manager.initialize_fresh_database()
    else:
        # Run any pending migrations
        manager.run_migrations()

    # Verify schema compatibility
    if not manager.check_schema_compatibility():
        logger.error("Schema compatibility check failed after migrations")
        raise RuntimeError("Database schema is not compatible with application models")
