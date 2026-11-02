"""Database Initialization & Migration Runner.

Course: BBAT104 - Fundamentals of Total Quality Management (TQM)
Quality Goal: Q05 - Reduce Response Time
"""

import sqlite3
from typing import Optional
from backend.app.config import settings
from backend.app.database.connection import get_db_connection
from backend.app.database.migrations import run_migrations
from backend.app.database.seeder import seed_database
from backend.app.utils.logger import logger


def initialize_database(conn: Optional[sqlite3.Connection] = None, seed: Optional[bool] = None) -> bool:
    """Run migrations and optionally populate demonstration data."""
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

        logger.info(
            f"Configuring SQLite v{sqlite_ver} (journal_mode={journal_mode}, foreign_keys={'ON' if foreign_keys else 'OFF'})"
        )

        # Apply schema migrations
        run_migrations(conn)

        # Maintain system_metadata for Prompt 01 compatibility
        cursor.execute("CREATE TABLE IF NOT EXISTS system_metadata (id INTEGER PRIMARY KEY AUTOINCREMENT, key TEXT UNIQUE, value TEXT, updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP);")
        cursor.execute("INSERT OR REPLACE INTO system_metadata (key, value) VALUES ('schema_stage', 'prompt_01_initialized');")
        conn.commit()

        # Seed demonstration records if requested and permitted by environment configuration
        should_seed = seed if seed is not None else settings.enable_demo_seeding
        if should_seed:
            seed_database(conn)
        else:
            logger.info("Demo seeding skipped (disabled by configuration or production environment mode).")

        # Synchronize Fast Search FTS5 Virtual Index
        try:
            from backend.app.services.search_service import SearchService
            SearchService.rebuild_fts5_index(conn)
        except Exception as e:
            logger.warning(f"Could not initialize FTS5 search index: {e}")

        logger.info("Database schema and data initialized successfully.")
        return True
    finally:
        if should_close:
            conn.close()


if __name__ == "__main__":
    initialize_database()
