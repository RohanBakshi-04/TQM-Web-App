"""Area C Test Suite: RBAC, Data Scopes & Cross-Role Security (SA-02).

Course: BBAT104 - Fundamentals of Total Quality Management (TQM)
Quality Goal: Q05 - Zero-Defect Authorization, Cross-Scope Data Isolation & Audit Logging
"""

import os
import shutil
import sqlite3
import tempfile
import unittest
from typing import Any, Dict
from fastapi.testclient import TestClient

from backend.app.config import settings
from backend.app.database.init_db import initialize_database
from backend.app.main import app
from backend.app.services.auth_dependencies import verify_infrastructure_scope
from backend.app.services.rbac_data import (
    PERMISSION_EQUIVALENCES,
    _REVERSE_EQUIVALENCES,
    get_equivalent_permission,
)
from fastapi import HTTPException


class TestSA02RBACAndScopeIsolation(unittest.TestCase):
    """Exhaustive authorization tests verifying 9 canonical roles, cross-scope isolation, and audit privacy."""

    @classmethod
    def setUpClass(cls):
        cls.temp_dir = tempfile.mkdtemp(prefix="hms_sa02_rbac_")
        cls.db_path = os.path.join(cls.temp_dir, "test_rbac.db")
        cls.orig_db_path = settings.database_path
        settings.database_path = cls.db_path

        initialize_database()
        cls.client = TestClient(app)

        # Helper to obtain auth token for demo users
        def login_user(username: str, password: str = "Password123!") -> Dict[str, str]:
            res = cls.client.post("/api/v1/auth/login", json={"username_or_email": username, "password": password})
            assert res.status_code == 200, f"Login failed for {username}: {res.text}"
            token = res.json()["access_token"]
            return {"Authorization": f"Bearer {token}"}

        # 1. Super Admin
        cls.superadmin_headers = login_user("superadmin")

        # 2. Hostel Admin (linked to Hostel 1)
        cls.hosteladmin_headers = login_user("hosteladmin")

        # 3. Warden (linked to Hostel 1)
        cls.warden_headers = login_user("warden")

        # 4. Assistant Warden (linked to Hostel 2)
        cls.asstwarden_headers = login_user("asstwarden")

        # 5. Student
        cls.student_headers = login_user("rohan")

        # 6. Accountant
        cls.accountant_headers = login_user("accountant")

        # 7. Admission Officer
        cls.admission_headers = login_user("admission")

        # Create Institutional Admin user if not present
        conn = sqlite3.connect(cls.db_path)
        cur = conn.cursor()
        cur.execute("SELECT id FROM roles WHERE name = 'institutional_admin';")
        r_inst = cur.fetchone()
        inst_role_id = r_inst[0] if r_inst else 44

        # Seed institutional admin user
        from backend.app.services.security import hash_password
        pwd_hash = hash_password("Password123!")
        cur.execute("""
            INSERT OR IGNORE INTO users (id, username, email, password_hash, salt, first_name, last_name, is_active)
            VALUES (9001, 'instadmin', 'instadmin@univ.edu', ?, 'dummy_salt', 'Inst', 'Admin', 1);
        """, (pwd_hash,))
        cur.execute("INSERT OR IGNORE INTO user_roles (user_id, role_id) VALUES (9001, ?);", (inst_role_id,))

        conn.commit()
        conn.close()

        # Login Institutional Admin & Clerk
        cls.instadmin_headers = login_user("instadmin")
        cls.clerk_headers = login_user("clerk")

    @classmethod
    def tearDownClass(cls):
        settings.database_path = cls.orig_db_path
        shutil.rmtree(cls.temp_dir, ignore_errors=True)

    # -------------------------------------------------------------
    # 1. Permission Equivalences & Bidirectional Resolution
    # -------------------------------------------------------------
    def test_01_permission_equivalence_and_bidirectional_resolution(self):
        """Verify SA-02 granular permissions and bidirectional translation between legacy and enterprise formats."""
        required_sa02_mappings = {
            "institution:read": "institutions.profile.read",
            "institution:update": "institutions.profile.update",
            "campuses:read": "campuses.facility.read",
            "campuses:create": "campuses.facility.create",
            "campuses:update": "campuses.facility.update",
            "campuses:delete": "campuses.facility.delete",
            "campuses:manage": "campuses.facility.manage",
            "hostels:read": "hostels.facility.read",
            "hostels:create": "hostels.facility.create",
            "hostels:update": "hostels.facility.update",
            "hostels:delete": "hostels.facility.delete",
            "hostels:manage": "hostels.facility.manage",
            "buildings:read": "hostels.facility.read",
            "buildings:create": "hostels.facility.manage",
            "buildings:update": "hostels.facility.manage",
            "buildings:delete": "hostels.facility.manage",
            "infrastructure:read": "infrastructure.hierarchy.read",
            "infrastructure:manage": "infrastructure.capacity.manage",
            "rooms:manage": "infrastructure.capacity.manage",
            "beds:manage": "allocations.bed.update",
        }

        for legacy_perm, enterprise_perm in required_sa02_mappings.items():
            self.assertIn(legacy_perm, PERMISSION_EQUIVALENCES, f"Mapping missing for {legacy_perm}")
            self.assertEqual(PERMISSION_EQUIVALENCES[legacy_perm], enterprise_perm)

            # Forward resolution
            resolved = get_equivalent_permission(legacy_perm)
            self.assertEqual(resolved, enterprise_perm)

            # Bidirectional resolution consistency: resolving reverse must map back to same enterprise perm
            rev_resolved = get_equivalent_permission(enterprise_perm)
            self.assertEqual(get_equivalent_permission(rev_resolved), enterprise_perm)

    # -------------------------------------------------------------
    # 2. RBAC Across 9 Canonical Roles
    # -------------------------------------------------------------
    def test_02_rbac_canonical_nine_roles_authorization(self):
        """Test access authorization across all 9 canonical roles."""
        # 1. Super Admin: full access
        res = self.client.get("/api/v1/institutions", headers=self.superadmin_headers)
        self.assertEqual(res.status_code, 200)

        # 2. Institutional Admin: read institutional profile
        res = self.client.get("/api/v1/institutions", headers=self.instadmin_headers)
        self.assertEqual(res.status_code, 200)

        # 3. Student: strictly blocked (403 Forbidden)
        res = self.client.get("/api/v1/institutions", headers=self.student_headers)
        self.assertEqual(res.status_code, 403)

        res = self.client.post("/api/v1/campuses", json={"name": "Illegal", "code": "ILL-01", "address": "X"}, headers=self.student_headers)
        self.assertEqual(res.status_code, 403)

        # 4. Accountant: cannot manage campuses
        res = self.client.post("/api/v1/campuses", json={"name": "Acct Campus", "code": "ACC-01", "address": "X"}, headers=self.accountant_headers)
        self.assertEqual(res.status_code, 403)

        # 5. Admission Officer: cannot create campuses
        res = self.client.post("/api/v1/campuses", json={"name": "Adm Campus", "code": "ADM-01", "address": "X"}, headers=self.admission_headers)
        self.assertEqual(res.status_code, 403)

        # 6. Clerk: cannot delete campus
        res = self.client.delete("/api/v1/campuses/1", headers=self.clerk_headers)
        self.assertEqual(res.status_code, 403)

        # 7. Assistant Warden: cannot delete campus
        res = self.client.delete("/api/v1/campuses/1", headers=self.asstwarden_headers)
        self.assertEqual(res.status_code, 403)

        # 8. Warden: cannot delete campus
        res = self.client.delete("/api/v1/campuses/1", headers=self.warden_headers)
        self.assertEqual(res.status_code, 403)

        # 9. Hostel Admin: cannot delete campus
        res = self.client.delete("/api/v1/campuses/1", headers=self.hosteladmin_headers)
        self.assertEqual(res.status_code, 403)

    # -------------------------------------------------------------
    # 3. Cross-Scope Data Isolation
    # -------------------------------------------------------------
    def test_03_cross_scope_data_isolation(self):
        """Verify cross-scope data isolation: users cannot mutate hostels or campuses outside their assigned scope."""
        # Unit verification of verify_infrastructure_scope logic:
        # Mock warden assigned to hostel 1
        warden_user = {
            "id": 3,
            "username": "warden",
            "active_role": "warden",
            "role_code": "WARDEN",
            "linked_hostel_id": 1,
            "user_scopes": [{"type": "hostel", "id": 1}],
        }

        # Warden accessing own hostel 1 -> Allowed (no exception)
        verify_infrastructure_scope(warden_user, hostel_id=1)

        # Warden attempting to access hostel 2 -> Rejected with 403
        with self.assertRaises(HTTPException) as ctx:
            verify_infrastructure_scope(warden_user, hostel_id=2)
        self.assertEqual(ctx.exception.status_code, 403)
        self.assertIn("outside your assigned administrative scope", ctx.exception.detail)

        # Non-institutional role attempting institutional config change -> Rejected with 403
        with self.assertRaises(HTTPException) as ctx:
            verify_infrastructure_scope(warden_user, institution_id=1)
        self.assertEqual(ctx.exception.status_code, 403)
        self.assertIn("You do not possess institutional governance authority", ctx.exception.detail)

        # HTTP API validation:
        # Warden (linked to hostel 1) attempting to update hostel 2 category
        res = self.client.patch(
            "/api/v1/infrastructure/hostels/2/category",
            json={"category": "International"},
            headers=self.warden_headers
        )
        self.assertEqual(res.status_code, 403)
        self.assertIn("outside your assigned administrative scope", res.json()["detail"])

        # Assistant Warden attempting to update hostel 1 category -> Blocked (403 Forbidden)
        res = self.client.patch(
            "/api/v1/infrastructure/hostels/1/category",
            json={"category": "Deluxe"},
            headers=self.asstwarden_headers
        )
        self.assertEqual(res.status_code, 403)

        # Warden 1 successfully updating assigned hostel 1 -> Allowed (200 OK)
        res = self.client.patch(
            "/api/v1/infrastructure/hostels/1/category",
            json={"category": "General"},
            headers=self.warden_headers
        )
        self.assertEqual(res.status_code, 200)

        # Super Admin updating hostel 1 or 2 -> Allowed
        res = self.client.patch(
            "/api/v1/infrastructure/hostels/1/category",
            json={"category": "General"},
            headers=self.superadmin_headers
        )
        self.assertEqual(res.status_code, 200)

    # -------------------------------------------------------------
    # 4. Privilege Escalation Defense & Sensitive Data Privacy in Audit Logs
    # -------------------------------------------------------------
    def test_04_privilege_escalation_and_sensitive_audit_logs(self):
        """Verify non-super-admins cannot elevate privileges and audit logs never record plaintext passwords or tokens."""
        # 1. Non-super-admin attempting to assign super_admin role
        res = self.client.post(
            "/api/v1/campuses/1/admin",
            json={"admin_user_id": 9002, "role": "super_admin"},
            headers=self.hosteladmin_headers
        )
        self.assertEqual(res.status_code, 403)

        # 2. Check audit logs table for data privacy
        conn = sqlite3.connect(self.db_path)
        cur = conn.cursor()
        cur.execute("SELECT id, action, details FROM audit_logs WHERE details IS NOT NULL;")
        logs = cur.fetchall()
        conn.close()

        forbidden_leak_terms = ["Password123!", "password_hash", "access_token", "Bearer ey"]
        for log_id, action, details in logs:
            for term in forbidden_leak_terms:
                self.assertNotIn(
                    term,
                    details,
                    f"Audit log #{log_id} ({action}) must never contain sensitive secrets: {term}"
                )


if __name__ == "__main__":
    unittest.main()
