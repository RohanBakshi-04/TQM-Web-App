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


---

## Prompt 12: Fee & Financial Management

### 1. Fee Structure Management
- [x] Fee structures configuration (CRUD) with institutional categories
- [x] Configurations by hostel, room type, academic year, semester, frequency, and mandatory flag
- [x] Late payment fine configuration
- [x] Poka-Yoke duplicate fee structure prevention
- [x] Immutability preservation: Soft-deactivation when invoices reference structure

### 2. Invoice Generation & Billing
- [x] Single student invoice generation with unique format `INV-YYYYMM-XXXX`
- [x] Itemized fee breakdown in `invoice_items`
- [x] Bulk invoice generation for eligible hostel residents
- [x] Poka-Yoke duplicate billing prevention (skips existing resident invoices)
- [x] Concession/discount approvals with balance recalculation
- [x] Poka-Yoke excess discount rejection
- [x] Invoice cancellation with mandatory justification
- [x] Poka-Yoke payment block: Invoices with recorded payments cannot be cancelled
- [x] Official cryptographic invoice demand notice generation

### 3. Payment Processing & Audited Reversals
- [x] Full and partial student payments against invoices
- [x] Unique payment reference `PAY-YYYYMM-XXXX` and receipt number `RCP-YYYYMM-XXXX`
- [x] Automatic invoice balance and status transitions (`Partially_Paid`, `Paid`)
- [x] Poka-Yoke duplicate transaction reference and duplicate transaction ID prevention
- [x] Audited payment reversals restoring invoice balance with audit logging
- [x] Downloadable official payment receipts

### 4. Refund Management
- [x] Four-stage refund workflow (`Requested` -> `Under_Review` -> `Approved` / `Rejected` -> `Processed`)
- [x] Unique refund reference `REF-YYYYMM-XXXX`
- [x] Poka-Yoke refund limit validation: Cannot exceed payment amount minus prior refunds
- [x] Review actions: Approval, rejection with mandatory reason, processing with transaction references

### 5. Financial Dashboard & Reports
- [x] Executive financial dashboard metrics with Q05 caching and tag invalidation
- [x] Collections Report with payment method and date range filters
- [x] Dues Report with student details and room locations
- [x] Overdue Report with 4 aging analysis brackets (1-30d, 31-60d, 61-90d, 90+d)
- [x] Streaming RFC 4180 CSV export generator
- [x] Role-based financial data isolation (Auditor read-only, Student self-access, Staff forbidden)

### 6. Infrastructure & Testing
- [x] Migration `007_fee_and_financial_enhancements` with 13 composite B-Tree indexes
- [x] Total 105 automated tests passing across entire project (100% success rate)

---

## Prompt 13: Mess & Inventory Management

### 1. Mess Menu Management
- [x] Create and manage daily and weekly menus across 4 meal categories: Breakfast, Lunch, Evening Snacks, Dinner
- [x] Add multiple food items per meal with portion sizes and descriptions
- [x] Configure meal timings and dietary tags (Vegetarian, Non-Veg, Vegan, Jain, Gluten-Free)
- [x] Menu lifecycle workflow: Draft, Published, and Cancelled
- [x] Audited menu modification and cancellation with mandatory justification
- [x] Poka-Yoke duplicate menu prevention enforcing `UNIQUE(hostel_id, date, meal_type)`
- [x] Role-based access control: Only Mess Manager, Super Admin, Hostel Admin, and Warden can modify menus

### 2. Mess Subscription Management
- [x] Multiple subscription plan tiers: Monthly, Semester, and Custom date-range
- [x] Dietary preferences: Standard, Vegetarian, Non-Vegetarian, Special Dietary
- [x] Unique subscription codes `SUB-YYYYMM-XXXX`
- [x] Poka-Yoke overlapping active subscription prevention for the same student
- [x] Lifecycle statuses: Active, Suspended, Expired, Cancelled
- [x] Student self-service subscription view and cancellation with data isolation barrier

### 3. Meal Attendance & Verification
- [x] Daily meal attendance recording across all 4 meal sessions
- [x] Fast verification workflows: Manual entry desk and fast QR barcode verification (`/api/v1/mess/attendance/verify-qr`)
- [x] Active subscription verification prior to meal entry confirmation
- [x] Poka-Yoke double-punching prevention: Disallows duplicate attendance for the same student, date, and meal type
- [x] Attendance correction mechanism with mandatory reason and immutable audit log entry
- [x] Real-time mess dashboard metrics: Active subscriptions, today's meal counts, consumption by meal, and expiring subscriptions

