"""Remediation Hardening & Verification Test Suite.

Covers:
1. Active-role authorization enforcement and dual-role context switching
2. Payment verification state machine and RBAC
3. Complaints IDOR and hostel-scoped warden filtering
4. Registration approval lifecycle and pending account lockout
5. Liveness and Readiness probes (/api/health/live, /api/health/ready)
6. reset_db.py production and flag safety guards
"""

import subprocess
import sys
import time
import unittest
from datetime import datetime
from fastapi.testclient import TestClient

from backend.app.database.connection import get_db_connection
from backend.app.database.init_db import initialize_database
from backend.app.main import app
from backend.app.services.auth_service import AuthService
from backend.app.services.security import hash_password


class TestRemediationSecurityHardening(unittest.TestCase):
    """Rigorous verification of comprehensive HMS remediation fixes."""

    @classmethod
    def setUpClass(cls):
        initialize_database()
        cls.client = TestClient(app)

    def setUp(self):
        self.conn = get_db_connection()

    def tearDown(self):
        self.conn.close()

    def _login(self, username: str, password: str = "Password123!") -> dict:
        user_dict = AuthService.authenticate_user(username, password, conn=self.conn)
        tokens = AuthService.issue_token_pair(user_dict, conn=self.conn)
        return {
            "Authorization": f"Bearer {tokens['access_token']}",
            "user": user_dict,
            "token": tokens["access_token"]
        }

    # ==================== 1. ACTIVE-ROLE ENFORCEMENT ====================

    def test_01_active_role_enforcement_dual_role(self):
        """A user holding super_admin role with active_role='student' is constrained to student permissions."""
        cursor = self.conn.cursor()
        cursor.execute("SELECT id FROM users WHERE username = 'dual_test_user';")
        existing = cursor.fetchone()
        if existing:
            uid = existing[0]
            cursor.execute("UPDATE users SET is_active = 1, failed_login_attempts = 0, locked_until = NULL WHERE id = ?;", (uid,))
            self.conn.commit()
        else:
            pwd_hash = hash_password("Password123!")
            cursor.execute("""
                INSERT INTO users (username, email, password_hash, salt, first_name, last_name, is_active)
                VALUES ('dual_test_user', 'dual@univ.edu', ?, '', 'Dual', 'User', 1);
            """, (pwd_hash,))
            uid = cursor.lastrowid
            r_stu = cursor.execute("SELECT id FROM roles WHERE name = 'student';").fetchone()[0]
            r_adm = cursor.execute("SELECT id FROM roles WHERE name = 'super_admin';").fetchone()[0]
            cursor.execute("INSERT OR IGNORE INTO user_roles (user_id, role_id) VALUES (?, ?);", (uid, r_stu))
            cursor.execute("INSERT OR IGNORE INTO user_roles (user_id, role_id) VALUES (?, ?);", (uid, r_adm))
            self.conn.commit()

        # Login with dual-role user
        login_res = self.client.post("/api/v1/auth/login", json={
            "username_or_email": "dual_test_user",
            "password": "Password123!"
        })
        self.assertEqual(login_res.status_code, 200)
        base_token = login_res.json()["access_token"]
        base_headers = {"Authorization": f"Bearer {base_token}"}

        # Explicitly switch active context to 'student'
        switch_stu = self.client.post("/api/v1/auth/switch-role", json={"role": "student"}, headers=base_headers)
        self.assertEqual(switch_stu.status_code, 200)
        stu_token = switch_stu.json()["access_token"]
        stu_headers = {"Authorization": f"Bearer {stu_token}"}

        # Attempt to access super_admin endpoint: GET /api/v1/users
        # Must be strictly 403 Forbidden because active_role is student
        users_res = self.client.get("/api/v1/users", headers=stu_headers)
        self.assertEqual(users_res.status_code, 403)
        self.assertIn("active role", users_res.json()["detail"].lower())

        # Switch active context to 'super_admin'
        switch_adm = self.client.post("/api/v1/auth/switch-role", json={"role": "super_admin"}, headers=stu_headers)
        self.assertEqual(switch_adm.status_code, 200)
        adm_token = switch_adm.json()["access_token"]
        adm_headers = {"Authorization": f"Bearer {adm_token}"}

        # Now GET /api/v1/users must succeed
        users_res2 = self.client.get("/api/v1/users", headers=adm_headers)
        self.assertEqual(users_res2.status_code, 200)

    # ==================== 2. PAYMENT VERIFICATION ====================

    def test_02_payment_verification_rbac_and_reversal(self):
        """Accountant/Admin can verify payments; non-finance roles and reversed payments are rejected."""
        cursor = self.conn.cursor()
        cursor.execute("SELECT id, status FROM payments WHERE status = 'Completed' LIMIT 1;")
        pay_row = cursor.fetchone()
        if not pay_row:
            cursor.execute("""
                INSERT INTO payments (invoice_id, payment_number, amount_paise, payment_method, status, transaction_reference)
                VALUES (1, 'PAY-TEST-001', 500000, 'UPI', 'Completed', 'TXN-999');
            """)
            self.conn.commit()
            pay_id = cursor.lastrowid
        else:
            pay_id = pay_row[0]

        student_auth = self._login("rohan")
        accountant_auth = self._login("accountant")

        # Student attempt to verify payment -> 403
        stu_res = self.client.post(f"/api/v1/fees/payments/{pay_id}/verify", headers={"Authorization": student_auth["Authorization"]})
        self.assertEqual(stu_res.status_code, 403)

        # Accountant verify payment -> 200
        acc_res = self.client.post(f"/api/v1/fees/payments/{pay_id}/verify", headers={"Authorization": accountant_auth["Authorization"]})
        self.assertEqual(acc_res.status_code, 200)
        self.assertEqual(acc_res.json()["status"], "Completed")
        self.assertEqual(acc_res.json()["verification_status"], "Verified")

        # Verify that verifying a reversed payment fails with 400
        cursor.execute("UPDATE payments SET status = 'Reversed' WHERE id = ?;", (pay_id,))
        self.conn.commit()

        fail_res = self.client.post(f"/api/v1/fees/payments/{pay_id}/verify", headers={"Authorization": accountant_auth["Authorization"]})
        self.assertEqual(fail_res.status_code, 400)
        self.assertIn("reversed", fail_res.json()["detail"].lower())

    # ==================== 3. COMPLAINTS IDOR & WARDEN SCOPING ====================

    def test_03_complaints_idor_isolation(self):
        """Student cannot view or comment on another student's complaint."""
        cursor = self.conn.cursor()
        cursor.execute("SELECT id FROM complaints WHERE student_id = 1 LIMIT 1;")
        c_row = cursor.fetchone()
        if not c_row:
            cursor.execute("""
                INSERT INTO complaints (complaint_id, student_id, category, title, description, severity, status)
                VALUES ('CMP-TEST-01', 1, 'Plumbing', 'Leaking tap', 'Water leaking', 'Medium', 'Submitted');
            """)
            self.conn.commit()
            c_id = cursor.lastrowid
        else:
            c_id = c_row[0]

        # Login as student_boy_02 (student_id=2, user_id=21)
        other_student_auth = self._login("student_boy_02")

        # Student 2 accessing Student 1's complaint details -> 403
        view_res = self.client.get(f"/api/v1/complaints/{c_id}", headers={"Authorization": other_student_auth["Authorization"]})
        self.assertEqual(view_res.status_code, 403)

        # Student 2 commenting on Student 1's complaint -> 403
        comment_res = self.client.post(
            f"/api/v1/complaints/{c_id}/comments",
            json={"comment": "Unauthorized comment"},
            headers={"Authorization": other_student_auth["Authorization"]}
        )
        self.assertEqual(comment_res.status_code, 403)

    def test_04_warden_hostel_scoping_for_complaints(self):
        """Warden cannot query complaints belonging to a different hostel facility."""
        # Warden user #3 is assigned to hostel #1 (Tagore Hostel)
        warden_auth = self._login("warden")

        # Querying complaints for hostel #2 (Mother Teresa Girls Hostel) -> 403
        res = self.client.get("/api/v1/complaints?hostel_id=2", headers={"Authorization": warden_auth["Authorization"]})
        self.assertEqual(res.status_code, 403)
        self.assertIn("different hostel", res.json()["detail"].lower())

    # ==================== 4. REGISTRATION APPROVAL SECURITY ====================

    def test_05_pending_registration_lockout(self):
        """Pending student registration cannot log in or acquire tokens until approved."""
        ts = int(time.time() * 1000) % 10000000
        test_uname = f"reg_t_{ts}"
        phone_num = f"91{ts:08d}"[:10]
        reg_payload = {
            "username": test_uname,
            "email": f"{test_uname}@univ.edu",
            "password": "Password123!",
            "first_name": "Test",
            "last_name": "Applicant",
            "phone": phone_num,
            "role": "student",
            "branch": "CSE"
        }
        reg_res = self.client.post("/api/v1/auth/register", json=reg_payload)
        self.assertEqual(reg_res.status_code, 201)
        data = reg_res.json()
        self.assertEqual(data["status"], "Pending_Approval")
        self.assertEqual(data["access_token"], "")
        self.assertTrue(data["requires_approval"])

        # Attempt to log in with the pending credentials -> 403
        login_res = self.client.post("/api/v1/auth/login", json={
            "username_or_email": test_uname,
            "password": "Password123!"
        })
        self.assertEqual(login_res.status_code, 403)
        self.assertIn("pending", login_res.json()["detail"].lower())

    # ==================== 5. HEALTH PROBES ====================

    def test_06_health_liveness_and_readiness(self):
        """Verify /api/health/live and /api/health/ready endpoints."""
        live_res = self.client.get("/api/health/live")
        self.assertEqual(live_res.status_code, 200)
        self.assertEqual(live_res.json()["status"], "alive")

        ready_res = self.client.get("/api/health/ready")
        self.assertEqual(ready_res.status_code, 200)
        self.assertEqual(ready_res.json()["status"], "ready")

        health_res = self.client.get("/api/health")
        self.assertEqual(health_res.status_code, 200)
        self.assertEqual(health_res.json()["status"], "healthy")
        self.assertEqual(health_res.json()["database"]["status"], "connected")

    # ==================== 6. RESET_DB SAFETY GUARD ====================

    def test_07_reset_db_safety_flag_required(self):
        """Executing reset_db.py without --confirm-destructive-reset is blocked."""
        result = subprocess.run(
            [sys.executable, "reset_db.py"],
            capture_output=True,
            text=True
        )
        self.assertEqual(result.returncode, 1)
        self.assertIn("Safety guard triggered", result.stderr)


if __name__ == "__main__":
    unittest.main()
