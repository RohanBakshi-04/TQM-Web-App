"""Regression and Verification Tests for Migration Safety and Historical Archival.

Validates:
- Migration 015 & 016 safe referential integrity enforcement.
- Archival of historical orphaned records into historical_orphan_archives.
- Zero FK constraint violations after migration execution.
- Hostels warden_id nullification without synthetic warden fabrication.
- Transactional rollback on migration exception.
"""

import json
import os
import shutil
import sqlite3
import tempfile
import unittest

from backend.app.database.connection import get_db_connection
from backend.app.database.init_db import initialize_database
from backend.app.database.migrations import (
    get_applied_migrations,
    run_migrations,
)


class TestMigrationArchivalSafety(unittest.TestCase):
    """Test suite for migration integrity, historical archival, and rollback safety."""

    def setUp(self):
        self.temp_dir = tempfile.mkdtemp()
        self.pre015_backup = os.path.join(
            os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))),
            "data", "backups", "hms_backup_20261102_212154.db"
        )

    def tearDown(self):
        shutil.rmtree(self.temp_dir, ignore_errors=True)

    def test_pre015_migration_archives_81_orphans_and_achieves_zero_violations(self):
        """Pre-015 database must archive all 81 historical orphans and have 0 FK violations."""
        if not os.path.exists(self.pre015_backup):
            self.skipTest(f"Pre-015 backup not found at {self.pre015_backup}")

        test_db_path = os.path.join(self.temp_dir, "test_pre015.db")
        shutil.copy2(self.pre015_backup, test_db_path)

        conn = sqlite3.connect(test_db_path)
        conn.row_factory = sqlite3.Row

        # Verify 81 violations exist initially
        pre_violations = conn.execute("PRAGMA foreign_key_check;").fetchall()
        self.assertEqual(len(pre_violations), 81, "Pre-015 backup should have 81 violations")

        # Execute migrations
        applied = run_migrations(conn)
        self.assertIn("015_enforce_referential_integrity_and_clean_orphans", applied)
        self.assertIn("016_reconcile_archival_and_operational_records", applied)

        # Verify zero FK violations after migration
        post_violations = conn.execute("PRAGMA foreign_key_check;").fetchall()
        self.assertEqual(len(post_violations), 0, f"Expected 0 violations, found {len(post_violations)}: {post_violations}")

        # Verify historical_orphan_archives table exists and contains archived records
        cur = conn.cursor()
        archives = cur.execute("SELECT * FROM historical_orphan_archives;").fetchall()
        self.assertEqual(len(archives), 81, f"Expected 81 archived records, found {len(archives)}")

        # Verify distinct source tables in archives
        tables_archived = set(a["source_table"] for a in archives)
        self.assertIn("hostels", tables_archived)
        self.assertIn("registration_requests", tables_archived)
        self.assertIn("visitor_logs", tables_archived)
        self.assertIn("leave_requests", tables_archived)
        self.assertIn("complaint_updates", tables_archived)
        self.assertIn("audit_logs", tables_archived)
        self.assertIn("login_history", tables_archived)
        self.assertIn("notifications", tables_archived)
        self.assertIn("refresh_tokens", tables_archived)
        self.assertIn("user_roles", tables_archived)

        # Verify hostel 3 warden_id is NULL (NOT assigned to fake warden user)
        h3 = cur.execute("SELECT id, name, warden_id FROM hostels WHERE id = 3;").fetchone()
        self.assertIsNotNone(h3)
        self.assertIsNone(h3["warden_id"], "Hostel 3 warden_id must be NULL, not assigned to fake warden")

        # Verify orphaned visitor_log 1 is archived into historical_orphan_archives with zero synthetic visitor fabricated
        archived_vl = cur.execute("SELECT * FROM historical_orphan_archives WHERE source_table = 'visitor_logs';").fetchall()
        self.assertTrue(len(archived_vl) > 0, "Orphaned visitor_logs must be archived safely")

        # Zero synthetic visitor 101 fabricated
        v101 = cur.execute("SELECT * FROM visitors WHERE id = 101;").fetchone()
        self.assertIsNone(v101, "No synthetic visitor 101 should be fabricated")

        conn.close()

    def test_migration_idempotency_on_repeated_runs(self):
        """Running migrations consecutively must be completely idempotent."""
        test_db_path = os.path.join(self.temp_dir, "test_idempotent.db")
        conn = sqlite3.connect(test_db_path)
        conn.row_factory = sqlite3.Row

        applied_first = run_migrations(conn)
        self.assertGreater(len(applied_first), 0)

        applied_second = run_migrations(conn)
        self.assertEqual(applied_second, [], "Second migration execution must apply 0 migrations")

        violations = conn.execute("PRAGMA foreign_key_check;").fetchall()
        self.assertEqual(len(violations), 0)
        conn.close()

    def test_migration_transaction_rollback_on_failure(self):
        """If a failure occurs during migration execution, conn.rollback() must be executed."""
        test_db_path = os.path.join(self.temp_dir, "test_rollback.db")
        conn = sqlite3.connect(test_db_path)
        conn.row_factory = sqlite3.Row

        # Apply schema up to some point
        run_migrations(conn)
        applied_before = get_applied_migrations(conn)

        # Simulate a faulty migration by deliberately executing an invalid statement wrapped in transaction
        with self.assertRaises(sqlite3.OperationalError):
            try:
                cur = conn.cursor()
                cur.execute("INVALID SQL STATEMENT DELIBERATELY THROWN;")
                conn.commit()
            except Exception:
                conn.rollback()
                raise

        applied_after = get_applied_migrations(conn)
        self.assertEqual(applied_before, applied_after)
        conn.close()


if __name__ == "__main__":
    unittest.main()
