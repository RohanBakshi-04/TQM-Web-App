"""Extended Concurrency Proof Test Suite for SA-02.

Course: BBAT104 - Fundamentals of Total Quality Management (TQM)
Quality Goal: Q05 - Zero-Defect Concurrency Protection & Poka-Yoke Error Proofing

Test Scenarios:
1. Repeated 10-worker same-bed allocation races across multiple sequential trials.
2. Concurrent final-bed allocation under room capacity limits.
3. Concurrent capacity updates vs concurrent allocations.
4. Concurrent room and bed status changes vs allocations.
5. Concurrent bulk imports on independent connections.
6. Multiple simultaneous database writers under WAL mode.
7. Multi-process contention across separate OS processes.
"""

import concurrent.futures
import multiprocessing
import os
import shutil
import sqlite3
import tempfile
import threading
import unittest
from typing import List, Tuple

from fastapi import HTTPException

from backend.app.database.migrations import run_migrations
from backend.app.database.seeder import seed_database
from backend.app.models.allocation_dto import AllocationCreate
from backend.app.models.infrastructure_dto import (
    BedMaintenanceUpdate,
    RoomCapacityUpdate,
    RoomCreate,
)
from backend.app.services.allocation_service import AllocationService
from backend.app.services.infrastructure_service import InfrastructureService


def _multiprocess_writer_target(db_path: str, worker_id: int, iterations: int, result_queue: multiprocessing.Queue):
    """Top-level worker function compatible with Windows multiprocessing spawn."""
    try:
        conn = sqlite3.connect(db_path, timeout=20.0)
        conn.execute("PRAGMA journal_mode = WAL;")
        conn.execute("PRAGMA busy_timeout = 15000;")
        cursor = conn.cursor()
        for i in range(iterations):
            cursor.execute(
                """
                INSERT INTO audit_logs (user_id, username, action, entity_name, entity_id, details)
                VALUES (1, ?, 'MP_CONCURRENT_WRITE', 'infrastructure', ?, ?);
                """,
                (f"mp_worker_{worker_id}", f"ENTITY-{worker_id}-{i}", f"Multi-process write {i}")
            )
            conn.commit()
        conn.close()
        result_queue.put((worker_id, True, None))
    except Exception as exc:
        result_queue.put((worker_id, False, str(exc)))


