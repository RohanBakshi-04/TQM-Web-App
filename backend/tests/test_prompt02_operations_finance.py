"""Verification tests for Operations, Maintenance, and Financial Tables."""

import sqlite3
import unittest
from backend.app.database.schema import initialize_all_tables


class TestOperationsFinanceTables(unittest.TestCase):
    def setUp(self):
        self.conn = sqlite3.connect(":memory:")
        self.conn.execute("PRAGMA foreign_keys = ON;")
        initialize_all_tables(self.conn)

    def tearDown(self):
        self.conn.close()

    def test_all_39_tables_exist(self):
        c = self.conn.cursor()
        c.execute("SELECT name FROM sqlite_master WHERE type='table' AND name NOT LIKE 'sqlite_%';")
        tables = [r[0] for r in c.fetchall()]
        self.assertEqual(len(tables), 39, f"Expected 39 tables, got {len(tables)}: {tables}")

    def test_invoice_and_payment_constraints(self):
        c = self.conn.cursor()
        # Seed student
        c.execute("""INSERT INTO students (student_id, first_name, last_name, email, phone, gender, branch, academic_year, admission_date)
                     VALUES ('ST_FIN', 'Finance', 'Student', 'fin@univ.edu', '9888877777', 'Male', 'IT', '1st', '2026-08-01')""")
        s_id = c.lastrowid

        # Insert Invoice
        c.execute("""INSERT INTO invoices (invoice_number, student_id, issue_date, due_date, total_amount, paid_amount)
                     VALUES ('INV-2026-001', ?, '2026-08-01', '2026-08-15', 5000.0, 0.0)""", (s_id,))
        inv_id = c.lastrowid

        # Insert Invoice Item
        c.execute("INSERT INTO invoice_items (invoice_id, title, amount) VALUES (?, 'Hostel Rent Semester 1', 5000.0)", (inv_id,))

        # Verify Payment positive amount constraint (<= 0 must fail)
        with self.assertRaises(sqlite3.IntegrityError):
            c.execute("""INSERT INTO payments (payment_reference, invoice_id, student_id, amount, payment_method, payment_date)
                         VALUES ('PAY-000', ?, ?, -500.0, 'UPI', '2026-08-05')""", (inv_id, s_id))

        # Insert valid Payment
        c.execute("""INSERT INTO payments (payment_reference, invoice_id, student_id, amount, payment_method, payment_date)
                     VALUES ('PAY-001', ?, ?, 5000.0, 'UPI', '2026-08-05')""", (inv_id, s_id))
        self.conn.commit()

        c.execute("SELECT COUNT(*) FROM payments WHERE invoice_id = ?", (inv_id,))
        self.assertEqual(c.fetchone()[0], 1)

    def test_complaint_history_preservation(self):
        c = self.conn.cursor()
        c.execute("""INSERT INTO students (student_id, first_name, last_name, email, phone, gender, branch, academic_year, admission_date)
                     VALUES ('ST_COMP', 'Complainant', 'Student', 'comp@univ.edu', '9111122222', 'Female', 'CSE', '2nd', '2026-08-01')""")
        s_id = c.lastrowid

        c.execute("""INSERT INTO complaints (complaint_id, student_id, category, title, description, severity, status)
                     VALUES ('CMP-001', ?, 'Electrical', 'Light flickering', 'Tube light in study desk flickers', 'Low', 'Pending')""", (s_id,))
        c_id = c.lastrowid

        # Record Status Updates in complaint_updates
        c.execute("""INSERT INTO complaint_updates (complaint_id, previous_status, new_status, comment)
                     VALUES (?, 'Pending', 'In_Progress', 'Electrician assigned to inspect fixture')""", (c_id,))
        c.execute("""INSERT INTO complaint_updates (complaint_id, previous_status, new_status, comment)
                     VALUES (?, 'In_Progress', 'Resolved', 'Choke replaced and tested')""", (c_id,))
        self.conn.commit()

        c.execute("SELECT COUNT(*) FROM complaint_updates WHERE complaint_id = ?", (c_id,))
        self.assertEqual(c.fetchone()[0], 2)


if __name__ == "__main__":
    unittest.main()
