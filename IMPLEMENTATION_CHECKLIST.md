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

---

## Prompt 08: Q05 Fast Search and Database Indexing

### 1. Unified Fast Search System
- [x] Multi-domain search endpoint: `GET /api/v1/search`
- [x] Full support across Students, Hostels, Rooms, Beds, Allocations, Complaints, Maintenance, Payments
- [x] Parameterized SQL query execution completely eliminating SQL injection vulnerabilities
- [x] Case-insensitive matching across uppercase, lowercase, and mixed-case tokens
- [x] Prefix search token expansion (`LIKE 'term%'` and `term*`)
- [x] Category filtering pills (*All Entities*, *Students*, *Hostels*, *Rooms*, *Allocations*, *Complaints*, *Payments*)
- [x] Strict Role-Based Access Control and data isolation (Students blocked from financial payment records)
- [x] Facility-scoped search boundaries for hostel administrators and wardens

### 2. SQLite FTS5 Full-Text Virtual Indexing
- [x] Virtual table `search_index_fts` configured with `tokenize = 'porter unicode61'`
- [x] BM25 relevance ranking calculation returning sorted matches
- [x] Administrative index synchronization utility (`POST /api/v1/search/rebuild-index`) restricted to Super Admin and Auditors

### 3. Database Indexes Optimization (Migration 004)
- [x] `idx_students_name`: Composite B-Tree on `students(first_name, last_name)`
- [x] `idx_rooms_number`: Single B-Tree on `rooms(room_number)`
- [x] `idx_complaints_created_at`: Ordered B-Tree on `complaints(created_at DESC)` eliminating in-memory sorting
- [x] `idx_complaints_status_date`: Composite B-Tree on `complaints(status, created_at DESC)`
- [x] `idx_maintenance_status`: Single B-Tree on `maintenance_tasks(status)`
- [x] `idx_payments_ref_tx`: Composite B-Tree on `payments(payment_reference, transaction_id)`
- [x] `idx_allocations_status_date`: Composite B-Tree on `room_allocations(allocation_status, start_date DESC)`
- [x] `idx_hostels_active_type`: Composite B-Tree on `hostels(is_active, hostel_type)`
- [x] `idx_visitors_name_phone`: Composite B-Tree on `visitors(name, phone)`
- [x] Query plan verification with `EXPLAIN QUERY PLAN` confirming index usage

### 4. Synthetic Multi-Tier Benchmarks
- [x] Benchmarking harness `scripts/benchmark_search.py` evaluating 1,000, 10,000, 50,000, and 100,000 records
- [x] Evaluates Table Scans vs Python In-Memory vs B-Tree vs SQLite FTS5
- [x] Confirmed FTS5 sub-millisecond execution ($< 0.35\text{ ms}$ p50, $< 1.25\text{ ms}$ p95 at 100k records)
- [x] Documented results in `docs/PERFORMANCE_BENCHMARKS.md`

### 5. Frontend Quick Search Modal (Ctrl + K)
- [x] Keyboard shortcut `Ctrl + K` (or `Cmd + K`) launcher with ESC to close
- [x] 250ms debounced user input
- [x] Live response time latency badge (`⚡ 1.25 ms (<10ms SLA)`)
- [x] Category filter tab pills
- [x] Search result keyword highlighting with `<mark>` tags
- [x] Direct entity navigation on result click
- [x] Fallback role dashboard presets when input is empty

### 6. Documentation & Testing
- [x] Created `docs/Q05_FAST_SEARCH.md` (Search architecture & security isolation)
- [x] Created `docs/DATABASE_INDEXES.md` (Index catalog, query plans, write overhead)
- [x] Created `docs/PERFORMANCE_BENCHMARKS.md` (Empirical latency measurements)
- [x] Created 10 automated tests in `backend/tests/test_fast_search.py`
- [x] Total 64 automated tests passing across the entire project (100% success rate)

---

## Prompt 09: Q05 Cached Dashboard and Quick Navigation

### 1. In-Memory Cache Service
- [x] Implemented thread-safe `CacheService` with `threading.RLock()` in `backend/app/services/cache_service.py`
- [x] Configurable TTL (60s default) with passive and active eviction
- [x] In-memory telemetry: hits, misses, hit ratio %, active entries, evictions, uptime
- [x] Partitioned deterministic cache keys: `dashboard:role:{role}:hostel:{hostel_id}:user:{user_id}`
- [x] Multi-tenant facility isolation preventing cross-hostel data leakage