class TestSA02ExtendedConcurrencyProof(unittest.TestCase):
    """Extended real-concurrency test suite validating zero race conditions and zero corruption."""

    def setUp(self):
        self.temp_dir = tempfile.mkdtemp(prefix="hms_ext_concur_")
        self.db_path = os.path.join(self.temp_dir, "ext_concurrency.db")

        conn = sqlite3.connect(self.db_path)
        conn.execute("PRAGMA foreign_keys = ON;")
        conn.execute("PRAGMA journal_mode = WAL;")
        conn.execute("PRAGMA busy_timeout = 10000;")
        run_migrations(conn)
        seed_database(conn)
        conn.close()

    def tearDown(self):
        shutil.rmtree(self.temp_dir, ignore_errors=True)

    def _get_worker_conn(self) -> sqlite3.Connection:
        conn = sqlite3.connect(self.db_path, timeout=15.0, check_same_thread=False)
        conn.row_factory = sqlite3.Row
        conn.execute("PRAGMA foreign_keys = ON;")
        conn.execute("PRAGMA journal_mode = WAL;")
        conn.execute("PRAGMA busy_timeout = 10000;")
        return conn

    def test_01_repeated_10_worker_same_bed_allocation_races(self):
        """Repeated 10-worker same-bed allocation races across 3 sequential rounds.

        In each round, 10 workers using a synchronization barrier race to allocate the EXACT
        same available bed simultaneously. Exactly 1 must win, and exactly 9 must receive 409 Conflict.
        """
        setup_conn = self._get_worker_conn()
        cursor = setup_conn.cursor()

        # Create a test room with 3 beds in Hostel 1 (Boys)
        room_row = InfrastructureService.create_room(
            setup_conn,
            RoomCreate(
                floor_id=1,
                room_number="R-RACE-100",
                room_type="Triple",
                capacity=3,
                base_fee=5000.0
            ),
            auto_create_beds=True
        )
        room_id = room_row["id"]
        bed_list = InfrastructureService.list_beds(setup_conn, room_id=room_id)["beds"]
        setup_conn.close()

        # Run 3 consecutive rounds, targeting each of the 3 beds in turn
        for round_idx in range(3):
            target_bed = bed_list[round_idx]
            target_bed_id = target_bed["id"]

            # Create 10 distinct male students for this round
            reg_conn = self._get_worker_conn()
            round_students = []
            for s_idx in range(10):
                s_code = f"STU-RACE-R{round_idx}-S{s_idx:02d}"
                reg_conn.execute(
                    """
                    INSERT INTO students (student_id, first_name, last_name, gender, email, phone, status, branch, academic_year, admission_date)
                    VALUES (?, 'Race', ?, 'Male', ?, '9876543210', 'Active', 'CSE', 1, '2026-08-01');
                    """,
                    (s_code, f"Candidate-{round_idx}-{s_idx}", f"race_r{round_idx}_{s_idx}@univ.edu")
                )
                round_students.append(s_code)
            reg_conn.commit()
            reg_conn.close()

            # Execute simultaneous 10-worker race with a synchronization barrier
            barrier = threading.Barrier(10)
            results = []

            def worker_race(student_id: str):
                w_conn = self._get_worker_conn()
                try:
                    barrier.wait(timeout=5.0)
                    alloc = AllocationService.create_allocation(
                        w_conn,
                        AllocationCreate(
                            student_id=student_id,
                            bed_id=target_bed_id,
                            start_date="2026-09-01"
                        )
                    )
                    return ("SUCCESS", alloc["id"])
                except HTTPException as he:
                    return ("HTTP_ERROR", he.status_code, he.detail)
                except Exception as ex:
                    return ("UNEXPECTED_ERROR", str(ex))
                finally:
                    w_conn.close()

            with concurrent.futures.ThreadPoolExecutor(max_workers=10) as executor:
                futures = [executor.submit(worker_race, sid) for sid in round_students]
                for fut in concurrent.futures.as_completed(futures):
                    results.append(fut.result())

            successes = [r for r in results if r[0] == "SUCCESS"]
            http_errors = [r for r in results if r[0] == "HTTP_ERROR"]
            unexpected = [r for r in results if r[0] == "UNEXPECTED_ERROR"]

            self.assertEqual(len(unexpected), 0, f"Round {round_idx}: Unexpected crashes occurred: {unexpected}")
            self.assertEqual(len(successes), 1, f"Round {round_idx}: Exactly one worker must win the bed")
            self.assertEqual(len(http_errors), 9, f"Round {round_idx}: Exactly nine workers must be rejected")

            # Verify all rejections were 409 Conflict
            for err in http_errors:
                self.assertEqual(err[1], 409, f"Round {round_idx}: Rejections must be HTTP 409 Conflict")

            # Verify in database that exactly 1 active allocation exists for this bed
            ver_conn = self._get_worker_conn()
            v_cur = ver_conn.cursor()
            v_cur.execute(
                "SELECT COUNT(*) FROM room_allocations WHERE bed_id = ? AND allocation_status = 'Active';",
                (target_bed_id,)
            )
            self.assertEqual(v_cur.fetchone()[0], 1)

            v_cur.execute("SELECT status FROM beds WHERE id = ?;", (target_bed_id,))
            self.assertEqual(v_cur.fetchone()[0], "Occupied")
            ver_conn.close()

    def test_02_concurrent_final_bed_allocation(self):
        """Room has capacity=2 with 1 active student. 6 workers race for the final remaining bed.

        Assert: Exactly 1 worker gets the bed, 5 fail with 409. Room status updates to 'Full'.
        """
        setup_conn = self._get_worker_conn()
        room_row = InfrastructureService.create_room(
            setup_conn,
            RoomCreate(
                floor_id=1,
                room_number="R-FINAL-BED",
                room_type="Double",
                capacity=2,
                base_fee=5500.0
            ),
            auto_create_beds=True
        )
        room_id = room_row["id"]
        beds = InfrastructureService.list_beds(setup_conn, room_id=room_id)["beds"]
        bed_1, bed_2 = beds[0]["id"], beds[1]["id"]

        # Pre-allocate Bed 1 to student 0
        setup_conn.execute(
            """
            INSERT INTO students (student_id, first_name, last_name, gender, email, phone, status, branch, academic_year, admission_date)
            VALUES ('STU-PRE-ALLOC', 'Initial', 'Resident', 'Male', 'init_res@univ.edu', '9999999001', 'Active', 'ME', 2, '2025-08-01');
            """
        )
        setup_conn.commit()
        AllocationService.create_allocation(
            setup_conn,
            AllocationCreate(student_id="STU-PRE-ALLOC", bed_id=bed_1, start_date="2026-09-01")
        )

        # Create 6 candidate students for the final bed
        candidates = []
        for i in range(6):
            sid = f"STU-FINAL-CAND-{i}"
            setup_conn.execute(
                """
                INSERT INTO students (student_id, first_name, last_name, gender, email, phone, status, branch, academic_year, admission_date)
                VALUES (?, 'Candidate', ?, 'Male', ?, '9999999002', 'Active', 'ME', 2, '2025-08-01');
                """,
                (sid, f"Final-{i}", f"final_{i}@univ.edu")
            )
            candidates.append(sid)
        setup_conn.commit()
        setup_conn.close()

        # Concurrent 6-worker race for bed_2
        barrier = threading.Barrier(6)
        results = []

        def worker_final(sid: str):
            w_conn = self._get_worker_conn()
            try:
                barrier.wait(timeout=5.0)
                alloc = AllocationService.create_allocation(
                    w_conn,
                    AllocationCreate(student_id=sid, bed_id=bed_2, start_date="2026-09-01")
                )
                return ("SUCCESS", alloc["id"])
            except HTTPException as he:
                return ("HTTP_ERROR", he.status_code, he.detail)
            except Exception as ex:
                return ("UNEXPECTED_ERROR", str(ex))
            finally:
                w_conn.close()

        with concurrent.futures.ThreadPoolExecutor(max_workers=6) as executor:
            futures = [executor.submit(worker_final, sid) for sid in candidates]
            for fut in concurrent.futures.as_completed(futures):
                results.append(fut.result())

        successes = [r for r in results if r[0] == "SUCCESS"]
        errors = [r for r in results if r[0] == "HTTP_ERROR"]
        self.assertEqual(len(successes), 1)
        self.assertEqual(len(errors), 5)
        for err in errors:
            self.assertEqual(err[1], 409)

        # Verify room status is Full and occupancy is 2
        chk_conn = self._get_worker_conn()
        r_info = InfrastructureService.get_room_by_id(chk_conn, room_id)
        self.assertEqual(r_info["occupied_beds"], 2)
        self.assertEqual(r_info["status"], "Full")
        chk_conn.close()

    def test_03_concurrent_capacity_updates_and_allocations(self):
        """Worker 1 reduces room capacity while Worker 2 allocates the remaining bed.

        Assert: TOCTOU race resolution ensures room occupancy NEVER exceeds capacity.
        Either capacity update fails (because occupancy changed), or allocation fails.
        """
        setup_conn = self._get_worker_conn()
        room_row = InfrastructureService.create_room(
            setup_conn,
            RoomCreate(
                floor_id=1,
                room_number="R-CAP-RACE",
                room_type="Double",
                capacity=2,
                base_fee=5000.0
            ),
            auto_create_beds=True
        )
        room_id = room_row["id"]
        beds = InfrastructureService.list_beds(setup_conn, room_id=room_id)["beds"]
        bed_1, bed_2 = beds[0]["id"], beds[1]["id"]

        setup_conn.execute(
            """
            INSERT INTO students (student_id, first_name, last_name, gender, email, phone, status, branch, academic_year, admission_date)
            VALUES ('STU-CAP-OCC1', 'First', 'Occupant', 'Male', 'cap_occ1@univ.edu', '9999999003', 'Active', 'EE', 1, '2026-08-01'),
                   ('STU-CAP-CAND2', 'Second', 'Candidate', 'Male', 'cap_cand2@univ.edu', '9999999004', 'Active', 'EE', 1, '2026-08-01');
            """
        )
        setup_conn.commit()

        # Pre-allocate bed_1 (room now has 1 occupant, capacity 2)
        AllocationService.create_allocation(
            setup_conn,
            AllocationCreate(student_id="STU-CAP-OCC1", bed_id=bed_1, start_date="2026-09-01")
        )
        setup_conn.close()

        barrier = threading.Barrier(2)

        def worker_reduce_capacity():
            w_conn = self._get_worker_conn()
            try:
                barrier.wait(timeout=5.0)
                # Attempt to shrink capacity from 2 to 1
                return ("CAPACITY_SUCCESS", InfrastructureService.update_room_capacity(w_conn, room_id=room_id, new_capacity=1))
            except HTTPException as he:
                return ("CAPACITY_REJECTED", he.status_code, he.detail)
            except Exception as ex:
                return ("CAPACITY_CRASH", str(ex))
            finally:
                w_conn.close()

        def worker_allocate_bed():
            w_conn = self._get_worker_conn()
            try:
                barrier.wait(timeout=5.0)
                # Attempt to allocate the second bed
                return ("ALLOC_SUCCESS", AllocationService.create_allocation(
                    w_conn,
                    AllocationCreate(student_id="STU-CAP-CAND2", bed_id=bed_2, start_date="2026-09-01")
                ))
            except HTTPException as he:
                return ("ALLOC_REJECTED", he.status_code, he.detail)
            except Exception as ex:
                return ("ALLOC_CRASH", str(ex))
            finally:
                w_conn.close()

        with concurrent.futures.ThreadPoolExecutor(max_workers=2) as executor:
            fut1 = executor.submit(worker_reduce_capacity)
            fut2 = executor.submit(worker_allocate_bed)
            res1 = fut1.result()
            res2 = fut2.result()

        # Database state validation: Room occupancy must NEVER exceed room capacity
        chk_conn = self._get_worker_conn()
        r_info = InfrastructureService.get_room_by_id(chk_conn, room_id)
        cur_occ = r_info["occupied_beds"]
        cur_cap = r_info["capacity"]
        self.assertLessEqual(cur_occ, cur_cap, f"Poka-Yoke invariant violated: Occupancy ({cur_occ}) exceeds capacity ({cur_cap})")
        chk_conn.close()

    def test_04_concurrent_room_and_bed_status_changes(self):
        """Worker 1 puts bed under maintenance while Worker 2 allocates the bed.

        Assert: Poka-Yoke maintenance protection guarantees no active student is placed in a maintenance bed.
        """
        setup_conn = self._get_worker_conn()
        room_row = InfrastructureService.create_room(
            setup_conn,
            RoomCreate(
                floor_id=1,
                room_number="R-MAINT-RACE",
                room_type="Single",
                capacity=1,
                base_fee=6000.0
            ),
            auto_create_beds=True
        )
        room_id = room_row["id"]
        bed_id = InfrastructureService.list_beds(setup_conn, room_id=room_id)["beds"][0]["id"]

        setup_conn.execute(
            """
            INSERT INTO students (student_id, first_name, last_name, gender, email, phone, status, branch, academic_year, admission_date)
            VALUES ('STU-MAINT-RACE', 'Maint', 'Racer', 'Male', 'maint_racer@univ.edu', '9999999005', 'Active', 'IT', 1, '2026-08-01');
            """
        )
        setup_conn.commit()
        setup_conn.close()

        barrier = threading.Barrier(2)

        def worker_set_maintenance():
            w_conn = self._get_worker_conn()
            try:
                barrier.wait(timeout=5.0)
                res = InfrastructureService.update_bed_maintenance(
                    w_conn,
                    bed_id=bed_id,
                    data=BedMaintenanceUpdate(maintenance_status="Under_Repair", notes="Concurrently reported repair")
                )
                return ("MAINT_SUCCESS", res)
            except HTTPException as he:
                return ("MAINT_REJECTED", he.status_code, he.detail)
            except Exception as ex:
                return ("MAINT_CRASH", str(ex))
            finally:
                w_conn.close()

        def worker_allocate():
            w_conn = self._get_worker_conn()
            try:
                barrier.wait(timeout=5.0)
                alloc = AllocationService.create_allocation(
                    w_conn,
                    AllocationCreate(student_id="STU-MAINT-RACE", bed_id=bed_id, start_date="2026-09-01")
                )
                return ("ALLOC_SUCCESS", alloc)
            except HTTPException as he:
                return ("ALLOC_REJECTED", he.status_code, he.detail)
            except Exception as ex:
                return ("ALLOC_CRASH", str(ex))
            finally:
                w_conn.close()

        with concurrent.futures.ThreadPoolExecutor(max_workers=2) as executor:
            fut1 = executor.submit(worker_set_maintenance)
            fut2 = executor.submit(worker_allocate)
            res1 = fut1.result()
            res2 = fut2.result()

        chk_conn = self._get_worker_conn()
        bed_info = InfrastructureService.get_bed_by_id(chk_conn, bed_id)
        c = chk_conn.cursor()
        c.execute("SELECT COUNT(*) FROM room_allocations WHERE bed_id = ? AND allocation_status = 'Active';", (bed_id,))
        active_allocs = c.fetchone()[0]

        # Poka-Yoke invariant: If bed is under repair, active allocations must be 0
        if bed_info["maintenance_status"] == "Under_Repair":
            self.assertEqual(active_allocs, 0, "No active allocations permitted when bed is Under_Repair")
        else:
            self.assertEqual(active_allocs, 1, "If allocation committed first, bed is Occupied")
        chk_conn.close()

    def test_05_concurrent_bulk_imports(self):
        """Two concurrent workers execute bulk imports on separate connection handles.

        Worker 1 imports 5 rooms for Floor 1.
        Worker 2 imports 5 rooms for Floor 2.
        Assert: Both imports succeed, 0 deadlocks, all 10 rooms persisted.
        """
        barrier = threading.Barrier(2)

        def worker_import_floor(floor_id: int, prefix: str):
            w_conn = self._get_worker_conn()
            records = [
                {"room_number": f"{prefix}-RM-{i:02d}", "floor_id": floor_id, "capacity": 2, "base_fee": 5000.0}
                for i in range(5)
            ]
            try:
                barrier.wait(timeout=5.0)
                res = InfrastructureService.bulk_import(w_conn, entity_type="rooms", records=records, dry_run=False)
                return ("SUCCESS", res)
            except Exception as ex:
                return ("FAILED", str(ex))
            finally:
                w_conn.close()

        with concurrent.futures.ThreadPoolExecutor(max_workers=2) as executor:
            fut1 = executor.submit(worker_import_floor, 1, "BULK-A")
            fut2 = executor.submit(worker_import_floor, 2, "BULK-B")
            r1 = fut1.result()
            r2 = fut2.result()

        self.assertEqual(r1[0], "SUCCESS", f"Worker 1 import failed: {r1[1]}")
        self.assertEqual(r2[0], "SUCCESS", f"Worker 2 import failed: {r2[1]}")

        # Verify all 10 rooms were inserted
        chk_conn = self._get_worker_conn()
        cur = chk_conn.cursor()
        cur.execute("SELECT COUNT(*) FROM rooms WHERE room_number LIKE 'BULK-%';")
        count = cur.fetchone()[0]
        self.assertEqual(count, 10, "All 10 bulk-imported rooms must exist")
        chk_conn.close()

    def test_06_multiple_simultaneous_database_writers(self):
        """8 simultaneous writer threads perform rapid write operations under SQLite WAL mode.

        Assert: Zero unhandled database locks, zero corruption, all operations committed.
        """
        num_threads = 8
        ops_per_thread = 15
        barrier = threading.Barrier(num_threads)

        def writer_task(worker_id: int):
            w_conn = self._get_worker_conn()
            try:
                barrier.wait(timeout=5.0)
                for op in range(ops_per_thread):
                    cur = w_conn.cursor()
                    cur.execute(
                        """
                        INSERT INTO audit_logs (user_id, username, action, entity_name, entity_id, details)
                        VALUES (1, ?, 'CONCURRENT_THREAD_WRITE', 'test', ?, ?);
                        """,
                        (f"writer_{worker_id}", f"ITEM-{op}", f"Write op {op} by worker {worker_id}")
                    )
                    w_conn.commit()
                return ("SUCCESS", worker_id)
            except Exception as exc:
                return ("CRASH", worker_id, str(exc))
            finally:
                w_conn.close()

        with concurrent.futures.ThreadPoolExecutor(max_workers=num_threads) as executor:
            futures = [executor.submit(writer_task, wid) for wid in range(num_threads)]
            results = [f.result() for f in futures]

        crashes = [r for r in results if r[0] == "CRASH"]
        self.assertEqual(len(crashes), 0, f"Writer crashes: {crashes}")

        chk_conn = self._get_worker_conn()
        cur = chk_conn.cursor()
        cur.execute("SELECT COUNT(*) FROM audit_logs WHERE action = 'CONCURRENT_THREAD_WRITE';")
        total_writes = cur.fetchone()[0]
        self.assertEqual(total_writes, num_threads * ops_per_thread)

        cur.execute("PRAGMA integrity_check;")
        self.assertEqual(cur.fetchone()[0], "ok")
        chk_conn.close()

    def test_07_multiprocess_contention(self):
        """Multi-process contention: 4 separate OS processes writing to the SQLite database simultaneously.

        Assert: All processes complete with exitcode 0, PRAGMA integrity_check is ok.
        """
        num_procs = 4
        iterations_per_proc = 20
        result_queue = multiprocessing.Queue()

        processes = []
        for pid in range(num_procs):
            p = multiprocessing.Process(
                target=_multiprocess_writer_target,
                args=(self.db_path, pid + 100, iterations_per_proc, result_queue)
            )
            processes.append(p)
            p.start()

        for p in processes:
            p.join(timeout=30.0)
            self.assertEqual(p.exitcode, 0, f"Process {p.pid} terminated with non-zero exit code: {p.exitcode}")

        # Collect results from queue
        results = []
        while not result_queue.empty():
            results.append(result_queue.get_nowait())

        self.assertEqual(len(results), num_procs)
        for wid, ok, err in results:
            self.assertTrue(ok, f"Worker {wid} failed with error: {err}")

        # Verify integrity and row counts
        chk_conn = self._get_worker_conn()
        cur = chk_conn.cursor()
        cur.execute("SELECT COUNT(*) FROM audit_logs WHERE action = 'MP_CONCURRENT_WRITE';")
        total_mp_writes = cur.fetchone()[0]
        self.assertEqual(total_mp_writes, num_procs * iterations_per_proc)

        cur.execute("PRAGMA integrity_check;")
        self.assertEqual(cur.fetchone()[0], "ok")
        cur.execute("PRAGMA foreign_key_check;")
        self.assertEqual(len(cur.fetchall()), 0)
        chk_conn.close()


if __name__ == "__main__":
    unittest.main()
