"""System Health, Liveness, Readiness, and Q05 Telemetry Endpoints.

Course: BBAT104 - Fundamentals of TQM
Quality Goal: Q05 - Reduce Response Time
"""

import time
from datetime import datetime, timezone
from typing import Any, Dict
from fastapi import APIRouter, Response, status
from backend.app.config import settings
from backend.app.database.connection import get_db_connection
from backend.app.utils.logger import logger

router = APIRouter(prefix="/api", tags=["Health"])


@router.get("/health/live")
def liveness_check() -> Dict[str, str]:
    """Kubernetes/Container liveness probe to confirm HTTP process is running."""
    return {"status": "alive", "timestamp": datetime.now(timezone.utc).isoformat()}


@router.get("/health/ready")
def readiness_check(response: Response) -> Dict[str, Any]:
    """Kubernetes/Container readiness probe to confirm database connectivity."""
    try:
        conn = get_db_connection()
        cursor = conn.cursor()
        cursor.execute("SELECT 1;")
        cursor.fetchone()
        conn.close()
        return {"status": "ready", "database": "connected"}
    except Exception as e:
        logger.error(f"Readiness probe failed: {e}")
        response.status_code = status.HTTP_503_SERVICE_UNAVAILABLE
        return {"status": "unhealthy", "database": "disconnected", "detail": "Database connection failed."}


@router.get("/health")
def health_check(response: Response) -> Dict[str, Any]:
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
        logger.error(f"Health check database failure: {e}")
        db_status = "disconnected"
        response.status_code = status.HTTP_503_SERVICE_UNAVAILABLE

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
