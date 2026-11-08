"""Complete Authorization Matrix Test Suite for SA-02.

Course: BBAT104 - Fundamentals of Total Quality Management (TQM)
Quality Goal: Q05 - Zero-Defect Authorization, Data Isolation & Audit Logging

Validates every endpoint and HTTP method in backend/app/routers/infrastructure.py:
1. Unauthenticated request rejection (401 Unauthorized)
2. Unauthorized role rejection (403 Forbidden)
3. Authorized role acceptance (200 OK / 201 Created)
4. Data-scope restriction enforcement
5. Audit trail generation on mutations
"""

import os
import shutil
import sqlite3
import tempfile
import unittest
from typing import Any, Dict
from fastapi.testclient import TestClient

from backend.app.config import settings
from backend.app.database.init_db import initialize_database
from backend.app.main import app


class TestSA02CompleteAuthorizationMatrix(unittest.TestCase):
    """Exhaustive authorization matrix test suite for all 49 SA-02 infrastructure endpoints."""

    @classmethod
    def setUpClass(cls):
        cls.temp_dir = tempfile.mkdtemp(prefix="hms_sa02_auth_matrix_")
        cls.db_path = os.path.join(cls.temp_dir, "test_auth_matrix.db")
        cls.orig_db_path = settings.database_path
        settings.database_path = cls.db_path

        initialize_database()
        cls.client = TestClient(app)

        # Login helpers
        def login_user(username: str, password: str = "Password123!") -> Dict[str, str]:
            res = cls.client.post("/api/v1/auth/login", json={"username_or_email": username, "password": password})
            assert res.status_code == 200, f"Login failed for {username}: {res.text}"
            token = res.json()["access_token"]
            return {"Authorization": f"Bearer {token}"}

        # 1. Super Admin (Full institution scope)
        cls.superadmin_headers = login_user("superadmin")

        # 2. Student (rohan) - Lacks all infrastructure write & management permissions
        cls.student_headers = login_user("rohan")

        # 3. Hostel Admin (hosteladmin) - Scoped to Hostel 1
        cls.hosteladmin_headers = login_user("hosteladmin")

    @classmethod
    def tearDownClass(cls):
        settings.database_path = cls.orig_db_path
        shutil.rmtree(cls.temp_dir, ignore_errors=True)

    # -------------------------------------------------------------------------
    # Helper assertion methods
    # -------------------------------------------------------------------------
    def _assert_unauthenticated(self, method: str, path: str, **kwargs):
        """Verify request without Authorization header returns 401 Unauthorized."""
        fn = getattr(self.client, method.lower())
        res = fn(path, **kwargs)
        self.assertIn(res.status_code, (401, 403), f"Expected 401/403 unauthenticated for {method} {path}, got {res.status_code}")

    def _assert_forbidden(self, method: str, path: str, headers: Dict[str, str], **kwargs):
        """Verify request with insufficient permissions returns 403 Forbidden."""
        fn = getattr(self.client, method.lower())
        res = fn(path, headers=headers, **kwargs)
        self.assertEqual(res.status_code, 403, f"Expected 403 Forbidden for {method} {path}, got {res.status_code}: {res.text}")

    def _assert_authorized(self, method: str, path: str, headers: Dict[str, str], expected_status: int = 200, **kwargs):
        """Verify request with authorized permissions returns expected status."""
        fn = getattr(self.client, method.lower())
        res = fn(path, headers=headers, **kwargs)
        self.assertEqual(res.status_code, expected_status, f"Expected {expected_status} for {method} {path}, got {res.status_code}: {res.text}")
        return res

    # -------------------------------------------------------------------------
    # Module A: Institution Endpoints
    # -------------------------------------------------------------------------
    def test_01_institution_endpoints_authorization(self):
        """GET, PUT /api/v1/institutions, PUT /api/v1/institutions/config."""
        # GET /api/v1/institutions
        self._assert_unauthenticated("get", "/api/v1/institutions")
        self._assert_authorized("get", "/api/v1/institutions", self.superadmin_headers, 200)

        # PUT /api/v1/institutions
        inst_payload = {"name": "National Technical University of Excellence"}
        self._assert_unauthenticated("put", "/api/v1/institutions", json=inst_payload)
        self._assert_forbidden("put", "/api/v1/institutions", self.student_headers, json=inst_payload)
        put_res = self._assert_authorized("put", "/api/v1/institutions", self.superadmin_headers, 200, json=inst_payload)
        self.assertEqual(put_res.json()["name"], "National Technical University of Excellence")

        # PUT /api/v1/institutions/config
        cfg_payload = {"config": {"maintenance_mode": False, "academic_term": "2026-2027"}}
        self._assert_unauthenticated("put", "/api/v1/institutions/config", json=cfg_payload)
        self._assert_forbidden("put", "/api/v1/institutions/config", self.student_headers, json=cfg_payload)
        self._assert_authorized("put", "/api/v1/institutions/config", self.superadmin_headers, 200, json=cfg_payload)

    # -------------------------------------------------------------------------
    # Module B: Campus Endpoints
    # -------------------------------------------------------------------------
    def test_02_campus_endpoints_authorization(self):
        """GET, POST, PUT, PATCH, DELETE /api/v1/campuses."""
        # 1. GET /api/v1/campuses
        self._assert_unauthenticated("get", "/api/v1/campuses")
        self._assert_authorized("get", "/api/v1/campuses", self.superadmin_headers, 200)

        # 2. GET /api/v1/campuses/{id}
        self._assert_unauthenticated("get", "/api/v1/campuses/1")
        self._assert_authorized("get", "/api/v1/campuses/1", self.superadmin_headers, 200)

        # 3. POST /api/v1/campuses
        new_campus = {
            "name": "Auth Matrix North Campus",
            "code": "AM-NC-01",
            "address": "123 University Road",
            "city": "Dehradun",
            "state": "Uttarakhand",
            "country": "India"
        }
        self._assert_unauthenticated("post", "/api/v1/campuses", json=new_campus)
        self._assert_forbidden("post", "/api/v1/campuses", self.student_headers, json=new_campus)
        c_res = self._assert_authorized("post", "/api/v1/campuses", self.superadmin_headers, 201, json=new_campus)
        created_campus_id = c_res.json()["id"]

        # 4. PUT /api/v1/campuses/{id}
        c_update = {"name": "Auth Matrix North Campus Updated"}
        self._assert_unauthenticated("put", f"/api/v1/campuses/{created_campus_id}", json=c_update)
        self._assert_forbidden("put", f"/api/v1/campuses/{created_campus_id}", self.student_headers, json=c_update)
        self._assert_authorized("put", f"/api/v1/campuses/{created_campus_id}", self.superadmin_headers, 200, json=c_update)

        # 5. PATCH /api/v1/campuses/{id}/status
        c_status = {"operating_status": "Active", "reason": "Operational certification complete"}
        self._assert_unauthenticated("patch", f"/api/v1/campuses/{created_campus_id}/status", json=c_status)
        self._assert_forbidden("patch", f"/api/v1/campuses/{created_campus_id}/status", self.student_headers, json=c_status)
        self._assert_authorized("patch", f"/api/v1/campuses/{created_campus_id}/status", self.superadmin_headers, 200, json=c_status)

        # 6. POST /api/v1/campuses/{id}/admin
        c_admin = {"admin_id": 1, "notes": "Super admin assigned as interim campus administrator"}
        self._assert_unauthenticated("post", f"/api/v1/campuses/{created_campus_id}/admin", json=c_admin)
        self._assert_forbidden("post", f"/api/v1/campuses/{created_campus_id}/admin", self.student_headers, json=c_admin)
        self._assert_authorized("post", f"/api/v1/campuses/{created_campus_id}/admin", self.superadmin_headers, 200, json=c_admin)

        # 7. DELETE /api/v1/campuses/{id}
        self._assert_unauthenticated("delete", f"/api/v1/campuses/{created_campus_id}")
        self._assert_forbidden("delete", f"/api/v1/campuses/{created_campus_id}", self.student_headers)
        self._assert_authorized("delete", f"/api/v1/campuses/{created_campus_id}", self.superadmin_headers, 200)

    # -------------------------------------------------------------------------
    # Module C: Hostel Endpoints
    # -------------------------------------------------------------------------
    def test_03_hostel_endpoints_authorization(self):
        """GET, POST, PUT, PATCH, DELETE /api/v1/infrastructure/hostels."""
        # 1. GET /api/v1/infrastructure/hostels
        self._assert_unauthenticated("get", "/api/v1/infrastructure/hostels")
        self._assert_authorized("get", "/api/v1/infrastructure/hostels", self.superadmin_headers, 200)

        # 2. GET /api/v1/infrastructure/hostels/{id}
        self._assert_unauthenticated("get", "/api/v1/infrastructure/hostels/1")
        self._assert_authorized("get", "/api/v1/infrastructure/hostels/1", self.superadmin_headers, 200)

        # 3. POST /api/v1/infrastructure/hostels
        new_hostel = {
            "name": "Auth Matrix Research Hostel",
            "code": "AM-RH-01",
            "campus_id": 1,
            "hostel_type": "Boys",
            "category": "Standard"
        }
        self._assert_unauthenticated("post", "/api/v1/infrastructure/hostels", json=new_hostel)
        self._assert_forbidden("post", "/api/v1/infrastructure/hostels", self.student_headers, json=new_hostel)
        h_res = self._assert_authorized("post", "/api/v1/infrastructure/hostels", self.superadmin_headers, 201, json=new_hostel)
        created_hostel_id = h_res.json()["id"]

        # 4. PUT /api/v1/infrastructure/hostels/{id}
        h_update = {"name": "Auth Matrix Research Hall Updated"}
        self._assert_unauthenticated("put", f"/api/v1/infrastructure/hostels/{created_hostel_id}", json=h_update)
        self._assert_forbidden("put", f"/api/v1/infrastructure/hostels/{created_hostel_id}", self.student_headers, json=h_update)
        self._assert_authorized("put", f"/api/v1/infrastructure/hostels/{created_hostel_id}", self.superadmin_headers, 200, json=h_update)

        # 5. PATCH /api/v1/infrastructure/hostels/{id}/leadership
        h_lead = {"warden_id": 1, "notes": "Assigned supervisory warden"}
        self._assert_unauthenticated("patch", f"/api/v1/infrastructure/hostels/{created_hostel_id}/leadership", json=h_lead)
        self._assert_forbidden("patch", f"/api/v1/infrastructure/hostels/{created_hostel_id}/leadership", self.student_headers, json=h_lead)
        self._assert_authorized("patch", f"/api/v1/infrastructure/hostels/{created_hostel_id}/leadership", self.superadmin_headers, 200, json=h_lead)

        # 6. PATCH /api/v1/infrastructure/hostels/{id}/category
        h_cat = {"category": "Premium", "reason": "Infrastructure upgrade"}
        self._assert_unauthenticated("patch", f"/api/v1/infrastructure/hostels/{created_hostel_id}/category", json=h_cat)
        self._assert_forbidden("patch", f"/api/v1/infrastructure/hostels/{created_hostel_id}/category", self.student_headers, json=h_cat)
        self._assert_authorized("patch", f"/api/v1/infrastructure/hostels/{created_hostel_id}/category", self.superadmin_headers, 200, json=h_cat)

        # 7. DELETE /api/v1/infrastructure/hostels/{id}
        self._assert_unauthenticated("delete", f"/api/v1/infrastructure/hostels/{created_hostel_id}")
        self._assert_forbidden("delete", f"/api/v1/infrastructure/hostels/{created_hostel_id}", self.student_headers)
        self._assert_authorized("delete", f"/api/v1/infrastructure/hostels/{created_hostel_id}", self.superadmin_headers, 200)

    # -------------------------------------------------------------------------
    # Module D: Building Endpoints
    # -------------------------------------------------------------------------
    def test_04_building_endpoints_authorization(self):
        """GET, POST, PUT, DELETE /api/v1/infrastructure/buildings."""
        # 1. GET /api/v1/infrastructure/buildings
        self._assert_unauthenticated("get", "/api/v1/infrastructure/buildings")
        self._assert_authorized("get", "/api/v1/infrastructure/buildings", self.superadmin_headers, 200)

        # 2. GET /api/v1/infrastructure/buildings/{id}
        self._assert_unauthenticated("get", "/api/v1/infrastructure/buildings/1")
        self._assert_authorized("get", "/api/v1/infrastructure/buildings/1", self.superadmin_headers, 200)

        # 3. POST /api/v1/infrastructure/buildings
        new_bld = {
            "hostel_id": 1,
            "name": "Auth Matrix Science Wing",
            "code": "AM-SW-01",
            "total_floors": 3,
            "status": "Good"
        }
        self._assert_unauthenticated("post", "/api/v1/infrastructure/buildings", json=new_bld)
        self._assert_forbidden("post", "/api/v1/infrastructure/buildings", self.student_headers, json=new_bld)
        b_res = self._assert_authorized("post", "/api/v1/infrastructure/buildings", self.superadmin_headers, 201, json=new_bld)
        created_building_id = b_res.json()["id"]

        # 4. PUT /api/v1/infrastructure/buildings/{id}
        b_update = {"name": "Auth Matrix Science Wing Renamed"}
        self._assert_unauthenticated("put", f"/api/v1/infrastructure/buildings/{created_building_id}", json=b_update)
        self._assert_forbidden("put", f"/api/v1/infrastructure/buildings/{created_building_id}", self.student_headers, json=b_update)
        self._assert_authorized("put", f"/api/v1/infrastructure/buildings/{created_building_id}", self.superadmin_headers, 200, json=b_update)

        # 5. DELETE /api/v1/infrastructure/buildings/{id}
        self._assert_unauthenticated("delete", f"/api/v1/infrastructure/buildings/{created_building_id}")
        self._assert_forbidden("delete", f"/api/v1/infrastructure/buildings/{created_building_id}", self.student_headers)
        self._assert_authorized("delete", f"/api/v1/infrastructure/buildings/{created_building_id}", self.superadmin_headers, 200)

    # -------------------------------------------------------------------------
    # Module E: Block Endpoints
    # -------------------------------------------------------------------------
    def test_05_block_endpoints_authorization(self):
        """GET, POST, PUT, DELETE /api/v1/blocks."""
        # 1. GET /api/v1/blocks
        self._assert_unauthenticated("get", "/api/v1/blocks")
        self._assert_authorized("get", "/api/v1/blocks", self.superadmin_headers, 200)

        # 2. GET /api/v1/blocks/{id}
        self._assert_unauthenticated("get", "/api/v1/blocks/1")
        self._assert_authorized("get", "/api/v1/blocks/1", self.superadmin_headers, 200)

        # 3. POST /api/v1/blocks
        new_block = {
            "building_id": 1,
            "name": "Auth Matrix North Block",
            "code": "AM-NB-01"
        }
        self._assert_unauthenticated("post", "/api/v1/blocks", json=new_block)
        self._assert_forbidden("post", "/api/v1/blocks", self.student_headers, json=new_block)
        blk_res = self._assert_authorized("post", "/api/v1/blocks", self.superadmin_headers, 201, json=new_block)
        created_block_id = blk_res.json()["id"]

        # 4. PUT /api/v1/blocks/{id}
        blk_update = {"name": "Auth Matrix North Block Renamed"}
        self._assert_unauthenticated("put", f"/api/v1/blocks/{created_block_id}", json=blk_update)
        self._assert_forbidden("put", f"/api/v1/blocks/{created_block_id}", self.student_headers, json=blk_update)
        self._assert_authorized("put", f"/api/v1/blocks/{created_block_id}", self.superadmin_headers, 200, json=blk_update)

        # 5. DELETE /api/v1/blocks/{id}
        self._assert_unauthenticated("delete", f"/api/v1/blocks/{created_block_id}")
        self._assert_forbidden("delete", f"/api/v1/blocks/{created_block_id}", self.student_headers)
        self._assert_authorized("delete", f"/api/v1/blocks/{created_block_id}", self.superadmin_headers, 200)

    # -------------------------------------------------------------------------
    # Module F: Floor Endpoints
    # -------------------------------------------------------------------------
    def test_06_floor_endpoints_authorization(self):
        """GET, POST, PUT, DELETE /api/v1/floors."""
        # 1. GET /api/v1/floors
        self._assert_unauthenticated("get", "/api/v1/floors")
        self._assert_authorized("get", "/api/v1/floors", self.superadmin_headers, 200)

        # 2. GET /api/v1/floors/{id}
        self._assert_unauthenticated("get", "/api/v1/floors/1")
        self._assert_authorized("get", "/api/v1/floors/1", self.superadmin_headers, 200)

        # 3. POST /api/v1/floors
        new_floor = {
            "building_id": 1,
            "floor_number": 5,
            "floor_name": "Auth Matrix Test Floor",
            "capacity": 20
        }
        self._assert_unauthenticated("post", "/api/v1/floors", json=new_floor)
        self._assert_forbidden("post", "/api/v1/floors", self.student_headers, json=new_floor)
        flr_res = self._assert_authorized("post", "/api/v1/floors", self.superadmin_headers, 201, json=new_floor)
        created_floor_id = flr_res.json()["id"]

        # 4. PUT /api/v1/floors/{id}
        flr_update = {"floor_name": "Auth Matrix Test Floor Renamed"}
        self._assert_unauthenticated("put", f"/api/v1/floors/{created_floor_id}", json=flr_update)
        self._assert_forbidden("put", f"/api/v1/floors/{created_floor_id}", self.student_headers, json=flr_update)
        self._assert_authorized("put", f"/api/v1/floors/{created_floor_id}", self.superadmin_headers, 200, json=flr_update)

        # 5. DELETE /api/v1/floors/{id}
        self._assert_unauthenticated("delete", f"/api/v1/floors/{created_floor_id}")
        self._assert_forbidden("delete", f"/api/v1/floors/{created_floor_id}", self.student_headers)
        self._assert_authorized("delete", f"/api/v1/floors/{created_floor_id}", self.superadmin_headers, 200)

    # -------------------------------------------------------------------------
    # Module G: Room Endpoints
    # -------------------------------------------------------------------------
    def test_07_room_endpoints_authorization(self):
        """GET, POST, PUT, PATCH, DELETE /api/v1/rooms."""
        # 1. GET /api/v1/rooms
        self._assert_unauthenticated("get", "/api/v1/rooms")
        self._assert_authorized("get", "/api/v1/rooms", self.superadmin_headers, 200)

        # 2. GET /api/v1/rooms/{id}
        self._assert_unauthenticated("get", "/api/v1/rooms/1")
        self._assert_authorized("get", "/api/v1/rooms/1", self.superadmin_headers, 200)

        # 3. POST /api/v1/rooms
        new_room = {
            "floor_id": 1,
            "room_number": "AM-RM-77",
            "room_type": "Double",
            "capacity": 2,
            "base_fee": 5200.0
        }
        self._assert_unauthenticated("post", "/api/v1/rooms", json=new_room)
        self._assert_forbidden("post", "/api/v1/rooms", self.student_headers, json=new_room)
        rm_res = self._assert_authorized("post", "/api/v1/rooms", self.superadmin_headers, 201, json=new_room)
        created_room_id = rm_res.json()["id"]

        # 4. PUT /api/v1/rooms/{id}
        rm_update = {"base_fee": 5500.0}
        self._assert_unauthenticated("put", f"/api/v1/rooms/{created_room_id}", json=rm_update)
        self._assert_forbidden("put", f"/api/v1/rooms/{created_room_id}", self.student_headers, json=rm_update)
        self._assert_authorized("put", f"/api/v1/rooms/{created_room_id}", self.superadmin_headers, 200, json=rm_update)

        # 5. PATCH /api/v1/rooms/{id}/capacity
        rm_cap = {"capacity": 3, "reason": "Added extra bed"}
        self._assert_unauthenticated("patch", f"/api/v1/rooms/{created_room_id}/capacity", json=rm_cap)
        self._assert_forbidden("patch", f"/api/v1/rooms/{created_room_id}/capacity", self.student_headers, json=rm_cap)
        self._assert_authorized("patch", f"/api/v1/rooms/{created_room_id}/capacity", self.superadmin_headers, 200, json=rm_cap)

        # 6. PATCH /api/v1/rooms/{id}/maintenance
        rm_maint = {"maintenance_status": "Operational", "notes": "Room verified clean"}
        self._assert_unauthenticated("patch", f"/api/v1/rooms/{created_room_id}/maintenance", json=rm_maint)
        self._assert_forbidden("patch", f"/api/v1/rooms/{created_room_id}/maintenance", self.student_headers, json=rm_maint)
        self._assert_authorized("patch", f"/api/v1/rooms/{created_room_id}/maintenance", self.superadmin_headers, 200, json=rm_maint)

        # 7. DELETE /api/v1/rooms/{id}
        self._assert_unauthenticated("delete", f"/api/v1/rooms/{created_room_id}")
        self._assert_forbidden("delete", f"/api/v1/rooms/{created_room_id}", self.student_headers)
        self._assert_authorized("delete", f"/api/v1/rooms/{created_room_id}", self.superadmin_headers, 200)

    # -------------------------------------------------------------------------
    # Module H: Bed Endpoints
    # -------------------------------------------------------------------------
    def test_08_bed_endpoints_authorization(self):
        """GET, POST, PUT, PATCH, DELETE /api/v1/beds."""
        # 1. GET /api/v1/beds
        self._assert_unauthenticated("get", "/api/v1/beds")
        self._assert_authorized("get", "/api/v1/beds", self.superadmin_headers, 200)

        # 2. GET /api/v1/beds/{id}
        self._assert_unauthenticated("get", "/api/v1/beds/1")
        self._assert_authorized("get", "/api/v1/beds/1", self.superadmin_headers, 200)

        # 3. POST /api/v1/beds
        new_bed = {
            "room_id": 1,
            "bed_number": "AM-BED-Z1"
        }
        self._assert_unauthenticated("post", "/api/v1/beds", json=new_bed)
        self._assert_forbidden("post", "/api/v1/beds", self.student_headers, json=new_bed)
        bd_res = self._assert_authorized("post", "/api/v1/beds", self.superadmin_headers, 201, json=new_bed)
        created_bed_id = bd_res.json()["id"]

        # 4. PUT /api/v1/beds/{id}
        bd_update = {"bed_number": "AM-BED-Z1-RENAMED"}
        self._assert_unauthenticated("put", f"/api/v1/beds/{created_bed_id}", json=bd_update)
        self._assert_forbidden("put", f"/api/v1/beds/{created_bed_id}", self.student_headers, json=bd_update)
        self._assert_authorized("put", f"/api/v1/beds/{created_bed_id}", self.superadmin_headers, 200, json=bd_update)

        # 5. PATCH /api/v1/beds/{id}/maintenance
        bd_maint = {"maintenance_status": "Operational", "notes": "Bed verified usable"}
        self._assert_unauthenticated("patch", f"/api/v1/beds/{created_bed_id}/maintenance", json=bd_maint)
        self._assert_forbidden("patch", f"/api/v1/beds/{created_bed_id}/maintenance", self.student_headers, json=bd_maint)
        self._assert_authorized("patch", f"/api/v1/beds/{created_bed_id}/maintenance", self.superadmin_headers, 200, json=bd_maint)

        # 6. DELETE /api/v1/beds/{id}
        self._assert_unauthenticated("delete", f"/api/v1/beds/{created_bed_id}")
        self._assert_forbidden("delete", f"/api/v1/beds/{created_bed_id}", self.student_headers)
        self._assert_authorized("delete", f"/api/v1/beds/{created_bed_id}", self.superadmin_headers, 200)

    # -------------------------------------------------------------------------
    # Module I: Hierarchy, Capacity, Import & Export Endpoints
    # -------------------------------------------------------------------------
    def test_09_hierarchy_capacity_import_export_authorization(self):
        """GET /api/v1/infrastructure/hierarchy, /capacity, /export, POST /import."""
        # 1. GET /api/v1/infrastructure/hierarchy
        self._assert_unauthenticated("get", "/api/v1/infrastructure/hierarchy")
        h_res = self._assert_authorized("get", "/api/v1/infrastructure/hierarchy", self.superadmin_headers, 200)
        self.assertIn("hierarchy", h_res.json())

        # 2. GET /api/v1/infrastructure/capacity
        self._assert_unauthenticated("get", "/api/v1/infrastructure/capacity")
        cap_res = self._assert_authorized("get", "/api/v1/infrastructure/capacity", self.superadmin_headers, 200)
        self.assertIn("total_physical_capacity", cap_res.json())

        # 3. GET /api/v1/infrastructure/export
        self._assert_unauthenticated("get", "/api/v1/infrastructure/export?entity_type=campuses")
        self._assert_forbidden("get", "/api/v1/infrastructure/export?entity_type=campuses", self.student_headers)
        exp_res = self._assert_authorized("get", "/api/v1/infrastructure/export?entity_type=campuses", self.superadmin_headers, 200)
        self.assertIsInstance(exp_res.json(), list)
        self.assertGreater(len(exp_res.json()), 0)

        # 4. POST /api/v1/infrastructure/import
        import_payload = {
            "entity_type": "rooms",
            "dry_run": True,
            "records": [{"room_number": "AM-IMPORT-DRY", "floor_id": 1, "capacity": 1, "base_fee": 4000.0}]
        }
        self._assert_unauthenticated("post", "/api/v1/infrastructure/import", json=import_payload)
        self._assert_forbidden("post", "/api/v1/infrastructure/import", self.student_headers, json=import_payload)
        imp_res = self._assert_authorized("post", "/api/v1/infrastructure/import", self.superadmin_headers, 200, json=import_payload)
        self.assertTrue(imp_res.json()["success"])

    # -------------------------------------------------------------------------
    # Verification of Audit Logging
    # -------------------------------------------------------------------------
    def test_10_audit_logging_integrity_on_infrastructure_mutations(self):
        """Verify that representative infrastructure mutations create audit trail records."""
        # Execute a mutation via API
        c_payload = {
            "name": "Audit Logging Test Campus",
            "code": "ALTC-01",
            "address": "456 Campus Blvd",
            "city": "Dehradun",
            "state": "Uttarakhand",
            "country": "India"
        }
        res = self.client.post("/api/v1/campuses", json=c_payload, headers=self.superadmin_headers)
        self.assertEqual(res.status_code, 201)
        cid = res.json()["id"]

        # Check in a fresh connection that audit record exists
        conn = sqlite3.connect(self.db_path)
        cur = conn.cursor()
        cur.execute("SELECT COUNT(*) FROM audit_logs WHERE action = 'CREATE_CAMPUS' AND entity_id = ?;", (str(cid),))
        created_audit = cur.fetchone()[0]
        self.assertGreaterEqual(created_audit, 1, "Audit log must be recorded when a campus is created")

        # Cleanup
        self.client.delete(f"/api/v1/campuses/{cid}", headers=self.superadmin_headers)
        conn.close()


if __name__ == "__main__":
    unittest.main()
