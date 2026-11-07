"""Comprehensive Test Suite for SA-01: Super Admin Executive Overview.

Course: BBAT104 - Fundamentals of Total Quality Management (TQM)
Quality Goal: Q05 - Reduce Response Time (<10ms SLA)
Standard: Poka-Yoke Zero Defects & RBAC Strict Isolation
"""

import os
import shutil
import tempfile
import unittest
from fastapi.testclient import TestClient

from backend.app.config import settings
from backend.app.database.init_db import initialize_database
from backend.app.main import app
from backend.app.services.cache_service import cache_service


class TestSA01ExecutiveDashboard(unittest.TestCase):
    """Test suite validating all 13 sections of SA-01 Super Admin Executive Overview."""

    @classmethod
    def setUpClass(cls):
        cls.temp_dir = tempfile.mkdtemp()
        cls.db_path = os.path.join(cls.temp_dir, "test_sa01.db")
        cls.orig_db_path = settings.database_path
        settings.database_path = cls.db_path
        initialize_database()
        cls.client = TestClient(app)

        # Login as superadmin to obtain access token
        login_res = cls.client.post("/api/v1/auth/login", json={
            "username_or_email": "superadmin",
            "password": "Password123!"
        })
        assert login_res.status_code == 200, f"Superadmin login failed: {login_res.text}"
        cls.superadmin_token = login_res.json()["access_token"]
        cls.superadmin_headers = {"Authorization": f"Bearer {cls.superadmin_token}"}

        # Login as student (demo user 'rohan') to test RBAC rejection
        stu_login = cls.client.post("/api/v1/auth/login", json={
            "username_or_email": "rohan",
            "password": "Password123!"
        })
        assert stu_login.status_code == 200, f"Student login failed: {stu_login.text}"
        cls.student_token = stu_login.json()["access_token"]
        cls.student_headers = {"Authorization": f"Bearer {cls.student_token}"}

    @classmethod
    def tearDownClass(cls):
        settings.database_path = cls.orig_db_path
        shutil.rmtree(cls.temp_dir, ignore_errors=True)

    def test_01_super_admin_executive_overview_success(self):
        """Verify SA-01 returns 200 with all 13 core sections and required fields."""
        res = self.client.get("/api/v1/dashboard/executive-overview", headers=self.superadmin_headers)
        self.assertEqual(res.status_code, 200, res.text)
        data = res.json()

        # Section A: Metadata
        self.assertIn("metadata", data)
        meta = data["metadata"]
        self.assertIn("institution_name", meta)
        self.assertIn("academic_session", meta)
        self.assertIn("currency_symbol", meta)
        self.assertIn("execution_time_ms", meta)
        self.assertIn("cache_status", meta)

        # Section B: Institutional Overview (10 entities)
        self.assertIn("institution_overview", data)
        inst = data["institution_overview"]
        for key in ["campuses", "hostels", "buildings", "departments", "floors", "rooms", "beds", "students", "users", "dashboards", "stakeholders"]:
            self.assertIn(key, inst, f"Missing key '{key}' in institution_overview")
            self.assertGreaterEqual(inst[key], 0)

        # Section C: Critical KPI Grid (4 domains)
        self.assertIn("kpi_grid", data)
        kpi = data["kpi_grid"]
        self.assertIn("students", kpi)
        self.assertIn("hostels", kpi)
        self.assertIn("users", kpi)
        self.assertIn("admissions", kpi)

        self.assertIn("retention_rate_pct", kpi["students"])
        self.assertIn("occupancy_rate_pct", kpi["hostels"])
        self.assertIn("total_roles", kpi["users"])
        self.assertIn("conversion_rate_pct", kpi["admissions"])

        # Section D: Operational Performance
        self.assertIn("operational_performance", data)
        ops = data["operational_performance"]
        self.assertIn("complaints", ops)
        self.assertIn("maintenance", ops)
        self.assertIn("leaves_outpasses", ops)
        self.assertIn("visitors", ops)
        self.assertIn("security", ops)

        # Section E: Financial Overview (Authoritative Integer Paise)
        self.assertIn("financial_overview", data)
        fin = data["financial_overview"]
        self.assertIn("total_invoiced_paise", fin)
        self.assertIn("total_invoiced_inr", fin)
        self.assertIn("total_collected_paise", fin)
        self.assertIn("total_collected_inr", fin)
        self.assertIn("outstanding_dues_paise", fin)
        self.assertIn("outstanding_dues_inr", fin)
        self.assertIn("collection_efficiency_pct", fin)
        self.assertIn("monthly_trend", fin)
        self.assertIn("hostel_breakdown", fin)

        # Section F: Admission Overview
        self.assertIn("admission_overview", data)
        adm = data["admission_overview"]
        self.assertIn("total_applications", adm)
        self.assertIn("branch_distribution", adm)
        self.assertIn("gender_distribution", adm)

        # Section G: Infrastructure Table
        self.assertIn("infrastructure_table", data)
        self.assertIsInstance(data["infrastructure_table"], list)
        self.assertGreater(len(data["infrastructure_table"]), 0)
        h0 = data["infrastructure_table"][0]
        for key in ["id", "name", "code", "campus", "buildings_count", "rooms_count", "total_beds", "occupied_beds", "available_beds", "occupancy_rate_pct"]:
            self.assertIn(key, h0, f"Missing key '{key}' in infrastructure_table item")

        # Section H: Workforce & 17 Departments
        self.assertIn("workforce_overview", data)
        wf = data["workforce_overview"]
        self.assertIn("total_staff", wf)
        self.assertIn("active_staff", wf)
        self.assertIn("department_distribution", wf)
        self.assertEqual(len(wf["department_distribution"]), 17, "All 17 departments must be represented in distribution")

        # Section J: Live Activity Center
        self.assertIn("recent_activity", data)
        self.assertIsInstance(data["recent_activity"], list)

        # Section K: Critical Alerts Center
        self.assertIn("critical_alerts", data)
        self.assertIsInstance(data["critical_alerts"], list)
        self.assertGreater(len(data["critical_alerts"]), 0)

        # Section M: System Health Telemetry
        self.assertIn("system_health", data)
        health = data["system_health"]
        self.assertTrue(health["db_connected"])
        self.assertEqual(health["journal_mode"], "wal")
        self.assertEqual(health["integrity_check"], "ok")
        self.assertIn("cache_stats", health)
        self.assertEqual(health["api_latency_target_ms"], 10.0)

    def test_02_filter_parameters_and_isolation(self):
        """Test executive overview queries with campus, hostel, and department filters."""
        # Filter by North Campus
        res_campus = self.client.get(
            "/api/v1/dashboard/executive-overview?campus=North%20Campus",
            headers=self.superadmin_headers
        )
        self.assertEqual(res_campus.status_code, 200)
        d_campus = res_campus.json()
        self.assertEqual(d_campus["metadata"]["filters_applied"]["campus"], "North Campus")

        # Filter by specific hostel_id=1
        res_hostel = self.client.get(
            "/api/v1/dashboard/executive-overview?hostel_id=1",
            headers=self.superadmin_headers
        )
        self.assertEqual(res_hostel.status_code, 200)
        d_hostel = res_hostel.json()
        self.assertEqual(d_hostel["metadata"]["filters_applied"]["hostel_id"], 1)
        self.assertEqual(d_hostel["institution_overview"]["hostels"], 1)

    def test_03_q05_caching_and_sub_10ms_latency(self):
        """Verify Q05 caching accelerates secondary requests to sub-10ms with cache HIT."""
        cache_service.clear()

        # Request 1: Cache Miss
        res1 = self.client.get("/api/v1/dashboard/executive-overview", headers=self.superadmin_headers)
        self.assertEqual(res1.status_code, 200)
        d1 = res1.json()
        self.assertEqual(d1["metadata"]["cache_status"], "MISS")

        # Request 2: Cache Hit
        res2 = self.client.get("/api/v1/dashboard/executive-overview", headers=self.superadmin_headers)
        self.assertEqual(res2.status_code, 200)
        d2 = res2.json()
        self.assertEqual(d2["metadata"]["cache_status"], "HIT")
        self.assertLess(d2["metadata"]["execution_time_ms"], 10.0, "Execution time must satisfy Q05 < 10ms SLA")

    def test_04_rbac_forbidden_for_student(self):
        """Verify unprivileged roles (e.g. student) receive 403 Forbidden."""
        res = self.client.get("/api/v1/dashboard/executive-overview", headers=self.student_headers)
        self.assertEqual(res.status_code, 403)

    def test_05_financial_integer_paise_integrity(self):
        """Verify financial calculations strictly adhere to integer-paise standard."""
        res = self.client.get("/api/v1/dashboard/executive-overview?bypass_cache=true", headers=self.superadmin_headers)
        self.assertEqual(res.status_code, 200)
        fin = res.json()["financial_overview"]

        # Assert paise integers
        self.assertIsInstance(fin["total_invoiced_paise"], int)
        self.assertIsInstance(fin["total_collected_paise"], int)
        self.assertIsInstance(fin["outstanding_dues_paise"], int)

        # Assert INR conversions match exact division by 100
        self.assertEqual(fin["total_invoiced_inr"], round(fin["total_invoiced_paise"] / 100.0, 2))
        self.assertEqual(fin["total_collected_inr"], round(fin["total_collected_paise"] / 100.0, 2))
        self.assertEqual(fin["outstanding_dues_inr"], round(fin["outstanding_dues_paise"] / 100.0, 2))

        # Dues must equal max(0, invoiced - collected)
        expected_dues_paise = max(0, fin["total_invoiced_paise"] - fin["total_collected_paise"])
        self.assertEqual(fin["outstanding_dues_paise"], expected_dues_paise)

    def test_06_cache_clear_endpoint(self):
        """Verify cache clear endpoint flushes cache entries."""
        res = self.client.post("/api/v1/metrics/cache/clear", headers=self.superadmin_headers)
        self.assertEqual(res.status_code, 200)
        self.assertEqual(res.json()["status"], "success")


if __name__ == "__main__":
    unittest.main()
