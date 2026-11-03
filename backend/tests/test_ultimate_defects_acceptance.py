"""Comprehensive Acceptance Test Suite for Ultimate Master Defects 1-7.

Validates:
- Defect 1: Migration atomicity and rollback safety (covered also in test_migration_atomicity.py).
- Defect 2: Strict Warden facility scoping (no unassigned approvals, no cross-hostel approvals, HTTP 403).
- Defect 3: Multi-child parent approval across different hostels (independent warden approvals, activation only on 100% approval).
- Defect 4: Parent access strictly through verified parent_student_links.
- Defect 5: Student date_of_birth and semester persistence and validation.
- Defect 6: Real notification delivery logging into notification_deliveries table with honest channel statuses.
- Defect 7: Distributed multi-worker curfew monitoring with background_job_leases, atomic transitions, and alert deduplication.
"""

import os
import secrets
import shutil
import sqlite3
import tempfile
import unittest
from datetime import datetime, timedelta
from fastapi import HTTPException
from fastapi.testclient import TestClient

from backend.app.config import settings
from backend.app.database.connection import get_db_connection
from backend.app.database.init_db import initialize_database
from backend.app.database.migrations import run_migrations
from backend.app.main import app
from backend.app.models.auth_dto import RegisterRequest
from backend.app.models.notification_dto import NotificationCreate, NotificationPreferenceDTO
from backend.app.services.auth_dependencies import (
    get_parent_authorized_ward_ids,
    verify_student_isolation,
)
from backend.app.services.auth_service import AuthService
from backend.app.services.notification_service import NotificationService
from backend.app.services.visitor_service import VisitorService


