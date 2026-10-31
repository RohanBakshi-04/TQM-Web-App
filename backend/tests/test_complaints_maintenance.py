"""Comprehensive Unit and Integration Test Suite for Complaints and Maintenance Lifecycle.

Course: BBAT104 - Fundamentals of Total Quality Management (TQM)
Quality Goal: Q05 - Reduce Response Time (<10ms SLA)
Defect Prevention: Poka-Yoke Automated Work-Order Lifecycle & Room Maintenance Constraints
"""

import os
import unittest
from fastapi.testclient import TestClient

# Ensure test environment
os.environ["APP_ENV"] = "testing"
os.environ["DATABASE_URL"] = "sqlite:///:memory:"

from backend.app.database.connection import get_db_connection
from backend.app.database.init_db import initialize_database
from backend.app.main import app
from backend.app.models.complaint_dto import (
    ComplaintAssign,
    ComplaintClose,
    ComplaintCreate,
    ComplaintEscalate,
    ComplaintFeedback,
    ComplaintReject,
    ComplaintReopen,
)
from backend.app.models.maintenance_dto import (
    MaintenanceTaskComplete,
    MaintenanceTaskCreate,
    MaintenanceTaskHold,
    MaintenanceTaskProgress,
    MaintenanceTaskVerify,
)
from backend.app.services.auth_service import AuthService
from backend.app.services.complaint_service import ComplaintService
from backend.app.services.maintenance_service import MaintenanceService


