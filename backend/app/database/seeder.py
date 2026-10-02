"""Safe Demonstration Data Seeder for Development and Evaluation.

Course: BBAT104 - Fundamentals of Total Quality Management (TQM)
Quality Goal: Q05 - Reduce Response Time
"""

import hashlib
import os
import secrets
import sqlite3
from typing import Optional
from backend.app.database.connection import get_db_connection
from backend.app.utils.logger import logger


def _hash_demo_password(password: str) -> tuple[str, str]:
    """Hash password using PBKDF2-HMAC-SHA256 for safe demonstration data."""
    salt = secrets.token_hex(16)
    key = hashlib.pbkdf2_hmac("sha256", password.encode("utf-8"), salt.encode("utf-8"), 100_000)
    return key.hex(), salt


def seed_database(conn: Optional[sqlite3.Connection] = None) -> bool:
    """Populate database with structured demonstration records across all domains."""
    should_close = False
    if conn is None:
        conn = get_db_connection()
        should_close = True

    try:
        cursor = conn.cursor()

        # Check if users already exist to avoid duplicate seeding
        cursor.execute("SELECT COUNT(*) FROM users;")
        if cursor.fetchone()[0] > 0:
            logger.info("Database already seeded. Skipping seeder execution.")
            return False

        logger.info("Beginning database demonstration data seeding...")

        # 1. Seed Roles
        roles_data = [
            ("admin", "Full system administrator access", 1),
            ("warden", "Hostel chief warden operations and student welfare", 1),
            ("student", "Hostel resident self-service portal", 1),
            ("staff", "Maintenance technician and caretaker desk", 1),
            ("auditor", "TQM compliance and quality assurance evaluator", 1)
        ]
        cursor.executemany("INSERT INTO roles (name, description, is_system) VALUES (?, ?, ?);", roles_data)

        # 2. Seed Permissions
        permissions_data = [
            ("users.manage", "users", "Manage system accounts and roles"),
            ("hostel.manage", "hostel", "Manage rooms, beds, and buildings"),
            ("students.manage", "students", "Manage student profiles and admissions"),
            ("allocations.manage", "allocations", "Perform bed allotments and checkout"),
            ("complaints.redress", "complaints", "Update and resolve grievance tickets"),
            ("finance.invoicing", "finance", "Generate invoices and record payments"),
            ("audit.read", "audit", "Inspect Q05 performance telemetry and audit logs")
        ]
        cursor.executemany("INSERT INTO permissions (name, module, description) VALUES (?, ?, ?);", permissions_data)

        # 3. Seed Users (Safe demo credentials: admin123, warden123, student123, staff123, audit123)
        h_admin, s_admin = _hash_demo_password("admin123")
        h_warden, s_warden = _hash_demo_password("warden123")
        h_student, s_student = _hash_demo_password("student123")
        h_staff, s_staff = _hash_demo_password("staff123")
        h_audit, s_audit = _hash_demo_password("audit123")

        users_data = [
            ("admin", "admin@univ.edu", h_admin, s_admin, "System", "Administrator", "9800000001"),
            ("warden", "warden@univ.edu", h_warden, s_warden, "Dr. Anand", "Kulkarni", "9800000002"),
            ("rohan", "rohan.bakshi@univ.edu", h_student, s_student, "Rohan", "Bakshi", "9810301057"),
            ("caretaker", "caretaker@univ.edu", h_staff, s_staff, "Ramesh", "Kumar", "9800000004"),
            ("evaluator", "evaluator@univ.edu", h_audit, s_audit, "TQM Faculty", "Auditor", "9800000005")
        ]
        cursor.executemany(
            """INSERT INTO users (username, email, password_hash, salt, first_name, last_name, phone)
               VALUES (?, ?, ?, ?, ?, ?, ?);""",
            users_data
        )

        # Map User Roles
        cursor.execute("INSERT INTO user_roles (user_id, role_id) VALUES (1, 1);") # admin -> admin
        cursor.execute("INSERT INTO user_roles (user_id, role_id) VALUES (2, 2);") # warden -> warden
        cursor.execute("INSERT INTO user_roles (user_id, role_id) VALUES (3, 3);") # rohan -> student
        cursor.execute("INSERT INTO user_roles (user_id, role_id) VALUES (4, 4);") # caretaker -> staff
        cursor.execute("INSERT INTO user_roles (user_id, role_id) VALUES (5, 5);") # evaluator -> auditor

        # 4. Seed Hostel, Buildings, Floors, Rooms & Beds
        cursor.execute(
            """INSERT INTO hostels (name, code, hostel_type, address, warden_id, contact_phone, contact_email)
               VALUES ('Rabindranath Tagore Hostel', 'RTH-01', 'Boys', 'North Campus, Tech Avenue', 2, '011-2700101', 'tagore.hostel@univ.edu');"""
        )
        hostel_id = cursor.lastrowid

        cursor.execute("INSERT INTO buildings (hostel_id, name, code, total_floors) VALUES (?, 'Aryabhata Block', 'BLK-A', 3);", (hostel_id,))
        bldg_a = cursor.lastrowid

        cursor.execute("INSERT INTO floors (building_id, floor_number, floor_name) VALUES (?, 1, 'First Floor');", (bldg_a,))
        flr_1 = cursor.lastrowid
        cursor.execute("INSERT INTO floors (building_id, floor_number, floor_name) VALUES (?, 2, 'Second Floor');", (bldg_a,))
        flr_2 = cursor.lastrowid

        # Rooms
        cursor.execute("INSERT INTO rooms (floor_id, room_number, room_type, capacity, base_fee, status) VALUES (?, '101', 'Single', 1, 6000.0, 'Full');", (flr_1,))
        r101 = cursor.lastrowid
        cursor.execute("INSERT INTO rooms (floor_id, room_number, room_type, capacity, base_fee, status) VALUES (?, '102', 'Double', 2, 4500.0, 'Partially_Occupied');", (flr_1,))
        r102 = cursor.lastrowid
        cursor.execute("INSERT INTO rooms (floor_id, room_number, room_type, capacity, base_fee, status) VALUES (?, '201', 'Double', 2, 4500.0, 'Available');", (flr_2,))
        r201 = cursor.lastrowid

        # Beds
        cursor.execute("INSERT INTO beds (room_id, bed_number, status) VALUES (?, '101-A', 'Occupied');", (r101,))
        b101_a = cursor.lastrowid
        cursor.execute("INSERT INTO beds (room_id, bed_number, status) VALUES (?, '102-A', 'Occupied');", (r102,))
        b102_a = cursor.lastrowid
        cursor.execute("INSERT INTO beds (room_id, bed_number, status) VALUES (?, '102-B', 'Available');", (r102,))
        b102_b = cursor.lastrowid
        cursor.execute("INSERT INTO beds (room_id, bed_number, status) VALUES (?, '201-A', 'Available');", (r201,))
        cursor.execute("INSERT INTO beds (room_id, bed_number, status) VALUES (?, '201-B', 'Available');", (r201,))

        # 5. Seed Students (Fictional Demo Records)
        students_data = [
            ("2410301057", 3, "Rohan", "Bakshi", "rohan.bakshi@univ.edu", "9810301057", "Male", "2005-04-12", "B+", "CSE", "3rd Year", "5th", "Hostel Resident", "2026-08-01"),
            ("2410301012", None, "Priya", "Sharma", "priya.sharma@univ.edu", "9811223344", "Female", "2006-02-18", "O+", "ECE", "2nd Year", "3rd", "East Wing", "2026-08-01"),
            ("2410301034", None, "Aarav", "Patel", "aarav.patel@univ.edu", "9822334455", "Male", "2005-09-25", "A+", "CSE", "3rd Year", "5th", "North Wing", "2026-08-02")
        ]
        cursor.executemany(
            """INSERT INTO students (student_id, user_id, first_name, last_name, email, phone, gender, date_of_birth, blood_group, branch, academic_year, semester, address, admission_date)
               VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?);""",
            students_data
        )
        s_rohan = 1
        s_priya = 2
        s_aarav = 3

        # 6. Seed Guardians
        cursor.execute(
            """INSERT INTO guardians (name, relationship, phone, email, occupation, address)
               VALUES ('Sunil Bakshi', 'Father', '9810301000', 'sunil.bakshi@demo.com', 'Senior Engineer', 'Civil Lines, City');"""
        )
        g_id = cursor.lastrowid
        cursor.execute("INSERT INTO student_guardians (student_id, guardian_id, is_primary) VALUES (?, ?, 1);", (s_rohan, g_id))

        # 7. Seed Room Allocations
        cursor.execute(
            """INSERT INTO room_allocations (student_id, bed_id, room_id, start_date, fee_status, allocation_status, remarks, allocated_by)
               VALUES (?, ?, ?, '2026-08-01', 'Paid', 'Active', 'Allocated for Academic Year 2026-27', 1);""",
            (s_rohan, b101_a, r101)
        )
        cursor.execute(
            """INSERT INTO room_allocations (student_id, bed_id, room_id, start_date, fee_status, allocation_status, remarks, allocated_by)
               VALUES (?, ?, ?, '2026-08-01', 'Pending', 'Active', 'Double sharing room allotment', 1);""",
            (s_aarav, b102_a, r102)
        )

        # 8. Seed Complaints & History
        cursor.execute(
            """INSERT INTO complaints (complaint_id, student_id, room_id, category, title, description, severity, status, assigned_to)
               VALUES ('CMP-2026-001', ?, ?, 'Electrical', 'Study Lamp Socket Failure', 'Wall socket on study table not powering laptop charger', 'Medium', 'In_Progress', 4);""",
            (s_rohan, r101)
        )
        cmp_id = cursor.lastrowid
        cursor.execute(
            """INSERT INTO complaint_updates (complaint_id, updated_by, previous_status, new_status, comment)
               VALUES (?, 4, 'Pending', 'In_Progress', 'Caretaker Ramesh assigned to inspect and replace socket unit.');""",
            (cmp_id,)
        )

        # 9. Seed Financials: Fee Structure, Invoice & Payment
        cursor.execute(
            """INSERT INTO fee_structures (name, room_type, academic_year, semester, amount, payment_frequency)
               VALUES ('Semester 5 Single Occupancy Fee', 'Single', '2026-27', '5th', 6000.0, 'Monthly');"""
        )
        fee_id = cursor.lastrowid

        cursor.execute(
            """INSERT INTO invoices (invoice_number, student_id, fee_structure_id, issue_date, due_date, total_amount, paid_amount, status)
               VALUES ('INV-2026-08-001', ?, ?, '2026-08-01', '2026-08-15', 6000.0, 6000.0, 'Paid');""",
            (s_rohan, fee_id)
        )
        inv_id = cursor.lastrowid

        cursor.execute("INSERT INTO invoice_items (invoice_id, title, amount) VALUES (?, 'Room 101 Monthly Rent', 6000.0);", (inv_id,))

        cursor.execute(
            """INSERT INTO payments (payment_reference, invoice_id, student_id, amount, payment_method, payment_date, transaction_id, status)
               VALUES ('PAY-2026-08-01-ROH', ?, ?, 6000.0, 'UPI', '2026-08-05', 'UPI-TXN-99887766', 'Completed');""",
            (inv_id, s_rohan)
        )

        # 10. Seed Mess Menu & Inventory
        cursor.execute(
            """INSERT INTO mess_menus (day_of_week, meal_type, items_description, is_special)
               VALUES ('Monday', 'Breakfast', 'Idli, Sambhar, Coconut Chutney, Tea / Coffee', 0);"""
        )
        cursor.execute(
            """INSERT INTO mess_menus (day_of_week, meal_type, items_description, is_special)
               VALUES ('Monday', 'Lunch', 'Dal Tadka, Paneer Butter Masala, Roti, Rice, Gulab Jamun', 1);"""
        )

        cursor.execute("INSERT INTO inventory_categories (name, description) VALUES ('Electrical Supplies', 'Switches, wires, bulbs, fuses');")
        cat_id = cursor.lastrowid

        cursor.execute(
            """INSERT INTO inventory_items (category_id, item_code, name, description, unit, quantity_in_stock, min_reorder_level, unit_price)
               VALUES (?, 'ELE-SOC-16A', '16A 3-Pin Wall Socket', 'Modular electrical socket with switch', 'pieces', 45, 10, 180.0);""",
            (cat_id,)
        )

        # 11. Seed System Settings
        cursor.execute("INSERT INTO system_settings (setting_key, setting_value, category, description) VALUES ('institution_name', 'University College of Engineering', 'general', 'Institute name');")
        cursor.execute("INSERT INTO system_settings (setting_key, setting_value, category, description) VALUES ('q05_latency_target_ms', '10.0', 'performance', 'Target response time SLA');")

        conn.commit()
        logger.info("Database demonstration data seeded successfully.")
        return True
    except Exception as e:
        logger.error(f"Seeding failed: {e}")
        conn.rollback()
        raise
    finally:
        if should_close:
            conn.close()


if __name__ == "__main__":
    seed_database()
