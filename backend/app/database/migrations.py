"""Database Migration and Version Tracking Engine.

Course: BBAT104 - Fundamentals of Total Quality Management (TQM)
Quality Goal: Q05 - Reduce Response Time
"""

import sqlite3
from typing import List, Optional
from backend.app.database.connection import get_db_connection
from backend.app.database.indexes import create_initial_indexes
from backend.app.database.schema import initialize_all_tables
from backend.app.database.schema_auth import AUTH_TABLES_SQL
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

        # Migration 002: Authentication & Security Tables (Tokens, Resets, Login History)
        if "002_auth_tables" not in applied:
            logger.info("Applying Migration 002_auth_tables (refresh_tokens, password_resets, login_history)...")
            cursor = conn.cursor()
            cursor.executescript(AUTH_TABLES_SQL)
            cursor.execute("CREATE INDEX IF NOT EXISTS idx_refresh_tokens_user ON refresh_tokens(user_id);")
            cursor.execute("CREATE INDEX IF NOT EXISTS idx_refresh_tokens_hash ON refresh_tokens(token_hash);")
            cursor.execute("CREATE INDEX IF NOT EXISTS idx_login_history_user ON login_history(user_id);")
            cursor.execute("CREATE INDEX IF NOT EXISTS idx_login_history_time ON login_history(timestamp);")
            conn.commit()
            record_migration(conn, "002_auth_tables", "Auth Tokens, Password Resets & Login Audit History")
            applied_now.append("002_auth_tables")
            logger.info("Migration 002_auth_tables applied successfully.")

        # Migration 003: Poka-Yoke Room Allocations & Transfer Lifecycle Engine
        if "003_poka_yoke_allocation_tables" not in applied:
            logger.info("Applying Migration 003_poka_yoke_allocation_tables (Poka-Yoke constraints, transfers, lifecycle)...")
            cursor = conn.cursor()

            # Ensure additional lifecycle columns in room_allocations
            col_info = [col[1] for col in cursor.execute("PRAGMA table_info(room_allocations);").fetchall()]
            if "approval_status" not in col_info:
                cursor.execute("ALTER TABLE room_allocations ADD COLUMN approval_status TEXT NOT NULL DEFAULT 'Approved' CHECK(approval_status IN ('Pending', 'Approved', 'Rejected'));")
            if "checkin_date" not in col_info:
                cursor.execute("ALTER TABLE room_allocations ADD COLUMN checkin_date TEXT NULL;")
            if "checkout_date" not in col_info:
                cursor.execute("ALTER TABLE room_allocations ADD COLUMN checkout_date TEXT NULL;")
            if "checkout_reason" not in col_info:
                cursor.execute("ALTER TABLE room_allocations ADD COLUMN checkout_reason TEXT NULL;")

            # Poka-Yoke Database-Enforced Partial Unique Indexes
            cursor.execute("""
                CREATE UNIQUE INDEX IF NOT EXISTS uq_active_bed_allocation 
                ON room_allocations(bed_id) 
                WHERE allocation_status = 'Active';
            """)
            cursor.execute("""
                CREATE UNIQUE INDEX IF NOT EXISTS uq_active_student_allocation 
                ON room_allocations(student_id) 
                WHERE allocation_status = 'Active';
            """)

            # Room Transfers Table
            cursor.execute("""
                CREATE TABLE IF NOT EXISTS room_transfers (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    allocation_id INTEGER NOT NULL REFERENCES room_allocations(id) ON DELETE RESTRICT,
                    student_id INTEGER NOT NULL REFERENCES students(id) ON DELETE RESTRICT,
                    from_bed_id INTEGER NOT NULL REFERENCES beds(id) ON DELETE RESTRICT,
                    to_bed_id INTEGER NOT NULL REFERENCES beds(id) ON DELETE RESTRICT,
                    reason TEXT NOT NULL,
                    status TEXT NOT NULL DEFAULT 'Pending' CHECK(status IN ('Pending', 'Approved', 'Rejected')),
                    requested_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    reviewed_by INTEGER NULL REFERENCES users(id) ON DELETE SET NULL,
                    reviewed_at TIMESTAMP NULL,
                    remarks TEXT DEFAULT '',
                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                );
            """)

            # Performance indexes
            cursor.execute("CREATE INDEX IF NOT EXISTS idx_allocations_student ON room_allocations(student_id);")
            cursor.execute("CREATE INDEX IF NOT EXISTS idx_allocations_room ON room_allocations(room_id);")
            cursor.execute("CREATE INDEX IF NOT EXISTS idx_allocations_bed ON room_allocations(bed_id);")
            cursor.execute("CREATE INDEX IF NOT EXISTS idx_allocations_status ON room_allocations(allocation_status);")
            cursor.execute("CREATE INDEX IF NOT EXISTS idx_transfers_alloc ON room_transfers(allocation_id);")
            cursor.execute("CREATE INDEX IF NOT EXISTS idx_transfers_status ON room_transfers(status);")

            conn.commit()
            record_migration(conn, "003_poka_yoke_allocation_tables", "Poka-Yoke Allocation Constraints & Transfer Lifecycle")
            applied_now.append("003_poka_yoke_allocation_tables")
            logger.info("Migration 003_poka_yoke_allocation_tables applied successfully.")

        return applied_now
    finally:
        if should_close:
            conn.close()


if __name__ == "__main__":
    run_migrations()
