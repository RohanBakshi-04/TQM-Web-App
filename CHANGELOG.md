# CHANGELOG — HOSTEL MANAGEMENT SYSTEM WEB APP

All notable changes to this project are documented in this file, adhering to Semantic Versioning and Conventional Commits.

---

## [0.1.0] - 2026-09-16 (Prompt 01: Project Initialization)

### Added
- **Project Structure:** Modular layered architecture separating `backend/`, `frontend/`, `data/`, `docs/`, and `scripts/`.
- **Backend Foundation:** FastAPI ASGI application configured with centralized settings, structured logging, and CORS middleware.
- **Database Engine:** SQLite3 connection manager with Write-Ahead Logging (`WAL` mode), foreign key integrity, and connection timeout handling.
- **Health Check Endpoint:** `GET /api/health` providing real-time system status, database connectivity verification, and timestamp.
- **Frontend Skeleton:** Modern, responsive HTML5 user interface styled with Tailwind CSS (CDN) and powered by Alpine.js for lightweight reactivity.
- **Login Placeholder:** Professional authentication UI placeholder supporting multiple stakeholder roles (Admin, Student, Staff, Auditor).
- **Startup Script:** Unified `run.py` launcher ensuring environment validation, directory creation, and automatic browser launch.
- **Automated Verification:** Initial unit tests for database connection and health-check endpoint.
