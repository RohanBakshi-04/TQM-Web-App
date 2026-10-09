"""Unit Tests for Authentication Service, Lockout, and Token Rotation.

Course: BBAT104 - Fundamentals of Total Quality Management (TQM)
Quality Goal: Q05 - Reduce Response Time
"""

import sqlite3
import unittest
from fastapi import HTTPException
from backend.app.database.init_db import initialize_database
from backend.app.services.auth_service import AuthService


class TestAuthServiceLogic(unittest.TestCase):
    def setUp(self):
        self.conn = sqlite3.connect(":memory:")
        self.conn.row_factory = sqlite3.Row
        self.conn.execute("PRAGMA foreign_keys = ON;")
        initialize_database(self.conn, seed=True)

    def tearDown(self):
        self.conn.close()

    def test_01_successful_authentication(self):
        user = AuthService.authenticate_user("rohan", "Password123!", "127.0.0.1", "TestClient", conn=self.conn)
        self.assertIsNotNone(user)
        self.assertEqual(user["username"], "rohan")
        self.assertIn("student", user["roles"])
        self.assertEqual(user["linked_student_id"], 1)

    def test_02_login_failure_and_lockout(self):
        # 4 failed attempts should raise 401
        for _ in range(4):
            with self.assertRaises(HTTPException) as ctx:
                AuthService.authenticate_user("asstwarden", "WrongPass", "127.0.0.1", conn=self.conn)
            self.assertEqual(ctx.exception.status_code, 401)

        # 5th failed attempt should lock account
        with self.assertRaises(HTTPException) as ctx:
            AuthService.authenticate_user("asstwarden", "WrongPass", "127.0.0.1", conn=self.conn)
        self.assertEqual(ctx.exception.status_code, 401)

        # 6th attempt should return 429 Too Many Requests (Account Locked)
        with self.assertRaises(HTTPException) as ctx:
            AuthService.authenticate_user("asstwarden", "Password123!", "127.0.0.1", conn=self.conn)
        self.assertEqual(ctx.exception.status_code, 429)
        self.assertIn("temporarily locked", ctx.exception.detail)

    def test_03_token_rotation_and_reuse_detection(self):
        user = AuthService.authenticate_user("warden", "Password123!", conn=self.conn)
        token_pair = AuthService.issue_token_pair(user, conn=self.conn)
        raw_refresh = token_pair["refresh_token"]

        # Rotate token
        new_token_pair = AuthService.rotate_refresh_token(raw_refresh, conn=self.conn)
        self.assertNotEqual(raw_refresh, new_token_pair["refresh_token"])

        # Attempt to reuse old raw_refresh token -> must raise 401 (compromised)
        with self.assertRaises(HTTPException) as ctx:
            AuthService.rotate_refresh_token(raw_refresh, conn=self.conn)
        self.assertEqual(ctx.exception.status_code, 401)
        self.assertIn("Token compromised", ctx.exception.detail)


if __name__ == "__main__":
    unittest.main()
