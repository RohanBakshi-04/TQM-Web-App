import unittest
import sqlite3
import os
from backend.app.services.auth_service import AuthService

DB_PATH = os.path.join(os.path.dirname(__file__), "..", "..", "data", "hostel_web.db")

class TestUniqueStaffAndStudentIDs(unittest.TestCase):
    def setUp(self):
        self.conn = sqlite3.connect(DB_PATH)
        self.conn.row_factory = sqlite3.Row

    def tearDown(self):
        self.conn.close()

    def test_all_staff_ids_are_unique_and_non_null_for_staff(self):
        """Verify all staff users have non-null, uniquely formatted STF-XXXX IDs without any duplicates."""
        cur = self.conn.cursor()
        cur.execute("""
            SELECT u.id, u.username, u.staff_id, GROUP_CONCAT(r.name) as roles
            FROM users u
            JOIN user_roles ur ON u.id = ur.user_id
            JOIN roles r ON ur.role_id = r.id
            WHERE r.name NOT IN ('student', 'parent_guardian')
            GROUP BY u.id
        """)
        staff_users = cur.fetchall()
        self.assertGreater(len(staff_users), 0, "There should be staff members in the system.")

        staff_ids = []
        for staff in staff_users:
            sid = staff["staff_id"]
            self.assertIsNotNone(sid, f"Staff user {staff['username']} must have a staff_id")
            self.assertTrue(sid.startswith("STF-"), f"Staff ID {sid} should start with STF-")
            staff_ids.append(sid)

        # Check for zero duplicates
        unique_staff_ids = set(staff_ids)
        self.assertEqual(len(staff_ids), len(unique_staff_ids), f"Duplicate staff IDs detected: {len(staff_ids)} vs {len(unique_staff_ids)}")

    def test_all_student_ids_are_unique_without_duplicates(self):
        """Verify all student records in the database have strictly unique student_id values."""
        cur = self.conn.cursor()
        cur.execute("SELECT id, student_id FROM students")
        students = cur.fetchall()
        self.assertGreater(len(students), 0, "There should be student records in the system.")

        student_ids = []
        for s in students:
            sid = s["student_id"]
            self.assertIsNotNone(sid, f"Student record {s['id']} must have a student_id")
            student_ids.append(sid)

        unique_student_ids = set(student_ids)
        self.assertEqual(len(student_ids), len(unique_student_ids), f"Duplicate student IDs detected: {len(student_ids)} vs {len(unique_student_ids)}")

    def test_unique_indexes_exist_in_db_schema(self):
        """Verify SQLite unique indexes are established for staff_id on users and student_id on students."""
        cur = self.conn.cursor()
        cur.execute("PRAGMA index_list('users')")
        user_indexes = [row["name"] for row in cur.fetchall()]
        self.assertIn("idx_users_staff_id", user_indexes, "idx_users_staff_id must exist on users table")

        cur.execute("PRAGMA index_list('students')")
        student_indexes = [row["name"] for row in cur.fetchall()]
        self.assertTrue(any("student_id" in idx for idx in student_indexes), "students table must have unique index on student_id")

    def test_auth_profile_returns_staff_and_student_ids(self):
        """Verify authenticate_user returns both staff_id and student_id in profile."""
        # 1. Staff user check: superadmin
        admin_user = AuthService.authenticate_user("superadmin", "Password123!", conn=self.conn)
        self.assertIsNotNone(admin_user["staff_id"], "Superadmin must have staff_id")
        self.assertEqual(admin_user["staff_id"], "STF-0001")
        self.assertIsNone(admin_user["student_id"], "Superadmin should not have student_id")

        # 2. Staff user check: warden
        warden_user = AuthService.authenticate_user("warden", "Password123!", conn=self.conn)
        self.assertIsNotNone(warden_user["staff_id"], "Warden must have staff_id")
        self.assertEqual(warden_user["staff_id"], "STF-0003")
        self.assertIsNone(warden_user["student_id"], "Warden should not have student_id")

        # 3. Staff user check: maintenance
        maint_user = AuthService.authenticate_user("maintenance", "Password123!", conn=self.conn)
        self.assertIsNotNone(maint_user["staff_id"], "Maintenance staff must have staff_id")
        self.assertEqual(maint_user["staff_id"], "STF-0008")

        # 4. Student user check: rohan
        student_user = AuthService.authenticate_user("rohan", "Password123!", conn=self.conn)
        self.assertIsNotNone(student_user["student_id"], "Rohan must have student_id")
        self.assertEqual(student_user["student_id"], "2410301057")


if __name__ == "__main__":
    unittest.main()
