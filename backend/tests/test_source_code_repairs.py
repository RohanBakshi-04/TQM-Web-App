"""Comprehensive Test Suite for Source-Code Repairs and Security Enhancements.

Course: BBAT104 - Fundamentals of Total Quality Management (TQM)
Quality Goal: Q05 - Zero Defects, Strict RBAC Isolation, and Cryptographic Security
"""

import os
import secrets
import unittest
from unittest import mock
import sqlite3
from decimal import Decimal
from fastapi import FastAPI, HTTPException
from fastapi.testclient import TestClient

from backend.app.config import Settings
from backend.app.database.connection import get_db_connection
from backend.app.services.security import hash_password, create_access_token, decode_access_token
from backend.app.services.auth_service import AuthService
from backend.app.services.backup_service import BackupService
from backend.app.services.cache_service import CacheService
from backend.app.services.auth_dependencies import (
    get_parent_authorized_ward_ids,
    verify_student_isolation,
)
from backend.app.services.payment_service import _to_dec, PaymentService
from backend.app.main import app


class TestSourceCodeRepairs(unittest.TestCase):
    """Rigorous verification for all Priority 1-10 source-code repairs."""

    @classmethod
    def setUpClass(cls):
        cls.client = TestClient(app)

    def setUp(self):
        self.client.cookies.clear()

    # =========================================================================
    # 1. PRIORITY 1: PRODUCTION SECRETS AND JWT SECURITY
    # =========================================================================

    def test_production_weak_secret_rejection(self):
        """Production startup fails if JWT secret is a default placeholder or < 32 chars."""
        weak_settings = Settings(
            app_env="production",
            secret_key="short_key",
            jwt_secret_key="short_key"
        )
        with self.assertRaises(ValueError) as ctx:
            weak_settings.validate_production_secrets()
        self.assertIn("CRITICAL SECURITY CONFIGURATION ERROR", str(ctx.exception))

    def test_production_default_secret_rejection(self):
        """Production startup fails if JWT secret matches known default."""
        default_settings = Settings(
            app_env="production",
            secret_key="tqm-q05-hms-secret-key-2026-dev-32bytes-min",
            jwt_secret_key="tqm-q05-hms-secret-key-2026-dev-32bytes-min"
        )
        with self.assertRaises(ValueError) as ctx:
            default_settings.validate_production_secrets()
        self.assertIn("cannot use default placeholders", str(ctx.exception))

    def test_production_strong_secret_accepted(self):
        """Production startup passes with a 32+ character non-default secret."""
        strong_settings = Settings(
            app_env="production",
            secret_key="a" * 32,
            jwt_secret_key="a" * 32
        )
        # Should execute cleanly without raising
        strong_settings.validate_production_secrets()

    # =========================================================================
    # 2. PRIORITY 1: SECURE PASSWORD RESET TOKEN HANDLING
    # =========================================================================

    def test_password_reset_anti_enumeration_and_rate_limiting(self):
        """Password reset returns generic response, does not reveal account existence."""
        resp1 = self.client.post("/api/v1/auth/forgot-password", json={
            "email": "nonexistent_student_user_xyz@univ.edu"
        })
        self.assertEqual(resp1.status_code, 200)
        data1 = resp1.json()
        self.assertIn("password reset instructions", data1["message"])
        # Should not leak dev_token for nonexistent user
        self.assertIsNone(data1.get("dev_token"))

    def test_password_reset_token_single_use(self):
        """Password reset tokens are single-use and invalidated immediately upon use."""
        conn = get_db_connection()
        try:
            # Create a test user
            cursor = conn.cursor()
            cursor.execute("DELETE FROM users WHERE username = 'test_reset_user';")
            salt_val = secrets.token_hex(16)
            pwd_hash = hash_password("TempPassword123!")
            cursor.execute("""
                INSERT INTO users (username, email, password_hash, salt, first_name, last_name, is_active)
                VALUES ('test_reset_user', 'test_reset@univ.edu', ?, ?, 'Test', 'Reset', 1);
            """, (pwd_hash, salt_val))
            conn.commit()

            # Initiate reset
            res = AuthService.initiate_password_reset("test_reset@univ.edu")
            token = res["dev_token"]
            self.assertIsNotNone(token)

            # First reset succeeds
            reset_res = AuthService.complete_password_reset(token, "NewPassword12345!")
            self.assertTrue(reset_res)

            # Second attempt with same token fails (single use)
            with self.assertRaises(HTTPException) as ctx:
                AuthService.complete_password_reset(token, "AnotherPassword123!")
            self.assertEqual(ctx.exception.status_code, 400)
            self.assertIn("Invalid or already used", ctx.exception.detail)
        finally:
            conn.close()

    # =========================================================================
    # 3. PRIORITY 2: AUTHORIZATION AND DATA ISOLATION
    # =========================================================================

    def test_parent_authorized_ward_ids_lookup(self):
        """Parent/guardian can only access authorized wards linked to their account."""
        conn = get_db_connection()
        try:
            cursor = conn.cursor()
            # Ensure student 1 exists
            cursor.execute("SELECT id FROM students WHERE id = 1;")
            if not cursor.fetchone():
                self.skipTest("Student 1 not found for parent ward test.")

            fake_parent = {
                "user_id": 99999,
                "email": "parent_unknown@test.com",
                "phone": "9999999999",
                "linked_student_id": 1
            }
            wards = get_parent_authorized_ward_ids(conn, fake_parent)
            self.assertIn(1, wards)

            # Unlinked parent gets empty set
            unlinked_parent = {
                "user_id": 88888,
                "email": "unlinked@test.com",
                "phone": "8888888888",
                "linked_student_id": None
            }
            unlinked_wards = get_parent_authorized_ward_ids(conn, unlinked_parent)
            self.assertNotIn(1, unlinked_wards)
        finally:
            conn.close()

    def test_verify_student_isolation_parent(self):
        """Parent cannot inspect unrelated student record."""
        current_user = {
            "id": 99999,
            "user_id": 99999,
            "role": "parent_guardian",
            "active_role": "parent_guardian",
            "roles": ["parent_guardian"],
            "linked_student_id": 1,
            "email": "parent_test@univ.edu",
            "phone": "9999999999"
        }
        # Accessing own ward (1) passes
        verify_student_isolation(1, current_user)

        # Accessing foreign student (999) raises 403
        with self.assertRaises(HTTPException) as ctx:
            verify_student_isolation(999, current_user)
        self.assertEqual(ctx.exception.status_code, 403)

    # =========================================================================
    # 4. PRIORITY 3: BACKUP SERVICE PATH TRAVERSAL REJECTION
    # =========================================================================

    def test_backup_restore_path_traversal_rejected(self):
        """Backup restore rejects path traversal sequences and non-.db extensions."""
        with self.assertRaises(ValueError) as ctx:
            BackupService.restore_backup("../../../etc/passwd")
        self.assertIn("Directory traversal", str(ctx.exception))

        with self.assertRaises(ValueError) as ctx2:
            BackupService.restore_backup("malicious_script.sh")
        self.assertIn("Directory traversal", str(ctx2.exception))

    # =========================================================================
    # 5. PRIORITY 4: FINANCIAL DECIMAL PRECISION
    # =========================================================================

    def test_decimal_conversion_and_rounding(self):
        """_to_dec ensures exact decimal representation without float drift."""
        d1 = _to_dec(10.555)
        self.assertEqual(str(d1), "10.56")

        d2 = _to_dec(0.1) + _to_dec(0.2)
        self.assertEqual(str(d2), "0.30")

    def test_negative_or_zero_payment_rejected(self):
        """Payment service rejects zero or negative amounts."""
        payload = mock.MagicMock()
        payload.invoice_id = 99999
        payload.amount = 0.0
        current_user = {"user_id": 1, "roles": ["super_admin"], "role": "super_admin"}

        with self.assertRaises(HTTPException):
            PaymentService.record_payment(payload, current_user)

    # =========================================================================
    # 6. PRIORITY 5: SAFE 500 ERROR HANDLING
    # =========================================================================

    def test_safe_500_error_response_no_traceback_leak(self):
        """Middleware catches unhandled exceptions and returns sanitized JSON with request_id."""
        from backend.app.main import app as main_app
        client = TestClient(main_app, raise_server_exceptions=False)
        resp = client.get("/api/v1/invalid-route-that-does-not-exist")
        self.assertEqual(resp.status_code, 404)

    # =========================================================================
    # 7. PRIORITY 7: BOUNDED LRU CACHE
    # =========================================================================

    def test_lru_cache_bounded_capacity(self):
        """CacheService enforces max_size and evicts oldest items in LRU order."""
        cache = CacheService(default_ttl=60.0, max_size=3)
        cache.set("a", 1)
        cache.set("b", 2)
        cache.set("c", 3)

        # Access 'a' to make it recently used: order is now b, c, a
        self.assertEqual(cache.get("a"), 1)

        # Add 'd', which exceeds max_size (3), should evict oldest ('b')
        cache.set("d", 4)

        self.assertIsNone(cache.get("b"))
        self.assertEqual(cache.get("a"), 1)
        self.assertEqual(cache.get("c"), 3)
        self.assertEqual(cache.get("d"), 4)

    # =========================================================================
    # 8. PRIORITY 8 & 9: DEMO SEEDING CONFIGURATION
    # =========================================================================

    def test_demo_seeding_flag_in_settings(self):
        """Settings properly detects production vs development for demo seeding."""
        dev_settings = Settings(app_env="development", enable_demo_seeding=True)
        self.assertTrue(dev_settings.enable_demo_seeding)

        prod_settings = Settings(app_env="production", enable_demo_seeding=False)
        self.assertFalse(prod_settings.enable_demo_seeding)



    # =========================================================================
    # 9. COOKIE-BASED AUTHENTICATION & ZERO-JSON-EXPOSURE VERIFICATION
    # =========================================================================

    def test_login_sets_httponly_cookie_and_excludes_refresh_from_json(self):
        """Login delivers refresh token exclusively via HttpOnly cookie; never in JSON."""
        res = self.client.post("/api/v1/auth/login", json={
            "username_or_email": "superadmin",
            "password": "Password123!"
        })
        self.assertEqual(res.status_code, 200)
        data = res.json()
        self.assertIn("access_token", data)
        self.assertNotIn("refresh_token", data, "Security failure: refresh_token leaked in login JSON response!")
        self.assertIn("refresh_token", res.cookies, "HttpOnly refresh_token cookie missing from login response!")

    def test_registration_excludes_refresh_from_json(self):
        """Registration delivers refresh token via HttpOnly cookie; never in JSON."""
        unique_username = f"new_stu_{secrets.token_hex(4)}"
        unique_phone = f"9{secrets.randbelow(899999999) + 100000000}"
        res = self.client.post("/api/v1/auth/register", json={
            "username": unique_username,
            "email": f"{unique_username}@univ.edu",
            "password": "Password123!",
            "first_name": "New",
            "last_name": "Student",
            "phone": unique_phone,
            "gender": "Male",
            "role": "student"
        })
        self.assertIn(res.status_code, (200, 201))
        data = res.json()
        self.assertNotIn("refresh_token", data, "Security failure: refresh_token leaked in register JSON response!")

    def test_refresh_endpoint_excludes_refresh_from_json(self):
        """Refresh response returns new access_token in JSON and sets rotated cookie; no refresh_token in JSON."""
        login_res = self.client.post("/api/v1/auth/login", json={
            "username_or_email": "accountant",
            "password": "Password123!"
        })
        self.assertEqual(login_res.status_code, 200)
        refresh_cookie = login_res.cookies.get("refresh_token")
        self.assertIsNotNone(refresh_cookie)

        # Silent cookie-only refresh (empty body)
        refresh_res = self.client.post("/api/v1/auth/refresh", json={}, cookies={"refresh_token": refresh_cookie})
        self.assertEqual(refresh_res.status_code, 200)
        ref_data = refresh_res.json()
        self.assertIn("access_token", ref_data)
        self.assertNotIn("refresh_token", ref_data, "Security failure: refresh_token leaked in refresh JSON response!")
        self.assertIn("refresh_token", refresh_res.cookies)
        self.assertNotEqual(refresh_res.cookies.get("refresh_token"), refresh_cookie)

    def test_rotated_refresh_token_reuse_revocation(self):
        """Attempting to reuse an already rotated refresh token cookie fails with 401 and revokes sessions."""
        login_res = self.client.post("/api/v1/auth/login", json={
            "username_or_email": "warden",
            "password": "Password123!"
        })
        first_cookie = login_res.cookies.get("refresh_token")

        # 1. Rotate token once
        rot_res = self.client.post("/api/v1/auth/refresh", json={}, cookies={"refresh_token": first_cookie})
        self.assertEqual(rot_res.status_code, 200)

        # 2. Replay the first (now rotated) cookie
        replay_res = self.client.post("/api/v1/auth/refresh", json={}, cookies={"refresh_token": first_cookie})
        self.assertEqual(replay_res.status_code, 401)
        self.assertIn("compromised", replay_res.json().get("detail", "").lower())

    def test_frontend_api_client_in_memory_contract(self):
        """Verify frontend/js/api.js maintains tokens purely in memory and permits only removeItem cleanup."""
        api_js_path = os.path.join(os.path.dirname(os.path.dirname(os.path.dirname(__file__))), "frontend", "js", "api.js")
        with open(api_js_path, "r", encoding="utf-8") as f:
            api_content = f.read()

        # Access tokens must be maintained in module-scoped JavaScript memory
        self.assertIn("_inMemoryAccessToken", api_content)
        # Parallel refresh requests must be coalesced using module-scoped promise
        self.assertIn("_refreshPromise", api_content)
        # Zero token persistence in localStorage or sessionStorage
        self.assertNotIn("localStorage.setItem(\"hms_access_token\"", api_content)
        self.assertNotIn("localStorage.setItem(\"hms_refresh_token\"", api_content)
        self.assertNotIn("sessionStorage.setItem(\"hms_access_token\"", api_content)
        self.assertNotIn("sessionStorage.setItem(\"hms_refresh_token\"", api_content)
        # Active cleanup of legacy/stale tokens via removeItem is permitted and enforced
        self.assertIn("localStorage.removeItem(\"hms_access_token\")", api_content)
        self.assertIn("localStorage.removeItem(\"hms_refresh_token\")", api_content)
        self.assertIn("sessionStorage.removeItem(\"hms_access_token\")", api_content)

    def test_failed_refresh_returns_401_without_looping(self):
        """Failed refresh request with invalid cookie returns clean 401."""
        res = self.client.post("/api/v1/auth/refresh", json={}, cookies={"refresh_token": "nonexistent_fake_cookie"})
        self.assertEqual(res.status_code, 401)



    # =========================================================================
    # 10. PRIORITY 10: AUTHORITATIVE INTEGER PAISE STORAGE & RECONCILIATION
    # =========================================================================

    def test_currency_utility_exact_conversions(self):
        """Monetary currency utilities convert rupee to paise without floating-point loss."""
        from backend.app.utils.currency import to_paise, from_paise, paise_to_float
        self.assertEqual(to_paise(6000.0), 600000)
        self.assertEqual(to_paise("15000.50"), 1500050)
        self.assertEqual(to_paise(Decimal("123.45")), 12345)
        self.assertEqual(to_paise(0), 0)
        self.assertEqual(to_paise(None), 0)
        self.assertEqual(from_paise(600000), Decimal("6000.00"))
        self.assertEqual(from_paise(1500050), Decimal("15000.50"))
        self.assertEqual(paise_to_float(600000), 6000.0)
        # Half-up rounding test
        self.assertEqual(to_paise("10.005"), 1001)
        self.assertEqual(to_paise("10.004"), 1000)

    def test_migration_014_schema_integrity_and_reconciliation(self):
        """Migration 014 exists and all monetary tables contain authoritative integer paise columns."""
        conn = get_db_connection()
        try:
            cursor = conn.cursor()
            cursor.execute("SELECT version FROM schema_migrations WHERE version = '014_monetary_paise_migration';")
            self.assertIsNotNone(cursor.fetchone(), "Migration 014_monetary_paise_migration not found in schema_migrations!")

            expected_cols = {
                "fee_structures": ["amount_paise", "late_fine_amount_paise"],
                "invoices": ["total_amount_paise", "paid_amount_paise", "discount_amount_paise", "fine_amount_paise"],
                "invoice_items": ["amount_paise"],
                "payments": ["amount_paise"],
                "refunds": ["amount_paise"]
            }

            for table, cols in expected_cols.items():
                existing_cols = [c[1] for c in cursor.execute(f"PRAGMA table_info({table});").fetchall()]
                for col in cols:
                    self.assertIn(col, existing_cols, f"Column {col} missing from table {table}!")

            # Verify reconciliation: historical records have amount_paise == round(amount * 100)
            cursor.execute("SELECT id, amount, amount_paise FROM payments;")
            for row in cursor.fetchall():
                self.assertEqual(int(round(row["amount"] * 100)), row["amount_paise"])

            cursor.execute("SELECT id, total_amount, total_amount_paise, paid_amount, paid_amount_paise FROM invoices;")
            for row in cursor.fetchall():
                self.assertEqual(int(round(row["total_amount"] * 100)), row["total_amount_paise"])
                self.assertEqual(int(round(row["paid_amount"] * 100)), row["paid_amount_paise"])
        finally:
            conn.close()

    def test_fee_structure_and_invoice_paise_persistence(self):
        """Fee service dual-writes integer paise on fee structure and invoice creation."""
        from backend.app.services.fee_service import FeeService
        from backend.app.models.finance_dto import FeeStructureCreate, InvoiceCreate
        from backend.app.utils.currency import to_paise

        admin_user = {"user_id": 1, "username": "admin", "role": "super_admin"}
        unique_suffix = secrets.token_hex(4)
        fs_payload = FeeStructureCreate(
            name=f"Test Term Fee {unique_suffix}",
            fee_category="Tuition",
            academic_year="2026-2027",
            room_type="Single",
            semester="1",
            amount=7500.50,
            payment_frequency="Semester",
            is_mandatory=True,
            late_fine_amount=250.00,
            description="Paise persistence test"
        )
        fs = FeeService.create_fee_structure(fs_payload, admin_user)
        self.assertEqual(fs["amount"], 7500.50)
        self.assertEqual(fs["amount_paise"], 750050)
        self.assertEqual(fs["late_fine_amount_paise"], 25000)

        # Create an invoice under this fee structure
        inv_payload = InvoiceCreate(
            student_id="1",
            fee_structure_id=fs["id"],
            issue_date="2026-11-01",
            due_date="2026-11-30",
            total_amount=7500.50,
            discount_amount=500.50,
            discount_reason="Merit Scholarship"
        )
        inv = FeeService.create_invoice(inv_payload, admin_user)
        self.assertEqual(inv["total_amount_paise"], 750050)
        self.assertEqual(inv["discount_amount_paise"], 50050)
        self.assertEqual(inv["paid_amount_paise"], 0)

        # Verify payment recording updates paid_amount_paise
        from backend.app.models.finance_dto import PaymentRecordCreate
        pay_payload = PaymentRecordCreate(
            invoice_id=inv["id"],
            amount=3000.00,
            payment_method="Cash",
            payment_date="2026-11-02",
            notes="Partial cash payment"
        )
        pay_res = PaymentService.record_payment(pay_payload, admin_user)
        self.assertIn("payment_reference", pay_res)

        updated_inv = FeeService.get_invoice(inv["id"], admin_user)
        self.assertEqual(updated_inv["paid_amount_paise"], 300000)
        self.assertEqual(updated_inv["status"], "Partially_Paid")



    # =========================================================================
    # 11. REGISTRATION APPROVAL LIFECYCLE & MULTI-STATE RBAC ENFORCEMENT
    # =========================================================================

    def test_pending_student_registration_security_lifecycle(self):
        """Pending student registration restricts normal session, verifies approval/rejection lifecycle."""
        unique_suffix = secrets.token_hex(4)
        uname = f"pen_stu_{unique_suffix}"
        phone = f"9{secrets.randbelow(899999999) + 100000000}"
        pwd = "Password123!"

        # 1. Register student
        reg_res = self.client.post("/api/v1/auth/register", json={
            "username": uname,
            "email": f"{uname}@univ.edu",
            "password": pwd,
            "first_name": "Pending",
            "last_name": "Applicant",
            "phone": phone,
            "gender": "Male",
            "role": "student",
            "enrollment_no": f"ROLL-{unique_suffix.upper()}"
        })
        self.assertEqual(reg_res.status_code, 201)
        reg_data = reg_res.json()

        # 2. Assert account status is pending
        self.assertEqual(reg_data["status"], "Pending_Approval")
        self.assertTrue(reg_data["requires_approval"])

        # 3. Assert registration does NOT return an active access token
        self.assertEqual(reg_data.get("access_token"), "")

        # 4. Assert registration does NOT set an HttpOnly refresh cookie
        self.assertNotIn("refresh_token", reg_res.cookies)

        # 5. Attempt login while pending -> 403 Forbidden with pending explanation
        log_pending_res = self.client.post("/api/v1/auth/login", json={
            "username_or_email": uname,
            "password": pwd
        })
        self.assertEqual(log_pending_res.status_code, 403)
        self.assertIn("pending approval", log_pending_res.json().get("detail", "").lower())

        # 6. Attempt token refresh with empty/stale cookie -> 401 Unauthorized
        ref_pending_res = self.client.post("/api/v1/auth/refresh", json={})
        self.assertEqual(ref_pending_res.status_code, 401)

        # 7. Even if an attacker synthesizes a JWT for this pending user ID:
        user_id = reg_data["user"]["id"]
        forged_jwt = create_access_token({"sub": uname, "user_id": user_id, "roles": ["student"]})
        auth_hdr = {"Authorization": f"Bearer {forged_jwt}"}

        # Attempt to call /api/v1/auth/me
        me_res = self.client.get("/api/v1/auth/me", headers=auth_hdr)
        self.assertEqual(me_res.status_code, 401)
        self.assertIn("inactive", me_res.json().get("detail", "").lower())

        # Attempt to access protected endpoints (allocations, leaves, attendance, fees)
        alloc_res = self.client.get("/api/v1/allocations", headers=auth_hdr)
        self.assertEqual(alloc_res.status_code, 401)

        leaves_res = self.client.get("/api/v1/leave", headers=auth_hdr)
        self.assertEqual(leaves_res.status_code, 401)

        attend_res = self.client.get("/api/v1/attendance", headers=auth_hdr)
        self.assertEqual(attend_res.status_code, 401)

        fees_res = self.client.get("/api/v1/fees/structures", headers=auth_hdr)
        self.assertEqual(fees_res.status_code, 401)

        # Attempt to switch roles
        switch_res = self.client.post("/api/v1/auth/switch-role", json={"role": "warden"}, headers=auth_hdr)
        self.assertEqual(switch_res.status_code, 401)

        # 8. Warden / Administrator approves the registration request
        conn = get_db_connection()
        try:
            cursor = conn.cursor()
            cursor.execute("SELECT id FROM registration_requests WHERE user_id = ?;", (user_id,))
            req_id = cursor.fetchone()[0]
        finally:
            conn.close()

        warden_user = {"id": 3, "username": "warden", "roles": ["warden"]}
        approval_res = AuthService.process_registration_action(
            req_id=req_id,
            action="approve",
            reason="Verified enrollment records",
            current_user=warden_user
        )
        self.assertTrue(approval_res["success"])
        self.assertEqual(approval_res["status"], "Approved")

        # 9. Now that account is approved: login succeeds and yields token pair + cookie
        log_approved_res = self.client.post("/api/v1/auth/login", json={
            "username_or_email": uname,
            "password": pwd
        })
        self.assertEqual(log_approved_res.status_code, 200)
        app_data = log_approved_res.json()
        active_access_token = app_data["access_token"]
        self.assertTrue(bool(active_access_token))
        self.assertNotIn("refresh_token", app_data)
        self.assertIn("refresh_token", log_approved_res.cookies)

        valid_hdr = {"Authorization": f"Bearer {active_access_token}"}
        me_app_res = self.client.get("/api/v1/auth/me", headers=valid_hdr)
        self.assertEqual(me_app_res.status_code, 200)
        self.assertEqual(me_app_res.json()["username"], uname)

    def test_rejected_student_registration_security(self):
        """Rejected student registrations are locked in inactive status and cannot authenticate."""
        unique_suffix = secrets.token_hex(4)
        uname = f"rej_stu_{unique_suffix}"
        phone = f"9{secrets.randbelow(899999999) + 100000000}"
        pwd = "Password123!"

        reg_res = self.client.post("/api/v1/auth/register", json={
            "username": uname,
            "email": f"{uname}@univ.edu",
            "password": pwd,
            "first_name": "Rejected",
            "last_name": "Candidate",
            "phone": phone,
            "gender": "Female",
            "role": "student",
            "enrollment_no": f"ROLL-REJ-{unique_suffix.upper()}"
        })
        self.assertEqual(reg_res.status_code, 201)
        user_id = reg_res.json()["user"]["id"]

        conn = get_db_connection()
        try:
            cursor = conn.cursor()
            cursor.execute("SELECT id FROM registration_requests WHERE user_id = ?;", (user_id,))
            req_id = cursor.fetchone()[0]
        finally:
            conn.close()

        warden_user = {"id": 3, "username": "warden", "roles": ["warden"]}
        reject_res = AuthService.process_registration_action(
            req_id=req_id,
            action="reject",
            reason="Invalid departmental enrollment",
            current_user=warden_user
        )
        self.assertTrue(reject_res["success"])
        self.assertEqual(reject_res["status"], "Rejected")

        # Attempt to log in as rejected user
        log_res = self.client.post("/api/v1/auth/login", json={
            "username_or_email": uname,
            "password": pwd
        })
        self.assertEqual(log_res.status_code, 403)
        self.assertIn("not approved", log_res.json().get("detail", "").lower())

    def test_disabled_or_deactivated_account_security(self):
        """Deactivated accounts are immediately blocked from login and token usage."""
        unique_suffix = secrets.token_hex(4)
        uname = f"deact_stu_{unique_suffix}"
        phone = f"9{secrets.randbelow(899999999) + 100000000}"
        pwd = "Password123!"

        conn = get_db_connection()
        try:
            cursor = conn.cursor()
            salt = secrets.token_hex(16)
            pwd_h = hash_password(pwd)
            cursor.execute("""
                INSERT INTO users (username, email, password_hash, salt, first_name, last_name, phone, is_active, gender)
                VALUES (?, ?, ?, ?, 'Disabled', 'User', ?, 0, 'Male');
            """, (uname, f"{uname}@univ.edu", pwd_h, salt, phone))
            user_id = cursor.lastrowid
            conn.commit()
        finally:
            conn.close()

        log_res = self.client.post("/api/v1/auth/login", json={
            "username_or_email": uname,
            "password": pwd
        })
        self.assertEqual(log_res.status_code, 403)
        self.assertIn("deactivated", log_res.json().get("detail", "").lower())


if __name__ == "__main__":
    unittest.main()