class TestComplaintsAndMaintenance(unittest.TestCase):
    """Test suite covering Student Complaints, Maintenance Work-Orders, Poka-Yoke Locks, and State Transitions."""

    @classmethod
    def setUpClass(cls):
        initialize_database()
        cls.client = TestClient(app)

    def setUp(self):
        self.conn = get_db_connection()
        cursor = self.conn.cursor()
        cursor.execute("UPDATE maintenance_tasks SET status = 'Cancelled' WHERE status IN ('Open', 'Assigned', 'Accepted', 'In Progress', 'On Hold');")
        cursor.execute("UPDATE rooms SET status = 'Available' WHERE status = 'Maintenance';")
        cursor.execute("UPDATE beds SET status = 'Available' WHERE status = 'Maintenance';")
        self.conn.commit()

    def tearDown(self):
        self.conn.close()

    def _get_auth_header(self, username: str = "rohan") -> dict:
        auth_data = AuthService.authenticate_user(self.conn, username, "Password123!")
        return {"Authorization": f"Bearer {auth_data['tokens']['access_token']}"}

    def test_01_student_complaint_submission_success(self):
        """Verify student can submit a valid grievance and initial state is 'Submitted'."""
        data = ComplaintCreate(
            category="Electrical",
            title="Geyser power trip in bathroom",
            description="The geyser switch sparks and trips the main MCB breaker.",
            severity="High",
            attachment_url="https://example.com/geyser.jpg"
        )
        res = ComplaintService.submit_complaint(
            conn=self.conn,
            student_id=1,
            data=data,
            submitted_by_user_id=5  # Student Rohan user ID
        )

        self.assertIn("complaint_id", res)
        self.assertTrue(res["complaint_id"].startswith("CMP-"))
        self.assertEqual(res["status"], "Submitted")
        self.assertEqual(res["category"], "Electrical")
        self.assertEqual(res["severity"], "High")
        self.assertEqual(len(res["updates"]), 1)
        self.assertEqual(res["updates"][0]["new_status"], "Submitted")

    def test_02_complaint_invalid_category_or_severity(self):
        """Verify invalid category or severity is rejected with HTTP 400."""
        from fastapi import HTTPException
        # Invalid Category
        bad_data = ComplaintCreate(
            category="Astronomy",
            title="Telescope not working",
            description="Telescope lens cracked.",
            severity="Medium"
        )
        with self.assertRaises(HTTPException) as ctx:
            ComplaintService.submit_complaint(self.conn, 1, bad_data)
        self.assertEqual(ctx.exception.status_code, 400)
        self.assertIn("Invalid complaint category", ctx.exception.detail)

        # Invalid Severity
        bad_sev = ComplaintCreate(
            category="Plumbing",
            title="Pipe leak",
            description="Water is dripping under the basin.",
            severity="Catastrophic"
        )
        with self.assertRaises(HTTPException) as ctx:
            ComplaintService.submit_complaint(self.conn, 1, bad_sev)
        self.assertEqual(ctx.exception.status_code, 400)
        self.assertIn("Invalid complaint severity", ctx.exception.detail)

    def test_03_student_data_isolation(self):
        """Verify Student A cannot inspect or comment on Student B's private grievance."""
        from fastapi import HTTPException

        # Student 1 submits complaint
        data = ComplaintCreate(
            category="Plumbing",
            title="Sink clogged",
            description="Sink drain is backed up.",
            severity="Low"
        )
        complaint = ComplaintService.submit_complaint(self.conn, student_id=1, data=data, submitted_by_user_id=5)

        # Student 2 tries to read it
        with self.assertRaises(HTTPException) as ctx:
            ComplaintService.get_complaint_by_id(self.conn, complaint["id"], student_id_restriction=2)
        self.assertEqual(ctx.exception.status_code, 403)
        self.assertIn("Access Denied", ctx.exception.detail)

        # Student 2 tries to add comment
        with self.assertRaises(HTTPException) as ctx:
            ComplaintService.add_comment(self.conn, complaint["id"], user_id=6, comment="Spying", student_id_restriction=2)
        self.assertEqual(ctx.exception.status_code, 403)

    def test_04_warden_assignment_and_work_order_generation(self):
        """Verify Warden assigning a complaint creates an active maintenance work-order."""
        data = ComplaintCreate(
            category="Carpentry",
            title="Wardrobe door hinge broken",
            description="Wardrobe door will not close securely.",
            severity="Medium"
        )
        complaint = ComplaintService.submit_complaint(self.conn, student_id=1, data=data, submitted_by_user_id=5)

        # Maintenance worker user ID 8 (maintenance)
        assign_data = ComplaintAssign(
            assigned_to=8,
            priority="Medium",
            deadline="2026-11-15",
            internal_remarks="Replace with heavy-duty 4-inch steel hinge."
        )

        res = ComplaintService.assign_complaint(self.conn, complaint["id"], user_id=3, data=assign_data)
        self.assertEqual(res["status"], "Assigned")
        self.assertEqual(res["assigned_to"], 8)
        self.assertIsNotNone(res["maintenance_task"])
        self.assertTrue(res["maintenance_task"]["task_code"].startswith("MT-"))
        self.assertEqual(res["maintenance_task"]["status"], "Assigned")

    def test_05_maintenance_worker_task_lifecycle(self):
        """Verify worker accepts, starts, holds, and completes maintenance task with cost & photo."""
        # Create standalone task
        task_data = MaintenanceTaskCreate(
            title="Corridor Light Tube Replacement",
            description="Replace burned out LED tube in Floor 2 corridor.",
            priority="Low",
            assigned_to=8,
            estimated_cost=250.0
        )
        task = MaintenanceService.create_maintenance_task(self.conn, task_data, created_by_user_id=3)
        task_id = task["id"]
        self.assertEqual(task["status"], "Assigned")

        # 1. Accept
        accepted = MaintenanceService.accept_task(self.conn, task_id, worker_user_id=8)
        self.assertEqual(accepted["status"], "Accepted")

        # 2. Start
        started = MaintenanceService.start_task(self.conn, task_id, worker_user_id=8)
        self.assertEqual(started["status"], "In Progress")

        # 3. Progress note
        prog = MaintenanceService.update_task_progress(self.conn, task_id, worker_user_id=8, data=MaintenanceTaskProgress(notes="Tested wiring; voltage normal."))
        self.assertEqual(len(prog["history"]), 4)

        # 4. Hold
        held = MaintenanceService.hold_task(self.conn, task_id, worker_user_id=8, data=MaintenanceTaskHold(hold_reason="Store room locked; awaiting spare tube."))
        self.assertEqual(held["status"], "On Hold")
        self.assertEqual(held["hold_reason"], "Store room locked; awaiting spare tube.")

        # 5. Resume
        resumed = MaintenanceService.start_task(self.conn, task_id, worker_user_id=8)
        self.assertEqual(resumed["status"], "In Progress")

        # 6. Complete
        completed = MaintenanceService.complete_task(
            self.conn,
            task_id,
            worker_user_id=8,
            data=MaintenanceTaskComplete(
                resolution_notes="Installed 20W Philips LED batten.",
                actual_cost=220.0,
                completion_photo_url="https://example.com/repair-complete.jpg"
            )
        )
        self.assertEqual(completed["status"], "Completed")
        self.assertEqual(completed["actual_cost"], 220.0)
        self.assertIsNotNone(completed["completed_at"])

        # 7. Warden Verifies
        verified = MaintenanceService.verify_task(
            self.conn,
            task_id,
            verified_by_user_id=3,
            data=MaintenanceTaskVerify(approved=True, verification_notes="Illumination meets 200 lux standard.")
        )
        self.assertEqual(verified["status"], "Verified")
        self.assertEqual(verified["verified_by"], 3)

    def test_06_complaint_state_machine_illegal_skip_prevention(self):
        """Poka-Yoke: Verify illegal workflow state transitions are rejected with HTTP 400."""
        from fastapi import HTTPException

        data = ComplaintCreate(
            category="Wi-Fi and Internet",
            title="Router reboot required",
            description="Packet loss on 5GHz band.",
            severity="Low"
        )
        c = ComplaintService.submit_complaint(self.conn, student_id=1, data=data, submitted_by_user_id=5)

        # Illegal skip: Attempting to close a 'Submitted' complaint directly
        with self.assertRaises(HTTPException) as ctx:
            ComplaintService.close_complaint(self.conn, c["id"], user_id=3)
        self.assertEqual(ctx.exception.status_code, 400)
        self.assertIn("Poka-Yoke Workflow Violation", ctx.exception.detail)

        # Illegal skip: Attempting to give feedback before resolution
        with self.assertRaises(HTTPException) as ctx:
            ComplaintService.submit_feedback(self.conn, c["id"], student_id=1, data=ComplaintFeedback(rating=5))
        self.assertEqual(ctx.exception.status_code, 400)
        self.assertIn("Feedback can only be provided after complaint resolution", ctx.exception.detail)

    def test_07_complaint_rejection_and_reopening(self):
        """Verify Warden rejecting a complaint with reason, and student reopening resolved complaints."""
        # 1. Rejection
        data1 = ComplaintCreate(
            category="Other",
            title="Private sound system installation",
            description="Want institutional permission to wire 5.1 speakers.",
            severity="Low"
        )
        c1 = ComplaintService.submit_complaint(self.conn, student_id=1, data=data1, submitted_by_user_id=5)

        rejected = ComplaintService.reject_complaint(self.conn, c1["id"], user_id=3, reason="Violates hostel sound pollution policy.")
        self.assertEqual(rejected["status"], "Rejected")
        self.assertEqual(rejected["rejection_reason"], "Violates hostel sound pollution policy.")

        # 2. Reopening a Resolved complaint
        data2 = ComplaintCreate(
            category="Plumbing",
            title="Water leakage under sink",
            description="P-trap joint is dripping slowly.",
            severity="Medium"
        )
        c2 = ComplaintService.submit_complaint(self.conn, student_id=1, data=data2, submitted_by_user_id=5)
        # Advance to Resolved
        assign_res = ComplaintService.assign_complaint(self.conn, c2["id"], user_id=3, data=ComplaintAssign(assigned_to=8))
        task_id = assign_res["maintenance_task"]["id"]
        MaintenanceService.accept_task(self.conn, task_id, 8)
        MaintenanceService.complete_task(self.conn, task_id, 8, MaintenanceTaskComplete(resolution_notes="Tightened joint."))

        reopened = ComplaintService.reopen_complaint(self.conn, c2["id"], student_id=1, data=ComplaintReopen(reason="Joint started dripping again after 1 hour."), user_id=5)
        self.assertEqual(reopened["status"], "Reopened")
        self.assertEqual(reopened["reopened_count"], 1)

    def test_08_poka_yoke_room_maintenance_lock_and_allocation_blocking(self):
        """Poka-Yoke: Critical maintenance task sets room to 'Maintenance' and blocks student allocation."""
        from fastapi import HTTPException
        from backend.app.models.allocation_dto import AllocationCreate
        from backend.app.services.allocation_service import AllocationService

        # Assign task affecting occupancy on Room 2
        cursor = self.conn.cursor()
        cursor.execute("UPDATE rooms SET status = 'Available' WHERE id = 2;")
        cursor.execute("UPDATE beds SET status = 'Available' WHERE room_id = 2;")
        self.conn.commit()

        # Ensure a test unallocated male student exists
        test_student = cursor.execute("SELECT id FROM students WHERE student_id = 'TEST-ALLOC-MALE';").fetchone()
        if not test_student:
            cursor.execute("""
                INSERT INTO students (student_id, first_name, last_name, email, phone, gender, branch, academic_year, semester, admission_date, status)
                VALUES ('TEST-ALLOC-MALE', 'Vikram', 'Mehta', 'vikram@example.com', '9876543299', 'Male', 'Mechanical', '2026-27', 1, '2026-08-01', 'Active');
            """)
            test_stu_id = cursor.lastrowid
        else:
            test_stu_id = test_student[0]
            cursor.execute("DELETE FROM room_allocations WHERE student_id = ?;", (test_stu_id,))

        task_data = MaintenanceTaskCreate(
            room_id=2,
            title="Emergency Ceiling Plaster Repair",
            description="Loose plaster hanging over beds; hazardous until scraped and cured.",
            priority="Critical",
            assigned_to=8,
            affects_occupancy=True
        )
        task = MaintenanceService.create_maintenance_task(self.conn, task_data, created_by_user_id=3)

        # Verify Room 2 is now under Maintenance
        r_status = cursor.execute("SELECT status FROM rooms WHERE id = 2;").fetchone()[0]
        self.assertEqual(r_status, "Maintenance")

        # Attempt to allocate Bed 3 (inside Room 2) to Vikram
        alloc_data = AllocationCreate(
            student_id=test_stu_id,
            bed_id=3,
            start_date="2026-11-01",
            end_date="2027-05-31"
        )
        with self.assertRaises(HTTPException) as ctx:
            AllocationService.create_allocation(self.conn, alloc_data, allocated_by_user_id=3)
        self.assertEqual(ctx.exception.status_code, 400)
        self.assertIn("under Maintenance", ctx.exception.detail)

        # Complete and Verify the maintenance task
        MaintenanceService.accept_task(self.conn, task["id"], 8)
        MaintenanceService.complete_task(self.conn, task["id"], 8, MaintenanceTaskComplete(resolution_notes="Plaster cured and repainted."))
        MaintenanceService.verify_task(self.conn, task["id"], 3, MaintenanceTaskVerify(approved=True, verification_notes="Safe for student habitation."))

        # Verify Room 2 is restored to Available
        r_restored = cursor.execute("SELECT status FROM rooms WHERE id = 2;").fetchone()[0]
        self.assertEqual(r_restored, "Available")

    def test_09_complaint_escalation(self):
        """Verify escalation marks grievance as escalated and logs justification."""
        data = ComplaintCreate(
            category="Security",
            title="Unauthorized person spotted near emergency exit",
            description="Side fire exit latch was found tampered with.",
            severity="High"
        )
        c = ComplaintService.submit_complaint(self.conn, student_id=1, data=data, submitted_by_user_id=5)

        esc = ComplaintService.escalate_complaint(self.conn, c["id"], user_id=3, reason="Safety perimeter compromise requiring immediate guard deployment.")
        self.assertEqual(esc["escalated"], 1)
        self.assertEqual(esc["escalation_reason"], "Safety perimeter compromise requiring immediate guard deployment.")
        self.assertIsNotNone(esc["escalated_at"])

    def test_10_staff_availability_matrix(self):
        """Verify staff availability matrix counts active and completed tasks per worker."""
        staff = MaintenanceService.get_staff_availability(self.conn)
        self.assertIsInstance(staff, list)
        self.assertGreater(len(staff), 0)
        worker = staff[0]
        self.assertIn("active_task_count", worker)
        self.assertIn("is_available", worker)
        self.assertIn("workload_level", worker)


if __name__ == "__main__":
    unittest.main()
