"""Comprehensive Test Suite for Database Architecture, Constraints, and Relationships.

Course: BBAT104 - Fundamentals of Total Quality Management (TQM)
Quality Goal: Q05 - Reduce Response Time
"""

import sqlite3
import unittest
from backend.app.database.connection import get_db_connection
from backend.app.database.init_db import initialize_database
from backend.app.database.migrations import run_migrations, get_applied_migrations
from backend.app.database.seeder import seed_database
from backend.app.database.schema import initialize_all_tables


class TestDatabaseArchitecture(unittest.TestCase):
    """Rigorous verification of the 39-table schema, integrity rules, and migrations."""

    def setUp(self):
        self.conn = sqlite3.connect(":memory:")
        self.conn.row_factory = sqlite3.Row
        self.conn.execute("PRAGMA foreign_keys = ON;")
        self.conn.execute("PRAGMA journal_mode = MEMORY;")

    def tearDown(self):
        self.conn.close()

    def test_01_all_39_tables_creation(self):
        """Assert that exactly 39 tables are created in the schema."""
        initialize_all_tables(self.conn)
        cursor = self.conn.cursor()
        cursor.execute("SELECT name FROM sqlite_master WHERE type='table' AND name NOT LIKE 'sqlite_%';")
        tables = [r[0] for r in cursor.fetchall()]
        self.assertEqual(len(tables), 39, f"Expected 39 tables, got {len(tables)}: {tables}")

    def test_02_foreign_key_orphan_block(self):
        """Assert inserting orphan records violates foreign-key constraints."""
        initialize_all_tables(self.conn)
        cursor = self.conn.cursor()
        # Non-existent building foreign key reference
        with self.assertRaises(sqlite3.IntegrityError):
            cursor.execute(
                "INSERT INTO floors (building_id, floor_number, floor_name) VALUES (9999, 1, 'Invalid Floor');"
            )

    def test_03_cascade_deletion_hierarchy(self):
        """Assert deleting a parent building cascades down to floors, rooms, and beds."""
        initialize_all_tables(self.conn)
        cursor = self.conn.cursor()

        cursor.execute("INSERT INTO hostels (name, code, hostel_type) VALUES ('Hostel H', 'HH', 'Boys');")
        h_id = cursor.lastrowid
        cursor.execute("INSERT INTO buildings (hostel_id, name, code, total_floors) VALUES (?, 'Building B', 'BB', 2);", (h_id,))
        b_id = cursor.lastrowid
        cursor.execute("INSERT INTO floors (building_id, floor_number, floor_name) VALUES (?, 1, 'Floor 1');", (b_id,))
        f_id = cursor.lastrowid
        cursor.execute("INSERT INTO rooms (floor_id, room_number, room_type, capacity, base_fee) VALUES (?, '101', 'Single', 1, 4000);", (f_id,))
        r_id = cursor.lastrowid
        cursor.execute("INSERT INTO beds (room_id, bed_number) VALUES (?, 'Bed-1');", (r_id,))
        self.conn.commit()

        # Delete Building
        cursor.execute("DELETE FROM buildings WHERE id = ?;", (b_id,))
        self.conn.commit()

        # Verify cascades
        cursor.execute("SELECT COUNT(*) FROM floors WHERE building_id = ?;", (b_id,))
        self.assertEqual(cursor.fetchone()[0], 0)
        cursor.execute("SELECT COUNT(*) FROM rooms WHERE id = ?;", (r_id,))
        self.assertEqual(cursor.fetchone()[0], 0)
        cursor.execute("SELECT COUNT(*) FROM beds WHERE room_id = ?;", (r_id,))
        self.assertEqual(cursor.fetchone()[0], 0)

    def test_04_unique_constraint_student_id(self):
        """Assert duplicate student ID is rejected."""
        initialize_all_tables(self.conn)
        cursor = self.conn.cursor()
        sql = """INSERT INTO students (student_id, first_name, last_name, email, phone, gender, branch, academic_year, admission_date)
                 VALUES (?, 'Test', 'User', ?, '9999999999', 'Male', 'CSE', '1st', '2026-08-01');"""
        cursor.execute(sql, ("ST_UNIQUE", "email1@univ.edu"))
        with self.assertRaises(sqlite3.IntegrityError):
            cursor.execute(sql, ("ST_UNIQUE", "email2@univ.edu"))

    def test_05_unique_constraint_room_per_floor(self):
        """Assert duplicate room number on same floor is rejected."""
        initialize_all_tables(self.conn)
        cursor = self.conn.cursor()
        cursor.execute("INSERT INTO hostels (name, code, hostel_type) VALUES ('H', 'H', 'Boys');")
        h_id = cursor.lastrowid
        cursor.execute("INSERT INTO buildings (hostel_id, name, code, total_floors) VALUES (?, 'B', 'B', 1);", (h_id,))
        b_id = cursor.lastrowid
        cursor.execute("INSERT INTO floors (building_id, floor_number, floor_name) VALUES (?, 1, 'F1');", (b_id,))
        f_id = cursor.lastrowid

        cursor.execute("INSERT INTO rooms (floor_id, room_number, room_type, capacity, base_fee) VALUES (?, '101', 'Double', 2, 4000);", (f_id,))
        with self.assertRaises(sqlite3.IntegrityError):
            cursor.execute("INSERT INTO rooms (floor_id, room_number, room_type, capacity, base_fee) VALUES (?, '101', 'Single', 1, 5000);", (f_id,))

    def test_06_check_constraint_capacity_bounds(self):
        """Assert room capacity must be between 1 and 10 beds."""
        initialize_all_tables(self.conn)
        cursor = self.conn.cursor()
        cursor.execute("INSERT INTO hostels (name, code, hostel_type) VALUES ('H', 'H', 'Boys');")
        h_id = cursor.lastrowid
        cursor.execute("INSERT INTO buildings (hostel_id, name, code, total_floors) VALUES (?, 'B', 'B', 1);", (h_id,))
        b_id = cursor.lastrowid
        cursor.execute("INSERT INTO floors (building_id, floor_number, floor_name) VALUES (?, 1, 'F1');", (b_id,))
        f_id = cursor.lastrowid

        # Capacity 0 (invalid)
        with self.assertRaises(sqlite3.IntegrityError):
            cursor.execute("INSERT INTO rooms (floor_id, room_number, room_type, capacity, base_fee) VALUES (?, '102', 'Double', 0, 4000);", (f_id,))

        # Capacity 15 (invalid)
        with self.assertRaises(sqlite3.IntegrityError):
            cursor.execute("INSERT INTO rooms (floor_id, room_number, room_type, capacity, base_fee) VALUES (?, '103', 'Double', 15, 4000);", (f_id,))

    def test_07_check_constraint_positive_payment(self):
        """Assert payments with zero or negative amounts fail check constraint."""
        initialize_all_tables(self.conn)
        cursor = self.conn.cursor()
        cursor.execute("""INSERT INTO students (student_id, first_name, last_name, email, phone, gender, branch, academic_year, admission_date)
                         VALUES ('ST_PAY', 'P', 'U', 'pay@univ.edu', '9999999999', 'Male', 'CSE', '1st', '2026-08-01');""")
        s_id = cursor.lastrowid
        cursor.execute("""INSERT INTO invoices (invoice_number, student_id, issue_date, due_date, total_amount)
                         VALUES ('INV-TEST', ?, '2026-08-01', '2026-08-10', 5000);""", (s_id,))
        inv_id = cursor.lastrowid

        with self.assertRaises(sqlite3.IntegrityError):
            cursor.execute("""INSERT INTO payments (payment_reference, invoice_id, student_id, amount, payment_method, payment_date)
                             VALUES ('REF-NEG', ?, ?, 0.0, 'UPI', '2026-08-02');""", (inv_id, s_id))

    def test_08_transaction_rollback_guarantee(self):
        """Assert multi-statement transaction completely rolls back on failure."""
        initialize_all_tables(self.conn)
        cursor = self.conn.cursor()
        cursor.execute("SELECT COUNT(*) FROM hostels;")
        initial_count = cursor.fetchone()[0]

        try:
            self.conn.execute("BEGIN TRANSACTION;")
            cursor.execute("INSERT INTO hostels (name, code, hostel_type) VALUES ('Rollback Hostel', 'RH', 'Boys');")
            # Force violation in second query
            cursor.execute("INSERT INTO hostels (name, code, hostel_type) VALUES ('Rollback Hostel', 'RH', 'INVALID_TYPE');")
            self.conn.commit()
        except sqlite3.IntegrityError:
            self.conn.rollback()

        cursor.execute("SELECT COUNT(*) FROM hostels;")
        final_count = cursor.fetchone()[0]
        self.assertEqual(initial_count, final_count)

    def test_09_migration_and_seeder_integration(self):
        """Verify migration runner tracks version and seeder loads demo entities."""
        # Clean connection
        mig_conn = sqlite3.connect(":memory:")
        mig_conn.row_factory = sqlite3.Row
        mig_conn.execute("PRAGMA foreign_keys = ON;")

        applied = run_migrations(mig_conn)
        self.assertIn("001_initial_schema", applied)
        self.assertIn("001_initial_schema", get_applied_migrations(mig_conn))

        seeded = seed_database(mig_conn)
        self.assertTrue(seeded)

        cursor = mig_conn.cursor()
        cursor.execute("SELECT COUNT(*) FROM users;")
        self.assertGreaterEqual(cursor.fetchone()[0], 5)

        cursor.execute("SELECT COUNT(*) FROM students;")
        self.assertGreaterEqual(cursor.fetchone()[0], 3)

        mig_conn.close()


if __name__ == "__main__":
    unittest.main()
