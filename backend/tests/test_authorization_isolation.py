"""Dedicated Comprehensive Regression Tests for Authorization Hardening and Student Isolation.

Validates all 16 scenarios specified in Phase 2.1:
1. Student accesses own record (numeric ID) -> PASS
2. Student accesses own record (string ID) -> PASS
3. Student accesses another student record (numeric ID) -> 403 Forbidden
4. Student accesses another student record (string ID) -> 403 Forbidden
5. Dual-role user (e.g. student + assistant_warden) acting as student -> 403 Forbidden (active_role takes precedence)
6. Warden with assigned hostel accesses resident student -> PASS
7. Warden accesses student allocated to different hostel -> 403 Forbidden
8. Warden with unassigned hostel (None / empty) -> 403 Forbidden (fails closed)
9. Warden accesses student with no active room allocation -> 403 Forbidden (fails closed)
10. Warden accesses non-existent student ID -> 403 Forbidden (fails closed)
11. Assistant Warden with assigned hostel accesses resident student -> PASS
12. Assistant Warden accesses student in different hostel -> 403 Forbidden
13. Assistant Warden with unassigned hostel -> 403 Forbidden (fails closed)
14. Parent accesses linked ward -> PASS
15. Parent accesses unlinked student -> 403 Forbidden
16. Financial/Audit and Super Admin authorization scoping -> PASS / 403
"""

import os
import shutil
import sqlite3
import tempfile
import unittest
from fastapi import HTTPException

from backend.app.config import settings
from backend.app.database.init_db import initialize_database
from backend.app.services.auth_dependencies import verify_student_isolation


