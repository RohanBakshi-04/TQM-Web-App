"""Hostel Management System Web App - Main Application.

Course: BBAT104 - Fundamentals of Total Quality Management (TQM)
Quality Goal: Q05 - Reduce Response Time
"""

import os
import time
from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse
from fastapi.staticfiles import StaticFiles

from backend.app.config import settings
from backend.app.database.init_db import initialize_database
from backend.app.routers.auth import router as auth_router
from backend.app.routers.health import router as health_router
from backend.app.utils.logger import logger

BASE_DIR = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
FRONTEND_DIR = os.path.join(BASE_DIR, "frontend")

app = FastAPI(
    title=settings.app_name,
    description="High-performance, modular web application for Hostel Administration engineered for Q05 Latency Reduction.",
    version="0.1.0"
)

# CORS Middleware
app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.cors_origins,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


@app.middleware("http")
async def add_latency_header(request: Request, call_next):
    """Q05 Telemetry Middleware: Measures and exposes response time in headers."""
    t0 = time.perf_counter()
    response = await call_next(request)
    duration_ms = (time.perf_counter() - t0) * 1000.0
    response.headers["X-Response-Time-Ms"] = f"{duration_ms:.3f}"
    return response


# Include API routers
app.include_router(health_router)
app.include_router(auth_router)


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


@app.on_event("startup")
def on_startup():
    """Initialize database and verify configuration on application startup."""
    logger.info(f"Starting {settings.app_name} in {settings.app_env} mode...")
    initialize_database()
    logger.info("Application startup sequence completed successfully.")
