"""Comprehensive Integration, Authorization, and RBAC Security Tests for 12 Role-Based Dashboards.

Verifies:
1. Public landing page availability vs unauthenticated endpoint protection (HTTP 401).
2. Dedicated authenticated workspace metrics for all 12 stakeholder roles:
   - super_admin, hostel_admin, warden, assistant_warden, student, accountant,
     mess_manager, maintenance_staff, security_guard, admission_officer, parent_guardian, auditor.
3. Role-switching security and multi-role account policies:
   - Single-role Assistant Warden CANNOT switch to Super Admin (HTTP 403).
   - Single-role Assistant Warden CANNOT switch to Warden (HTTP 403).
   - Single-role Student CANNOT switch to Accountant or Super Admin (HTTP 403).
   - Single-role Accountant CANNOT switch to Super Admin (HTTP 403).
   - Multi-role user can switch ONLY between assigned roles (HTTP 200).
   - Multi-role user CANNOT switch to unassigned Super Admin role (HTTP 403).
   - Role switch operations are recorded in audit logs.
   - Non-existent/invalid role identifiers are strictly rejected (HTTP 403).
4. Super Admin privilege protection and direct API defense:
   - Assistant Warden cannot access admin settings, users, or role management (HTTP 403).
   - Hostel Admin cannot assign roles or escalate privileges (HTTP 403).
   - Student cannot access admin settings (HTTP 403).
   - Security Guard cannot access admin settings (HTTP 403).
   - Super Admin can legitimately access admin configurations (HTTP 200).
5. Strict data isolation & functional RBAC boundaries:
   - Student cannot inspect another student's profile (HTTP 403).
   - Student can inspect own profile (HTTP 200).
   - Parent cannot access unlinked student's records (HTTP 403).
   - Auditor cannot modify records (HTTP 403).
   - Security Guard cannot access financial billing (HTTP 403).
   - Maintenance Staff cannot access room allocations (HTTP 403).
   - Accountant cannot approve student leaves (HTTP 403).
"""

import json
import unittest
from fastapi.testclient import TestClient

from backend.app.main import app
from backend.app.database.connection import get_db_connection
from backend.app.database.init_db import initialize_database
from backend.app.services.security import hash_password


