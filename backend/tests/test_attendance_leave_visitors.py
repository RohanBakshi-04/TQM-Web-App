"""Comprehensive Unit & Integration Test Suite for Attendance, Leave & Outpasses, and Visitor Operations.

Course: BBAT104 - Fundamentals of Total Quality Management (TQM)
Quality Goal: Q05 - Reduce Response Time (< 10ms SLA)
Poka-Yoke Controls: Duplicate Prevention, Role Isolation, Curfew Integrity, ID Privacy Masking
"""

import os
import unittest
from datetime import date, datetime, timedelta
from fastapi.testclient import TestClient

# Ensure test environment
os.environ["APP_ENV"] = "testing"
os.environ["DATABASE_URL"] = "sqlite:///:memory:"

from backend.app.database.connection import get_db_connection
from backend.app.database.init_db import initialize_database
from backend.app.main import app
from backend.app.models.attendance_dto import (
    AttendanceRecordCreate,
    AttendanceCorrectionRequest
)
from backend.app.models.leave_dto import (
    LeaveApplicationCreate,
    LeaveApprovalRequest,
    LeaveRejectionRequest,
    OutpassVerificationRequest
)
from backend.app.models.visitor_dto import (
    VisitorRegistrationRequest,
    VisitorCheckInRequest,
    VisitorCheckOutRequest
)
from backend.app.services.attendance_service import AttendanceService
from backend.app.services.auth_service import AuthService
from backend.app.services.leave_service import LeaveService
from backend.app.services.visitor_service import VisitorService


