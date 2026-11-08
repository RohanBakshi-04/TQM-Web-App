"""Area A Test Suite: Database Integrity, Migration Rollback & Backup Recovery (SA-02).

Course: BBAT104 - Fundamentals of Total Quality Management (TQM)
Quality Goal: Q05 - Zero-Defect Database Architecture & Relational Integrity
"""

import os
import shutil
import sqlite3
import tempfile
import unittest
from backend.app.database.connection import get_db_connection
from backend.app.database.migrations import (
    ensure_migrations_table,
    get_applied_migrations,
    record_migration,
    run_migrations,
)
from backend.app.database.schema import initialize_all_tables
from backend.app.services.backup_service import BackupService
from backend.app.services.infrastructure_service import InfrastructureService
from backend.app.models.infrastructure_dto import (
    CampusCreate,
    HostelCreateExt,
    BuildingCreateExt,
    FloorCreate,
    RoomCreate,
    BedCreate,
)
from fastapi import HTTPException


class TestSA02DatabaseIntegrityAndRecovery(unittest.TestCase):
    """Test suite for Migration Correctness, Foreign Key Consistency, and Online Backup Recovery."""

    def setUp(self):
        self.temp_dir = tempfile.mkdtemp(prefix="hms_test_db_")
        self.db_path = os.path.join(self.temp_dir, "test_hms.db")
        self.backup_dir = os.path.join(self.temp_dir, "backups")
        os.makedirs(self.backup_dir, exist_ok=True)

        # Initialize fresh database up to Migration 022
        conn = sqlite3.connect(self.db_path)
        conn.execute("PRAGMA foreign_keys = ON;")
        conn.execute("PRAGMA journal_mode = WAL;")
        run_migrations(conn)
        conn.close()

    def tearDown(self):
        shutil.rmtree(self.temp_dir, ignore_errors=True)

    def test_01_migration_execution_and_idempotency(self):
        """Verify migrations execute cleanly, record history, and are idempotent on re-run."""
        conn = sqlite3.connect(self.db_path)
        try:
            applied = get_applied_migrations(conn)
            self.assertIn("022_sa02_institution_campus_hostel_management", applied)

            # Re-running migrations on an already migrated database should apply 0 new migrations safely
            applied_again = run_migrations(conn)
            self.assertEqual(len(applied_again), 0, "Migration runner should be completely idempotent")

            # Check PRAGMA integrity
            cursor = conn.cursor()
            cursor.execute("PRAGMA integrity_check;")
            res = cursor.fetchone()
            self.assertEqual(res[0], "ok", "Database integrity check must pass with 'ok'")

            # Check PRAGMA foreign_key_check
            cursor.execute("PRAGMA foreign_key_check;")
            fk_violations = cursor.fetchall()
            self.assertEqual(len(fk_violations), 0, f"Zero foreign key violations expected, found {fk_violations}")
        finally:
            conn.close()

    def test_02_pre_sa02_schema_upgrade_simulation(self):
        """Verify that a database representing pre-SA-02 schema upgrades safely to 022 without data loss."""
        pre_db_path = os.path.join(self.temp_dir, "pre_sa02.db")
        conn = sqlite3.connect(pre_db_path)
        conn.execute("PRAGMA foreign_keys = ON;")
        conn.execute("PRAGMA journal_mode = WAL;")

        try:
            # Initialize core schema and migrations 001 through 021 manually
            ensure_migrations_table(conn)
            initialize_all_tables(conn)

            # Insert realistic pre-SA-02 hostel and building records
            cursor = conn.cursor()
            cursor.execute("""
                INSERT INTO hostels (id, name, code, hostel_type, address, is_active)
                VALUES (101, 'Legacy North Hostel', 'LNH-01', 'Boys', 'North Campus Enclave', 1);
            """)
            cursor.execute("""
                INSERT INTO buildings (id, hostel_id, name, code, total_floors, is_active)
                VALUES (201, 101, 'Legacy North Block A', 'LNB-A', 3, 1);
            """)
            cursor.execute("""
                INSERT INTO floors (id, building_id, floor_number, floor_name)
                VALUES (301, 201, 1, 'First Floor');
            """)
            conn.commit()

            # Record that migrations 001-021 were applied
            for i in range(1, 22):
                v_str = f"{i:03d}_mock_migration"
                record_migration(conn, v_str, f"Mock pre-migration {i}", commit=False)
            conn.commit()

            # Now run migrations: migration 022 should execute and upgrade the pre-existing records safely
            applied = run_migrations(conn)
            self.assertIn("022_sa02_institution_campus_hostel_management", applied)

            # Assert legacy hostel now has institution_id and campus_id backfilled
            cursor.execute("SELECT institution_id, campus_id, category FROM hostels WHERE id = 101;")
            h_row = cursor.fetchone()
            self.assertIsNotNone(h_row[0], "Hostel should be associated with default institution")
            self.assertIsNotNone(h_row[1], "Hostel should be associated with default campus")

            # Assert building now has campus_id and block created
            cursor.execute("SELECT campus_id FROM buildings WHERE id = 201;")
            b_row = cursor.fetchone()
            self.assertEqual(b_row[0], h_row[1], "Building campus_id should inherit from hostel")

            # Assert auto-block creation
            cursor.execute("SELECT id, name FROM blocks WHERE building_id = 201;")
            blk_row = cursor.fetchone()
            self.assertIsNotNone(blk_row, "Default block should be auto-created for legacy building")

            # Assert foreign key check passes
            cursor.execute("PRAGMA foreign_key_check;")
            self.assertEqual(len(cursor.fetchall()), 0, "No FK violations on pre-SA02 upgrade")
        finally:
            conn.close()

    def test_03_invalid_parent_relationship_rejection(self):
        """Verify that service layer and DB reject invalid parent-child relationships across the 8 tiers."""
        conn = sqlite3.connect(self.db_path)
        conn.row_factory = sqlite3.Row
        conn.execute("PRAGMA foreign_keys = ON;")

        try:
            # 1. Campus linked to nonexistent institution (ID 99999)
            with self.assertRaises(HTTPException) as ctx:
                InfrastructureService.create_campus(
                    conn,
                    CampusCreate(
                        institution_id=99999,
                        name="Invalid Institution Campus",
                        code="INV-C1",
                        address="Unknown Road",
                        city="Nowhere",
                        state="Delhi"
                    )
                )
            self.assertEqual(ctx.exception.status_code, 400)
            self.assertIn("Institution with ID 99999 does not exist", ctx.exception.detail)

            # 2. Hostel linked to nonexistent campus (ID 88888)
            with self.assertRaises(HTTPException) as ctx:
                InfrastructureService.create_hostel_extended(
                    conn,
                    HostelCreateExt(
                        campus_id=88888,
                        name="Invalid Campus Hostel",
                        code="INV-H1",
                        hostel_type="Boys"
                    )
                )
            self.assertEqual(ctx.exception.status_code, 400)
            self.assertIn("Campus with ID 88888 does not exist", ctx.exception.detail)

            # 3. Building linked to nonexistent hostel (ID 77777)
            with self.assertRaises(HTTPException) as ctx:
                InfrastructureService.create_building_extended(
                    conn,
                    BuildingCreateExt(
                        hostel_id=77777,
                        name="Invalid Hostel Building",
                        code="INV-B1",
                        total_floors=2
                    )
                )
            self.assertEqual(ctx.exception.status_code, 400)
            self.assertIn("Hostel with ID 77777 does not exist", ctx.exception.detail)

            # 4. Floor linked to nonexistent building (ID 66666)
            with self.assertRaises(HTTPException) as ctx:
                InfrastructureService.create_floor(
                    conn,
                    FloorCreate(
                        building_id=66666,
                        floor_number=1,
                        floor_name="First Floor"
                    )
                )
            self.assertEqual(ctx.exception.status_code, 400)
            self.assertIn("Building with ID 66666 does not exist", ctx.exception.detail)

            # 5. Room linked to nonexistent floor (ID 55555)
            with self.assertRaises(HTTPException) as ctx:
                InfrastructureService.create_room(
                    conn,
                    RoomCreate(
                        floor_id=55555,
                        room_number="R-999",
                        room_type="Single",
                        capacity=1,
                        base_fee=5000.0
                    )
                )
            self.assertEqual(ctx.exception.status_code, 400)
            self.assertIn("Floor with ID 55555 does not exist", ctx.exception.detail)

            # 6. Bed linked to nonexistent room (ID 44444)
            with self.assertRaises(HTTPException) as ctx:
                InfrastructureService.create_bed(
                    conn,
                    BedCreate(
                        room_id=44444,
                        bed_number="R999-A"
                    )
                )
            self.assertEqual(ctx.exception.status_code, 400)
            self.assertIn("Room with ID 44444 does not exist", ctx.exception.detail)
        finally:
            conn.close()

    def test_04_online_backup_creation_and_restoration_lifecycle(self):
        """Verify SQLite WAL online backup, integrity verification, and safe restoration."""
        # 1. Create a live state with a custom campus
        conn = sqlite3.connect(self.db_path)
        conn.row_factory = sqlite3.Row
        conn.execute("PRAGMA foreign_keys = ON;")
        new_campus = InfrastructureService.create_campus(
            conn,
            CampusCreate(
                institution_id=1,
                name="West Campus Enclave",
                code="WC-01",
                address="West Bypass",
                city="New Delhi",
                state="Delhi"
            )
        )
        conn.close()

        # 2. Trigger online backup
        backup_result = BackupService.create_backup(
            note="SA-02 Milestone Hardening Test Backup",
            custom_db_path=self.db_path,
            custom_backup_dir=self.backup_dir,
            user_id=1,
            username="superadmin"
        )
        self.assertEqual(backup_result["status"], "success")
        self.assertTrue(os.path.exists(backup_result["path"]))
        self.assertGreater(backup_result["size_bytes"], 1024)

        # 3. Verify backup file integrity
        integrity = BackupService.verify_backup_integrity(backup_result["path"])
        self.assertTrue(integrity["is_valid"])
        self.assertIsNone(integrity["error"])
        self.assertGreater(integrity["table_count"], 30)

        # 4. Mutate live database by deleting the newly created campus
        conn = sqlite3.connect(self.db_path)
        conn.row_factory = sqlite3.Row
        conn.execute("PRAGMA foreign_keys = ON;")
        InfrastructureService.delete_campus(conn, new_campus["id"])
        with self.assertRaises(HTTPException):
            InfrastructureService.get_campus_by_id(conn, new_campus["id"])
        conn.close()

        # 5. Restore from backup into target database
        restore_result = BackupService.restore_backup(
            backup_result["filename"],
            custom_db_path=self.db_path,
            custom_backup_dir=self.backup_dir,
            user_id=1,
            username="superadmin"
        )
        self.assertEqual(restore_result["status"], "success")
        self.assertIn("successfully restored", restore_result["message"])

        # 6. Verify restored database preserves the recovered campus
        conn = sqlite3.connect(self.db_path)
        conn.row_factory = sqlite3.Row
        conn.execute("PRAGMA foreign_keys = ON;")
        recovered = InfrastructureService.get_campus_by_id(conn, new_campus["id"])
        self.assertEqual(recovered["name"], "West Campus Enclave")
        self.assertEqual(recovered["code"], "WC-01")

        # 7. Assert integrity and foreign keys are clean post-restore
        cursor = conn.cursor()
        cursor.execute("PRAGMA integrity_check;")
        self.assertEqual(cursor.fetchone()[0], "ok")
        cursor.execute("PRAGMA foreign_key_check;")
        self.assertEqual(len(cursor.fetchall()), 0)
        conn.close()


if __name__ == "__main__":
    unittest.main()
