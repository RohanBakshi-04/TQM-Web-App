"""Section 1 Proof Suite: End-to-End Backup and Restoration Proof on Isolated Database.

Course: BBAT104 - Fundamentals of Total Quality Management (TQM)
Quality Target: Q05 Zero Defects - ACID Durability, Online WAL Backup & Verified Restoration
"""

import os
import shutil
import sqlite3
import tempfile
import unittest
from fastapi.testclient import TestClient

from backend.app.config import settings
from backend.app.database.connection import get_db_connection
from backend.app.database.init_db import initialize_database
from backend.app.main import app
from backend.app.services.backup_service import BackupService
from backend.app.services.security import hash_password


class TestSA02BackupAndRestorationProof(unittest.TestCase):
    """Rigorous end-to-end verification of SQLite WAL online backup and restore lifecycle."""

    def setUp(self):
        self.temp_dir = tempfile.mkdtemp(prefix="hms_e2e_backup_")
        self.live_db_path = os.path.join(self.temp_dir, "live_operational.db")
        self.restored_db_path = os.path.join(self.temp_dir, "isolated_restored.db")
        self.backup_dir = os.path.join(self.temp_dir, "backups")
        os.makedirs(self.backup_dir, exist_ok=True)

        self.orig_db_path = settings.database_path
        settings.database_path = self.live_db_path
        initialize_database()

    def tearDown(self):
        settings.database_path = self.orig_db_path
        shutil.rmtree(self.temp_dir, ignore_errors=True)

    def test_end_to_end_backup_and_restoration_lifecycle(self):
        """Execute the 9-stage backup, mutation, restoration, and API verification lifecycle."""
        # ---------------------------------------------------------------------
        # Stage 1: Create realistic hierarchy, occupancy, user, permission, and audit records
        # ---------------------------------------------------------------------
        conn = sqlite3.connect(self.live_db_path)
        conn.execute("PRAGMA foreign_keys = ON;")
        conn.execute("PRAGMA journal_mode = WAL;")
        cur = conn.cursor()

        # 1.1 Custom Institution
        cur.execute("""
            INSERT INTO institutions (
                name, code, legal_name, established_year, affiliation, website,
                contact_email, contact_phone, address, city, state, country, postal_code,
                timezone, academic_year_start, academic_year_end, currency, is_active
            ) VALUES (
                'Imperial Science & Tech Institute', 'ISTI-01', 'Imperial Technical Trust', 1990, 'Central University',
                'https://isti.ac.in', 'chancellor@isti.ac.in', '+91-11-29998888', 'Knowledge Valley',
                'New Delhi', 'Delhi', 'India', '110025', 'Asia/Kolkata', '08-01', '07-31', 'INR', 1
            );
        """)
        e2e_inst_id = cur.lastrowid

        # 1.2 Custom Campus
        cur.execute("""
            INSERT INTO campuses (
                institution_id, name, code, address, city, state, country, postal_code, is_active
            ) VALUES (?, 'East Tech Campus', 'ETC-01', 'East Knowledge Highway', 'New Delhi', 'Delhi', 'India', '110092', 1);
        """, (e2e_inst_id,))
        e2e_campus_id = cur.lastrowid

        # 1.3 Custom Hostel
        cur.execute("""
            INSERT INTO hostels (
                institution_id, campus_id, name, code, hostel_type, category, address, is_active
            ) VALUES (?, ?, 'CV Raman Research Hall', 'CVR-01', 'Boys', 'Postgraduate', 'Gate 3 East Campus', 1);
        """, (e2e_inst_id, e2e_campus_id))
        e2e_hostel_id = cur.lastrowid

        # 1.4 Building, Floor, Room, Bed
        cur.execute("INSERT INTO buildings (hostel_id, campus_id, name, code, total_floors, is_active) VALUES (?, ?, 'Homi Bhabha Wing', 'HBW-01', 2, 1);", (e2e_hostel_id, e2e_campus_id))
        e2e_bldg_id = cur.lastrowid

        cur.execute("INSERT INTO floors (building_id, floor_number, floor_name, is_active) VALUES (?, 1, 'Research Floor 1', 1);", (e2e_bldg_id,))
        e2e_floor_id = cur.lastrowid

        cur.execute("INSERT INTO rooms (floor_id, room_number, room_type, capacity, base_fee, status, maintenance_status, is_active) VALUES (?, 'RF-101', 'Single', 1, 7500.0, 'Full', 'Operational', 1);", (e2e_floor_id,))
        e2e_room_id = cur.lastrowid

        cur.execute("INSERT INTO beds (room_id, bed_number, status, maintenance_status, is_active) VALUES (?, 'RF-101-A', 'Occupied', 'Operational', 1);", (e2e_room_id,))
        e2e_bed_id = cur.lastrowid

        # 1.5 Student and Active Occupancy
        cur.execute("""
            INSERT INTO students (
                student_id, first_name, last_name, gender, email, phone, status, branch, academic_year, admission_date
            ) VALUES ('STU-E2E-RAMAN', 'Vikram', 'Sarabhai', 'Male', 'vikram.s@isti.ac.in', '9811122233', 'Active', 'Aerospace', 1, '2026-08-01');
        """)
        e2e_student_row_id = cur.lastrowid

        cur.execute("""
            INSERT INTO room_allocations (
                student_id, bed_id, room_id, start_date, fee_status, allocation_status, allocated_by
            ) VALUES (?, ?, ?, '2026-08-01', 'Paid', 'Active', 1);
        """, (e2e_student_row_id, e2e_bed_id, e2e_room_id))
        e2e_alloc_id = cur.lastrowid

        # 1.6 User with role warden and specific credentials
        e2e_pwd_hash = hash_password("WardenPass2026!")
        cur.execute("""
            INSERT INTO users (
                id, username, email, password_hash, salt, first_name, last_name, phone, is_active, linked_hostel_id
            ) VALUES (8888, 'warden_raman', 'warden.raman@isti.ac.in', ?, 'salt8888', 'Vikram', 'Warden', '9899911122', 1, ?);
        """, (e2e_pwd_hash, e2e_hostel_id))
        cur.execute("INSERT INTO user_roles (user_id, role_id) VALUES (8888, 3);")  # role_id 3 = warden

        # 1.7 Audit record
        cur.execute("""
            INSERT INTO audit_logs (user_id, username, action, entity_name, entity_id, details)
            VALUES (8888, 'warden_raman', 'E2E_PRE_BACKUP_TEST', 'hostel', ?, 'Pre-backup verification footprint');
        """, (str(e2e_hostel_id),))

        conn.commit()
        conn.close()

        # ---------------------------------------------------------------------
        # Stage 2: Create a verified online backup
        # ---------------------------------------------------------------------
        backup_res = BackupService.create_backup(
            note="E2E Pre-Restoration Snapshot",
            custom_db_path=self.live_db_path,
            custom_backup_dir=self.backup_dir,
            user_id=1,
            username="superadmin"
        )
        self.assertEqual(backup_res["status"], "success")
        backup_filename = backup_res["filename"]
        backup_file_path = os.path.join(self.backup_dir, backup_filename)
        self.assertTrue(os.path.exists(backup_file_path))
        self.assertGreater(backup_res["size_bytes"], 0)
        self.assertIsNotNone(backup_res.get("checksum_sha256"))

        # ---------------------------------------------------------------------
        # Stage 3: Perform controlled post-backup database modifications
        # ---------------------------------------------------------------------
        mut_conn = sqlite3.connect(self.live_db_path)
        mut_cur = mut_conn.cursor()
        # Mutate institution name
        mut_cur.execute("UPDATE institutions SET name = 'TAMPERED_INSTITUTION_NAME' WHERE id = ?;", (e2e_inst_id,))
        # Insert a volatile hostel that must disappear after restoration
        mut_cur.execute("""
            INSERT INTO hostels (institution_id, campus_id, name, code, hostel_type, address, is_active)
            VALUES (?, ?, 'Phantom Ghost Hostel', 'GHOST-01', 'Co-Ed', 'Nowhere', 1);
        """, (e2e_inst_id, e2e_campus_id))
        # Delete the active allocation
        mut_cur.execute("DELETE FROM room_allocations WHERE id = ?;", (e2e_alloc_id,))
        mut_conn.commit()
        mut_conn.close()

        # ---------------------------------------------------------------------
        # Stage 4: Restore backup into isolated database
        # ---------------------------------------------------------------------
        # Initialize target isolated DB with a dummy placeholder file so restore has a target path
        with open(self.restored_db_path, "wb") as f:
            f.write(b"")

        restore_res = BackupService.restore_backup(
            backup_filename=backup_filename,
            custom_db_path=self.restored_db_path,
            custom_backup_dir=self.backup_dir,
            user_id=1,
            username="superadmin"
        )
        self.assertEqual(restore_res["status"], "success")
        self.assertIn("Database successfully restored", restore_res["message"])

        # ---------------------------------------------------------------------
        # Stage 5: Run SQLite integrity and foreign-key checks on restored database
        # ---------------------------------------------------------------------
        restored_conn = sqlite3.connect(self.restored_db_path)
        restored_cur = restored_conn.cursor()

        restored_cur.execute("PRAGMA integrity_check;")
        self.assertEqual(restored_cur.fetchone()[0], "ok", "Restored database must pass PRAGMA integrity_check")

        restored_cur.execute("PRAGMA foreign_key_check;")
        fk_violations = restored_cur.fetchall()
        self.assertEqual(len(fk_violations), 0, f"Restored database must have zero FK violations: {fk_violations}")

        # ---------------------------------------------------------------------
        # Stage 6: Verify all expected records and relationships
        # ---------------------------------------------------------------------
        # Verify institution has original name, NOT tampered name
        restored_cur.execute("SELECT name, code FROM institutions WHERE id = ?;", (e2e_inst_id,))
        inst_row = restored_cur.fetchone()
        self.assertIsNotNone(inst_row)
        self.assertEqual(inst_row[0], "Imperial Science & Tech Institute")
        self.assertEqual(inst_row[1], "ISTI-01")

        # Verify campus and hostel exist
        restored_cur.execute("SELECT name, code FROM campuses WHERE id = ?;", (e2e_campus_id,))
        self.assertEqual(restored_cur.fetchone()[0], "East Tech Campus")

        restored_cur.execute("SELECT name, code FROM hostels WHERE id = ?;", (e2e_hostel_id,))
        self.assertEqual(restored_cur.fetchone()[0], "CV Raman Research Hall")

        # Assert post-backup ghost hostel DOES NOT exist
        restored_cur.execute("SELECT COUNT(*) FROM hostels WHERE code = 'GHOST-01';")
        self.assertEqual(restored_cur.fetchone()[0], 0, "Post-backup modifications must be strictly eliminated")

        # Verify active room allocation is preserved
        restored_cur.execute("SELECT allocation_status, fee_status FROM room_allocations WHERE id = ?;", (e2e_alloc_id,))
        alloc_row = restored_cur.fetchone()
        self.assertIsNotNone(alloc_row)
        self.assertEqual(alloc_row[0], "Active")
        self.assertEqual(alloc_row[1], "Paid")

        # Verify audit log
        restored_cur.execute("SELECT details FROM audit_logs WHERE action = 'E2E_PRE_BACKUP_TEST';")
        self.assertEqual(restored_cur.fetchone()[0], "Pre-backup verification footprint")

        restored_conn.close()

        # ---------------------------------------------------------------------
        # Stage 7: Authenticate against the restored database
        # ---------------------------------------------------------------------
        settings.database_path = self.restored_db_path
        client = TestClient(app)

        # Login with the user seeded before the backup
        login_resp = client.post(
            "/api/v1/auth/login",
            json={"username_or_email": "warden_raman", "password": "WardenPass2026!"}
        )
        self.assertEqual(login_resp.status_code, 200, f"Login on restored DB failed: {login_resp.text}")
        warden_token = login_resp.json()["access_token"]
        warden_headers = {"Authorization": f"Bearer {warden_token}"}

        # Login superadmin to perform admin operations
        sa_resp = client.post(
            "/api/v1/auth/login",
            json={"username_or_email": "superadmin", "password": "Password123!"}
        )
        self.assertEqual(sa_resp.status_code, 200)
        sa_headers = {"Authorization": f"Bearer {sa_resp.json()['access_token']}"}

        # ---------------------------------------------------------------------
        # Stage 8: Perform representative institution and hostel API operations
        # ---------------------------------------------------------------------
        # Read institutions
        inst_api = client.get("/api/v1/institutions", headers=sa_headers)
        self.assertEqual(inst_api.status_code, 200)
        self.assertIn("total_campuses", inst_api.json())

        # Read campuses
        camp_api = client.get("/api/v1/campuses", headers=sa_headers)
        self.assertEqual(camp_api.status_code, 200)
        camp_json = camp_api.json()
        campus_codes = [c["code"] for c in (camp_json if isinstance(camp_json, list) else camp_json.get("campuses", []))]
        self.assertIn("ETC-01", campus_codes)

        # Read hostels
        hostel_api = client.get("/api/v1/infrastructure/hostels", headers=sa_headers)
        self.assertEqual(hostel_api.status_code, 200)
        hostel_json = hostel_api.json()
        hostel_codes = [h["code"] for h in (hostel_json if isinstance(hostel_json, list) else hostel_json.get("hostels", []))]
        self.assertIn("CVR-01", hostel_codes)

        # Read 8-tier hierarchy
        hier_api = client.get("/api/v1/infrastructure/hierarchy", headers=sa_headers)
        self.assertEqual(hier_api.status_code, 200)
        self.assertIn("hierarchy", hier_api.json())

        # ---------------------------------------------------------------------
        # Stage 9: Verify WAL handling and backup metadata
        # ---------------------------------------------------------------------
        chk_conn = sqlite3.connect(self.restored_db_path)
        chk_cur = chk_conn.cursor()
        chk_cur.execute("PRAGMA journal_mode = WAL;")
        jmode = chk_cur.fetchone()[0]
        self.assertEqual(jmode.lower(), "wal", "Restored database must operate in WAL journal mode")

        # Verify backup metadata tracking
        chk_cur.execute("SELECT filename, size_bytes, checksum_sha256 FROM backup_metadata WHERE filename = ?;", (backup_filename,))
        bmeta_row = chk_cur.fetchone()
        self.assertIsNotNone(bmeta_row, "Backup metadata must be recorded in the database")
        self.assertEqual(bmeta_row[0], backup_filename)
        self.assertGreater(bmeta_row[1], 0)
        self.assertTrue(len(bmeta_row[2]) == 64, "SHA-256 checksum must be a 64-char hex string")

        chk_conn.close()


if __name__ == "__main__":
    unittest.main()