class TestRoleDashboardsAndAuth(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        initialize_database()
        cls.client = TestClient(app)
        cls.tokens = {}
        cls.users = {}

        # 12 Seeded stakeholders
        stakeholders = [
            ("superadmin", "super_admin"),
            ("hosteladmin", "hostel_admin"),
            ("warden", "warden"),
            ("asstwarden", "assistant_warden"),
            ("rohan", "student"),
            ("accountant", "accountant"),
            ("messmanager", "mess_manager"),
            ("maintenance", "maintenance_staff"),
            ("security", "security_guard"),
            ("admission", "admission_officer"),
            ("parent", "parent_guardian"),
            ("evaluator", "auditor")
        ]

        for username, expected_role in stakeholders:
            resp = cls.client.post("/api/v1/auth/login", json={
                "username_or_email": username,
                "password": "Password123!"
            })
            if resp.status_code == 200:
                data = resp.json()
                cls.tokens[username] = data["access_token"]
                cls.users[username] = data["user"]

        # Seed a test multi-role user for legitimate role-switching verification
        conn = get_db_connection()
        try:
            cursor = conn.cursor()
            cursor.execute("SELECT id FROM users WHERE username = 'multirole_user';")
            existing = cursor.fetchone()
            if not existing:
                cursor.execute("""
                    INSERT INTO users (username, email, password_hash, salt, first_name, last_name, is_active)
                    VALUES ('multirole_user', 'multirole@hostel.edu', ?, '', 'Multi', 'Role', 1);
                """, (hash_password("Password123!"),))
                user_id = cursor.lastrowid

                # Assign two roles: accountant and hostel_admin
                cursor.execute("SELECT id FROM roles WHERE name = 'accountant';")
                r_acc = cursor.fetchone()[0]
                cursor.execute("SELECT id FROM roles WHERE name = 'hostel_admin';")
                r_hadmin = cursor.fetchone()[0]

                cursor.execute("INSERT INTO user_roles (user_id, role_id) VALUES (?, ?);", (user_id, r_acc))
                cursor.execute("INSERT INTO user_roles (user_id, role_id) VALUES (?, ?);", (user_id, r_hadmin))
                conn.commit()

            # Login as multi-role user
            resp = cls.client.post("/api/v1/auth/login", json={
                "username_or_email": "multirole_user",
                "password": "Password123!"
            })
            if resp.status_code == 200:
                data = resp.json()
                cls.tokens["multirole_user"] = data["access_token"]
                cls.users["multirole_user"] = data["user"]
        finally:
            conn.close()

    def _headers(self, username: str):
        token = self.tokens.get(username)
        return {"Authorization": f"Bearer {token}"} if token else {}

    # ==========================================
    # 1. PUBLIC LANDING & AUTH PROTECTION TESTS
    # ==========================================

    def test_public_landing_page_accessible_without_auth(self):
        """Public homepage is accessible to unauthenticated visitors."""
        resp = self.client.get("/")
        self.assertEqual(resp.status_code, 200)
        self.assertIn("Hostel Management", resp.text)
        self.assertIn("Complete Hostel Management, Simplified.", resp.text)

    def test_unauthenticated_dashboard_stats_rejected(self):
        """Operational dashboard stats endpoint strictly requires authentication."""
        resp = self.client.get("/api/v1/dashboard/stats")
        self.assertEqual(resp.status_code, 401)
        self.assertIn("Authentication token is missing", resp.json()["detail"])

    def test_unauthenticated_metrics_rejected(self):
        """Telemetry metrics endpoint requires valid authentication."""
        resp = self.client.get("/api/v1/metrics/dashboard")
        self.assertEqual(resp.status_code, 401)

    # ==========================================
    # 2. ALL 12 STAKEHOLDER ROLE METRICS TESTS
    # ==========================================

    def test_super_admin_dashboard_metrics(self):
        """Super Admin receives comprehensive multi-hostel system statistics."""
        resp = self.client.get("/api/v1/dashboard/stats", headers=self._headers("superadmin"))
        self.assertEqual(resp.status_code, 200)
        data = resp.json()
        self.assertIn("hostels", data)
        self.assertIn("students", data)
        self.assertIn("operations", data)
        self.assertGreaterEqual(data["hostels"]["total"], 1)
        self.assertIn("super_admin", self.users["superadmin"]["roles"])

    def test_hostel_admin_dashboard_metrics(self):
        """Hostel Admin receives facility-scoped operational metrics."""
        resp = self.client.get("/api/v1/dashboard/stats", headers=self._headers("hosteladmin"))
        self.assertEqual(resp.status_code, 200)
        data = resp.json()
        self.assertIn("hostels", data)
        self.assertIn("occupancy_rate", data["hostels"])

    def test_chief_warden_dashboard_metrics(self):
        """Chief Warden receives resident welfare, attendance, and leave statistics."""
        resp = self.client.get("/api/v1/dashboard/stats", headers=self._headers("warden"))
        self.assertEqual(resp.status_code, 200)
        data = resp.json()
        self.assertIn("operations", data)
        self.assertIn("pending_complaints", data["operations"])

    def test_assistant_warden_dashboard_metrics(self):
        """Assistant Warden receives floor-level attendance and duty metrics."""
        resp = self.client.get("/api/v1/dashboard/stats", headers=self._headers("asstwarden"))
        self.assertEqual(resp.status_code, 200)
        data = resp.json()
        self.assertIn("operations", data)

    def test_student_dashboard_metrics(self):
        """Student receives personalized resident metrics."""
        resp = self.client.get("/api/v1/dashboard/stats", headers=self._headers("rohan"))
        self.assertEqual(resp.status_code, 200)
        data = resp.json()
        self.assertIn("hostels", data)
        self.assertIn("operations", data)

    def test_accountant_dashboard_metrics(self):
        """Accountant receives fee collection and dues reconciliation metrics."""
        resp = self.client.get("/api/v1/dashboard/stats", headers=self._headers("accountant"))
        self.assertEqual(resp.status_code, 200)
        data = resp.json()
        self.assertIn("finance", data)
        self.assertIn("total_collected", data["finance"])

    def test_mess_manager_dashboard_metrics(self):
        """Mess Manager receives dining operational headcount metrics."""
        resp = self.client.get("/api/v1/dashboard/stats", headers=self._headers("messmanager"))
        self.assertEqual(resp.status_code, 200)
        data = resp.json()
        self.assertIn("hostels", data)

    def test_maintenance_staff_dashboard_metrics(self):
        """Maintenance Staff receives work order and repair workload metrics."""
        resp = self.client.get("/api/v1/dashboard/stats", headers=self._headers("maintenance"))
        self.assertEqual(resp.status_code, 200)
        data = resp.json()
        self.assertIn("operations", data)
        self.assertIn("pending_maintenance", data["operations"])

    def test_security_guard_dashboard_metrics(self):
        """Security Guard receives active campus visitor and ingress/egress metrics."""
        resp = self.client.get("/api/v1/dashboard/stats", headers=self._headers("security"))
        self.assertEqual(resp.status_code, 200)
        data = resp.json()
        self.assertIn("operations", data)

    def test_admission_officer_dashboard_metrics(self):
        """Admission Officer receives candidate pipeline and available bed metrics."""
        resp = self.client.get("/api/v1/dashboard/stats", headers=self._headers("admission"))
        self.assertEqual(resp.status_code, 200)
        data = resp.json()
        self.assertIn("operations", data)
        self.assertIn("pending_admissions", data["operations"])

    def test_parent_guardian_dashboard_metrics(self):
        """Parent/Guardian receives authenticated ward monitoring metrics."""
        resp = self.client.get("/api/v1/dashboard/stats", headers=self._headers("parent"))
        self.assertEqual(resp.status_code, 200)
        data = resp.json()
        self.assertIn("hostels", data)

    def test_auditor_dashboard_metrics(self):
        """Auditor receives compliance review telemetry and SLA audit data."""
        resp = self.client.get("/api/v1/dashboard/stats", headers=self._headers("evaluator"))
        self.assertEqual(resp.status_code, 200)
        data = resp.json()
        self.assertIn("hostels", data)

    # ==========================================
    # 3. ROLE-SWITCHING SECURITY & MULTI-ROLE TESTS
    # ==========================================

    def test_single_role_assistant_warden_cannot_switch_to_super_admin(self):
        """Single-role Assistant Warden cannot switch to Super Admin."""
        resp = self.client.post("/api/v1/auth/switch-role", json={"role": "super_admin"}, headers=self._headers("asstwarden"))
        self.assertEqual(resp.status_code, 403)
        self.assertIn("not assigned", resp.json()["detail"])

    def test_single_role_assistant_warden_cannot_switch_to_warden(self):
        """Single-role Assistant Warden cannot switch to Chief Warden."""
        resp = self.client.post("/api/v1/auth/switch-role", json={"role": "warden"}, headers=self._headers("asstwarden"))
        self.assertEqual(resp.status_code, 403)
        self.assertIn("not assigned", resp.json()["detail"])

    def test_single_role_student_cannot_switch_roles(self):
        """Single-role Student cannot switch to Accountant or Super Admin."""
        resp_acc = self.client.post("/api/v1/auth/switch-role", json={"role": "accountant"}, headers=self._headers("rohan"))
        self.assertEqual(resp_acc.status_code, 403)
        self.assertIn("not assigned", resp_acc.json()["detail"])

        resp_admin = self.client.post("/api/v1/auth/switch-role", json={"role": "super_admin"}, headers=self._headers("rohan"))
        self.assertEqual(resp_admin.status_code, 403)

    def test_single_role_accountant_cannot_switch_to_super_admin(self):
        """Single-role Accountant cannot switch to Super Admin."""
        resp = self.client.post("/api/v1/auth/switch-role", json={"role": "super_admin"}, headers=self._headers("accountant"))
        self.assertEqual(resp.status_code, 403)

    def test_multi_role_user_can_switch_only_between_assigned_roles(self):
        """User assigned Accountant and Hostel Admin can switch between those two roles, but not to Super Admin."""
        # Switch to hostel_admin -> 200 OK
        resp1 = self.client.post("/api/v1/auth/switch-role", json={"role": "hostel_admin"}, headers=self._headers("multirole_user"))
        self.assertEqual(resp1.status_code, 200)
        self.assertTrue(resp1.json()["success"])
        self.assertEqual(resp1.json()["active_role"], "hostel_admin")

        # Switch to accountant -> 200 OK
        resp2 = self.client.post("/api/v1/auth/switch-role", json={"role": "accountant"}, headers=self._headers("multirole_user"))
        self.assertEqual(resp2.status_code, 200)
        self.assertTrue(resp2.json()["success"])
        self.assertEqual(resp2.json()["active_role"], "accountant")

        # Attempt to switch to unassigned super_admin -> 403 Forbidden!
        resp3 = self.client.post("/api/v1/auth/switch-role", json={"role": "super_admin"}, headers=self._headers("multirole_user"))
        self.assertEqual(resp3.status_code, 403)
        self.assertIn("not assigned", resp3.json()["detail"])

    def test_role_switch_records_audit_log(self):
        """Legitimate role switch generates an immutable audit log entry."""
        self.client.post("/api/v1/auth/switch-role", json={"role": "hostel_admin"}, headers=self._headers("multirole_user"))
        conn = get_db_connection()
        try:
            cursor = conn.cursor()
            cursor.execute("SELECT action, details FROM audit_logs WHERE action = 'ROLE_SWITCH' ORDER BY id DESC LIMIT 1;")
            row = cursor.fetchone()
            self.assertIsNotNone(row)
            self.assertEqual(row[0], "ROLE_SWITCH")
            self.assertIn("hostel_admin", row[1])
        finally:
            conn.close()

    def test_invalid_role_identifier_rejected(self):
        """Attempting to switch to non-existent role returns 403 Forbidden."""
        resp = self.client.post("/api/v1/auth/switch-role", json={"role": "non_existent_role_xyz"}, headers=self._headers("asstwarden"))
        self.assertEqual(resp.status_code, 403)

    # ==========================================
    # 4. SUPER ADMIN DIRECT API DEFENSE TESTS
    # ==========================================

    def test_assistant_warden_cannot_access_admin_settings(self):
        """Assistant Warden direct API access to admin settings is blocked."""
        resp = self.client.get("/api/v1/admin/settings", headers=self._headers("asstwarden"))
        self.assertEqual(resp.status_code, 403)

    def test_assistant_warden_cannot_access_admin_users(self):
        """Assistant Warden direct API access to user directory is blocked."""
        resp = self.client.get("/api/v1/admin/users", headers=self._headers("asstwarden"))
        self.assertEqual(resp.status_code, 403)

    def test_assistant_warden_cannot_mutate_settings(self):
        """Assistant Warden cannot modify system settings."""
        resp = self.client.put("/api/v1/admin/settings", json={"settings": []}, headers=self._headers("asstwarden"))
        self.assertEqual(resp.status_code, 403)

    def test_hostel_admin_without_super_admin_cannot_assign_roles(self):
        """Hostel Admin cannot assign or escalate user roles."""
        resp = self.client.put("/api/v1/admin/users/1/roles", json={"role_names": ["super_admin"]}, headers=self._headers("hosteladmin"))
        self.assertEqual(resp.status_code, 403)

    def test_student_cannot_access_admin_settings(self):
        """Student is blocked from administrative configuration endpoints."""
        resp = self.client.get("/api/v1/admin/settings", headers=self._headers("rohan"))
        self.assertEqual(resp.status_code, 403)

    def test_security_guard_cannot_access_admin_settings(self):
        """Security Guard direct API access to admin settings is blocked."""
        resp = self.client.get("/api/v1/admin/settings", headers=self._headers("security"))
        self.assertEqual(resp.status_code, 403)

    def test_only_authorized_super_admin_can_access_admin_settings(self):
        """Explicitly authorized Super Admin account can access admin settings."""
        resp = self.client.get("/api/v1/admin/settings", headers=self._headers("superadmin"))
        self.assertEqual(resp.status_code, 200)

    # ==========================================
    # 5. STRICT DATA ISOLATION & RBAC BOUNDARIES
    # ==========================================

    def test_student_isolation_cannot_access_other_student_profile(self):
        """Student Rohan (linked to student 1) cannot inspect Student 2's profile."""
        resp = self.client.get("/api/v1/students/2/profile", headers=self._headers("rohan"))
        self.assertEqual(resp.status_code, 403)
        self.assertIn("Security Violation", resp.json()["detail"])

    def test_student_isolation_can_access_own_profile(self):
        """Student Rohan can access his own profile (student 1)."""
        resp = self.client.get("/api/v1/students/1/profile", headers=self._headers("rohan"))
        self.assertEqual(resp.status_code, 200)
        self.assertEqual(resp.json()["id"], 1)

    def test_parent_cannot_access_unlinked_student_profile(self):
        """Parent linked to student 1 cannot access student 2's profile."""
        resp = self.client.get("/api/v1/students/2/profile", headers=self._headers("parent"))
        self.assertEqual(resp.status_code, 403)

    def test_auditor_is_strictly_read_only(self):
        """Auditor role cannot create announcements or mutate system settings."""
        resp = self.client.post("/api/v1/announcements", json={
            "title": "Auditor Test Announcement",
            "content": "This should be forbidden for auditors.",
            "target_roles": ["all"],
            "priority": "Normal"
        }, headers=self._headers("evaluator"))
        self.assertEqual(resp.status_code, 403)

    def test_security_guard_restricted_from_financial_billing(self):
        """Security guard is restricted from creating invoices or accessing financial billing."""
        resp = self.client.post("/api/v1/fees/invoices", json={
            "student_id": 1,
            "fee_structure_id": 1,
            "academic_term": "Fall 2026",
            "due_date": "2026-12-01"
        }, headers=self._headers("security"))
        self.assertEqual(resp.status_code, 403)

    def test_maintenance_staff_restricted_from_allocations(self):
        """Maintenance staff is restricted from creating room allocations."""
        resp = self.client.post("/api/v1/allocations", json={
            "student_id": 1,
            "bed_id": 1,
            "academic_year": "2026-2027"
        }, headers=self._headers("maintenance"))
        self.assertEqual(resp.status_code, 403)

    def test_accountant_restricted_from_leave_approvals(self):
        """Accountant is restricted from approving student leave applications."""
        resp = self.client.post("/api/v1/leave/1/approve", json={"remarks": "Approved by accountant"}, headers=self._headers("accountant"))
        self.assertEqual(resp.status_code, 403)

    # =========================================================================
    # 5. USER REGISTRATION & PERSONAL ATTENDANCE TESTS
    # =========================================================================

    def test_student_registration_creates_account_and_profile(self):
        """Self-registration as a student creates user account, student record, and issues token."""
        import uuid
        uid = uuid.uuid4().hex[:6]
        uname = f"reg_stu_{uid}"
        uemail = f"reg_stu_{uid}@univ.edu"
        resp = self.client.post("/api/v1/auth/register", json={
            "username": uname,
            "email": uemail,
            "password": "Password123!",
            "first_name": "Kavita",
            "last_name": "Rao",
            "phone": f"98{uuid.uuid4().int % 100000000:08d}",
            "role": "student",
            "branch": "CSE"
        })
        self.assertEqual(resp.status_code, 201)
        data = resp.json()
        self.assertIn("access_token", data)
        self.assertEqual(data["user"]["username"], uname)
        self.assertEqual(data["user"]["roles"], ["student"])
        self.assertIsNotNone(data["user"]["linked_student_id"])

    def test_staff_registration_with_specialization(self):
        """Self-registration as staff maps specialization (e.g. electrician) to maintenance_staff."""
        import uuid
        uid = uuid.uuid4().hex[:6]
        uname = f"reg_elec_{uid}"
        uemail = f"reg_elec_{uid}@univ.edu"
        resp = self.client.post("/api/v1/auth/register", json={
            "username": uname,
            "email": uemail,
            "password": "Password123!",
            "first_name": "Ramesh",
            "last_name": "Kumar",
            "phone": f"98{uuid.uuid4().int % 100000000:08d}",
            "role": "staff",
            "specialization": "electrician"
        })
        self.assertEqual(resp.status_code, 201)
        data = resp.json()
        self.assertEqual(data["user"]["username"], uname)
        self.assertIn("maintenance_staff", data["user"]["roles"])

    def test_administrative_role_self_registration_forbidden(self):
        """Attempting to self-register as super_admin or admin is rejected with HTTP 403."""
        resp = self.client.post("/api/v1/auth/register", json={
            "username": "hacker_admin",
            "email": "hacker@univ.edu",
            "password": "Password123!",
            "first_name": "Malicious",
            "last_name": "Actor",
            "role": "super_admin"
        })
        self.assertEqual(resp.status_code, 403)

    def test_duplicate_registration_rejected(self):
        """Registering with an existing username returns HTTP 409 Conflict."""
        resp = self.client.post("/api/v1/auth/register", json={
            "username": "superadmin",
            "email": "superadmin_new@univ.edu",
            "password": "Password123!",
            "first_name": "Duplicate",
            "last_name": "User",
            "role": "student"
        })
        self.assertEqual(resp.status_code, 409)

    def test_my_attendance_endpoint_returns_personal_status(self):
        """Student Rohan accessing /api/v1/attendance/my-attendance receives personal metrics & today status."""
        resp = self.client.get("/api/v1/attendance/my-attendance", headers=self._headers("rohan"))
        self.assertEqual(resp.status_code, 200)
        data = resp.json()
        self.assertIn("today_status", data)
        self.assertIn("present_days", data)
        self.assertIn("absent_days", data)
        self.assertIn("attendance_percentage", data)
        self.assertIn("history", data)


if __name__ == "__main__":
    unittest.main()