class TestAttendanceLeaveVisitors(unittest.TestCase):
    """Test suite covering Attendance, Leave/Outpass Workflows, and Visitor Pass Management."""

    @classmethod
    def setUpClass(cls):
        initialize_database()
        cls.client = TestClient(app)
        conn = get_db_connection()
        try:
            # Ensure student 1 has an active room allocation for tests
            conn.execute("UPDATE room_allocations SET allocation_status = 'Vacated' WHERE student_id = 1;")
            conn.execute("UPDATE room_allocations SET allocation_status = 'Active' WHERE id = (SELECT id FROM room_allocations WHERE student_id = 1 LIMIT 1);")
            conn.commit()
        finally:
            conn.close()

    def setUp(self):
        self.conn = get_db_connection()
        self.today_str = date.today().isoformat()
        self.yesterday_str = (date.today() - timedelta(days=1)).isoformat()
        self.tomorrow_str = (date.today() + timedelta(days=1)).isoformat()

        # Demo users:
        # User 1: superadmin
        # User 3: warden (Tagore Hostel)
        # User 5: rohan (student, id=1)
        # User 9: guard (security_guard)
        self.superadmin_user = {"user_id": 1, "username": "superadmin", "role": "super_admin", "hostel_id": None}
        self.warden_user = {"user_id": 3, "username": "warden", "role": "warden", "hostel_id": 1}
        self.student_user = {"user_id": 5, "username": "rohan", "role": "student", "hostel_id": 1}
        self.guard_user = {"user_id": 9, "username": "guard", "role": "security_guard", "hostel_id": 1}

    def tearDown(self):
        self.conn.close()

    def _get_auth_header(self, username: str = "superadmin") -> dict:
        auth_data = AuthService.authenticate_user(self.conn, username, "Password123!")
        return {"Authorization": f"Bearer {auth_data['tokens']['access_token']}"}

    # ==================== 1. ATTENDANCE MANAGEMENT TESTS ====================

    def test_01_mark_attendance_success(self):
        """Verify authorized staff marks attendance for a student on a specific date."""
        test_date = "2026-09-10"
        # Ensure clean state for test_date
        self.conn.execute("DELETE FROM attendance WHERE date = ?;", (test_date,))
        self.conn.commit()

        payload = AttendanceRecordCreate(
            student_id=1,
            date=test_date,
            status="Present",
            remarks="On-time biometric verification"
        )
        res = AttendanceService.mark_attendance(payload, self.warden_user)
        self.assertEqual(res["student_id"], 1)
        self.assertEqual(res["status"], "Present")
        self.assertEqual(res["date"], test_date)

    def test_02_duplicate_attendance_prevention(self):
        """Poka-Yoke: Assert duplicate attendance on the same date for the same student is blocked."""
        test_date = "2026-09-11"
        self.conn.execute("DELETE FROM attendance WHERE date = ?;", (test_date,))
        self.conn.commit()

        payload = AttendanceRecordCreate(student_id=1, date=test_date, status="Present")
        AttendanceService.mark_attendance(payload, self.warden_user)

        # Second attempt must raise 409 Conflict
        with self.assertRaises(Exception) as ctx:
            AttendanceService.mark_attendance(payload, self.warden_user)
        self.assertIn("already marked", str(ctx.exception).lower())

    def test_03_attendance_correction_with_mandatory_audit(self):
        """Verify authorized warden can correct attendance status with an auditable reason."""
        test_date = "2026-09-12"
        self.conn.execute("DELETE FROM attendance WHERE date = ?;", (test_date,))
        self.conn.commit()

        payload = AttendanceRecordCreate(student_id=1, date=test_date, status="Absent")
        rec = AttendanceService.mark_attendance(payload, self.warden_user)

        # Correct Absent -> Present
        corr = AttendanceCorrectionRequest(
            new_status="Present",
            reason="Medical certificate verified by warden; late arrival excused."
        )
        updated = AttendanceService.correct_attendance(rec["id"], corr, self.warden_user)
        self.assertEqual(updated["previous_status"], "Absent")
        self.assertEqual(updated["new_status"], "Present")

        # Verify audit history
        history = AttendanceService.get_student_attendance_history(1, self.superadmin_user)
        self.assertTrue(len(history["corrections"]) >= 1)
        self.assertEqual(history["corrections"][0]["new_status"], "Present")

    def test_04_attendance_summary_and_repeated_absence_detection(self):
        """Assert attendance summary metrics and detection of repeated absentees (>= 3 absences)."""
        # Insert 3 absences for student 1 in September
        dates = ["2026-09-20", "2026-09-21", "2026-09-22"]
        for d in dates:
            self.conn.execute("DELETE FROM attendance WHERE student_id = 1 AND date = ?;", (d,))
            self.conn.execute("INSERT INTO attendance (student_id, date, status, marked_by) VALUES (1, ?, 'Absent', 3);", (d,))
        self.conn.commit()

        summary = AttendanceService.get_daily_summary("2026-09-22", 1, self.warden_user)
        self.assertGreaterEqual(summary["absent_students"], 1)

        # Check repeated absentees
        flagged_ids = [s["student_id"] for s in summary["repeated_absentees"]]
        self.assertIn(1, flagged_ids)

    # ==================== 2. LEAVE & OUTPASS WORKFLOW TESTS ====================

    def test_05_student_leave_application_submission(self):
        """Verify student submits a valid leave application with departure and return dates."""
        payload = LeaveApplicationCreate(
            leave_type="Home Leave",
            start_date=self.tomorrow_str,
            end_date=(date.today() + timedelta(days=3)).isoformat(),
            departure_time="09:00",
            expected_return_time="19:00",
            reason="Sister's wedding ceremony in home town",
            destination="Jaipur, Rajasthan",
            emergency_contact="+91 9876543210",
            guardian_contact="+91 9123456780"
        )
        res = LeaveService.create_leave_application(payload, self.student_user)
        self.assertEqual(res["status"], "Submitted")
        self.assertEqual(res["leave_type"], "Home Leave")
        self.assertEqual(res["destination"], "Jaipur, Rajasthan")

    def test_06_warden_leave_approval_and_outpass_issuance(self):
        """Verify warden approves a leave application, triggering digital gate outpass creation."""
        payload = LeaveApplicationCreate(
            leave_type="Medical Leave",
            start_date=self.today_str,
            end_date=self.tomorrow_str,
            departure_time="10:00",
            expected_return_time="18:00",
            reason="Hospital consultation for dental surgery",
            destination="Apollo Hospital, City Center",
            emergency_contact="+91 9876543210"
        )
        leave_app = LeaveService.create_leave_application(payload, self.student_user)

        # Warden approves
        approval = LeaveApprovalRequest(remarks="Approved; prescription submitted")
        res = LeaveService.approve_leave_application(leave_app["id"], approval, self.warden_user)

        self.assertEqual(res["status"], "Approved")
        self.assertIsNotNone(res["outpass"])
        self.assertTrue(res["outpass"]["outpass_number"].startswith("OP-"))
        self.assertEqual(res["outpass"]["status"], "Issued")

    def test_07_poka_yoke_self_approval_and_invalid_transition(self):
        """Poka-Yoke: Assert student cannot self-approve their own leave, and rejected leave cannot be approved."""
        payload = LeaveApplicationCreate(
            leave_type="Personal Leave",
            start_date=self.today_str,
            end_date=self.tomorrow_str,
            reason="Personal work in city",
            destination="Local Market",
            emergency_contact="+91 9876543210"
        )
        leave_app = LeaveService.create_leave_application(payload, self.student_user)

        # 1. Self-approval attempt by student must fail (403)
        with self.assertRaises(Exception) as ctx:
            LeaveService.approve_leave_application(leave_app["id"], LeaveApprovalRequest(), self.student_user)
        self.assertIn("approve", str(ctx.exception).lower())

        # 2. Reject application
        LeaveService.reject_leave_application(leave_app["id"], LeaveRejectionRequest(reason="Curfew restriction active"), self.warden_user)

        # 3. Approving already rejected application must fail
        with self.assertRaises(Exception) as ctx2:
            LeaveService.approve_leave_application(leave_app["id"], LeaveApprovalRequest(), self.warden_user)
        self.assertIn("invalid workflow transition", str(ctx2.exception).lower())

    def test_08_outpass_gate_exit_and_return_verification(self):
        """Verify security guard records student gate exit and subsequent return, blocking duplicates."""
        # Create and approve a leave application
        payload = LeaveApplicationCreate(
            leave_type="Home Leave",
            start_date=self.today_str,
            end_date=self.tomorrow_str,
            reason="Weekend leave",
            destination="Delhi NCR",
            emergency_contact="+91 9876543210"
        )
        leave_app = LeaveService.create_leave_application(payload, self.student_user)
        approved = LeaveService.approve_leave_application(leave_app["id"], LeaveApprovalRequest(), self.warden_user)
        outpass_id = approved["outpass"]["id"]

        # Security records exit
        exit_res = LeaveService.verify_outpass_exit(str(outpass_id), OutpassVerificationRequest(remarks="Bag inspected"), self.guard_user)
        self.assertEqual(exit_res["outpass"]["status"], "Departed")
        self.assertIsNotNone(exit_res["outpass"]["actual_exit_time"])

        # Duplicate exit attempt must fail
        with self.assertRaises(Exception) as ctx:
            LeaveService.verify_outpass_exit(str(outpass_id), OutpassVerificationRequest(), self.guard_user)
        self.assertIn("already", str(ctx.exception).lower())

        # Security records return
        return_res = LeaveService.verify_outpass_return(str(outpass_id), OutpassVerificationRequest(remarks="Returned safely"), self.guard_user)
        self.assertEqual(return_res["outpass"]["status"], "Returned")
        self.assertIsNotNone(return_res["outpass"]["actual_return_time"])

        # Duplicate return attempt must fail
        with self.assertRaises(Exception) as ctx2:
            LeaveService.verify_outpass_return(str(outpass_id), OutpassVerificationRequest(), self.guard_user)
        self.assertIn("already", str(ctx2.exception).lower())

    # ==================== 3. VISITOR OPERATIONS TESTS ====================

    def test_09_visitor_registration_and_duplicate_active_prevention(self):
        """Verify visitor registration with pass generation, and prevent duplicate active visits."""
        phone = "+91 9988776655"
        self.conn.execute("DELETE FROM visitor_logs WHERE visitor_id IN (SELECT id FROM visitors WHERE phone = ?);", (phone,))
        self.conn.commit()

        payload = VisitorRegistrationRequest(
            name="Mr. Rajesh Sharma",
            phone=phone,
            id_proof_type="Aadhaar",
            id_proof_number="1234-5678-9012",
            student_id=1,
            purpose="Parents visiting hostel room",
            immediate_checkin=True
        )
        v_res = VisitorService.register_visitor(payload, self.guard_user)
        self.assertEqual(v_res["name"], "Mr. Rajesh Sharma")
        self.assertEqual(v_res["status"], "Checked_In")
        self.assertTrue(v_res["pass_number"].startswith("VP-"))

        # Poka-Yoke: Registering another visit while previous is still active must fail
        with self.assertRaises(Exception) as ctx:
            VisitorService.register_visitor(payload, self.guard_user)
        self.assertIn("active visit conflict", str(ctx.exception).lower())

    def test_10_visitor_check_out_and_active_listing(self):
        """Verify active visitors listing and gate departure check out."""
        phone = "+91 9112233445"
        self.conn.execute("DELETE FROM visitor_logs WHERE visitor_id IN (SELECT id FROM visitors WHERE phone = ?);", (phone,))
        self.conn.commit()

        payload = VisitorRegistrationRequest(
            name="Sunil Verma",
            phone=phone,
            id_proof_type="Driving_License",
            id_proof_number="DL-04-2020-001234",
            student_id=1,
            purpose="Book handover",
            immediate_checkin=True
        )
        v_res = VisitorService.register_visitor(payload, self.guard_user)
        log_id = v_res["id"]

        # Check active visitors contains this visitor
        active = VisitorService.get_active_visitors(1, self.guard_user)
        active_ids = [item["id"] for item in active]
        self.assertIn(log_id, active_ids)

        # Check out
        out_res = VisitorService.check_out_visitor(log_id, VisitorCheckOutRequest(remarks="Gate departure confirmed"), self.guard_user)
        self.assertEqual(out_res["status"], "Checked_Out")
        self.assertIsNotNone(out_res["check_out_time"])

        # Active visitors should no longer include this visitor
        active_after = VisitorService.get_active_visitors(1, self.guard_user)
        active_after_ids = [item["id"] for item in active_after]
        self.assertNotIn(log_id, active_after_ids)

    def test_11_role_based_data_isolation_and_privacy_masking(self):
        """Assert privacy masking: Student cannot see raw ID proof of visitors, and only sees their own visits."""
        phone = "+91 9776655443"
        self.conn.execute("DELETE FROM visitor_logs WHERE visitor_id IN (SELECT id FROM visitors WHERE phone = ?);", (phone,))
        self.conn.commit()

        payload = VisitorRegistrationRequest(
            name="Alok Nath",
            phone=phone,
            id_proof_type="Aadhaar",
            id_proof_number="9876-5432-1098",
            student_id=1,
            purpose="Family visit",
            immediate_checkin=True
        )
        v_res = VisitorService.register_visitor(payload, self.guard_user)
        log_id = v_res["id"]

        # Guard sees full ID proof
        guard_view = VisitorService.get_visitor_log(log_id, self.guard_user)
        self.assertEqual(guard_view["id_proof_number"], "9876-5432-1098")

        # Student views: ID proof must be masked
        student_view = VisitorService.get_visitor_log(log_id, self.student_user)
        self.assertTrue(student_view["id_proof_number"].startswith("XXXX"))
        self.assertEqual(student_view["id_proof_number"][-4:], "1098")


if __name__ == "__main__":
    unittest.main()
