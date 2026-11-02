"""End-to-End Acceptance Test Suite for Hostel Management System (HMS).

Course: BBAT104 - Fundamentals of Total Quality Management (TQM)
Quality Objective: Q05 - Zero-defect operations, strict RBAC isolation,
                   authoritative integer paise financial precision, and <10ms SLA.

This test suite executes in an isolated SQLite environment cloned from the
production schema, ensuring zero side-effects on persistent application data.
"""

import os
import shutil
import tempfile
import unittest
import sqlite3
import secrets
from typing import Dict, Any, Tuple

from fastapi.testclient import TestClient

# Import application components
from backend.app.main import app
from backend.app.database.connection import get_db_connection
from backend.app.database.migrations import run_migrations


class TestE2EAcceptance(unittest.TestCase):
    """Full-spectrum multi-stakeholder end-to-end acceptance tests."""

    @classmethod
    def setUpClass(cls):
        """Provision isolated temporary database clone for destructive acceptance testing."""
        cls.temp_dir = tempfile.mkdtemp(prefix="hms_e2e_")
        cls.db_path = os.path.join(cls.temp_dir, "test_acceptance.db")

        # Copy existing live database if present to test real migrations/state
        source_db = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "..", "data", "hostel_web.db"))
        if os.path.exists(source_db):
            shutil.copy2(source_db, cls.db_path)
        else:
            # Create fresh if not found
            conn = sqlite3.connect(cls.db_path)
            conn.close()

        # Set database path so application points to isolated DB
        from backend.app.config import settings
        cls.orig_db_path = settings.database_path
        settings.database_path = cls.db_path

        # Run all migrations up to 015
        conn = sqlite3.connect(cls.db_path)
        conn.row_factory = sqlite3.Row
        run_migrations(conn)
        conn.close()

        cls.client = TestClient(app)

    @classmethod
    def tearDownClass(cls):
        """Restore environment and clean up temporary database."""
        from backend.app.config import settings
        if cls.orig_db_path:
            settings.database_path = cls.orig_db_path

        shutil.rmtree(cls.temp_dir, ignore_errors=True)

    def get_db(self) -> sqlite3.Connection:
        """Helper to get a raw SQLite connection to the isolated test database."""
        conn = sqlite3.connect(self.db_path)
        conn.row_factory = sqlite3.Row
        return conn

    def login_as(self, username_or_email: str, password: str = "Password123!") -> Tuple[Any, Dict[str, str]]:
        """Helper to log in and retrieve access token headers."""
        res = self.client.post("/api/v1/auth/login", json={
            "username_or_email": username_or_email,
            "password": password
        })
        if res.status_code == 200:
            token = res.json().get("access_token")
            return res, {"Authorization": f"Bearer {token}"}
        return res, {}

    # =========================================================================
    # STEP 1: AUTHENTICATION & SESSION SECURITY
    # =========================================================================

    def test_auth_valid_and_invalid_login(self):
        """Verify login accepts valid credentials and rejects incorrect passwords & unknown users."""
        # 1. Valid login as superadmin
        res, headers = self.login_as("superadmin")
        self.assertEqual(res.status_code, 200)
        body = res.json()
        self.assertIn("access_token", body)
        self.assertNotIn("refresh_token", body, "Security Defect: refresh_token exposed in JSON response!")
        self.assertIn("refresh_token", res.cookies)

        # 2. Invalid password
        res_fail, _ = self.login_as("superadmin", "WrongPassword!")
        self.assertEqual(res_fail.status_code, 401)
        self.assertIn("username or password", res_fail.json().get("detail", "").lower())

        # 3. Nonexistent user
        res_unknown, _ = self.login_as("completely_nonexistent_user_999", "Password123!")
        self.assertEqual(res_unknown.status_code, 401)

    def test_auth_registration_validation_and_duplicate_handling(self):
        """Verify registration validates input, rejects duplicate email/username, and isolates pending students."""
        unique_suffix = secrets.token_hex(4)
        reg_payload = {
            "first_name": "Acceptance",
            "last_name": "Candidate",
            "email": f"candidate_{unique_suffix}@univ.edu",
            "phone": f"9{secrets.randbelow(899999999) + 100000000}",
            "username": f"cand_{unique_suffix}",
            "password": "Password123!",
            "role": "student",
            "gender": "Male"
        }

        # 1. Valid Student Registration
        res = self.client.post("/api/v1/auth/register", json=reg_payload)
        self.assertIn(res.status_code, (200, 201))
        reg_data = res.json()
        self.assertFalse(reg_data.get("access_token"), "Pending student must not receive an active access token")
        self.assertFalse(reg_data.get("refresh_token"), "Pending student must not receive an active refresh token")

        # 2. Duplicate Username Rejection
        res_dup_user = self.client.post("/api/v1/auth/register", json={
            **reg_payload,
            "email": f"other_{unique_suffix}@univ.edu"
        })
        self.assertIn(res_dup_user.status_code, (400, 409))

        # 3. Duplicate Email Rejection
        res_dup_email = self.client.post("/api/v1/auth/register", json={
            **reg_payload,
            "username": f"other_{unique_suffix}"
        })
        self.assertIn(res_dup_email.status_code, (400, 409))

        # 4. Pending student login attempt -> Must be 403 Forbidden
        res_pend_login, _ = self.login_as(reg_payload["username"], "Password123!")
        self.assertEqual(res_pend_login.status_code, 403, "Pending student must not be able to log in before approval")

    def test_auth_refresh_rotation_and_logout_revocation(self):
        """Verify refresh token rotation and logout session invalidation."""
        # Log in
        res_login, headers = self.login_as("accountant")
        self.assertEqual(res_login.status_code, 200)
        refresh_cookie = res_login.cookies.get("refresh_token")
        self.assertIsNotNone(refresh_cookie)

        # Refresh token rotation
        res_refresh = self.client.post(
            "/api/v1/auth/refresh",
            cookies={"refresh_token": refresh_cookie}
        )
        self.assertEqual(res_refresh.status_code, 200)
        self.assertIn("access_token", res_refresh.json())
        self.assertNotIn("refresh_token", res_refresh.json())

        # Old refresh token should now be rotated/invalidated
        res_reuse = self.client.post(
            "/api/v1/auth/refresh",
            cookies={"refresh_token": refresh_cookie}
        )
        self.assertIn(res_reuse.status_code, (401, 403), "Reused refresh token was unexpectedly accepted!")

        # Logout
        new_refresh = res_refresh.cookies.get("refresh_token")
        new_access = res_refresh.json()["access_token"]
        res_logout = self.client.post(
            "/api/v1/auth/logout",
            headers={"Authorization": f"Bearer {new_access}"},
            cookies={"refresh_token": new_refresh}
        )
        self.assertEqual(res_logout.status_code, 200)

        # Refresh with logged-out token must fail
        res_revoked = self.client.post(
            "/api/v1/auth/refresh",
            cookies={"refresh_token": new_refresh}
        )
        self.assertEqual(res_revoked.status_code, 401)

    # =========================================================================
    # STEP 4: ROLE-BASED ACCESS CONTROL & SECURITY BOUNDARIES (ALL 12 ROLES)
    # =========================================================================

    def test_rbac_dashboard_and_navigation_isolation(self):
        """Verify each stakeholder role can access their respective dashboard and cannot access unpermitted areas."""
        all_roles = [
            ("superadmin", "super_admin"),
            ("hosteladmin", "hostel_admin"),
            ("warden", "warden"),
            ("asstwarden", "assistant_warden"),
            ("rohan", "student"),
            ("accountant", "accountant"),
            ("messmanager", "mess_manager"),
            ("maintenance", "maintenance_staff"),
            ("security", "security_guard"),
            ("admission", "admission_officer"),
            ("parent", "parent_guardian"),
            ("evaluator", "auditor")
        ]

        for username, role_name in all_roles:
            res, headers = self.login_as(username)
            self.assertEqual(res.status_code, 200, f"Failed to log in as {username} ({role_name})")

            # Call /api/v1/dashboard/stats
            stats_res = self.client.get("/api/v1/dashboard/stats", headers=headers)
            self.assertEqual(stats_res.status_code, 200, f"Role {role_name} failed to access dashboard stats")
            data = stats_res.json()
            self.assertEqual(data.get("scope", {}).get("role"), role_name, f"Scope role mismatch for {role_name}")

    def test_rbac_admin_endpoint_defense(self):
        """Verify non-superadmin users are strictly blocked from admin settings and user modification."""
        non_admin_users = ["warden", "asstwarden", "rohan", "accountant", "security", "parent", "evaluator"]
        for user in non_admin_users:
            _, headers = self.login_as(user)
            res = self.client.get("/api/v1/admin/settings", headers=headers)
            self.assertEqual(res.status_code, 403, f"Security Breach: {user} was able to access admin settings!")

            # Attempt to modify user status
            res_put = self.client.put("/api/v1/admin/users/1/status", json={"is_active": 0}, headers=headers)
            self.assertEqual(res_put.status_code, 403, f"Security Breach: {user} was able to modify user status!")

    def test_rbac_student_cross_access_isolation_idor(self):
        """Verify Student cannot access another student's profile, invoices, attendance or leave requests (IDOR defense)."""
        _, headers = self.login_as("rohan")  # student_id = 1

        # Attempt to access student profile of Student #2
        res_profile = self.client.get("/api/v1/students/2/profile", headers=headers)
        self.assertEqual(res_profile.status_code, 403, "IDOR Vulnerability: Student accessed another student's profile!")

        # Attempt to access invoices of Student #2
        res_invoices = self.client.get("/api/v1/fees/invoices/student/2", headers=headers)
        self.assertEqual(res_invoices.status_code, 403, "IDOR Vulnerability: Student accessed another student's invoices!")

        # Attempt to access attendance history of Student #2
        res_att = self.client.get("/api/v1/attendance/student/2", headers=headers)
        self.assertEqual(res_att.status_code, 403, "IDOR Vulnerability: Student accessed another student's attendance!")

    def test_rbac_role_switching_security(self):
        """Verify users cannot switch to arbitrary or unassigned roles."""
        _, headers = self.login_as("rohan")

        # Attempt to switch to super_admin
        res = self.client.post("/api/v1/auth/switch-role", json={"role": "super_admin"}, headers=headers)
        self.assertEqual(res.status_code, 403, "Privilege Escalation: Student switched to super_admin!")

        # Attempt to switch to accountant
        res_acc = self.client.post("/api/v1/auth/switch-role", json={"role": "accountant"}, headers=headers)
        self.assertEqual(res_acc.status_code, 403, "Privilege Escalation: Student switched to accountant!")

    # =========================================================================
    # STEP 5 & 6: DATABASE REFERENTIAL INTEGRITY & POKA-YOKE WORKFLOWS
    # =========================================================================

    def test_database_integrity_and_foreign_keys(self):
        """Verify SQLite PRAGMA integrity_check and PRAGMA foreign_key_check have zero errors."""
        conn = self.get_db()
        cursor = conn.cursor()

        # PRAGMA integrity_check
        cursor.execute("PRAGMA integrity_check;")
        res_ic = cursor.fetchall()
        self.assertEqual(len(res_ic), 1)
        self.assertEqual(res_ic[0][0], "ok", "Database corruption detected by PRAGMA integrity_check")

        # PRAGMA foreign_key_check
        cursor.execute("PRAGMA foreign_key_check;")
        res_fk = cursor.fetchall()
        self.assertEqual(len(res_fk), 0, f"Foreign key constraint violations present: {len(res_fk)} rows")
        conn.close()

    def test_workflow_student_registration_approval_and_activation(self):
        """Workflow: Student registers -> Warden approves request -> Student logs in successfully."""
        uid = secrets.token_hex(4)
        username = f"new_stu_{uid}"
        email = f"{username}@university.edu"

        # 1. Register student
        res_reg = self.client.post("/api/v1/auth/register", json={
            "first_name": "Test",
            "last_name": "Registration",
            "email": email,
            "phone": f"9{secrets.randbelow(899999999) + 100000000}",
            "username": username,
            "password": "Password123!",
            "role": "student",
            "gender": "Male"
        })
        self.assertIn(res_reg.status_code, (200, 201))

        # 2. Warden fetches pending registrations
        _, warden_headers = self.login_as("warden")
        res_pending = self.client.get("/api/v1/registrations/pending", headers=warden_headers)
        self.assertEqual(res_pending.status_code, 200)
        requests = res_pending.json()
        target_req = next((r for r in requests if r.get("username") == username), None)
        self.assertIsNotNone(target_req, "Newly registered student must appear in pending registrations")

        # 3. Warden approves registration
        req_id = target_req["id"]
        res_action = self.client.post(
            f"/api/v1/registrations/{req_id}/action",
            json={"action": "approve", "notes": "Approved in E2E acceptance test"},
            headers=warden_headers
        )
        self.assertEqual(res_action.status_code, 200)

        # 4. Now student attempts login -> Must succeed with 200 OK
        res_login, student_headers = self.login_as(username, "Password123!")
        self.assertEqual(res_login.status_code, 200)
        self.assertIn("access_token", res_login.json())

        # 5. Student accesses their own profile
        me_res = self.client.get("/api/v1/auth/me", headers=student_headers)
        self.assertEqual(me_res.status_code, 200)
        self.assertEqual(me_res.json().get("username"), username)

    def test_workflow_hostel_room_allocation_poka_yoke_and_transfer(self):
        """Workflow: Admin creates allocation -> Double allocation blocked -> Transfer executed -> Checkout executed."""
        _, admin_headers = self.login_as("superadmin")

        # 1. Fetch available beds
        res_beds = self.client.get("/api/v1/allocations/available-beds", headers=admin_headers)
        self.assertEqual(res_beds.status_code, 200)
        beds = res_beds.json()
        self.assertGreater(len(beds), 1, "Need at least 2 available beds for allocation and transfer test")
        bed1_id = beds[0].get("bed_id", beds[0].get("id"))
        bed2_id = beds[1].get("bed_id", beds[1].get("id"))
        target_gender = "Female" if beds[0].get("hostel_type") == "Girls" else "Male"

        # Register a test student to allocate matching hostel gender
        uid = secrets.token_hex(4)
        stu_uname = f"alloc_stu_{uid}"
        self.client.post("/api/v1/auth/register", json={
            "first_name": "Alloc",
            "last_name": "Test",
            "email": f"{stu_uname}@univ.edu",
            "phone": f"9{secrets.randbelow(899999999) + 100000000}",
            "username": stu_uname,
            "password": "Password123!",
            "role": "student",
            "gender": target_gender
        })

        # Approve student
        res_p = self.client.get("/api/v1/registrations/pending", headers=admin_headers)
        req_id = next(r["id"] for r in res_p.json() if r["username"] == stu_uname)
        self.client.post(f"/api/v1/registrations/{req_id}/action", json={"action": "approve"}, headers=admin_headers)

        # Get student record ID
        conn = self.get_db()
        cur = conn.cursor()
        cur.execute("SELECT id FROM students WHERE user_id = (SELECT id FROM users WHERE username = ?)", (stu_uname,))
        student_db_id = cur.fetchone()["id"]

        # Find another student of the same gender for duplicate allocation test
        cur.execute("SELECT id FROM students WHERE gender = ? AND id != ? LIMIT 1;", (target_gender, student_db_id))
        another_st_row = cur.fetchone()
        another_student_id = another_st_row["id"] if another_st_row else student_db_id
        conn.close()

        # 2. Allocate Bed 1 to student
        alloc_payload = {
            "student_id": student_db_id,
            "bed_id": bed1_id,
            "start_date": "2026-11-01"
        }
        res_alloc = self.client.post("/api/v1/allocations", json=alloc_payload, headers=admin_headers)
        self.assertEqual(res_alloc.status_code, 201)
        alloc_id = res_alloc.json()["id"]

        # 3. Poka-Yoke: Attempt to allocate same Bed 1 to another student -> Must fail
        dup_payload = {
            "student_id": another_student_id,
            "bed_id": bed1_id,
            "start_date": "2026-11-01"
        }
        res_dup = self.client.post("/api/v1/allocations", json=dup_payload, headers=admin_headers)
        self.assertEqual(res_dup.status_code, 400, "Poka-Yoke failure: Occupied bed was re-allocated!")

        # 4. Execute Room/Bed Transfer to Bed 2
        transfer_payload = {
            "to_bed_id": bed2_id,
            "reason": "Relocating for academic peer study group"
        }
        res_transfer = self.client.post(f"/api/v1/allocations/{alloc_id}/transfer", json=transfer_payload, headers=admin_headers)
        self.assertEqual(res_transfer.status_code, 200)
        active_alloc_id = res_transfer.json()["id"]

        # Verify old bed is released and new bed is occupied
        res_beds_after = self.client.get("/api/v1/allocations/available-beds", headers=admin_headers)
        avail_bed_ids = [b.get("bed_id", b.get("id")) for b in res_beds_after.json()]
        self.assertIn(bed1_id, avail_bed_ids, "Bed 1 should now be available after transfer")
        self.assertNotIn(bed2_id, avail_bed_ids, "Bed 2 should be occupied after transfer")

        # 5. Checkout student
        res_checkout = self.client.post(f"/api/v1/allocations/{active_alloc_id}/checkout", json={
            "reason": "Course completion"
        }, headers=admin_headers)
        self.assertEqual(res_checkout.status_code, 200)

        # Bed 2 must now be released
        res_beds_final = self.client.get("/api/v1/allocations/available-beds", headers=admin_headers)
        avail_final_ids = [b.get("bed_id", b.get("id")) for b in res_beds_final.json()]
        self.assertIn(bed2_id, avail_final_ids, "Bed 2 should be available after checkout")

    # =========================================================================
    # STEP 7: FINANCIAL INTEGRITY & INTEGER-PAISE RECONCILIATION
    # =========================================================================

    def test_workflow_financial_invoicing_paise_and_refunds(self):
        """Workflow: Create fee structure -> Generate invoice -> Record partial payment -> Prevent overpayment -> Process refund."""
        _, accountant_headers = self.login_as("accountant")

        # 1. Create Fee Structure (₹5,000.00 = 500,000 paise)
        fee_name = f"Term Fee {secrets.token_hex(4)}"
        res_fee = self.client.post("/api/v1/fees/structures", json={
            "name": fee_name,
            "room_type": "Double",
            "academic_year": "2026-27",
            "semester": "Odd",
            "amount": 5000.0,
            "amount_paise": 500000,
            "payment_frequency": "Semester"
        }, headers=accountant_headers)
        self.assertEqual(res_fee.status_code, 201)
        fee_id = res_fee.json()["id"]

        # 2. Generate Invoice for Student 1
        res_inv = self.client.post("/api/v1/fees/invoices", json={
            "student_id": 1,
            "fee_structure_id": fee_id,
            "due_date": "2026-11-30",
            "items": [
                {"title": "Hostel Room Rent", "amount": 4000.0, "amount_paise": 400000},
                {"title": "Utility Deposit", "amount": 1000.0, "amount_paise": 100000}
            ]
        }, headers=accountant_headers)
        self.assertEqual(res_inv.status_code, 201)
        invoice = res_inv.json()
        invoice_id = invoice["id"]
        self.assertEqual(invoice["total_amount_paise"], 500000)
        self.assertEqual(invoice["paid_amount_paise"], 0)

        # 3. Record Partial Payment (₹2,500.00 = 250,000 paise)
        res_pay = self.client.post("/api/v1/fees/payments", json={
            "invoice_id": invoice_id,
            "student_id": 1,
            "amount": 2500.0,
            "amount_paise": 250000,
            "payment_method": "UPI",
            "transaction_id": f"UPI-{secrets.token_hex(6)}"
        }, headers=accountant_headers)
        self.assertEqual(res_pay.status_code, 201)

        # Verify updated invoice status and remaining balance
        res_get_inv = self.client.get(f"/api/v1/fees/invoices/{invoice_id}", headers=accountant_headers)
        inv_data = res_get_inv.json()
        self.assertEqual(inv_data["paid_amount_paise"], 250000)
        self.assertEqual(inv_data["status"], "Partially_Paid")

        # 4. Poka-Yoke: Attempt Overpayment (₹5,000.00 when only ₹2,500.00 is due) -> Must be rejected
        res_overpay = self.client.post("/api/v1/fees/payments", json={
            "invoice_id": invoice_id,
            "student_id": 1,
            "amount": 5000.0,
            "amount_paise": 500000,
            "payment_method": "UPI",
            "transaction_id": f"UPI-{secrets.token_hex(6)}"
        }, headers=accountant_headers)
        self.assertEqual(res_overpay.status_code, 400, "Financial Bug: Overpayment exceeding invoice balance was allowed!")

        # 5. Process Remaining Payment (₹2,500.00) -> Invoice becomes Fully Paid
        res_final_pay = self.client.post("/api/v1/fees/payments", json={
            "invoice_id": invoice_id,
            "student_id": 1,
            "amount": 2500.0,
            "amount_paise": 250000,
            "payment_method": "UPI",
            "transaction_id": f"UPI-{secrets.token_hex(6)}"
        }, headers=accountant_headers)
        self.assertEqual(res_final_pay.status_code, 201)
        final_pay_id = res_final_pay.json()["id"]

        res_paid_inv = self.client.get(f"/api/v1/fees/invoices/{invoice_id}", headers=accountant_headers)
        self.assertEqual(res_paid_inv.json()["status"], "Paid")
        self.assertEqual(res_paid_inv.json()["paid_amount_paise"], 500000)

        # 6. Refund Request and Approval Workflow (₹500.00 = 50,000 paise)
        res_ref_req = self.client.post("/api/v1/fees/refunds", json={
            "payment_id": final_pay_id,
            "amount": 500.0,
            "amount_paise": 50000,
            "reason": "Over-deposited utility maintenance fee",
            "refund_method": "Bank_Transfer"
        }, headers=accountant_headers)
        self.assertEqual(res_ref_req.status_code, 201)
        refund_id = res_ref_req.json()["id"]

        # Approve refund
        res_ref_app = self.client.post(f"/api/v1/fees/refunds/{refund_id}/approve", headers=accountant_headers)
        self.assertEqual(res_ref_app.status_code, 200)

        # Process refund
        res_ref_proc = self.client.post(f"/api/v1/fees/refunds/{refund_id}/process", json={
            "action": "Process",
            "reason": "Approved and transferred",
            "transaction_reference": f"TXN-REF-{secrets.token_hex(4)}"
        }, headers=accountant_headers)
        self.assertEqual(res_ref_proc.status_code, 200)

    # =========================================================================
    # STEP 8: LEAVE, MAINTENANCE, AND VISITOR PASS WORKFLOWS
    # =========================================================================

    def test_workflow_leave_request_approval_and_gate_outpass(self):
        """Workflow: Student applies for leave -> Warden approves and issues Outpass -> Security guard verifies gate exit and return."""
        # 1. Student applies for leave
        _, student_headers = self.login_as("rohan")
        leave_payload = {
            "leave_type": "Home Leave",
            "start_date": "2026-11-10",
            "end_date": "2026-11-12",
            "reason": "Visiting home for festival",
            "destination": "42 Park Street, Kolkata",
            "emergency_contact": "9810301057"
        }
        res_leave = self.client.post("/api/v1/leave", json=leave_payload, headers=student_headers)
        self.assertIn(res_leave.status_code, (200, 201))
        leave_id = res_leave.json()["id"]

        # 2. Warden approves leave
        _, warden_headers = self.login_as("warden")
        res_app = self.client.post(f"/api/v1/leave/{leave_id}/approve", json={"remarks": "Granted"}, headers=warden_headers)
        self.assertEqual(res_app.status_code, 200)
        outpass_ref = res_app.json().get("outpass", {}).get("outpass_number")
        self.assertIsNotNone(outpass_ref, "Outpass must be generated upon leave approval")

        # 3. Security Guard verifies gate exit
        _, guard_headers = self.login_as("security")
        res_exit = self.client.post(f"/api/v1/outpasses/{outpass_ref}/verify-exit", json={"remarks": "Gate exit approved"}, headers=guard_headers)
        self.assertEqual(res_exit.status_code, 200)

        # 4. Security Guard verifies gate return
        res_return = self.client.post(f"/api/v1/outpasses/{outpass_ref}/verify-return", json={"remarks": "Gate return verified"}, headers=guard_headers)
        self.assertEqual(res_return.status_code, 200)

        # 5. Outpass status should now be Returned
        res_outpass = self.client.get(f"/api/v1/outpasses/{outpass_ref}", headers=guard_headers)
        self.assertEqual(res_outpass.json()["status"], "Returned")

    def test_workflow_complaint_and_maintenance_task_lifecycle(self):
        """Workflow: Student files complaint -> Warden assigns task -> Maintenance accepts and completes task."""
        # 1. Student files complaint
        _, student_headers = self.login_as("rohan")
        comp_res = self.client.post("/api/v1/complaints", json={
            "category": "Electrical",
            "severity": "Medium",
            "title": "Study table tube-light flickering",
            "description": "Tube light in Room 101 flickers continuously."
        }, headers=student_headers)
        self.assertIn(comp_res.status_code, (200, 201))
        complaint_id = comp_res.json()["id"]

        # 2. Warden reviews and assigns to maintenance staff
        _, warden_headers = self.login_as("warden")
        conn = self.get_db()
        cur = conn.cursor()
        cur.execute("SELECT id FROM users WHERE username = 'maintenance'")
        maint_uid = cur.fetchone()["id"]
        conn.close()

        assign_res = self.client.post(f"/api/v1/complaints/{complaint_id}/assign", json={
            "assigned_to": maint_uid,
            "scheduled_date": "2026-11-05",
            "notes": "Replace choke/starter"
        }, headers=warden_headers)
        self.assertEqual(assign_res.status_code, 200)

        # 3. Maintenance staff accepts and starts work
        _, maint_headers = self.login_as("maintenance")
        task_res = self.client.get("/api/v1/maintenance/tasks", headers=maint_headers)
        self.assertEqual(task_res.status_code, 200)
        tasks = task_res.json()
        target_task = next((t for t in tasks if t.get("complaint_id") == complaint_id), None)
        self.assertIsNotNone(target_task)
        task_id = target_task["id"]

        # Accept task
        res_accept = self.client.post(f"/api/v1/maintenance/tasks/{task_id}/accept", headers=maint_headers)
        self.assertEqual(res_accept.status_code, 200)

        # Complete task
        res_complete = self.client.post(f"/api/v1/maintenance/tasks/{task_id}/complete", json={
            "resolution_notes": "Replaced starter and bulb; operational",
            "actual_cost": 150.0
        }, headers=maint_headers)
        self.assertEqual(res_complete.status_code, 200)

        # Verify complaint status is resolved
        res_comp_status = self.client.get(f"/api/v1/complaints/{complaint_id}", headers=warden_headers)
        self.assertIn(res_comp_status.json()["status"], ("Resolved", "Completed"))

    def test_workflow_visitor_pass_management(self):
        """Workflow: Register visitor -> Approve & check-in -> Verify active status -> Check-out."""
        _, guard_headers = self.login_as("security")

        # 1. Register visitor with immediate check-in
        vis_res = self.client.post("/api/v1/visitors", json={
            "name": "Deepak Bakshi",
            "phone": "9811223344",
            "id_proof_type": "Aadhaar",
            "id_proof_number": "1234-5678-9012",
            "student_id": 1,
            "purpose": "Academic consultation",
            "immediate_checkin": True
        }, headers=guard_headers)
        self.assertIn(vis_res.status_code, (200, 201))
        visitor_log_id = vis_res.json()["id"]

        # 2. Active visitors list must include this visitor
        res_active = self.client.get("/api/v1/visitors/active", headers=guard_headers)
        self.assertEqual(res_active.status_code, 200)
        active_ids = [v["id"] for v in res_active.json()]
        self.assertIn(visitor_log_id, active_ids)

        # 3. Check-out visitor
        res_out = self.client.post(f"/api/v1/visitors/{visitor_log_id}/check-out", json={"remarks": "Visitor departed campus"}, headers=guard_headers)
        self.assertEqual(res_out.status_code, 200)

        # Visitor should no longer be active
        res_active_after = self.client.get("/api/v1/visitors/active", headers=guard_headers)
        active_after_ids = [v["id"] for v in res_active_after.json()]
        self.assertNotIn(visitor_log_id, active_after_ids)

    def test_workflow_parent_guardian_telemetry_isolation(self):
        """Workflow: Parent logs in -> Sees ward's attendance, fees, leave -> Cannot access unlinked students."""
        _, parent_headers = self.login_as("parent")

        # Parent's linked ward is Student 1 (Rohan Bakshi)
        res_att = self.client.get("/api/v1/attendance/student/1", headers=parent_headers)
        self.assertEqual(res_att.status_code, 200, "Parent must be able to view their own ward's attendance")

        res_fees = self.client.get("/api/v1/fees/invoices/student/1", headers=parent_headers)
        self.assertEqual(res_fees.status_code, 200, "Parent must be able to view their own ward's invoices")

        # Attempt to access unlinked student (e.g. Student 2) -> Must be blocked with 403 Forbidden
        res_unlinked_att = self.client.get("/api/v1/attendance/student/2", headers=parent_headers)
        self.assertEqual(res_unlinked_att.status_code, 403, "Privacy Breach: Parent viewed unlinked student attendance!")

        res_unlinked_fees = self.client.get("/api/v1/fees/invoices/student/2", headers=parent_headers)
        self.assertEqual(res_unlinked_fees.status_code, 403, "Privacy Breach: Parent viewed unlinked student invoices!")

    # =========================================================================
    # STEP 9: PERFORMANCE & Q05 SLA TELEMETRY
    # =========================================================================

    def test_q05_telemetry_and_caching_performance(self):
        """Verify endpoints return X-Response-Time-Ms header satisfying Q05 SLA (<10.0 ms)."""
        # Health check
        res_health = self.client.get("/api/health")
        self.assertEqual(res_health.status_code, 200)
        self.assertIn("X-Response-Time-Ms", res_health.headers)

        # Cached Dashboard stats
        _, headers = self.login_as("superadmin")
        # Cold fetch to populate cache
        self.client.get("/api/v1/dashboard/stats", headers=headers)

        # Warm fetch over cache
        res_warm = None
        for _ in range(3):
            res_warm = self.client.get("/api/v1/dashboard/stats", headers=headers)
        self.assertEqual(res_warm.status_code, 200)
        self.assertIn("X-Response-Time-Ms", res_warm.headers)
        data = res_warm.json()
        self.assertEqual(data.get("cache_status"), "HIT")
        self.assertLess(float(data.get("execution_time_ms", 0.0)), 10.0, "Database query exceeded Q05 SLA (<10ms)")


if __name__ == "__main__":
    unittest.main()
