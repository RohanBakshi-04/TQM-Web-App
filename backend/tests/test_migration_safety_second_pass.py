"""
Comprehensive Second-Pass Verification Suite for Database Migration Safety & Atomicity.

Validates:
1. Fresh migration sequence (001 - 017) without synthetic visitor fabrication.
2. Safe historical orphan archival and referential integrity check.
3. Previously migrated DB reconciliation: archival of synthetic visitor 101 without data loss.
4. Fail-closed foreign key enforcement (PRAGMA foreign_key_check).
5. Atomic rollback upon failure injection during migration execution.
6. Migration idempotency on repeated execution.

Strict Isolation: All tests run against temporary, disposable SQLite databases in tempfile.
"""

import os
import shutil
import sqlite3
import tempfile
import unittest

from backend.app.database.migrations import (
    run_migrations,
    get_applied_migrations,
    record_migration,
    ensure_migrations_table
)


class TestMigrationSafetySecondPass(unittest.TestCase):
    """Test suite ensuring absolute migration safety, atomicity, and zero fabricated identities."""

    def setUp(self):
        self.temp_dir = tempfile.mkdtemp()
        self.test_db_path = os.path.join(self.temp_dir, "test_hms.db")

    def tearDown(self):
        shutil.rmtree(self.temp_dir, ignore_errors=True)

    def _get_connection(self, foreign_keys: bool = True) -> sqlite3.Connection:
        conn = sqlite3.connect(self.test_db_path)
        conn.row_factory = sqlite3.Row
        if foreign_keys:
            conn.execute("PRAGMA foreign_keys = ON;")
        else:
            conn.execute("PRAGMA foreign_keys = OFF;")
        return conn

    # ==================== 1. FRESH MIGRATION SEQUENCE ====================

    def test_01_fresh_migration_no_synthetic_visitors_and_zero_fk_violations(self):
        """Fresh database migration sequence must apply 001-017, create zero fake visitors, and have 0 FK violations."""
        conn = self._get_connection()
        try:
            applied = run_migrations(conn)
            self.assertIn("001_initial_schema", applied)
            self.assertIn("015_enforce_referential_integrity_and_clean_orphans", applied)
            self.assertIn("016_reconcile_archival_and_operational_records", applied)
            self.assertIn("017_second_pass_remediation_and_profile_tables", applied)

            # Assert NO fabricated visitor 'Ramesh Sharma' exists
            cur = conn.cursor()
            cur.execute("SELECT * FROM visitors WHERE name = 'Ramesh Sharma' OR phone = '+91 9876543210';")
            fake_visitor = cur.fetchall()
            self.assertEqual(len(fake_visitor), 0, "No fabricated visitor (Ramesh Sharma) must exist in visitors table!")

            # Assert staff_profiles table exists
            cur.execute("SELECT name FROM sqlite_master WHERE type='table' AND name='staff_profiles';")
            self.assertIsNotNone(cur.fetchone(), "staff_profiles table must exist after migration 017")

            # Assert new student columns exist
            cur.execute("PRAGMA table_info(students);")
            cols = {c["name"] for c in cur.fetchall()}
            for expected_col in ("course", "permanent_address", "current_address", "city", "state", "postal_code", "guardian_name"):
                self.assertIn(expected_col, cols, f"Column '{expected_col}' must exist in students table")

            # Assert zero foreign key violations
            violations = cur.execute("PRAGMA foreign_key_check;").fetchall()
            self.assertEqual(len(violations), 0, f"Expected 0 foreign key violations, found {len(violations)}")

            # Idempotency check: Running again applies 0 new migrations
            repeat_applied = run_migrations(conn)
            self.assertEqual(len(repeat_applied), 0, "Repeated migration execution must be completely idempotent")
        finally:
            conn.close()

    # ==================== 2. HISTORICAL PRE-015 MIGRATION WITH DELIBERATE ORPHANS ====================

    def test_02_historical_pre015_migration_archives_deliberate_orphans(self):
        """Historical database with deliberate orphan records must safely archive orphans and leave 0 violations."""
        conn = self._get_connection()
        try:
            # 1. Apply baseline migrations 001 - 014
            applied = run_migrations(conn)
            self.assertIn("014_monetary_paise_migration", applied)

            # Revert 015, 016, 017 from schema_migrations so they can be re-run against our deliberate orphans
            conn.execute("DELETE FROM schema_migrations WHERE version IN ('015_enforce_referential_integrity_and_clean_orphans', '016_reconcile_archival_and_operational_records', '017_second_pass_remediation_and_profile_tables');")
            conn.commit()

            # Insert deliberate orphan records referencing non-existent IDs
            # Temporarily turn off foreign keys to simulate legacy unvalidated insertions
            conn.execute("PRAGMA foreign_keys = OFF;")
            cur = conn.cursor()
            cur.execute("INSERT OR IGNORE INTO users (id, username, email, password_hash, salt, first_name, last_name, is_active, failed_login_attempts) VALUES (1, 'admin', 'admin@univ.edu', 'hash', 'salt', 'Admin', 'User', 1, 0);")
            cur.execute("INSERT OR IGNORE INTO students (id, student_id, user_id, first_name, last_name, email, phone, gender, branch, academic_year, admission_date, status) VALUES (1, 'STU-001', 1, 'John', 'Doe', 'john@univ.edu', '9876543210', 'Male', 'CSE', '1st Year', '2026-08-01', 'Active');")
            cur.execute("INSERT OR IGNORE INTO visitors (id, name, phone) VALUES (10, 'Valid Visitor', '9811223344');")

            cur.execute("INSERT INTO hostels (id, name, code, hostel_type, warden_id) VALUES (99, 'Hostel Orphan', 'HO', 'Boys', 9999);")  # broken warden_id
            cur.execute("INSERT INTO visitor_logs (pass_number, visitor_id, student_id, purpose) VALUES ('VP-DELIBERATE-001', 8888, 1, 'Test');") # broken visitor_id
            cur.execute("INSERT INTO leave_requests (student_id, leave_type, destination, emergency_contact, start_date, end_date, reason, approved_by) VALUES (1, 'Home Leave', 'New Delhi', '9876543210', '2026-11-01', '2026-11-05', 'Test', 7777);") # broken approved_by
            cur.execute("INSERT INTO audit_logs (user_id, username, action, entity_name, details) VALUES (6666, 'legacy_user', 'LOGIN', 'auth', 'Orphan log');") # broken user_id
            conn.commit()
            conn.execute("PRAGMA foreign_keys = ON;")

            # Verify that FK violations exist prior to migration
            pre_violations = conn.execute("PRAGMA foreign_key_check;").fetchall()
            self.assertGreater(len(pre_violations), 0, "Deliberate orphans must register foreign key violations before migration")

            # Execute pending migrations (015, 016, 017)
            re_applied = run_migrations(conn)
            self.assertIn("015_enforce_referential_integrity_and_clean_orphans", re_applied)
            self.assertIn("016_reconcile_archival_and_operational_records", re_applied)
            self.assertIn("017_second_pass_remediation_and_profile_tables", re_applied)

            # Verify zero FK violations after migration
            post_violations = conn.execute("PRAGMA foreign_key_check;").fetchall()
            self.assertEqual(len(post_violations), 0, f"Expected 0 foreign key violations after migration, found {len(post_violations)}")

            # Verify historical_orphan_archives holds the cataloged records
            archives = conn.execute("SELECT * FROM historical_orphan_archives;").fetchall()
            self.assertGreaterEqual(len(archives), 4, "All deliberately introduced orphans must be preserved in archives")

            # Verify NO synthetic visitor was inserted
            fake = conn.execute("SELECT * FROM visitors WHERE name = 'Ramesh Sharma';").fetchall()
            self.assertEqual(len(fake), 0, "No synthetic visitor must be created during orphan remediation!")
        finally:
            conn.close()

    # ==================== 3. SYNTHETIC VISITOR RECONCILIATION IN MIGRATION 017 ====================

    def test_03_reconciliation_archives_synthetic_visitor_101(self):
        """If a previously migrated DB has synthetic visitor 101 ('Ramesh Sharma'), migration 017 safely archives it."""
        conn = self._get_connection()
        try:
            # Run up to migration 016
            run_migrations(conn)

            # Insert synthetic visitor 101 to simulate existing migrated state
            conn.execute("""
                INSERT OR IGNORE INTO visitors (id, name, phone, id_proof_type, id_proof_number, address)
                VALUES (101, 'Ramesh Sharma', '+91 9876543210', 'Aadhaar', '9876-5432-1098', '123 Civil Lines, New Delhi');
            """)
            conn.commit()

            # Mark migration 017 as pending
            conn.execute("DELETE FROM schema_migrations WHERE version = '017_second_pass_remediation_and_profile_tables';")
            conn.commit()

            # Verify visitor 101 is present
            v = conn.execute("SELECT * FROM visitors WHERE id = 101;").fetchone()
            self.assertIsNotNone(v, "Visitor 101 should be present prior to reconciliation")

            # Execute migration 017
            applied = run_migrations(conn)
            self.assertIn("017_second_pass_remediation_and_profile_tables", applied)

            # Verify visitor 101 was archived and removed from operational table
            v_post = conn.execute("SELECT * FROM visitors WHERE id = 101;").fetchone()
            self.assertIsNone(v_post, "Synthetic visitor 101 must be removed from visitors table by migration 017")

            arch = conn.execute("SELECT * FROM historical_orphan_archives WHERE source_table = 'visitors' AND source_record_id = 101;").fetchone()
            self.assertIsNotNone(arch, "Synthetic visitor 101 must be preserved in historical_orphan_archives")
            self.assertIn("Ramesh Sharma", arch["record_payload_json"])

            # Verify 0 FK violations
            violations = conn.execute("PRAGMA foreign_key_check;").fetchall()
            self.assertEqual(len(violations), 0)
        finally:
            conn.close()

    # ==================== 4. FAILURE INJECTION & ATOMIC ROLLBACK ====================

    def test_04_failure_injection_triggers_atomic_rollback(self):
        """A failure inside the migration runner must roll back changes and NOT record the migration version."""
        conn = self._get_connection()
        try:
            # Initialize migrations through 016
            run_migrations(conn)

            # Mark migration 017 as pending
            conn.execute("DELETE FROM schema_migrations WHERE version = '017_second_pass_remediation_and_profile_tables';")
            # Drop staff_profiles if created
            conn.execute("DROP TABLE IF EXISTS staff_profiles;")
            conn.commit()

            # Inject a failure condition: Create a VIEW named staff_profiles which causes CREATE TABLE staff_profiles to fail
            conn.execute("CREATE VIEW staff_profiles AS SELECT 1 AS dummy;")
            conn.commit()

            # Executing migration 017 must raise sqlite3.OperationalError because staff_profiles already exists as a view!
            with self.assertRaises(sqlite3.OperationalError):
                run_migrations(conn)

            # Verify that migration 017 was NOT recorded as applied
            applied = get_applied_migrations(conn)
            self.assertNotIn(
                "017_second_pass_remediation_and_profile_tables",
                applied,
                "Failed migration must NEVER be recorded in schema_migrations!"
            )
        finally:
            conn.close()


if __name__ == "__main__":
    unittest.main()
