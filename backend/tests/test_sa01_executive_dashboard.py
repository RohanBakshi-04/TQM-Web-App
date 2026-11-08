import os
import shutil
import statistics
import tempfile
import time
import unittest
from fastapi.testclient import TestClient

from backend.app.config import settings
from backend.app.database.connection import get_db_connection
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
        self.assertIn(health["integrity_check"], ["ok", "healthy"])
        self.assertIn("integrity_diagnostics", health)
        diag = health["integrity_diagnostics"]
        self.assertIn(diag["status"], ["ok", "healthy"])
        self.assertIn("freshness_seconds", diag)
        self.assertIn("freshness_label", diag)
        self.assertIn("cache_stats", health)
        self.assertEqual(health["api_latency_target_ms"], 10.0)

    def test_02_filter_parameters_and_isolation(self):
        """Test executive overview queries with campus, hostel, and department filters."""
        # Filter by North Campus
        res_campus = self.client.get(
            "/api/v1/dashboard/executive-overview?campus=North%20Campus&bypass_cache=true",
            headers=self.superadmin_headers
        )
        self.assertEqual(res_campus.status_code, 200)
        d_campus = res_campus.json()
        self.assertEqual(d_campus["metadata"]["filters_applied"]["campus"], "North Campus")

        # Filter by specific hostel_id=1
        res_hostel = self.client.get(
            "/api/v1/dashboard/executive-overview?hostel_id=1&bypass_cache=true",
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

    def test_07_no_fabricated_fallback_metrics(self):
        """Verify that all metrics are genuinely derived from the database and not hardcoded defaults."""
        res = self.client.get("/api/v1/dashboard/executive-overview?bypass_cache=true", headers=self.superadmin_headers)
        self.assertEqual(res.status_code, 200)
        data = res.json()

        conn = get_db_connection()
        try:
            # Roles count
            actual_roles = conn.execute("SELECT COUNT(*) FROM roles").fetchone()[0]
            self.assertEqual(data["institution_overview"]["stakeholders"], actual_roles)

            # Dashboards count
            actual_dashboards = conn.execute("SELECT COUNT(*) FROM dashboards").fetchone()[0]
            self.assertEqual(data["institution_overview"]["dashboards"], actual_dashboards)

            # Departments count
            actual_departments = conn.execute("SELECT COUNT(*) FROM departments").fetchone()[0]
            self.assertEqual(data["institution_overview"]["departments"], actual_departments)

            # Hostels count
            actual_hostels = conn.execute("SELECT COUNT(*) FROM hostels").fetchone()[0]
            self.assertEqual(data["institution_overview"]["hostels"], actual_hostels)

            # Buildings count
            actual_buildings = conn.execute("SELECT COUNT(*) FROM buildings").fetchone()[0]
            self.assertEqual(data["institution_overview"]["buildings"], actual_buildings)

            # Rooms count
            actual_rooms = conn.execute("SELECT COUNT(*) FROM rooms").fetchone()[0]
            self.assertEqual(data["institution_overview"]["rooms"], actual_rooms)

            # Beds count
            actual_beds = conn.execute("SELECT COUNT(*) FROM beds").fetchone()[0]
            self.assertEqual(data["institution_overview"]["beds"], actual_beds)
        finally:
            conn.close()

    def test_08_student_deduplication_and_reconciliation(self):
        """Verify student counting is strictly deduplicated and active + inactive reconciles."""
        res = self.client.get("/api/v1/dashboard/executive-overview?bypass_cache=true", headers=self.superadmin_headers)
        self.assertEqual(res.status_code, 200)
        data = res.json()

        inst = data["institution_overview"]
        kpi = data["kpi_grid"]["students"]

        # Exact reconciliation: active + inactive = total
        self.assertEqual(inst["students_active"] + inst["students_inactive"], inst["students"])
        self.assertEqual(kpi["active"] + kpi["inactive_withdrawn"], kpi["total"])

        # Insert multiple historical allocations for student 1 to ensure distinct deduplication
        conn = get_db_connection()
        try:
            s_row = conn.execute("SELECT id FROM students LIMIT 1").fetchone()
            b_row = conn.execute("SELECT id, room_id FROM beds LIMIT 1").fetchone()
            if s_row and b_row:
                s_id = s_row[0]
                b_id = b_row["id"]
                r_id = b_row["room_id"]
                # Insert two historical cancelled/transferred allocations for this same student
                conn.execute(
                    "INSERT INTO room_allocations (student_id, room_id, bed_id, start_date, allocation_status) VALUES (?, ?, ?, '2026-01-01', 'Cancelled')",
                    (s_id, r_id, b_id)
                )
                conn.execute(
                    "INSERT INTO room_allocations (student_id, room_id, bed_id, start_date, allocation_status) VALUES (?, ?, ?, '2026-02-01', 'Transferred')",
                    (s_id, r_id, b_id)
                )
                conn.commit()
        finally:
            conn.close()

        # Query again with bypass_cache
        res2 = self.client.get("/api/v1/dashboard/executive-overview?bypass_cache=true", headers=self.superadmin_headers)
        self.assertEqual(res2.status_code, 200)
        data2 = res2.json()

        # Student count must NOT have increased due to multiple room allocations
        self.assertEqual(data2["institution_overview"]["students"], inst["students"])

    def test_09_cache_isolation_and_role_boundaries(self):
        """Verify cache keys incorporate facility and role scopes to prevent cross-boundary data leakage."""
        cache_service.clear()

        # Request for Hostel 1
        res_h1 = self.client.get("/api/v1/dashboard/executive-overview?hostel_id=1", headers=self.superadmin_headers)
        self.assertEqual(res_h1.status_code, 200)
        d_h1 = res_h1.json()
        self.assertEqual(d_h1["metadata"]["cache_status"], "MISS")
        self.assertEqual(d_h1["institution_overview"]["hostels"], 1)

        # Request for Hostel 2 (must be a cache MISS, not leaking Hostel 1 data)
        res_h2 = self.client.get("/api/v1/dashboard/executive-overview?hostel_id=2", headers=self.superadmin_headers)
        self.assertEqual(res_h2.status_code, 200)
        d_h2 = res_h2.json()
        self.assertEqual(d_h2["metadata"]["cache_status"], "MISS")
        self.assertEqual(d_h2["institution_overview"]["hostels"], 1)

        # Global Request (must also be a cache MISS, returning all hostels)
        res_global = self.client.get("/api/v1/dashboard/executive-overview", headers=self.superadmin_headers)
        self.assertEqual(res_global.status_code, 200)
        d_global = res_global.json()
        self.assertEqual(d_global["metadata"]["cache_status"], "MISS")
        self.assertGreater(d_global["institution_overview"]["hostels"], 1)

    def test_10_cache_invalidation_on_mutation(self):
        """Verify domain tag cache invalidation purges executive overview cache upon data mutations."""
        cache_service.clear()

        # Prime cache
        res1 = self.client.get("/api/v1/dashboard/executive-overview", headers=self.superadmin_headers)
        self.assertEqual(res1.status_code, 200)
        self.assertEqual(res1.json()["metadata"]["cache_status"], "MISS")

        # Verify warm hit
        res2 = self.client.get("/api/v1/dashboard/executive-overview", headers=self.superadmin_headers)
        self.assertEqual(res2.status_code, 200)
        self.assertEqual(res2.json()["metadata"]["cache_status"], "HIT")

        # Invalidate via domain tag 'students'
        cache_service.invalidate_by_tag("students")

        # Next query must be a cache MISS due to domain invalidation
        res3 = self.client.get("/api/v1/dashboard/executive-overview", headers=self.superadmin_headers)
        self.assertEqual(res3.status_code, 200)
        self.assertEqual(res3.json()["metadata"]["cache_status"], "MISS")

    def test_11_q05_benchmarking_telemetry(self):
        """Honest benchmark telemetry for Q05 (< 10ms SLA) across cold (N=100) and warm (N=100) requests."""
        cache_service.clear()

        def compute_stats(data):
            sorted_data = sorted(data)
            n = len(sorted_data)
            return {
                "count": n,
                "median": round(statistics.median(sorted_data), 3),
                "p90": round(sorted_data[min(int(n * 0.90), n - 1)], 3),
                "p95": round(sorted_data[min(int(n * 0.95), n - 1)], 3),
                "p99": round(sorted_data[min(int(n * 0.99), n - 1)], 3),
                "min": round(min(sorted_data), 3),
                "max": round(max(sorted_data), 3),
                "mean": round(statistics.mean(sorted_data), 3),
                "stddev": round(statistics.stdev(sorted_data) if n > 1 else 0.0, 3)
            }

        cold_client_latencies = []
        cold_server_latencies = []
        for _ in range(100):
            t0 = time.perf_counter()
            res = self.client.get("/api/v1/dashboard/executive-overview?bypass_cache=true", headers=self.superadmin_headers)
            dt = (time.perf_counter() - t0) * 1000.0
            self.assertEqual(res.status_code, 200)
            cold_client_latencies.append(dt)
            cold_server_latencies.append(res.json()["metadata"]["execution_time_ms"])

        warm_client_latencies = []
        warm_server_latencies = []
        for _ in range(100):
            t0 = time.perf_counter()
            res = self.client.get("/api/v1/dashboard/executive-overview", headers=self.superadmin_headers)
            dt = (time.perf_counter() - t0) * 1000.0
            self.assertEqual(res.status_code, 200)
            warm_client_latencies.append(dt)
            warm_server_latencies.append(res.json()["metadata"]["execution_time_ms"])

        cold_client_stats = compute_stats(cold_client_latencies)
        cold_server_stats = compute_stats(cold_server_latencies)
        warm_client_stats = compute_stats(warm_client_latencies)
        warm_server_stats = compute_stats(warm_server_latencies)

        print("\n=================== Q05 BENCHMARK REPORT (N=100) ===================")
        print(f"Cold HTTP Roundtrip (ms):  {cold_client_stats}")
        print(f"Cold Internal Service (ms): {cold_server_stats}")
        print(f"Warm HTTP Roundtrip (ms):  {warm_client_stats}")
        print(f"Warm Internal Service (ms): {warm_server_stats}")
        print("===================================================================")

        # Q05 Verification: Internal service execution is strictly < 10ms SLA
        self.assertLess(warm_server_stats["p95"], 10.0)
        self.assertLess(cold_server_stats["median"], 10.0)

    def test_12_database_integrity_monitor_endpoints(self):
        """Verify DatabaseIntegrityMonitor endpoints and diagnostic state payload."""
        # GET /api/v1/metrics/integrity
        res_get = self.client.get("/api/v1/metrics/integrity", headers=self.superadmin_headers)
        self.assertEqual(res_get.status_code, 200)
        data_get = res_get.json()
        self.assertIn("status", data_get)
        self.assertIn(data_get["status"], ["healthy", "warning", "failed", "unknown"])
        self.assertIn("freshness_label", data_get)
        self.assertIn("freshness_seconds", data_get)
        self.assertIn("last_verified_at", data_get)

        # POST /api/v1/metrics/integrity/verify (Manual trigger)
        res_post = self.client.post("/api/v1/metrics/integrity/verify", headers=self.superadmin_headers)
        self.assertEqual(res_post.status_code, 200)
        data_post = res_post.json()
        self.assertEqual(data_post["status"], "success")
        self.assertEqual(data_post["diagnostics"]["status"], "healthy")
        self.assertGreaterEqual(data_post["diagnostics"]["duration_ms"], 0.0)

    def test_13_database_integrity_concurrent_stampede_protection(self):
        """Verify thread-safe locking prevents multiple simultaneous database page scans under concurrent stampede."""
        import threading
        import time
        from backend.app.services.database_integrity_service import integrity_monitor

        # 1. Reset and force expired cache before starting concurrent workers
        integrity_monitor.reset()
        integrity_monitor.cached_until = time.time() - 100.0
        integrity_monitor._last_verified_ts = 0.0
        integrity_monitor.status = "unknown"
        initial_scans = integrity_monitor.total_physical_scans

        # 2. Use a synchronization barrier so all 10 workers attempt verification simultaneously
        worker_count = 10
        barrier = threading.Barrier(worker_count)
        results = []
        lock = threading.Lock()

        def worker():
            barrier.wait()
            diag = integrity_monitor.check_integrity(force=False)
            with lock:
                results.append(diag)

        threads = [threading.Thread(target=worker) for _ in range(worker_count)]
        for t in threads:
            t.start()
        for t in threads:
            t.join()

        # 3. Exactly one physical scan must have occurred
        scans_executed = integrity_monitor.total_physical_scans - initial_scans
        self.assertEqual(
            scans_executed, 1,
            f"Cache stampede defect: expected exactly 1 physical scan, but {scans_executed} were executed."
        )

        # 4. Assert that all returned diagnostics are valid and consistent
        self.assertEqual(len(results), worker_count)
        for diag in results:
            self.assertEqual(diag["status"], "healthy")
            self.assertEqual(diag["raw_result"].lower(), "ok")
            self.assertGreaterEqual(diag["duration_ms"], 0.0)
            self.assertIsNotNone(diag["last_verified_at"])

        # 5. Subsequent concurrent calls with valid cache must cause 0 physical scans
        scans_before_cached = integrity_monitor.total_physical_scans
        results_cached = []
        barrier_cached = threading.Barrier(worker_count)

        def worker_cached():
            barrier_cached.wait()
            diag = integrity_monitor.check_integrity(force=False)
            with lock:
                results_cached.append(diag)

        threads_cached = [threading.Thread(target=worker_cached) for _ in range(worker_count)]
        for t in threads_cached:
            t.start()
        for t in threads_cached:
            t.join()

        self.assertEqual(
            integrity_monitor.total_physical_scans - scans_before_cached, 0,
            "Valid cache should not trigger any physical scans"
        )
        self.assertEqual(len(results_cached), worker_count)
        for diag in results_cached:
            self.assertTrue(diag["is_cached"])
            self.assertEqual(diag["status"], "healthy")

        # 6. Test forced verification behavior (force=True must perform exactly 1 fresh scan)
        scans_before_forced = integrity_monitor.total_physical_scans
        forced_diag = integrity_monitor.check_integrity(force=True)
        self.assertEqual(
            integrity_monitor.total_physical_scans - scans_before_forced, 1,
            "Forced verification must execute a physical scan"
        )
        self.assertFalse(forced_diag["is_cached"])
        self.assertEqual(forced_diag["status"], "healthy")

    def test_14_database_integrity_simulation_and_recovery(self):
        """Verify integrity monitoring detects anomalies and recovers cleanly."""
        from backend.app.services.database_integrity_service import integrity_monitor

        # Simulate warning state
        integrity_monitor.simulate_status("warning", error="Simulated page scan degradation")
        res_warn = self.client.get("/api/v1/metrics/integrity", headers=self.superadmin_headers)
        self.assertEqual(res_warn.status_code, 200)
        self.assertEqual(res_warn.json()["status"], "warning")
        self.assertEqual(res_warn.json()["last_error"], "Simulated page scan degradation")

        # Recover using real scan
        res_recover = self.client.post("/api/v1/metrics/integrity/verify", headers=self.superadmin_headers)
        self.assertEqual(res_recover.status_code, 200)
        self.assertEqual(res_recover.json()["status"], "success")
        self.assertEqual(res_recover.json()["diagnostics"]["status"], "healthy")
        self.assertIsNone(res_recover.json()["diagnostics"]["last_error"])


    def test_15_database_integrity_double_checked_locking_and_ttl(self):
        """Verify double-checked locking, TTL expiration, and timestamp correctness."""
        from backend.app.services.database_integrity_service import integrity_monitor
        import time

        # 1. Healthy scan primes cache
        diag1 = integrity_monitor.check_integrity(force=True)
        self.assertEqual(diag1["status"], "healthy")
        self.assertFalse(diag1["is_cached"])
        first_verified_at = diag1["last_verified_at"]
        self.assertIsNotNone(first_verified_at)

        # 2. Subsequent call within TTL returns cached result without live scan
        diag2 = integrity_monitor.check_integrity(force=False)
        self.assertEqual(diag2["status"], "healthy")
        self.assertTrue(diag2["is_cached"])
        self.assertEqual(diag2["last_verified_at"], first_verified_at)

        # 3. Simulate TTL expiration by adjusting cached_until into past
        integrity_monitor.cached_until = time.time() - 1.0
        diag3 = integrity_monitor.check_integrity(force=False)
        self.assertFalse(diag3["is_cached"], "Expired TTL must trigger live physical scan")
        self.assertEqual(diag3["status"], "healthy")

        # 4. Verify failed verification preserves last successful verification timestamp
        prior_verified_at = integrity_monitor.last_verified_at
        integrity_monitor.set_simulated_error("Simulated B-Tree corrupt node error")
        diag_fail = integrity_monitor.check_integrity(force=True)
        self.assertEqual(diag_fail["status"], "failed")
        # last_verified_at must NOT be updated on failure
        self.assertEqual(diag_fail["last_verified_at"], prior_verified_at)
        # last_attempted_at must be updated
        self.assertIsNotNone(diag_fail["last_attempted_at"])

        # Reset simulation
        integrity_monitor.reset()
        diag_clean = integrity_monitor.check_integrity(force=True)
        self.assertEqual(diag_clean["status"], "healthy")

    def test_16_rbac_unauthorized_access_matrix(self):
        """Verify non-executive roles receive 403 Forbidden on executive overview & integrity verify."""
        unauthorized_users = [
            ("rohan", "Password123!", "student"),
            ("parent", "Password123!", "parent_guardian"),
            ("maintenance", "Password123!", "maintenance_staff"),
            ("security", "Password123!", "security_guard"),
            ("clerk", "Password123!", "hostel_clerk"),
            ("accountant", "Password123!", "accountant"),
        ]

        for username, password, role_name in unauthorized_users:
            login_res = self.client.post("/api/v1/auth/login", json={
                "username_or_email": username,
                "password": password
            })
            self.assertEqual(login_res.status_code, 200, f"Login failed for demo user {username}")
            token = login_res.json()["access_token"]
            headers = {"Authorization": f"Bearer {token}"}

            # 1. Executive overview endpoint (Super Admin only)
            res_exec = self.client.get("/api/v1/dashboard/executive-overview", headers=headers)
            self.assertEqual(
                res_exec.status_code, 403,
                f"Role {role_name} ({username}) must be rejected with 403 Forbidden from executive overview"
            )

            # 2. Trigger manual integrity scan endpoint (Super Admin & IT Admin only)
            res_verify = self.client.post("/api/v1/metrics/integrity/verify", headers=headers)
            self.assertEqual(
                res_verify.status_code, 403,
                f"Role {role_name} ({username}) must be rejected with 403 Forbidden from integrity scan trigger"
            )


if __name__ == "__main__":
    unittest.main()
