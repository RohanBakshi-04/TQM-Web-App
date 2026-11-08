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

        # Seed custom multi-campus fixtures (East Campus / Kaveri Hostel)
        conn = get_db_connection()
        try:
            cur = conn.cursor()
            cur.execute("""
                INSERT INTO hostels (name, code, hostel_type, address, contact_phone, contact_email)
                VALUES ('Kaveri Innovation Hostel', 'KIH-01', 'Co-Ed', 'East Campus, Innovation Hub', '011-2700103', 'kaveri.hostel@univ.edu');
            """)
            cls.east_hostel_id = cur.lastrowid

            cur.execute("INSERT INTO buildings (hostel_id, name, code, total_floors) VALUES (?, 'Turing Block', 'BLK-E1', 1);", (cls.east_hostel_id,))
            bldg_id = cur.lastrowid

            cur.execute("INSERT INTO floors (building_id, floor_number, floor_name) VALUES (?, 1, 'Ground Floor');", (bldg_id,))
            flr_id = cur.lastrowid

            cur.execute("INSERT INTO rooms (floor_id, room_number, room_type, capacity, base_fee, status) VALUES (?, 'E101', 'Double', 2, 7000.0, 'Full');", (flr_id,))
            r1 = cur.lastrowid
            cur.execute("INSERT INTO rooms (floor_id, room_number, room_type, capacity, base_fee, status) VALUES (?, 'E102', 'Double', 2, 7000.0, 'Available');", (flr_id,))
            r2 = cur.lastrowid

            cur.execute("INSERT INTO beds (room_id, bed_number, status) VALUES (?, 'E101-A', 'Occupied');", (r1,))
            b_occ1 = cur.lastrowid
            cur.execute("INSERT INTO beds (room_id, bed_number, status) VALUES (?, 'E101-B', 'Occupied');", (r1,))
            b_occ2 = cur.lastrowid
            cur.execute("INSERT INTO beds (room_id, bed_number, status) VALUES (?, 'E102-A', 'Available');", (r2,))
            cur.execute("INSERT INTO beds (room_id, bed_number, status) VALUES (?, 'E102-B', 'Available');", (r2,))

            # Students for East Campus
            cur.execute("""
                INSERT INTO students (student_id, first_name, last_name, email, phone, gender, branch, academic_year, admission_date, status)
                VALUES ('STU-EAST-01', 'Aditi', 'Sen', 'aditi.sen@univ.edu', '9899001122', 'Female', 'IT', '2026-27', '2026-01-01', 'Active');
            """)
            cls.east_student1_id = cur.lastrowid

            cur.execute("""
                INSERT INTO students (student_id, first_name, last_name, email, phone, gender, branch, academic_year, admission_date, status)
                VALUES ('STU-EAST-02', 'Vikram', 'Rathore', 'vikram.rathore@univ.edu', '9899001133', 'Male', 'CSE', '2026-27', '2026-01-01', 'Withdrawn');
            """)
            cls.east_student2_id = cur.lastrowid

            # Invoices & Payments for East Campus students
            cur.execute("""
                INSERT INTO invoices (student_id, invoice_number, issue_date, due_date, total_amount, paid_amount, discount_amount, fine_amount, status, total_amount_paise, paid_amount_paise)
                VALUES (?, 'INV-EAST-001', '2026-04-01', '2026-05-01', 5000.0, 5000.0, 0.0, 0.0, 'Paid', 500000, 500000);
            """, (cls.east_student1_id,))
            inv_id = cur.lastrowid

            cur.execute("""
                INSERT INTO payments (invoice_id, student_id, payment_reference, amount_paise, amount, payment_date, payment_method, status)
                VALUES (?, ?, 'PAY-EAST-001', 500000, 5000.0, '2026-04-15', 'UPI', 'Completed');
            """, (inv_id, cls.east_student1_id))

            # Room allocation for student
            cur.execute("""
                INSERT INTO room_allocations (student_id, room_id, bed_id, start_date, allocation_status)
                VALUES (?, ?, ?, '2026-01-01', 'Active');
            """, (cls.east_student1_id, r1, b_occ1))

            conn.commit()
        finally:
            conn.close()

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

    def test_09_multi_campus_custom_fixtures_reconciliation(self):
        """Verify newly seeded East Campus custom fixtures reconcile against direct independent SQL."""
        res = self.client.get("/api/v1/dashboard/executive-overview?campus=East%20Campus&bypass_cache=true", headers=self.headers)
        self.assertEqual(res.status_code, 200)
        data = res.json()

        conn = get_db_connection()
        try:
            cur = conn.cursor()
            # 1. Hostels count for East Campus
            east_h_count = cur.execute("SELECT COUNT(*) FROM hostels WHERE address LIKE '%East Campus%'").fetchone()[0]
            self.assertEqual(data["institution_overview"]["hostels"], east_h_count)
            self.assertEqual(east_h_count, 1)

            # 2. Bed capacity for East Campus
            east_beds = cur.execute("""
                SELECT 
                    COUNT(bd.id) AS total,
                    SUM(CASE WHEN bd.status = 'Occupied' THEN 1 ELSE 0 END) AS occupied,
                    SUM(CASE WHEN bd.status = 'Available' THEN 1 ELSE 0 END) AS available
                FROM beds bd
                JOIN rooms r ON bd.room_id = r.id
                JOIN floors f ON r.floor_id = f.id
                JOIN buildings b ON f.building_id = b.id
                JOIN hostels h ON b.hostel_id = h.id
                WHERE h.address LIKE '%East Campus%';
            """).fetchone()
            self.assertEqual(data["institution_overview"]["beds"], east_beds[0])
            self.assertEqual(data["kpi_grid"]["hostels"]["total_capacity"], east_beds[0])
            self.assertEqual(data["kpi_grid"]["hostels"]["occupied_beds"], east_beds[1])
            self.assertEqual(data["kpi_grid"]["hostels"]["available_beds"], east_beds[2])

            # 3. All items in infrastructure table belong to East Campus
            self.assertEqual(len(data["infrastructure_table"]), 1)
            self.assertIn("East Campus", data["infrastructure_table"][0]["campus"])
            self.assertEqual(data["infrastructure_table"][0]["name"], "Kaveri Innovation Hostel")
        finally:
            conn.close()

    def test_10_global_governance_invariance_under_all_filters(self):
        """Verify global governance metrics (32 roles, 28 dashboards, 17 departments) remain invariant across all filter slices."""
        conn = get_db_connection()
        try:
            cur = conn.cursor()
            expected_roles = cur.execute("SELECT COUNT(*) FROM roles").fetchone()[0]
            expected_dashboards = cur.execute("SELECT COUNT(*) FROM dashboards").fetchone()[0]
            expected_departments = cur.execute("SELECT COUNT(*) FROM departments").fetchone()[0]
        finally:
            conn.close()

        filter_urls = [
            "/api/v1/dashboard/executive-overview?bypass_cache=true",
            "/api/v1/dashboard/executive-overview?campus=North%20Campus&bypass_cache=true",
            "/api/v1/dashboard/executive-overview?campus=South%20Campus&bypass_cache=true",
            "/api/v1/dashboard/executive-overview?campus=East%20Campus&bypass_cache=true",
            f"/api/v1/dashboard/executive-overview?hostel_id={self.east_hostel_id}&bypass_cache=true",
            "/api/v1/dashboard/executive-overview?department=MAINTENANCE&bypass_cache=true",
            "/api/v1/dashboard/executive-overview?academic_session=2026-27&bypass_cache=true",
            "/api/v1/dashboard/executive-overview?date_from=2026-01-01&date_to=2026-12-31&bypass_cache=true"
        ]

        for url in filter_urls:
            res = self.client.get(url, headers=self.headers)
            self.assertEqual(res.status_code, 200, f"Filter URL failed: {url}")
            data = res.json()
            inst = data["institution_overview"]
            self.assertEqual(inst["stakeholders"], expected_roles, f"Role count varied on {url}")
            self.assertEqual(inst["dashboards"], expected_dashboards, f"Dashboard count varied on {url}")
            self.assertEqual(inst["departments"], expected_departments, f"Department count varied on {url}")

    def test_11_boundary_and_empty_filter_conditions(self):
        """Verify boundary dates and empty result sets produce well-formed empty states without exceptions."""
        # 1. Non-existent future date range
        res_future = self.client.get(
            "/api/v1/dashboard/executive-overview?date_from=2099-01-01&date_to=2099-12-31&bypass_cache=true",
            headers=self.headers
        )
        self.assertEqual(res_future.status_code, 200)
        d_future = res_future.json()
        self.assertEqual(len(d_future["recent_activity"]), 0)
        self.assertEqual(len(d_future["critical_alerts"]), 1)
        self.assertEqual(d_future["critical_alerts"][0]["type"], "all_clear")

        # 2. Non-existent campus
        res_empty_campus = self.client.get(
            "/api/v1/dashboard/executive-overview?campus=NonExistentCampusXYZ&bypass_cache=true",
            headers=self.headers
        )
        self.assertEqual(res_empty_campus.status_code, 200)
        d_empty = res_empty_campus.json()
        self.assertEqual(d_empty["institution_overview"]["hostels"], 0)
        self.assertEqual(len(d_empty["infrastructure_table"]), 0)

        # 3. Empty string / whitespace filters handled gracefully
        res_ws = self.client.get(
            "/api/v1/dashboard/executive-overview?campus=%20%20&department=%20%20&bypass_cache=true",
            headers=self.headers
        )
        self.assertEqual(res_ws.status_code, 200)


if __name__ == "__main__":
    unittest.main()
