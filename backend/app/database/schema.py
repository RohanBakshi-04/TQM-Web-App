"""Master Database Schema Aggregator.

Course: BBAT104 - Fundamentals of Total Quality Management (TQM)
Quality Goal: Q05 - Reduce Response Time
"""

import sqlite3
from typing import Optional
from backend.app.database.connection import get_db_connection
from backend.app.database.schema_core import CORE_TABLES_SQL
from backend.app.utils.logger import logger


def get_core_ddl() -> str:
    """Return DDL for core user access and system management tables."""
    return CORE_TABLES_SQL


def initialize_core_tables(conn: Optional[sqlite3.Connection] = None) -> None:
    """Execute creation of core access and system tables."""
    should_close = False
    if conn is None:
        conn = get_db_connection()
        should_close = True

    try:
        cursor = conn.cursor()
        cursor.executescript(CORE_TABLES_SQL)
        conn.commit()
        logger.info("Core database tables initialized successfully.")
    finally:
        if should_close:
            conn.close()