class TestUltimateDefectsAcceptance(unittest.TestCase):
    """End-to-end acceptance tests verifying zero defects across groups 1 through 7."""

    @classmethod
    def setUpClass(cls):
        cls.temp_dir = tempfile.mkdtemp()
        cls.db_path = os.path.join(cls.temp_dir, "test_ultimate_acceptance.db")
        cls.orig_db_path = settings.database_path
        settings.database_path = cls.db_path

        conn = get_db_connection()
        initialize_database(conn, seed=True)
        conn.close()

        cls.client = TestClient(app)

    @classmethod
    def tearDownClass(cls):
        settings.database_path = cls.orig_db_path
        shutil.rmtree(cls.temp_dir, ignore_errors=True)

    # -------------------------------------------------------------------------
    # DEFECT 2: STRICT WARDEN FACILITY SCOPING
    # -------------------------------------------------------------------------

    def test_defect2_warden_cannot_approve_unassigned_student_registration(self):
        """Warden cannot approve an unassigned student registration (HTTP 403)."""
        suffix = secrets.token_hex(4)
        uname = f"unassigned_{suffix}"
        reg_res = self.client.post("/api/v1/auth/register", json={
            "username": uname,
            "email": f"{uname}@univ.edu",
            "password": "Password123!",
            "first_name": "Unassigned",
            "last_name": "Student",
            "phone": f"9{secrets.randbelow(899999999) + 100000000}",
            "gender": "Male",
            "role": "student",
            "enrollment_no": f"ENR-{suffix.upper()}",
            "date_of_birth": "2004-03-15",
            "semester": 2
        })
        self.assertEqual(reg_res.status_code, 201)
        user_id = reg_res.json()["user"]["id"]

        conn = get_db_connection()
        cur = conn.cursor()
        cur.execute("SELECT id FROM registration_requests WHERE user_id = ?;", (user_id,))
        req_id = cur.fetchone()[0]
        conn.close()

        # Warden assigned to Hostel 1 attempts approval -> 403 Forbidden
        warden_user = {"id": 3, "username": "warden", "roles": ["warden"], "linked_hostel_id": 1}
        with self.assertRaises(HTTPException) as ctx:
            AuthService.process_registration_action(
                req_id=req_id,
                action="approve",
                reason="Attempting unauthorized approval",
                current_user=warden_user
            )
        self.assertEqual(ctx.exception.status_code, 403)
        self.assertIn("Unassigned student registrations must be processed by Central Admissions or Administrator", ctx.exception.detail)

        # Central Administrator CAN approve unassigned registrations
        admin_user = {"id": 1, "username": "admin", "roles": ["super_admin"]}
        admin_res = AuthService.process_registration_action(
            req_id=req_id,
            action="approve",
            reason="Approved by Central Administration",
            current_user=admin_user
        )
        self.assertTrue(admin_res["success"])
        self.assertEqual(admin_res["status"], "Approved")

    def test_defect2_warden_cross_hostel_registration_rejection(self):
        """Warden assigned to Hostel 1 cannot approve registration assigned to Hostel 2."""
        conn = get_db_connection()
        try:
            cur = conn.cursor()
            # Seed a student registration for Hostel 2
            suffix = secrets.token_hex(4)
            cur.execute("""
                INSERT INTO users (username, email, password_hash, salt, first_name, last_name, phone, is_active)
                VALUES (?, ?, 'hash', 'salt', 'H2', 'Applicant', '9888812345', 0);
            """, (f"h2_app_{suffix}", f"h2_{suffix}@univ.edu"))
            u_id = cur.lastrowid
            cur.execute("""
                INSERT INTO registration_requests (user_id, username, email, first_name, last_name, requested_role, status, hostel_id)
                VALUES (?, ?, ?, 'H2', 'Applicant', 'student', 'Pending', 2);
            """, (u_id, f"h2_app_{suffix}", f"h2_{suffix}@univ.edu"))
            req_id = cur.lastrowid
            conn.commit()
        finally:
            conn.close()

        warden_h1 = {"id": 3, "username": "warden_h1", "roles": ["warden"], "linked_hostel_id": 1}
        with self.assertRaises(HTTPException) as ctx:
            AuthService.process_registration_action(
                req_id=req_id,
                action="approve",
                reason="Warden H1 cross-facility approval",
                current_user=warden_h1
            )
        self.assertEqual(ctx.exception.status_code, 403)
        self.assertIn("assigned hostel facility", ctx.exception.detail)

    # -------------------------------------------------------------------------
    # DEFECT 3: MULTI-CHILD PARENT APPROVAL ACROSS DIFFERENT HOSTELS
    # -------------------------------------------------------------------------

    def test_defect3_multi_child_parent_approval_workflow(self):
        """Parent with children in different hostels requires independent approvals before account activates."""
        conn = get_db_connection()
        try:
            cur = conn.cursor()

            # Create two students: Student A in Hostel 1, Student B in Hostel 2
            suffix = secrets.token_hex(4)
            cur.execute("""
                INSERT INTO students (student_id, first_name, last_name, email, phone, gender, date_of_birth, branch, academic_year, semester, admission_date, status)
                VALUES (?, 'WardA', 'Multi', ?, '9111111111', 'Male', '2005-01-01', 'CSE', '1st Year', 1, '2026-08-01', 'Active');
            """, (f"STU-WA-{suffix}", f"warda_{suffix}@univ.edu"))
            stu_a_id = cur.lastrowid

            cur.execute("""
                INSERT INTO students (student_id, first_name, last_name, email, phone, gender, date_of_birth, branch, academic_year, semester, admission_date, status)
                VALUES (?, 'WardB', 'Multi', ?, '9222222222', 'Female', '2005-02-02', 'ECE', '2nd Year', 3, '2026-08-01', 'Active');
            """, (f"STU-WB-{suffix}", f"wardb_{suffix}@univ.edu"))
            stu_b_id = cur.lastrowid

            # Allocate Student A to Room in Hostel 1, Student B to Room in Hostel 2
            cur.execute("""
                SELECT b.room_id, b.id FROM beds b
                JOIN rooms rm ON rm.id = b.room_id
                JOIN floors fl ON fl.id = rm.floor_id
                JOIN buildings bld ON bld.id = fl.building_id
                WHERE bld.hostel_id = 1 AND b.id NOT IN (
                    SELECT bed_id FROM room_allocations WHERE allocation_status = 'Active' AND bed_id IS NOT NULL
                ) LIMIT 1;
            """)
            row1 = cur.fetchone()
            r1_id, b1_id = row1[0], row1[1]

            cur.execute("""
                SELECT b.room_id, b.id FROM beds b
                JOIN rooms rm ON rm.id = b.room_id
                JOIN floors fl ON fl.id = rm.floor_id
                JOIN buildings bld ON bld.id = fl.building_id
                WHERE bld.hostel_id = 2 AND b.id NOT IN (
                    SELECT bed_id FROM room_allocations WHERE allocation_status = 'Active' AND bed_id IS NOT NULL
                ) LIMIT 1;
            """)
            row2 = cur.fetchone()
            r2_id, b2_id = row2[0], row2[1]

            cur.execute("""
                INSERT INTO room_allocations (student_id, room_id, bed_id, start_date, end_date, allocation_status, approval_status)
                VALUES (?, ?, ?, '2026-08-01', '2027-05-31', 'Active', 'Approved');
            """, (stu_a_id, r1_id, b1_id))
            cur.execute("""
                INSERT INTO room_allocations (student_id, room_id, bed_id, start_date, end_date, allocation_status, approval_status)
                VALUES (?, ?, ?, '2026-08-01', '2027-05-31', 'Active', 'Approved');
            """, (stu_b_id, r2_id, b2_id))

            # Register Parent user
            p_uname = f"parent_multi_{suffix}"
            cur.execute("""
                INSERT INTO users (username, email, password_hash, salt, first_name, last_name, phone, is_active)
                VALUES (?, ?, 'hash', 'salt', 'Parent', 'MultiWard', '9333333333', 0);
            """, (p_uname, f"{p_uname}@univ.edu"))
            p_user_id = cur.lastrowid

            # Insert Parent registration request with two wards
            cur.execute("""
                INSERT INTO registration_requests (user_id, username, email, first_name, last_name, requested_role, status)
                VALUES (?, ?, ?, 'Parent', 'MultiWard', 'parent_guardian', 'Pending');
            """, (p_user_id, p_uname, f"{p_uname}@univ.edu"))
            p_req_id = cur.lastrowid

            cur.execute("""
                INSERT INTO registration_request_wards (registration_request_id, student_id, relationship, student_approval_status, administrative_approval_status)
                VALUES (?, ?, 'Father', 'Approved', 'Pending');
            """, (p_req_id, stu_a_id))
            cur.execute("""
                INSERT INTO registration_request_wards (registration_request_id, student_id, relationship, student_approval_status, administrative_approval_status)
                VALUES (?, ?, 'Father', 'Approved', 'Pending');
            """, (p_req_id, stu_b_id))
            conn.commit()
        finally:
            conn.close()

        # Warden 1 sees only Ward A
        warden_h1 = {"id": 3, "username": "warden_h1", "roles": ["warden"], "linked_hostel_id": 1}
        pending_h1 = AuthService.get_pending_registrations(warden_h1)
        h1_parent_reqs = [r for r in pending_h1 if r["id"] == p_req_id]
        self.assertEqual(len(h1_parent_reqs), 1)
        wards_seen_h1 = h1_parent_reqs[0].get("wards", [])
        self.assertEqual(len(wards_seen_h1), 1)
        self.assertEqual(wards_seen_h1[0]["student_id"], stu_a_id)

        # Warden 1 approves Ward A
        act1 = AuthService.process_registration_action(
            req_id=p_req_id,
            action="approve",
            reason="Warden 1 verified Ward A",
            current_user=warden_h1
        )
        self.assertTrue(act1["success"])
        # Parent account remains pending because Ward B is not yet approved
        self.assertEqual(act1["status"], "Pending")

        conn = get_db_connection()
        cur = conn.cursor()
        cur.execute("SELECT is_active FROM users WHERE id = ?;", (p_user_id,))
        self.assertEqual(cur.fetchone()[0], 0, "Parent must remain inactive until all wards approved")

        # Warden 2 approves Ward B
        conn = get_db_connection()
        try:
            cur = conn.cursor()
            cur.execute("""
                INSERT OR IGNORE INTO users (id, username, email, password_hash, salt, first_name, last_name, phone, linked_hostel_id, is_active)
                VALUES (105, 'warden_h2', 'warden2@univ.edu', 'hash', 'salt', 'Warden', 'H2', '9888800105', 2, 1);
            """)
            conn.commit()
        finally:
            conn.close()

        warden_h2 = {"id": 105, "username": "warden_h2", "roles": ["warden"], "linked_hostel_id": 2}
        act2 = AuthService.process_registration_action(
            req_id=p_req_id,
            action="approve",
            reason="Warden 2 verified Ward B",
            current_user=warden_h2
        )
        self.assertTrue(act2["success"])
        # All wards approved -> parent account approved and active!
        self.assertEqual(act2["status"], "Approved")

        conn = get_db_connection()
        try:
            cur = conn.cursor()
            cur.execute("SELECT is_active FROM users WHERE id = ?;", (p_user_id,))
            self.assertEqual(cur.fetchone()[0], 1, "Parent must now be active")

            # Verify active links in parent_student_links for BOTH wards
            cur.execute("SELECT student_id, status FROM parent_student_links WHERE parent_user_id = ?;", (p_user_id,))
            links = cur.fetchall()
            self.assertEqual(len(links), 2)
            linked_sids = {r[0] for r in links}
            self.assertIn(stu_a_id, linked_sids)
            self.assertIn(stu_b_id, linked_sids)
            self.assertTrue(all(r[1] == "Active" for r in links))
        finally:
            conn.close()

    # -------------------------------------------------------------------------
    # DEFECT 4: PARENT ACCESS ONLY THROUGH VERIFIED RELATIONSHIPS
    # -------------------------------------------------------------------------

    def test_defect4_parent_access_strict_authorization(self):
        """Parent can only view verified wards from parent_student_links table."""
        conn = get_db_connection()
        try:
            cur = conn.cursor()
            suffix = secrets.token_hex(4)

            cur.execute("""
                INSERT INTO users (username, email, password_hash, salt, first_name, last_name, phone, is_active)
                VALUES (?, ?, 'hash', 'salt', 'Verified', 'Parent', '9444444444', 1);
            """, (f"p_verified_{suffix}", f"p_ver_{suffix}@univ.edu"))
            p_uid = cur.lastrowid

            # Insert student 1000
            cur.execute("""
                INSERT INTO students (student_id, first_name, last_name, email, phone, gender, date_of_birth, branch, academic_year, semester, admission_date, status)
                VALUES (?, 'Verified', 'Child', ?, '9555555555', 'Male', '2005-05-05', 'CSE', '1st Year', 1, '2026-08-01', 'Active');
            """, (f"STU-VER-{suffix}", f"child_{suffix}@univ.edu"))
            stu_id = cur.lastrowid
            conn.commit()

            parent_ctx = {
                "id": p_uid,
                "user_id": p_uid,
                "username": f"p_verified_{suffix}",
                "active_role": "parent_guardian",
                "roles": ["parent_guardian"],
                "linked_student_id": stu_id  # Should NOT be trusted implicitly!
            }

            # 1. Without entry in parent_student_links, access fails
            wards = get_parent_authorized_ward_ids(conn, parent_ctx)
            self.assertNotIn(stu_id, wards)
            with self.assertRaises(HTTPException) as ctx:
                verify_student_isolation(stu_id, parent_ctx)
            self.assertEqual(ctx.exception.status_code, 403)

            # 2. Add Active record into parent_student_links -> access succeeds
            cur.execute("""
                INSERT INTO parent_student_links (parent_user_id, student_id, relationship, status)
                VALUES (?, ?, 'Father', 'Active');
            """, (p_uid, stu_id))
            conn.commit()

            wards_after = get_parent_authorized_ward_ids(conn, parent_ctx)
            self.assertIn(stu_id, wards_after)
            verify_student_isolation(stu_id, parent_ctx)  # Succeeds without exception

            # 3. If status is Revoked -> access revoked
            cur.execute("UPDATE parent_student_links SET status = 'Revoked' WHERE parent_user_id = ?;", (p_uid,))
            conn.commit()
            wards_revoked = get_parent_authorized_ward_ids(conn, parent_ctx)
            self.assertNotIn(stu_id, wards_revoked)
            with self.assertRaises(HTTPException):
                verify_student_isolation(stu_id, parent_ctx)
        finally:
            conn.close()

    # -------------------------------------------------------------------------
    # DEFECT 5: COMPLETE STUDENT REGISTRATION & PROFILE PERSISTENCE
    # -------------------------------------------------------------------------

    def test_defect5_student_dob_and_semester_validation_and_persistence(self):
        """Student date_of_birth and semester are strictly validated and persisted."""
        # 1. Invalid DOB: future date rejected
        with self.assertRaises(Exception):
            RegisterRequest(
                username="future_student",
                email="future@univ.edu",
                password="Password123!",
                first_name="Future",
                last_name="Student",
                role="student",
                date_of_birth="2035-01-01"
            )

        # 2. Invalid DOB: age under 14 rejected
        with self.assertRaises(Exception):
            RegisterRequest(
                username="too_young_student",
                email="young@univ.edu",
                password="Password123!",
                first_name="Young",
                last_name="Student",
                role="student",
                date_of_birth=datetime.now().strftime("%Y-%m-%d")
            )

        # 3. Valid student registration persists dob and semester
        suffix = secrets.token_hex(4)
        uname = f"dob_stu_{suffix}"
        reg_res = self.client.post("/api/v1/auth/register", json={
            "username": uname,
            "email": f"{uname}@univ.edu",
            "password": "Password123!",
            "first_name": "Rohan",
            "last_name": "Bakshi",
            "phone": f"9{secrets.randbelow(899999999) + 100000000}",
            "gender": "Male",
            "role": "student",
            "enrollment_no": f"2410301057-{suffix}",
            "date_of_birth": "2004-11-20",
            "semester": 5
        })
        self.assertEqual(reg_res.status_code, 201)
        user_id = reg_res.json()["user"]["id"]

        conn = get_db_connection()
        try:
            cur = conn.cursor()
            cur.execute("SELECT date_of_birth, semester, academic_year FROM students WHERE user_id = ?;", (user_id,))
            stu_row = cur.fetchone()
            self.assertIsNotNone(stu_row)
            self.assertEqual(stu_row[0], "2004-11-20", "date_of_birth must be persisted correctly")
            self.assertEqual(stu_row[1], 5, "semester must be persisted correctly")
            self.assertEqual(stu_row[2], f"{datetime.now().year}-{datetime.now().year + 1}", "academic_year should be current calendar academic year")
        finally:
            conn.close()

    # -------------------------------------------------------------------------
    # DEFECT 6: REAL NOTIFICATION DELIVERY AND ACCURATE STATUS TRACKING
    # -------------------------------------------------------------------------

    def test_defect6_notification_delivery_logging_and_channel_status(self):
        """Notification dispatches record true delivery states in notification_deliveries."""
        # Enable channels for user 1
        NotificationService.update_preferences(1, NotificationPreferenceDTO(
            in_app_enabled=True, email_enabled=True, browser_enabled=True
        ))

        # Send notification to user 1
        payload = NotificationCreate(
            user_id=1,
            title="TQM SLA Verification Alert",
            message="Curfew verification completed within < 10.0ms SLA",
            category="general",
            priority="Critical",
            notification_type="info",
            delivery_channel="in_app"
        )
        notif_resp = NotificationService.create_notification(payload)
        self.assertIsNotNone(notif_resp)
        notif_id = notif_resp.id

        # Verify delivery records created in notification_deliveries table
        conn = get_db_connection()
        try:
            cur = conn.cursor()
            cur.execute("""
                SELECT channel, delivery_status
                FROM notification_deliveries
                WHERE notification_id = ?;
            """, (notif_id,))
            deliveries = cur.fetchall()
            self.assertGreaterEqual(len(deliveries), 2)
            channel_status_map = {d[0]: d[1] for d in deliveries}

            # in_app is always Sent or Delivered
            self.assertIn(channel_status_map.get("in_app"), ("Sent", "Delivered"))

            # email status must be honest (Sent, Disabled, or Unconfigured_Channel)
            self.assertIn(channel_status_map.get("email"), ("Sent", "Disabled", "Unconfigured_Channel"))

            # browser_push status must be honest
            push_status = channel_status_map.get("browser_push") or channel_status_map.get("web_push")
            self.assertIn(push_status, ("Sent", "Disabled", "Unconfigured_Channel"))
        finally:
            conn.close()

    # -------------------------------------------------------------------------
    # DEFECT 7: MULTI-WORKER SAFE CURFEW MONITORING
    # -------------------------------------------------------------------------

    def test_defect7_curfew_distributed_lease_contention_and_deduplication(self):
        """Curfew monitoring uses distributed lease, updates status atomically, and deduplicates alerts."""
        conn = get_db_connection()
        try:
            cur = conn.cursor()

            # Seed an overdue visitor
            suffix = secrets.token_hex(4)
            cur.execute("""
                INSERT INTO visitors (name, phone, id_proof_type, id_proof_number, address)
                VALUES (?, '9876543210', 'Aadhaar', ?, 'Campus Guest House');
            """, (f"Visitor_{suffix}", f"ID-{suffix}"))
            visitor_id = cur.lastrowid

            past_check_in = (datetime.now() - timedelta(hours=3)).strftime("%Y-%m-%d %H:%M:%S")
            past_curfew = (datetime.now() - timedelta(minutes=30)).strftime("%Y-%m-%d %H:%M:%S")
            pass_no = f"VP-OVERDUE-{suffix}"

            cur.execute("""
                INSERT INTO visitor_logs (pass_number, visitor_id, student_id, hostel_id, room_id, check_in_time, expected_exit_time, purpose, status)
                VALUES (?, ?, 1, 1, 1, ?, ?, 'Parent Visit', 'Checked_In');
            """, (pass_no, visitor_id, past_check_in, past_curfew))
            vlog_id = cur.lastrowid
            conn.commit()
        finally:
            conn.close()

        # 1. Test distributed job lease contention
        conn = get_db_connection()
        try:
            # Worker 1 acquires lease for 60 seconds
            lease1 = VisitorService.acquire_job_lease(conn, "curfew_monitor_test", owner_id="worker_alpha", lease_duration_seconds=60)
            self.assertTrue(lease1, "Worker alpha should acquire available lease")

            # Worker 2 attempts to acquire same lease -> must fail / yield safely
            lease2 = VisitorService.acquire_job_lease(conn, "curfew_monitor_test", owner_id="worker_beta", lease_duration_seconds=60)
            self.assertFalse(lease2, "Worker beta must NOT acquire lease while alpha holds active lease")

            # Worker 1 releases lease
            VisitorService.release_job_lease(conn, "curfew_monitor_test", owner_id="worker_alpha")
        finally:
            conn.close()

        # 2. Run visitor curfew check
        res1 = VisitorService.check_visitor_curfew(worker_id="curfew_worker_1")
        self.assertIn("overdue_count", res1)
        self.assertGreaterEqual(res1["overdue_count"], 1)

        # Verify visitor log status transitioned to 'Overdue' atomically
        conn = get_db_connection()
        try:
            cur = conn.cursor()
            cur.execute("SELECT status FROM visitor_logs WHERE id = ?;", (vlog_id,))
            self.assertEqual(cur.fetchone()[0], "Overdue")

            # Count notifications sent for this overdue pass
            cur.execute("SELECT COUNT(*) FROM notifications WHERE message LIKE ?;", (f"%{pass_no}%",))
            initial_notifs = cur.fetchone()[0]
            self.assertGreaterEqual(initial_notifs, 1)
        finally:
            conn.close()

        # 3. Alert deduplication: Run curfew check second time
        res2 = VisitorService.check_visitor_curfew(worker_id="curfew_worker_2")
        self.assertIn("overdue_count", res2)

        # Notification count must NOT increase (deduplication verified)
        conn = get_db_connection()
        try:
            cur = conn.cursor()
            cur.execute("SELECT COUNT(*) FROM notifications WHERE message LIKE ?;", (f"%{pass_no}%",))
            repeated_notifs = cur.fetchone()[0]
            self.assertEqual(initial_notifs, repeated_notifs, "Curfew monitor must not emit duplicate notifications for same overdue event")
        finally:
            conn.close()


if __name__ == "__main__":
    unittest.main()
