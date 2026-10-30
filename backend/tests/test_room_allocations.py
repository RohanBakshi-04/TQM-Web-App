"""Comprehensive Poka-Yoke Room Allocation & Concurrency Test Suite.

Course: BBAT104 - Fundamentals of Total Quality Management (TQM)
Quality Goal: Q05 - Reduce Response Time (<10ms)
Poka-Yoke: Defect Prevention Verification across 10 Mandatory TQM Rules
"""

import concurrent.futures
import sqlite3
import unittest
from fastapi import HTTPException
from fastapi.testclient import TestClient
from backend.app.database.connection import get_db_connection
from backend.app.database.init_db import initialize_database
from backend.app.main import app
from backend.app.models.allocation_dto import AllocationCreate
from backend.app.services.allocation_service import AllocationService
from backend.app.services.security import create_access_token


class TestRoomAllocationsAndPokaYoke(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        initialize_database()
        cls.client = TestClient(app)

        # Tokens
        cls.admin_token = create_access_token({"user_id": 1, "username": "superadmin", "roles": ["super_admin"]})
        cls.admin_headers = {"Authorization": f"Bearer {cls.admin_token}"}

        cls.warden_token = create_access_token({"user_id": 3, "username": "warden", "roles": ["warden"]})
        cls.warden_headers = {"Authorization": f"Bearer {cls.warden_token}"}

        cls.student_token = create_access_token({"user_id": 5, "username": "rohan", "roles": ["student"], "linked_student_id": 1})
        cls.student_headers = {"Authorization": f"Bearer {cls.student_token}"}

    def setUp(self):
        """Reset state before each test ensuring deterministic isolation."""
        conn = get_db_connection()
        # Keep only initial seed allocations (1 and 2)
        conn.execute("DELETE FROM room_allocations WHERE id NOT IN (1, 2);")
        # Ensure student 2 has no active allocations
        conn.execute("DELETE FROM room_allocations WHERE student_id = 2;")
        # Reset facilities
        conn.execute("UPDATE hostels SET is_active = 1 WHERE id IN (1, 2);")
        conn.execute("UPDATE buildings SET is_active = 1;")
        conn.execute("UPDATE rooms SET status = 'Available', is_active = 1 WHERE id NOT IN (1, 2);")
        conn.execute("UPDATE beds SET status = 'Available' WHERE id NOT IN (1, 2);")
        # Maintain seed allocations
        conn.execute("UPDATE room_allocations SET allocation_status = 'Active' WHERE id IN (1, 2);")
        conn.execute("UPDATE beds SET status = 'Occupied' WHERE id IN (1, 2);")
        conn.commit()
        conn.close()

    # ==================== 1. BASIC ALLOCATION & AUDIT SLIP ====================

    def test_01_successful_allocation(self):
        """Verify successful allocation of eligible student, updating bed/room status and generating slip."""
        payload = {
            "student_id": 2,
            "bed_id": 6,
            "start_date": "2026-09-01",
            "end_date": "2027-05-31",
            "remarks": "Merit Allotment",
            "fee_status": "Paid"
        }
        resp = self.client.post("/api/v1/allocations", json=payload, headers=self.admin_headers)
        self.assertEqual(resp.status_code, 201)
        data = resp.json()

        self.assertEqual(data["student_id"], 2)
        self.assertEqual(data["bed_id"], 6)
        self.assertEqual(data["allocation_status"], "Active")
        self.assertIn("TQM-ALC-", data["confirmation_number"])
        self.assertTrue(len(data["verification_hash"]) >= 16)

        # Verify bed is marked Occupied
        conn = get_db_connection()
        bed_status = conn.execute("SELECT status FROM beds WHERE id = 6;").fetchone()[0]
        self.assertEqual(bed_status, "Occupied")
        conn.close()

    # ==================== 2. POKA-YOKE 10-RULE DEFECT PREVENTION ====================

    def test_02_poka_yoke_rule_1_occupied_bed(self):
        """Poka-Yoke Rule 1: Prevent allocating one bed to multiple active students."""
        # Bed 1 is already active for student 1 (Rohan)
        payload = {
            "student_id": 2,
            "bed_id": 1,
            "start_date": "2026-09-01"
        }
        resp = self.client.post("/api/v1/allocations", json=payload, headers=self.admin_headers)
        self.assertIn(resp.status_code, (400, 409))
        self.assertIn("Poka-Yoke Violation", resp.json()["detail"])

    def test_03_poka_yoke_rule_2_full_room(self):
        """Poka-Yoke Rule 2: Prevent allocating students to full rooms."""
        conn = get_db_connection()
        # Create eligible male student 555
        conn.execute("INSERT OR REPLACE INTO students (id, student_id, first_name, last_name, email, phone, gender, branch, academic_year, admission_date, status) VALUES (555, 'MALE-01', 'Kabir', 'Singh', 'kabir@test.com', '9888111222', 'Male', 'CSE', '1st', '2026-09-01', 'Active');")
        # Room 1 has capacity 1 and is occupied by Rohan (student 1)
        # Create temporary available bed in Room 1
        conn.execute("INSERT OR REPLACE INTO beds (id, room_id, bed_number, status) VALUES (999, 1, '101-EXTRA', 'Available');")
        conn.commit()
        conn.close()

        payload = {
            "student_id": 555,
            "bed_id": 999,
            "start_date": "2026-09-01"
        }
        resp = self.client.post("/api/v1/allocations", json=payload, headers=self.admin_headers)
        self.assertEqual(resp.status_code, 400)
        self.assertIn("Poka-Yoke Violation", resp.json()["detail"])
        self.assertIn("maximum capacity", resp.json()["detail"])

        # Clean up
        conn = get_db_connection()
        conn.execute("DELETE FROM beds WHERE id = 999;")
        conn.execute("DELETE FROM students WHERE id = 555;")
        conn.commit()
        conn.close()

    def test_04_poka_yoke_rule_3_maintenance_bed(self):
        """Poka-Yoke Rule 3: Prevent allocating students to inactive/maintenance beds."""
        conn = get_db_connection()
        conn.execute("UPDATE beds SET status = 'Maintenance' WHERE id = 6;")
        conn.commit()
        conn.close()

        payload = {
            "student_id": 2,
            "bed_id": 6,
            "start_date": "2026-09-01"
        }
        resp = self.client.post("/api/v1/allocations", json=payload, headers=self.admin_headers)
        self.assertEqual(resp.status_code, 400)
        self.assertIn("Maintenance", resp.json()["detail"])

    def test_05_poka_yoke_rule_4_maintenance_room(self):
        """Poka-Yoke Rule 4: Prevent allocating students to rooms under maintenance."""
        conn = get_db_connection()
        conn.execute("UPDATE rooms SET status = 'Maintenance' WHERE id = 4;")
        conn.commit()
        conn.close()

        # Bed 6 is in Room 4
        payload = {
            "student_id": 2,
            "bed_id": 6,
            "start_date": "2026-09-01"
        }
        resp = self.client.post("/api/v1/allocations", json=payload, headers=self.admin_headers)
        self.assertEqual(resp.status_code, 400)
        self.assertIn("under Maintenance", resp.json()["detail"])

    def test_06_poka_yoke_rule_5_inactive_hostel(self):
        """Poka-Yoke Rule 5: Prevent allocating students to inactive hostels."""
        conn = get_db_connection()
        conn.execute("UPDATE hostels SET is_active = 0 WHERE id = 2;")
        conn.commit()
        conn.close()

        payload = {
            "student_id": 2,
            "bed_id": 6, # Bed in Girls hostel (id 2)
            "start_date": "2026-09-01"
        }
        resp = self.client.post("/api/v1/allocations", json=payload, headers=self.admin_headers)
        self.assertEqual(resp.status_code, 400)
        self.assertIn("inactive", resp.json()["detail"].lower())

    def test_07_poka_yoke_rule_6_gender_restriction(self):
        """Poka-Yoke Rule 6: Prevent allocating students to gender-restricted hostels."""
        # Priya is Female (id 2). Bed 4 is in Tagore Hostel (Boys)
        conn = get_db_connection()
        conn.execute("UPDATE rooms SET status = 'Available' WHERE id = 3;")
        conn.execute("UPDATE beds SET status = 'Available' WHERE id = 4;")
        conn.commit()
        conn.close()

        payload = {
            "student_id": 2,
            "bed_id": 4,
            "start_date": "2026-09-01"
        }
        resp = self.client.post("/api/v1/allocations", json=payload, headers=self.admin_headers)
        self.assertEqual(resp.status_code, 400)
        self.assertIn("Gender restriction mismatch", resp.json()["detail"])

    def test_08_poka_yoke_rule_7_duplicate_student_allocation(self):
        """Poka-Yoke Rule 7: Prevent creating duplicate active allocations for the same student."""
        # Student 1 (Rohan) already has active allocation #1
        payload = {
            "student_id": 1,
            "bed_id": 4,
            "start_date": "2026-09-01"
        }
        resp = self.client.post("/api/v1/allocations", json=payload, headers=self.admin_headers)
        self.assertEqual(resp.status_code, 400)
        self.assertIn("already possesses an Active allocation", resp.json()["detail"])

    def test_09_poka_yoke_rule_8_transfer_unavailable_bed(self):
        """Poka-Yoke Rule 8: Prevent transferring students to unavailable or occupied beds."""
        # Allocation 1 (Rohan) transferring to Bed 2 (already Occupied by Aarav)
        payload = {
            "to_bed_id": 2,
            "reason": "Requesting room change to friend room"
        }
        resp = self.client.post("/api/v1/allocations/1/transfer", json=payload, headers=self.admin_headers)
        self.assertEqual(resp.status_code, 400)
        self.assertIn("unavailable", resp.json()["detail"].lower())

    def test_10_poka_yoke_rule_9_checkout_non_active(self):
        """Poka-Yoke Rule 9: Prevent checking out students who have no active allocation or duplicate checkout."""
        # Create temporary vacated allocation for existing student 2
        conn = get_db_connection()
        conn.execute("UPDATE beds SET status = 'Available' WHERE id = 5;")
        conn.execute("""
            INSERT OR REPLACE INTO room_allocations (id, student_id, bed_id, room_id, start_date, allocation_status)
            VALUES (888, 2, 5, 3, '2026-09-01', 'Vacated');
        """)
        conn.commit()
        conn.close()

        payload = {"reason": "Duplicate checkout attempt"}
        resp = self.client.post("/api/v1/allocations/888/checkout", json=payload, headers=self.admin_headers)
        self.assertEqual(resp.status_code, 400)
        self.assertIn("no active allocation", resp.json()["detail"])

        # Clean up
        conn = get_db_connection()
        conn.execute("DELETE FROM room_allocations WHERE id = 888;")
        conn.commit()
        conn.close()

    def test_11_poka_yoke_rule_10_unauthorized_allocation(self):
        """Poka-Yoke Rule 10: Prevent unauthorized role from executing allocations."""
        payload = {
            "student_id": 2,
            "bed_id": 6,
            "start_date": "2026-09-01"
        }
        resp = self.client.post("/api/v1/allocations", json=payload, headers=self.student_headers)
        self.assertEqual(resp.status_code, 403)

    # ==================== 3. CONCURRENCY & RACE CONDITION TEST ====================

    def test_12_concurrency_simultaneous_allocation(self):
        """Verify that concurrent threads attempting to book the SAME bed cannot create a double-allocation."""
        conn = get_db_connection()
        conn.execute("INSERT OR REPLACE INTO students (id, student_id, first_name, last_name, email, phone, gender, branch, academic_year, admission_date, status) VALUES (701, 'CONC-01', 'TestUserA', 'One', 'u1@test.com', '9111', 'Male', 'CSE', '1st', '2026-09-01', 'Active');")
        conn.execute("INSERT OR REPLACE INTO students (id, student_id, first_name, last_name, email, phone, gender, branch, academic_year, admission_date, status) VALUES (702, 'CONC-02', 'TestUserB', 'Two', 'u2@test.com', '9222', 'Male', 'CSE', '1st', '2026-09-01', 'Active');")
        conn.execute("DELETE FROM room_allocations WHERE student_id IN (701, 702);")
        # Ensure target bed 5 (in Room 3, Boys hostel) is Available
        conn.execute("UPDATE rooms SET status = 'Available', is_active = 1 WHERE id = 3;")
        conn.execute("UPDATE beds SET status = 'Available' WHERE id = 5;")
        conn.commit()
        conn.close()

        def book_bed(student_id):
            c = get_db_connection()
            try:
                dto = AllocationCreate(student_id=student_id, bed_id=5, start_date="2026-09-01")
                res = AllocationService.create_allocation(c, dto, allocated_by_user_id=1)
                return ("SUCCESS", res["id"])
            except HTTPException as e:
                return ("HTTP_ERR", e.status_code, e.detail)
            except Exception as e:
                return ("ERR", str(e))
            finally:
                c.close()

        with concurrent.futures.ThreadPoolExecutor(max_workers=2) as executor:
            f1 = executor.submit(book_bed, 701)
            f2 = executor.submit(book_bed, 702)
            results = [f1.result(), f2.result()]

        success_count = sum(1 for r in results if r[0] == "SUCCESS")
        err_count = sum(1 for r in results if r[0] == "HTTP_ERR")

        self.assertEqual(success_count, 1, f"Expected exactly 1 success, got: {results}")
        self.assertEqual(err_count, 1, f"Expected exactly 1 error, got: {results}")

        # Database verification: exactly 1 active allocation exists for bed 5
        conn = get_db_connection()
        active_count = conn.execute("SELECT COUNT(*) FROM room_allocations WHERE bed_id = 5 AND allocation_status = 'Active';").fetchone()[0]
        self.assertEqual(active_count, 1)

        # Clean up
        conn.execute("DELETE FROM room_allocations WHERE student_id IN (701, 702);")
        conn.execute("DELETE FROM students WHERE id IN (701, 702);")
        conn.execute("UPDATE beds SET status = 'Available' WHERE id = 5;")
        conn.commit()
        conn.close()

    # ==================== 4. INTELLIGENT ALLOCATION SUGGESTIONS ====================

    def test_13_intelligent_allocation_suggestions(self):
        """Verify suggestion engine ranks available beds by gender, room type preference, and peer matching."""
        # Priya (Female, ECE)
        resp = self.client.get("/api/v1/allocations/suggestions?student_id=2", headers=self.admin_headers)
        self.assertEqual(resp.status_code, 200)
        suggestions = resp.json()
        self.assertIsInstance(suggestions, list)
        self.assertTrue(len(suggestions) > 0)

        # Female student must ONLY receive suggestions from Girls or Co-Ed facilities
        for s in suggestions:
            self.assertIn(s["hostel_type"], ("Girls", "Co-Ed"))
            self.assertTrue(s["match_score"] >= 50)
            self.assertTrue(len(s["reasons"]) > 0)

    # ==================== 5. CHECK-IN, TRANSFERS & CHECK-OUT ====================

    def test_14_checkin_lifecycle(self):
        """Verify check-in timestamp recording."""
        resp = self.client.post("/api/v1/allocations/1/checkin", json={"checkin_date": "2026-09-02"}, headers=self.admin_headers)
        self.assertEqual(resp.status_code, 200)
        data = resp.json()
        self.assertEqual(data["checkin_date"], "2026-09-02")

    def test_15_atomic_transfer_workflow(self):
        """Verify atomic transfer: old bed freed, new bed claimed, previous allocation marked Transferred."""
        conn = get_db_connection()
        # Student 3 (Aarav) is currently in bed 2 (Room 2)
        # Ensure bed 4 (Room 3) is Available
        conn.execute("UPDATE rooms SET status = 'Available', is_active = 1 WHERE id = 3;")
        conn.execute("UPDATE beds SET status = 'Available' WHERE id = 4;")
        conn.commit()
        conn.close()

        # Execute transfer
        resp = self.client.post(
            "/api/v1/allocations/2/transfer",
            json={"to_bed_id": 4, "reason": "Transfer to quieter floor"},
            headers=self.admin_headers
        )
        self.assertEqual(resp.status_code, 200)
        new_alloc = resp.json()

        self.assertEqual(new_alloc["student_id"], 3)
        self.assertEqual(new_alloc["bed_id"], 4)
        self.assertEqual(new_alloc["allocation_status"], "Active")

        # Verify old allocation #2 is marked Transferred
        conn = get_db_connection()
        old_status = conn.execute("SELECT allocation_status FROM room_allocations WHERE id = 2;").fetchone()[0]
        self.assertEqual(old_status, "Transferred")

        # Verify old bed 2 is Available
        old_bed_status = conn.execute("SELECT status FROM beds WHERE id = 2;").fetchone()[0]
        self.assertEqual(old_bed_status, "Available")

        # Verify new bed 4 is Occupied
        new_bed_status = conn.execute("SELECT status FROM beds WHERE id = 4;").fetchone()[0]
        self.assertEqual(new_bed_status, "Occupied")
        conn.close()

    def test_16_checkout_lifecycle_and_history_preservation(self):
        """Verify check-out releases assigned bed and preserves historical record."""
        # Check out allocation 1 (Rohan, Bed 1)
        resp = self.client.post(
            "/api/v1/allocations/1/checkout",
            json={"checkout_date": "2026-10-31", "reason": "Completed Semester"},
            headers=self.admin_headers
        )
        self.assertEqual(resp.status_code, 200)
        data = resp.json()
        self.assertEqual(data["allocation_status"], "Vacated")
        self.assertEqual(data["checkout_date"], "2026-10-31")

        # Verify bed 1 is released
        conn = get_db_connection()
        b_status = conn.execute("SELECT status FROM beds WHERE id = 1;").fetchone()[0]
        self.assertEqual(b_status, "Available")

        # Verify history preservation
        history_resp = self.client.get("/api/v1/students/1/allocation-history", headers=self.admin_headers)
        self.assertEqual(history_resp.status_code, 200)
        hist = history_resp.json()
        self.assertTrue(len(hist) >= 1)
        statuses = [h["allocation_status"] for h in hist]
        self.assertIn("Vacated", statuses)
        conn.close()


if __name__ == "__main__":
    unittest.main()
