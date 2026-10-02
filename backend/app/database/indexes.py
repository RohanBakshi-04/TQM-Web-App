"""Initial Database Indexes for Relational Foreign Keys and Lookup Columns.

Course: BBAT104 - Fundamentals of Total Quality Management (TQM)
Quality Goal: Q05 - Reduce Response Time
"""

import sqlite3
from typing import List, Optional
from backend.app.database.connection import get_db_connection
from backend.app.utils.logger import logger

INITIAL_INDEXES_SQL = [
    # User & Access Management Indexes
    "CREATE INDEX IF NOT EXISTS idx_users_username ON users(username);",
    "CREATE INDEX IF NOT EXISTS idx_users_email ON users(email);",
    "CREATE INDEX IF NOT EXISTS idx_user_roles_user ON user_roles(user_id);",
    "CREATE INDEX IF NOT EXISTS idx_role_permissions_role ON role_permissions(role_id);",

    # Student Management Indexes
    "CREATE INDEX IF NOT EXISTS idx_students_student_id ON students(student_id);",
    "CREATE INDEX IF NOT EXISTS idx_students_email ON students(email);",
    "CREATE INDEX IF NOT EXISTS idx_students_branch ON students(branch);",
    "CREATE INDEX IF NOT EXISTS idx_student_guardians_student ON student_guardians(student_id);",
    "CREATE INDEX IF NOT EXISTS idx_student_documents_student ON student_documents(student_id);",

    # Hostel & Inventory Hierarchy Indexes
    "CREATE INDEX IF NOT EXISTS idx_buildings_hostel ON buildings(hostel_id);",
    "CREATE INDEX IF NOT EXISTS idx_floors_building ON floors(building_id);",
    "CREATE INDEX IF NOT EXISTS idx_rooms_floor ON rooms(floor_id);",
    "CREATE INDEX IF NOT EXISTS idx_rooms_status ON rooms(status);",
    "CREATE INDEX IF NOT EXISTS idx_beds_room ON beds(room_id);",
    "CREATE INDEX IF NOT EXISTS idx_beds_status ON beds(status);",
    "CREATE INDEX IF NOT EXISTS idx_allocations_student ON room_allocations(student_id);",
    "CREATE INDEX IF NOT EXISTS idx_allocations_bed ON room_allocations(bed_id);",
    "CREATE INDEX IF NOT EXISTS idx_allocations_room ON room_allocations(room_id);",
    "CREATE INDEX IF NOT EXISTS idx_allocations_status ON room_allocations(allocation_status);",

    # Operations & Grievances Indexes
    "CREATE INDEX IF NOT EXISTS idx_attendance_student_date ON attendance(student_id, date);",
    "CREATE INDEX IF NOT EXISTS idx_leave_requests_student ON leave_requests(student_id);",
    "CREATE INDEX IF NOT EXISTS idx_visitor_logs_visitor ON visitor_logs(visitor_id);",
    "CREATE INDEX IF NOT EXISTS idx_complaints_ticket ON complaints(complaint_id);",
    "CREATE INDEX IF NOT EXISTS idx_complaints_student ON complaints(student_id);",
    "CREATE INDEX IF NOT EXISTS idx_complaints_status ON complaints(status);",
    "CREATE INDEX IF NOT EXISTS idx_complaint_updates_ticket ON complaint_updates(complaint_id);",
    "CREATE INDEX IF NOT EXISTS idx_maintenance_room ON maintenance_tasks(room_id);",

    # Financial Indexes
    "CREATE INDEX IF NOT EXISTS idx_invoices_number ON invoices(invoice_number);",
    "CREATE INDEX IF NOT EXISTS idx_invoices_student ON invoices(student_id);",
    "CREATE INDEX IF NOT EXISTS idx_invoices_status ON invoices(status);",
    "CREATE INDEX IF NOT EXISTS idx_invoice_items_invoice ON invoice_items(invoice_id);",
    "CREATE INDEX IF NOT EXISTS idx_payments_ref ON payments(payment_reference);",
    "CREATE INDEX IF NOT EXISTS idx_payments_invoice ON payments(invoice_id);",

    # Mess & Inventory Indexes
    "CREATE INDEX IF NOT EXISTS idx_mess_sub_student ON mess_subscriptions(student_id);",
    "CREATE INDEX IF NOT EXISTS idx_meal_att_student_date ON meal_attendance(student_id, date);",
    "CREATE INDEX IF NOT EXISTS idx_inventory_item_code ON inventory_items(item_code);",
    "CREATE INDEX IF NOT EXISTS idx_inventory_category ON inventory_items(category_id);",
    "CREATE INDEX IF NOT EXISTS idx_inv_trans_item ON inventory_transactions(item_id);"
]


def create_initial_indexes(conn: Optional[sqlite3.Connection] = None) -> List[str]:
    """Build all initial performance indexes on foreign keys and primary lookups."""
    should_close = False
    if conn is None:
        conn = get_db_connection()
        should_close = True

    created_indexes = []
    try:
        cursor = conn.cursor()
        for sql in INITIAL_INDEXES_SQL:
            cursor.execute(sql)
            idx_name = sql.split()[5]
            created_indexes.append(idx_name)
        conn.commit()
        logger.info(f"Created {len(created_indexes)} initial database indexes.")
        return created_indexes
    finally:
        if should_close:
            conn.close()
