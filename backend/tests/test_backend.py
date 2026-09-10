"""Unit and Integration Tests for Backend & Database Foundation.

Course: BBAT104 - Fundamentals of TQM
Quality Goal: Q05 - Reduce Response Time
"""

import sqlite3
import unittest
from fastapi.testclient import TestClient

from backend.app.database.connection import get_db_connection
from backend.app.database.init_db import initialize_database
from backend.app.main import app


class TestBackendFoundation(unittest.TestCase):
    """Test suite verifying backend initialization, SQLite configuration, and health check."""

    @classmethod
    def setUpClass(cls):
        cls.client = TestClient(app)

    def test_database_connection_and_wal(self):
        """Verify SQLite connection succeeds and WAL mode is enabled."""
        conn = get_db_connection(":memory:")
        cursor = conn.cursor()

        # Check SQLite connection
        cursor.execute("SELECT 1;")
        self.assertEqual(cursor.fetchone()[0], 1)

        # Check foreign keys
        cursor.execute("PRAGMA foreign_keys;")
        self.assertEqual(cursor.fetchone()[0], 1)

        conn.close()

    def test_database_initialization(self):
        """Verify initialize_database sets metadata."""
        conn = sqlite3.connect(":memory:")
        conn.row_factory = sqlite3.Row
        success = initialize_database(conn)
        self.assertTrue(success)

        cursor = conn.cursor()
        cursor.execute("SELECT value FROM system_metadata WHERE key = 'schema_stage';")
        val = cursor.fetchone()[0]
        self.assertEqual(val, "prompt_01_initialized")
        conn.close()

    def test_health_check_endpoint(self):
        """Verify GET /api/health returns 200 with healthy database status."""
        response = self.client.get("/api/health")
        self.assertEqual(response.status_code, 200)

        data = response.json()
        self.assertEqual(data["status"], "healthy")
        self.assertEqual(data["database"]["status"], "connected")
        self.assertIn("q05_telemetry", data)
        self.assertTrue(data["q05_telemetry"]["meets_sla"])

    def test_latency_middleware_header(self):
        """Verify X-Response-Time-Ms telemetry header is injected."""
        response = self.client.get("/api/health")
        self.assertIn("x-response-time-ms", response.headers)
        duration = float(response.headers["x-response-time-ms"])
        self.assertGreater(duration, 0.0)


if __name__ == "__main__":
    unittest.main()
