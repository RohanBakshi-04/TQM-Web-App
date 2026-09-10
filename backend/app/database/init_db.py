"""Database initialization utility.

Course: BBAT104 - Fundamentals of TQM
Quality Goal: Q05 - Reduce Response Time
Note: Business tables belong to Prompt 02. This utility initializes database connectivity and metadata.
"""

import sqlite3
from typing import Optional
from backend.app.database.connection import get_db_connection
from backend.app.utils.logger import logger


INIT_METADATA_SQL = """
CREATE TABLE IF NOT EXISTS system_metadata (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    key TEXT NOT NULL UNIQUE,
    value TEXT NOT NULL,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);
"""


def initialize_database(conn: Optional[sqlite3.Connection] = None) -> bool:
    """Verify SQLite connectivity, apply PRAGMAs, and initialize system metadata."""
    should_close = False
    if conn is None:
        conn = get_db_connection()
        should_close = True

    try:
        cursor = conn.cursor()
        cursor.execute("SELECT sqlite_version();")
        sqlite_ver = cursor.fetchone()[0]

        cursor.execute("PRAGMA journal_mode;")
        journal_mode = cursor.fetchone()[0].upper()

        cursor.execute("PRAGMA foreign_keys;")
        foreign_keys = cursor.fetchone()[0]

        # Initialize base metadata table
        cursor.executescript(INIT_METADATA_SQL)
        cursor.execute(
            """INSERT OR REPLACE INTO system_metadata (key, value)
               VALUES ('schema_stage', 'prompt_01_initialized')"""
        )
        conn.commit()

        logger.info(
            f"Database initialized successfully (SQLite v{sqlite_ver}, "
            f"journal_mode={journal_mode}, foreign_keys={'ON' if foreign_keys else 'OFF'})"
        )
        return True
    except Exception as e:
        logger.error(f"Database initialization failed: {e}")
        raise
    finally:
        if should_close:
            conn.close()


if __name__ == "__main__":
    initialize_database()
