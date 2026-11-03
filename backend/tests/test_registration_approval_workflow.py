import unittest
import sys
import os
import uuid

# Ensure backend app is on sys.path
web_app_dir = os.path.join(os.path.dirname(__file__), "Hostel Management System Web App")
if web_app_dir not in sys.path:
    sys.path.insert(0, web_app_dir)

from fastapi.testclient import TestClient
from backend.app.main import app

import shutil
import tempfile
from backend.app.config import settings
from backend.app.database.init_db import initialize_database

class TestRegistrationApprovalWorkflow(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.temp_dir = tempfile.mkdtemp()
        cls.db_path = os.path.join(cls.temp_dir, "test_reg_approval.db")
        cls.orig_db_path = settings.database_path
        settings.database_path = cls.db_path
        initialize_database()

        cls.client = TestClient(app)

        # Login admin to obtain token
        res = cls.client.post("/api/v1/auth/login", json={"username_or_email": "superadmin", "password": "Password123!"})
        cls.admin_token = res.json()["access_token"]
        cls.admin_headers = {"Authorization": f"Bearer {cls.admin_token}"}

        # Login warden to obtain token
        res_w = cls.client.post("/api/v1/auth/login", json={"username_or_email": "warden", "password": "Password123!"})
        cls.warden_token = res_w.json()["access_token"]
        cls.warden_headers = {"Authorization": f"Bearer {cls.warden_token}"}

        # Login child student (Rohan Bakshi, roll 2410301057)
        res_s = cls.client.post("/api/v1/auth/login", json={"username_or_email": "rohan", "password": "Password123!"})
        cls.student_token = res_s.json()["access_token"]
        cls.student_headers = {"Authorization": f"Bearer {cls.student_token}"}

    @classmethod
    def tearDownClass(cls):
        settings.database_path = cls.orig_db_path
        shutil.rmtree(cls.temp_dir, ignore_errors=True)

    def test_01_student_registration_approved_by_warden(self):
        uid = uuid.uuid4().hex[:6]
        username = f"std_{uid}"
        payload = {
            "username": username,
            "email": f"{username}@univ.edu",
            "password": "Password123!",
            "first_name": "TestStudent",
            "last_name": "Resident",
            "role": "student",
            "branch": "CSE"
        }
        # 1. Register student
        res = self.client.post("/api/v1/auth/register", json=payload)
        self.assertEqual(res.status_code, 201)
        data = res.json()
        self.assertEqual(data["status"], "Pending_Approval")
        self.assertTrue(data["requires_approval"])

        # 2. Student tries to login before approval -> blocked 403
        login_res = self.client.post("/api/v1/auth/login", json={"username_or_email": username, "password": "Password123!"})
        self.assertEqual(login_res.status_code, 403)
        self.assertIn("pending approval", login_res.json()["detail"].lower())

        # 3. Warden retrieves pending registrations
        pend_res = self.client.get("/api/v1/registrations/pending", headers=self.warden_headers)
        self.assertEqual(pend_res.status_code, 200)
        pending_list = pend_res.json()
        target = next((r for r in pending_list if r["username"] == username), None)
        self.assertIsNotNone(target, "Student request should be visible to warden")

        # 4. Warden approves student
        action_res = self.client.post(
            f"/api/v1/registrations/{target['id']}/action",
            headers=self.warden_headers,
            json={"action": "approve", "reason": "Verified credentials"}
        )
        self.assertEqual(action_res.status_code, 200)

        # 5. Student can now log in successfully!
        login_success = self.client.post("/api/v1/auth/login", json={"username_or_email": username, "password": "Password123!"})
        self.assertEqual(login_success.status_code, 200)
        self.assertIn("access_token", login_success.json())

    def test_02_staff_registration_with_warden_specialization_admin_only(self):
        uid = uuid.uuid4().hex[:6]
        username = f"warden_{uid}"
        payload = {
            "username": username,
            "email": f"{username}@univ.edu",
            "password": "Password123!",
            "first_name": "New",
            "last_name": "WardenStaff",
            "role": "staff",
            "specialization": "warden"
        }
        # 1. Register staff with warden specialization
        res = self.client.post("/api/v1/auth/register", json=payload)
        self.assertEqual(res.status_code, 201)
        self.assertEqual(res.json()["status"], "Pending_Approval")

        # 2. Staff cannot log in yet
        login_res = self.client.post("/api/v1/auth/login", json={"username_or_email": username, "password": "Password123!"})
        self.assertEqual(login_res.status_code, 403)

        # 3. Admin gets pending list to find this staff request
        admin_pend = self.client.get("/api/v1/registrations/pending", headers=self.admin_headers).json()
        target = next((r for r in admin_pend if r["username"] == username), None)
        self.assertIsNotNone(target)

        # 4. Warden tries to approve staff member -> Strictly rejected 403!
        warden_act = self.client.post(
            f"/api/v1/registrations/{target['id']}/action",
            headers=self.warden_headers,
            json={"action": "approve"}
        )
        self.assertEqual(warden_act.status_code, 403)
        self.assertIn("Only Administrators can approve staff", warden_act.json()["detail"])

        # 5. Administrator approves staff
        admin_act = self.client.post(
            f"/api/v1/registrations/{target['id']}/action",
            headers=self.admin_headers,
            json={"action": "approve"}
        )
        self.assertEqual(admin_act.status_code, 200)

        # 6. Staff can now log in and has warden role!
        login_success = self.client.post("/api/v1/auth/login", json={"username_or_email": username, "password": "Password123!"})
        self.assertEqual(login_success.status_code, 200)
        self.assertIn("warden", login_success.json()["user"]["roles"])

    def test_03_parent_dual_approval_workflow(self):
        uid = uuid.uuid4().hex[:6]
        username = f"parent_{uid}"
        payload = {
            "username": username,
            "email": f"{username}@family.org",
            "password": "Password123!",
            "first_name": "Parent",
            "last_name": "Bakshi",
            "role": "parent_guardian",
            "child_identifier": "2410301057", # Rohan Bakshi
            "relationship": "Father"
        }
        # 1. Register parent linked to child 2410301057
        res = self.client.post("/api/v1/auth/register", json=payload)
        self.assertEqual(res.status_code, 201)
        self.assertEqual(res.json()["status"], "Pending_Approval")

        # 2. Login blocked
        login_res = self.client.post("/api/v1/auth/login", json={"username_or_email": username, "password": "Password123!"})
        self.assertEqual(login_res.status_code, 403)

        # 3. Child student checks their pending requests -> sees parent request
        stud_pend = self.client.get("/api/v1/registrations/pending", headers=self.student_headers).json()
        target = next((r for r in stud_pend if r["username"] == username), None)
        self.assertIsNotNone(target, "Child student must see parent registration request")

        # 4. Warden approves parent request
        w_act = self.client.post(
            f"/api/v1/registrations/{target['id']}/action",
            headers=self.warden_headers,
            json={"action": "approve"}
        )
        self.assertEqual(w_act.status_code, 200)

        # 5. Parent still cannot log in because child has not approved yet!
        login_res2 = self.client.post("/api/v1/auth/login", json={"username_or_email": username, "password": "Password123!"})
        self.assertEqual(login_res2.status_code, 403)
        self.assertIn("confirmation by your child", login_res2.json()["detail"].lower())

        # 6. Child student approves parent request
        s_act = self.client.post(
            f"/api/v1/registrations/{target['id']}/action",
            headers=self.student_headers,
            json={"action": "approve"}
        )
        self.assertEqual(s_act.status_code, 200)

        # 7. Now BOTH parties have approved -> Parent is activated and logs in!
        login_success = self.client.post("/api/v1/auth/login", json={"username_or_email": username, "password": "Password123!"})
        self.assertEqual(login_success.status_code, 200)
        self.assertIn("parent_guardian", login_success.json()["user"]["roles"])


    def test_04_gender_persisted_for_student_and_staff_registration(self):
        # 1. Register student with Female gender
        s_uid = uuid.uuid4().hex[:6]
        s_uname = f"std_f_{s_uid}"
        res_s = self.client.post("/api/v1/auth/register", json={
            "username": s_uname,
            "email": f"{s_uname}@univ.edu",
            "password": "Password123!",
            "first_name": "Pooja",
            "last_name": "Sharma",
            "role": "student",
            "branch": "ECE",
            "gender": "Female"
        })
        self.assertEqual(res_s.status_code, 201)

        # Check in pending queue that gender is Female
        pend_w = self.client.get("/api/v1/registrations/pending", headers=self.warden_headers).json()
        target_s = next((r for r in pend_w if r["username"] == s_uname), None)
        self.assertIsNotNone(target_s)
        self.assertEqual(target_s["gender"], "Female")

        # 2. Register staff member with Female gender
        stf_uid = uuid.uuid4().hex[:6]
        stf_uname = f"stf_f_{stf_uid}"
        res_stf = self.client.post("/api/v1/auth/register", json={
            "username": stf_uname,
            "email": f"{stf_uname}@univ.edu",
            "password": "Password123!",
            "first_name": "Meena",
            "last_name": "Kumari",
            "role": "staff",
            "specialization": "warden",
            "gender": "Female"
        })
        self.assertEqual(res_stf.status_code, 201)

        # Check in admin queue that staff request has Female gender
        pend_a = self.client.get("/api/v1/registrations/pending", headers=self.admin_headers).json()
        target_stf = next((r for r in pend_a if r["username"] == stf_uname), None)
        self.assertIsNotNone(target_stf)
        self.assertEqual(target_stf["gender"], "Female")

if __name__ == "__main__":
    unittest.main()
