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


---

## [0.4.0] - 2026-10-28 (Prompt 04: Professional UI/UX and Dashboard Framework)

### Added
- **Modern Application Shell:** Built responsive layout with collapsible/expandable sidebar (72px vs 260px), mobile overlay drawer, top navigation bar, and breadcrumbs.
- **Light & Dark Theme Engine:** Implemented theme toggle with local storage persistence using Tailwind CSS `class` strategy.
- **Reusable Component System:** Created `frontend/js/components.js` providing status badge styling, pagination engine, zero-dependency SVG sparklines, and mini bar charts.
- **Micro-Interactions & Modals:** Added reusable confirmation modal dialog, floating toast notification queue (`success`, `error`, `warning`, `info`), and quick search modal (`Ctrl + K`).
- **All 12 Role-Specific Dashboards:** Delivered purpose-built interfaces tailored to each stakeholder role with custom telemetry cards and operation tables.
- **Backend Telemetry Router:** Created `GET /api/v1/dashboard/stats` aggregating real-time counts and occupancy rates across operational domains.

---

## [0.5.0] - 2026-10-30 (Prompt 07: Room Allocation and Poka-Yoke System)

### Added
- **Database Schema Migration 003:** Added allocation lifecycle columns (`approval_status`, `checkin_date`, `checkout_date`, `checkout_reason`) and created `room_transfers` table.
- **Poka-Yoke Partial Unique Indexes:** Enforced database-level mistake-proofing via `uq_active_bed_allocation` and `uq_active_student_allocation` on SQLite B-Tree engine.
- **Complete Allocation REST API:**
  - `POST /api/v1/allocations`: Defect-proof student room and bed allocation.
  - `GET /api/v1/allocations`: High-performance allocation listing with filtering by facility, room type, status, and search query.
  - `GET /api/v1/allocations/{id}`: Detailed allocation view with confirmation metadata.
  - `GET /api/v1/allocations/available-beds`: Real-time assignable inventory explorer.
  - `GET /api/v1/rooms/{id}/occupants`: Active residents lookup for a room.
  - `GET /api/v1/students/{id}/allocation-history`: Complete chronological residency history.
- **Intelligent Room Allocation Engine (`GET /api/v1/allocations/suggestions`):**
  - Multi-criteria scoring algorithm assessing student eligibility, gender constraints, room preferences, and peer clustering.
  - Cohort matching for branch/academic year and occupancy consolidation prioritization.
- **Atomic Transfer & Lifecycle Operations:**
  - `POST /api/v1/allocations/{id}/checkin`: Student check-in timestamping and verification.
  - `POST /api/v1/allocations/{id}/checkout`: Bed release, room status recalculation, and historical preservation.
  - `POST /api/v1/allocations/{id}/transfer`: Atomic room transfer releasing old bed and occupying new bed in a single transaction.
  - `GET /api/v1/transfers` & `POST /api/v1/transfers/{id}/review`: Administration review queue for pending transfer requests.
- **Cryptographic Allocation Confirmation Slip:** Generates printable certificates with SHA-256 verification hash and unique confirmation numbers (`TQM-ALC-XXXXXX`).
- **Frontend Allocation Management Dashboard:** Interactive management UI featuring metrics cards, available beds grid, allocation table, AI suggestions modal, and transfer/checkout actions.
- **Student Dashboard Integration:** Embedded assigned room, bed number, facility details, and interactive transfer request button in resident view.
- **Comprehensive Test Suite (`test_room_allocations.py`):** 16 rigorous tests validating all 10 Poka-Yoke rules, multi-threaded concurrency safety, suggestion engine, check-in, check-out, and atomic transfers.
- **Total Test Coverage:** 54 passing automated tests across the application.
- **12 Tailored Dashboards:** Created dedicated stakeholder interfaces for all 12 roles (`super_admin`, `hostel_admin`, `warden`, `assistant_warden`, `student`, `accountant`, `mess_manager`, `maintenance_staff`, `security_guard`, `admission_officer`, `parent_guardian`, `auditor`).
- **Live Metrics API:** Implemented `GET /api/v1/dashboard/stats` in `backend/app/routers/dashboard.py` querying real SQLite tables.
- **Automated Verification:** Added `backend/tests/test_dashboard_api.py`, expanding the test suite to 38 tests (100% pass rate).

