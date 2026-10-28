"""Integration tests for Dashboard Telemetry & Aggregation Endpoints.

Course: BBAT104 - Fundamentals of Total Quality Management (TQM)
Quality Goal: Q05 - Reduce Response Time
"""

import unittest
from fastapi.testclient import TestClient
from backend.app.database.init_db import initialize_database
from backend.app.main import app


class TestDashboardAPI(unittest.TestCase):
    """Test suite covering dashboard statistics and aggregation endpoints."""

    @classmethod
    def setUpClass(cls):
        initialize_database()
        cls.client = TestClient(app)

    def test_dashboard_stats_unauthorized(self):
        """Test accessing /api/v1/dashboard/stats without token returns 401."""
        res = self.client.get("/api/v1/dashboard/stats")
        self.assertEqual(res.status_code, 401)

    def test_dashboard_stats_authenticated(self):
        """Test authenticated user retrieves real aggregation statistics."""
        login_res = self.client.post("/api/v1/auth/login", json={
            "username_or_email": "superadmin",
            "password": "Password123!"
        })
        token = login_res.json()["access_token"]

        res = self.client.get(
            "/api/v1/dashboard/stats",
            headers={"Authorization": f"Bearer {token}"}
        )
        self.assertEqual(res.status_code, 200)
        data = res.json()
        self.assertIn("hostels", data)
        self.assertIn("students", data)
        self.assertIn("finance", data)
        self.assertIn("operations", data)
        self.assertIn("recent_activity", data)

        # Check real values from database seeder
        self.assertGreaterEqual(data["hostels"]["total"], 1)
        self.assertGreaterEqual(data["students"]["total"], 1)
        self.assertIsInstance(data["hostels"]["occupancy_rate"], float)


if __name__ == "__main__":
    unittest.main()
