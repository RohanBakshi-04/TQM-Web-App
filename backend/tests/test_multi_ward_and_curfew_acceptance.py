"""Multi-Ward Parent Relationship, Approval Flow, Curfew Monitor, and Backup Restoration Acceptance Tests.

Course: BBAT104 - Fundamentals of Total Quality Management (TQM)
Quality Goal: Q05 - Reduce Response Time (< 10ms SLA)
"""

import asyncio
import os
import shutil
import sqlite3
import tempfile
import unittest
from datetime import datetime, timedelta
from unittest.mock import patch, MagicMock

from backend.app.config import settings
from backend.app.database.connection import get_db_connection
from backend.app.database.migrations import run_migrations
from backend.app.models.auth_dto import RegisterRequest
from backend.app.services.auth_dependencies import get_parent_authorized_ward_ids
from backend.app.services.auth_service import AuthService
from backend.app.services.backup_service import BackupService
from backend.app.services.notification_service import NotificationService
from backend.app.services.visitor_service import VisitorService


class TestMultiWardAndCurfewAcceptance(unittest.TestCase):
    """Rigorous acceptance testing for multi-ward parent model, curfew lifecycle, SMTP adapter, and backup drill."""

    @classmethod
    def setUpClass(cls):
        # Create an isolated temporary test database directory
        cls.test_dir = tempfile.mkdtemp()
        cls.db_path = os.path.join(cls.test_dir, "test_multi_ward.db")
        cls._orig_db_path = settings.database_path
        settings.database_path = cls.db_path
        os.environ["DATABASE_PATH"] = cls.db_path
        os.environ["APP_ENV"] = "testing"

        # Initialize schema and run all migrations up to 018
        conn = sqlite3.connect(cls.db_path)
        conn.row_factory = sqlite3.Row
        run_migrations(conn)

        # Seed roles
        cursor = conn.cursor()
        for r_id, r_name in [
            (1, 'super_admin'), (2, 'student'), (3, 'parent_guardian'),
            (4, 'warden'), (5, 'staff'), (6, 'maintenance_staff'),
            (7, 'security_guard'), (8, 'mess_manager'), (9, 'accountant')
        ]:
            cursor.execute("INSERT OR IGNORE INTO roles (id, name, description) VALUES (?, ?, ?);", (r_id, r_name, r_name.title()))

        # Seed test hostel
        cursor.execute("""
            INSERT OR IGNORE INTO hostels (id, name, code, hostel_type, address, is_active)
            VALUES (1, 'Nilgiri Boys Hostel', 'NBH', 'Boys', 'Campus North', 1);
        """)

        # Seed admin user
        cursor.execute("""
            INSERT OR IGNORE INTO users (id, username, email, password_hash, salt, first_name, last_name, is_active)
            VALUES (1, 'admin_mw', 'admin_mw@univ.edu', 'hash', '', 'Admin', 'User', 1);
        """)
        cursor.execute("INSERT OR IGNORE INTO user_roles (user_id, role_id) VALUES (1, 1);")

        # Seed Student 1
        cursor.execute("""
            INSERT OR IGNORE INTO users (id, username, email, password_hash, salt, first_name, last_name, is_active)
            VALUES (10, 'stu_ward1', 'ward1@univ.edu', 'hash', '', 'Ward', 'One', 1);
        """)
        cursor.execute("INSERT OR IGNORE INTO user_roles (user_id, role_id) VALUES (10, 2);")
        cursor.execute("""
            INSERT OR IGNORE INTO students (id, student_id, user_id, first_name, last_name, email, phone, gender, branch, academic_year, admission_date, status)
            VALUES (101, 'ROLL-W1', 10, 'Ward', 'One', 'ward1@univ.edu', '9876500001', 'Male', 'CSE', '1st Year', '2026-08-01', 'Active');
        """)
        cursor.execute("UPDATE users SET linked_student_id = 101 WHERE id = 10;")

        # Seed Student 2
        cursor.execute("""
            INSERT OR IGNORE INTO users (id, username, email, password_hash, salt, first_name, last_name, is_active)
            VALUES (20, 'stu_ward2', 'ward2@univ.edu', 'hash', '', 'Ward', 'Two', 1);
        """)
        cursor.execute("INSERT OR IGNORE INTO user_roles (user_id, role_id) VALUES (20, 2);")
        cursor.execute("""
            INSERT OR IGNORE INTO students (id, student_id, user_id, first_name, last_name, email, phone, gender, branch, academic_year, admission_date, status)
            VALUES (102, 'ROLL-W2', 20, 'Ward', 'Two', 'ward2@univ.edu', '9876500002', 'Female', 'ECE', '2nd Year', '2026-08-01', 'Active');
        """)
        cursor.execute("UPDATE users SET linked_student_id = 102 WHERE id = 20;")

        conn.commit()
        conn.close()

    @classmethod
    def tearDownClass(cls):
        settings.database_path = cls._orig_db_path
        if os.path.exists(cls.test_dir):
            shutil.rmtree(cls.test_dir, ignore_errors=True)

    def test_01_migration_018_schema_and_integrity(self):
        """Verify Migration 018 created registration_request_wards and parent_student_links with valid foreign keys."""
        with get_db_connection() as conn:
            cursor = conn.cursor()
            # Verify tables exist
            cursor.execute("SELECT name FROM sqlite_master WHERE type='table' AND name='registration_request_wards';")
            self.assertIsNotNone(cursor.fetchone())

            cursor.execute("SELECT name FROM sqlite_master WHERE type='table' AND name='parent_student_links';")
            self.assertIsNotNone(cursor.fetchone())

            # Verify foreign key check passes
            violations = cursor.execute("PRAGMA foreign_key_check;").fetchall()
            self.assertEqual(len(violations), 0, f"Foreign key violations found: {violations}")

    def test_02_multi_ward_parent_registration_and_rejection_of_invalid_identifier(self):
        """Verify that registering with invalid ward identifier fails closed, while valid multi-ward succeeds."""
        # 1. Invalid ward identifier should raise 404
        invalid_payload = RegisterRequest(
            username="parent_invalid",
            email="parent_inv@univ.edu",
            password="SecurePassword123!",
            first_name="Inv",
            last_name="Parent",
            phone="9876543001",
            role="parent_guardian",
            ward_identifiers=["ROLL-W1", "NON_EXISTENT_ROLL"]
        )
        with self.assertRaises(Exception) as ctx:
            AuthService.register_user(invalid_payload)
        self.assertIn("No enrolled student found matching identifier 'NON_EXISTENT_ROLL'", str(ctx.exception))

        # 2. Valid multi-ward registration
        valid_payload = RegisterRequest(
            username="parent_multi",
            email="parent_multi@univ.edu",
            password="SecurePassword123!",
            first_name="Multi",
            last_name="Parent",
            phone="9876543002",
            role="parent_guardian",
            ward_identifiers=["ROLL-W1", "ROLL-W2"],
            relationship="Father"
        )
        res = AuthService.register_user(valid_payload)
        self.assertEqual(res["status"], "Pending_Approval")
        self.assertTrue(res["requires_student_approval"])

        # Verify registration_request_wards rows were created for both children
        with get_db_connection() as conn:
            cursor = conn.cursor()
            cursor.execute("""
                SELECT student_id, student_approval_status, administrative_approval_status
                FROM registration_request_wards
                WHERE registration_request_id = (SELECT id FROM registration_requests WHERE username = 'parent_multi');
            """)
            wards = cursor.fetchall()
            self.assertEqual(len(wards), 2)
            student_ids = {w[0] for w in wards}
            self.assertEqual(student_ids, {101, 102})
            for w in wards:
                self.assertEqual(w[1], "Pending")
                self.assertEqual(w[2], "Pending")

    def test_03_per_ward_student_approval_and_final_activation(self):
        """Verify that account remains pending until all wards and admin approve, then activates parent_student_links."""
        with get_db_connection() as conn:
            cursor = conn.cursor()
            cursor.execute("SELECT id, user_id FROM registration_requests WHERE username = 'parent_multi';")
            req_row = cursor.fetchone()
            req_id = req_row[0]
            parent_uid = req_row[1]

        # Context for Student 1
        stu1_user = {"id": 10, "username": "stu_ward1", "roles": ["student"], "active_role": "student", "linked_student_id": 101}
        # Context for Student 2
        stu2_user = {"id": 20, "username": "stu_ward2", "roles": ["student"], "active_role": "student", "linked_student_id": 102}
        # Context for Admin
        admin_user = {"id": 1, "username": "admin_mw", "roles": ["super_admin"], "active_role": "super_admin"}

        # 1. Student 1 approves their ward link
        res1 = AuthService.process_registration_action(req_id, "approve", None, stu1_user)
        self.assertEqual(res1["status"], "Pending")

        with get_db_connection() as conn:
            cursor = conn.cursor()
            cursor.execute("SELECT student_approval_status FROM registration_requests WHERE id = ?;", (req_id,))
            self.assertEqual(cursor.fetchone()[0], "Pending")
            cursor.execute("SELECT is_active FROM users WHERE id = ?;", (parent_uid,))
            self.assertEqual(cursor.fetchone()[0], 0)

        # 2. Student 2 approves their ward link
        res2 = AuthService.process_registration_action(req_id, "approve", None, stu2_user)
        self.assertEqual(res2["status"], "Pending")

        with get_db_connection() as conn:
            cursor = conn.cursor()
            cursor.execute("SELECT student_approval_status FROM registration_requests WHERE id = ?;", (req_id,))
            self.assertEqual(cursor.fetchone()[0], "Approved")  # Both students approved

        # 3. Administrator approves the request
        res3 = AuthService.process_registration_action(req_id, "approve", None, admin_user)
        self.assertEqual(res3["status"], "Approved")

        # 4. Verify account is active and parent_student_links contains both wards
        with get_db_connection() as conn:
            cursor = conn.cursor()
            cursor.execute("SELECT is_active FROM users WHERE id = ?;", (parent_uid,))
            self.assertEqual(cursor.fetchone()[0], 1)

            cursor.execute("SELECT student_id, status FROM parent_student_links WHERE parent_user_id = ?;", (parent_uid,))
            links = cursor.fetchall()
            self.assertEqual(len(links), 2)
            self.assertEqual({l[0] for l in links}, {101, 102})
            for l in links:
                self.assertEqual(l[1], "Active")

            # Verify get_parent_authorized_ward_ids returns both wards
            parent_ctx = {"id": parent_uid, "user_id": parent_uid, "email": "parent_multi@univ.edu", "phone": "9876543002"}
            auth_wards = get_parent_authorized_ward_ids(conn, parent_ctx)
            self.assertIn(101, auth_wards)
            self.assertIn(102, auth_wards)

    def test_04_staff_profile_work_location_and_emergency_contacts(self):
        """Verify that staff registration persists work_location alias and emergency contacts into staff_profiles."""
        staff_payload = RegisterRequest(
            username="staff_tech",
            email="staff_tech@univ.edu",
            password="SecurePassword123!",
            first_name="Tech",
            last_name="Staff",
            phone="9876543003",
            role="staff",
            specialization="electrician",
            work_location="Engineering Block",
            emergency_contact_name="Emergency Contact Person",
            emergency_contact_phone="9876549999"
        )
        res = AuthService.register_user(staff_payload)
        self.assertEqual(res["status"], "Pending_Approval")

        with get_db_connection() as conn:
            cursor = conn.cursor()
            cursor.execute("""
                SELECT assigned_location, emergency_contact_name, emergency_contact_phone
                FROM staff_profiles
                WHERE user_id = (SELECT id FROM users WHERE username = 'staff_tech');
            """)
            sp = cursor.fetchone()
            self.assertIsNotNone(sp)
            self.assertEqual(sp[0], "Engineering Block")
            self.assertEqual(sp[1], "Emergency Contact Person")
            self.assertEqual(sp[2], "9876549999")

    def test_05_curfew_monitor_detection_and_task_execution(self):
        """Verify visitor curfew monitor identifies overdue visitors and updates records safely."""
        with get_db_connection() as conn:
            cursor = conn.cursor()
            # Seed visitor and overdue visitor log
            cursor.execute("""
                INSERT OR IGNORE INTO visitors (id, name, phone, id_proof_type, id_proof_number)
                VALUES (501, 'Curfew Test Visitor', '9988776655', 'Aadhaar', '9988-7766-5544');
            """)
            past_time = (datetime.now() - timedelta(hours=2)).strftime("%Y-%m-%d %H:%M:%S")
            cursor.execute("""
                INSERT INTO visitor_logs (
                    visitor_id, student_id, hostel_id, check_in_time, expected_exit_time,
                    purpose, status, pass_number
                ) VALUES (501, 101, 1, ?, ?, 'Academic Discussion', 'Checked_In', 'VP-CURFEW-01');
            """, (past_time, past_time))
            conn.commit()

        # Run curfew monitor
        res = VisitorService.check_visitor_curfew()
        self.assertIn("overdue_count", res)
        self.assertGreaterEqual(res["overdue_count"], 1)

        # Verify visitor log status was updated to Overdue
        with get_db_connection() as conn:
            cursor = conn.cursor()
            cursor.execute("SELECT status FROM visitor_logs WHERE pass_number = 'VP-CURFEW-01';")
            status_val = cursor.fetchone()[0]
            self.assertEqual(status_val, "Overdue")

    def test_06_notification_service_smtp_adapter(self):
        """Verify SMTP adapter behavior for Unconfigured_Channel, Disabled, and simulated delivery."""
        # 1. Unconfigured SMTP_HOST
        with patch.dict(os.environ, {"SMTP_HOST": ""}):
            res = NotificationService.send_email_smtp("test@univ.edu", "Test Subject", "Test Body")
            self.assertEqual(res["status"], "Unconfigured_Channel")

        # 2. Configured SMTP_HOST with simulated successful delivery
        with patch.dict(os.environ, {"SMTP_HOST": "smtp.test.edu", "SMTP_PORT": "587"}):
            with patch("smtplib.SMTP") as mock_smtp:
                instance = mock_smtp.return_value.__enter__.return_value
                instance.send_message.return_value = {}
                res = NotificationService.send_email_smtp("test@univ.edu", "Subject", "Body")
                self.assertEqual(res["status"], "Sent")

        # 3. Configured SMTP_HOST with failed delivery
        with patch.dict(os.environ, {"SMTP_HOST": "smtp.test.edu", "SMTP_PORT": "587"}):
            with patch("smtplib.SMTP", side_effect=Exception("Connection refused")):
                res = NotificationService.send_email_smtp("test@univ.edu", "Subject", "Body")
                self.assertEqual(res["status"], "Failed")
                self.assertIn("Connection refused", res["error"])

    def test_07_backup_restoration_drill(self):
        """Verify hot online backup creation and integrity check during a restoration drill."""
        temp_backup_dir = os.path.join(self.test_dir, "backups")
        os.makedirs(temp_backup_dir, exist_ok=True)

        with patch("backend.app.services.backup_service.BACKUP_DIR", temp_backup_dir):
            # Create backup
            backup_res = BackupService.create_backup(note="Multi-Ward Acceptance Test Backup")
            self.assertEqual(backup_res["status"], "success")
            self.assertTrue(os.path.exists(backup_res["path"]))

            # Verify integrity
            integrity = BackupService.verify_backup_integrity(backup_res["path"])
            self.assertTrue(integrity["is_valid"])
            self.assertGreater(integrity["table_count"], 30)

            # Test isolated restore into a separate database file
            restore_target = os.path.join(self.test_dir, "restored_drill.db")
            src_conn = sqlite3.connect(backup_res["path"])
            dest_conn = sqlite3.connect(restore_target)
            src_conn.backup(dest_conn)
            src_conn.close()
            dest_conn.close()

            # Verify restored database integrity and zero FK violations
            restored_integrity = BackupService.verify_backup_integrity(restore_target)
            self.assertTrue(restored_integrity["is_valid"])

            chk_conn = sqlite3.connect(restore_target)
            violations = chk_conn.execute("PRAGMA foreign_key_check;").fetchall()
            chk_conn.close()
            self.assertEqual(len(violations), 0, f"Restored DB foreign key violations: {violations}")


if __name__ == "__main__":
    unittest.main()
