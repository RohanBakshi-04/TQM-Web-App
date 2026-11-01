import unittest
import sys
import os
import uuid

web_app_dir = os.path.join(os.path.dirname(__file__), "Hostel Management System Web App")
if web_app_dir not in sys.path:
    sys.path.insert(0, web_app_dir)

from fastapi.testclient import TestClient
from backend.app.main import app

class TestRegistrationInputValidation(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.client = TestClient(app)

    def test_01_phone_with_letters_rejected(self):
        """Entering alphabetic characters in phone number (e.g. ABCD@) must be rejected."""
        uid = uuid.uuid4().hex[:6]
        payload = {
            "username": f"user_{uid}",
            "email": f"user_{uid}@univ.edu",
            "password": "Password123!",
            "first_name": "Test",
            "last_name": "User",
            "phone": "ABCD@12345",
            "role": "student"
        }
        res = self.client.post("/api/v1/auth/register", json=payload)
        self.assertIn(res.status_code, (400, 422))
        err_text = str(res.json()).lower()
        self.assertTrue("phone" in err_text or "digits" in err_text)

    def test_02_phone_with_wrong_digit_count_rejected(self):
        """Phone numbers with fewer or more than 10 digits must be rejected."""
        uid = uuid.uuid4().hex[:6]
        # Short phone (4 digits)
        res_short = self.client.post("/api/v1/auth/register", json={
            "username": f"user_s_{uid}",
            "email": f"user_s_{uid}@univ.edu",
            "password": "Password123!",
            "first_name": "Test",
            "last_name": "User",
            "phone": "9811",
            "role": "student"
        })
        self.assertIn(res_short.status_code, (400, 422))

        # Long phone (12 digits)
        res_long = self.client.post("/api/v1/auth/register", json={
            "username": f"user_l_{uid}",
            "email": f"user_l_{uid}@univ.edu",
            "password": "Password123!",
            "first_name": "Test",
            "last_name": "User",
            "phone": "981122334455",
            "role": "student"
        })
        self.assertIn(res_long.status_code, (400, 422))

    def test_03_email_without_at_symbol_rejected(self):
        """Email missing '@' must be rejected."""
        uid = uuid.uuid4().hex[:6]
        payload = {
            "username": f"user_em_{uid}",
            "email": "invalidemailwithoutat.com",
            "password": "Password123!",
            "first_name": "Test",
            "last_name": "User",
            "phone": "9811223344",
            "role": "student"
        }
        res = self.client.post("/api/v1/auth/register", json=payload)
        self.assertIn(res.status_code, (400, 422))
        err_text = str(res.json()).lower()
        self.assertTrue("email" in err_text or "@" in err_text)

    def test_04_name_with_numbers_or_symbols_rejected(self):
        """Names with numeric digits (e.g. Rahul123) must be rejected."""
        uid = uuid.uuid4().hex[:6]
        payload = {
            "username": f"user_nm_{uid}",
            "email": f"user_{uid}@univ.edu",
            "password": "Password123!",
            "first_name": "Rahul123",
            "last_name": "Verma",
            "phone": "9811223344",
            "role": "student"
        }
        res = self.client.post("/api/v1/auth/register", json=payload)
        self.assertIn(res.status_code, (400, 422))

    def test_05_valid_registration_accepted(self):
        """Valid inputs (10-digit phone, proper email, alphabetic names) succeed."""
        uid = uuid.uuid4().hex[:6]
        payload = {
            "username": f"user_ok_{uid}",
            "email": f"valid_{uid}@univ.edu",
            "password": "Password123!",
            "first_name": "Rahul",
            "last_name": "Verma",
            "phone": "9811223344",
            "role": "student"
        }
        res = self.client.post("/api/v1/auth/register", json=payload)
        self.assertEqual(res.status_code, 201)
        self.assertEqual(res.json()["status"], "Pending_Approval")

if __name__ == "__main__":
    unittest.main()
