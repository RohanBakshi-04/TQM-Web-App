"""Unit and Integration Tests for Genuinely Atomic Database Migrations.

Course: BBAT104 - Fundamentals of Total Quality Management (TQM)
Quality Goal: Q05 - Reduce Response Time (< 10ms SLA)

Validates:
1. Genuine per-migration transaction atomicity.
2. Complete rollback of DDL (tables, indexes) and DML (rows, updates) upon failure.
3. Earlier committed migrations remain intact upon subsequent migration failure.
4. Migration version is NOT recorded when a migration fails.
5. Migration retry succeeds after removing injected failure.
6. Zero unresolved foreign key violations across all 19 migrations.
7. Complete idempotency on repeated execution.
"""

import os
import shutil
import sqlite3
import tempfile
import unittest
from typing import List

from backend.app.database.migrations import (
    begin_migration_transaction,
    ensure_migrations_table,
    get_applied_migrations,
    record_migration,
    run_migrations,
)


class TestMigrationAtomicity(unittest.TestCase):
    """Test suite for database migration transaction atomicity, failure rollback, and integrity."""

    def setUp(self):
        self.temp_dir = tempfile.mkdtemp()
        self.db_path = os.path.join(self.temp_dir, "test_atomicity.db")
        self.conn = sqlite3.connect(self.db_path)
        self.conn.row_factory = sqlite3.Row
        self.conn.execute("PRAGMA foreign_keys = ON;")

    def tearDown(self):
        if hasattr(self, "conn") and self.conn:
            self.conn.close()
        shutil.rmtree(self.temp_dir, ignore_errors=True)

    def test_01_all_20_migrations_fresh_db_zero_violations(self):
        """All 20 migrations must execute in atomic order with 0 foreign key violations."""
        applied = run_migrations(self.conn)
        self.assertEqual(len(applied), 20, f"Expected 20 migrations, applied: {len(applied)}")
        self.assertIn("001_initial_schema", applied)
        self.assertIn("018_multi_ward_parent_relationship_and_approvals", applied)
        self.assertIn("019_notification_deliveries_and_leases", applied)
        self.assertIn("020_enterprise_rbac_and_10_stakeholders", applied)

        violations = self.conn.execute("PRAGMA foreign_key_check;").fetchall()
        self.assertEqual(len(violations), 0, f"Expected 0 foreign key violations, found {len(violations)}")

        # Verify idempotency
        applied_second = run_migrations(self.conn)
        self.assertEqual(applied_second, [], "Second migration execution must apply 0 migrations")

    def test_02_failure_injection_rolls_back_ddl_dml_and_version(self):
        """Injected failure inside a migration must completely roll back DDL, DML, and version recording."""
        # 1. Establish baseline table and initial data
        cur = self.conn.cursor()
        cur.execute("CREATE TABLE baseline_items (id INTEGER PRIMARY KEY, name TEXT, balance INTEGER);")
        cur.execute("INSERT INTO baseline_items (id, name, balance) VALUES (1, 'Initial Asset', 5000);")
        self.conn.commit()

        ensure_migrations_table(self.conn)
        record_migration(self.conn, "000_baseline", "Baseline Setup", commit=True)
        applied_before = get_applied_migrations(self.conn)
        self.assertEqual(applied_before, ["000_baseline"])

        # 2. Simulate an atomic migration with an injected failure
        version_to_fail = "999_faulty_migration"
        begin_migration_transaction(self.conn)
        try:
            # Perform DDL: Create new table and new index
            cur.execute("CREATE TABLE faulty_new_table (id INTEGER PRIMARY KEY, details TEXT);")
            cur.execute("CREATE INDEX idx_faulty_details ON faulty_new_table(details);")

            # Perform DML: Modify baseline record and insert new record
            cur.execute("UPDATE baseline_items SET balance = 99999 WHERE id = 1;")
            cur.execute("INSERT INTO faulty_new_table (id, details) VALUES (1, 'Temporary Faulty Row');")

            # Record migration within the transaction
            record_migration(self.conn, version_to_fail, "Faulty Migration Name", commit=False)

            # Injected critical failure before commit
            raise RuntimeError("Deliberately injected migration failure for atomicity verification!")

            self.conn.commit()
        except Exception:
            self.conn.rollback()

        # 3. Assertions: Schema and data MUST be completely restored to pre-migration state
        # A. Faulty table must NOT exist in sqlite_master
        cur.execute("SELECT name FROM sqlite_master WHERE type='table' AND name='faulty_new_table';")
        self.assertIsNone(cur.fetchone(), "Newly created table must be completely absent after rollback!")

        # B. Faulty index must NOT exist
        cur.execute("SELECT name FROM sqlite_master WHERE type='index' AND name='idx_faulty_details';")
        self.assertIsNone(cur.fetchone(), "Newly created index must be completely absent after rollback!")

        # C. Modified row must return to its original value
        cur.execute("SELECT balance FROM baseline_items WHERE id = 1;")
        row = cur.fetchone()
        self.assertIsNotNone(row)
        self.assertEqual(row["balance"], 5000, "Modified row must return to its original value after rollback!")

        # D. Migration version must NOT be recorded in schema_migrations
        applied_after = get_applied_migrations(self.conn)
        self.assertEqual(applied_after, applied_before, "Failed migration version must NOT be recorded!")
        self.assertNotIn(version_to_fail, applied_after)

        # 4. Retry after removing injected failure: must succeed cleanly
        begin_migration_transaction(self.conn)
        cur.execute("CREATE TABLE faulty_new_table (id INTEGER PRIMARY KEY, details TEXT);")
        cur.execute("CREATE INDEX idx_faulty_details ON faulty_new_table(details);")
        cur.execute("UPDATE baseline_items SET balance = 7500 WHERE id = 1;")
        record_migration(self.conn, version_to_fail, "Faulty Migration Name", commit=False)
        self.conn.commit()

        # Verify retry succeeded
        applied_retry = get_applied_migrations(self.conn)
        self.assertIn(version_to_fail, applied_retry)
        cur.execute("SELECT name FROM sqlite_master WHERE type='table' AND name='faulty_new_table';")
        self.assertIsNotNone(cur.fetchone())
        cur.execute("SELECT balance FROM baseline_items WHERE id = 1;")
        self.assertEqual(cur.fetchone()["balance"], 7500)

    def test_03_migration_019_tables_and_indexes_exist(self):
        """Migration 019 must create notification_deliveries, background_job_leases, and web_push_subscriptions."""
        run_migrations(self.conn)
        cur = self.conn.cursor()

        cur.execute("SELECT name FROM sqlite_master WHERE type='table' AND name='notification_deliveries';")
        self.assertIsNotNone(cur.fetchone(), "notification_deliveries table must exist")

        cur.execute("SELECT name FROM sqlite_master WHERE type='table' AND name='background_job_leases';")
        self.assertIsNotNone(cur.fetchone(), "background_job_leases table must exist")

        cur.execute("SELECT name FROM sqlite_master WHERE type='table' AND name='web_push_subscriptions';")
        self.assertIsNotNone(cur.fetchone(), "web_push_subscriptions table must exist")

        # Verify columns of notification_deliveries
        cur.execute("PRAGMA table_info(notification_deliveries);")
        cols = {r["name"]: r["type"] for r in cur.fetchall()}
        self.assertIn("notification_id", cols)
        self.assertIn("user_id", cols)
        self.assertIn("channel", cols)
        self.assertIn("provider", cols)
        self.assertIn("delivery_status", cols)


if __name__ == "__main__":
    unittest.main()