---

## [0.7.0] - 2026-10-31 (Prompt 11: Attendance, Leave & Visitor Management)

### Added
- **Attendance Management Module:**
  - Daily student attendance marking across all hostels, floors, and rooms.
  - Poka-Yoke duplicate marking prevention (`UNIQUE(student_id, date)`).
  - Attendance corrections with mandatory audit trail (`attendance_corrections`).
  - Daily aggregated summaries and automated repeat absentee detection (>= 3 absences).
  - Date-range and monthly attendance reports with percentage calculation.
- **Leave & Outpass Engine:**
  - Complete multi-status leave application lifecycle with warden approval workflow.
  - Automated digital gate outpass generation (`OP-YYYYMM-XXXX`).
  - Gatekeeper exit and return verification with duplicate exit/return prevention.
  - Real-time curfew overdue tracking.
- **Visitor Pass Management:**
  - Visitor registration with active visit limits per phone number.
  - Digital visitor passes (`VP-YYYYMM-XXXX`) with entry and expected departure windows.
  - Gate check-in and check-out verification.
  - Role-based privacy masking of government ID numbers (`XXXX-XXXX-1234`).
- **Database Schema Migration 006:**
  - Added `attendance_corrections` and `outpasses` tables.
  - Added composite indexes for sub-10ms query performance.
- **Testing Suite:**
  - Added 11 tests in `backend/tests/test_attendance_leave_visitors.py`.
  - Expanded total test suite to 95 tests (100% passing).


---

## [0.8.0] - 2026-10-31 (Prompt 12: Fee & Financial Management)

### Added
- **Fee Structure Engine:** Complete CRUD with institutional categories, room types, academic years, semesters, payment frequencies, and soft-deactivation.
- **Invoicing System:** Single and bulk invoice generation (`INV-YYYYMM-XXXX`), breakdown items, concession/discount approvals, and audited cancellation.
- **Payment Processing:** Full and partial payments (`PAY-YYYYMM-XXXX`), balance updates, duplicate checks, cryptographic receipts (`RCP-YYYYMM-XXXX`), and audited reversals.
- **Refund Lifecycle:** Four-stage refund management (`Requested` -> `Under_Review` -> `Approved` / `Rejected` -> `Processed`) with refundable balance capping.
- **Executive Financial Dashboard:** Sub-10ms cached analytics (total invoiced, collected, dues, overdue, collection rate %, monthly collections, payment methods breakdown).
- **Financial Reports & CSV Export:** Collections, Dues, Overdue Aging (4 brackets), and Refunds reports with instant streaming CSV export.
- **Database Migration 007:** Non-destructive enhancement for `fee_structures`, `invoices`, `payments`, `refunds`, and 13 composite B-Tree indexes.
- **Testing Suite:** 10 new tests in `backend/tests/test_fee_and_finance.py`, expanding the complete application suite to 105 tests (100% pass rate).

---

## [0.10.0] - 2026-11-01 (Prompt 14: Notifications, Announcements & System Administration)

### Added
- **Centralized Notification Center:**
  - Multi-channel notification delivery (In-App, Email, Browser Web Push).
  - Categorization across 10 event types: Admissions, Allocations, Attendance, Leaves, Fees, Complaints, Maintenance, Emergency, System.
  - Priority levels: Normal, Important, Urgent, Critical.
  - Poka-Yoke duplicate alert prevention using cryptographic `event_key` cooldown index.
  - User notification delivery preferences and category suppression toggles.
  - Unread badge counter and instant mark-as-read REST endpoints.
