"""Area B Test Suite: Concurrency, Transaction Safety & Allocation Race Conditions (SA-02).

Course: BBAT104 - Fundamentals of Total Quality Management (TQM)
Quality Goal: Q05 - Zero-Defect Concurrency Protection & Poka-Yoke Error Proofing
"""

import concurrent.futures
import os
import shutil
import sqlite3
import tempfile
import unittest
from backend.app.database.migrations import run_migrations
from backend.app.database.seeder import seed_database
from backend.app.models.allocation_dto import AllocationCreate
from backend.app.models.infrastructure_dto import (
    BedCreate,
    BulkImportRequest,
    RoomCapacityUpdate,
    RoomCreate,
)
from backend.app.services.allocation_service import AllocationService
from backend.app.services.infrastructure_service import InfrastructureService
from fastapi import HTTPException


class TestSA02ConcurrencyAndTransactions(unittest.TestCase):
    """Rigorous concurrent tests using real independent SQLite threads and connections."""

    def setUp(self):
        self.temp_dir = tempfile.mkdtemp(prefix="hms_concurrency_")
        self.db_path = os.path.join(self.temp_dir, "concurrency_hms.db")

        # Initialize and seed test database
        conn = sqlite3.connect(self.db_path)
        conn.execute("PRAGMA foreign_keys = ON;")
        conn.execute("PRAGMA journal_mode = WAL;")
        conn.execute("PRAGMA busy_timeout = 5000;")
        run_migrations(conn)
        seed_database(conn)
        conn.close()

    def tearDown(self):
        shutil.rmtree(self.temp_dir, ignore_errors=True)

    def _get_worker_conn(self) -> sqlite3.Connection:
        conn = sqlite3.connect(self.db_path, timeout=10.0, check_same_thread=False)
        conn.row_factory = sqlite3.Row
        conn.execute("PRAGMA foreign_keys = ON;")
        conn.execute("PRAGMA journal_mode = WAL;")
        conn.execute("PRAGMA busy_timeout = 5000;")
        return conn

    def test_01_simultaneous_allocation_same_bed_contention(self):
        """10 concurrent threads attempt to allocate the exact same available bed.

        Assert: Exactly 1 succeeds, 9 fail with 409 Conflict, 0 duplicate active allocations.
        """
        # Pick an unallocated bed in Hostel 1
        setup_conn = self._get_worker_conn()
        cursor = setup_conn.cursor()
        cursor.execute("""
            SELECT id FROM beds 
            WHERE status = 'Available' AND is_active = 1 
            AND id NOT IN (SELECT bed_id FROM room_allocations WHERE allocation_status = 'Active')
            LIMIT 1;
        """)
        target_bed_id = cursor.fetchone()[0]

        # Create 10 dedicated male students without existing allocations
        student_ids = []
        for i in range(10):
            s_code = f"STU-CONCUR-{i:03d}"
            cursor.execute(
                "INSERT INTO students (student_id, first_name, last_name, gender, email, phone, status, branch, academic_year, admission_date) VALUES (?, 'Test', ?, 'Male', ?, '9999999999', 'Active', 'CSE', 1, '2026-08-01');",
                (s_code, f"Student{i}", f"testconcur{i}@univ.edu")
            )
            student_ids.append(s_code)
        setup_conn.commit()
        setup_conn.close()

        results = {"success": 0, "conflicts": 0, "errors": []}

        def worker_allocate(student_id):
            conn = self._get_worker_conn()
            try:
                dto = AllocationCreate(
                    student_id=student_id,
                    bed_id=target_bed_id,
                    start_date="2026-09-01",
                    fee_status="Pending"
                )
                AllocationService.create_allocation(conn, dto, allocated_by_user_id=1)
                return "SUCCESS"
            except HTTPException as exc:
                if exc.status_code in (400, 409) and ("allocated" in exc.detail.lower() or "available" in exc.detail.lower() or "conflict" in exc.detail.lower() or "capacity" in exc.detail.lower()):
                    return "CONFLICT"
                return f"HTTP_{exc.status_code}: {exc.detail}"
            except Exception as e:
                return f"EXCEPTION: {e}"
            finally:
                conn.close()

        with concurrent.futures.ThreadPoolExecutor(max_workers=10) as executor:
            futures = [executor.submit(worker_allocate, s_id) for s_id in student_ids[:10]]
            for future in concurrent.futures.as_completed(futures):
                res = future.result()
                if res == "SUCCESS":
                    results["success"] += 1
                elif res == "CONFLICT":
                    results["conflicts"] += 1
                else:
                    results["errors"].append(res)

        # Assertions
        self.assertEqual(results["success"], 1, "Exactly one concurrent worker must succeed in allocating the bed")
        self.assertEqual(results["conflicts"], 9, "All 9 concurrent contending workers must be rejected with 409 Conflict")
        self.assertEqual(len(results["errors"]), 0, f"No unexpected exceptions allowed: {results['errors']}")

        # Verify physical database integrity
        verify_conn = self._get_worker_conn()
        c = verify_conn.cursor()
        c.execute("SELECT COUNT(*) FROM room_allocations WHERE bed_id = ? AND allocation_status = 'Active';", (target_bed_id,))
        active_alloc_count = c.fetchone()[0]
        self.assertEqual(active_alloc_count, 1, "Database must have exactly 1 active allocation for the contested bed")

        # Check PRAGMA integrity
        c.execute("PRAGMA integrity_check;")
        self.assertEqual(c.fetchone()[0], "ok")
        verify_conn.close()

    def test_02_simultaneous_allocation_single_capacity_room(self):
        """Create a room with capacity=1 and two physical beds. Two concurrent workers attempt to allocate Bed A and Bed B.

        Assert: Exactly 1 succeeds, the second is rejected with 409 Conflict (Room reached maximum capacity), room capacity is not exceeded.
        """
        setup_conn = self._get_worker_conn()
        cursor = setup_conn.cursor()

        # Create isolated room with capacity=1
        r_row = InfrastructureService.create_room(
            setup_conn,
            RoomCreate(
                floor_id=1,
                room_number="R-CONC-01",
                room_type="Single",
                capacity=1,
                base_fee=6000.0
            ),
            auto_create_beds=False
        )
        test_room_id = r_row["id"]

        # Insert two beds into this capacity=1 room
        b1 = InfrastructureService.create_bed(setup_conn, BedCreate(room_id=test_room_id, bed_number="RCONC-A"))
        b2 = InfrastructureService.create_bed(setup_conn, BedCreate(room_id=test_room_id, bed_number="RCONC-B"))

        # Create two eligible active students
        setup_conn.execute("INSERT INTO students (student_id, first_name, last_name, gender, email, phone, status, branch, academic_year, admission_date) VALUES ('STU-C1', 'C1', 'User', 'Male', 'c1@univ.edu', '9999999901', 'Active', 'ME', 1, '2026-08-01');")
        setup_conn.execute("INSERT INTO students (student_id, first_name, last_name, gender, email, phone, status, branch, academic_year, admission_date) VALUES ('STU-C2', 'C2', 'User', 'Male', 'c2@univ.edu', '9999999902', 'Active', 'ME', 1, '2026-08-01');")
        setup_conn.commit()
        setup_conn.close()

        results = {"success": 0, "conflicts": 0, "errors": []}

        def worker_alloc(student_id, bed_id):
            conn = self._get_worker_conn()
            try:
                dto = AllocationCreate(
                    student_id=student_id,
                    bed_id=bed_id,
                    start_date="2026-09-01",
                    fee_status="Pending"
                )
                AllocationService.create_allocation(conn, dto, allocated_by_user_id=1)
                return "SUCCESS"
            except HTTPException as exc:
                if exc.status_code in (400, 409) and "capacity" in exc.detail.lower():
                    return "CONFLICT"
                return f"HTTP_{exc.status_code}: {exc.detail}"
            except Exception as e:
                return f"EXCEPTION: {e}"
            finally:
                conn.close()

        with concurrent.futures.ThreadPoolExecutor(max_workers=2) as executor:
            f1 = executor.submit(worker_alloc, "STU-C1", b1["id"])
            f2 = executor.submit(worker_alloc, "STU-C2", b2["id"])
            for fut in (f1, f2):
                res = fut.result()
                if res == "SUCCESS":
                    results["success"] += 1
                elif res == "CONFLICT":
                    results["conflicts"] += 1
                else:
                    results["errors"].append(res)

        self.assertEqual(results["success"], 1, "Only 1 worker must succeed when room capacity is 1")
        self.assertEqual(results["conflicts"], 1, "The competing worker must be rejected with capacity conflict")

        # Verify active occupancy in DB
        verify_conn = self._get_worker_conn()
        c = verify_conn.cursor()
        c.execute("SELECT COUNT(*) FROM room_allocations WHERE room_id = ? AND allocation_status = 'Active';", (test_room_id,))
        active_in_room = c.fetchone()[0]
        self.assertEqual(active_in_room, 1, "Room occupancy must strictly equal 1")
        verify_conn.close()

    def test_03_concurrent_capacity_reduction_and_active_occupancy(self):
        """Poka-Yoke: Attempt to reduce room capacity below active occupants must be strictly blocked."""
        setup_conn = self._get_worker_conn()

        # Create room with capacity=2 and allocate 2 beds
        r_row = InfrastructureService.create_room(
            setup_conn,
            RoomCreate(
                floor_id=1,
                room_number="R-CAP-02",
                room_type="Double",
                capacity=2,
                base_fee=5000.0
            ),
            auto_create_beds=True
        )
        room_id = r_row["id"]
        beds = InfrastructureService.list_beds(setup_conn, room_id=room_id)["beds"]

        setup_conn.execute("INSERT INTO students (student_id, first_name, last_name, gender, email, phone, status, branch, academic_year, admission_date) VALUES ('STU-CAP1', 'Cap1', 'User', 'Male', 'cap1@univ.edu', '9999999911', 'Active', 'EE', 1, '2026-08-01');")
        setup_conn.execute("INSERT INTO students (student_id, first_name, last_name, gender, email, phone, status, branch, academic_year, admission_date) VALUES ('STU-CAP2', 'Cap2', 'User', 'Male', 'cap2@univ.edu', '9999999912', 'Active', 'EE', 1, '2026-08-01');")
        setup_conn.commit()

        # Allocate both beds
        AllocationService.create_allocation(setup_conn, AllocationCreate(student_id="STU-CAP1", bed_id=beds[0]["id"], start_date="2026-09-01"))
        AllocationService.create_allocation(setup_conn, AllocationCreate(student_id="STU-CAP2", bed_id=beds[1]["id"], start_date="2026-09-01"))
        setup_conn.close()

        # Concurrently attempt to reduce capacity to 1
        worker_conn = self._get_worker_conn()
        try:
            with self.assertRaises(HTTPException) as ctx:
                InfrastructureService.update_room_capacity(worker_conn, room_id=room_id, new_capacity=1)
            self.assertEqual(ctx.exception.status_code, 400)
            self.assertIn("Cannot reduce room capacity to 1", ctx.exception.detail)
            self.assertIn("2 active students are allocated", ctx.exception.detail)
        finally:
            worker_conn.close()

    def test_04_concurrent_bulk_import_and_savepoint_rollback(self):
        """Verify bulk import handles transaction atomicity and rolls back completely on constraint failure."""
        conn = self._get_worker_conn()

        # Part 1: Pre-flight validation rejection (invalid parent reference)
        invalid_hostel_records = [
            {"name": "Valid Hostel Alpha", "code": "H-VAL-01", "campus_id": 1, "hostel_type": "Boys"},
            {"name": "Valid Hostel Beta", "code": "H-VAL-02", "campus_id": 1, "hostel_type": "Boys"},
            {"name": "Invalid Hostel Gamma", "code": "H-INV-03", "campus_id": 99999, "hostel_type": "Boys"},  # Non-existent campus!
        ]

        result = InfrastructureService.bulk_import(conn, entity_type="hostels", records=invalid_hostel_records, dry_run=False)

        self.assertFalse(result["success"])
        self.assertGreater(len(result["errors"]), 0)
        self.assertIn("campus_id 99999 does not exist", result["errors"][0])

        # Verify that atomic rollback / preflight abort prevented insertion of records 1 and 2
        cursor = conn.cursor()
        cursor.execute("SELECT COUNT(*) FROM hostels WHERE code IN ('H-VAL-01', 'H-VAL-02', 'H-INV-03');")
        inserted_count = cursor.fetchone()[0]
        self.assertEqual(inserted_count, 0, "Pre-flight rejection must prevent partial imports on invalid relations")

        # Part 2: Runtime atomic SAVEPOINT rollback on SQL constraint collision
        colliding_room_records = [
            {"room_number": "R-ATOMIC-01", "floor_id": 1, "capacity": 2, "base_fee": 5000.0},
            {"room_number": "R-ATOMIC-01", "floor_id": 1, "capacity": 2, "base_fee": 5000.0},  # Duplicate room_number on floor 1!
        ]

        with self.assertRaises(HTTPException) as ctx:
            InfrastructureService.bulk_import(conn, entity_type="rooms", records=colliding_room_records, dry_run=False)

        self.assertEqual(ctx.exception.status_code, 500)
        self.assertIn("rolled back", ctx.exception.detail)

        cursor.execute("SELECT COUNT(*) FROM rooms WHERE room_number = 'R-ATOMIC-01';")
        self.assertEqual(cursor.fetchone()[0], 0, "Atomic SAVEPOINT rollback must ensure 0 rooms inserted after constraint violation")
        conn.close()


if __name__ == "__main__":
    unittest.main()
