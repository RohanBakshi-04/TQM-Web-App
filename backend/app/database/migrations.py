"""Database Migration and Version Tracking Engine.



Course: BBAT104 - Fundamentals of Total Quality Management (TQM)

Quality Goal: Q05 - Reduce Response Time

"""



import json
from datetime import datetime

import sqlite3

from typing import List, Optional

from backend.app.database.connection import get_db_connection

from backend.app.database.indexes import create_initial_indexes

from backend.app.database.schema import initialize_all_tables

from backend.app.database.schema_auth import AUTH_TABLES_SQL

from backend.app.services.rbac_data import ROLES_LIST, ROLE_METADATA, PERMISSIONS_LIST, ROLE_PERMISSIONS_MAP

from backend.app.utils.logger import logger



MIGRATIONS_TABLE_SQL = """

CREATE TABLE IF NOT EXISTS schema_migrations (

    id INTEGER PRIMARY KEY AUTOINCREMENT,

    version TEXT NOT NULL UNIQUE,

    name TEXT NOT NULL,

    applied_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP

);

"""



HISTORICAL_ORPHAN_ARCHIVES_SQL = """

CREATE TABLE IF NOT EXISTS historical_orphan_archives (

    id INTEGER PRIMARY KEY AUTOINCREMENT,

    source_table TEXT NOT NULL,

    source_record_id INTEGER,

    broken_foreign_key_column TEXT NOT NULL,

    original_referenced_id INTEGER,

    record_payload_json TEXT NOT NULL,

    archival_reason TEXT NOT NULL,

    migration_version TEXT NOT NULL,

    archived_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP

);

CREATE INDEX IF NOT EXISTS idx_orphan_archives_table ON historical_orphan_archives(source_table);

CREATE INDEX IF NOT EXISTS idx_orphan_archives_col ON historical_orphan_archives(broken_foreign_key_column);

"""





def row_to_dict(cursor: sqlite3.Cursor, row: tuple) -> dict:
    """Safely convert a sqlite3 row (Row object or tuple) to a python dictionary."""
    if hasattr(row, 'keys'):
        return {k: row[k] for k in row.keys()}
    if cursor and cursor.description is not None:
        col_names = [d[0] for d in cursor.description]
        return {col_names[i]: row[i] for i in range(min(len(col_names), len(row)))}
    return {}


def archive_orphan_record(
    cursor: sqlite3.Cursor,
    source_table: str,
    source_record_id: Optional[int],
    broken_col: str,
    orig_ref_id: Optional[int],
    payload: dict,
    reason: str,
    migration_version: str
) -> None:
    """Persist historical orphaned record and FK diagnostic metadata prior to remediation."""
    archive_cur = cursor.connection.cursor()
    archive_cur.execute("""
        INSERT INTO historical_orphan_archives (
            source_table, source_record_id, broken_foreign_key_column, original_referenced_id,
            record_payload_json, archival_reason, migration_version
        ) VALUES (?, ?, ?, ?, ?, ?, ?);
    """, (
        source_table,
        source_record_id,
        broken_col,
        orig_ref_id,
        json.dumps(payload, default=str),
        reason,
        migration_version
    ))





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





def begin_migration_transaction(conn: sqlite3.Connection) -> None:
    """Ensure an explicit immediate write transaction is active for atomic DDL/DML execution."""
    if not conn.in_transaction:
        try:
            conn.execute("BEGIN IMMEDIATE;")
        except sqlite3.OperationalError:
            pass


def execute_sql_statements(cursor: sqlite3.Cursor, script_sql: str) -> None:
    """Execute semicolon-delimited SQL statements individually inside the active transaction without implicit COMMIT."""
    statements = [stmt.strip() for stmt in script_sql.split(";") if stmt.strip()]
    for stmt in statements:
        cursor.execute(stmt)


