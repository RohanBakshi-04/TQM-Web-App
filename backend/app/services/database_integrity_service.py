"""Database Integrity Monitor & Diagnostic Service with Freshness Tracking.

Course: BBAT104 - Fundamentals of Total Quality Management (TQM)
Quality Goal: Q05 - Reduce Response Time (<10ms SLA) & Poka-Yoke System Diagnostics
"""

import datetime
import logging
import sqlite3
import threading
import time
from typing import Any, Dict, Optional

from backend.app.database.connection import get_db_connection

logger = logging.getLogger("hms_app")


class DatabaseIntegrityMonitor:
    """Thread-safe SQLite integrity monitor tracking verification freshness, duration, and diagnostics."""

    _instance: Optional["DatabaseIntegrityMonitor"] = None
    _lock = threading.Lock()

    def __new__(cls, *args, **kwargs):
        if cls._instance is None:
            with cls._lock:
                if cls._instance is None:
                    cls._instance = super(DatabaseIntegrityMonitor, cls).__new__(cls)
                    cls._instance._initialized = False
        return cls._instance

    def __init__(self, ttl_seconds: float = 300.0):
        if getattr(self, "_initialized", False):
            return
        self.ttl_seconds = ttl_seconds
        self.status = "unknown"
        self.raw_result = "unknown"
        self.last_verified_at: Optional[str] = None
        self._last_verified_ts: float = 0.0
        self.last_attempted_at: Optional[str] = None
        self.check_duration_ms: float = 0.0
        self.last_error: Optional[str] = None
        self.cached_until: float = 0.0
        self.total_physical_scans: int = 0
        self._execution_lock = threading.Lock()
        self._simulated_error: Optional[str] = None
        self._initialized = True

    def check_integrity(
        self,
        conn: Optional[sqlite3.Connection] = None,
        force: bool = False
    ) -> Dict[str, Any]:
        """Perform or retrieve cached database integrity diagnostic.

        Guarantees:
        - Thread-safe non-blocking execution prevents stampedes.
        - Records exact timestamps for verification and attempts.
        - Provides human-readable freshness indicators.
        - Never silently converts corruption/errors into healthy status.
        """
        now_ts = time.time()
        now_dt = datetime.datetime.now()

        # Check if cache is still valid
        if not force and self.status != "unknown" and now_ts < self.cached_until and self._last_verified_ts > 0:
            freshness_sec = round(now_ts - self._last_verified_ts, 1)
            freshness_label = f"Cached — {int(freshness_sec)}s old" if freshness_sec < 60 else f"Cached — {int(freshness_sec // 60)}m old"
            return {
                "status": self.status,
                "raw_result": self.raw_result,
                "is_cached": True,
                "last_verified_at": self.last_verified_at,
                "last_attempted_at": self.last_attempted_at,
                "duration_ms": self.check_duration_ms,
                "freshness_seconds": freshness_sec,
                "freshness_label": freshness_label,
                "next_refresh_eligible_at": datetime.datetime.fromtimestamp(self.cached_until).strftime("%Y-%m-%d %H:%M:%S"),
                "last_error": self.last_error
            }

        # Acquire execution lock (non-blocking if not force to avoid stalling callers)
        acquired = self._execution_lock.acquire(blocking=force or self.status == "unknown")
        if not acquired:
            # Another thread is actively verifying; return current state safely marked
            freshness_sec = round(now_ts - self._last_verified_ts, 1) if self._last_verified_ts > 0 else 0.0
            return {
                "status": self.status if self.status != "unknown" else "checking",
                "raw_result": self.raw_result,
                "is_cached": True,
                "last_verified_at": self.last_verified_at,
                "last_attempted_at": self.last_attempted_at,
                "duration_ms": self.check_duration_ms,
                "freshness_seconds": freshness_sec,
                "freshness_label": "Verification in progress by concurrent worker",
                "next_refresh_eligible_at": datetime.datetime.fromtimestamp(self.cached_until).strftime("%Y-%m-%d %H:%M:%S"),
                "last_error": self.last_error
            }

        should_close_conn = False
        try:
            now_ts = time.time()
            now_dt = datetime.datetime.now()

            # Double-Checked Locking:
            # Recheck cache validity AFTER acquiring execution lock in case another thread just completed verification
            if not force and self.status != "unknown" and now_ts < self.cached_until and self._last_verified_ts > 0:
                freshness_sec = round(now_ts - self._last_verified_ts, 1)
                freshness_label = f"Cached — {int(freshness_sec)}s old" if freshness_sec < 60 else f"Cached — {int(freshness_sec // 60)}m old"
                return {
                    "status": self.status,
                    "raw_result": self.raw_result,
                    "is_cached": True,
                    "last_verified_at": self.last_verified_at,
                    "last_attempted_at": self.last_attempted_at,
                    "duration_ms": self.check_duration_ms,
                    "freshness_seconds": freshness_sec,
                    "freshness_label": freshness_label,
                    "next_refresh_eligible_at": datetime.datetime.fromtimestamp(self.cached_until).strftime("%Y-%m-%d %H:%M:%S"),
                    "last_error": self.last_error
                }

            self.last_attempted_at = now_dt.strftime("%Y-%m-%d %H:%M:%S")

            # Simulated error support for testing (isolated)
            if self._simulated_error:
                self.status = "failed"
                self.raw_result = self._simulated_error
                self.last_error = self._simulated_error
                self.check_duration_ms = 0.5
                self.cached_until = now_ts + 5.0
                prior_freshness = round(now_ts - self._last_verified_ts, 1) if self._last_verified_ts > 0 else 0.0
                return {
                    "status": "failed",
                    "raw_result": self._simulated_error,
                    "is_cached": False,
                    "last_verified_at": self.last_verified_at,
                    "last_attempted_at": self.last_attempted_at,
                    "duration_ms": self.check_duration_ms,
                    "freshness_seconds": prior_freshness,
                    "freshness_label": "Failed verification",
                    "next_refresh_eligible_at": datetime.datetime.fromtimestamp(self.cached_until).strftime("%Y-%m-%d %H:%M:%S"),
                    "last_error": self._simulated_error
                }

            if conn is None:
                conn = get_db_connection()
                should_close_conn = True

            t0 = time.perf_counter()
            cur = conn.cursor()
            self.total_physical_scans += 1
            cur.execute("PRAGMA quick_check(1);")
            row = cur.fetchone()
            dur_ms = round((time.perf_counter() - t0) * 1000.0, 3)

            raw_str = str(row[0]) if row and row[0] is not None else "unknown"
            self.raw_result = raw_str
            self.check_duration_ms = dur_ms

            if raw_str.lower() == "ok":
                self.status = "healthy"
                self.last_error = None
                self.last_verified_at = datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S")
                self._last_verified_ts = time.time()
                self.cached_until = self._last_verified_ts + self.ttl_seconds
                freshness_label = "Live verification"
                freshness_sec = 0.0
            else:
                self.status = "warning" if "warn" in raw_str.lower() else "failed"
                self.last_error = raw_str
                # For failures, allow re-check sooner (15s) and preserve last successful verification timestamp
                self.cached_until = time.time() + 15.0
                freshness_label = "Verification detected anomaly"
                freshness_sec = round(time.time() - self._last_verified_ts, 1) if self._last_verified_ts > 0 else 0.0

            return {
                "status": self.status,
                "raw_result": self.raw_result,
                "is_cached": False,
                "last_verified_at": self.last_verified_at,
                "last_attempted_at": self.last_attempted_at,
                "duration_ms": self.check_duration_ms,
                "freshness_seconds": freshness_sec,
                "freshness_label": freshness_label,
                "next_refresh_eligible_at": datetime.datetime.fromtimestamp(self.cached_until).strftime("%Y-%m-%d %H:%M:%S"),
                "last_error": self.last_error
            }

        except Exception as exc:
            logger.error(f"Database integrity verification error: {exc}", exc_info=True)
            self.status = "failed"
            self.last_error = str(exc)
            self.raw_result = "error"
            self.cached_until = time.time() + 10.0
            prior_freshness = round(time.time() - self._last_verified_ts, 1) if self._last_verified_ts > 0 else 0.0
            return {
                "status": "failed",
                "raw_result": "error",
                "is_cached": False,
                "last_verified_at": self.last_verified_at,
                "last_attempted_at": self.last_attempted_at,
                "duration_ms": 0.0,
                "freshness_seconds": prior_freshness,
                "freshness_label": "Verification error",
                "next_refresh_eligible_at": datetime.datetime.fromtimestamp(self.cached_until).strftime("%Y-%m-%d %H:%M:%S"),
                "last_error": str(exc)
            }
        finally:
            if should_close_conn and conn:
                try:
                    conn.close()
                except Exception:
                    pass
            self._execution_lock.release()

    def simulate_status(self, status: str, error: Optional[str] = None):
        """Helper for test suites to simulate specific status scenarios ('warning', 'failed', 'healthy')."""
        with self._execution_lock:
            self.status = status
            self.last_error = error or f"Simulated {status} state"
            self.raw_result = self.last_error
            self.last_attempted_at = datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S")
            self.cached_until = time.time() + 60.0

    def set_simulated_error(self, err: Optional[str]):
        """Helper for test suites to simulate corruption/failure scenarios."""
        self._simulated_error = err

    def reset(self):
        """Reset monitor state."""
        with self._execution_lock:
            self.status = "unknown"
            self.raw_result = "unknown"
            self.last_verified_at = None
            self._last_verified_ts = 0.0
            self.last_attempted_at = None
            self.check_duration_ms = 0.0
            self.last_error = None
            self.cached_until = 0.0
            self.total_physical_scans = 0
            self._simulated_error = None


# Authoritative Singleton Instance
integrity_monitor = DatabaseIntegrityMonitor()
