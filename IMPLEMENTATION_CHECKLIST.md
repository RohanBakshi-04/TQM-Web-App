# IMPLEMENTATION CHECKLIST — HOSTEL MANAGEMENT SYSTEM WEB APP

## Prompt 01: Project Initialization
- [x] Create project modular structure (`backend/`, `frontend/`, `data/`, `docs/`, `scripts/`)
- [x] Configure FastAPI ASGI application & Uvicorn entrypoint
- [x] Setup SQLite connection manager with WAL mode and foreign key enforcement
- [x] Implement centralized logger and environment configuration
- [x] Implement `/api/health` with Q05 latency telemetry
- [x] Create modern responsive HTML5 + Tailwind CSS + Alpine.js landing interface
- [x] Create one-click startup runner `run.py`
- [x] Create initial 3 conventional commits (`ab27ec1`, `d63d807`, `bc67c6f`)

---

## Prompt 02: Database Architecture and Schema

### 1. Database Configuration & Engine
- [x] SQLite3 engine configured with `PRAGMA journal_mode = WAL;`
- [x] `PRAGMA foreign_keys = ON;` strictly enforced on all connections
- [x] `PRAGMA synchronous = NORMAL;` and `PRAGMA busy_timeout = 5000;`
- [x] Database operations kept modular in `backend/app/database/`

### 2. Complete 39 Database Tables Created
- [x] **User and Access Management (1–5):** `users`, `roles`, `permissions`, `role_permissions`, `user_roles`
- [x] **Student Management (6–10):** `students`, `guardians`, `student_guardians`, `student_documents`, `admission_applications`
- [x] **Hostel Management (11–16):** `hostels`, `buildings`, `floors`, `rooms`, `beds`, `room_allocations`
- [x] **Attendance and Operations (17–20):** `attendance`, `leave_requests`, `visitors`, `visitor_logs`
- [x] **Complaints and Maintenance (21–24):** `complaints`, `complaint_updates`, `maintenance_tasks`, `maintenance_history`
- [x] **Financial Management (25–29):** `fee_structures`, `invoices`, `invoice_items`, `payments`, `refunds`
- [x] **Mess and Inventory (30–35):** `mess_menus`, `mess_subscriptions`, `meal_attendance`, `inventory_categories`, `inventory_items`, `inventory_transactions`
- [x] **System Management (36–39):** `notifications`, `announcements`, `audit_logs`, `system_settings`

### 3. Database Relationships & Constraints
- [x] Primary keys (AUTOINCREMENT) on all tables
- [x] Foreign keys with appropriate `ON DELETE` rules (`CASCADE`, `RESTRICT`, `SET NULL`)
- [x] Unique constraints on business keys (`student_id`, `email`, `(floor_id, room_number)`, `(room_id, bed_number)`)
- [x] Check constraints for capacity bounds (1–10), positive payments, valid date spans
- [x] Historical preservation of allocations and complaint updates without deletion

### 4. Database Indexing & Utilities
- [x] Created 38 initial B-Tree indexes on foreign keys and primary lookup columns
- [x] Implemented schema migration engine (`schema_migrations`)
- [x] Implemented safe demonstration data seeder (`seeder.py`) with PBKDF2 password hashing
- [x] Created comprehensive documentation in `docs/DATABASE_SCHEMA.md`
- [x] Created visual Mermaid ER diagram in `docs/ER_DIAGRAM.md`

### 5. Automated Verification & Testing
- [x] Unit test verifying all 39 tables created
- [x] Unit test verifying foreign-key orphan blocking
- [x] Unit test verifying cascading delete down hostel hierarchy
- [x] Unit test verifying unique constraints on student ID and room numbers
- [x] Unit test verifying check constraints on capacities and positive payments
- [x] Unit test verifying atomic transaction rollback on failure
- [x] Unit test verifying migration execution and seeder integration
- [x] 20/20 automated tests passing with 100% success rate


---

## Prompt 03: Authentication and RBAC System

### 1. Cryptographic Security & Password Management
- [x] Bcrypt password hashing (12 rounds) with salt generation
- [x] Zero plaintext password storage in database or memory
- [x] Safe password verification preventing timing side-channel attacks
- [x] Self-service password change API with current password verification
- [x] Token-based self-service password reset workflow

### 2. Session Management & Token Architecture
- [x] Stateless JSON Web Tokens (JWT) for access authentication (`HS256`, 30-min lifespan)
- [x] Cryptographically random refresh tokens (64-byte hex string)
- [x] Refresh tokens hashed with SHA-256 before storage in SQLite
- [x] Strict refresh token rotation: old refresh token revoked upon single exchange
- [x] Token reuse detection: revoked token reuse triggers immediate revocation of all user sessions
- [x] HttpOnly cookie support for refresh tokens with `SameSite=Lax`

