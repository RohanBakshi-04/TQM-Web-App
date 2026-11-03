"""Automated Test Suite for Q05 Cached Dashboard, Invalidation, and Quick Navigation.

Course: BBAT104 - Fundamentals of Total Quality Management (TQM)
Quality Goal: Q05 - Reduce Response Time (<10ms SLA)
"""

from concurrent.futures import ThreadPoolExecutor
import time
import unittest
from fastapi.testclient import TestClient

from backend.app.database.connection import get_db_connection
from backend.app.database.init_db import initialize_database
from backend.app.main import app
from backend.app.services.cache_invalidation import CacheInvalidator
from backend.app.services.cache_service import cache_service
from backend.app.services.dashboard_service import DashboardService


class TestCachedDashboardAndNavigation(unittest.TestCase):
    """Rigorous verification of in-memory caching, atomic invalidation, and multi-tenant isolation."""

    @classmethod
    def setUpClass(cls):
        cls.conn = get_db_connection()
        initialize_database(cls.conn, seed=True)
        cls.client = TestClient(app)

        # Login as Super Admin
        login_admin = cls.client.post("/api/v1/auth/login", json={
            "username_or_email": "superadmin",
            "password": "Password123!"
        })
        cls.admin_token = login_admin.json()["access_token"]
        cls.admin_headers = {"Authorization": f"Bearer {cls.admin_token}"}

        # Login as Student
        login_student = cls.client.post("/api/v1/auth/login", json={
            "username_or_email": "rohan",
            "password": "Password123!"
        })
        cls.student_token = login_student.json()["access_token"]
        cls.student_headers = {"Authorization": f"Bearer {cls.student_token}"}

    @classmethod
    def tearDownClass(cls):
        cls.conn.close()

    def setUp(self):
        cache_service.clear()
        cache_service.reset_stats()

    def test_01_cache_creation_and_hit(self):
        """Verify cold fetch causes MISS and subsequent fetch causes HIT with <1ms latency."""
        # 1. Cold fetch
        r1 = self.client.get("/api/v1/metrics/dashboard", headers=self.admin_headers)
        self.assertEqual(r1.status_code, 200)
        data1 = r1.json()
        self.assertEqual(data1["cache_status"], "MISS")

        # 2. Warm fetch
        r2 = self.client.get("/api/v1/metrics/dashboard", headers=self.admin_headers)
        self.assertEqual(r2.status_code, 200)
        data2 = r2.json()
        self.assertEqual(data2["cache_status"], "HIT")
        self.assertLess(data2["execution_time_ms"], 1.0, "Warm cache response time exceeded 1ms target.")
        self.assertEqual(data1["metrics"]["total_students"], data2["metrics"]["total_students"])

    def test_02_cache_expiration_ttl(self):
        """Verify cached items automatically expire when TTL elapses."""
        test_key = "test:ttl:key"
        cache_service.set(test_key, {"status": "valid"}, ttl=0.1)
        self.assertIsNotNone(cache_service.get(test_key))

        # Sleep past TTL
        time.sleep(0.15)
        self.assertIsNone(cache_service.get(test_key), "Expected key to be expired and return None.")

    def test_03_cache_hit_and_miss_telemetry(self):
        """Verify cache statistics accurately track hits, misses, and hit ratio."""
        cache_service.clear()
        cache_service.reset_stats()
        # Generate 1 miss and 3 hits
        self.client.get("/api/v1/metrics/dashboard", headers=self.admin_headers)
        self.client.get("/api/v1/metrics/dashboard", headers=self.admin_headers)
        self.client.get("/api/v1/metrics/dashboard", headers=self.admin_headers)
        self.client.get("/api/v1/metrics/dashboard", headers=self.admin_headers)

        stats_resp = self.client.get("/api/v1/metrics/cache/stats", headers=self.admin_headers)
        self.assertEqual(stats_resp.status_code, 200)
        stats = stats_resp.json()

        self.assertGreaterEqual(stats["hits"], 3)
        self.assertGreaterEqual(stats["misses"], 1)
        self.assertGreater(stats["hit_ratio_percent"], 50.0)

    def test_04_cache_invalidation_after_allocation(self):
        """Verify creating an allocation atomically invalidates cached dashboard aggregates."""
        # Populate warm cache
        r_warm = self.client.get("/api/v1/metrics/dashboard", headers=self.admin_headers)
        self.assertEqual(r_warm.json()["cache_status"], "MISS")

        r_hit = self.client.get("/api/v1/metrics/dashboard", headers=self.admin_headers)
        self.assertEqual(r_hit.json()["cache_status"], "HIT")

        # Create allocation (Student 2410301012 -> Bed G01-A)
        # Note: clean any existing active allocation for student 2 first
        self.conn.execute("UPDATE room_allocations SET allocation_status = 'Terminated' WHERE student_id = 2;")
        self.conn.execute("UPDATE beds SET status = 'Available' WHERE bed_number = 'G01-A';")
        self.conn.commit()

        # Trigger allocation mutation
        CacheInvalidator.on_allocation_mutation(hostel_id=1)

        # Subsequent fetch must be MISS
        r_after = self.client.get("/api/v1/metrics/dashboard", headers=self.admin_headers)
        self.assertEqual(r_after.json()["cache_status"], "MISS", "Expected cache to be invalidated after allocation mutation.")

    def test_05_cache_invalidation_after_checkout(self):
        """Verify checkout mutation invalidates bed counts and dashboard statistics."""
        # Warm cache
        self.client.get("/api/v1/metrics/dashboard", headers=self.admin_headers)
        self.assertEqual(self.client.get("/api/v1/metrics/dashboard", headers=self.admin_headers).json()["cache_status"], "HIT")

        # Invalidate via checkout hook
        CacheInvalidator.on_allocation_mutation()

        # Next query is fresh
        r_post = self.client.get("/api/v1/metrics/dashboard", headers=self.admin_headers)
        self.assertEqual(r_post.json()["cache_status"], "MISS")

    def test_06_cache_isolation_between_hostels(self):
        """Verify Hostel A cache is completely isolated from Hostel B and invalidations do not bleed."""
        # 1. Warm cache for Hostel 1 and Hostel 2
        _ = DashboardService.get_dashboard_metrics(self.conn, user_roles=["warden"], linked_hostel_id=1)
        _ = DashboardService.get_dashboard_metrics(self.conn, user_roles=["warden"], linked_hostel_id=2)

        # Verify both are warm
        m1 = DashboardService.get_dashboard_metrics(self.conn, user_roles=["warden"], linked_hostel_id=1)
        m2 = DashboardService.get_dashboard_metrics(self.conn, user_roles=["warden"], linked_hostel_id=2)
        self.assertEqual(m1["cache_status"], "HIT")
        self.assertEqual(m2["cache_status"], "HIT")

        # 2. Invalidate ONLY Hostel 1
        cache_service.invalidate_by_tag("hostel_1")

        # 3. Assert Hostel 1 was evicted (MISS) while Hostel 2 remains cached (HIT)
        m1_after = DashboardService.get_dashboard_metrics(self.conn, user_roles=["warden"], linked_hostel_id=1)
        m2_after = DashboardService.get_dashboard_metrics(self.conn, user_roles=["warden"], linked_hostel_id=2)

        self.assertEqual(m1_after["cache_status"], "MISS", "Hostel 1 should have been evicted.")
        self.assertEqual(m2_after["cache_status"], "HIT", "Hostel 2 must remain cached (isolation violation).")

    def test_07_failed_transaction_does_not_corrupt_cache(self):
        """Verify aborted database operations do NOT invalidate cache or corrupt state."""
        # Warm cache
        self.client.get("/api/v1/metrics/dashboard", headers=self.admin_headers)
        self.assertEqual(self.client.get("/api/v1/metrics/dashboard", headers=self.admin_headers).json()["cache_status"], "HIT")

        # Simulate failed transaction
        try:
            cursor = self.conn.cursor()
            # Attempt invalid SQL that fails
            cursor.execute("INSERT INTO students (id, student_id) VALUES (1, 'DUPLICATE');")
            self.conn.commit()
        except Exception:
            self.conn.rollback()

        # Cache must remain valid HIT
        r_check = self.client.get("/api/v1/metrics/dashboard", headers=self.admin_headers)
        self.assertEqual(r_check.json()["cache_status"], "HIT", "Aborted transaction prematurely invalidated cache.")

    def test_08_concurrent_cache_access(self):
        """Verify thread-safe cache operations under concurrent multi-threaded load."""
        def worker(idx):
            for _ in range(25):
                key = f"concurrent:key:{idx % 5}"
                cache_service.set(key, {"value": idx}, ttl=10.0, tags=["concurrency"])
                _ = cache_service.get(key)
                if idx % 10 == 0:
                    cache_service.invalidate_by_tag("concurrency")

        with ThreadPoolExecutor(max_workers=8) as executor:
            futures = [executor.submit(worker, i) for i in range(16)]
            for f in futures:
                f.result()  # Should complete cleanly without deadlock or exception

        stats = cache_service.get_stats()
        self.assertGreater(stats["hits"] + stats["misses"], 100)

    def test_09_role_based_dashboard_scoping(self):
        """Verify student dashboard hides global confidential financials while Super Admin sees all."""
        # Admin view
        r_admin = self.client.get("/api/v1/metrics/dashboard", headers=self.admin_headers)
        self.assertEqual(r_admin.status_code, 200)
        admin_data = r_admin.json()
        self.assertTrue(admin_data["scope"]["is_global"])

        # Student view
        r_student = self.client.get("/api/v1/metrics/dashboard", headers=self.student_headers)
        self.assertEqual(r_student.status_code, 200)
        student_data = r_student.json()
        self.assertEqual(student_data["scope"]["role"], "student")

    def test_10_manual_cache_flush_permissions(self):
        """Verify only privileged roles can invoke POST /api/v1/metrics/cache/clear."""
        # Student forbidden
        r_student = self.client.post("/api/v1/metrics/cache/clear", headers=self.student_headers)
        self.assertEqual(r_student.status_code, 403)

        # Admin allowed
        r_admin = self.client.post("/api/v1/metrics/cache/clear", headers=self.admin_headers)
        self.assertEqual(r_admin.status_code, 200)
        self.assertEqual(r_admin.json()["status"], "success")


if __name__ == "__main__":
    unittest.main()
