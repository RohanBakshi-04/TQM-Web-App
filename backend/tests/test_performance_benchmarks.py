"""High-Precision Performance Benchmarks & SLA Telemetry Verification.

Validates Q05 Performance Targets:
- Clear separation between Internal Execution Time (SQL / Cache Engine),
  FastAPI Middleware Processing Time (X-Response-Time-Ms header),
  and Total Client Round-Trip Latency.
- 20-run statistical distributions (min, avg, p50, p95, p99) across:
  * Health check (/api/health)
  * Dashboard Aggregation (/api/v1/dashboard/stats) [Cold vs Warm Cache]
  * Fast Search (/api/v1/search) [FTS5 Full-Text Indexed Search]
"""

import math
import os
import shutil
import tempfile
import time
import unittest
from typing import Dict, List, Any
from fastapi.testclient import TestClient

from backend.app.config import settings
from backend.app.database.connection import get_db_connection
from backend.app.database.init_db import initialize_database
from backend.app.main import app
from backend.app.services.auth_service import AuthService
from backend.app.services.cache_service import cache_service


def calculate_percentiles(latencies: List[float]) -> Dict[str, float]:
    """Calculate min, avg, p50, p95, and p99 percentiles for a list of latency measurements."""
    if not latencies:
        return {"min": 0.0, "avg": 0.0, "p50": 0.0, "p95": 0.0, "p99": 0.0}

    sorted_vals = sorted(latencies)
    n = len(sorted_vals)

    def percentile(p: float) -> float:
        k = (n - 1) * (p / 100.0)
        f = math.floor(k)
        c = math.ceil(k)
        if f == c:
            return sorted_vals[int(k)]
        d0 = sorted_vals[int(f)] * (c - k)
        d1 = sorted_vals[int(c)] * (k - f)
        return d0 + d1

    return {
        "min": round(min(sorted_vals), 3),
        "avg": round(sum(sorted_vals) / n, 3),
        "p50": round(percentile(50), 3),
        "p95": round(percentile(95), 3),
        "p99": round(percentile(99), 3),
    }


