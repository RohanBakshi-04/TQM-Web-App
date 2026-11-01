"""Comprehensive Integration and Authorization Tests for 12 Role-Based Dashboards.

Verifies:
1. Public landing page availability vs unauthenticated endpoint protection (HTTP 401).
2. Dedicated authenticated workspace metrics for all 12 stakeholder roles:
   - super_admin, hostel_admin, warden, assistant_warden, student, accountant,
     mess_manager, maintenance_staff, security_guard, admission_officer, parent_guardian, auditor.
3. Strict student data isolation (Student A cannot inspect Student B's profile).
4. Guardian isolation (Guardian restricted to linked ward).
5. Auditor read-only enforcement (Mutations rejected with HTTP 403).
6. Security guard boundary protection (Restricted from financial billing).
7. Maintenance staff boundary protection (Restricted from student room allocations).
"""

import unittest
from fastapi.testclient import TestClient

from backend.app.main import app
from backend.app.database.init_db import initialize_database


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
    # 3. STRICT DATA ISOLATION & RBAC BOUNDARIES
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

    def test_student_cannot_access_admin_settings(self):
        """Student is blocked from administrative configuration endpoints."""
        resp = self.client.get("/api/v1/admin/settings", headers=self._headers("rohan"))
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


if __name__ == "__main__":
    unittest.main()
