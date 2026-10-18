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


---

## [0.2.0] - 2026-10-02 (Prompt 02: Database Architecture and Schema)

### Added
- **Relational Tables:** Complete 39 normalized tables across 8 domains (User Access, Students, Hostels, Attendance, Maintenance, Finance, Mess, System).
- **Constraints & Integrity:** Enforced primary keys, cascading/restrict foreign keys, unique indexes, and business CHECK constraints.
- **B-Tree Indexing:** 38 initial database indexes covering all foreign keys and high-frequency search columns.
- **Migration Engine:** Automated schema migration manager with version tracking table `schema_migrations`.
- **Database Seeder:** Comprehensive demonstration data seeder populating users, hostels, rooms, beds, students, and allocations.
- **Documentation:** Created technical reference in `docs/DATABASE_SCHEMA.md` and visual entity-relationship diagram in `docs/ER_DIAGRAM.md`.
- **Testing Suite:** 20 automated unit tests verifying schema integrity, constraints, cascades, rollbacks, and migrations.

---

## [0.3.0] - 2026-10-18 (Prompt 03: Authentication and RBAC System)

### Added
- **Cryptographic Security:** Integrated `bcrypt` (12 rounds) salted hashing for password storage and verification.
- **Token Infrastructure:** Stateless JWT access tokens (`HS256`, 30-min lifespan) and cryptographically random 64-byte SHA-256 refresh tokens.
- **Token Rotation & Anti-Theft:** Implemented refresh token rotation with automated token theft / reuse detection, revoking all active sessions upon breach.
- **Brute-Force Lockout:** Automated account lockout after 5 consecutive failed login attempts with a 15-minute cooldown timer.
- **Audit Logging:** Immutable `login_history` table recording remote IP, User-Agent, timestamp, status, and failure reason for every login attempt.
- **12-Role RBAC:** Built complete 12-role matrix and 173 granular permission mappings across 16 system modules.
- **FastAPI Authorization Dependencies:** Added `get_current_user`, `require_roles`, and `require_permissions` reusable dependencies.
- **Student Data Isolation Barrier:** Added `verify_student_isolation` preventing students and guardians from accessing unauthorized records.
- **Authentication REST API:** Created `/api/v1/auth/login`, `/refresh`, `/logout`, `/me`, `/change-password`, `/forgot-password`, and `/reset-password`.
- **RBAC Endpoints:** Created `/api/v1/roles`, `/permissions`, `/users`, and isolated `/students/{id}/profile`.
- **Interactive Frontend:** Updated Alpine.js app with reactive auth state, 12-role quick presets, user directory table, student portal view, and interactive isolation test button.
- **Automated Verification:** Added 16 new test cases across `test_prompt03_rbac_schema.py`, `test_auth_service.py`, and `test_auth_api.py`, expanding the test suite to 36 tests (100% pass rate).