def record_migration(conn: sqlite3.Connection, version: str, name: str, commit: bool = False) -> None:
    """Log an applied migration into the version tracking table inside the current transaction."""
    cursor = conn.cursor()
    cursor.execute(
        "INSERT INTO schema_migrations (version, name) VALUES (?, ?);",
        (version, name)
    )
    if commit:
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
        cursor = conn.cursor()



        # Migration 001: Comprehensive 39-Table Normalized Relational Schema

        if "001_initial_schema" not in applied:
            begin_migration_transaction(conn)

            logger.info("Applying Migration 001_initial_schema (39 tables & initial indexes)...")
            begin_migration_transaction(conn)
            initialize_all_tables(conn)
            create_initial_indexes(conn)
            record_migration(conn, "001_initial_schema", "Complete 39-Table Normalized Architecture", commit=False)
            
            conn.commit()
            applied_now.append("001_initial_schema")
            logger.info("Migration 001_initial_schema applied successfully.")



        # Migration 002: Authentication & Security Tables (Tokens, Resets, Login History)

        if "002_auth_tables" not in applied:
            begin_migration_transaction(conn)

            logger.info("Applying Migration 002_auth_tables (refresh_tokens, password_resets, login_history)...")

            cursor = conn.cursor()

            execute_sql_statements(cursor, AUTH_TABLES_SQL)

            cursor.execute("CREATE INDEX IF NOT EXISTS idx_refresh_tokens_user ON refresh_tokens(user_id);")

            cursor.execute("CREATE INDEX IF NOT EXISTS idx_refresh_tokens_hash ON refresh_tokens(token_hash);")

            cursor.execute("CREATE INDEX IF NOT EXISTS idx_login_history_user ON login_history(user_id);")

            cursor.execute("CREATE INDEX IF NOT EXISTS idx_login_history_time ON login_history(timestamp);")

            record_migration(conn, "002_auth_tables", "Auth Tokens, Password Resets & Login Audit History", commit=False)


            


            conn.commit()

            applied_now.append("002_auth_tables")

            logger.info("Migration 002_auth_tables applied successfully.")



        # Migration 003: Poka-Yoke Room Allocations & Transfer Lifecycle Engine

        if "003_poka_yoke_allocation_tables" not in applied:
            begin_migration_transaction(conn)

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



            record_migration(conn, "003_poka_yoke_allocation_tables", "Poka-Yoke Allocation Constraints & Transfer Lifecycle", commit=False)




            




            conn.commit()

            applied_now.append("003_poka_yoke_allocation_tables")

            logger.info("Migration 003_poka_yoke_allocation_tables applied successfully.")



        # Migration 004: Q05 Fast Search & Database Indexes Optimization

        if "004_q05_search_and_indexes" not in applied:
            begin_migration_transaction(conn)

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



            record_migration(conn, "004_q05_search_and_indexes", "B-Tree Indexes & SQLite FTS5 Full-Text Acceleration", commit=False)




            




            conn.commit()

            applied_now.append("004_q05_search_and_indexes")

            logger.info("Migration 004_q05_search_and_indexes applied successfully.")



        # Migration 005: Complaints Lifecycle & Maintenance Work Orders

        if "005_complaints_and_maintenance_workflow" not in applied:
            begin_migration_transaction(conn)

            logger.info("Applying Migration 005_complaints_and_maintenance_workflow (rebuilding complaints & maintenance schemas)...")

            cursor = conn.cursor()

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

            record_migration(conn, "005_complaints_and_maintenance_workflow", "Expanded Complaints Lifecycle & Work Order Engine", commit=False)


            


            conn.commit()

            applied_now.append("005_complaints_and_maintenance_workflow")

            logger.info("Migration 005_complaints_and_maintenance_workflow applied successfully.")



        # Migration 006: Attendance, Leave & Outpass, and Visitor Management

        if "006_attendance_leave_visitor_enhancements" not in applied:
            begin_migration_transaction(conn)

            logger.info("Applying Migration 006_attendance_leave_visitor_enhancements...")

            cursor = conn.cursor()

            cursor = conn.cursor()

            cursor.execute("PRAGMA foreign_keys = OFF;")



            # 1. Attendance Corrections Table

            cursor.execute("""

                CREATE TABLE IF NOT EXISTS attendance_corrections (

                    id INTEGER PRIMARY KEY AUTOINCREMENT,

                    attendance_id INTEGER NOT NULL REFERENCES attendance(id) ON DELETE CASCADE,

                    student_id INTEGER NOT NULL REFERENCES students(id) ON DELETE CASCADE,

                    previous_status TEXT NOT NULL,

                    new_status TEXT NOT NULL,

                    reason TEXT NOT NULL,

                    corrected_by INTEGER NOT NULL REFERENCES users(id) ON DELETE RESTRICT,

                    corrected_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP

                );

            """)



            # Ensure columns in attendance

            att_cols = [c[1] for c in cursor.execute("PRAGMA table_info(attendance);").fetchall()]

            if "marked_at" not in att_cols:

                cursor.execute("ALTER TABLE attendance ADD COLUMN marked_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP;")



            # 2. Rebuild leave_requests for robust workflow & types

            cursor.execute("""

                CREATE TABLE leave_requests_new (

                    id INTEGER PRIMARY KEY AUTOINCREMENT,

                    student_id INTEGER NOT NULL REFERENCES students(id) ON DELETE CASCADE,

                    leave_type TEXT NOT NULL DEFAULT 'Personal Leave' CHECK(leave_type IN ('Home Leave', 'Personal Leave', 'Medical Leave', 'Emergency Leave', 'Other')),

                    start_date TEXT NOT NULL,

                    end_date TEXT NOT NULL,

                    departure_time TEXT NULL,

                    expected_return_time TEXT NULL,

                    reason TEXT NOT NULL,

                    destination TEXT NOT NULL,

                    emergency_contact TEXT NOT NULL,

                    guardian_contact TEXT NULL,

                    document_url TEXT NULL,

                    status TEXT NOT NULL DEFAULT 'Submitted' CHECK(status IN ('Draft', 'Submitted', 'Under Review', 'Approved', 'Rejected', 'Cancelled')),

                    approved_by INTEGER NULL REFERENCES users(id) ON DELETE SET NULL,

                    rejection_reason TEXT NULL,

                    reviewed_at TIMESTAMP NULL,

                    remarks TEXT DEFAULT '',

                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,

                    CHECK(end_date >= start_date)

                );

            """)

            old_leave_cols = [c[1] for c in cursor.execute("PRAGMA table_info(leave_requests);").fetchall()]

            common_l_cols = [c for c in ['id', 'student_id', 'start_date', 'end_date', 'reason', 'destination', 'emergency_contact', 'status', 'approved_by', 'reviewed_at', 'remarks', 'created_at'] if c in old_leave_cols]

            if common_l_cols:

                l_str = ", ".join(common_l_cols)

                cursor.execute(f"INSERT INTO leave_requests_new ({l_str}) SELECT {l_str} FROM leave_requests;")

            cursor.execute("DROP TABLE IF EXISTS leave_requests;")

            cursor.execute("ALTER TABLE leave_requests_new RENAME TO leave_requests;")



            # 3. Outpasses Table

            cursor.execute("""

                CREATE TABLE IF NOT EXISTS outpasses (

                    id INTEGER PRIMARY KEY AUTOINCREMENT,

                    outpass_number TEXT NOT NULL UNIQUE,

                    leave_request_id INTEGER NOT NULL UNIQUE REFERENCES leave_requests(id) ON DELETE CASCADE,

                    student_id INTEGER NOT NULL REFERENCES students(id) ON DELETE CASCADE,

                    status TEXT NOT NULL DEFAULT 'Issued' CHECK(status IN ('Issued', 'Departed', 'Returned', 'Overdue', 'Cancelled')),

                    expected_exit_time TEXT NOT NULL,

                    expected_return_time TEXT NOT NULL,

                    actual_exit_time TIMESTAMP NULL,

                    actual_return_time TIMESTAMP NULL,

                    exit_verified_by INTEGER NULL REFERENCES users(id) ON DELETE SET NULL,

                    return_verified_by INTEGER NULL REFERENCES users(id) ON DELETE SET NULL,

                    exit_remarks TEXT DEFAULT '',

                    return_remarks TEXT DEFAULT '',

                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP

                );

            """)



            # 4. Enhance visitor_logs table

            cursor.execute("""

                CREATE TABLE visitor_logs_new (

                    id INTEGER PRIMARY KEY AUTOINCREMENT,

                    pass_number TEXT NOT NULL UNIQUE,

                    visitor_id INTEGER NOT NULL REFERENCES visitors(id) ON DELETE CASCADE,

                    student_id INTEGER NOT NULL REFERENCES students(id) ON DELETE CASCADE,

                    hostel_id INTEGER NULL REFERENCES hostels(id) ON DELETE SET NULL,

                    room_id INTEGER NULL REFERENCES rooms(id) ON DELETE SET NULL,

                    check_in_time TIMESTAMP NULL,

                    check_out_time TIMESTAMP NULL,

                    expected_exit_time TIMESTAMP NULL,

                    purpose TEXT NOT NULL,

                    approval_status TEXT NOT NULL DEFAULT 'Approved' CHECK(approval_status IN ('Pending', 'Approved', 'Rejected')),

                    status TEXT NOT NULL DEFAULT 'Approved' CHECK(status IN ('Pending', 'Approved', 'Rejected', 'Checked_In', 'Checked_Out', 'Overdue', 'Cancelled')),

                    approved_by INTEGER NULL REFERENCES users(id) ON DELETE SET NULL,

                    rejection_reason TEXT NULL,

                    remarks TEXT DEFAULT '',

                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP

                );

            """)

            old_vl_cols = [c[1] for c in cursor.execute("PRAGMA table_info(visitor_logs);").fetchall()]

            if 'visitor_id' in old_vl_cols:

                # Copy existing records with generated pass numbers

                existing = cursor.execute("SELECT id, visitor_id, student_id, check_in_time, check_out_time, purpose, approved_by, remarks FROM visitor_logs;").fetchall()

                for row in existing:

                    pass_no = f"VP-LEGACY-{row[0]:04d}"

                    status = 'Checked_Out' if row[4] else ('Checked_In' if row[3] else 'Approved')

                    cursor.execute("""

                        INSERT INTO visitor_logs_new (id, pass_number, visitor_id, student_id, check_in_time, check_out_time, purpose, approved_by, remarks, status, approval_status)

                        VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, 'Approved')

                    """, (row[0], pass_no, row[1], row[2], row[3], row[4], row[5], row[6], row[7], status))

            cursor.execute("DROP TABLE IF EXISTS visitor_logs;")

            cursor.execute("ALTER TABLE visitor_logs_new RENAME TO visitor_logs;")



            # 5. High performance indexes

            cursor.execute("CREATE INDEX IF NOT EXISTS idx_attendance_date ON attendance(date);")

            cursor.execute("CREATE INDEX IF NOT EXISTS idx_attendance_student_date ON attendance(student_id, date);")

            cursor.execute("CREATE INDEX IF NOT EXISTS idx_attendance_status ON attendance(status);")

            cursor.execute("CREATE INDEX IF NOT EXISTS idx_attendance_corrections_att ON attendance_corrections(attendance_id);")

            cursor.execute("CREATE INDEX IF NOT EXISTS idx_leave_student ON leave_requests(student_id);")

            cursor.execute("CREATE INDEX IF NOT EXISTS idx_leave_status ON leave_requests(status);")

            cursor.execute("CREATE INDEX IF NOT EXISTS idx_leave_dates ON leave_requests(start_date, end_date);")

            cursor.execute("CREATE INDEX IF NOT EXISTS idx_outpasses_number ON outpasses(outpass_number);")

            cursor.execute("CREATE INDEX IF NOT EXISTS idx_outpasses_student ON outpasses(student_id);")

            cursor.execute("CREATE INDEX IF NOT EXISTS idx_outpasses_status ON outpasses(status);")

            cursor.execute("CREATE INDEX IF NOT EXISTS idx_outpasses_leave ON outpasses(leave_request_id);")

            cursor.execute("CREATE INDEX IF NOT EXISTS idx_visitor_logs_pass ON visitor_logs(pass_number);")

            cursor.execute("CREATE INDEX IF NOT EXISTS idx_visitor_logs_student ON visitor_logs(student_id);")

            cursor.execute("CREATE INDEX IF NOT EXISTS idx_visitor_logs_visitor ON visitor_logs(visitor_id);")

            cursor.execute("CREATE INDEX IF NOT EXISTS idx_visitor_logs_status ON visitor_logs(status);")



            cursor.execute("PRAGMA foreign_keys = ON;")

            record_migration(conn, "006_attendance_leave_visitor_enhancements", "Attendance Corrections, Outpass Workflow & Visitor Passes", commit=False)


            


            conn.commit()

            applied_now.append("006_attendance_leave_visitor_enhancements")

            logger.info("Migration 006_attendance_leave_visitor_enhancements applied successfully.")



        # ---------------------------------------------------------

        # Migration 007: Fee & Financial Management Enhancements

        # ---------------------------------------------------------

        if "007_fee_and_financial_enhancements" not in applied:
            begin_migration_transaction(conn)

            logger.info("Applying Migration 007_fee_and_financial_enhancements...")

            cursor = conn.cursor()

            cursor = conn.cursor()

            cursor.execute("PRAGMA foreign_keys = OFF;")



            # 1. Enhance fee_structures

            cursor.execute("""

                CREATE TABLE IF NOT EXISTS fee_structures_new (

                    id INTEGER PRIMARY KEY AUTOINCREMENT,

                    name TEXT NOT NULL,

                    fee_category TEXT NOT NULL DEFAULT 'Hostel Accommodation Fee',

                    hostel_id INTEGER NULL REFERENCES hostels(id) ON DELETE SET NULL,

                    room_type TEXT NOT NULL DEFAULT 'All' CHECK(room_type IN ('Single', 'Double', 'Triple', 'Dormitory', 'All')),

                    academic_year TEXT NOT NULL,

                    semester TEXT NOT NULL DEFAULT 'All',

                    amount REAL NOT NULL CHECK(amount >= 0),

                    payment_frequency TEXT NOT NULL DEFAULT 'Semester' CHECK(payment_frequency IN ('Monthly', 'Quarterly', 'Semester', 'Annual', 'One_Time')),

                    is_mandatory INTEGER NOT NULL DEFAULT 1 CHECK(is_mandatory IN (0, 1)),

                    late_fine_amount REAL NOT NULL DEFAULT 0.0 CHECK(late_fine_amount >= 0),

                    description TEXT DEFAULT '',

                    is_active INTEGER NOT NULL DEFAULT 1 CHECK(is_active IN (0, 1)),

                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,

                    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP

                );

            """)

            old_fs_cols = [c[1] for c in cursor.execute("PRAGMA table_info(fee_structures);").fetchall()]

            common_fs = [c for c in ['id', 'name', 'room_type', 'academic_year', 'semester', 'amount', 'payment_frequency', 'description', 'is_active', 'created_at', 'updated_at'] if c in old_fs_cols]

            if common_fs:

                c_str = ", ".join(common_fs)

                cursor.execute(f"INSERT INTO fee_structures_new ({c_str}) SELECT {c_str} FROM fee_structures;")

            cursor.execute("DROP TABLE IF EXISTS fee_structures;")

            cursor.execute("ALTER TABLE fee_structures_new RENAME TO fee_structures;")



            # 2. Enhance invoices

            cursor.execute("""

                CREATE TABLE IF NOT EXISTS invoices_new (

                    id INTEGER PRIMARY KEY AUTOINCREMENT,

                    invoice_number TEXT NOT NULL UNIQUE,

                    student_id INTEGER NOT NULL REFERENCES students(id) ON DELETE RESTRICT,

                    fee_structure_id INTEGER NULL REFERENCES fee_structures(id) ON DELETE SET NULL,

                    issue_date TEXT NOT NULL,

                    due_date TEXT NOT NULL,

                    total_amount REAL NOT NULL CHECK(total_amount >= 0),

                    paid_amount REAL NOT NULL DEFAULT 0.0 CHECK(paid_amount >= 0),

                    discount_amount REAL NOT NULL DEFAULT 0.0 CHECK(discount_amount >= 0),

                    discount_reason TEXT DEFAULT '',

                    fine_amount REAL NOT NULL DEFAULT 0.0 CHECK(fine_amount >= 0),

                    status TEXT NOT NULL DEFAULT 'Issued' CHECK(status IN ('Draft', 'Issued', 'Unpaid', 'Partially_Paid', 'Partially Paid', 'Paid', 'Cancelled', 'Overdue')),

                    cancellation_reason TEXT DEFAULT '',

                    remarks TEXT DEFAULT '',

                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,

                    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,

                    CHECK(due_date >= issue_date)

                );

            """)

            old_inv_cols = [c[1] for c in cursor.execute("PRAGMA table_info(invoices);").fetchall()]

            common_inv = [c for c in ['id', 'invoice_number', 'student_id', 'fee_structure_id', 'issue_date', 'due_date', 'total_amount', 'paid_amount', 'status', 'created_at', 'updated_at'] if c in old_inv_cols]

            if common_inv:

                c_str = ", ".join(common_inv)

                cursor.execute(f"INSERT INTO invoices_new ({c_str}) SELECT {c_str} FROM invoices;")

            cursor.execute("DROP TABLE IF EXISTS invoices;")

            cursor.execute("ALTER TABLE invoices_new RENAME TO invoices;")



            # 3. Enhance payments

            cursor.execute("""

                CREATE TABLE IF NOT EXISTS payments_new (

                    id INTEGER PRIMARY KEY AUTOINCREMENT,

                    payment_reference TEXT NOT NULL UNIQUE,

                    invoice_id INTEGER NOT NULL REFERENCES invoices(id) ON DELETE RESTRICT,

                    student_id INTEGER NOT NULL REFERENCES students(id) ON DELETE RESTRICT,

                    amount REAL NOT NULL CHECK(amount > 0),

                    payment_method TEXT NOT NULL CHECK(payment_method IN ('UPI', 'Credit_Card', 'Debit_Card', 'Net_Banking', 'Cash', 'Demand_Draft', 'Demand Draft', 'Card', 'Bank Transfer', 'Bank_Transfer', 'Cheque', 'Other')),

                    payment_date TEXT NOT NULL,

                    transaction_id TEXT DEFAULT '',

                    receipt_number TEXT NULL,

                    status TEXT NOT NULL DEFAULT 'Completed' CHECK(status IN ('Completed', 'Pending', 'Failed', 'Refunded', 'Reversed')),

                    notes TEXT DEFAULT '',

                    reversal_reason TEXT DEFAULT '',

                    reversed_by INTEGER NULL REFERENCES users(id) ON DELETE SET NULL,

                    recorded_by INTEGER NULL REFERENCES users(id) ON DELETE SET NULL,

                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP

                );

            """)

            old_pay_cols = [c[1] for c in cursor.execute("PRAGMA table_info(payments);").fetchall()]

            common_pay = [c for c in ['id', 'payment_reference', 'invoice_id', 'student_id', 'amount', 'payment_method', 'payment_date', 'transaction_id', 'status', 'notes', 'recorded_by', 'created_at'] if c in old_pay_cols]

            if common_pay:

                c_str = ", ".join(common_pay)

                cursor.execute(f"INSERT INTO payments_new ({c_str}) SELECT {c_str} FROM payments;")

            cursor.execute("DROP TABLE IF EXISTS payments;")

            cursor.execute("ALTER TABLE payments_new RENAME TO payments;")



            # 4. Enhance refunds

            cursor.execute("""

                CREATE TABLE IF NOT EXISTS refunds_new (

                    id INTEGER PRIMARY KEY AUTOINCREMENT,

                    refund_reference TEXT NOT NULL UNIQUE,

                    payment_id INTEGER NOT NULL REFERENCES payments(id) ON DELETE RESTRICT,

                    invoice_id INTEGER NULL REFERENCES invoices(id) ON DELETE SET NULL,

                    student_id INTEGER NULL REFERENCES students(id) ON DELETE SET NULL,

                    amount REAL NOT NULL CHECK(amount > 0),

                    reason TEXT NOT NULL,

                    refund_method TEXT NOT NULL DEFAULT 'Bank_Transfer',

                    rejection_reason TEXT DEFAULT '',

                    status TEXT NOT NULL DEFAULT 'Requested' CHECK(status IN ('Requested', 'Initiated', 'Under_Review', 'Under Review', 'Approved', 'Rejected', 'Processed', 'Cancelled')),

                    requested_by INTEGER NULL REFERENCES users(id) ON DELETE SET NULL,

                    reviewed_by INTEGER NULL REFERENCES users(id) ON DELETE SET NULL,

                    approved_by INTEGER NULL REFERENCES users(id) ON DELETE SET NULL,

                    processed_by INTEGER NULL REFERENCES users(id) ON DELETE SET NULL,

                    transaction_reference TEXT DEFAULT '',

                    processed_at TIMESTAMP NULL,

                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP

                );

            """)

            old_ref_cols = [c[1] for c in cursor.execute("PRAGMA table_info(refunds);").fetchall()]

            common_ref = [c for c in ['id', 'refund_reference', 'payment_id', 'amount', 'reason', 'status', 'approved_by', 'processed_at', 'created_at'] if c in old_ref_cols]

            if common_ref:

                c_str = ", ".join(common_ref)

                cursor.execute(f"INSERT INTO refunds_new ({c_str}) SELECT {c_str} FROM refunds;")

            cursor.execute("DROP TABLE IF EXISTS refunds;")

            cursor.execute("ALTER TABLE refunds_new RENAME TO refunds;")



            # 5. Financial B-Tree Indexes

            cursor.execute("CREATE INDEX IF NOT EXISTS idx_fee_structures_hostel ON fee_structures(hostel_id);")

            cursor.execute("CREATE INDEX IF NOT EXISTS idx_fee_structures_category ON fee_structures(fee_category);")

            cursor.execute("CREATE INDEX IF NOT EXISTS idx_fee_structures_year ON fee_structures(academic_year, is_active);")

            cursor.execute("CREATE INDEX IF NOT EXISTS idx_invoices_student ON invoices(student_id);")

            cursor.execute("CREATE INDEX IF NOT EXISTS idx_invoices_status ON invoices(status);")

            cursor.execute("CREATE INDEX IF NOT EXISTS idx_invoices_due ON invoices(due_date);")

            cursor.execute("CREATE INDEX IF NOT EXISTS idx_invoices_number ON invoices(invoice_number);")

            cursor.execute("CREATE INDEX IF NOT EXISTS idx_payments_invoice ON payments(invoice_id);")

            cursor.execute("CREATE INDEX IF NOT EXISTS idx_payments_student ON payments(student_id);")

            cursor.execute("CREATE INDEX IF NOT EXISTS idx_payments_ref ON payments(payment_reference);")

            cursor.execute("CREATE INDEX IF NOT EXISTS idx_payments_date ON payments(payment_date);")

            cursor.execute("CREATE INDEX IF NOT EXISTS idx_refunds_payment ON refunds(payment_id);")

            cursor.execute("CREATE INDEX IF NOT EXISTS idx_refunds_status ON refunds(status);")



            cursor.execute("PRAGMA foreign_keys = ON;")

            record_migration(conn, "007_fee_and_financial_enhancements", "Fee Structures, Invoicing, Payments & Refund Workflows", commit=False)


            


            conn.commit()

            applied_now.append("007_fee_and_financial_enhancements")

            logger.info("Migration 007_fee_and_financial_enhancements applied successfully.")





        # =========================================================================

        # MIGRATION 008: Mess & Inventory Operations

        # =========================================================================

        if "008_mess_and_inventory_enhancements" not in applied:
            begin_migration_transaction(conn)

            logger.info("Applying Migration 008_mess_and_inventory_enhancements...")

            cursor = conn.cursor()

            cursor = conn.cursor()

            cursor.execute("PRAGMA foreign_keys = OFF;")



            # 1. Suppliers Table

            cursor.execute("""

                CREATE TABLE IF NOT EXISTS suppliers (

                    id INTEGER PRIMARY KEY AUTOINCREMENT,

                    name TEXT NOT NULL UNIQUE,

                    contact_person TEXT DEFAULT '',

                    phone TEXT DEFAULT '',

                    email TEXT DEFAULT '',

                    address TEXT DEFAULT '',

                    category TEXT DEFAULT 'General',

                    is_active INTEGER NOT NULL DEFAULT 1 CHECK(is_active IN (0, 1)),

                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,

                    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP

                );

            """)



            # 2. Enhance mess_menus

            cursor.execute("""

                CREATE TABLE IF NOT EXISTS mess_menus_new (

                    id INTEGER PRIMARY KEY AUTOINCREMENT,

                    hostel_id INTEGER NULL REFERENCES hostels(id) ON DELETE CASCADE,

                    menu_date TEXT NULL,

                    day_of_week TEXT NOT NULL CHECK(day_of_week IN ('Monday', 'Tuesday', 'Wednesday', 'Thursday', 'Friday', 'Saturday', 'Sunday')),

                    meal_type TEXT NOT NULL CHECK(meal_type IN ('Breakfast', 'Lunch', 'Evening Snacks', 'Snacks', 'Dinner')),

                    title TEXT DEFAULT '',

                    items_description TEXT NOT NULL,

                    items TEXT NOT NULL DEFAULT '[]',

                    start_time TEXT DEFAULT '',

                    end_time TEXT DEFAULT '',

                    is_special INTEGER NOT NULL DEFAULT 0 CHECK(is_special IN (0, 1)),

                    status TEXT NOT NULL DEFAULT 'Published' CHECK(status IN ('Draft', 'Published', 'Cancelled')),

                    cancelled_reason TEXT DEFAULT '',

                    created_by INTEGER NULL REFERENCES users(id) ON DELETE SET NULL,

                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,

                    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP

                );

            """)

            old_mm_cols = [c[1] for c in cursor.execute("PRAGMA table_info(mess_menus);").fetchall()]

            common_mm = [c for c in ['id', 'day_of_week', 'meal_type', 'items_description', 'is_special', 'created_at', 'updated_at'] if c in old_mm_cols]

            if common_mm:

                c_str = ", ".join(common_mm)

                cursor.execute(f"INSERT INTO mess_menus_new ({c_str}) SELECT {c_str} FROM mess_menus;")

            cursor.execute("DROP TABLE IF EXISTS mess_menus;")

            cursor.execute("ALTER TABLE mess_menus_new RENAME TO mess_menus;")



            # 3. Enhance mess_subscriptions

            cursor.execute("""

                CREATE TABLE IF NOT EXISTS mess_subscriptions_new (

                    id INTEGER PRIMARY KEY AUTOINCREMENT,

                    subscription_reference TEXT NOT NULL UNIQUE,

                    student_id INTEGER NOT NULL REFERENCES students(id) ON DELETE RESTRICT,

                    hostel_id INTEGER NULL REFERENCES hostels(id) ON DELETE SET NULL,

                    plan_type TEXT NOT NULL CHECK(plan_type IN ('Monthly', 'Semester', 'Custom', 'Annual')),

                    diet_type TEXT NOT NULL DEFAULT 'Regular' CHECK(diet_type IN ('Regular', 'Vegetarian', 'Non-Vegetarian', 'Jain', 'Special')),

                    start_date TEXT NOT NULL,

                    end_date TEXT NOT NULL,

                    monthly_fee REAL NOT NULL CHECK(monthly_fee >= 0),

                    total_fee REAL NOT NULL DEFAULT 0.0 CHECK(total_fee >= 0),

                    status TEXT NOT NULL DEFAULT 'Active' CHECK(status IN ('Pending', 'Active', 'Suspended', 'Expired', 'Cancelled')),

                    invoice_id INTEGER NULL REFERENCES invoices(id) ON DELETE SET NULL,

                    is_exempted INTEGER NOT NULL DEFAULT 0 CHECK(is_exempted IN (0, 1)),

                    exemption_reason TEXT DEFAULT '',

                    remarks TEXT DEFAULT '',

                    approved_by INTEGER NULL REFERENCES users(id) ON DELETE SET NULL,

                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,

                    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,

                    CHECK(end_date >= start_date)

                );

            """)

            old_sub_cols = [c[1] for c in cursor.execute("PRAGMA table_info(mess_subscriptions);").fetchall()]

            if 'id' in old_sub_cols:

                cursor.execute("""

                    INSERT INTO mess_subscriptions_new (

                        id, subscription_reference, student_id, plan_type, start_date, end_date,

                        monthly_fee, total_fee, status, created_at, updated_at

                    )

                    SELECT

                        id, 'SUB-LEGACY-' || id, student_id, plan_type, start_date, end_date,

                        monthly_fee, monthly_fee, status, created_at, updated_at

                    FROM mess_subscriptions;

                """)

            cursor.execute("DROP TABLE IF EXISTS mess_subscriptions;")

            cursor.execute("ALTER TABLE mess_subscriptions_new RENAME TO mess_subscriptions;")



            # 4. Enhance meal_attendance

            cursor.execute("""

                CREATE TABLE IF NOT EXISTS meal_attendance_new (

                    id INTEGER PRIMARY KEY AUTOINCREMENT,

                    student_id INTEGER NOT NULL REFERENCES students(id) ON DELETE RESTRICT,

                    subscription_id INTEGER NULL REFERENCES mess_subscriptions(id) ON DELETE SET NULL,

                    hostel_id INTEGER NULL REFERENCES hostels(id) ON DELETE SET NULL,

                    date TEXT NOT NULL,

                    meal_type TEXT NOT NULL CHECK(meal_type IN ('Breakfast', 'Lunch', 'Evening Snacks', 'Snacks', 'Dinner')),

                    verification_method TEXT NOT NULL DEFAULT 'Manual' CHECK(verification_method IN ('Manual', 'QR_Scan', 'Biometric', 'RFID')),

                    status TEXT NOT NULL DEFAULT 'Present' CHECK(status IN ('Present', 'Absent', 'Corrected', 'Cancelled')),

                    marked_by INTEGER NULL REFERENCES users(id) ON DELETE SET NULL,

                    correction_reason TEXT DEFAULT '',

                    corrected_by INTEGER NULL REFERENCES users(id) ON DELETE SET NULL,

                    marked_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,

                    UNIQUE(student_id, date, meal_type)

                );

            """)

            old_att_cols = [c[1] for c in cursor.execute("PRAGMA table_info(meal_attendance);").fetchall()]

            common_att = [c for c in ['id', 'student_id', 'date', 'meal_type', 'marked_at'] if c in old_att_cols]

            if common_att:

                c_str = ", ".join(common_att)

                cursor.execute(f"INSERT OR IGNORE INTO meal_attendance_new ({c_str}) SELECT {c_str} FROM meal_attendance;")

            cursor.execute("DROP TABLE IF EXISTS meal_attendance;")

            cursor.execute("ALTER TABLE meal_attendance_new RENAME TO meal_attendance;")



            # 5. Enhance inventory_categories default records

            default_cats = [

                ("Food Grains", "Rice, wheat, pulses, oats, and cereals"),

                ("Vegetables", "Fresh vegetables, tubers, and greens"),

                ("Fruits", "Fresh seasonal fruits"),

                ("Dairy Products", "Milk, curd, paneer, butter, and cheese"),

                ("Cooking Oil and Spices", "Edible oils, ghee, ground spices, and herbs"),

                ("Cleaning Supplies", "Detergents, floor cleaners, disinfectants, and sanitizers"),

                ("Kitchen Equipment", "Utensils, cookers, pans, and appliances"),

                ("Furniture", "Beds, study tables, chairs, and cupboards"),

                ("Maintenance Materials", "Pipes, plumbing fixtures, cement, and paint"),

                ("Other", "Miscellaneous institutional hostel items")

            ]

            for cat_name, cat_desc in default_cats:

                cursor.execute("""

                    INSERT INTO inventory_categories (name, description)

                    SELECT ?, ? WHERE NOT EXISTS (SELECT 1 FROM inventory_categories WHERE name = ?);

                """, (cat_name, cat_desc, cat_name))



            # 6. Enhance inventory_items

            cursor.execute("""

                CREATE TABLE IF NOT EXISTS inventory_items_new (

                    id INTEGER PRIMARY KEY AUTOINCREMENT,

                    item_code TEXT NOT NULL UNIQUE,

                    name TEXT NOT NULL,

                    category_id INTEGER NOT NULL REFERENCES inventory_categories(id) ON DELETE RESTRICT,

                    supplier_id INTEGER NULL REFERENCES suppliers(id) ON DELETE SET NULL,

                    hostel_id INTEGER NULL REFERENCES hostels(id) ON DELETE SET NULL,

                    description TEXT DEFAULT '',

                    unit TEXT NOT NULL,

                    quantity_in_stock REAL NOT NULL DEFAULT 0.0 CHECK(quantity_in_stock >= 0),

                    min_reorder_level REAL NOT NULL DEFAULT 0.0 CHECK(min_reorder_level >= 0),

                    max_stock_threshold REAL NULL,

                    unit_price REAL NOT NULL DEFAULT 0.0 CHECK(unit_price >= 0),

                    storage_location TEXT NOT NULL DEFAULT 'Main Store',

                    expiry_date TEXT NULL,

                    status TEXT NOT NULL DEFAULT 'Active' CHECK(status IN ('Active', 'Available', 'Inactive', 'Discontinued', 'Low_Stock', 'Out_of_Stock')),

                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,

                    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP

                );

            """)

            old_item_cols = [c[1] for c in cursor.execute("PRAGMA table_info(inventory_items);").fetchall()]

            common_items = [c for c in ['id', 'category_id', 'item_code', 'name', 'description', 'unit', 'quantity_in_stock', 'min_reorder_level', 'unit_price', 'status', 'created_at', 'updated_at'] if c in old_item_cols]

            if common_items:

                c_str = ", ".join(common_items)

                cursor.execute(f"INSERT INTO inventory_items_new ({c_str}) SELECT {c_str} FROM inventory_items;")

            cursor.execute("DROP TABLE IF EXISTS inventory_items;")

            cursor.execute("ALTER TABLE inventory_items_new RENAME TO inventory_items;")



            # 7. Enhance inventory_transactions

            cursor.execute("""

                CREATE TABLE IF NOT EXISTS inventory_transactions_new (

                    id INTEGER PRIMARY KEY AUTOINCREMENT,

                    transaction_reference TEXT NOT NULL UNIQUE,

                    item_id INTEGER NOT NULL REFERENCES inventory_items(id) ON DELETE RESTRICT,

                    transaction_type TEXT NOT NULL CHECK(transaction_type IN ('Stock_In', 'Stock_Out', 'Adjustment', 'Transfer', 'Damaged', 'Wastage', 'Expired')),

                    quantity REAL NOT NULL CHECK(quantity > 0),

                    unit_price REAL NOT NULL DEFAULT 0.0 CHECK(unit_price >= 0),

                    total_amount REAL NOT NULL DEFAULT 0.0 CHECK(total_amount >= 0),

                    supplier_id INTEGER NULL REFERENCES suppliers(id) ON DELETE SET NULL,

                    invoice_reference TEXT DEFAULT '',

                    purchase_date TEXT NULL,

                    department_destination TEXT DEFAULT '',

                    purpose TEXT DEFAULT '',

                    issued_to_user INTEGER NULL REFERENCES users(id) ON DELETE SET NULL,

                    source_location TEXT DEFAULT '',

                    target_location TEXT DEFAULT '',

                    adjustment_reason TEXT DEFAULT '',

                    approval_status TEXT NOT NULL DEFAULT 'Approved' CHECK(approval_status IN ('Pending_Approval', 'Approved', 'Rejected')),

                    approved_by INTEGER NULL REFERENCES users(id) ON DELETE SET NULL,

                    related_maintenance_task_id INTEGER NULL REFERENCES maintenance_tasks(id) ON DELETE SET NULL,

                    performed_by INTEGER NULL REFERENCES users(id) ON DELETE SET NULL,

                    notes TEXT DEFAULT '',

                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP

                );

            """)

            old_tx_cols = [c[1] for c in cursor.execute("PRAGMA table_info(inventory_transactions);").fetchall()]

            if 'id' in old_tx_cols:

                cursor.execute("""

                    INSERT INTO inventory_transactions_new (

                        id, transaction_reference, item_id, transaction_type, quantity,

                        unit_price, total_amount, related_maintenance_task_id, performed_by, notes, created_at

                    )

                    SELECT

                        id, 'TX-LEGACY-' || id, item_id, transaction_type, quantity,

                        unit_price, ROUND(quantity * unit_price, 2), related_maintenance_task_id, performed_by, notes, created_at

                    FROM inventory_transactions;

                """)

            cursor.execute("DROP TABLE IF EXISTS inventory_transactions;")

            cursor.execute("ALTER TABLE inventory_transactions_new RENAME TO inventory_transactions;")



            # 8. Composite B-Tree Indexes

            cursor.execute("CREATE INDEX IF NOT EXISTS idx_mess_menus_hostel ON mess_menus(hostel_id);")

            cursor.execute("CREATE INDEX IF NOT EXISTS idx_mess_menus_date ON mess_menus(menu_date);")

            cursor.execute("CREATE INDEX IF NOT EXISTS idx_mess_menus_day_meal ON mess_menus(day_of_week, meal_type);")

            cursor.execute("CREATE INDEX IF NOT EXISTS idx_mess_subs_student ON mess_subscriptions(student_id);")

            cursor.execute("CREATE INDEX IF NOT EXISTS idx_mess_subs_status ON mess_subscriptions(status);")

            cursor.execute("CREATE INDEX IF NOT EXISTS idx_mess_subs_dates ON mess_subscriptions(start_date, end_date);")

            cursor.execute("CREATE INDEX IF NOT EXISTS idx_meal_att_student_date ON meal_attendance(student_id, date);")

            cursor.execute("CREATE INDEX IF NOT EXISTS idx_meal_att_date_meal ON meal_attendance(date, meal_type);")

            cursor.execute("CREATE INDEX IF NOT EXISTS idx_inv_items_code ON inventory_items(item_code);")

            cursor.execute("CREATE INDEX IF NOT EXISTS idx_inv_items_cat ON inventory_items(category_id);")

            cursor.execute("CREATE INDEX IF NOT EXISTS idx_inv_items_stock ON inventory_items(quantity_in_stock);")

            cursor.execute("CREATE INDEX IF NOT EXISTS idx_inv_items_expiry ON inventory_items(expiry_date);")

            cursor.execute("CREATE INDEX IF NOT EXISTS idx_inv_tx_item ON inventory_transactions(item_id);")

            cursor.execute("CREATE INDEX IF NOT EXISTS idx_inv_tx_type ON inventory_transactions(transaction_type);")

            cursor.execute("CREATE INDEX IF NOT EXISTS idx_inv_tx_date ON inventory_transactions(created_at);")

            cursor.execute("CREATE INDEX IF NOT EXISTS idx_suppliers_name ON suppliers(name);")



            cursor.execute("PRAGMA foreign_keys = ON;")

            record_migration(conn, "008_mess_and_inventory_enhancements", "Mess Menus, Subscriptions, Meal Attendance, Inventory & Suppliers", commit=False)


            


            conn.commit()

            applied_now.append("008_mess_and_inventory_enhancements")

            logger.info("Migration 008_mess_and_inventory_enhancements applied successfully.")



        # Migration 009: Notifications, Announcements & System Administration Enhancements

        if "009_notifications_announcements_and_admin_enhancements" not in applied:
            begin_migration_transaction(conn)

            logger.info("Applying Migration 009_notifications_announcements_and_admin_enhancements...")

            cursor = conn.cursor()

            cursor.execute("PRAGMA foreign_keys = OFF;")



            # 1. Enhance notifications table

            cursor.execute("PRAGMA table_info(notifications);")

            notif_cols = [c[1] for c in cursor.fetchall()]

            if "category" not in notif_cols:

                cursor.execute("ALTER TABLE notifications ADD COLUMN category TEXT DEFAULT 'general';")

            if "priority" not in notif_cols:

                cursor.execute("ALTER TABLE notifications ADD COLUMN priority TEXT DEFAULT 'Normal';")

            if "related_entity_type" not in notif_cols:

                cursor.execute("ALTER TABLE notifications ADD COLUMN related_entity_type TEXT DEFAULT '';")

            if "related_entity_id" not in notif_cols:

                cursor.execute("ALTER TABLE notifications ADD COLUMN related_entity_id TEXT DEFAULT '';")

            if "event_key" not in notif_cols:

                cursor.execute("ALTER TABLE notifications ADD COLUMN event_key TEXT DEFAULT '';")

            if "delivery_channel" not in notif_cols:

                cursor.execute("ALTER TABLE notifications ADD COLUMN delivery_channel TEXT DEFAULT 'in_app';")



            # 2. Create notification_preferences table

            cursor.execute("""

                CREATE TABLE IF NOT EXISTS notification_preferences (

                    id INTEGER PRIMARY KEY AUTOINCREMENT,

                    user_id INTEGER NOT NULL UNIQUE REFERENCES users(id) ON DELETE CASCADE,

                    in_app_enabled INTEGER DEFAULT 1 CHECK(in_app_enabled IN (0, 1)),

                    email_enabled INTEGER DEFAULT 0 CHECK(email_enabled IN (0, 1)),

                    browser_enabled INTEGER DEFAULT 0 CHECK(browser_enabled IN (0, 1)),

                    disabled_categories TEXT DEFAULT '[]',

                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,

                    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP

                );

            """)



            # 3. Enhance announcements table schema

            cursor.execute("""

                CREATE TABLE IF NOT EXISTS announcements_new (

                    id INTEGER PRIMARY KEY AUTOINCREMENT,

                    title TEXT NOT NULL,

                    content TEXT NOT NULL,

                    category TEXT NOT NULL DEFAULT 'General Notice',

                    priority TEXT NOT NULL DEFAULT 'Normal' CHECK(priority IN ('Low', 'Normal', 'High', 'Critical', 'Emergency', 'low', 'normal', 'high', 'urgent')),

                    target_audience TEXT NOT NULL DEFAULT 'All Users',

                    target_hostel_id INTEGER NULL REFERENCES hostels(id) ON DELETE SET NULL,

                    target_roles TEXT DEFAULT '',

                    status TEXT NOT NULL DEFAULT 'Published' CHECK(status IN ('Draft', 'Scheduled', 'Published', 'Expired', 'Archived')),

                    publish_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,

                    expires_at TIMESTAMP NULL,

                    attachment_url TEXT DEFAULT '',

                    attachment_name TEXT DEFAULT '',

                    created_by INTEGER NULL REFERENCES users(id) ON DELETE SET NULL,

                    published_by INTEGER NULL REFERENCES users(id) ON DELETE SET NULL,

                    published_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,

                    archived_at TIMESTAMP NULL,

                    archived_by INTEGER NULL REFERENCES users(id) ON DELETE SET NULL,

                    is_active INTEGER NOT NULL DEFAULT 1 CHECK(is_active IN (0, 1)),

                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP

                );

            """)

            cursor.execute("""

                INSERT INTO announcements_new (

                    id, title, content, target_audience, priority, published_by, published_at, expires_at, is_active, created_at

                )

                SELECT id, title, content, target_audience, priority, published_by, published_at, expires_at, is_active, created_at

                FROM announcements;

            """)

            cursor.execute("DROP TABLE IF EXISTS announcements;")

            cursor.execute("ALTER TABLE announcements_new RENAME TO announcements;")



            # 4. Create announcement_views table

            cursor.execute("""

                CREATE TABLE IF NOT EXISTS announcement_views (

                    id INTEGER PRIMARY KEY AUTOINCREMENT,

                    announcement_id INTEGER NOT NULL REFERENCES announcements(id) ON DELETE CASCADE,

                    user_id INTEGER NOT NULL REFERENCES users(id) ON DELETE CASCADE,

                    viewed_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,

                    acknowledged_at TIMESTAMP NULL,

                    UNIQUE(announcement_id, user_id)

                );

            """)



            # 5. Create system_setting_history table

            cursor.execute("""

                CREATE TABLE IF NOT EXISTS system_setting_history (

                    id INTEGER PRIMARY KEY AUTOINCREMENT,

                    setting_key TEXT NOT NULL,

                    old_value TEXT,

                    new_value TEXT NOT NULL,

                    changed_by INTEGER NULL REFERENCES users(id) ON DELETE SET NULL,

                    reason TEXT DEFAULT '',

                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP

                );

            """)



            # 6. Seed standard system settings

            standard_settings = [

                ('app_name', 'Hostel Management System TQM', 'general', 'Application display name'),

                ('institution_name', 'University College of Engineering', 'general', 'Institute name'),

                ('institution_contact', '+91-20-25507000, contact@uce.edu.in', 'general', 'Institute official contact details'),

                ('institution_logo', '/static/img/logo.png', 'general', 'Institution logo URL'),

                ('default_timezone', 'Asia/Kolkata', 'localization', 'Default system timezone'),

                ('date_format', 'YYYY-MM-DD', 'localization', 'Standard date display format'),

                ('time_format', 'HH:mm', 'localization', 'Standard time display format'),

                ('currency', 'INR', 'finance', 'Standard billing currency'),

                ('currency_symbol', '₹', 'finance', 'Billing currency symbol'),

                ('academic_session', '2026-27', 'academic', 'Current academic operational session'),

                ('admission_auto_approval', 'false', 'admission', 'Enable automatic admission review approval'),

                ('max_applications_per_student', '1', 'admission', 'Maximum active admission applications per candidate'),

                ('auto_allocation_enabled', 'true', 'allocation', 'Allow algorithmic smart room suggestions'),

                ('room_transfer_cooldown_days', '14', 'allocation', 'Minimum days before subsequent room transfer request'),

                ('attendance_cutoff_time', '22:00', 'attendance', 'Nightly attendance curfew reporting cutoff'),

                ('min_attendance_percentage', '75.0', 'attendance', 'Minimum academic attendance threshold'),

                ('max_leave_duration_days', '15', 'leave', 'Maximum permissible consecutive leave span'),

                ('require_parent_consent', 'true', 'leave', 'Require guardian verification for overnight leaves'),

                ('visiting_hours_start', '09:00', 'visitor', 'Campus visitor entry opening time'),

                ('visiting_hours_end', '19:00', 'visitor', 'Campus visitor departure closing time'),

                ('max_visitor_stay_hours', '4', 'visitor', 'Maximum authorized duration per visitor pass'),

                ('late_fine_grace_period_days', '7', 'finance', 'Grace period days before late payment penalties apply'),

                ('daily_late_fine_rate', '50.0', 'finance', 'Daily penalty amount for overdue fee payments'),

                ('email_notifications_enabled', 'false', 'notification', 'Enable outbound email dispatch via SMTP'),

                ('browser_notifications_enabled', 'true', 'notification', 'Enable web push / browser notifications'),

                ('session_timeout_minutes', '30', 'security', 'JWT user session idle timeout window'),

                ('max_login_attempts', '5', 'security', 'Consecutive failed login attempts before lockout'),

                ('lockout_duration_minutes', '15', 'security', 'Account lock duration in minutes upon brute force')

            ]

            for key, val, cat, desc in standard_settings:

                cursor.execute("""

                    INSERT INTO system_settings (setting_key, setting_value, category, description, updated_at)

                    VALUES (?, ?, ?, ?, CURRENT_TIMESTAMP)

                    ON CONFLICT(setting_key) DO UPDATE SET

                        category = excluded.category,

                        description = excluded.description;

                """, (key, val, cat, desc))



            # 7. Seed sample announcements (defer user/hostel references until seeded)

            cursor.execute("""

                INSERT OR IGNORE INTO announcements (

                    id, title, content, category, priority, target_audience, target_hostel_id,

                    status, publish_at, created_by, published_by, is_active, created_at

                ) VALUES

                (1, 'Hostel Annual Maintenance & Wi-Fi Upgrade', 'Hostel Wi-Fi access points and electrical switchboards will undergo routine maintenance this weekend from 10:00 AM to 02:00 PM.', 'Maintenance Notice', 'Normal', 'All Users', NULL, 'Published', CURRENT_TIMESTAMP, (SELECT id FROM users WHERE id = 1), (SELECT id FROM users WHERE id = 1), 1, CURRENT_TIMESTAMP),

                (2, 'Semester Fee Payment Deadline Notice', 'All residential students are hereby reminded to clear their semester hostel and mess dues before November 15, 2026 to avoid late payment fines.', 'Fee Notice', 'High', 'All Students', NULL, 'Published', CURRENT_TIMESTAMP, (SELECT id FROM users WHERE id = 1), (SELECT id FROM users WHERE id = 1), 1, CURRENT_TIMESTAMP),

                (3, 'Emergency Water Pipeline Repair', 'Emergency maintenance is in progress on the central water supply line of Nilgiri Boys Hostel. Tanker backup has been deployed on ground floor.', 'Emergency Notice', 'Critical', 'Hostel Residents', (SELECT id FROM hostels WHERE id = 1), 'Published', CURRENT_TIMESTAMP, (SELECT id FROM users WHERE id = 1), (SELECT id FROM users WHERE id = 1), 1, CURRENT_TIMESTAMP);

            """)



            # 8. Composite B-Tree Indexes for Sub-10ms Q05 SLA

            cursor.execute("CREATE INDEX IF NOT EXISTS idx_notifications_user_unread ON notifications(user_id, is_read, created_at);")

            cursor.execute("CREATE INDEX IF NOT EXISTS idx_notifications_category ON notifications(category, priority);")

            cursor.execute("CREATE INDEX IF NOT EXISTS idx_notifications_event_key ON notifications(event_key);")

            cursor.execute("CREATE INDEX IF NOT EXISTS idx_announcements_status_publish ON announcements(status, publish_at, expires_at);")

            cursor.execute("CREATE INDEX IF NOT EXISTS idx_announcements_target ON announcements(target_audience, target_hostel_id);")

            cursor.execute("CREATE INDEX IF NOT EXISTS idx_announcement_views_user ON announcement_views(user_id, announcement_id);")

            cursor.execute("CREATE INDEX IF NOT EXISTS idx_audit_logs_user_action ON audit_logs(user_id, action, created_at);")

            cursor.execute("CREATE INDEX IF NOT EXISTS idx_audit_logs_entity ON audit_logs(entity_name, entity_id);")

            cursor.execute("CREATE INDEX IF NOT EXISTS idx_users_role_status ON users(is_active, username);")

            cursor.execute("CREATE INDEX IF NOT EXISTS idx_settings_key ON system_settings(setting_key);")



            cursor.execute("PRAGMA foreign_keys = ON;")

            record_migration(conn, "009_notifications_announcements_and_admin_enhancements", "Notifications, Preferences, Announcements, Views, Settings & Audit Indexes", commit=False)


            


            conn.commit()

            applied_now.append("009_notifications_announcements_and_admin_enhancements")

            logger.info("Migration 009_notifications_announcements_and_admin_enhancements applied successfully.")



        # Migration 010: Registration Approval Workflow (Student, Staff, Parent Multi-Party Approvals)

        if "010_registration_approval_workflow" not in applied:
            begin_migration_transaction(conn)

            logger.info("Applying Migration 010_registration_approval_workflow...")

            cursor = conn.cursor()

            cursor.execute("""

                CREATE TABLE IF NOT EXISTS registration_requests (

                    id INTEGER PRIMARY KEY AUTOINCREMENT,

                    user_id INTEGER NOT NULL REFERENCES users(id) ON DELETE CASCADE,

                    username TEXT NOT NULL,

                    email TEXT NOT NULL,

                    first_name TEXT NOT NULL,

                    last_name TEXT NOT NULL,

                    phone TEXT,

                    requested_role TEXT NOT NULL,

                    specialization TEXT,

                    student_roll_no TEXT,

                    branch TEXT,

                    linked_student_id INTEGER REFERENCES students(id),

                    relationship TEXT,

                    status TEXT NOT NULL DEFAULT 'Pending',

                    admin_warden_approval_status TEXT NOT NULL DEFAULT 'Pending',

                    admin_warden_approved_by INTEGER REFERENCES users(id),

                    admin_warden_approved_at TEXT,

                    admin_warden_role TEXT,

                    student_approval_status TEXT NOT NULL DEFAULT 'Pending',

                    student_approved_by INTEGER REFERENCES users(id),

                    student_approved_at TEXT,

                    rejection_reason TEXT,

                    created_at TEXT NOT NULL DEFAULT (datetime('now')),

                    updated_at TEXT NOT NULL DEFAULT (datetime('now'))

                );

            """)

            cursor.execute("CREATE INDEX IF NOT EXISTS idx_reg_req_user ON registration_requests(user_id);")

            cursor.execute("CREATE INDEX IF NOT EXISTS idx_reg_req_status ON registration_requests(status);")

            cursor.execute("CREATE INDEX IF NOT EXISTS idx_reg_req_linked_student ON registration_requests(linked_student_id);")

            cursor.execute("CREATE INDEX IF NOT EXISTS idx_reg_req_role ON registration_requests(requested_role);")

            record_migration(conn, "010_registration_approval_workflow", "Multi-party registration approval tables and indexes", commit=False)


            


            conn.commit()

            applied_now.append("010_registration_approval_workflow")

            logger.info("Migration 010_registration_approval_workflow applied successfully.")



        # Migration 011: Staff ID and Student ID Unique Identifiers

        if "011_staff_ids_and_unique_identifiers" not in applied:
            begin_migration_transaction(conn)

            logger.info("Applying Migration 011_staff_ids_and_unique_identifiers...")

            cursor = conn.cursor()



            # 1. Add staff_id to users if not present

            user_cols = [c[1] for c in cursor.execute("PRAGMA table_info(users);").fetchall()]

            if "staff_id" not in user_cols:

                cursor.execute("ALTER TABLE users ADD COLUMN staff_id TEXT;")



            # 2. Add staff_id to registration_requests if not present

            reg_cols = [c[1] for c in cursor.execute("PRAGMA table_info(registration_requests);").fetchall()]

            if "staff_id" not in reg_cols:

                cursor.execute("ALTER TABLE registration_requests ADD COLUMN staff_id TEXT;")



            # 3. Create unique index for staff_id on users

            cursor.execute("CREATE UNIQUE INDEX IF NOT EXISTS idx_users_staff_id ON users(staff_id) WHERE staff_id IS NOT NULL;")



            # 4. Backfill unique Staff IDs for all existing staff members

            staff_roles = ('super_admin', 'hostel_admin', 'warden', 'assistant_warden', 'accountant', 'mess_manager', 'maintenance_staff', 'security_guard', 'admission_officer', 'auditor')

            cursor.execute("""

                SELECT DISTINCT u.id

                FROM users u

                JOIN user_roles ur ON u.id = ur.user_id

                JOIN roles r ON ur.role_id = r.id

                WHERE r.name IN (?, ?, ?, ?, ?, ?, ?, ?, ?, ?) AND (u.staff_id IS NULL OR u.staff_id = '')

                ORDER BY u.id ASC;

            """, staff_roles)

            staff_user_ids = [row[0] for row in cursor.fetchall()]

            for uid in staff_user_ids:

                s_id = f"STF-{uid:04d}"

                cursor.execute("UPDATE users SET staff_id = ? WHERE id = ?;", (s_id, uid))



            record_migration(conn, "011_staff_ids_and_unique_identifiers", "Add staff_id column, unique indexes, and backfill staff and student unique identifiers", commit=False)




            




            conn.commit()

            applied_now.append("011_staff_ids_and_unique_identifiers")

            logger.info("Migration 011_staff_ids_and_unique_identifiers applied successfully.")



        # 12. Migration 012: Gender support for users and registration requests

        if "012_gender_support_for_users_and_registrations" not in applied:
            begin_migration_transaction(conn)

            logger.info("Applying Migration 012_gender_support_for_users_and_registrations...")

            cursor = conn.cursor()



            # 1. Add gender to users if not present

            user_cols = [c[1] for c in cursor.execute("PRAGMA table_info(users);").fetchall()]

            if "gender" not in user_cols:

                cursor.execute("ALTER TABLE users ADD COLUMN gender TEXT DEFAULT 'Male';")



            # 2. Add gender to registration_requests if not present

            reg_cols = [c[1] for c in cursor.execute("PRAGMA table_info(registration_requests);").fetchall()]

            if "gender" not in reg_cols:

                cursor.execute("ALTER TABLE registration_requests ADD COLUMN gender TEXT DEFAULT 'Male';")



            # 3. Synchronize existing students' gender to users table

            cursor.execute("""

                UPDATE users

                SET gender = (SELECT s.gender FROM students s WHERE s.id = users.linked_student_id)

                WHERE users.linked_student_id IS NOT NULL AND EXISTS (SELECT 1 FROM students s WHERE s.id = users.linked_student_id);

            """)



            record_migration(conn, "012_gender_support_for_users_and_registrations", "Add gender column to users and registration_requests tables", commit=False)




            




            conn.commit()

            applied_now.append("012_gender_support_for_users_and_registrations")

            logger.info("Migration 012_gender_support_for_users_and_registrations applied successfully.")



        # 13. Migration 013: Hostel Warden hostel allocation constraint & Mother Teresa Girls Hostel (Single Rooms)

        if "013_hostel_warden_allocation_and_girls_single_hostel" not in applied:
            begin_migration_transaction(conn)

            logger.info("Applying Migration 013_hostel_warden_allocation_and_girls_single_hostel...")

            cursor = conn.cursor()



            # 1. Add hostel_id to registration_requests if not present

            reg_cols = [c[1] for c in cursor.execute("PRAGMA table_info(registration_requests);").fetchall()]

            if "hostel_id" not in reg_cols:

                cursor.execute("ALTER TABLE registration_requests ADD COLUMN hostel_id INTEGER REFERENCES hostels(id);")



            record_migration(conn, "013_hostel_warden_allocation_and_girls_single_hostel", "Add hostel_id to registration_requests", commit=False)




            




            conn.commit()

            applied_now.append("013_hostel_warden_allocation_and_girls_single_hostel")

            logger.info("Migration 013_hostel_warden_allocation_and_girls_single_hostel applied successfully.")



        # 14. Migration 014: Authoritative Integer Paise Monetary Storage

        if "014_monetary_paise_migration" not in applied:
            begin_migration_transaction(conn)

            logger.info("Applying Migration 014_monetary_paise_migration (authoritative integer paise storage)...")

            from backend.app.utils.currency import to_paise

            cursor = conn.cursor()



            # 1. fee_structures: amount_paise, late_fine_amount_paise

            cols = [c[1] for c in cursor.execute("PRAGMA table_info(fee_structures);").fetchall()]

            if "amount_paise" not in cols:

                cursor.execute("ALTER TABLE fee_structures ADD COLUMN amount_paise INTEGER DEFAULT 0;")

            if "late_fine_amount_paise" not in cols:

                cursor.execute("ALTER TABLE fee_structures ADD COLUMN late_fine_amount_paise INTEGER DEFAULT 0;")



            cursor.execute("SELECT id, amount, COALESCE(late_fine_amount, 0) FROM fee_structures;")

            for row in cursor.fetchall():

                fs_id, amt, late_amt = row

                cursor.execute(

                    "UPDATE fee_structures SET amount_paise = ?, late_fine_amount_paise = ? WHERE id = ?;",

                    (to_paise(amt), to_paise(late_amt), fs_id)

                )



            # 2. invoices: total_amount_paise, paid_amount_paise, discount_amount_paise, fine_amount_paise

            cols = [c[1] for c in cursor.execute("PRAGMA table_info(invoices);").fetchall()]

            if "total_amount_paise" not in cols:

                cursor.execute("ALTER TABLE invoices ADD COLUMN total_amount_paise INTEGER DEFAULT 0;")

            if "paid_amount_paise" not in cols:

                cursor.execute("ALTER TABLE invoices ADD COLUMN paid_amount_paise INTEGER DEFAULT 0;")

            if "discount_amount_paise" not in cols:

                cursor.execute("ALTER TABLE invoices ADD COLUMN discount_amount_paise INTEGER DEFAULT 0;")

            if "fine_amount_paise" not in cols:

                cursor.execute("ALTER TABLE invoices ADD COLUMN fine_amount_paise INTEGER DEFAULT 0;")



            cursor.execute("SELECT id, total_amount, COALESCE(paid_amount, 0), COALESCE(discount_amount, 0), COALESCE(fine_amount, 0) FROM invoices;")

            for row in cursor.fetchall():

                inv_id, total, paid, discount, fine = row

                cursor.execute(

                    "UPDATE invoices SET total_amount_paise = ?, paid_amount_paise = ?, discount_amount_paise = ?, fine_amount_paise = ? WHERE id = ?;",

                    (to_paise(total), to_paise(paid), to_paise(discount), to_paise(fine), inv_id)

                )



            # 3. invoice_items: amount_paise

            cols = [c[1] for c in cursor.execute("PRAGMA table_info(invoice_items);").fetchall()]

            if "amount_paise" not in cols:

                cursor.execute("ALTER TABLE invoice_items ADD COLUMN amount_paise INTEGER DEFAULT 0;")



            cursor.execute("SELECT id, amount FROM invoice_items;")

            for row in cursor.fetchall():

                item_id, amt = row

                cursor.execute(

                    "UPDATE invoice_items SET amount_paise = ? WHERE id = ?;",

                    (to_paise(amt), item_id)

                )



            # 4. payments: amount_paise

            cols = [c[1] for c in cursor.execute("PRAGMA table_info(payments);").fetchall()]

            if "amount_paise" not in cols:

                cursor.execute("ALTER TABLE payments ADD COLUMN amount_paise INTEGER DEFAULT 0;")



            cursor.execute("SELECT id, amount FROM payments;")

            for row in cursor.fetchall():

                pay_id, amt = row

                cursor.execute(

                    "UPDATE payments SET amount_paise = ? WHERE id = ?;",

                    (to_paise(amt), pay_id)

                )



            # 5. refunds: amount_paise

            cols = [c[1] for c in cursor.execute("PRAGMA table_info(refunds);").fetchall()]

            if "amount_paise" not in cols:

                cursor.execute("ALTER TABLE refunds ADD COLUMN amount_paise INTEGER DEFAULT 0;")



            cursor.execute("SELECT id, amount FROM refunds;")

            for row in cursor.fetchall():

                ref_id, amt = row

                cursor.execute(

                    "UPDATE refunds SET amount_paise = ? WHERE id = ?;",

                    (to_paise(amt), ref_id)

                )



            record_migration(conn, "014_monetary_paise_migration", "Authoritative Integer Paise Monetary Storage", commit=False)




            




            conn.commit()

            applied_now.append("014_monetary_paise_migration")

            logger.info("Migration 014_monetary_paise_migration applied successfully.")



        # 15. Migration 015: Enforce Referential Integrity and Clean Orphans with Archival

        if "015_enforce_referential_integrity_and_clean_orphans" not in applied:
            begin_migration_transaction(conn)

            logger.info("Applying Migration 015_enforce_referential_integrity_and_clean_orphans...")

            cursor = conn.cursor()

            execute_sql_statements(cursor, HISTORICAL_ORPHAN_ARCHIVES_SQL)



            # 1. Hostels: Nullify dangling warden_id without fabricating fake warden user

            cursor.execute("SELECT * FROM hostels WHERE warden_id IS NOT NULL AND warden_id NOT IN (SELECT id FROM users);")

            hostels = cursor.fetchall()

            for h in hostels:

                h_dict = row_to_dict(cursor, h)

                archive_orphan_record(

                    cursor,

                    source_table="hostels",

                    source_record_id=h_dict.get("id"),

                    broken_col="warden_id",

                    orig_ref_id=h_dict.get("warden_id"),

                    payload=h_dict,

                    reason="Referenced warden_id does not exist in users table; nullified to maintain referential integrity without fabricating warden assignment",

                    migration_version="015_enforce_referential_integrity_and_clean_orphans"

                )

            cursor.execute("""

                UPDATE hostels

                SET warden_id = NULL

                WHERE warden_id IS NOT NULL AND warden_id NOT IN (SELECT id FROM users);

            """)



            # 2. Visitors & visitor_logs: Clean and archive any dangling visitor logs without fabricating fake visitor identities

            cursor.execute("SELECT * FROM visitor_logs WHERE visitor_id IS NOT NULL AND visitor_id NOT IN (SELECT id FROM visitors);")

            dangling_vl = cursor.fetchall()

            for vl in dangling_vl:

                vl_dict = row_to_dict(cursor, vl)

                archive_orphan_record(

                    cursor,

                    source_table="visitor_logs",

                    source_record_id=vl_dict.get("id"),

                    broken_col="visitor_id",

                    orig_ref_id=vl_dict.get("visitor_id"),

                    payload=vl_dict,

                    reason="Historical visitor log with non-existent visitor_id archived before removal to preserve referential integrity without fabricating visitor identity",

                    migration_version="015_enforce_referential_integrity_and_clean_orphans"

                )

            cursor.execute("""

                DELETE FROM visitor_logs

                WHERE visitor_id IS NOT NULL AND visitor_id NOT IN (SELECT id FROM visitors);

            """)



            # 3. Registration requests

            cursor.execute("SELECT * FROM registration_requests WHERE admin_warden_approved_by IS NOT NULL AND admin_warden_approved_by NOT IN (SELECT id FROM users);")

            for r in cursor.fetchall():

                r_dict = row_to_dict(cursor, r)

                archive_orphan_record(

                    cursor,

                    source_table="registration_requests",

                    source_record_id=r_dict.get("id"),

                    broken_col="admin_warden_approved_by",

                    orig_ref_id=r_dict.get("admin_warden_approved_by"),

                    payload=r_dict,

                    reason="Referenced admin_warden_approved_by user does not exist; nullified to preserve registration application",

                    migration_version="015_enforce_referential_integrity_and_clean_orphans"

                )

            cursor.execute("""

                UPDATE registration_requests

                SET admin_warden_approved_by = NULL

                WHERE admin_warden_approved_by IS NOT NULL AND admin_warden_approved_by NOT IN (SELECT id FROM users);

            """)



            cursor.execute("SELECT * FROM registration_requests WHERE student_approved_by IS NOT NULL AND student_approved_by NOT IN (SELECT id FROM users);")

            for r in cursor.fetchall():

                r_dict = row_to_dict(cursor, r)

                archive_orphan_record(

                    cursor,

                    source_table="registration_requests",

                    source_record_id=r_dict.get("id"),

                    broken_col="student_approved_by",

                    orig_ref_id=r_dict.get("student_approved_by"),

                    payload=r_dict,

                    reason="Referenced student_approved_by user does not exist; nullified to preserve registration application",

                    migration_version="015_enforce_referential_integrity_and_clean_orphans"

                )

            cursor.execute("""

                UPDATE registration_requests

                SET student_approved_by = NULL

                WHERE student_approved_by IS NOT NULL AND student_approved_by NOT IN (SELECT id FROM users);

            """)



            # 3b. Announcements: Nullify dangling references

            cursor.execute("UPDATE announcements SET created_by = NULL WHERE created_by IS NOT NULL AND created_by NOT IN (SELECT id FROM users);")

            cursor.execute("UPDATE announcements SET published_by = NULL WHERE published_by IS NOT NULL AND published_by NOT IN (SELECT id FROM users);")

            cursor.execute("UPDATE announcements SET target_hostel_id = NULL WHERE target_hostel_id IS NOT NULL AND target_hostel_id NOT IN (SELECT id FROM hostels);")



            # 4. Leave requests: Nullify dangling approved_by

            cursor.execute("SELECT * FROM leave_requests WHERE approved_by IS NOT NULL AND approved_by NOT IN (SELECT id FROM users);")

            for l in cursor.fetchall():

                l_dict = row_to_dict(cursor, l)

                archive_orphan_record(

                    cursor,

                    source_table="leave_requests",

                    source_record_id=l_dict.get("id"),

                    broken_col="approved_by",

                    orig_ref_id=l_dict.get("approved_by"),

                    payload=l_dict,

                    reason="Referenced approved_by user does not exist; nullified to preserve historical leave request",

                    migration_version="015_enforce_referential_integrity_and_clean_orphans"

                )

            cursor.execute("""

                UPDATE leave_requests

                SET approved_by = NULL

                WHERE approved_by IS NOT NULL AND approved_by NOT IN (SELECT id FROM users);

            """)



            # 5. Complaint updates: Nullify dangling updated_by

            cursor.execute("SELECT * FROM complaint_updates WHERE updated_by IS NOT NULL AND updated_by NOT IN (SELECT id FROM users);")

            for c in cursor.fetchall():

                c_dict = row_to_dict(cursor, c)

                archive_orphan_record(

                    cursor,

                    source_table="complaint_updates",

                    source_record_id=c_dict.get("id"),

                    broken_col="updated_by",

                    orig_ref_id=c_dict.get("updated_by"),

                    payload=c_dict,

                    reason="Referenced updated_by user does not exist; nullified to preserve complaint resolution history",

                    migration_version="015_enforce_referential_integrity_and_clean_orphans"

                )

            cursor.execute("""

                UPDATE complaint_updates

                SET updated_by = NULL

                WHERE updated_by IS NOT NULL AND updated_by NOT IN (SELECT id FROM users);

            """)



            # 6. Audit logs: Nullify dangling user_id

            cursor.execute("SELECT * FROM audit_logs WHERE user_id IS NOT NULL AND user_id NOT IN (SELECT id FROM users);")

            for a in cursor.fetchall():

                a_dict = row_to_dict(cursor, a)

                archive_orphan_record(

                    cursor,

                    source_table="audit_logs",

                    source_record_id=a_dict.get("id"),

                    broken_col="user_id",

                    orig_ref_id=a_dict.get("user_id"),

                    payload=a_dict,

                    reason="Historical audit trail record user_id nullified to preserve audit history",

                    migration_version="015_enforce_referential_integrity_and_clean_orphans"

                )

            cursor.execute("""

                UPDATE audit_logs

                SET user_id = NULL

                WHERE user_id IS NOT NULL AND user_id NOT IN (SELECT id FROM users);

            """)



            # 7. Login history: Nullify dangling user_id

            cursor.execute("SELECT * FROM login_history WHERE user_id IS NOT NULL AND user_id NOT IN (SELECT id FROM users);")

            for lh in cursor.fetchall():

                lh_dict = row_to_dict(cursor, lh)

                archive_orphan_record(

                    cursor,

                    source_table="login_history",

                    source_record_id=lh_dict.get("id"),

                    broken_col="user_id",

                    orig_ref_id=lh_dict.get("user_id"),

                    payload=lh_dict,

                    reason="Historical login attempt record user_id nullified to preserve login telemetry",

                    migration_version="015_enforce_referential_integrity_and_clean_orphans"

                )

            cursor.execute("""

                UPDATE login_history

                SET user_id = NULL

                WHERE user_id IS NOT NULL AND user_id NOT IN (SELECT id FROM users);

            """)



            # 8. Notifications: Archive before deletion

            cursor.execute("SELECT * FROM notifications WHERE user_id IS NOT NULL AND user_id NOT IN (SELECT id FROM users);")

            for n in cursor.fetchall():

                n_dict = row_to_dict(cursor, n)

                archive_orphan_record(

                    cursor,

                    source_table="notifications",

                    source_record_id=n_dict.get("id"),

                    broken_col="user_id",

                    orig_ref_id=n_dict.get("user_id"),

                    payload=n_dict,

                    reason="Orphaned notification for deleted user archived before removal",

                    migration_version="015_enforce_referential_integrity_and_clean_orphans"

                )

            cursor.execute("""

                DELETE FROM notifications

                WHERE user_id IS NOT NULL AND user_id NOT IN (SELECT id FROM users);

            """)



            # 9. Refresh tokens: Archive before deletion

            cursor.execute("SELECT * FROM refresh_tokens WHERE user_id IS NOT NULL AND user_id NOT IN (SELECT id FROM users);")

            for rt in cursor.fetchall():

                rt_dict = row_to_dict(cursor, rt)

                archive_orphan_record(

                    cursor,

                    source_table="refresh_tokens",

                    source_record_id=rt_dict.get("id"),

                    broken_col="user_id",

                    orig_ref_id=rt_dict.get("user_id"),

                    payload=rt_dict,

                    reason="Dangling refresh token for deleted user archived before removal",

                    migration_version="015_enforce_referential_integrity_and_clean_orphans"

                )

            cursor.execute("""

                DELETE FROM refresh_tokens

                WHERE user_id IS NOT NULL AND user_id NOT IN (SELECT id FROM users);

            """)



            # 10. User roles: Archive before deletion

            cursor.execute("SELECT * FROM user_roles WHERE user_id IS NOT NULL AND user_id NOT IN (SELECT id FROM users);")

            for ur in cursor.fetchall():

                ur_dict = row_to_dict(cursor, ur)

                archive_orphan_record(

                    cursor,

                    source_table="user_roles",

                    source_record_id=ur_dict.get("user_id"),

                    broken_col="user_id",

                    orig_ref_id=ur_dict.get("user_id"),

                    payload=ur_dict,

                    reason="Orphaned user role assignment for deleted user archived before removal",

                    migration_version="015_enforce_referential_integrity_and_clean_orphans"

                )

            cursor.execute("""

                DELETE FROM user_roles

                WHERE user_id IS NOT NULL AND user_id NOT IN (SELECT id FROM users);

            """)



            record_migration(conn, "015_enforce_referential_integrity_and_clean_orphans", "Enforce Referential Integrity and Clean Orphans with Archival", commit=False)




            violations = cursor.execute("PRAGMA foreign_key_check;").fetchall()
            if violations:
                logger.info(f"Migration 015 intermediate foreign key check: {len(violations)} records pending reconciliation in Migration 016.")
            conn.commit()

            applied_now.append("015_enforce_referential_integrity_and_clean_orphans")

            logger.info("Migration 015_enforce_referential_integrity_and_clean_orphans applied successfully.")



        # 16. Migration 016: Reconcile Archival and Operational Records

        if "016_reconcile_archival_and_operational_records" not in applied:
            begin_migration_transaction(conn)

            logger.info("Applying Migration 016_reconcile_archival_and_operational_records...")

            cursor = conn.cursor()

            execute_sql_statements(cursor, HISTORICAL_ORPHAN_ARCHIVES_SQL)



            # Reconcile synthetic warden assignment on Mother Teresa Girls Hostel if set previously

            cursor.execute("SELECT id, name, warden_id FROM hostels WHERE id = 3;")

            h3 = cursor.fetchone()

            if h3:

                h3_dict = row_to_dict(cursor, h3)

                cursor.execute("SELECT id FROM users WHERE username = 'warden';")

                w_row = cursor.fetchone()

                warden_user_id = w_row[0] if w_row else None

                if h3_dict.get("warden_id") == warden_user_id and warden_user_id is not None:

                    archive_orphan_record(

                        cursor,

                        source_table="hostels",

                        source_record_id=3,

                        broken_col="warden_id",

                        orig_ref_id=15,

                        payload=h3_dict,

                        reason="Reconciled erroneous synthetic warden assignment on Mother Teresa Girls Hostel; nullified to reflect true unassigned state and prevent unauthorized access",

                        migration_version="016_reconcile_archival_and_operational_records"

                    )

                    cursor.execute("UPDATE hostels SET warden_id = NULL WHERE id = 3;")



            # Nullify any dangling announcements references

            cursor.execute("UPDATE announcements SET created_by = NULL WHERE created_by IS NOT NULL AND created_by NOT IN (SELECT id FROM users);")

            cursor.execute("UPDATE announcements SET published_by = NULL WHERE published_by IS NOT NULL AND published_by NOT IN (SELECT id FROM users);")

            cursor.execute("UPDATE announcements SET target_hostel_id = NULL WHERE target_hostel_id IS NOT NULL AND target_hostel_id NOT IN (SELECT id FROM hostels);")



            # Validate 0 remaining foreign key violations (Fail-Closed Integrity Check)

            violations = cursor.execute("PRAGMA foreign_key_check;").fetchall()

            if violations:

                violation_summary = [f"table={v[0]}, rowid={v[1]}, target={v[2]}, fkid={v[3]}" for v in violations]

                err_msg = f"Migration 016 foreign key validation failed with {len(violations)} unresolved violations: {violation_summary}"

                logger.error(err_msg)

                raise RuntimeError(err_msg)



            record_migration(conn, "016_reconcile_archival_and_operational_records", "Reconcile Archival and Operational Records", commit=False)




            violations = cursor.execute("PRAGMA foreign_key_check;").fetchall()




            if violations:




                raise RuntimeError(f"Foreign key validation failed for migration 016_reconcile_archival_and_operational_records: {violations}")




            conn.commit()

            applied_now.append("016_reconcile_archival_and_operational_records")

            logger.info("Migration 016_reconcile_archival_and_operational_records applied successfully.")

        # 17. Migration 017: Second-Pass Remediation, Safe Visitor History Repair & Staff Profiles

        if "017_second_pass_remediation_and_profile_tables" not in applied:
            begin_migration_transaction(conn)

            logger.info("Applying Migration 017_second_pass_remediation_and_profile_tables...")

            cursor = conn.cursor()

            execute_sql_statements(cursor, HISTORICAL_ORPHAN_ARCHIVES_SQL)



            # Reconcile and safely archive previously inserted synthetic visitor 101 ('Ramesh Sharma')

            cursor.execute("SELECT * FROM visitors WHERE id = 101 AND name = 'Ramesh Sharma' AND phone = '+91 9876543210';")

            synth_v = cursor.fetchone()

            if synth_v:

                synth_dict = row_to_dict(cursor, synth_v)

                cursor.execute("SELECT COUNT(*) FROM visitor_logs WHERE visitor_id = 101;")

                ref_count = cursor.fetchone()[0]

                if ref_count == 0:

                    archive_orphan_record(

                        cursor,

                        source_table="visitors",

                        source_record_id=101,

                        broken_col="id",

                        orig_ref_id=101,

                        payload=synth_dict,

                        reason="Reconciled and safely archived previously generated synthetic visitor identity (Ramesh Sharma) with 0 active log references",

                        migration_version="017_second_pass_remediation_and_profile_tables"

                    )

                    cursor.execute("DELETE FROM visitors WHERE id = 101;")

                    logger.info("Migration 017: Archived and removed synthetic visitor 101 record.")

                else:

                    logger.warning(f"Migration 017: Visitor 101 has {ref_count} active log references; preserving record.")



            # Expand students table with additional institutional profile fields and support status='Pending'
            cursor.execute("PRAGMA foreign_keys = OFF;")
            cursor.execute("""
                CREATE TABLE IF NOT EXISTS students_new (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    student_id TEXT UNIQUE NOT NULL,
                    user_id INTEGER UNIQUE REFERENCES users(id) ON DELETE SET NULL,
                    first_name TEXT NOT NULL,
                    last_name TEXT NOT NULL,
                    email TEXT UNIQUE NOT NULL,
                    phone TEXT NOT NULL,
                    gender TEXT NOT NULL CHECK(gender IN ('Male', 'Female', 'Other')),
                    date_of_birth TEXT,
                    blood_group TEXT,
                    branch TEXT NOT NULL,
                    academic_year TEXT NOT NULL,
                    semester INTEGER DEFAULT 1,
                    address TEXT,
                    admission_date TEXT NOT NULL,
                    status TEXT NOT NULL DEFAULT 'Active' CHECK(status IN ('Active', 'Graduated', 'Suspended', 'Withdrawn', 'Pending')),
                    created_at TEXT DEFAULT (datetime('now')),
                    updated_at TEXT DEFAULT (datetime('now')),
                    course TEXT DEFAULT 'B.Tech',
                    permanent_address TEXT DEFAULT '',
                    current_address TEXT DEFAULT '',
                    city TEXT DEFAULT '',
                    state TEXT DEFAULT '',
                    postal_code TEXT DEFAULT '',
                    country TEXT DEFAULT 'India',
                    guardian_name TEXT DEFAULT '',
                    guardian_relation TEXT DEFAULT 'Parent',
                    guardian_phone TEXT DEFAULT '',
                    guardian_email TEXT DEFAULT '',
                    emergency_contact_name TEXT DEFAULT '',
                    emergency_contact_phone TEXT DEFAULT ''
                );
            """)
            existing_cols = [c[1] for c in cursor.execute("PRAGMA table_info(students);").fetchall()]
            new_target_cols = [c[1] for c in cursor.execute("PRAGMA table_info(students_new);").fetchall()]
            common_cols = [c for c in existing_cols if c in new_target_cols]
            common_str = ", ".join(common_cols)
            cursor.execute(f"INSERT INTO students_new ({common_str}) SELECT {common_str} FROM students;")
            cursor.execute("DROP TABLE students;")
            cursor.execute("ALTER TABLE students_new RENAME TO students;")
            cursor.execute("CREATE UNIQUE INDEX IF NOT EXISTS idx_students_student_id ON students(student_id);")
            cursor.execute("CREATE UNIQUE INDEX IF NOT EXISTS idx_students_email ON students(email);")
            cursor.execute("CREATE INDEX IF NOT EXISTS idx_students_name ON students(first_name, last_name);")
            cursor.execute("CREATE INDEX IF NOT EXISTS idx_students_user_id ON students(user_id);")
            cursor.execute("CREATE INDEX IF NOT EXISTS idx_students_status ON students(status);")
            cursor.execute("PRAGMA foreign_keys = ON;\n\n            ")# Create staff_profiles table to persist complete employment and personal details

            cursor.execute("""

                CREATE TABLE IF NOT EXISTS staff_profiles (

                    id INTEGER PRIMARY KEY AUTOINCREMENT,

                    user_id INTEGER NOT NULL UNIQUE REFERENCES users(id) ON DELETE CASCADE,

                    employee_id TEXT UNIQUE,

                    category TEXT NOT NULL DEFAULT 'staff',

                    designation TEXT DEFAULT '',

                    department TEXT DEFAULT '',

                    specialization TEXT DEFAULT '',

                    employment_type TEXT DEFAULT 'Full-Time',

                    date_of_joining TEXT NULL,

                    assigned_location TEXT DEFAULT '',

                    permanent_address TEXT DEFAULT '',

                    current_address TEXT DEFAULT '',

                    city TEXT DEFAULT '',

                    state TEXT DEFAULT '',

                    postal_code TEXT DEFAULT '',
                    country TEXT DEFAULT 'India',

                    emergency_contact_name TEXT DEFAULT '',

                    emergency_contact_phone TEXT DEFAULT '',

                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,

                    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP

                );

            """)

            staff_cols = [c[1] for c in cursor.execute("PRAGMA table_info(staff_profiles);").fetchall()]
            if "country" not in staff_cols:
                cursor.execute("ALTER TABLE staff_profiles ADD COLUMN country TEXT DEFAULT 'India';")
            cursor.execute("CREATE INDEX IF NOT EXISTS idx_staff_profiles_user ON staff_profiles(user_id);")

            cursor.execute("CREATE INDEX IF NOT EXISTS idx_staff_profiles_emp ON staff_profiles(employee_id);")



            # Validate zero foreign key violations

            violations = cursor.execute("PRAGMA foreign_key_check;").fetchall()

            if violations:

                violation_summary = [f"table={v[0]}, rowid={v[1]}, target={v[2]}, fkid={v[3]}" for v in violations]

                err_msg = f"Migration 017 foreign key validation failed with {len(violations)} unresolved violations: {violation_summary}"

                logger.error(err_msg)

                raise RuntimeError(err_msg)



            record_migration(conn, "017_second_pass_remediation_and_profile_tables", "Second-Pass Remediation, Safe Visitor History Repair & Staff Profiles", commit=False)




            violations = cursor.execute("PRAGMA foreign_key_check;").fetchall()




            if violations:




                raise RuntimeError(f"Foreign key validation failed for migration 017_second_pass_remediation_and_profile_tables: {violations}")




            conn.commit()

            applied_now.append("017_second_pass_remediation_and_profile_tables")

            logger.info("Migration 017_second_pass_remediation_and_profile_tables applied successfully.")





        
        # 18. Migration 018: Multi-Ward Parent Relationship and Multi-Party Approvals
        if "018_multi_ward_parent_relationship_and_approvals" not in applied:
            begin_migration_transaction(conn)
            logger.info("Applying Migration 018_multi_ward_parent_relationship_and_approvals...")
            cursor = conn.cursor()

            # Create registration_request_wards table
            cursor.execute("""
                CREATE TABLE IF NOT EXISTS registration_request_wards (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    registration_request_id INTEGER NOT NULL REFERENCES registration_requests(id) ON DELETE CASCADE,
                    student_id INTEGER NOT NULL REFERENCES students(id) ON DELETE CASCADE,
                    relationship TEXT NOT NULL DEFAULT 'Parent',
                    student_approval_status TEXT NOT NULL DEFAULT 'Pending' CHECK(student_approval_status IN ('Pending', 'Approved', 'Rejected')),
                    student_approved_by INTEGER NULL REFERENCES users(id),
                    student_approved_at TIMESTAMP NULL,
                    administrative_approval_status TEXT NOT NULL DEFAULT 'Pending' CHECK(administrative_approval_status IN ('Pending', 'Approved', 'Rejected')),
                    administrative_approved_by INTEGER NULL REFERENCES users(id),
                    administrative_approved_at TIMESTAMP NULL,
                    rejection_reason TEXT NULL,
                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                );
            """)

            # Create parent_student_links table
            cursor.execute("""
                CREATE TABLE IF NOT EXISTS parent_student_links (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    parent_user_id INTEGER NOT NULL REFERENCES users(id) ON DELETE CASCADE,
                    student_id INTEGER NOT NULL REFERENCES students(id) ON DELETE CASCADE,
                    guardian_id INTEGER NULL REFERENCES guardians(id) ON DELETE SET NULL,
                    relationship TEXT NOT NULL DEFAULT 'Parent',
                    verified_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    approved_by INTEGER NULL REFERENCES users(id),
                    status TEXT NOT NULL DEFAULT 'Active' CHECK(status IN ('Active', 'Inactive', 'Revoked')),
                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    UNIQUE(parent_user_id, student_id)
                );
            """)

            cursor.execute("CREATE INDEX IF NOT EXISTS idx_req_wards_req_id ON registration_request_wards(registration_request_id);")
            cursor.execute("CREATE INDEX IF NOT EXISTS idx_req_wards_student_id ON registration_request_wards(student_id);")
            cursor.execute("CREATE INDEX IF NOT EXISTS idx_parent_student_links_parent ON parent_student_links(parent_user_id);")
            cursor.execute("CREATE INDEX IF NOT EXISTS idx_parent_student_links_student ON parent_student_links(student_id);")

            # Backfill existing approved registration requests into registration_request_wards
            cursor.execute("""
                SELECT id, linked_student_id, relationship, student_approval_status,
                       student_approved_by, student_approved_at, admin_warden_approval_status,
                       admin_warden_approved_by, admin_warden_approved_at, rejection_reason, created_at
                FROM registration_requests
                WHERE requested_role = 'parent_guardian' AND linked_student_id IS NOT NULL;
            """)
            existing_reqs = cursor.fetchall()
            for r in existing_reqs:
                req_id_val = r[0]
                st_id_val = r[1]
                cursor.execute("SELECT id FROM students WHERE id = ?;", (st_id_val,))
                if cursor.fetchone():
                    cursor.execute("""
                        SELECT id FROM registration_request_wards
                        WHERE registration_request_id = ? AND student_id = ?;
                    """, (req_id_val, st_id_val))
                    if not cursor.fetchone():
                        cursor.execute("""
                            INSERT INTO registration_request_wards (
                                registration_request_id, student_id, relationship,
                                student_approval_status, student_approved_by, student_approved_at,
                                administrative_approval_status, administrative_approved_by, administrative_approved_at,
                                rejection_reason, created_at, updated_at
                            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, CURRENT_TIMESTAMP);
                        """, (
                            req_id_val, st_id_val, r[2] or 'Parent',
                            r[3] or 'Pending', r[4], r[5],
                            r[6] or 'Pending', r[7], r[8],
                            r[9], r[10] or datetime.now().isoformat()
                        ))

            # Backfill existing active parent users into parent_student_links
            cursor.execute("""
                SELECT u.id, u.linked_student_id, u.first_name, u.last_name, u.phone, u.email
                FROM users u
                JOIN user_roles ur ON u.id = ur.user_id
                JOIN roles r ON ur.role_id = r.id
                WHERE r.name = 'parent_guardian' AND u.linked_student_id IS NOT NULL AND u.is_active = 1;
            """)
            existing_parents = cursor.fetchall()
            for p in existing_parents:
                p_uid = p[0]
                p_sid = p[1]
                cursor.execute("SELECT id FROM students WHERE id = ?;", (p_sid,))
                if cursor.fetchone():
                    cursor.execute("""
                        SELECT id FROM parent_student_links
                        WHERE parent_user_id = ? AND student_id = ?;
                    """, (p_uid, p_sid))
                    if not cursor.fetchone():
                        cursor.execute("SELECT id FROM guardians WHERE (phone = ? AND ? != '') OR (LOWER(email) = ? AND ? != '') LIMIT 1;",
                                       (p[4] or '', p[4] or '', (p[5] or '').lower(), (p[5] or '').lower()))
                        g_row = cursor.fetchone()
                        g_id = g_row[0] if g_row else None
                        cursor.execute("""
                            INSERT INTO parent_student_links (
                                parent_user_id, student_id, guardian_id, relationship, status
                            ) VALUES (?, ?, ?, 'Parent', 'Active');
                        """, (p_uid, p_sid, g_id))

            # Validate zero foreign key violations
            violations = cursor.execute("PRAGMA foreign_key_check;").fetchall()
            if violations:
                violation_summary = [f"table={v[0]}, rowid={v[1]}, target={v[2]}, fkid={v[3]}" for v in violations]
                err_msg = f"Migration 018 foreign key validation failed with {len(violations)} unresolved violations: {violation_summary}"
                logger.error(err_msg)
                raise RuntimeError(err_msg)

            record_migration(conn, "018_multi_ward_parent_relationship_and_approvals", "Multi-Ward Parent Relationship and Multi-Party Approvals", commit=False)


            violations = cursor.execute("PRAGMA foreign_key_check;").fetchall()


            if violations:


                raise RuntimeError(f"Foreign key validation failed for migration 018_multi_ward_parent_relationship_and_approvals: {violations}")


            conn.commit()
            applied_now.append("018_multi_ward_parent_relationship_and_approvals")
            logger.info("Migration 018_multi_ward_parent_relationship_and_approvals applied successfully.")


        # Migration 019: Notification Deliveries Tracking, Multi-Worker Leases, and Push Subscriptions
        if "019_notification_deliveries_and_leases" not in applied:
            logger.info("Applying Migration 019_notification_deliveries_and_leases...")
            begin_migration_transaction(conn)
            cursor = conn.cursor()

            # 1. Create notification_deliveries table
            cursor.execute("""
                CREATE TABLE IF NOT EXISTS notification_deliveries (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    notification_id INTEGER,
                    user_id INTEGER NOT NULL,
                    channel TEXT NOT NULL CHECK(channel IN ('in_app', 'email', 'browser_push', 'sms')),
                    provider TEXT NOT NULL,
                    delivery_status TEXT NOT NULL CHECK(delivery_status IN ('Sent', 'Failed', 'Disabled', 'Unconfigured_Channel', 'Pending')),
                    attempt_count INTEGER DEFAULT 1,
                    error_code TEXT DEFAULT '',
                    safe_error_message TEXT DEFAULT '',
                    provider_message_id TEXT DEFAULT '',
                    attempted_at TEXT NOT NULL,
                    completed_at TEXT,
                    FOREIGN KEY (notification_id) REFERENCES notifications(id) ON DELETE CASCADE,
                    FOREIGN KEY (user_id) REFERENCES users(id) ON DELETE CASCADE
                );
            """)
            cursor.execute("CREATE INDEX IF NOT EXISTS idx_notif_deliv_nid ON notification_deliveries(notification_id);")
            cursor.execute("CREATE INDEX IF NOT EXISTS idx_notif_deliv_uid ON notification_deliveries(user_id);")
            cursor.execute("CREATE INDEX IF NOT EXISTS idx_notif_deliv_status ON notification_deliveries(delivery_status);")
            cursor.execute("CREATE INDEX IF NOT EXISTS idx_notif_deliv_channel ON notification_deliveries(channel);")

            # 2. Create background_job_leases table for multi-worker coordination
            cursor.execute("""
                CREATE TABLE IF NOT EXISTS background_job_leases (
                    job_name TEXT PRIMARY KEY,
                    owner_id TEXT NOT NULL,
                    acquired_at TEXT NOT NULL,
                    expires_at TEXT NOT NULL,
                    heartbeat_at TEXT NOT NULL,
                    last_completed_at TEXT
                );
            """)
            cursor.execute("CREATE INDEX IF NOT EXISTS idx_bg_leases_expires ON background_job_leases(expires_at);")

            # 3. Create web_push_subscriptions table
            cursor.execute("""
                CREATE TABLE IF NOT EXISTS web_push_subscriptions (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    user_id INTEGER NOT NULL,
                    endpoint TEXT NOT NULL UNIQUE,
                    p256dh_key TEXT NOT NULL,
                    auth_key TEXT NOT NULL,
                    user_agent TEXT DEFAULT '',
                    is_active INTEGER DEFAULT 1 CHECK(is_active IN (0, 1)),
                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    FOREIGN KEY (user_id) REFERENCES users(id) ON DELETE CASCADE
                );
            """)
            cursor.execute("CREATE INDEX IF NOT EXISTS idx_push_sub_user ON web_push_subscriptions(user_id);")
            cursor.execute("CREATE INDEX IF NOT EXISTS idx_push_sub_active ON web_push_subscriptions(is_active);")

            # 4. Reconcile and backfill active parent-student links for legacy approved parents
            cursor.execute("""
                SELECT u.id, u.linked_student_id, g.id
                FROM users u
                JOIN user_roles ur ON u.id = ur.user_id
                JOIN roles r ON ur.role_id = r.id
                LEFT JOIN guardians g ON (LOWER(g.email) = LOWER(u.email) AND u.email != '') OR (g.phone = u.phone AND u.phone != '')
                WHERE r.name = 'parent' AND u.is_active = 1 AND u.linked_student_id IS NOT NULL;
            """)
            legacy_parents = cursor.fetchall()
            for p_uid, p_sid, g_id in legacy_parents:
                cursor.execute("""
                    INSERT INTO parent_student_links (parent_user_id, student_id, guardian_id, relationship, status)
                    VALUES (?, ?, ?, 'Parent', 'Active')
                    ON CONFLICT(parent_user_id, student_id) DO UPDATE SET status = 'Active', updated_at = CURRENT_TIMESTAMP;
                """, (p_uid, p_sid, g_id))

            # 5. Validate zero foreign key violations
            violations = cursor.execute("PRAGMA foreign_key_check;").fetchall()
            if violations:
                violation_summary = [f"table={v[0]}, rowid={v[1]}, target={v[2]}, fkid={v[3]}" for v in violations]
                err_msg = f"Migration 019 foreign key validation failed with {len(violations)} unresolved violations: {violation_summary}"
                logger.error(err_msg)
                raise RuntimeError(err_msg)

            record_migration(conn, "019_notification_deliveries_and_leases", "Notification Deliveries Tracking, Multi-Worker Leases, and Push Subscriptions", commit=False)
            conn.commit()
            applied_now.append("019_notification_deliveries_and_leases")
            logger.info("Migration 019_notification_deliveries_and_leases applied successfully.")

        # Migration 020: Enterprise RBAC, 10 Core Administrative Stakeholders and Data Scoping
        if "020_enterprise_rbac_and_10_stakeholders" not in applied:
            logger.info("Applying Migration 020_enterprise_rbac_and_10_stakeholders...")
            begin_migration_transaction(conn)
            cursor = conn.cursor()

            # 1. Add metadata columns to roles table if missing
            cursor.execute("PRAGMA table_info(roles);")
            role_cols = {col[1] for col in cursor.fetchall()}
            if "code" not in role_cols:
                cursor.execute("ALTER TABLE roles ADD COLUMN code TEXT;")
            if "stakeholder_category" not in role_cols:
                cursor.execute("ALTER TABLE roles ADD COLUMN stakeholder_category TEXT DEFAULT 'Operational / Student Life';")
            if "is_system_role" not in role_cols:
                cursor.execute("ALTER TABLE roles ADD COLUMN is_system_role INTEGER DEFAULT 1;")

            # 2. Insert or update all 15 system roles with canonical codes and categories
            for r_name, r_desc in ROLES_LIST:
                meta = ROLE_METADATA.get(r_name, {})
                r_code = meta.get("code", r_name.upper())
                r_cat = meta.get("category", "Operational / Student Life")
                cursor.execute("""
                    INSERT INTO roles (name, code, description, stakeholder_category, is_system, is_system_role)
                    VALUES (?, ?, ?, ?, 1, 1)
                    ON CONFLICT(name) DO UPDATE SET
                        code = excluded.code,
                        description = excluded.description,
                        stakeholder_category = excluded.stakeholder_category,
                        is_system = 1,
                        is_system_role = 1,
                        updated_at = CURRENT_TIMESTAMP;
                """, (r_name, r_code, r_desc, r_cat))

            cursor.execute("CREATE UNIQUE INDEX IF NOT EXISTS idx_roles_code ON roles(code);")

            # 3. Create user_scope_assignments table for fine-grained multi-scope authorization
            cursor.execute("""
                CREATE TABLE IF NOT EXISTS user_scope_assignments (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    user_id INTEGER NOT NULL,
                    scope_type TEXT NOT NULL CHECK(scope_type IN ('hostel', 'block', 'gate', 'financial', 'global')),
                    scope_id TEXT NOT NULL,
                    assigned_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    FOREIGN KEY (user_id) REFERENCES users(id) ON DELETE CASCADE,
                    UNIQUE(user_id, scope_type, scope_id)
                );
            """)
            cursor.execute("CREATE INDEX IF NOT EXISTS idx_user_scope_user ON user_scope_assignments(user_id);")
            cursor.execute("CREATE INDEX IF NOT EXISTS idx_user_scope_lookup ON user_scope_assignments(scope_type, scope_id);")

            # 4. Insert or update granular permissions
            for p_name, p_mod, p_desc in PERMISSIONS_LIST:
                cursor.execute("""
                    INSERT INTO permissions (name, module, description)
                    VALUES (?, ?, ?)
                    ON CONFLICT(name) DO UPDATE SET
                        module = excluded.module,
                        description = excluded.description;
                """, (p_name, p_mod, p_desc))

            # 5. Populate role_permissions for all 15 roles
            cursor.execute("SELECT id, name FROM roles;")
            role_id_map = {r[1]: r[0] for r in cursor.fetchall()}
            cursor.execute("SELECT id, name FROM permissions;")
            perm_id_map = {p[1]: p[0] for p in cursor.fetchall()}

            for r_name, p_names in ROLE_PERMISSIONS_MAP.items():
                r_id = role_id_map.get(r_name)
                if not r_id:
                    continue
                for p_name in p_names:
                    p_id = perm_id_map.get(p_name)
                    if p_id:
                        cursor.execute("""
                            INSERT OR IGNORE INTO role_permissions (role_id, permission_id)
                            VALUES (?, ?);
                        """, (r_id, p_id))

            # 6. Seed demo accounts for the 3 new roles if running on an existing seeded database
            cursor.execute("SELECT id FROM users WHERE username = 'superadmin';")
            if cursor.fetchone():
                from backend.app.services.security import hash_password
                default_pw = "Password123!"
                hashed_pw = hash_password(default_pw)
                new_demo_users = [
                    ("clerk", "clerk@univ.edu", "Amit", "Patel", "9800000013", "hostel_clerk", 1, "STF-0013"),
                    ("secsupervisor", "secsupervisor@univ.edu", "Gurpreet", "Singh", "9800000014", "security_supervisor", 1, "STF-0014"),
                    ("itadmin", "itadmin@univ.edu", "Neha", "Verma", "9800000015", "it_admin", None, "STF-0015"),
                ]
                for uname, uemail, ufn, uln, uph, rname, l_hid, stf_id in new_demo_users:
                    cursor.execute("SELECT id FROM users WHERE username = ? OR email = ?;", (uname, uemail))
                    existing_u = cursor.fetchone()
                    if not existing_u:
                        cursor.execute("""
                            INSERT INTO users (username, email, password_hash, salt, first_name, last_name, phone, linked_hostel_id, staff_id, is_active)
                            VALUES (?, ?, ?, '', ?, ?, ?, ?, ?, 1);
                        """, (uname, uemail, hashed_pw, ufn, uln, uph, l_hid, stf_id))
                        u_id = cursor.lastrowid
                        r_id = role_id_map.get(rname)
                        if r_id:
                            cursor.execute("INSERT OR IGNORE INTO user_roles (user_id, role_id) VALUES (?, ?);", (u_id, r_id))
                        if l_hid:
                            cursor.execute("INSERT OR IGNORE INTO user_scope_assignments (user_id, scope_type, scope_id) VALUES (?, 'hostel', ?);", (u_id, str(l_hid)))

            # 7. Validate zero foreign key violations
            violations = cursor.execute("PRAGMA foreign_key_check;").fetchall()
            if violations:
                violation_summary = [f"table={v[0]}, rowid={v[1]}, target={v[2]}, fkid={v[3]}" for v in violations]
                err_msg = f"Migration 020 foreign key validation failed with {len(violations)} unresolved violations: {violation_summary}"
                logger.error(err_msg)
                raise RuntimeError(err_msg)

            record_migration(conn, "020_enterprise_rbac_and_10_stakeholders", "Enterprise RBAC, 10 Core Administrative Stakeholders and Data Scoping", commit=False)
            conn.commit()
            applied_now.append("020_enterprise_rbac_and_10_stakeholders")
            logger.info("Migration 020_enterprise_rbac_and_10_stakeholders applied successfully.")

        return applied_now

    except Exception as e:

        conn.rollback()

        logger.error(f"Schema migration failed. Transaction rolled back: {e}", exc_info=True)

        raise

    finally:

        if should_close:

            conn.close()





if __name__ == "__main__":

    run_migrations()