- **Institutional Announcements Center:**
  - Complete lifecycle management: Draft -> Scheduled -> Published -> Archived.
  - Target audience filtering (All, Students, Staff, Hostel Residents) with strict multi-tenant hostel isolation.
  - Resident view tracking and formal drill acknowledgement recording (`announcement_views`).
  - Real-time emergency announcement alert banner integrated at the top of the frontend interface.
- **System Administration:**
  - Centralized key-value system settings with category grouping and audit change history (`system_setting_history`).
  - User management: Status toggle with Poka-Yoke Super Admin deactivation protection; Role updates with privilege escalation barrier.
  - Administrative password resets without logging plaintext credentials.
  - Roles & Permissions directory and core permission protection.
  - Multi-criteria audit log filtering with streaming RFC 4180 CSV export.
  - Online hot SQLite WAL database backups with `PRAGMA integrity_check` verification.
- **Database Schema Migration 009:**
  - Enhanced `notifications`, created `notification_preferences`, enhanced `announcements`, created `announcement_views`, created `system_setting_history`.
  - Added 10 composite B-Tree indexes for sub-10ms query execution.
- **Testing Suite:**
  - 13 comprehensive unit and integration tests in `backend/tests/test_notifications_and_admin.py`.

---

## [1.0.0] - 2026-11-01 (Prompt 15: Final Integration, Quality Assurance & Deployment)

### Added
- **Unified Q05 Performance Benchmark Suite:**
  - Implemented `scripts/benchmark_q05.py` testing FTS5 search, indexed queries, cold SQL dashboard, warm cache, invalidation speed, and 100k-row scalability.
  - Empirically verified all P95 latencies operate under 0.5 ms, surpassing the < 10.0 ms SLA by a 20x factor.
- **Comprehensive Quality Assurance:**
  - Complete test discovery running all 131 automated unit and integration tests with a 100% pass rate in 8.89 seconds.
  - Fixed test pollution in admin password reset test and ensured idempotency across test database re-seeding.
- **Production Containerization & Deployment Assets:**
  - Created multi-stage `Dockerfile` with healthcheck endpoint probe.
  - Created `docker-compose.yml` with persistent volume mappings and automatic restart policies.
  - Created `.dockerignore` for minimal, secure image footprints.
- **Comprehensive Documentation Suite:**
  - Authored `docs/INSTALLATION_GUIDE.md` covering prerequisites, Windows/Linux setup, and containerized deployment.
  - Authored `docs/USER_MANUAL.md` with role-by-role workflows across all 12 stakeholder accounts.
  - Authored `docs/API_DOCUMENTATION.md` documenting all endpoints across 21 functional domains.
  - Authored `docs/DEPLOYMENT_GUIDE.md` covering Nginx reverse proxy, TLS/SSL, systemd unit, and SQLite backup cron jobs.
  - Authored `docs/TQM_FINAL_PROJECT_REPORT.md` providing an exhaustive academic project report on TQM methodology, Deming PDCA, Q05 (< 10ms SLA), and Poka-Yoke error-proofing.
- **Release Finalization:**
  - Synchronized and verified all documentation, changelogs, implementation checklists, and progress tracking files.

### Added
- **Mess Menu System:**
  - Daily and weekly menus across 4 meal categories: Breakfast, Lunch, Evening Snacks, Dinner.
  - Multi-item scheduling with portion sizes, nutritional notes, and meal timings.
  - Draft, Published, and Cancelled lifecycle with audited cancellation reason.
  - Poka-Yoke duplicate menu prevention enforcing `UNIQUE(hostel_id, date, meal_type)`.
- **Mess Subscriptions:**
  - Monthly, Semester, and Custom date-range subscription tiers with dietary preferences (Veg, Non-Veg, Special).
  - Unique subscription reference `SUB-YYYYMM-XXXX`.
  - Poka-Yoke overlapping active subscription prevention for the same student.
  - Student self-service subscription views and cancellations with RBAC data isolation.
