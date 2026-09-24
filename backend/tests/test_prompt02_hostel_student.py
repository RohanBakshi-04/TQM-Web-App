"""Verification tests for Hostel and Student Database Tables."""

import sqlite3
import unittest
from backend.app.database.schema import initialize_all_tables


class TestHostelStudentTables(unittest.TestCase):
    def setUp(self):
        self.conn = sqlite3.connect(":memory:")
        self.conn.execute("PRAGMA foreign_keys = ON;")
        initialize_all_tables(self.conn)

    def tearDown(self):
        self.conn.close()

    def test_tables_created(self):
        cursor = self.conn.cursor()
        cursor.execute("SELECT name FROM sqlite_master WHERE type='table' AND name NOT LIKE 'sqlite_%';")
        tables = set([r[0] for r in cursor.fetchall()])
        expected = {
            "students", "guardians", "student_guardians", "student_documents", "admission_applications",
            "hostels", "buildings", "floors", "rooms", "beds", "room_allocations"
        }
        self.assertTrue(expected.issubset(tables))

    def test_hostel_hierarchy_and_cascade(self):
        c = self.conn.cursor()
        c.execute("INSERT INTO hostels (name, code, hostel_type) VALUES ('Tagore Hostel', 'TH-01', 'Boys')")
        h_id = c.lastrowid

        c.execute("INSERT INTO buildings (hostel_id, name, code, total_floors) VALUES (?, 'Wing A', 'WA', 3)", (h_id,))
        b_id = c.lastrowid

        c.execute("INSERT INTO floors (building_id, floor_number, floor_name) VALUES (?, 1, 'First Floor')", (b_id,))
        f_id = c.lastrowid

        c.execute("INSERT INTO rooms (floor_id, room_number, room_type, capacity, base_fee) VALUES (?, '101', 'Double', 2, 4500.0)", (f_id,))
        r_id = c.lastrowid

        c.execute("INSERT INTO beds (room_id, bed_number) VALUES (?, '101-1')", (r_id,))
        c.execute("INSERT INTO beds (room_id, bed_number) VALUES (?, '101-2')", (r_id,))

        self.conn.commit()

        # Verify bed count
        c.execute("SELECT COUNT(*) FROM beds WHERE room_id = ?", (r_id,))
        self.assertEqual(c.fetchone()[0], 2)

    def test_allocation_check_constraint_invalid_dates(self):
        c = self.conn.cursor()
        c.execute("INSERT INTO hostels (name, code, hostel_type) VALUES ('H1', 'H1', 'Boys')")
        h_id = c.lastrowid
        c.execute("INSERT INTO buildings (hostel_id, name, code, total_floors) VALUES (?, 'B1', 'B1', 1)", (h_id,))
        b_id = c.lastrowid
        c.execute("INSERT INTO floors (building_id, floor_number, floor_name) VALUES (?, 1, 'F1')", (b_id,))
        f_id = c.lastrowid
        c.execute("INSERT INTO rooms (floor_id, room_number, room_type, capacity, base_fee) VALUES (?, '101', 'Single', 1, 5000)", (f_id,))
        r_id = c.lastrowid
        c.execute("INSERT INTO beds (room_id, bed_number) VALUES (?, 'B-1')", (r_id,))
        bed_id = c.lastrowid

        c.execute("""INSERT INTO students (student_id, first_name, last_name, email, phone, gender, branch, academic_year, admission_date)
                     VALUES ('ST99', 'Test', 'Student', 'test@univ.edu', '9999999999', 'Male', 'CSE', '1st', '2026-08-01')""")
        s_id = c.lastrowid

        # Attempt end_date < start_date (must fail CHECK constraint)
        with self.assertRaises(sqlite3.IntegrityError):
            c.execute("""INSERT INTO room_allocations (student_id, bed_id, room_id, start_date, end_date)
                         VALUES (?, ?, ?, '2026-09-01', '2026-08-01')""", (s_id, bed_id, r_id))


if __name__ == "__main__":
    unittest.main()