### 3. Brute-Force Defense & Audit Logging
- [x] Account lockout after 5 consecutive failed login attempts
- [x] 15-minute temporary lockout cooldown period with dynamic remaining time reporting
- [x] Automatic failed counter reset on successful authentication
- [x] Immutable `login_history` audit table recording IP, User-Agent, status, and failure reason

### 4. 12 User Roles & Granular Permissions (RBAC)
- [x] Seeded all 12 system roles:
  1. `super_admin`: Global system administration
  2. `hostel_admin`: Management of assigned hostels
  3. `warden`: Student supervision, attendance, leave, complaints, and room ops
  4. `assistant_warden`: Delegated operational duties
  5. `student`: Personal profile, room, fees, attendance, complaints, and leaves
  6. `accountant`: Financial records, invoices, payments, and refunds
  7. `mess_manager`: Mess menus, subscriptions, and dining attendance
  8. `maintenance_staff`: Assigned maintenance work orders
  9. `security_guard`: Visitor records, ingress/egress logs
  10. `admission_officer`: Applications and document verification
  11. `parent_guardian`: Authorized info on linked wards
  12. `auditor`: Read-only compliance and latency reports
- [x] Granular permission actions: `CREATE`, `READ`, `UPDATE`, `DELETE`, `APPROVE`, `REJECT`, `EXPORT`, `MANAGE`
- [x] Normalized `role_permissions` mapping (173 distinct permissions mapped)
- [x] FastAPI dependencies: `get_current_user`, `require_roles`, `require_permissions`

### 5. Strict Student Data Isolation
- [x] Backend isolation barrier in `verify_student_isolation(student_id, current_user)`
- [x] HTTP 403 Forbidden returned when student queries another student's record
- [x] Parent/Guardian constrained to linked student records
- [x] Privileged roles (Wardens, Admins, Accountants) permitted authorized access

### 6. Interactive Frontend & Verification
- [x] Alpine.js reactive authentication state with automatic token renewal
- [x] 12-Role Quick Demo selector buttons for seamless multi-stakeholder testing
- [x] Real credential submission with inline error alerts and loading spinners
- [x] Multi-tab dashboard: Role overview, User Directory, Student Portal, 12-Role directory
- [x] Interactive Student Data Isolation test button verifying HTTP 403 barrier live in UI
- [x] 36 automated unit, integration, and API tests passing (100% success rate)


---

## Prompt 04: Professional UI/UX and Dashboard Framework

### 1. Application Layout & Navigation
- [x] Responsive application shell with desktop & mobile layout
- [x] Expandable and collapsible sidebar (260px expanded, 72px icon mode)
- [x] Mobile drawer overlay with touch-friendly backdrop dismissal
- [x] Role-based sidebar navigation items with active indicators
- [x] Top navigation bar with logo, hamburger, search trigger, latency badge, theme toggle, notifications, and profile dropdown
- [x] Dynamic breadcrumb navigation tracking active section and stakeholder role
- [x] Accessible keyboard navigation and focus visible ring indicators (`outline: 2px solid #2563eb`)
- [x] Modern professional footer with TQM accreditation and student details

### 2. Reusable UI Components & Design System
- [x] Reusable component module in `frontend/js/components.js`
- [x] Modern KPI dashboard stat cards with responsive grid
- [x] Data table component with hover elevation and responsive scroll wrap
- [x] Live search filter input and status dropdown filters
- [x] Reusable pagination controls (`paginate(items, page, pageSize)`)
- [x] Reusable confirmation dialog and modal wrapper
- [x] Floating toast notification queue with auto-dismissal
- [x] Status badge styling generator (`getStatusBadge(status)`)
- [x] Zero-dependency SVG sparkline and mini bar chart renderers (< 0.1ms render time)
- [x] Accessible empty states with icons, titles, and action placeholders
- [x] Full Light and Dark mode styling across all components with local storage persistence