### 2. Automatic Dependency-Based Invalidation
- [x] Dependency-based invalidation engine in `backend/app/services/cache_invalidation.py`
- [x] Invalidation triggers for students, hostels, buildings, rooms, beds, allocations, complaints, maintenance, payments, admissions
- [x] Atomic post-commit guarantee: Invalidation executed strictly after successful `conn.commit()`
- [x] Rollback safety: Aborted or failed transactions do not invalidate or corrupt cached entries
- [x] Fine-grained hostel scoping: Invalidation of Hostel 1 leaves Hostel 2 cache intact

### 3. Dashboard API Optimization
- [x] High-performance endpoint: `GET /api/v1/metrics/dashboard`
- [x] Full support for role-specific and facility-specific scoping
- [x] Cache stats telemetry endpoint: `GET /api/v1/metrics/cache/stats`
- [x] Admin cache flush endpoint: `POST /api/v1/metrics/cache/clear`
- [x] Pre-warming cache on application startup sequence in `backend/app/main.py`
- [x] Backward compatibility preserved for `GET /api/v1/dashboard/stats`

### 4. Quick Navigation & Frontend Performance
- [x] Persistent Single Page Application (SPA) shell with Alpine.js reactive components
- [x] Client-side request deduplication (`API.deduplicatedFetch`) preventing redundant simultaneous queries
- [x] State preservation across view switches (active role dashboard, search filters, pagination offsets)
- [x] Sub-0.1ms client-side view transition latency

### 5. Performance Benchmarks
- [x] Benchmark harness: `scripts/benchmark_dashboard_cache.py`
- [x] Cold Cache: $0.049\text{ ms}$ (p50), Warm Cache: $0.001\text{ ms}$ (p50)
- [x] Tag Invalidation Turnaround: $0.019\text{ ms}$ (p50)
- [x] Warm Hit Ratio: $98.8\%$
- [x] Recorded in `docs/PERFORMANCE_BENCHMARKS.md`

### 6. Documentation & Automated Testing
- [x] Created `docs/Q05_CACHED_DASHBOARD.md`
- [x] Created `docs/Q05_QUICK_NAVIGATION.md`
- [x] Updated `docs/PERFORMANCE_BENCHMARKS.md`
- [x] 10 comprehensive tests in `backend/tests/test_cached_dashboard.py`
- [x] Total 74 automated tests passing across the entire project (100% success rate)


---

## Prompt 11: Attendance, Leave & Visitor Management

### 1. Attendance Management
- [x] Daily student attendance recording with status options (`Present`, `Absent`, `On Leave`, `Not Marked`)
- [x] Room-by-room batch marking roster by hostel, building, floor, and room
- [x] Authorized staff access control (Warden, Assistant Warden, Super Admin, Hostel Admin)
- [x] Poka-Yoke duplicate prevention via database `UNIQUE(student_id, date)` constraint
- [x] Immutable correction audit log (`attendance_corrections`) requiring mandatory justification
- [x] Daily attendance metrics aggregation and repeat absentee detection (>= 3 absences in 30 days)
- [x] Comprehensive date-range and monthly attendance reports with percentage calculation

### 2. Leave & Gate Outpass Management
- [x] Student leave request workflow (`Draft` -> `Submitted` -> `Approved` / `Rejected` / `Cancelled`)
- [x] Poka-Yoke self-approval defense: Students strictly blocked from approving own leaves (HTTP 403)
- [x] State transition integrity: Rejected/Cancelled applications cannot be approved
- [x] Overlapping active leave prevention
- [x] Automated digital gate outpass generation (`OP-YYYYMM-XXXX`) upon warden approval
- [x] Security officer gate verification (`verify-exit` and `verify-return`)
- [x] Poka-Yoke exit/return defenses: Duplicate exits and premature returns rejected
- [x] Real-time overdue curfew tracking for students outside campus premises

### 3. Visitor Management & Security Passes
- [x] Complete visitor registration capturing full credentials and host resident link
- [x] Duplicate active visit prevention for the same contact number
- [x] Digital visitor entry pass generation (`VP-YYYYMM-XXXX`)
- [x] Gatekeeper check-in and check-out verification
- [x] Real-time active visitors tracking on campus premises
- [x] Overdue visit tracking flagging passes exceeding scheduled duration
- [x] Role-based privacy masking: Government ID proof numbers masked (`XXXX-XXXX-1234`) for resident students

### 4. Database & Infrastructure
- [x] Migration `006_attendance_leave_visitor_enhancements` adding `attendance_corrections` and `outpasses`
- [x] B-Tree composite indexes for attendance, leaves, outpasses, and visitor logs
- [x] Total 95 tests passing across complete application test suite (100% success rate)
