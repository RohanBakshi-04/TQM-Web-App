"""Verification tests for Prompt 03 RBAC Schema, Roles, and Auth Tables."""

import sqlite3
import unittest
from backend.app.database.init_db import initialize_database
from backend.app.services.security import verify_password


class TestPrompt03RBACSchema(unittest.TestCase):
    def setUp(self):
        self.conn = sqlite3.connect(":memory:")
        self.conn.row_factory = sqlite3.Row
        self.conn.execute("PRAGMA foreign_keys = ON;")
        initialize_database(self.conn, seed=True)

    def tearDown(self):
        self.conn.close()

    def test_12_roles_seeded(self):
        cursor = self.conn.cursor()
        cursor.execute("SELECT name FROM roles ORDER BY name ASC;")
        roles = [r[0] for r in cursor.fetchall()]
        expected_15 = [
            "accountant", "admission_officer", "assistant_warden", "auditor",
            "hostel_admin", "hostel_clerk", "it_admin", "maintenance_staff",
            "mess_manager", "parent_guardian", "security_guard",
            "security_supervisor", "student", "super_admin", "warden"
        ]
        for r in expected_15:
            self.assertIn(r, roles)
        self.assertGreaterEqual(len(roles), 15)

    def test_auth_tables_created(self):
        cursor = self.conn.cursor()
        cursor.execute("SELECT name FROM sqlite_master WHERE type='table';")
        tables = set([r[0] for r in cursor.fetchall()])
        self.assertTrue({"refresh_tokens", "password_resets", "login_history"}.issubset(tables))

    def test_bcrypt_password_verification_on_seeded_users(self):
        cursor = self.conn.cursor()
        cursor.execute("SELECT password_hash FROM users WHERE username = 'superadmin';")
        row = cursor.fetchone()
        self.assertIsNotNone(row)
        self.assertTrue(verify_password("Password123!", row["password_hash"]))
        self.assertFalse(verify_password("WrongPassword", row["password_hash"]))

    def test_role_permissions_populated(self):
        cursor = self.conn.cursor()
        cursor.execute("""
            SELECT COUNT(*) FROM role_permissions rp
            JOIN roles r ON rp.role_id = r.id
            WHERE r.name = 'super_admin';
        """)
        superadmin_perms_count = cursor.fetchone()[0]
        self.assertGreater(superadmin_perms_count, 10)


if __name__ == "__main__":
    unittest.main()
