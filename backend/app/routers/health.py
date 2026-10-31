"""System Health and Q05 Telemetry Endpoint.

Course: BBAT104 - Fundamentals of TQM
Quality Goal: Q05 - Reduce Response Time
"""

import time
from datetime import datetime, timezone
from typing import Any, Dict
from fastapi import APIRouter
from backend.app.config import settings
from backend.app.database.connection import get_db_connection

router = APIRouter(prefix="/api", tags=["Health"])


@router.get("/health")
def health_check() -> Dict[str, Any]:
    """Verify backend services, SQLite connection, and Q05 response time compliance."""
    db_status = "connected"
    sqlite_version = "unknown"
    journal_mode = "unknown"

    t0 = time.perf_counter()
    try:
        conn = get_db_connection()
        cursor = conn.cursor()
        cursor.execute("SELECT sqlite_version();")
        sqlite_version = cursor.fetchone()[0]
        cursor.execute("PRAGMA journal_mode;")
        journal_mode = cursor.fetchone()[0].upper()
        conn.close()
    except Exception as e:
        db_status = f"error: {str(e)}"

    elapsed_ms = (time.perf_counter() - t0) * 1000.0

    return {
        "status": "healthy" if db_status == "connected" else "degraded",
        "app_name": settings.app_name,
        "environment": settings.app_env,
        "version": "0.1.0",
        "timestamp": datetime.now(timezone.utc).isoformat(),
        "database": {
            "status": db_status,
            "engine": f"SQLite v{sqlite_version}",
            "journal_mode": journal_mode,
            "ping_latency_ms": round(elapsed_ms, 3)
        },
        "q05_telemetry": {
            "sla_target_ms": 10.0,
            "meets_sla": elapsed_ms < 10.0
        }
    }
