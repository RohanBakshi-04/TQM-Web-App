"""Verification tests for Core Database Tables."""

import sqlite3
import unittest
from backend.app.database.schema import initialize_core_tables


class TestCoreTables(unittest.TestCase):
    def test_core_tables_created(self):
        conn = sqlite3.connect(":memory:")
        initialize_core_tables(conn)
        cursor = conn.cursor()
        cursor.execute("SELECT name FROM sqlite_master WHERE type='table' AND name NOT LIKE 'sqlite_%';")
        tables = sorted([r[0] for r in cursor.fetchall()])
        expected = [
            "announcements", "audit_logs", "notifications",
            "permissions", "role_permissions", "roles",
            "system_settings", "user_roles", "users"
        ]
        self.assertEqual(tables, expected)
        conn.close()


if __name__ == "__main__":
    unittest.main()
