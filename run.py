"""Unified Startup Launcher for Hostel Management System Web App.

Course: BBAT104 - Fundamentals of Total Quality Management (TQM)
Academic Session: 2026-27
Student: Rohan Bakshi (Roll No: 2410301057)
Quality Goal: Q05 - Reduce Response Time
"""

import sys
import webbrowser
from threading import Timer
import uvicorn

from backend.app.config import settings
from backend.app.database.init_db import initialize_database
from backend.app.utils.logger import logger


def open_browser():
    """Launch the web application portal in default browser."""
    webbrowser.open(f"http://{settings.host}:{settings.port}")


def main():
    print("=" * 70)
    print("  HOSTEL MANAGEMENT SYSTEM (HMS) — WEB APPLICATION")
    print("  Assigned Quality Goal: Q05 — REDUCE RESPONSE TIME")
    print("  Course: BBAT104 Fundamentals of TQM (Session 2026-27)")
    print("  Student: Rohan Bakshi | Roll No: 2410301057 | CSE (Sec A)")
    print("=" * 70)

    # 1. Initialize SQLite connection and WAL mode
    logger.info("Initializing SQLite database with WAL mode and foreign key enforcement...")
    initialize_database()

    # 2. Server Startup Information
    url = f"http://{settings.host}:{settings.port}"
    print("\n" + "-" * 70)
    print(f"  • Web Application URL:   {url}")
    print(f"  • API Health Endpoint:   {url}/api/health")
    print(f"  • Interactive API Docs:  {url}/docs")
    print("-" * 70)
    print("  Press Ctrl+C to stop the server.\n" + "=" * 70 + "\n")

    # Schedule browser opening after 1 second
    Timer(1.0, open_browser).start()

    # Launch Uvicorn ASGI Server
    uvicorn.run(
        "backend.app.main:app",
        host=settings.host,
        port=settings.port,
        reload=settings.debug,
        log_level="info"
    )


if __name__ == "__main__":
    try:
        main()
    except KeyboardInterrupt:
        print("\nServer shutdown requested. Gracefully stopped.")
        sys.exit(0)
