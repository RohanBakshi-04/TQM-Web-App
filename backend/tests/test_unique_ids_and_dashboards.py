import unittest
import sqlite3
import os
from fastapi import HTTPException
from backend.app.services.auth_service import AuthService
from backend.app.services.allocation_service import AllocationService
from backend.app.models.allocation_dto import AllocationCreate

DB_PATH = os.path.join(os.path.dirname(__file__), "..", "..", "data", "hostel_web.db")

class TestUniqueStaffAndStudentIDs(unittest.TestCase):
    def setUp(self):
        self.conn = sqlite3.connect(DB_PATH)
        self.conn.row_factory = sqlite3.Row
        self.conn.execute("PRAGMA foreign_keys = ON;")

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

    def test_allocation_and_suggestions_with_alphanumeric_student_id(self):
        """Verify allocating rooms using alphanumeric Student IDs (e.g. STU-202611-0089)."""
        cur = self.conn.cursor()
        test_sid = "STU-202611-9988"

        # Create a test active student with alphanumeric student_id
        cur.execute("DELETE FROM students WHERE student_id = ?;", (test_sid,))
        cur.execute("""
            INSERT INTO students (student_id, first_name, last_name, email, phone, gender, branch, academic_year, admission_date, status)
            VALUES (?, 'Ananya', 'Sen', 'ananya.test9988@university.edu', '9876543210', 'Female', 'CSE', '1st Year', date('now'), 'Active');
        """, (test_sid,))
        self.conn.commit()

        # 1. Test AI Suggestions with alphanumeric Student ID
        suggestions = AllocationService.get_allocation_suggestions(self.conn, test_sid)
        self.assertIsInstance(suggestions, list)
        self.assertGreater(len(suggestions), 0, "Should generate suggestions for active female student")

        # 2. Test Room Allocation using alphanumeric Student ID string
        candidate_bed = suggestions[0]["bed_id"]
        alloc_data = AllocationCreate(
            student_id=test_sid,
            bed_id=candidate_bed,
            start_date="2026-11-01",
            remarks="Test Alphanumeric Student ID Allotment"
        )
        res = AllocationService.create_allocation(self.conn, alloc_data, allocated_by_user_id=1)
        self.assertIsNotNone(res)
        self.assertEqual(res["student_enrollment"], test_sid)
        self.assertEqual(res["allocation_status"], "Active")

        # Cleanup
        cur.execute("DELETE FROM room_allocations WHERE id = ?;", (res["id"],))
        cur.execute("UPDATE beds SET status = 'Available' WHERE id = ?;", (candidate_bed,))
        cur.execute("DELETE FROM students WHERE student_id = ?;", (test_sid,))
        self.conn.commit()

    def test_allocation_fails_cleanly_for_nonexistent_student_id(self):
        """Verify non-existent student ID returns HTTP 404 with helpful message."""
        alloc_data = AllocationCreate(
            student_id="STU-NONEXISTENT-0000",
            bed_id=1,
            start_date="2026-11-01"
        )
        with self.assertRaises(HTTPException) as ctx:
            AllocationService.create_allocation(self.conn, alloc_data)
        self.assertEqual(ctx.exception.status_code, 404)
        self.assertIn("not found", ctx.exception.detail)


if __name__ == "__main__":
    unittest.main()
