"""SQLite connection manager with WAL mode and foreign key enforcement.

Course: BBAT104 - Fundamentals of TQM
Quality Goal: Q05 - Reduce Response Time
"""

import os
import sqlite3
from typing import Optional
from backend.app.config import settings
from backend.app.utils.logger import logger


def get_db_path(custom_path: Optional[str] = None) -> str:
    """Return absolute path to database, ensuring parent directory exists."""
    path = custom_path or settings.database_path
    if path == ":memory:":
        return ":memory:"
    if not os.path.isabs(path):
        # Resolve relative to root of Hostel Management System Web App
        base_dir = os.path.dirname(os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))
        path = os.path.join(base_dir, path)
    os.makedirs(os.path.dirname(path), exist_ok=True)
    return path


def get_db_connection(db_path: Optional[str] = None) -> sqlite3.Connection:
    """Create and configure a high-performance SQLite connection.

    Q05 Optimization & Reliability PRAGMAs:
    - WAL Mode: Non-blocking concurrent reads and writes.
    - Foreign Keys: Enforced relational consistency.
    - Synchronous=NORMAL: Low transaction latency with ACID guarantees.
    - Busy Timeout: 5000ms prevents lock contention errors.
    """
    path = get_db_path(db_path)
    conn = sqlite3.connect(path, timeout=10.0, check_same_thread=False)
    conn.row_factory = sqlite3.Row

    # Performance and integrity PRAGMAs
    conn.execute("PRAGMA foreign_keys = ON;")
    if settings.enable_sqlite_wal:
        conn.execute("PRAGMA journal_mode = WAL;")
    conn.execute("PRAGMA synchronous = NORMAL;")
    conn.execute("PRAGMA busy_timeout = 5000;")

    return conn
