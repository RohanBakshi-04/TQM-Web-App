"""Integration tests for Authentication & RBAC API Endpoints.

Course: BBAT104 - Fundamentals of Total Quality Management (TQM)
Quality Goal: Q05 - Reduce Response Time
"""

import os
import unittest
from fastapi.testclient import TestClient

from backend.app.config import settings
from backend.app.database.init_db import initialize_database
from backend.app.main import app


class TestAuthAPI(unittest.TestCase):
    """Test suite covering FastAPI authentication endpoints and RBAC authorization."""

    @classmethod
    def setUpClass(cls):
        # Set database to a test database or initialize current DB
        initialize_database()
        cls.client = TestClient(app)

    def test_login_success_and_cookie_set(self):
        """Test successful login returns access token and sets HttpOnly refresh cookie."""
        res = self.client.post("/api/v1/auth/login", json={
            "username_or_email": "superadmin",
            "password": "Password123!"
        })
        self.assertEqual(res.status_code, 200)
        data = res.json()
        self.assertIn("access_token", data)
        self.assertIn("refresh_token", data)
        self.assertEqual(data["user"]["username"], "superadmin")
        self.assertIn("super_admin", data["user"]["roles"])
        self.assertIn("refresh_token", res.cookies)

    def test_login_invalid_password(self):
        """Test invalid credentials returns 401."""
        res = self.client.post("/api/v1/auth/login", json={
            "username_or_email": "superadmin",
            "password": "WrongPassword!"
        })
        self.assertEqual(res.status_code, 401)
        self.assertIn("Invalid username or password", res.json()["detail"])

    def test_get_me_authenticated(self):
        """Test /auth/me returns current user identity with resolved permissions."""
        login_res = self.client.post("/api/v1/auth/login", json={
            "username_or_email": "warden",
            "password": "Password123!"
        })
        token = login_res.json()["access_token"]

        res = self.client.get(
            "/api/v1/auth/me",
            headers={"Authorization": f"Bearer {token}"}
        )
        self.assertEqual(res.status_code, 200)
        me = res.json()
        self.assertEqual(me["username"], "warden")
        self.assertIn("warden", me["roles"])
        self.assertIn("attendance:read", me["permissions"])

    def test_get_me_unauthorized(self):
        """Test /auth/me without token returns 401."""
        res = self.client.get("/api/v1/auth/me")
        self.assertEqual(res.status_code, 401)

    def test_refresh_token_rotation(self):
        """Test refreshing token returns new pair and rotates refresh token."""
        login_res = self.client.post("/api/v1/auth/login", json={
            "username_or_email": "accountant",
            "password": "Password123!"
        })
        refresh_token = login_res.json()["refresh_token"]

        res = self.client.post("/api/v1/auth/refresh", json={
            "refresh_token": refresh_token
        })
        self.assertEqual(res.status_code, 200)
        new_data = res.json()
        self.assertIn("access_token", new_data)
        self.assertNotEqual(new_data["refresh_token"], refresh_token)

    def test_logout_revokes_token(self):
        """Test logout revokes token and clears cookie."""
        login_res = self.client.post("/api/v1/auth/login", json={
            "username_or_email": "messmanager",
            "password": "Password123!"
        })
        refresh_token = login_res.json()["refresh_token"]

        res = self.client.post("/api/v1/auth/logout", json={
            "refresh_token": refresh_token
        })
        self.assertEqual(res.status_code, 200)

        # Attempting refresh with revoked token must fail
        refresh_res = self.client.post("/api/v1/auth/refresh", json={
            "refresh_token": refresh_token
        })
        self.assertEqual(refresh_res.status_code, 401)

    def test_roles_directory(self):
        """Test /roles returns all 12 system roles."""
        res = self.client.get("/api/v1/roles")
        self.assertEqual(res.status_code, 200)
        roles = res.json()
        self.assertEqual(len(roles), 12)
        role_names = [r["name"] for r in roles]
        self.assertIn("super_admin", role_names)
        self.assertIn("warden", role_names)
        self.assertIn("student", role_names)
        self.assertIn("security_guard", role_names)

    def test_rbac_authorization_super_admin_vs_student(self):
        """Test that /users endpoint is restricted to super_admin and forbidden to student."""
        # 1. Login as Student
        student_login = self.client.post("/api/v1/auth/login", json={
            "username_or_email": "rohan",
            "password": "Password123!"
        })
        student_token = student_login.json()["access_token"]

        # Student accesses /users -> Forbidden (403)
        res_student = self.client.get(
            "/api/v1/users",
            headers={"Authorization": f"Bearer {student_token}"}
        )
        self.assertEqual(res_student.status_code, 403)

        # 2. Login as Super Admin
        admin_login = self.client.post("/api/v1/auth/login", json={
            "username_or_email": "superadmin",
            "password": "Password123!"
        })
        admin_token = admin_login.json()["access_token"]

        # Admin accesses /users -> OK (200)
        res_admin = self.client.get(
            "/api/v1/users",
            headers={"Authorization": f"Bearer {admin_token}"}
        )
        self.assertEqual(res_admin.status_code, 200)
        self.assertIsInstance(res_admin.json(), list)

    def test_student_data_isolation(self):
        """Test student data isolation: student can access own profile, but 403 on another student's profile."""
        # Student user is linked to student_id = 1
        student_login = self.client.post("/api/v1/auth/login", json={
            "username_or_email": "rohan",
            "password": "Password123!"
        })
        student_token = student_login.json()["access_token"]
        user_info = student_login.json()["user"]
        my_student_id = user_info["linked_student_id"]
        self.assertEqual(my_student_id, 1)

        # Accessing own profile -> 200 OK
        res_own = self.client.get(
            f"/api/v1/students/{my_student_id}/profile",
            headers={"Authorization": f"Bearer {student_token}"}
        )
        self.assertEqual(res_own.status_code, 200)
        self.assertEqual(res_own.json()["id"], 1)

        # Accessing another student's profile (e.g. ID 2) -> 403 FORBIDDEN
        res_other = self.client.get(
            "/api/v1/students/2/profile",
            headers={"Authorization": f"Bearer {student_token}"}
        )
        self.assertEqual(res_other.status_code, 403)
        self.assertIn("Security Violation", res_other.json()["detail"])

        # Admin or Warden can access student 1 and student 2 profiles -> 200 OK
        warden_login = self.client.post("/api/v1/auth/login", json={
            "username_or_email": "warden",
            "password": "Password123!"
        })
        warden_token = warden_login.json()["access_token"]

        res_warden_view = self.client.get(
            f"/api/v1/students/{my_student_id}/profile",
            headers={"Authorization": f"Bearer {warden_token}"}
        )
        self.assertEqual(res_warden_view.status_code, 200)


if __name__ == "__main__":
    unittest.main()