- **Meal Attendance Verification:**
  - Rapid meal attendance logging with active subscription verification.
  - Fast QR code verification workflow (`/api/v1/mess/attendance/verify-qr`) and manual desk punch.
  - Poka-Yoke duplicate attendance prevention blocking double-punching in the same meal session.
  - Audited attendance corrections with mandatory justification and audit log tracking.
  - Real-time mess dashboard KPI aggregation.
- **Inventory & Stock Management:**
  - Institutional item catalog tracking stock on hand, min reorder levels, max thresholds, and valuations.
  - Real-time low-stock alerts and 30-day upcoming expiry alerts.
  - Stock Inward (Receipt): Inward transaction with supplier, invoice ref, unit price, and atomic stock increment.
  - Stock Outward (Issue): Outward transaction with department, purpose, and atomic stock decrement.
  - **Poka-Yoke Zero-Negative Inventory:** Outward requests exceeding available stock are strictly rejected with HTTP 400 Bad Request.
  - Stock Adjustments: Audited adjustments (Damaged, Expired, Wastage, Discrepancy) with supervisor approval workflow (`Pending_Approval` -> `Approved` / `Rejected`).
  - Stock Transfers: Multi-hostel inventory rebalancing with source and target location tracking.
- **Supplier Directory:**
  - Complete supplier CRUD: Name, contact person, phone, email, address, goods category, active status.
- **Mess & Inventory Reports & CSV Export:**
  - Meal consumption report with hostel, date range, and meal type breakdown.
  - Stock summary valuation report and stock movement audit report.
  - Streaming RFC 4180 compliant CSV export generator.
- **Database Schema Migration 008:**
  - Non-destructive enhancement of `mess_menus`, `mess_subscriptions`, `meal_attendance`, `inventory_items`, `inventory_transactions`, `suppliers`.
  - 15 composite B-Tree indexes for sub-10ms Q05 SLA query execution.
- **Testing Suite:**
  - 13 comprehensive unit and integration tests in `backend/tests/test_mess_and_inventory.py`.
  - Expanded total test suite to 118 tests (100% pass rate).

---

## [1.1.0] - 2026-11-01 (RBAC Security Audit, Role Isolation & Unauthorized Role Switching Elimination)

### Security Fixes
- **Elimination of Unauthorized Frontend Role-Switching:**
  - Identified and eradicated frontend vulnerability where authenticated users (e.g., Assistant Warden) could view and select arbitrary stakeholder dashboards (including Super Admin) from a header dropdown.
  - Restricted role switcher display strictly to multi-role accounts (`userRoles.length > 1`). Single-role accounts no longer render any role switching selector, dropdown, or unassigned roles.
  - Removed unauthorized role switching triggers from the search modal (`Ctrl+K`) and user profile flyouts.
- **Backend Role Authorization & Multi-Role Switching API:**
  - Implemented secure backend endpoint `POST /api/v1/auth/switch-role` validating that the requested target role is explicitly assigned to the user in the database.
  - Enforced JWT `active_role` claim injection and runtime permission re-computation upon valid role switch.
  - Implemented immutable audit logging in `audit_logs` tracking every role change attempt with client IP address, user agent, and timestamp.
  - Single-role users and unauthorized privilege escalation attempts are strictly rejected with HTTP 403 Forbidden.
- **Privileged API & Data Isolation Barriers:**
  - Verified backend RBAC enforcement preventing non-Super-Admin roles (e.g. Assistant Warden, Hostel Admin) from accessing system administration, user management, and system settings mutation endpoints.
  - Verified student data isolation: students cannot access peer profiles; unlinked guardians cannot access student records; accountants cannot approve leaves; maintenance staff cannot allocate beds; security guards cannot access financial billing; auditors cannot mutate operational records.

### Added
- **Role Isolation & Security Test Suite:**
  - Created 36 comprehensive security and integration tests in `backend/tests/test_role_dashboards_and_auth.py`.
  - Total automated test suite expanded to **167 tests with 100% pass rate**.
