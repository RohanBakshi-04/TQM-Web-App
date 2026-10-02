"""Database Migration and Version Tracking Engine.

Course: BBAT104 - Fundamentals of Total Quality Management (TQM)
Quality Goal: Q05 - Reduce Response Time
"""

import sqlite3
from typing import List, Optional
from backend.app.database.connection import get_db_connection
from backend.app.database.indexes import create_initial_indexes
from backend.app.database.schema import initialize_all_tables
from backend.app.utils.logger import logger

MIGRATIONS_TABLE_SQL = """
CREATE TABLE IF NOT EXISTS schema_migrations (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    version TEXT NOT NULL UNIQUE,
    name TEXT NOT NULL,
    applied_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);
"""


def ensure_migrations_table(conn: sqlite3.Connection) -> None:
    """Ensure the schema_migrations tracking table exists."""
    cursor = conn.cursor()
    cursor.execute(MIGRATIONS_TABLE_SQL)
    conn.commit()


def get_applied_migrations(conn: sqlite3.Connection) -> List[str]:
    """Return list of applied migration version identifiers."""
    cursor = conn.cursor()
    cursor.execute("SELECT version FROM schema_migrations ORDER BY id ASC;")
    return [r[0] for r in cursor.fetchall()]


def record_migration(conn: sqlite3.Connection, version: str, name: str) -> None:
    """Log an applied migration into the version tracking table."""
    cursor = conn.cursor()
    cursor.execute(
        "INSERT INTO schema_migrations (version, name) VALUES (?, ?);",
        (version, name)
    )
    conn.commit()


def run_migrations(conn: Optional[sqlite3.Connection] = None) -> List[str]:
    """Execute all pending database schema migrations in atomic order."""
    should_close = False
    if conn is None:
        conn = get_db_connection()
        should_close = True

    applied_now = []
    try:
        ensure_migrations_table(conn)
        applied = set(get_applied_migrations(conn))

        # Migration 001: Comprehensive 39-Table Normalized Relational Schema
        if "001_initial_schema" not in applied:
            logger.info("Applying Migration 001_initial_schema (39 tables & initial indexes)...")
            initialize_all_tables(conn)
            create_initial_indexes(conn)
            record_migration(conn, "001_initial_schema", "Complete 39-Table Normalized Architecture")
            applied_now.append("001_initial_schema")
            logger.info("Migration 001_initial_schema applied successfully.")

        return applied_now
    finally:
        if should_close:
            conn.close()


if __name__ == "__main__":
    run_migrations()