### 3. All 12 Stakeholder Role Dashboards Implemented
- [x] 1. `super_admin`: Total hostels, students, users, overall occupancy, system activity feed, user directory
- [x] 2. `hostel_admin`: Hostel occupancy, room availability, student stats, pending complaints, floor-by-floor breakdown
- [x] 3. `warden`: Student attendance check, pending leave approvals, complaints card, hostel notices
- [x] 4. `assistant_warden`: Operational rounds checklist, attendance log verification, gate entry checks
- [x] 5. `student`: Personal profile, room and bed info, fee status, attendance, leave requests, isolation barrier test
- [x] 6. `accountant`: Total invoiced, total collected, outstanding dues, fee receipts review, zero pending anomalies
- [x] 7. `mess_manager`: Today's 4-Meal dining schedule (Breakfast, Lunch, Snacks, Dinner), subscriptions, inventory alerts
- [x] 8. `maintenance_staff`: Assigned task count, pending repairs, weekly completed work orders, repair queue
- [x] 9. `security_guard`: Campus visitors count, gate entry/exit log, outpass barcode/enrollment verification scanner
- [x] 10. `admission_officer`: Application review pipeline (Submitted, Approved, Verified), candidate intake statistics
- [x] 11. `parent_guardian`: Linked ward oversight (Rohan Bakshi), attendance percentage, fee clearance receipt, leave history
- [x] 12. `auditor`: TQM audit log trail, financial consistency review, Q05 Response Time SLA performance telemetry

### 4. Backend Aggregation & Verification
- [x] Created `backend/app/routers/dashboard.py` implementing `GET /api/v1/dashboard/stats`
- [x] Registered dashboard router in `backend/app/main.py`
- [x] Automated integration tests in `backend/tests/test_dashboard_api.py`
- [x] 38 automated unit, integration, and API tests passing (100% success rate)

---

## Prompt 07: Room Allocation and Poka-Yoke System

### 1. Database & Schema Enhancements (Migration 003)
- [x] Added `approval_status`, `checkin_date`, `checkout_date`, `checkout_reason` to `room_allocations`
- [x] Enforced B-Tree Partial Unique Index `uq_active_bed_allocation` on `room_allocations(bed_id) WHERE allocation_status = 'Active'`
- [x] Enforced B-Tree Partial Unique Index `uq_active_student_allocation` on `room_allocations(student_id) WHERE allocation_status = 'Active'`
- [x] Created `room_transfers` table for tracked room transfer requests and audit trail
- [x] Created secondary performance indexes on allocation lookups

### 2. Poka-Yoke Defect Prevention System (10/10 Rules)
- [x] **Rule 1:** Prevent allocating one bed to multiple active students (B-Tree index + backend guard)
- [x] **Rule 2:** Prevent allocating students to full rooms (Bound by capacity constraints 1-10)
- [x] **Rule 3:** Prevent allocating students to inactive/maintenance beds
- [x] **Rule 4:** Prevent allocating students to rooms under maintenance
- [x] **Rule 5:** Prevent allocating students to inactive hostels or buildings
- [x] **Rule 6:** Prevent allocating students to restricted hostels (Gender mismatch barrier)
- [x] **Rule 7:** Prevent creating duplicate active allocations for the same student
- [x] **Rule 8:** Prevent transferring students to unavailable or occupied beds
- [x] **Rule 9:** Prevent checking out students with no active allocation & duplicate checkout prevention
- [x] **Rule 10:** Enforce RBAC authorization on allocations and reviews (Student forbidden from approving allotments)

### 3. Intelligent Room Allocation Suggestions
- [x] Implemented multi-criteria matching engine (`GET /api/v1/allocations/suggestions`)
- [x] Evaluates student eligibility, gender constraints, room preferences, cohort branch/year peer clustering
- [x] Prioritizes space optimization and partially occupied room consolidation
- [x] Transparent score breakdown and human-readable justification reasons

### 4. Lifecycle & Transfer Management
- [x] Check-in verification endpoint (`POST /api/v1/allocations/{id}/checkin`)
- [x] Check-out with bed status release and room status recalculation (`POST /api/v1/allocations/{id}/checkout`)
- [x] Atomic student room/bed transfer transactions (`POST /api/v1/allocations/{id}/transfer`, `/api/v1/transfers`)
- [x] Cryptographic allocation confirmation certificate with SHA-256 verification hash

### 5. Frontend Dashboard & Student Integration
- [x] Allocation Management tab with real-time metrics and Available Beds grid
- [x] Interactive New Allocation Modal with AI Suggestion launcher
- [x] Interactive Room Transfer Modal and Check-Out Modal
- [x] Printable Allocation Confirmation Slip Modal
- [x] Student Dashboard integration displaying assigned room, bed, facility, and transfer request button

### 6. Automated Testing & Verification
- [x] 16 comprehensive Poka-Yoke and allocation lifecycle tests in `backend/tests/test_room_allocations.py`
- [x] Multi-threaded concurrency race condition test proving zero double bookings
- [x] All 54 tests passing across the entire project with 100% success rate
