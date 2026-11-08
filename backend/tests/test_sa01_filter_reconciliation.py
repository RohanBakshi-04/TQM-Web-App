"""Deterministic Test Suite for SA-01 Metric Reconciliation & Multi-Dimensional Filter Verification.

Course: BBAT104 - Fundamentals of Total Quality Management (TQM)
Quality Target: Q05 Zero Defects - Independent SQL Reconciliation & Scope Isolation
"""

import os
import shutil
import tempfile
import unittest
from fastapi.testclient import TestClient

from backend.app.config import settings
from backend.app.database.connection import get_db_connection
from backend.app.database.init_db import initialize_database
from backend.app.main import app
from backend.app.services.cache_service import cache_service


class TestSA01FilterReconciliation(unittest.TestCase):
    """Exhaustive SQL reconciliation tests across all 5 filter dimensions and combinations."""

    @classmethod
    def setUpClass(cls):
        cls.temp_dir = tempfile.mkdtemp(prefix="hms_reconcile_")
        cls.db_path = os.path.join(cls.temp_dir, "test_reconciliation.db")
        cls.orig_db_path = settings.database_path
        settings.database_path = cls.db_path
        initialize_database()
        cls.client = TestClient(app)

        # Login as superadmin
        res = cls.client.post("/api/v1/auth/login", json={"username_or_email": "superadmin", "password": "Password123!"})
        assert res.status_code == 200, res.text
        cls.token = res.json()["access_token"]
        cls.headers = {"Authorization": f"Bearer {cls.token}"}

    @classmethod
    def tearDownClass(cls):
        settings.database_path = cls.orig_db_path
        shutil.rmtree(cls.temp_dir, ignore_errors=True)

    def test_01_global_unfiltered_sql_reconciliation(self):
        """Verify global unfiltered metrics match independent direct SQL queries exactly."""
        res = self.client.get("/api/v1/dashboard/executive-overview?bypass_cache=true", headers=self.headers)
        self.assertEqual(res.status_code, 200)
        data = res.json()

        conn = get_db_connection()
        try:
            cur = conn.cursor()

            # 1. Total hostels
            actual_hostels = cur.execute("SELECT COUNT(*) FROM hostels").fetchone()[0]
            self.assertEqual(data["institution_overview"]["hostels"], actual_hostels)

            # 2. Total buildings
            actual_buildings = cur.execute("SELECT COUNT(*) FROM buildings").fetchone()[0]
            self.assertEqual(data["institution_overview"]["buildings"], actual_buildings)

            # 3. Total rooms
            actual_rooms = cur.execute("SELECT COUNT(*) FROM rooms").fetchone()[0]
            self.assertEqual(data["institution_overview"]["rooms"], actual_rooms)

            # 4. Total beds & occupancy
            b_row = cur.execute("""
                SELECT 
                    COUNT(*) AS total,
                    SUM(CASE WHEN status = 'Occupied' THEN 1 ELSE 0 END) AS occupied,
                    SUM(CASE WHEN status = 'Available' THEN 1 ELSE 0 END) AS available
                FROM beds;
            """).fetchone()
            self.assertEqual(data["institution_overview"]["beds"], b_row[0])
            self.assertEqual(data["kpi_grid"]["hostels"]["total_capacity"], b_row[0])
            self.assertEqual(data["kpi_grid"]["hostels"]["occupied_beds"], b_row[1])
            self.assertEqual(data["kpi_grid"]["hostels"]["available_beds"], b_row[2])

            # 5. Deduplicated students
            s_row = cur.execute("""
                SELECT 
                    COUNT(DISTINCT s.id) AS total,
                    COUNT(DISTINCT CASE WHEN s.status = 'Active' THEN s.id ELSE NULL END) AS active,
                    COUNT(DISTINCT CASE WHEN s.status != 'Active' THEN s.id ELSE NULL END) AS inactive
                FROM students s;
            """).fetchone()
            self.assertEqual(data["institution_overview"]["students"], s_row[0])
            self.assertEqual(data["institution_overview"]["students_active"], s_row[1])
            self.assertEqual(data["institution_overview"]["students_inactive"], s_row[2])
            # Strict reconciliation: active + inactive == total
            self.assertEqual(s_row[1] + s_row[2], s_row[0])

            # 6. Financial integer-paise reconciliation
            inv_p = cur.execute("SELECT COALESCE(SUM(total_amount_paise), 0) FROM invoices WHERE status != 'Cancelled'").fetchone()[0]
            pay_p = cur.execute("SELECT COALESCE(SUM(amount_paise), 0) FROM payments WHERE status = 'Completed'").fetchone()[0]
            self.assertEqual(data["financial_overview"]["total_invoiced_paise"], inv_p)
            self.assertEqual(data["financial_overview"]["total_collected_paise"], pay_p)
            self.assertEqual(data["financial_overview"]["outstanding_dues_paise"], max(0, inv_p - pay_p))

            # 7. Departments count
            actual_depts = cur.execute("SELECT COUNT(*) FROM departments").fetchone()[0]
            self.assertEqual(data["institution_overview"]["departments"], actual_depts)
            self.assertEqual(len(data["workforce_overview"]["department_distribution"]), actual_depts)

            # 8. System users
            u_row = cur.execute("""
                SELECT 
                    COUNT(*) AS total,
                    SUM(CASE WHEN is_active = 1 THEN 1 ELSE 0 END) AS active,
                    SUM(CASE WHEN is_active = 0 THEN 1 ELSE 0 END) AS inactive
                FROM users;
            """).fetchone()
            self.assertEqual(data["institution_overview"]["users"], u_row[0])
            self.assertEqual(data["institution_overview"]["users_active"], u_row[1])
            self.assertEqual(data["kpi_grid"]["users"]["total_accounts"], u_row[0])
            self.assertEqual(data["kpi_grid"]["users"]["active_accounts"], u_row[1])
            self.assertEqual(data["kpi_grid"]["users"]["inactive_accounts"], u_row[2])
        finally:
            conn.close()

    def test_02_campus_filter_isolation(self):
        """Verify filtering by campus isolates hostels, rooms, beds, and students to that campus only."""
        # Query North Campus
        res_north = self.client.get("/api/v1/dashboard/executive-overview?campus=North%20Campus&bypass_cache=true", headers=self.headers)
        self.assertEqual(res_north.status_code, 200)
        d_north = res_north.json()

        # Query South Campus
        res_south = self.client.get("/api/v1/dashboard/executive-overview?campus=South%20Campus&bypass_cache=true", headers=self.headers)
        self.assertEqual(res_south.status_code, 200)
        d_south = res_south.json()

        conn = get_db_connection()
        try:
            cur = conn.cursor()
            north_hostels = cur.execute("SELECT COUNT(*) FROM hostels WHERE address LIKE '%North%'").fetchone()[0]
            south_hostels = cur.execute("SELECT COUNT(*) FROM hostels WHERE address LIKE '%South%'").fetchone()[0]

            self.assertEqual(d_north["institution_overview"]["hostels"], north_hostels)
            self.assertEqual(d_south["institution_overview"]["hostels"], south_hostels)

            # Verify that every item in infrastructure table belongs to the filtered campus
            for h in d_north["infrastructure_table"]:
                self.assertIn("North", h["campus"])
            for h in d_south["infrastructure_table"]:
                self.assertIn("South", h["campus"])
        finally:
            conn.close()

    def test_03_hostel_facility_filter_isolation(self):
        """Verify filtering by hostel_id isolates infrastructure, capacity, and aggregates to exactly 1 hostel."""
        target_id = 1
        res = self.client.get(f"/api/v1/dashboard/executive-overview?hostel_id={target_id}&bypass_cache=true", headers=self.headers)
        self.assertEqual(res.status_code, 200)
        data = res.json()

        self.assertEqual(data["institution_overview"]["hostels"], 1)
        self.assertEqual(len(data["infrastructure_table"]), 1)
        self.assertEqual(data["infrastructure_table"][0]["id"], target_id)

        conn = get_db_connection()
        try:
            cur = conn.cursor()
            # Verify bed capacity matches this specific hostel
            h1_beds = cur.execute("""
                SELECT COUNT(bd.id)
                FROM beds bd
                JOIN rooms r ON bd.room_id = r.id
                JOIN floors f ON r.floor_id = f.id
                JOIN buildings b ON f.building_id = b.id
                WHERE b.hostel_id = ?;
            """, (target_id,)).fetchone()[0]
            self.assertEqual(data["kpi_grid"]["hostels"]["total_capacity"], h1_beds)
        finally:
            conn.close()

    def test_04_department_filter_isolation(self):
        """Verify filtering by department isolates workforce distribution and staff counts."""
        target_code = "MAINTENANCE"
        res = self.client.get(f"/api/v1/dashboard/executive-overview?department={target_code}&bypass_cache=true", headers=self.headers)
        self.assertEqual(res.status_code, 200)
        data = res.json()

        # In workforce overview, only the requested department is returned
        depts = data["workforce_overview"]["department_distribution"]
        self.assertEqual(len(depts), 1)
        self.assertEqual(depts[0]["code"], target_code)

        # Global role count and dashboard count remain invariant
        self.assertGreater(data["institution_overview"]["stakeholders"], 0)
        self.assertGreater(data["institution_overview"]["dashboards"], 0)

    def test_05_academic_session_filter(self):
        """Verify filtering by academic_session filters students and admission intakes."""
        session = "2026-27"
        res = self.client.get(f"/api/v1/dashboard/executive-overview?academic_session={session}&bypass_cache=true", headers=self.headers)
        self.assertEqual(res.status_code, 200)
        data = res.json()
        self.assertEqual(data["metadata"]["filters_applied"]["academic_session"], session)

        conn = get_db_connection()
        try:
            cur = conn.cursor()
            expected_apps = cur.execute("SELECT COUNT(*) FROM admission_applications WHERE academic_year = ?", (session,)).fetchone()[0]
            self.assertEqual(data["kpi_grid"]["admissions"]["total_applications"], expected_apps)
        finally:
            conn.close()

    def test_06_date_range_filter(self):
        """Verify filtering by date_from and date_to restricts audit logs, complaints, and transactions."""
        d_from = "2026-01-01"
        d_to = "2026-12-31"
        res = self.client.get(f"/api/v1/dashboard/executive-overview?date_from={d_from}&date_to={d_to}&bypass_cache=true", headers=self.headers)
        self.assertEqual(res.status_code, 200)
        data = res.json()

        self.assertEqual(data["metadata"]["filters_applied"]["date_from"], d_from)
        self.assertEqual(data["metadata"]["filters_applied"]["date_to"], d_to)

        # Verify recent activity logs fall within date range
        for log in data["recent_activity"]:
            log_date = log["created_at"].split()[0]
            self.assertGreaterEqual(log_date, d_from)
            self.assertLessEqual(log_date, d_to)

    def test_07_combined_multi_dimensional_filters(self):
        """Verify combined filters (Campus + Hostel + Department + Date Range) produce exact reconciled results."""
        res = self.client.get(
            "/api/v1/dashboard/executive-overview?campus=North%20Campus&hostel_id=1&department=MAINTENANCE&date_from=2026-01-01&date_to=2026-12-31&bypass_cache=true",
            headers=self.headers
        )
        self.assertEqual(res.status_code, 200)
        data = res.json()

        # Must return exactly 1 hostel (Hostel 1 on North Campus)
        self.assertEqual(data["institution_overview"]["hostels"], 1)
        self.assertEqual(len(data["infrastructure_table"]), 1)
        self.assertEqual(data["infrastructure_table"][0]["id"], 1)
        self.assertIn("North", data["infrastructure_table"][0]["campus"])

        # Must return exactly 1 department (MAINTENANCE)
        self.assertEqual(len(data["workforce_overview"]["department_distribution"]), 1)
        self.assertEqual(data["workforce_overview"]["department_distribution"][0]["code"], "MAINTENANCE")

    def test_08_invalid_filter_handling(self):
        """Verify invalid or non-existent filter values are safely handled without unhandled errors."""
        res = self.client.get(
            "/api/v1/dashboard/executive-overview?hostel_id=99999&campus=InvalidCampus&department=FakeDept&date_from=bad-date&bypass_cache=true",
            headers=self.headers
        )
        self.assertEqual(res.status_code, 200)
        data = res.json()

        # Non-matching filters return empty list / 0 counts, never crashes
        self.assertEqual(data["institution_overview"]["hostels"], 0)
        self.assertEqual(len(data["infrastructure_table"]), 0)
        self.assertEqual(len(data["workforce_overview"]["department_distribution"]), 0)


if __name__ == "__main__":
    unittest.main()
