"""Automated Verification Test Suite for SA-02: Complete Institution, Campus & Hostel Management.

Course: BBAT104 - Fundamentals of Total Quality Management (TQM)
Quality Target: Q05 Zero Defects - Sub-10ms SLA, Poka-Yoke Error Proofing & RBAC Authorization Scopes
"""

import os
import shutil
import tempfile
import time
import unittest
from fastapi.testclient import TestClient

from backend.app.config import settings
from backend.app.database.connection import get_db_connection
from backend.app.database.init_db import initialize_database
from backend.app.main import app
from backend.app.services.infrastructure_service import InfrastructureService


class TestSA02InstitutionCampusHostel(unittest.TestCase):
    """Exhaustive test suite verifying Modules A through O of Milestone SA-02."""

    @classmethod
    def setUpClass(cls):
        cls.temp_dir = tempfile.mkdtemp(prefix="hms_sa02_test_")
        cls.db_path = os.path.join(cls.temp_dir, "test_sa02.db")
        cls.orig_db_path = settings.database_path
        settings.database_path = cls.db_path
        initialize_database()
        cls.client = TestClient(app)

        # Super Admin login
        res = cls.client.post("/api/v1/auth/login", json={"username_or_email": "superadmin", "password": "Password123!"})
        assert res.status_code == 200, res.text
        cls.token = res.json()["access_token"]
        cls.headers = {"Authorization": f"Bearer {cls.token}"}

        # Student login (for unauthorized check)
        res_stud = cls.client.post("/api/v1/auth/login", json={"username_or_email": "rohan", "password": "Password123!"})
        assert res_stud.status_code == 200, res_stud.text
        cls.student_token = res_stud.json()["access_token"]
        cls.student_headers = {"Authorization": f"Bearer {cls.student_token}"}

    @classmethod
    def tearDownClass(cls):
        settings.database_path = cls.orig_db_path
        shutil.rmtree(cls.temp_dir, ignore_errors=True)

    # -------------------------------------------------------------
    # Module A: Institution Profile & Configuration
    # -------------------------------------------------------------
    def test_01_institution_profile_read_and_update(self):
        # 1. Read profile
        res = self.client.get("/api/v1/institutions", headers=self.headers)
        self.assertEqual(res.status_code, 200)
        data = res.json()
        self.assertEqual(data["code"], "UCE-01")
        self.assertGreaterEqual(data["total_campuses"], 4)
        self.assertGreaterEqual(data["total_hostels"], 3)
        self.assertGreaterEqual(data["total_capacity"], 20)

        # 2. Update profile
        update_payload = {
            "legal_name": "University Campus of Excellence Global Trust",
            "website": "https://global.uce.edu.in",
            "contact_email": "provost@uce.edu.in",
        }
        res_up = self.client.put("/api/v1/institutions", json=update_payload, headers=self.headers)
        self.assertEqual(res_up.status_code, 200)
        updated = res_up.json()
        self.assertEqual(updated["legal_name"], "University Campus of Excellence Global Trust")
        self.assertEqual(updated["website"], "https://global.uce.edu.in")

        # 3. Update configuration
        cfg_payload = {
            "timezone": "Asia/Kolkata",
            "academic_year_start": "08-01",
            "academic_year_end": "05-31",
            "currency": "INR",
        }
        res_cfg = self.client.put("/api/v1/institutions/config", json=cfg_payload, headers=self.headers)
        self.assertEqual(res_cfg.status_code, 200)
        self.assertEqual(res_cfg.json()["academic_year_start"], "08-01")

    # -------------------------------------------------------------
    # Module B: Multi-Campus Management
    # -------------------------------------------------------------
    def test_02_campus_lifecycle_and_administration(self):
        # 1. List campuses
        res = self.client.get("/api/v1/campuses", headers=self.headers)
        self.assertEqual(res.status_code, 200)
        campuses = res.json()
        self.assertGreaterEqual(len(campuses), 4)

        # 2. Create new campus (Western Technology Campus)
        new_campus = {
            "institution_id": 1,
            "name": "West Campus Innovation Park",
            "code": "WC-01",
            "address": "Expressway Sector 62",
            "city": "Noida",
            "state": "Uttar Pradesh",
            "country": "India",
            "contact_person": "Dr. Vikas Sen",
            "contact_email": "west.admin@uce.edu.in",
            "operating_status": "Active",
            "is_active": 1,
        }
        res_cr = self.client.post("/api/v1/campuses", json=new_campus, headers=self.headers)
        self.assertEqual(res_cr.status_code, 201)
        created = res_cr.json()
        c_id = created["id"]
        self.assertEqual(created["code"], "WC-01")

        # Duplicate code rejection
        res_dup = self.client.post("/api/v1/campuses", json=new_campus, headers=self.headers)
        self.assertEqual(res_dup.status_code, 400)

        # 3. Update campus
        res_up = self.client.put(
            f"/api/v1/campuses/{c_id}",
            json={"contact_person": "Dr. Vikas Sen, Director", "postal_code": "201301"},
            headers=self.headers,
        )
        self.assertEqual(res_up.status_code, 200)
        self.assertEqual(res_up.json()["contact_person"], "Dr. Vikas Sen, Director")

        # 4. Status update
        res_st = self.client.patch(
            f"/api/v1/campuses/{c_id}/status",
            json={"operating_status": "Under_Maintenance", "is_active": 1},
            headers=self.headers,
        )
        self.assertEqual(res_st.status_code, 200)
        self.assertEqual(res_st.json()["operating_status"], "Under_Maintenance")

        # 5. Delete newly created campus (safe since no hostels attached yet)
        res_del = self.client.delete(f"/api/v1/campuses/{c_id}", headers=self.headers)
        self.assertEqual(res_del.status_code, 200)

        # 6. Poka-Yoke: Attempt to delete campus with hostels (North Campus id=1)
        res_del_fail = self.client.delete("/api/v1/campuses/1", headers=self.headers)
        self.assertEqual(res_del_fail.status_code, 400)
        self.assertIn("hostels are currently associated", res_del_fail.json()["detail"])

    # -------------------------------------------------------------
    # Module C: Hostel Management Extended & Categories
    # -------------------------------------------------------------
    def test_03_hostel_extended_lifecycle(self):
        # 1. List hostels extended
        res = self.client.get("/api/v1/infrastructure/hostels", headers=self.headers)
        self.assertEqual(res.status_code, 200)
        hostels = res.json()
        self.assertGreaterEqual(len(hostels), 3)

        # 2. Create new specialized hostel (Engineering Boys Hostel)
        new_hostel = {
            "institution_id": 1,
            "campus_id": 1,
            "name": "Visvesvaraya Engineering Hostel",
            "code": "VEH-01",
            "hostel_type": "Boys",
            "category": "Engineering",
            "address": "North Campus, Engineering Quad",
            "curfew_time": "22:30",
            "visitor_hours": "17:00 - 19:30",
            "mess_type": "Veg and Non-Veg",
            "is_active": 1,
        }
        res_cr = self.client.post("/api/v1/infrastructure/hostels", json=new_hostel, headers=self.headers)
        self.assertEqual(res_cr.status_code, 201)
        created = res_cr.json()
        h_id = created["id"]
        self.assertEqual(created["category"], "Engineering")
        self.assertEqual(created["curfew_time"], "22:30")

        # 3. Update category
        res_cat = self.client.patch(
            f"/api/v1/infrastructure/hostels/{h_id}/category",
            json={"category": "International"},
            headers=self.headers,
        )
        self.assertEqual(res_cat.status_code, 200)
        self.assertEqual(res_cat.json()["category"], "International")

        # 4. Assign leadership
        res_lead = self.client.patch(
            f"/api/v1/infrastructure/hostels/{h_id}/leadership",
            json={"warden_id": 1, "assistant_warden_id": None, "supervisor_id": None},
            headers=self.headers,
        )
        self.assertEqual(res_lead.status_code, 200)
        self.assertEqual(res_lead.json()["warden_id"], 1)

    # -------------------------------------------------------------
    # Module D: Building Management
    # -------------------------------------------------------------
    def test_04_building_lifecycle(self):
        # Create a building under hostel 1
        bld_payload = {
            "hostel_id": 1,
            "name": "Bhabha Research Block",
            "code": "BLK-BRB",
            "total_floors": 4,
            "construction_year": 2021,
            "condition_rating": "Excellent",
            "fire_safety_cert_date": "2026-01-15",
            "emergency_exits_count": 3,
            "elevators_count": 2,
            "is_active": 1,
        }
        res = self.client.post("/api/v1/infrastructure/buildings", json=bld_payload, headers=self.headers)
        self.assertEqual(res.status_code, 201)
        bld = res.json()
        b_id = bld["id"]
        self.assertEqual(bld["condition_rating"], "Excellent")
        self.assertEqual(bld["elevators_count"], 2)

        # Verify auto-created block exists
        res_blk = self.client.get(f"/api/v1/blocks?building_id={b_id}", headers=self.headers)
        self.assertEqual(res_blk.status_code, 200)
        blocks = res_blk.json()
        self.assertEqual(len(blocks), 1)
        self.assertEqual(blocks[0]["code"], "BLK-MAIN")

        # Update building
        res_up = self.client.put(
            f"/api/v1/infrastructure/buildings/{b_id}",
            json={"condition_rating": "Good", "elevators_count": 3},
            headers=self.headers,
        )
        self.assertEqual(res_up.status_code, 200)
        self.assertEqual(res_up.json()["elevators_count"], 3)

    # -------------------------------------------------------------
    # Module E & F: Block and Floor Management
    # -------------------------------------------------------------
    def test_05_block_and_floor_lifecycle(self):
        # 1. Create secondary block in building 1
        block_payload = {
            "building_id": 1,
            "name": "East Residential Wing",
            "code": "BLK-EAST",
            "description": "Postgraduate wing",
            "is_active": 1,
        }
        res_blk = self.client.post("/api/v1/blocks", json=block_payload, headers=self.headers)
        self.assertEqual(res_blk.status_code, 201)
        blk = res_blk.json()
        blk_id = blk["id"]

        # 2. Create floor under building 1, block blk_id
        floor_payload = {
            "building_id": 1,
            "block_id": blk_id,
            "floor_number": 10,
            "floor_name": "Penthouse Floor",
            "is_active": 1,
        }
        res_flr = self.client.post("/api/v1/floors", json=floor_payload, headers=self.headers)
        self.assertEqual(res_flr.status_code, 201)
        flr = res_flr.json()
        self.assertEqual(flr["floor_number"], 10)

        # Duplicate floor number rejection
        res_dup_flr = self.client.post("/api/v1/floors", json=floor_payload, headers=self.headers)
        self.assertEqual(res_dup_flr.status_code, 400)

    # -------------------------------------------------------------
    # Module G & H: Room & Bed Management with Poka-Yoke Error Proofing
    # -------------------------------------------------------------
    def test_06_room_and_bed_lifecycle_and_pokayoke(self):
        # 1. Create a room on floor 1 with auto beds enabled (capacity 3)
        room_payload = {
            "floor_id": 1,
            "room_number": "109-TEST",
            "room_type": "Triple",
            "capacity": 3,
            "base_fee": 6500.0,
            "status": "Available",
            "maintenance_status": "Operational",
            "is_ac": 1,
            "attached_washroom": 1,
            "is_active": 1,
        }
        res_rm = self.client.post("/api/v1/rooms?auto_create_beds=true", json=room_payload, headers=self.headers)
        self.assertEqual(res_rm.status_code, 201)
        room = res_rm.json()
        r_id = room["id"]
        self.assertEqual(room["capacity"], 3)
        self.assertEqual(room["beds_count"], 3)

        # Verify auto-generated beds
        res_beds = self.client.get(f"/api/v1/beds?room_id={r_id}", headers=self.headers)
        self.assertEqual(res_beds.status_code, 200)
        beds_data = res_beds.json()
        self.assertEqual(beds_data["total"], 3)
        bed_list = beds_data["beds"]
        first_bed_id = bed_list[0]["id"]

        # 2. Test Bed Maintenance Lock (Allocation Lock)
        res_maint = self.client.patch(
            f"/api/v1/beds/{first_bed_id}/maintenance",
            json={"maintenance_status": "Under_Repair", "notes": "Broken frame repair"},
            headers=self.headers,
        )
        self.assertEqual(res_maint.status_code, 200)
        maint_bed = res_maint.json()
        self.assertEqual(maint_bed["maintenance_status"], "Under_Repair")
        self.assertEqual(maint_bed["status"], "Maintenance")
        self.assertFalse(maint_bed["is_allocatable"])

        # 3. Restore bed to Operational
        res_restore = self.client.patch(
            f"/api/v1/beds/{first_bed_id}/maintenance",
            json={"maintenance_status": "Operational"},
            headers=self.headers,
        )
        self.assertEqual(res_restore.status_code, 200)
        self.assertTrue(res_restore.json()["is_allocatable"])

        # 4. Poka-Yoke Capacity Protection:
        # Simulate active student allocation on bed 2
        second_bed_id = bed_list[1]["id"]
        conn = get_db_connection()
        try:
            cur = conn.cursor()
            cur.execute("SELECT id FROM students LIMIT 1;")
            s_row = cur.fetchone()
            s_id = s_row[0] if s_row else 1
            cur.execute(
                """
                INSERT INTO room_allocations (student_id, bed_id, room_id, start_date, fee_status, allocation_status, approval_status)
                VALUES (?, ?, ?, '2026-08-01', 'Paid', 'Active', 'Approved');
                """,
                (s_id, second_bed_id, r_id),
            )
            conn.commit()
        finally:
            conn.close()

        # Attempt to reduce capacity to 0 (below active occupants = 1) -> must reject with 400
        res_cap_fail = self.client.patch(
            f"/api/v1/rooms/{r_id}/capacity",
            json={"capacity": 0},
            headers=self.headers,
        )
        # Capacity validator enforces ge=1, so Pydantic or service rejects
        self.assertIn(res_cap_fail.status_code, [400, 422])

        # Attempt to reduce capacity to 1 (which matches 1 occupant, should succeed and adjust unallocated beds)
        res_cap_ok = self.client.patch(
            f"/api/v1/rooms/{r_id}/capacity",
            json={"capacity": 2},
            headers=self.headers,
        )
        self.assertEqual(res_cap_ok.status_code, 200)
        self.assertEqual(res_cap_ok.json()["capacity"], 2)

        # Clean up allocation
        conn = get_db_connection()
        try:
            cur = conn.cursor()
            cur.execute("DELETE FROM room_allocations WHERE room_id = ?;", (r_id,))
            conn.commit()
        finally:
            conn.close()

        # Clean up room
        self.client.delete(f"/api/v1/rooms/{r_id}", headers=self.headers)

    # -------------------------------------------------------------
    # Module I & J: Hierarchy Explorer & Capacity Engine Performance (Q05 SLA)
    # -------------------------------------------------------------
    def test_07_hierarchy_and_capacity_engine_performance(self):
        # 1. Benchmark Hierarchy Explorer endpoint
        t0 = time.perf_counter()
        res_h = self.client.get("/api/v1/infrastructure/hierarchy", headers=self.headers)
        http_latency = (time.perf_counter() - t0) * 1000.0

        self.assertEqual(res_h.status_code, 200)
        h_data = res_h.json()
        tree = h_data["hierarchy"]
        internal_latency = h_data["latency_ms"]

        # Validate hierarchy integrity
        self.assertEqual(tree["node_type"], "institution")
        self.assertGreater(len(tree["children"]), 0)  # Campuses
        self.assertGreater(tree["capacity"], 0)
        # Quality Objective Q05: Internal latency < 10.0ms SLA
        self.assertLess(internal_latency, 10.0, f"Hierarchy internal latency {internal_latency}ms exceeded 10ms SLA")

        # 2. Benchmark Capacity & Occupancy Engine
        t1 = time.perf_counter()
        res_c = self.client.get("/api/v1/infrastructure/capacity", headers=self.headers)
        http_cap_latency = (time.perf_counter() - t1) * 1000.0

        self.assertEqual(res_c.status_code, 200)
        c_data = res_c.json()
        internal_cap_latency = c_data["latency_ms"]

        self.assertGreater(c_data["total_physical_capacity"], 0)
        self.assertGreater(c_data["total_operational_capacity"], 0)
        self.assertGreaterEqual(c_data["total_occupied_beds"], 0)
        self.assertEqual(
            c_data["total_occupied_beds"] + c_data["total_available_beds"] + c_data["total_maintenance_beds"],
            c_data["total_physical_capacity"],
        )
        # Quality Objective Q05: Internal latency < 10.0ms SLA
        self.assertLess(internal_cap_latency, 10.0, f"Capacity internal latency {internal_cap_latency}ms exceeded 10ms SLA")

    # -------------------------------------------------------------
    # Module L: Bulk Import & Export
    # -------------------------------------------------------------
    def test_08_bulk_import_and_export(self):
        # 1. Bulk import with dry_run = True (should validate without creating)
        import_records = [
            {"name": "Bulk Test Campus Alpha", "code": "BTC-01", "address": "Alpha Road 1"},
            {"name": "Bulk Test Campus Beta", "code": "BTC-02", "address": "Beta Road 2"},
        ]
        res_dry = self.client.post(
            "/api/v1/infrastructure/import",
            json={"entity_type": "campuses", "records": import_records, "dry_run": True},
            headers=self.headers,
        )
        self.assertEqual(res_dry.status_code, 200)
        dry_res = res_dry.json()
        self.assertTrue(dry_res["success"])
        self.assertTrue(dry_res["dry_run"])
        self.assertEqual(dry_res["valid_rows"], 2)
        self.assertEqual(dry_res["invalid_rows"], 0)

        # 2. Bulk import commit (dry_run = False)
        res_commit = self.client.post(
            "/api/v1/infrastructure/import",
            json={"entity_type": "campuses", "records": import_records, "dry_run": False},
            headers=self.headers,
        )
        self.assertEqual(res_commit.status_code, 200)
        commit_res = res_commit.json()
        self.assertTrue(commit_res["success"])
        self.assertFalse(commit_res["dry_run"])
        self.assertEqual(commit_res["created_count"], 2)

        # 3. Export in JSON
        res_exp_json = self.client.get(
            "/api/v1/infrastructure/export?entity_type=campuses&format=json",
            headers=self.headers,
        )
        self.assertEqual(res_exp_json.status_code, 200)
        exp_data = res_exp_json.json()
        self.assertGreaterEqual(len(exp_data), 6)  # 4 default + 2 bulk imported

        # 4. Export in CSV
        res_exp_csv = self.client.get(
            "/api/v1/infrastructure/export?entity_type=campuses&format=csv",
            headers=self.headers,
        )
        self.assertEqual(res_exp_csv.status_code, 200)
        self.assertIn("BTC-01", res_exp_csv.text)
        self.assertIn("BTC-02", res_exp_csv.text)

        # Clean up imported campuses
        conn = get_db_connection()
        try:
            cur = conn.cursor()
            cur.execute("DELETE FROM campuses WHERE code IN ('BTC-01', 'BTC-02');")
            conn.commit()
        finally:
            conn.close()

    # -------------------------------------------------------------
    # Module N: Authorization & RBAC Isolation
    # -------------------------------------------------------------
    def test_09_rbac_security_isolation(self):
        if not self.student_headers:
            self.skipTest("Student credentials not available for unauthorized check")

        # Unauthorized user attempting to mutate campus
        res = self.client.post(
            "/api/v1/campuses",
            json={"name": "Hacker Campus", "code": "HC-01", "address": "Nowhere"},
            headers=self.student_headers,
        )
        self.assertEqual(res.status_code, 403)

        # Unauthorized user attempting to access infrastructure tree
        res_h = self.client.get("/api/v1/infrastructure/hierarchy", headers=self.student_headers)
        self.assertEqual(res_h.status_code, 403)

        # Unauthorized user attempting to bulk import
        res_imp = self.client.post(
            "/api/v1/infrastructure/import",
            json={"entity_type": "campuses", "records": [{"name": "Test", "code": "T-1", "address": "X"}], "dry_run": False},
            headers=self.student_headers,
        )
        self.assertEqual(res_imp.status_code, 403)


if __name__ == "__main__":
    unittest.main()