class TestPerformanceBenchmarks(unittest.TestCase):
    """Rigorous statistical performance benchmarks for core HMS endpoints."""

    @classmethod
    def setUpClass(cls):
        """Provision an isolated, fully-seeded SQLite test database in WAL mode."""
        cls.temp_dir = tempfile.mkdtemp(prefix="hms_perf_bench_")
        cls.db_path = os.path.join(cls.temp_dir, "test_perf.db")
        cls.orig_db_path = settings.database_path

        settings.database_path = cls.db_path

        conn = get_db_connection()
        try:
            initialize_database(conn, seed=True)
        finally:
            conn.close()

        cls.client = TestClient(app)

        # Generate auth tokens
        conn = get_db_connection()
        try:
            user = AuthService.authenticate_user("superadmin", "Password123!", conn=conn)
            tokens = AuthService.issue_token_pair(user, conn=conn)
            cls.auth_headers = {"Authorization": f"Bearer {tokens['access_token']}"}
        finally:
            conn.close()

    @classmethod
    def tearDownClass(cls):
        """Restore global settings and clean up isolated test artifacts."""
        settings.database_path = cls.orig_db_path
        shutil.rmtree(cls.temp_dir, ignore_errors=True)

    def test_01_health_endpoint_latency_distribution(self):
        """Verify /api/health SLA: 20 iterations, verifying header and round-trip SLA."""
        iterations = 20
        roundtrip_times = []
        middleware_times = []

        for _ in range(iterations):
            t0 = time.perf_counter()
            resp = self.client.get("/api/health")
            t1 = time.perf_counter()

            self.assertEqual(resp.status_code, 200)
            roundtrip_ms = (t1 - t0) * 1000.0
            roundtrip_times.append(roundtrip_ms)

            self.assertIn("x-response-time-ms", resp.headers)
            mw_ms = float(resp.headers["x-response-time-ms"])
            middleware_times.append(mw_ms)

        rt_stats = calculate_percentiles(roundtrip_times)
        mw_stats = calculate_percentiles(middleware_times)

        print("\n--- Health Check (/api/health) Telemetry (20 runs) ---")
        print(f"Roundtrip Latency (ms) : Min={rt_stats['min']}, Avg={rt_stats['avg']}, P50={rt_stats['p50']}, P95={rt_stats['p95']}, P99={rt_stats['p99']}")
        print(f"Middleware Time (ms)   : Min={mw_stats['min']}, Avg={mw_stats['avg']}, P50={mw_stats['p50']}, P95={mw_stats['p95']}, P99={mw_stats['p99']}")

        # SLA assertions
        self.assertLess(mw_stats["avg"], 30.0, "Average health middleware time exceeded 30ms SLA")
        self.assertLess(rt_stats["p95"], 80.0, "P95 health roundtrip latency exceeded 80ms SLA")

    def test_02_dashboard_stats_cold_vs_warm_cache_performance(self):
        """Verify /api/v1/dashboard/stats: compare Cold Cache (MISS) vs Warm Cache (HIT, <5ms)."""
        # 1. COLD CACHE: Flush cache to force full SQL aggregation
        cache_service.clear()

        t0 = time.perf_counter()
        cold_resp = self.client.get("/api/v1/dashboard/stats", headers=self.auth_headers)
        t1 = time.perf_counter()

        self.assertEqual(cold_resp.status_code, 200)
        cold_data = cold_resp.json()
        cold_roundtrip_ms = (t1 - t0) * 1000.0
        cold_mw_ms = float(cold_resp.headers.get("x-response-time-ms", 0.0))
        cold_exec_ms = float(cold_data.get("execution_time_ms", 0.0))

        self.assertEqual(cold_data.get("cache_status"), "MISS", "Expected cold cache status to be MISS")

        print("\n--- Dashboard Cold Cache (MISS) Telemetry ---")
        print(f"Internal SQL Execution Time : {cold_exec_ms:.3f} ms")
        print(f"FastAPI Middleware Time     : {cold_mw_ms:.3f} ms")
        print(f"Client Roundtrip Latency    : {cold_roundtrip_ms:.3f} ms")

        # 2. WARM CACHE: 20 iterations on primed in-memory cache
        warm_roundtrip_times = []
        warm_middleware_times = []
        warm_internal_exec_times = []

        for _ in range(20):
            t_start = time.perf_counter()
            resp = self.client.get("/api/v1/dashboard/stats", headers=self.auth_headers)
            t_end = time.perf_counter()

            self.assertEqual(resp.status_code, 200)
            data = resp.json()

            self.assertEqual(data.get("cache_status"), "HIT")
            warm_roundtrip_times.append((t_end - t_start) * 1000.0)
            warm_middleware_times.append(float(resp.headers["x-response-time-ms"]))
            warm_internal_exec_times.append(float(data.get("execution_time_ms", 0.0)))

        rt_stats = calculate_percentiles(warm_roundtrip_times)
        mw_stats = calculate_percentiles(warm_middleware_times)
        exec_stats = calculate_percentiles(warm_internal_exec_times)

        print("\n--- Dashboard Warm Cache (HIT) Telemetry (20 runs) ---")
        print(f"Internal Cache Retrieval (ms) : Min={exec_stats['min']}, Avg={exec_stats['avg']}, P50={exec_stats['p50']}, P95={exec_stats['p95']}")
        print(f"Middleware Time (ms)          : Min={mw_stats['min']}, Avg={mw_stats['avg']}, P50={mw_stats['p50']}, P95={mw_stats['p95']}")
        print(f"Client Roundtrip Latency (ms) : Min={rt_stats['min']}, Avg={rt_stats['avg']}, P50={rt_stats['p50']}, P95={rt_stats['p95']}")

        # Strict Q05 SLA: Warm cache internal retrieval must be < 5ms
        self.assertLess(exec_stats["avg"], 5.0, "Warm cache internal retrieval exceeded 5ms SLA")
        self.assertLess(mw_stats["avg"], 25.0, "Warm cache middleware time exceeded 25ms SLA")
        self.assertLess(rt_stats["p95"], 50.0, "Warm cache P95 roundtrip exceeded 50ms SLA")

    def test_03_fast_search_fts5_performance(self):
        """Verify /api/v1/search Q05 Fast Search SLA across 20 query executions."""
        query = "Rohan"
        roundtrip_times = []
        middleware_times = []
        internal_search_times = []

        for _ in range(20):
            t_start = time.perf_counter()
            resp = self.client.get(f"/api/v1/search?q={query}", headers=self.auth_headers)
            t_end = time.perf_counter()

            self.assertEqual(resp.status_code, 200)
            payload = resp.json()

            roundtrip_times.append((t_end - t_start) * 1000.0)
            middleware_times.append(float(resp.headers["x-response-time-ms"]))
            internal_search_times.append(float(payload.get("execution_time_ms", 0.0)))

        rt_stats = calculate_percentiles(roundtrip_times)
        mw_stats = calculate_percentiles(middleware_times)
        search_stats = calculate_percentiles(internal_search_times)

        print("\n--- Q05 Fast Search (/api/v1/search) Telemetry (20 runs) ---")
        print(f"Internal FTS5 Search Time (ms): Min={search_stats['min']}, Avg={search_stats['avg']}, P50={search_stats['p50']}, P95={search_stats['p95']}")
        print(f"Middleware Time (ms)          : Min={mw_stats['min']}, Avg={mw_stats['avg']}, P50={mw_stats['p50']}, P95={mw_stats['p95']}")
        print(f"Client Roundtrip Latency (ms) : Min={rt_stats['min']}, Avg={rt_stats['avg']}, P50={rt_stats['p50']}, P95={rt_stats['p95']}")

        # Strict Q05 SLA: Internal FTS5 indexed search execution time < 10ms
        self.assertLess(search_stats["avg"], 10.0, "FTS5 internal search average exceeded 10ms SLA")
        self.assertLess(mw_stats["avg"], 30.0, "Fast search middleware average exceeded 30ms SLA")
        self.assertLess(rt_stats["p95"], 60.0, "Fast search P95 roundtrip exceeded 60ms SLA")


if __name__ == "__main__":
    unittest.main()
