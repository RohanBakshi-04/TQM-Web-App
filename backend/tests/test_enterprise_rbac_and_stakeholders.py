"""Comprehensive Test Suite for Enterprise RBAC & 15 Stakeholder Architecture.

Verifies:
1. All 15 stakeholder logins, tokens, role codes, and categories.
2. Canonical role codes and aliases in require_roles().
3. Standardized module.resource.action and legacy module:action permissions in require_permissions().
4. Data-level isolation and IT Admin privacy restriction.
5. Role-switching protection (single-role blocked, unauthorized elevation to super_admin blocked).
6. Super Admin Role & Permission Management API (create custom role, system role protection, delete custom role).

Course: BBAT104 - Fundamentals of Total Quality Management (TQM)
Quality Goal: Q05 - Reduce Response Time
"""

import os
import shutil
import tempfile
import unittest
from fastapi.testclient import TestClient

from backend.app.config import settings
from backend.app.database.init_db import initialize_database
from backend.app.database.connection import get_db_connection
from backend.app.main import app
from backend.app.services.auth_dependencies import (
    require_roles,
    require_permissions,
    verify_student_isolation
)


class TestEnterpriseRBACAndStakeholders(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.temp_dir = tempfile.mkdtemp()
        cls.db_path = os.path.join(cls.temp_dir, "test_enterprise_rbac.db")
        cls.orig_db_path = settings.database_path
        settings.database_path = cls.db_path
        initialize_database()

        cls.client = TestClient(app)

    @classmethod
    def tearDownClass(cls):
        settings.database_path = cls.orig_db_path
        if os.path.exists(cls.temp_dir):
            shutil.rmtree(cls.temp_dir, ignore_errors=True)

    def test_01_all_15_stakeholder_logins_and_role_codes(self):
        """Verify all 15 stakeholders can authenticate and receive canonical role codes and categories."""
        stakeholders = [
            # 10 Core Administrative & Operational Roles
            ("superadmin", "super_admin", "SUPER_ADMIN", "Executive / Leadership"),
            ("hosteladmin", "hostel_admin", "HOSTEL_DIRECTOR", "Executive / Leadership"),
            ("warden", "warden", "CHIEF_WARDEN", "Operational / Student Life"),
            ("asstwarden", "assistant_warden", "ASSISTANT_WARDEN", "Operational / Student Life"),
            ("clerk", "hostel_clerk", "HOSTEL_CLERK", "Administrative / Support"),
            ("accountant", "accountant", "ACCOUNTANT", "Administrative / Support"),
            ("admission", "admission_officer", "ADMISSION_OFFICER", "Administrative / Support"),
            ("secsupervisor", "security_supervisor", "SECURITY_SUPERVISOR", "Security & Gate"),
            ("security", "security_guard", "SECURITY_GUARD", "Security & Gate"),
            ("itadmin", "it_admin", "IT_ADMIN", "Technical & Compliance"),
            # 5 Preserved Functional Roles
            ("rohan", "student", "STUDENT", "Resident & Beneficiary"),
            ("parent", "parent_guardian", "PARENT_GUARDIAN", "Resident & Beneficiary"),
            ("messmanager", "mess_manager", "MESS_MANAGER", "Operational / Student Life"),
            ("maintenance", "maintenance_staff", "MAINTENANCE_STAFF", "Operational / Student Life"),
            ("evaluator", "auditor", "AUDITOR", "Technical & Compliance"),
        ]

        for username, exp_role, exp_code, exp_cat in stakeholders:
            res = self.client.post("/api/v1/auth/login", json={
                "username_or_email": username,
                "password": "Password123!"
            })
            self.assertEqual(res.status_code, 200, f"Login failed for {username}: {res.text}")
            data = res.json()
            self.assertIn("access_token", data)
            user = data.get("user", {})
            self.assertEqual(user.get("active_role"), exp_role, f"Role mismatch for {username}")
            self.assertEqual(user.get("role_code"), exp_code, f"Role code mismatch for {username}")
            self.assertEqual(user.get("stakeholder_category"), exp_cat, f"Category mismatch for {username}")

    def test_02_require_roles_canonical_codes_and_aliases(self):
        """Verify require_roles() resolves canonical uppercase codes, names, and aliases."""
        # Login as hosteladmin (HOSTEL_DIRECTOR)
        res = self.client.post("/api/v1/auth/login", json={
            "username_or_email": "hosteladmin",
            "password": "Password123!"
        })
        token = res.json()["access_token"]
        headers = {"Authorization": f"Bearer {token}"}

        # User profile endpoint checks auth dependency
        me_res = self.client.get("/api/v1/auth/me", headers=headers)
        self.assertEqual(me_res.status_code, 200)
        user_dict = me_res.json()

        # Test require_roles with canonical code HOSTEL_DIRECTOR
        checker1 = require_roles("HOSTEL_DIRECTOR")
        self.assertEqual(checker1(user_dict)["active_role"], "hostel_admin")

        # Test require_roles with legacy name hostel_admin
        checker2 = require_roles("hostel_admin")
        self.assertEqual(checker2(user_dict)["active_role"], "hostel_admin")

        # Test require_roles with alias hostel_director
        checker3 = require_roles("hostel_director")
        self.assertEqual(checker3(user_dict)["active_role"], "hostel_admin")

        # Login as warden (CHIEF_WARDEN)
        res_w = self.client.post("/api/v1/auth/login", json={
            "username_or_email": "warden",
            "password": "Password123!"
        })
        token_w = res_w.json()["access_token"]
        user_w = self.client.get("/api/v1/auth/me", headers={"Authorization": f"Bearer {token_w}"}).json()

        checker_w1 = require_roles("CHIEF_WARDEN")
        self.assertEqual(checker_w1(user_w)["active_role"], "warden")
        checker_w2 = require_roles("warden")
        self.assertEqual(checker_w2(user_w)["active_role"], "warden")

    def test_03_require_permissions_standardized_and_legacy(self):
        """Verify require_permissions() succeeds for both module.resource.action and legacy module:action."""
        res = self.client.post("/api/v1/auth/login", json={
            "username_or_email": "clerk",
            "password": "Password123!"
        })
        token = res.json()["access_token"]
        user_clerk = self.client.get("/api/v1/auth/me", headers={"Authorization": f"Bearer {token}"}).json()

        # Test legacy format
        checker_leg = require_permissions("student:read")
        self.assertEqual(checker_leg(user_clerk)["active_role"], "hostel_clerk")

        # Test enterprise standardized format
        checker_ent = require_permissions("students.profile.read")
        self.assertEqual(checker_ent(user_clerk)["active_role"], "hostel_clerk")

        # Test clerk-specific permission
        checker_clerk = require_permissions("clerk.document.verify")
        self.assertEqual(checker_clerk(user_clerk)["active_role"], "hostel_clerk")

    def test_04_data_level_isolation_it_admin_restriction(self):
        """Verify IT Administrator accounts are strictly blocked from accessing student personal records."""
        from fastapi import HTTPException
        res = self.client.post("/api/v1/auth/login", json={
            "username_or_email": "itadmin",
            "password": "Password123!"
        })
        token = res.json()["access_token"]
        user_it = self.client.get("/api/v1/auth/me", headers={"Authorization": f"Bearer {token}"}).json()

        with self.assertRaises(HTTPException) as ctx:
            verify_student_isolation(student_id=1, current_user=user_it)
        self.assertEqual(ctx.exception.status_code, 403)
        self.assertIn("IT Administrator accounts are restricted", ctx.exception.detail)

    def test_05_data_level_isolation_warden_and_clerk(self):
        """Verify Chief Warden is scoped to their assigned facility."""
        res = self.client.post("/api/v1/auth/login", json={
            "username_or_email": "warden",
            "password": "Password123!"
        })
        token = res.json()["access_token"]
        user_warden = self.client.get("/api/v1/auth/me", headers={"Authorization": f"Bearer {token}"}).json()

        # Student 1 is in Warden's assigned hostel 1 -> Allowed
        verify_student_isolation(student_id=1, current_user=user_warden)

    def test_06_role_switching_protection_single_role_blocked(self):
        """Verify single-role users cannot switch roles."""
        res = self.client.post("/api/v1/auth/login", json={
            "username_or_email": "rohan",
            "password": "Password123!"
        })
        token = res.json()["access_token"]
        headers = {"Authorization": f"Bearer {token}"}

        switch_res = self.client.post("/api/v1/auth/switch-role", json={"role": "warden"}, headers=headers)
        self.assertEqual(switch_res.status_code, 403)
        self.assertIn("disabled for single-role", switch_res.json()["detail"])

    def test_07_role_switching_protection_unauthorized_elevation_blocked(self):
        """Verify multi-role accounts cannot switch to unassigned roles or elevate to super_admin."""
        with get_db_connection() as conn:
            c = conn.cursor()
            c.execute("""
                INSERT INTO users (username, email, password_hash, salt, first_name, last_name, is_active)
                VALUES ('multi_guard', 'guard.multi@univ.edu', 'hash', '', 'Multi', 'Guard', 1);
            """)
            uid = c.lastrowid
            c.execute("SELECT id FROM roles WHERE name = 'security_guard';")
            rg = c.fetchone()[0]
            c.execute("SELECT id FROM roles WHERE name = 'security_supervisor';")
            rs = c.fetchone()[0]
            c.execute("INSERT INTO user_roles (user_id, role_id) VALUES (?, ?);", (uid, rg))
            c.execute("INSERT INTO user_roles (user_id, role_id) VALUES (?, ?);", (uid, rs))
            conn.commit()

        try:
            from backend.app.services.auth_service import AuthService
            # Allowed switch between assigned roles
            sw1 = AuthService.switch_user_role(user_id=uid, target_role="security_supervisor")
            self.assertTrue(sw1["success"])
            self.assertEqual(sw1["role_code"], "SECURITY_SUPERVISOR")

            # Unauthorized elevation to super_admin rejected
            from fastapi import HTTPException
            with self.assertRaises(HTTPException) as ctx:
                AuthService.switch_user_role(user_id=uid, target_role="super_admin")
            self.assertEqual(ctx.exception.status_code, 403)
            self.assertIn("not assigned to your account", ctx.exception.detail)

            # Audit log check
            with get_db_connection() as conn:
                c = conn.cursor()
                c.execute("""
                    SELECT action, details FROM audit_logs
                    WHERE user_id = ? AND action = 'UNAUTHORIZED_ROLE_SWITCH_ATTEMPT';
                """, (uid,))
                log_row = c.fetchone()
                self.assertIsNotNone(log_row)
                self.assertIn("super_admin", log_row["details"])
        finally:
            with get_db_connection() as conn:
                c = conn.cursor()
                c.execute("DELETE FROM audit_logs WHERE user_id = ?;", (uid,))
                c.execute("DELETE FROM user_roles WHERE user_id = ?;", (uid,))
                c.execute("DELETE FROM users WHERE id = ?;", (uid,))
                conn.commit()

    def test_08_super_admin_role_management_api(self):
        """Verify Super Admin Role & Permission Management API endpoints."""
        res = self.client.post("/api/v1/auth/login", json={
            "username_or_email": "superadmin",
            "password": "Password123!"
        })
        token = res.json()["access_token"]
        headers = {"Authorization": f"Bearer {token}"}

        # 1. List roles: should return all 15 roles
        roles_res = self.client.get("/api/v1/admin/roles", headers=headers)
        self.assertEqual(roles_res.status_code, 200)
        roles_data = roles_res.json()
        self.assertGreaterEqual(len(roles_data), 15)

        # 2. Create custom role
        create_res = self.client.post("/api/v1/admin/roles", json={
            "name": "floor_captain",
            "code": "FLOOR_CAPTAIN",
            "description": "Floor student representative assisting assistant warden",
            "stakeholder_category": "Operational / Student Life",
            "permissions": ["students.profile.read", "attendance.record.read"]
        }, headers=headers)
        self.assertEqual(create_res.status_code, 201)
        created_role = create_res.json()
        self.assertEqual(created_role["name"], "floor_captain")
        self.assertEqual(created_role["code"], "FLOOR_CAPTAIN")
        self.assertFalse(created_role["is_system"])
        self.assertFalse(created_role["is_system_role"])
        role_id = created_role["id"]

        # 3. Attempting to delete a system role (e.g. role 1) must be rejected with 400
        del_sys_res = self.client.delete("/api/v1/admin/roles/1", headers=headers)
        self.assertEqual(del_sys_res.status_code, 400)
        self.assertIn("Protected system role", del_sys_res.json()["detail"])

        # 4. Deleting custom role succeeds
        del_custom_res = self.client.delete(f"/api/v1/admin/roles/{role_id}", headers=headers)
        self.assertEqual(del_custom_res.status_code, 200)
        self.assertEqual(del_custom_res.json()["status"], "success")


if __name__ == "__main__":
    unittest.main()