class TestAuthorizationIsolationScenarios(unittest.TestCase):
    """Test suite for verify_student_isolation strict fail-closed enforcement."""

    @classmethod
    def setUpClass(cls):
        # Create an isolated temporary database for testing
        cls.temp_dir = tempfile.mkdtemp()
        cls.db_path = os.path.join(cls.temp_dir, "test_auth_isolation.db")
        cls.orig_db_path = settings.database_path
        settings.database_path = cls.db_path

        conn = sqlite3.connect(cls.db_path)
        conn.row_factory = sqlite3.Row
        initialize_database(conn, seed=True)

        cur = conn.cursor()
        # Insert a resident student allocated to hostel 2 (Sarojini Naidu Girls Hostel)
        cur.execute("""
            INSERT INTO students (student_id, first_name, last_name, email, phone, gender, date_of_birth, branch, academic_year, semester, admission_date, status)
            VALUES ('STU-H2-FEMALE', 'Ananya', 'Sen', 'ananya.sen@test.edu', '9888877777', 'Female', '2005-06-15', 'ECE', '2nd Year', '3rd', '2026-08-01', 'Active');
        """)
        h2_student_pk = cur.lastrowid
        cur.execute("""
            INSERT INTO room_allocations (student_id, bed_id, room_id, start_date, end_date, allocation_status, approval_status)
            VALUES (?, 6, 4, '2026-08-01', '2027-05-31', 'Active', 'Approved');
        """, (h2_student_pk,))

        # Inspect seeded students and allocations
        cur.execute("""
            SELECT s.id, s.student_id, bld.hostel_id
            FROM students s
            JOIN room_allocations ra ON ra.student_id = s.id AND ra.allocation_status = 'Active'
            JOIN rooms rm ON rm.id = ra.room_id
            JOIN floors fl ON fl.id = rm.floor_id
            JOIN buildings bld ON bld.id = fl.building_id;
        """)
        allocations = cur.fetchall()
        cls.student_hostel_map = {row["id"]: row["hostel_id"] for row in allocations}
        cls.student_str_map = {row["id"]: row["student_id"] for row in allocations}

        # Pick students in hostel 1 and hostel 2
        cls.h1_students = [sid for sid, hid in cls.student_hostel_map.items() if hid == 1]
        cls.h2_students = [sid for sid, hid in cls.student_hostel_map.items() if hid == 2]

        # Insert an unallocated student (no active room allocation)
        cur.execute("""
            INSERT INTO students (student_id, first_name, last_name, email, phone, gender, date_of_birth, branch, academic_year, semester, admission_date, status)
            VALUES ('STU-UNALLOCATED-99', 'Unallocated', 'Student', 'unallocated@test.edu', '9999999999', 'Male', '2005-01-01', 'CSE', '3rd Year', '5th', '2026-08-01', 'Active');
        """)
        cls.unallocated_student_id = cur.lastrowid

        # Insert active parent-student link for seeded parent user -> h1_students[0]
        cur.execute("SELECT id FROM users WHERE username = 'parent';")
        p_row = cur.fetchone()
        cls.parent_user_id = p_row["id"] if p_row else 11
        cur.execute("""
            INSERT OR REPLACE INTO parent_student_links (parent_user_id, student_id, relationship, status)
            VALUES (?, ?, 'Parent', 'Active');
        """, (cls.parent_user_id, cls.h1_students[0]))

        conn.commit()
        conn.close()

    @classmethod
    def tearDownClass(cls):
        settings.database_path = cls.orig_db_path
        shutil.rmtree(cls.temp_dir, ignore_errors=True)

    def test_01_student_access_own_record_by_numeric_id(self):
        """Student accessing own record by numeric primary key must succeed."""
        sid = self.h1_students[0]
        current_user = {
            "id": 100,
            "username": "student_user",
            "active_role": "student",
            "roles": ["student"],
            "linked_student_id": sid,
            "student_id": self.student_str_map[sid],
            "permissions": []
        }
        verify_student_isolation(sid, current_user)

    def test_02_student_access_own_record_by_string_id(self):
        """Student accessing own record by string student_id must succeed."""
        sid = self.h1_students[0]
        str_id = self.student_str_map[sid]
        current_user = {
            "id": 100,
            "username": "student_user",
            "active_role": "student",
            "roles": ["student"],
            "linked_student_id": sid,
            "student_id": str_id,
            "permissions": []
        }
        verify_student_isolation(str_id, current_user)

    def test_03_student_access_other_student_numeric_id(self):
        """Student accessing other student's record by numeric ID must be rejected with 403."""
        sid1 = self.h1_students[0]
        sid2 = self.h1_students[1] if len(self.h1_students) > 1 else self.h2_students[0]
        current_user = {
            "id": 100,
            "username": "student_user",
            "active_role": "student",
            "roles": ["student"],
            "linked_student_id": sid1,
            "student_id": self.student_str_map[sid1],
            "permissions": []
        }
        with self.assertRaises(HTTPException) as ctx:
            verify_student_isolation(sid2, current_user)
        self.assertEqual(ctx.exception.status_code, 403)

    def test_04_student_access_other_student_string_id(self):
        """Student accessing other student's record by string student_id must be rejected with 403."""
        sid1 = self.h1_students[0]
        sid2 = self.h1_students[1] if len(self.h1_students) > 1 else self.h2_students[0]
        current_user = {
            "id": 100,
            "username": "student_user",
            "active_role": "student",
            "roles": ["student"],
            "linked_student_id": sid1,
            "student_id": self.student_str_map[sid1],
            "permissions": []
        }
        with self.assertRaises(HTTPException) as ctx:
            verify_student_isolation(self.student_str_map[sid2], current_user)
        self.assertEqual(ctx.exception.status_code, 403)

    def test_05_student_dual_role_active_student_idor(self):
        """User with dual roles (e.g. student + assistant_warden) acting as student must be restricted to own record."""
        sid1 = self.h1_students[0]
        sid2 = self.h1_students[1] if len(self.h1_students) > 1 else self.h2_students[0]
        current_user = {
            "id": 100,
            "username": "dual_role_user",
            "active_role": "student",  # Acting as student
            "roles": ["student", "assistant_warden"],
            "linked_student_id": sid1,
            "student_id": self.student_str_map[sid1],
            "linked_hostel_id": 1,
            "permissions": []
        }
        with self.assertRaises(HTTPException) as ctx:
            verify_student_isolation(sid2, current_user)
        self.assertEqual(ctx.exception.status_code, 403)

    def test_06_warden_assigned_hostel_access_resident_student(self):
        """Warden with assigned hostel must be granted access to student allocated in that hostel."""
        sid = self.h1_students[0]
        current_user = {
            "id": 3,
            "username": "warden_user",
            "active_role": "warden",
            "roles": ["warden"],
            "linked_hostel_id": 1,
            "permissions": []
        }
        verify_student_isolation(sid, current_user)

    def test_07_warden_assigned_hostel_access_different_hostel_student(self):
        """Warden with hostel 1 must be rejected with 403 when accessing student allocated in hostel 2."""
        if not self.h2_students:
            self.skipTest("No students allocated to hostel 2 in test database")
        sid2 = self.h2_students[0]
        current_user = {
            "id": 3,
            "username": "warden_user",
            "active_role": "warden",
            "roles": ["warden"],
            "linked_hostel_id": 1,
            "permissions": []
        }
        with self.assertRaises(HTTPException) as ctx:
            verify_student_isolation(sid2, current_user)
        self.assertEqual(ctx.exception.status_code, 403)

    def test_08_warden_unassigned_hostel_fails_closed(self):
        """Warden with NO assigned hostel facility must be rejected with 403 for any student access."""
        sid = self.h1_students[0]
        current_user = {
            "id": 3,
            "username": "unassigned_warden",
            "active_role": "warden",
            "roles": ["warden"],
            "linked_hostel_id": None,
            "permissions": []
        }
        with self.assertRaises(HTTPException) as ctx:
            verify_student_isolation(sid, current_user)
        self.assertEqual(ctx.exception.status_code, 403)
        self.assertIn("no assigned hostel facility", ctx.exception.detail)

    def test_09_warden_access_unallocated_student_fails_closed(self):
        """Warden accessing student without an active room allocation must be rejected with 403."""
        current_user = {
            "id": 3,
            "username": "warden_user",
            "active_role": "warden",
            "roles": ["warden"],
            "linked_hostel_id": 1,
            "permissions": []
        }
        with self.assertRaises(HTTPException) as ctx:
            verify_student_isolation(self.unallocated_student_id, current_user)
        self.assertEqual(ctx.exception.status_code, 403)
        self.assertIn("no active room allocation", ctx.exception.detail)

    def test_10_warden_access_nonexistent_student_fails_closed(self):
        """Warden accessing non-existent student must be rejected with 403."""
        current_user = {
            "id": 3,
            "username": "warden_user",
            "active_role": "warden",
            "roles": ["warden"],
            "linked_hostel_id": 1,
            "permissions": []
        }
        with self.assertRaises(HTTPException) as ctx:
            verify_student_isolation(999999, current_user)
        self.assertEqual(ctx.exception.status_code, 403)
        self.assertIn("not found or inaccessible", ctx.exception.detail)

    def test_11_assistant_warden_assigned_hostel_access_resident(self):
        """Assistant Warden with assigned hostel 1 must be granted access to student in hostel 1."""
        sid = self.h1_students[0]
        current_user = {
            "id": 4,
            "username": "assistant_warden_user",
            "active_role": "assistant_warden",
            "roles": ["assistant_warden"],
            "linked_hostel_id": 1,
            "permissions": []
        }
        verify_student_isolation(sid, current_user)

    def test_12_assistant_warden_different_hostel_student(self):
        """Assistant Warden with assigned hostel 1 must be rejected when accessing student in hostel 2."""
        if not self.h2_students:
            self.skipTest("No students allocated to hostel 2 in test database")
        sid2 = self.h2_students[0]
        current_user = {
            "id": 4,
            "username": "assistant_warden_user",
            "active_role": "assistant_warden",
            "roles": ["assistant_warden"],
            "linked_hostel_id": 1,
            "permissions": []
        }
        with self.assertRaises(HTTPException) as ctx:
            verify_student_isolation(sid2, current_user)
        self.assertEqual(ctx.exception.status_code, 403)

    def test_13_assistant_warden_unassigned_hostel_fails_closed(self):
        """Assistant Warden with NO assigned hostel facility must be rejected with 403."""
        sid = self.h1_students[0]
        current_user = {
            "id": 4,
            "username": "unassigned_assistant_warden",
            "active_role": "assistant_warden",
            "roles": ["assistant_warden"],
            "linked_hostel_id": None,
            "permissions": []
        }
        with self.assertRaises(HTTPException) as ctx:
            verify_student_isolation(sid, current_user)
        self.assertEqual(ctx.exception.status_code, 403)
        self.assertIn("no assigned hostel facility", ctx.exception.detail)

    def test_14_parent_access_linked_ward(self):
        """Parent accessing authorized linked ward must succeed."""
        sid = self.h1_students[0]
        current_user = {
            "id": self.parent_user_id,
            "user_id": self.parent_user_id,
            "username": "parent_user",
            "active_role": "parent_guardian",
            "roles": ["parent_guardian"],
            "linked_student_id": sid,
            "permissions": []
        }
        verify_student_isolation(sid, current_user)

    def test_15_parent_access_unlinked_student(self):
        """Parent accessing unauthorized non-ward student must be rejected with 403."""
        sid = self.h1_students[0]
        current_user = {
            "id": 999,
            "username": "other_parent",
            "active_role": "parent_guardian",
            "roles": ["parent_guardian"],
            "permissions": []
        }
        with self.assertRaises(HTTPException) as ctx:
            verify_student_isolation(sid, current_user)
        self.assertEqual(ctx.exception.status_code, 403)

    def test_16_financial_audit_and_super_admin_scopes(self):
        """Accountant and Auditor must have valid read permissions; Super Admin has campus access."""
        sid = self.h1_students[0]

        # Accountant with finance:read
        acc_user = {
            "id": 5,
            "username": "accountant_user",
            "active_role": "accountant",
            "roles": ["accountant"],
            "permissions": ["finance:read"]
        }
        verify_student_isolation(sid, acc_user)

        # Auditor with audit:read
        audit_user = {
            "id": 6,
            "username": "auditor_user",
            "active_role": "auditor",
            "roles": ["auditor"],
            "permissions": ["audit:read"]
        }
        verify_student_isolation(sid, audit_user)

        # Accountant without permissions -> 403
        bad_acc = {
            "id": 5,
            "username": "bad_acc",
            "active_role": "accountant",
            "roles": ["accountant"],
            "permissions": []
        }
        with self.assertRaises(HTTPException) as ctx:
            verify_student_isolation(sid, bad_acc)
        self.assertEqual(ctx.exception.status_code, 403)

        # Super Admin -> campus-wide access
        admin_user = {
            "id": 1,
            "username": "admin",
            "active_role": "super_admin",
            "roles": ["super_admin"],
            "permissions": []
        }
        verify_student_isolation(sid, admin_user)


if __name__ == "__main__":
    unittest.main()
