import unittest
import sys
import os
import uuid

web_app_dir = os.path.join(os.path.dirname(__file__), "Hostel Management System Web App")
if web_app_dir not in sys.path:
    sys.path.insert(0, web_app_dir)

from fastapi.testclient import TestClient
from backend.app.main import app

def generate_unique_phone():
    return f"98{uuid.uuid4().int % 100000000:08d}"

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
            "phone": generate_unique_phone(),
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
            "phone": generate_unique_phone(),
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
            "phone": generate_unique_phone(),
            "role": "student"
        }
        res = self.client.post("/api/v1/auth/register", json=payload)
        self.assertEqual(res.status_code, 201)
        self.assertEqual(res.json()["status"], "Pending_Approval")

    def test_06_duplicate_phone_in_pending_requests_rejected(self):
        """Registering with a phone number already pending approval must be rejected with HTTP 409."""
        uid1 = uuid.uuid4().hex[:6]
        shared_phone = generate_unique_phone()
        payload1 = {
            "username": f"user_ph1_{uid1}",
            "email": f"user_ph1_{uid1}@univ.edu",
            "password": "Password123!",
            "first_name": "Aman",
            "last_name": "Sharma",
            "phone": shared_phone,
            "role": "student"
        }
        res1 = self.client.post("/api/v1/auth/register", json=payload1)
        self.assertEqual(res1.status_code, 201)

        # Attempt to register a staff account using the same phone number
        uid2 = uuid.uuid4().hex[:6]
        payload2 = {
            "username": f"user_ph2_{uid2}",
            "email": f"user_ph2_{uid2}@univ.edu",
            "password": "Password123!",
            "first_name": "Deepak",
            "last_name": "Sharma",
            "phone": shared_phone,
            "role": "staff",
            "specialization": "electrician"
        }
        res2 = self.client.post("/api/v1/auth/register", json=payload2)
        self.assertEqual(res2.status_code, 409)
        self.assertIn("phone number", res2.json()["detail"].lower())

    def test_07_duplicate_email_in_pending_requests_rejected(self):
        """Registering with an email already pending approval must be rejected with HTTP 409."""
        uid1 = uuid.uuid4().hex[:6]
        shared_email = f"shared_{uid1}@univ.edu"
        payload1 = {
            "username": f"user_em1_{uid1}",
            "email": shared_email,
            "password": "Password123!",
            "first_name": "Pooja",
            "last_name": "Gupta",
            "phone": generate_unique_phone(),
            "role": "student"
        }
        res1 = self.client.post("/api/v1/auth/register", json=payload1)
        self.assertEqual(res1.status_code, 201)

        # Attempt to register second account with same email
        uid2 = uuid.uuid4().hex[:6]
        payload2 = {
            "username": f"user_em2_{uid2}",
            "email": shared_email,
            "password": "Password123!",
            "first_name": "Suresh",
            "last_name": "Gupta",
            "phone": generate_unique_phone(),
            "role": "student"
        }
        res2 = self.client.post("/api/v1/auth/register", json=payload2)
        self.assertEqual(res2.status_code, 409)
        self.assertIn("email", res2.json()["detail"].lower())

    def test_08_duplicate_phone_with_existing_user_rejected(self):
        """Registering with a phone number belonging to an existing active user must be rejected."""
        uid = uuid.uuid4().hex[:6]
        existing_phone = generate_unique_phone()
        # First register an account
        res1 = self.client.post("/api/v1/auth/register", json={
            "username": f"orig_user_{uid}",
            "email": f"orig_{uid}@univ.edu",
            "password": "Password123!",
            "first_name": "Original",
            "last_name": "User",
            "phone": existing_phone,
            "role": "student"
        })
        self.assertEqual(res1.status_code, 201)

        # Now try to register a different person with that same phone
        uid2 = uuid.uuid4().hex[:6]
        res2 = self.client.post("/api/v1/auth/register", json={
            "username": f"diff_user_{uid2}",
            "email": f"diff_{uid2}@univ.edu",
            "password": "Password123!",
            "first_name": "Different",
            "last_name": "Person",
            "phone": existing_phone,
            "role": "student"
        })
        self.assertEqual(res2.status_code, 409)
        self.assertIn("phone number", res2.json()["detail"].lower())

if __name__ == "__main__":
    unittest.main()
