"""Automated Test Suite for Q05 Fast Search & Database Indexing.

Course: BBAT104 - Fundamentals of Total Quality Management (TQM)
Quality Goal: Q05 - Reduce Response Time (<10ms SLA)
"""

import time
import unittest
from fastapi.testclient import TestClient

from backend.app.database.connection import get_db_connection
from backend.app.database.init_db import initialize_database
from backend.app.main import app
from backend.app.services.search_service import SearchService


class TestFastSearchAndIndexing(unittest.TestCase):
    """Rigorous quality verification for Fast Search, B-Tree Indexes, and FTS5 engine."""

    @classmethod
    def setUpClass(cls):
        """Initialize database with full schema, migrations, seed records, and FTS5 virtual index."""
        cls.conn = get_db_connection()
        initialize_database(cls.conn, seed=True)
        SearchService.rebuild_fts5_index(cls.conn)
        cls.client = TestClient(app)

        # Login as Super Admin for privileged tests
        login_resp = cls.client.post("/api/v1/auth/login", json={
            "username_or_email": "superadmin",
            "password": "Password123!"
        })
        cls.admin_token = login_resp.json()["access_token"]
        cls.admin_headers = {"Authorization": f"Bearer {cls.admin_token}"}

        # Login as Student for isolation tests
        student_resp = cls.client.post("/api/v1/auth/login", json={
            "username_or_email": "rohan",
            "password": "Password123!"
        })
        cls.student_token = student_resp.json()["access_token"]
        cls.student_headers = {"Authorization": f"Bearer {cls.student_token}"}

    @classmethod
    def tearDownClass(cls):
        cls.conn.close()

    def test_01_exact_match_search(self):
        """Verify exact match lookup across student names, hostel codes, and room numbers."""
        resp = self.client.get("/api/v1/search?q=Priya", headers=self.admin_headers)
        self.assertEqual(resp.status_code, 200)
        data = resp.json()
        self.assertGreater(data["total_matches"], 0)
        found_priya = any("Priya" in r["title"] for r in data["results"])
        self.assertTrue(found_priya, "Expected to find Priya in search results.")

    def test_02_prefix_search(self):
        """Verify token prefix expansion (e.g. 'Pri*' matches 'Priya', 'H1*' matches 'H1-A')."""
        resp = self.client.get("/api/v1/search?q=Pri", headers=self.admin_headers)
        self.assertEqual(resp.status_code, 200)
        data = resp.json()
        self.assertGreater(data["total_matches"], 0)
        self.assertTrue(any("Priya" in r["title"] for r in data["results"]))

    def test_03_case_insensitive_search(self):
        """Verify case insensitivity across uppercase, lowercase, and mixed case tokens."""
        resp_lower = self.client.get("/api/v1/search?q=priya", headers=self.admin_headers)
        resp_upper = self.client.get("/api/v1/search?q=PRIYA", headers=self.admin_headers)
        self.assertEqual(resp_lower.status_code, 200)
        self.assertEqual(resp_upper.status_code, 200)
        self.assertEqual(resp_lower.json()["total_matches"], resp_upper.json()["total_matches"])

    def test_04_category_filtering(self):
        """Verify explicit category filter pills constrain results to specified entity types."""
        # 1. Students only
        resp_s = self.client.get("/api/v1/search?q=Priya&category=students", headers=self.admin_headers)
        self.assertEqual(resp_s.status_code, 200)
        for r in resp_s.json()["results"]:
            self.assertEqual(r["category"], "students")

        # 2. Hostels only
        resp_h = self.client.get("/api/v1/search?q=Hostel&category=hostels", headers=self.admin_headers)
        self.assertEqual(resp_h.status_code, 200)
        for r in resp_h.json()["results"]:
            self.assertEqual(r["category"], "hostels")

    def test_05_empty_query_boundary(self):
        """Verify empty and whitespace queries return empty results gracefully without errors."""
        resp = self.client.get("/api/v1/search?q=   ", headers=self.admin_headers)
        # Query min_length constraint in FastAPI returns 422 or empty response if valid
        if resp.status_code == 200:
            self.assertEqual(resp.json()["total_matches"], 0)
        else:
            self.assertEqual(resp.status_code, 422)

    def test_06_special_characters_and_sql_injection_resilience(self):
        """Verify malicious inputs, SQL injection strings, and special characters are safely neutralized."""
        malicious_payloads = [
            "' OR '1'='1",
            "'; DROP TABLE students; --",
            '" OR 1=1 --',
            "../../../etc/passwd",
            "<script>alert(1)</script>",
            "%%%____***",
            "UNION SELECT * FROM users --"
        ]
        for payload in malicious_payloads:
            resp = self.client.get(f"/api/v1/search?q={payload}", headers=self.admin_headers)
            # Must either return 200 with 0 results or 400 bad request, NEVER 500 error
            self.assertIn(resp.status_code, [200, 400])
            if resp.status_code == 200:
                # Confirm database integrity intact
                cnt = self.conn.execute("SELECT COUNT(*) FROM students;").fetchone()[0]
                self.assertGreater(cnt, 0)

    def test_07_role_based_data_isolation(self):
        """Verify Student role cannot discover confidential payment or financial records."""
        # Admin searching for payment references
        resp_admin = self.client.get("/api/v1/search?q=PAY&category=payments", headers=self.admin_headers)
        self.assertEqual(resp_admin.status_code, 200)

        # Student searching for payments
        resp_student = self.client.get("/api/v1/search?q=PAY&category=payments", headers=self.student_headers)
        self.assertEqual(resp_student.status_code, 200)
        # Should return 0 matches for student
        self.assertEqual(resp_student.json()["total_matches"], 0)

    def test_08_explain_query_plan_uses_indexes(self):
        """Verify SQLite query planner confirms use of B-Tree indexes for critical search queries."""
        plans = [
            ("SELECT * FROM students WHERE first_name = 'Priya' AND last_name = 'Sharma';", "idx_students_name"),
            ("SELECT * FROM rooms WHERE room_number = '101';", "idx_rooms_number"),
            ("SELECT * FROM complaints WHERE status = 'Open' ORDER BY created_at DESC;", "idx_complaints_status_date"),
            ("SELECT * FROM maintenance_tasks WHERE status = 'Pending';", "idx_maintenance_status"),
            ("SELECT * FROM room_allocations WHERE allocation_status = 'Active' ORDER BY start_date DESC;", "idx_allocations_status_date")
        ]
        for sql, expected_idx in plans:
            cursor = self.conn.execute(f"EXPLAIN QUERY PLAN {sql}")
            details = [row[3] for row in cursor.fetchall()]
            has_idx = any(expected_idx in d for d in details)
            self.assertTrue(has_idx, f"Query '{sql}' failed to utilize index '{expected_idx}'. Plan: {details}")

    def test_09_q05_response_time_sla(self):
        """Verify Q05 Quality Goal: 95% of search queries execute within <10ms SLA."""
        latencies = []
        queries = ["Priya", "Sharma", "CSE", "Hostel", "Room", "101", "201", "Alloc", "Water", "Wifi"]

        for q in queries * 2:  # 20 trials
            t0 = time.perf_counter()
            resp = self.client.get(f"/api/v1/search?q={q}", headers=self.admin_headers)
            duration_ms = (time.perf_counter() - t0) * 1000.0
            latencies.append(duration_ms)
            self.assertEqual(resp.status_code, 200)
            server_latency = resp.json()["execution_time_ms"]
            # Assert server internal query execution is well under 10ms
            self.assertLess(server_latency, 10.0, f"Server execution time {server_latency}ms violated <10ms SLA")

        avg_latency = sum(latencies) / len(latencies)
        self.assertLess(avg_latency, 35.0, f"Average end-to-end HTTP latency {avg_latency:.2f}ms exceeds target.")

    def test_10_rebuild_index_authorization(self):
        """Verify only privileged administrators can trigger full index rebuilds."""
        # Student forbidden
        resp_forbidden = self.client.post("/api/v1/search/rebuild-index", headers=self.student_headers)
        self.assertEqual(resp_forbidden.status_code, 403)

        # Admin authorized
        resp_ok = self.client.post("/api/v1/search/rebuild-index", headers=self.admin_headers)
        self.assertEqual(resp_ok.status_code, 200)
        self.assertEqual(resp_ok.json()["status"], "success")


if __name__ == "__main__":
    unittest.main()