### 4. Inventory Catalog & Item Management
- [x] Institutional category hierarchy: Provisions, Vegetables & Fruits, Dairy, Cleaning & Housekeeping, Electrical, Plumbing, Linen & Bedding, Office Supplies
- [x] Item catalog tracking: item_code, name, category, unit, quantity_in_stock, min_reorder_level, max_threshold, unit_price, supplier, location, expiry_date, status
- [x] Real-time total inventory valuation computation (`quantity_in_stock * unit_price`)
- [x] Automated low-stock detection (`quantity_in_stock <= min_reorder_level`)
- [x] Automated upcoming expiry detection (`expiry_date <= 30 days`)

### 5. Stock Transactions & Poka-Yoke Controls
- [x] Stock Inward (Receipt): Records quantity, supplier, invoice reference, purchase date, unit price, and total value with atomic stock addition
- [x] Stock Outward (Issue): Records quantity, department destination, purpose, and issuer with atomic stock deduction
- [x] **Poka-Yoke Zero-Negative Inventory:** Strictly rejects stock issues exceeding current available stock with HTTP 400 Bad Request
- [x] Immutable transaction audit history in `inventory_transactions`

### 6. Stock Adjustments & Approvals
- [x] Audited stock adjustments for Damaged, Expired, Wastage, or Discrepancy
- [x] Multi-stage approval workflow (`Pending_Approval` -> `Approved` / `Rejected`)
- [x] Authorized supervisor approval requirement for inventory write-offs
- [x] Stock Transfers: Multi-hostel inventory rebalancing with source and target location tracking

### 7. Supplier Management
- [x] Complete supplier directory CRUD: Name, contact person, phone, email, address, goods category, active status
- [x] Active status toggling and supplier-item association

### 8. Mess & Inventory Reports & RFC 4180 Streaming CSV Export
- [x] Meal consumption report with hostel, date range, and meal type breakdown
- [x] Inventory stock summary valuation report with low-stock and expiry filtering
- [x] Stock movement report with inward/outward/adjustment transaction tracking
- [x] Streaming RFC 4180 compliant CSV export generator with high-efficiency memory streaming

### 9. Database & Infrastructure
- [x] Migration `008_mess_and_inventory_enhancements` with 15 composite B-Tree indexes
- [x] In-memory cache integration with tag invalidation (`mess`, `inventory`)
- [x] Total 118 automated tests passing across entire project (100% success rate)


---

## Prompt 14: Notifications, Announcements & System Administration

### 1. Centralized Notification Center
- [x] Multi-channel notification delivery (In-App, Email, Browser Web Push)
- [x] 10 event categories: Admissions, Allocations, Attendance, Leaves, Fees, Complaints, Maintenance, Emergency, System, General
- [x] Priority levels: Normal, Important, Urgent, Critical
- [x] Poka-Yoke duplicate event prevention via cryptographic `event_key` unique index
- [x] User notification delivery preference management and category suppression toggles
- [x] Unread badge counter endpoint and instant mark-as-read / mark-all-read REST actions
- [x] Paginated notification listing with category and priority filtering

### 2. Institutional Announcements Center
- [x] Complete lifecycle: Draft -> Scheduled -> Published -> Archived
- [x] Target audience filtering (All Users, Students, Staff, Hostel Residents)
- [x] Multi-tenant hostel isolation: residents only see announcements for their assigned hostel
- [x] Resident view tracking and formal drill acknowledgement recording (`announcement_views`)
- [x] Emergency announcement alert banner integrated at the top of the frontend interface
- [x] Automated in-app notification generation upon announcement publication

### 3. System Administration
- [x] Centralized key-value system settings with category grouping
- [x] Audit change history logging in `system_setting_history`
- [x] Cache invalidation on settings update
- [x] User management: search, pagination, status toggle
- [x] Poka-Yoke Super Admin deactivation protection (user ID 1 invariant)
- [x] Role reassignment with privilege escalation prevention barrier
- [x] Administrative password reset without logging plaintext credentials
- [x] Roles & Permissions directory inspection
- [x] Core permission protection: cannot strip fundamental permissions from super_admin
- [x] Multi-criteria audit log filtering with date range, user, entity, and action
- [x] Streaming RFC 4180 CSV audit log export
- [x] Online hot SQLite WAL database backup via `sqlite3.Connection.backup()`
- [x] Backup integrity verification via `PRAGMA integrity_check`
- [x] Safe database restoration with pre-restore safety snapshots

### 4. Database & Infrastructure
- [x] Migration `009_notifications_announcements_and_admin_enhancements`
- [x] Enhanced `notifications` with `category`, `priority`, `event_key`, `delivery_channel`
- [x] Created `notification_preferences` table
- [x] Enhanced `announcements` with `status`, `category`, `priority`, `target_audience`, `target_hostel_id`
- [x] Created `announcement_views` table
- [x] Created `system_setting_history` table
- [x] Seeded 28 standard institutional settings and 3 initial announcements
- [x] Added 10 composite B-Tree indexes for sub-10ms Q05 SLA
- [x] 13 new automated tests in `test_notifications_and_admin.py`

