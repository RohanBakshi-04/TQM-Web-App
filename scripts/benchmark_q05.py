"""
Total Quality Management (TQM) Quality Goal Q05 Comprehensive Benchmark Suite
=============================================================================
Course: BBAT104 - Fundamentals of Total Quality Management
Quality SLA: Target Response Time < 10.0 ms across all operations.

Benchmarks Executed:
  1. Global FTS5 Full-Text Search Latency
  2. Entity-Specific Parameterized SQL Search (Indexed)
  3. Dashboard Metrics (Cold SQL Aggregation vs Warm In-Memory Cache)
  4. Cache Invalidation Turnaround Latency
  5. High-Frequency Domain Operations (Attendance, Fees, Complaints, Audit Logs)
  6. Scalability Analysis across Record Volumes (1k, 10k, 50k, 100k rows)
"""

import os
import sys
import time
import statistics
import sqlite3
from typing import Dict, List, Any

# Add project root to sys.path
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from backend.app.database.connection import get_db_connection
from backend.app.database.init_db import initialize_database
from backend.app.services.cache_service import cache_service
from backend.app.services.cache_invalidation import CacheInvalidator
from backend.app.services.dashboard_service import DashboardService
from backend.app.services.search_service import SearchService


def format_ms(val: float) -> str:
    return f"{val:6.3f} ms"


