"""Hostel Management System Web App - Main Application.

Course: BBAT104 - Fundamentals of Total Quality Management (TQM)
Quality Goal: Q05 - Reduce Response Time
"""

import asyncio
import os
import time
import uuid
from typing import Optional
from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse
from fastapi.staticfiles import StaticFiles

from backend.app.config import settings
from backend.app.database.init_db import initialize_database
from backend.app.routers.allocations import (
    router as allocations_router,
    room_occupants_router,
    student_history_router,
    transfers_router,
)
from backend.app.routers.auth import router as auth_router
from backend.app.routers.complaints import router as complaints_router
from backend.app.routers.attendance import router as attendance_router
from backend.app.routers.leave import router as leave_router, outpass_router
from backend.app.routers.visitors import router as visitors_router
from backend.app.routers.fees import fees_router
from backend.app.routers.mess import mess_router
from backend.app.routers.inventory import inventory_router
from backend.app.routers.notifications import router as notifications_router
from backend.app.routers.announcements import router as announcements_router
from backend.app.routers.admin import admin_router
from backend.app.routers.dashboard import metrics_router, router as dashboard_router
from backend.app.routers.health import router as health_router
from backend.app.routers.hostels import building_router, router as hostels_router
from backend.app.routers.maintenance import router as maintenance_router
from backend.app.routers.search import router as search_router
from backend.app.utils.logger import logger

BASE_DIR = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
FRONTEND_DIR = os.path.join(BASE_DIR, "frontend")

app = FastAPI(
    title=settings.app_name,
    description="A unified platform for intelligent hostel administration and management.",
    version="1.0.0"
)

# CORS Middleware
app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.cors_origins,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


from fastapi.responses import JSONResponse

@app.middleware("http")
async def add_latency_header(request: Request, call_next):
    """Q05 Telemetry Middleware: Measures and exposes response time in headers."""
    t0 = time.perf_counter()
    try:
        response = await call_next(request)
    except Exception as exc:
        request_id = str(uuid.uuid4())[:8]
        logger.error(f"[{request_id}] Unhandled exception during {request.method} {request.url.path}: {exc}", exc_info=True)
        detail_msg = f"Internal server error: {str(exc)}" if settings.debug else "An internal server error occurred. Please contact the administrator."
        response = JSONResponse(
            status_code=500,
            content={"detail": detail_msg, "request_id": request_id}
        )
    duration_ms = (time.perf_counter() - t0) * 1000.0
    response.headers["X-Response-Time-Ms"] = f"{duration_ms:.3f}"
    return response


# Include API routers
app.include_router(health_router)
app.include_router(auth_router)
app.include_router(dashboard_router)
app.include_router(metrics_router)
app.include_router(hostels_router)
app.include_router(building_router)
app.include_router(allocations_router)
app.include_router(transfers_router)
app.include_router(room_occupants_router)
app.include_router(student_history_router)
app.include_router(search_router)
app.include_router(complaints_router)
app.include_router(maintenance_router)
app.include_router(attendance_router)
app.include_router(leave_router)
app.include_router(outpass_router)
app.include_router(visitors_router)
app.include_router(fees_router)
app.include_router(mess_router)
app.include_router(inventory_router)
app.include_router(notifications_router)
app.include_router(announcements_router)
app.include_router(admin_router)


# Mount static assets if directory exists
if os.path.exists(FRONTEND_DIR):
    app.mount("/static", StaticFiles(directory=FRONTEND_DIR), name="static")


@app.get("/")
def serve_frontend():
    """Serve the single-page application frontend."""
    index_path = os.path.join(FRONTEND_DIR, "index.html")
    if os.path.exists(index_path):
        return FileResponse(index_path)
    return {
        "app": settings.app_name,
        "status": "ready",
        "docs": "/docs",
        "health": "/api/health"
    }


_curfew_task: Optional[asyncio.Task] = None


async def curfew_monitor_loop():
    """Background lifecycle monitor: checks visitor curfews periodically with graceful error handling."""
    logger.info("Visitor curfew monitor background task started.")
    interval = getattr(settings, "curfew_check_interval_seconds", 300)
    while True:
        try:
            from backend.app.services.visitor_service import VisitorService
            res = VisitorService.check_visitor_curfew()
            count = res.get("overdue_count", res.get("updated_count", 0))
            if count > 0:
                logger.info(f"Curfew monitor updated {count} overdue visitors.")
        except asyncio.CancelledError:
            logger.info("Curfew monitor background task cancelled.")
            break
        except Exception as e:
            logger.error(f"Error in curfew monitor loop: {e}", exc_info=True)
        try:
            await asyncio.sleep(interval)
        except asyncio.CancelledError:
            logger.info("Curfew monitor background task cancelled during sleep.")
            break


@app.on_event("startup")
async def on_startup():
    """Initialize database, verify configuration, and launch background tasks on startup."""
    logger.info(f"Starting {settings.app_name} in {settings.app_env} mode...")
    settings.validate_production_secrets()
    initialize_database()
    try:
        from backend.app.database.connection import get_db_connection
        from backend.app.services.dashboard_service import DashboardService
        conn = get_db_connection()
        DashboardService.get_dashboard_metrics(conn, user_roles=["super_admin"])
        conn.close()
        logger.info("Pre-warmed in-memory dashboard cache successfully.")
    except Exception as e:
        logger.warning(f"Dashboard cache pre-warm skipped: {e}")

    # Launch background curfew monitor loop
    global _curfew_task
    if settings.app_env != "testing":
        _curfew_task = asyncio.create_task(curfew_monitor_loop())
    logger.info("Application startup sequence completed successfully.")


@app.on_event("shutdown")
async def on_shutdown():
    """Graceful shutdown sequence: cancels background tasks."""
    global _curfew_task
    if _curfew_task and not _curfew_task.done():
        _curfew_task.cancel()
        try:
            await _curfew_task
        except asyncio.CancelledError:
            pass
    logger.info("Application shutdown sequence completed successfully.")