---

## Prompt 15: Final Integration, Quality Assurance & Deployment

### 1. Complete Project Audit & Test Verification
- [x] Full test discovery: 131 automated unit and integration tests
- [x] 100% pass rate (131/131 OK) in 8.89 seconds
- [x] Fixed seeder `INSERT OR IGNORE` for system_settings idempotency
- [x] Fixed admin password reset test pollution (restored user 5 password after reset)

### 2. Q05 Performance Benchmark Suite
- [x] Created unified `scripts/benchmark_q05.py` benchmarking all 6 operation categories
- [x] Verified FTS5 search P95 = 0.369 ms (< 10.0 ms SLA)
- [x] Verified cold SQL dashboard P95 = 0.266 ms (< 10.0 ms SLA)
- [x] Verified warm cache P95 = 0.002 ms (< 0.05 ms target)
- [x] Verified cache invalidation P95 = 0.031 ms
- [x] Verified domain operations P95 = 0.037 ms
- [x] Verified scalability at 100,000 rows = 0.002 ms (logarithmic B-Tree)

### 3. Production Containerization & Deployment Assets
- [x] Created multi-stage `Dockerfile` with healthcheck endpoint probe
- [x] Created `docker-compose.yml` with persistent volumes and restart policies
- [x] Created `.dockerignore` for minimal secure image footprint
- [x] Verified `.env.example` and `requirements.txt` completeness
- [x] Verified `run.py` unified startup launcher

### 4. Comprehensive Documentation Suite
- [x] `docs/INSTALLATION_GUIDE.md` — Prerequisites, setup (Windows/Linux/Docker), demo accounts
- [x] `docs/USER_MANUAL.md` — Role-by-role workflows for all 12 stakeholder accounts
- [x] `docs/API_DOCUMENTATION.md` — Complete endpoint specifications across 21 modules
- [x] `docs/DEPLOYMENT_GUIDE.md` — Nginx reverse proxy, TLS/SSL, systemd, backup cron
- [x] `docs/TQM_FINAL_PROJECT_REPORT.md` — Academic report: TQM methodology, Q05 SLA, Poka-Yoke
- [x] Updated `README.md` with benchmark results, quick start, and documentation index
- [x] Updated `CHANGELOG.md` with Prompt 14 (v0.10.0) and Prompt 15 (v1.0.0) entries
- [x] Updated `PROJECT_PROGRESS.md` with Prompt 14 and 15 completion status
- [x] Updated `TESTING_REPORT.md` with final 131-test verification and benchmark results
- [x] Updated `IMPLEMENTATION_CHECKLIST.md` with Prompt 14 and 15 checklists

---

## RBAC Security Audit & Role Isolation Enforcement

### 1. Frontend Role-Switching Elimination
- [x] Audited all templates, headers, sidebars, modals, and user flyouts
- [x] Removed unauthorized role-switching dropdown for single-role users
- [x] Render role selector strictly for multi-role accounts (`userRoles.length > 1`)
- [x] Verified zero unauthorized role options exposed to Assistant Warden, Student, Guard, or Staff
- [x] Cleaned search modal (`Ctrl+K`) to navigate directly within permitted routes

### 2. Backend Authorization & Role Switching
- [x] Created `POST /api/v1/auth/switch-role` endpoint with strict database verification
- [x] Enforced verification that target role exists in user's assigned roles in SQLite database
- [x] Dynamic generation of updated JWT token containing `active_role` claim and re-computed permissions
- [x] Immutable audit trail logging in `audit_logs` capturing user, action, target role, and remote IP
- [x] Strict HTTP 403 Forbidden rejection for unauthorized role escalation attempts

### 3. Privileged API Defense & Data Isolation
- [x] Protected system settings (`/api/v1/admin/settings`) and user management (`/api/v1/admin/users`) strictly to Super Admin
- [x] Blocked role escalation (e.g. non-super-admins granting super_admin)
- [x] Enforced student-to-student private profile isolation
- [x] Enforced parent/guardian isolation to verified wards
- [x] Enforced functional separation: Accountant cannot approve leaves, Maintenance cannot allocate beds, Security Guard cannot access financial records
- [x] Enforced read-only restriction on Auditor role across all mutating endpoints

### 4. Automated Security Verification
- [x] 36 automated unit and security tests in `backend/tests/test_role_dashboards_and_auth.py`
- [x] Total project test suite: 167 / 167 PASS (100% success rate)
