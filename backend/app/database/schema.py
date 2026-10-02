"""Master Database Schema Aggregator.

Course: BBAT104 - Fundamentals of Total Quality Management (TQM)
Quality Goal: Q05 - Reduce Response Time
"""

import sqlite3
from typing import Optional
from backend.app.database.connection import get_db_connection
from backend.app.database.schema_core import CORE_TABLES_SQL
from backend.app.database.schema_hostel_student import HOSTEL_STUDENT_TABLES_SQL
from backend.app.database.schema_operations_finance import OPERATIONS_FINANCE_TABLES_SQL
from backend.app.utils.logger import logger


def get_all_ddl() -> str:
    """Return complete DDL for all 39 tables across all 8 functional domains."""
    return f"{CORE_TABLES_SQL}\n{HOSTEL_STUDENT_TABLES_SQL}\n{OPERATIONS_FINANCE_TABLES_SQL}"


def initialize_core_tables(conn: Optional[sqlite3.Connection] = None) -> None:
    """Execute creation of core user and access management tables."""
    should_close = False
    if conn is None:
        conn = get_db_connection()
        should_close = True

    try:
        cursor = conn.cursor()
        cursor.executescript(CORE_TABLES_SQL)
        conn.commit()
    finally:
        if should_close:
            conn.close()


def initialize_all_tables(conn: Optional[sqlite3.Connection] = None) -> None:
    """Execute creation of all 39 normalized database tables."""
    should_close = False
    if conn is None:
        conn = get_db_connection()
        should_close = True

    try:
        cursor = conn.cursor()
        cursor.executescript(CORE_TABLES_SQL)
        cursor.executescript(HOSTEL_STUDENT_TABLES_SQL)
        cursor.executescript(OPERATIONS_FINANCE_TABLES_SQL)
        conn.commit()
        logger.info("All 39 database tables initialized successfully.")
    finally:
        if should_close:
            conn.close()