def run_q05_benchmarks() -> Dict[str, Any]:
    print("================================================================================")
    print("   HOSTEL MANAGEMENT SYSTEM - TQM QUALITY GOAL Q05 VERIFICATION SUITE           ")
    print("   SLA TARGET: < 10.000 ms response time for all queries & endpoints           ")
    print("================================================================================")

    conn = get_db_connection()
    initialize_database(conn, seed=True)
    cache_service.clear()

    results: Dict[str, Dict[str, float]] = {}

    # -------------------------------------------------------------------------
    # 1. Global FTS5 Full-Text Search
    # -------------------------------------------------------------------------
    print("\n[1/6] Benchmarking FTS5 Unified Search...")
    queries = ["Rohan", "Aryabhata", "Tagore", "Plumbing", "Single", "Room"]
    fts_latencies: List[float] = []

    for _ in range(20):
        for q in queries:
            t0 = time.perf_counter()
            _ = SearchService.search(conn=conn, q=q, limit=20)
            fts_latencies.append((time.perf_counter() - t0) * 1000.0)

    results["FTS5 Global Search"] = {
        "mean": statistics.mean(fts_latencies),
        "median": statistics.median(fts_latencies),
        "p95": sorted(fts_latencies)[int(len(fts_latencies) * 0.95)],
        "p99": sorted(fts_latencies)[int(len(fts_latencies) * 0.99)],
        "min": min(fts_latencies),
        "max": max(fts_latencies)
    }

    # -------------------------------------------------------------------------
    # 2. Entity-Specific Parameterized SQL Search
    # -------------------------------------------------------------------------
    print("[2/6] Benchmarking Entity-Specific Indexed SQL Queries...")
    sql_latencies: List[float] = []

    entity_tests = [
        ("SELECT * FROM students WHERE student_id LIKE ? LIMIT 20", ("%2026%",)),
        ("SELECT * FROM rooms WHERE status = ? AND room_type = ? LIMIT 20", ("Available", "Single")),
        ("SELECT * FROM room_allocations WHERE allocation_status = 'Active' AND bed_id = ? LIMIT 1", (1,)),
        ("SELECT * FROM complaints WHERE status = 'Assigned' AND category = ? LIMIT 20", ("Plumbing",)),
        ("SELECT * FROM payments WHERE status = 'Completed' ORDER BY id DESC LIMIT 20", ()),
    ]

    for _ in range(30):
        for sql, params in entity_tests:
            t0 = time.perf_counter()
            cursor = conn.cursor()
            cursor.execute(sql, params)
            _ = cursor.fetchall()
            sql_latencies.append((time.perf_counter() - t0) * 1000.0)

    results["Entity SQL Search"] = {
        "mean": statistics.mean(sql_latencies),
        "median": statistics.median(sql_latencies),
        "p95": sorted(sql_latencies)[int(len(sql_latencies) * 0.95)],
        "p99": sorted(sql_latencies)[int(len(sql_latencies) * 0.99)],
        "min": min(sql_latencies),
        "max": max(sql_latencies)
    }

    # -------------------------------------------------------------------------
    # 3. Dashboard Cold SQL Aggregation vs Warm In-Memory Cache
    # -------------------------------------------------------------------------
    print("[3/6] Benchmarking Dashboard Metrics (Cold SQL vs Warm In-Memory Cache)...")
    cold_latencies: List[float] = []
    warm_latencies: List[float] = []

    for _ in range(25):
        cache_service.clear()
        t0 = time.perf_counter()
        _ = DashboardService.get_dashboard_metrics(conn, user_roles=["super_admin"], bypass_cache=True)
        cold_latencies.append((time.perf_counter() - t0) * 1000.0)

    # Warm cache
    _ = DashboardService.get_dashboard_metrics(conn, user_roles=["super_admin"], bypass_cache=False)
    for _ in range(100):
        t0 = time.perf_counter()
        _ = DashboardService.get_dashboard_metrics(conn, user_roles=["super_admin"], bypass_cache=False)
        warm_latencies.append((time.perf_counter() - t0) * 1000.0)

    results["Dashboard Cold SQL"] = {
        "mean": statistics.mean(cold_latencies),
        "median": statistics.median(cold_latencies),
        "p95": sorted(cold_latencies)[int(len(cold_latencies) * 0.95)],
        "p99": sorted(cold_latencies)[int(len(cold_latencies) * 0.99)],
        "min": min(cold_latencies),
        "max": max(cold_latencies)
    }

    results["Dashboard Warm Cache"] = {
        "mean": statistics.mean(warm_latencies),
        "median": statistics.median(warm_latencies),
        "p95": sorted(warm_latencies)[int(len(warm_latencies) * 0.95)],
        "p99": sorted(warm_latencies)[int(len(warm_latencies) * 0.99)],
        "min": min(warm_latencies),
        "max": max(warm_latencies)
    }

    # -------------------------------------------------------------------------
    # 4. Cache Invalidation Speed
    # -------------------------------------------------------------------------
    print("[4/6] Benchmarking Tag-Based Cache Invalidation...")
    inv_latencies: List[float] = []
    for _ in range(50):
        # populate tags
        cache_service.set("bench_k1", {"val": 1}, ttl=60, tags=["allocations", "hostel_1"])
        cache_service.set("bench_k2", {"val": 2}, ttl=60, tags=["rooms", "hostel_1"])
        t0 = time.perf_counter()
        CacheInvalidator.on_allocation_mutation(hostel_id=1)
        inv_latencies.append((time.perf_counter() - t0) * 1000.0)

    results["Cache Invalidation"] = {
        "mean": statistics.mean(inv_latencies),
        "median": statistics.median(inv_latencies),
        "p95": sorted(inv_latencies)[int(len(inv_latencies) * 0.95)],
        "p99": sorted(inv_latencies)[int(len(inv_latencies) * 0.99)],
        "min": min(inv_latencies),
        "max": max(inv_latencies)
    }

    # -------------------------------------------------------------------------
    # 5. Core Operational Queries (Attendance, Fees, Audit, Notifications)
    # -------------------------------------------------------------------------
    print("[5/6] Benchmarking Core Operational Domain Queries...")
    ops_latencies: List[float] = []

    domain_queries = [
        # Attendance summary
        "SELECT status, COUNT(*) FROM attendance WHERE date = '2026-09-10' GROUP BY status",
        # Fee collection aggregate
        "SELECT SUM(paid_amount), SUM(total_amount - paid_amount) FROM invoices WHERE status != 'Cancelled'",
        # Audit logs with index filter
        "SELECT * FROM audit_logs WHERE entity_name = 'AUTH' ORDER BY id DESC LIMIT 50",
        # Notifications unread count
        "SELECT COUNT(*) FROM notifications WHERE user_id = 5 AND is_read = 0",
        # Announcements published
        "SELECT * FROM announcements WHERE status = 'Published' ORDER BY priority DESC, id DESC LIMIT 10",
    ]

    for _ in range(25):
        for sql in domain_queries:
            t0 = time.perf_counter()
            cursor = conn.cursor()
            cursor.execute(sql)
            _ = cursor.fetchall()
            ops_latencies.append((time.perf_counter() - t0) * 1000.0)

    results["Domain Queries"] = {
        "mean": statistics.mean(ops_latencies),
        "median": statistics.median(ops_latencies),
        "p95": sorted(ops_latencies)[int(len(ops_latencies) * 0.95)],
        "p99": sorted(ops_latencies)[int(len(ops_latencies) * 0.99)],
        "min": min(ops_latencies),
        "max": max(ops_latencies)
    }

    # -------------------------------------------------------------------------
    # 6. Scalability Analysis: Synthetic Volume Index Probe (1k to 100k)
    # -------------------------------------------------------------------------
    print("[6/6] Benchmarking Scalability Across Record Volumes (1k, 10k, 50k, 100k)...")
    scale_conn = sqlite3.connect(":memory:")
    scale_conn.execute("PRAGMA journal_mode = MEMORY;")
    scale_conn.execute("CREATE TABLE scale_test (id INTEGER PRIMARY KEY, student_id INT, status TEXT, amount REAL, created_at TEXT);")
    scale_conn.execute("CREATE INDEX idx_scale_test_status_student ON scale_test(status, student_id);")

    volumes = [1000, 10000, 50000, 100000]
    scale_results: Dict[str, float] = {}

    current_count = 0
    for target in volumes:
        rows_to_add = target - current_count
        scale_conn.executemany(
            "INSERT INTO scale_test (student_id, status, amount, created_at) VALUES (?, ?, ?, '2026-11-01');",
            [(i % 500 + 1, "Active" if i % 2 == 0 else "Archived", float(100 + (i % 50)),) for i in range(rows_to_add)]
        )
        scale_conn.commit()
        current_count = target

        # Probe indexed query over target volume
        probe_times: List[float] = []
        for _ in range(50):
            t0 = time.perf_counter()
            cur = scale_conn.cursor()
            cur.execute("SELECT COUNT(*), SUM(amount) FROM scale_test WHERE status = 'Active' AND student_id = 42")
            _ = cur.fetchone()
            probe_times.append((time.perf_counter() - t0) * 1000.0)

        scale_results[f"Volume {target:,} rows"] = statistics.mean(probe_times)

    scale_conn.close()
    conn.close()

    # -------------------------------------------------------------------------
    # Print Results Table
    # -------------------------------------------------------------------------
    print("\n" + "=" * 80)
    print("                     TQM Q05 BENCHMARK REPORT SUMMARY                           ")
    print("=" * 80)
    print(f"{'Operation / Metric':<28} | {'Mean':>10} | {'Median':>10} | {'P95':>10} | {'P99':>10} | {'Status':>8}")
    print("-" * 80)

    all_passed = True
    for name, stats in results.items():
        status = "PASSED" if stats["p95"] < 10.0 else "FAILED"
        if stats["p95"] >= 10.0:
            all_passed = False
        print(f"{name:<28} | {format_ms(stats['mean'])} | {format_ms(stats['median'])} | {format_ms(stats['p95'])} | {format_ms(stats['p99'])} | {status:>8}")

    print("-" * 80)
    print("SCALABILITY PROJECTION (Indexed B-Tree Range Scans):")
    for vol, avg_ms in scale_results.items():
        status = "PASSED" if avg_ms < 10.0 else "FAILED"
        print(f"  - {vol:<22} : {format_ms(avg_ms)} (SLA < 10ms: {status})")

    print("=" * 80)
    if all_passed:
        print("  RESULT: QUALITY GOAL Q05 VERIFIED - ALL OPERATIONAL P95 LATENCIES < 10ms SLA")
    else:
        print("  RESULT: SLA VIOLATION DETECTED - SOME OPERATIONS EXCEEDED 10ms")
    print("=" * 80)

    return results


if __name__ == "__main__":
    run_q05_benchmarks()
