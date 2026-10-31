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

        # Migration 004: Q05 Fast Search & Database Indexes Optimization
        if "004_q05_search_and_indexes" not in applied:
            logger.info("Applying Migration 004_q05_search_and_indexes (B-Tree composite indexes & FTS5 search engine)...")
            cursor = conn.cursor()

            # 1. High-Performance B-Tree Composite and Single-Column Indexes
            b_tree_indexes = [
                "CREATE INDEX IF NOT EXISTS idx_students_name ON students(first_name, last_name);",
                "CREATE INDEX IF NOT EXISTS idx_rooms_number ON rooms(room_number);",
                "CREATE INDEX IF NOT EXISTS idx_complaints_created_at ON complaints(created_at DESC);",
                "CREATE INDEX IF NOT EXISTS idx_complaints_status_date ON complaints(status, created_at DESC);",
                "CREATE INDEX IF NOT EXISTS idx_maintenance_status ON maintenance_tasks(status);",
                "CREATE INDEX IF NOT EXISTS idx_payments_ref_tx ON payments(payment_reference, transaction_id);",
                "CREATE INDEX IF NOT EXISTS idx_allocations_status_date ON room_allocations(allocation_status, start_date DESC);",
                "CREATE INDEX IF NOT EXISTS idx_hostels_active_type ON hostels(is_active, hostel_type);",
                "CREATE INDEX IF NOT EXISTS idx_visitors_name_phone ON visitors(name, phone);"
            ]
            for idx_sql in b_tree_indexes:
                cursor.execute(idx_sql)

            # 2. SQLite FTS5 Full-Text Virtual Table
            cursor.execute("""
                CREATE VIRTUAL TABLE IF NOT EXISTS search_index_fts USING fts5(
                    entity_type UNINDEXED,
                    entity_id UNINDEXED,
                    title,
                    subtitle,
                    content,
                    tags,
                    hostel_id UNINDEXED,
                    tokenize = 'porter unicode61'
                );
            """)

            conn.commit()
            record_migration(conn, "004_q05_search_and_indexes", "B-Tree Indexes & SQLite FTS5 Full-Text Acceleration")
            applied_now.append("004_q05_search_and_indexes")
            logger.info("Migration 004_q05_search_and_indexes applied successfully.")

        # Migration 005: Complaints Lifecycle & Maintenance Work Orders
        if "005_complaints_and_maintenance_workflow" not in applied:
            logger.info("Applying Migration 005_complaints_and_maintenance_workflow (rebuilding complaints & maintenance schemas)...")
            cursor = conn.cursor()
            cursor.execute("PRAGMA foreign_keys = OFF;")

            # 1. Rebuild complaints table
            cursor.execute("""
                CREATE TABLE complaints_new (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    complaint_id TEXT NOT NULL UNIQUE,
                    student_id INTEGER NOT NULL REFERENCES students(id) ON DELETE CASCADE,
                    room_id INTEGER NULL REFERENCES rooms(id) ON DELETE SET NULL,
                    bed_id INTEGER NULL REFERENCES beds(id) ON DELETE SET NULL,
                    category TEXT NOT NULL CHECK(category IN ('Electrical', 'Plumbing', 'Carpentry', 'Wi-Fi and Internet', 'Cleanliness', 'Water Supply', 'Furniture', 'Security', 'Mess', 'Other', 'Internet')),
                    title TEXT NOT NULL,
                    description TEXT NOT NULL,
                    severity TEXT NOT NULL DEFAULT 'Medium' CHECK(severity IN ('Low', 'Medium', 'High', 'Critical', 'Emergency')),
                    status TEXT NOT NULL DEFAULT 'Submitted' CHECK(status IN ('Submitted', 'Pending', 'Assigned', 'In Progress', 'In_Progress', 'On Hold', 'Resolved', 'Closed', 'Rejected', 'Reopened')),
                    assigned_to INTEGER NULL REFERENCES users(id) ON DELETE SET NULL,
                    attachment_url TEXT NULL,
                    internal_remarks TEXT NULL,
                    rejection_reason TEXT NULL,
                    escalated INTEGER NOT NULL DEFAULT 0,
                    escalated_at TIMESTAMP NULL,
                    escalation_reason TEXT NULL,
                    feedback_rating INTEGER NULL CHECK(feedback_rating IS NULL OR (feedback_rating >= 1 AND feedback_rating <= 5)),
                    feedback_comment TEXT NULL,
                    reopened_count INTEGER NOT NULL DEFAULT 0,
                    affects_occupancy INTEGER NOT NULL DEFAULT 0,
                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    resolved_at TIMESTAMP NULL,
                    closed_at TIMESTAMP NULL
                );
            """)

            old_cols = [c[1] for c in cursor.execute("PRAGMA table_info(complaints);").fetchall()]
            common_cols = [c for c in ['id', 'complaint_id', 'student_id', 'room_id', 'category', 'title', 'description', 'severity', 'status', 'assigned_to', 'created_at', 'resolved_at'] if c in old_cols]
            if common_cols:
                cols_str = ", ".join(common_cols)
                cursor.execute(f"INSERT INTO complaints_new ({cols_str}) SELECT {cols_str} FROM complaints;")

            cursor.execute("DROP TABLE IF EXISTS complaints;")
            cursor.execute("ALTER TABLE complaints_new RENAME TO complaints;")

            # 2. Rebuild maintenance_tasks table
            cursor.execute("""
                CREATE TABLE maintenance_tasks_new (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    task_code TEXT NOT NULL UNIQUE,
                    complaint_id INTEGER NULL REFERENCES complaints(id) ON DELETE SET NULL,
                    room_id INTEGER NULL REFERENCES rooms(id) ON DELETE SET NULL,
                    building_id INTEGER NULL REFERENCES buildings(id) ON DELETE SET NULL,
                    bed_id INTEGER NULL REFERENCES beds(id) ON DELETE SET NULL,
                    category TEXT NOT NULL,
                    title TEXT NOT NULL,
                    description TEXT NOT NULL,
                    priority TEXT NOT NULL DEFAULT 'Medium' CHECK(priority IN ('Low', 'Medium', 'High', 'Critical', 'Urgent')),
                    status TEXT NOT NULL DEFAULT 'Assigned' CHECK(status IN ('Open', 'Assigned', 'Accepted', 'In Progress', 'In_Progress', 'On Hold', 'Completed', 'Verified', 'Cancelled')),
                    assigned_worker TEXT DEFAULT '',
                    assigned_to INTEGER NULL REFERENCES users(id) ON DELETE SET NULL,
                    resolution_notes TEXT DEFAULT '',
                    completion_photo_url TEXT NULL,
                    hold_reason TEXT NULL,
                    deadline TEXT NULL,
                    estimated_cost REAL NOT NULL DEFAULT 0.0 CHECK(estimated_cost >= 0),
                    actual_cost REAL NOT NULL DEFAULT 0.0 CHECK(actual_cost >= 0),
                    scheduled_date TEXT DEFAULT '',
                    verified_by INTEGER NULL REFERENCES users(id) ON DELETE SET NULL,
                    verified_at TIMESTAMP NULL,
                    completed_at TIMESTAMP NULL,
                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                );
            """)

            old_m_cols = [c[1] for c in cursor.execute("PRAGMA table_info(maintenance_tasks);").fetchall()]
            common_m_cols = [c for c in ['id', 'task_code', 'room_id', 'building_id', 'category', 'title', 'description', 'priority', 'status', 'assigned_worker', 'estimated_cost', 'actual_cost', 'scheduled_date', 'completed_at', 'created_at'] if c in old_m_cols]
            if common_m_cols:
                m_cols_str = ", ".join(common_m_cols)
                cursor.execute(f"INSERT INTO maintenance_tasks_new ({m_cols_str}) SELECT {m_cols_str} FROM maintenance_tasks;")

            cursor.execute("DROP TABLE IF EXISTS maintenance_tasks;")
            cursor.execute("ALTER TABLE maintenance_tasks_new RENAME TO maintenance_tasks;")

            # 3. Performance indexes
            cursor.execute("CREATE INDEX IF NOT EXISTS idx_complaints_ticket ON complaints(complaint_id);")
            cursor.execute("CREATE INDEX IF NOT EXISTS idx_complaints_student ON complaints(student_id);")
            cursor.execute("CREATE INDEX IF NOT EXISTS idx_complaints_status ON complaints(status);")
            cursor.execute("CREATE INDEX IF NOT EXISTS idx_complaints_created_at ON complaints(created_at DESC);")
            cursor.execute("CREATE INDEX IF NOT EXISTS idx_complaints_status_date ON complaints(status, created_at DESC);")
            cursor.execute("CREATE INDEX IF NOT EXISTS idx_maintenance_room ON maintenance_tasks(room_id);")
            cursor.execute("CREATE INDEX IF NOT EXISTS idx_maintenance_status ON maintenance_tasks(status);")
            cursor.execute("CREATE INDEX IF NOT EXISTS idx_maintenance_complaint ON maintenance_tasks(complaint_id);")
            cursor.execute("CREATE INDEX IF NOT EXISTS idx_maintenance_assigned ON maintenance_tasks(assigned_to);")

            cursor.execute("PRAGMA foreign_keys = ON;")
            conn.commit()
            record_migration(conn, "005_complaints_and_maintenance_workflow", "Expanded Complaints Lifecycle & Work Order Engine")
            applied_now.append("005_complaints_and_maintenance_workflow")
            logger.info("Migration 005_complaints_and_maintenance_workflow applied successfully.")

        return applied_now
    finally:
        if should_close:
            conn.close()


if __name__ == "__main__":
    run_migrations()
