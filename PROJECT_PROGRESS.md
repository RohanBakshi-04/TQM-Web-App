# PROJECT PROGRESS — HOSTEL MANAGEMENT SYSTEM WEB APP

**Course:** BBAT104 – Fundamentals of Total Quality Management (TQM)  
**Academic Session:** 2026–27  
**Quality Goal:** Q05 – Reduce Response Time  
**Baseline System:** Hostel Management System (Web Application)  
**Repository:** [https://github.com/RohanBakshi-04/TQM-Web-App](https://github.com/RohanBakshi-04/TQM-Web-App)

---

## 📌 Phase Progress Overview

| Phase / Prompt | Scope & Objectives | Status | Commits |
| :--- | :--- | :---: | :---: |
| **Prompt 01: Project Initialization** | Modular architecture, FastAPI setup, SQLite WAL mode, centralized logging, Alpine.js frontend skeleton, health endpoint, run.py launcher | 🟢 Completed | `ab27ec1`, `d63d807`, `bc67c6f` |
| **Prompt 02: Database & Schema** | Complete 39-table schema across 8 domains, B-Tree indexes, migrations engine, safe seeder, tests & ER diagram | 🟢 Completed | `ff25327`, `536c801`, `744dae5`, `8d54c2d` |
| **Prompt 03: Authentication & RBAC** | Enterprise 12-Role RBAC, bcrypt password hashing, JWT access tokens, refresh token rotation with reuse detection, student data isolation, login lockout & audit logging | 🟢 Completed | `7b00b92`, `e6954b4`, `6b49e04`, `dffabd7` |
| **Prompt 04: UI/UX & Dashboards** | Modern SaaS application shell, responsive collapsible sidebar, light/dark themes, reusable UI component library, and tailored dashboards for all 12 stakeholder roles | 🟢 Completed | `d5d71f4`, `06a7f4b`, `3c37643` |
| **Prompt 06: Infrastructure & Facility Engine** | Hostel, Building, Floor, Room, Bed hierarchy with dynamic capacity and occupancy calculation engine | 🟢 Completed | Included in Foundation |
| **Prompt 07: Room Allocation & Poka-Yoke** | Defect-proof student room & bed allocation, multi-criteria AI suggestion engine, atomic room transfers, check-in/check-out lifecycle, 10 Poka-Yoke barriers, concurrency protection, allocation dashboard & confirmation certificates | 🟢 Completed | `f403357`, `39395ad`, `6d8d0c1`, `a96d1e7` |
| **Prompt 08: Q05 Fast Search & Database Indexing** | Sub-10ms centralized search across students, hostels, rooms, allocations, complaints, maintenance, payments; SQLite FTS5 virtual engine; 9 B-Tree composite indexes; automated query plan verification; multi-tier benchmarks (1k-100k records); frontend Ctrl+K modal with debouncing & highlighting | 🟢 Completed | `47d9589`, `5b67acc`, `ea5c109` |
| **Prompt 09: Q05 Cached Dashboard & Quick Navigation** | Thread-safe in-memory cache engine with TTL, dependency tag invalidation (students, hostels, rooms, allocations, complaints, finance), sub-0.05ms warm response time, role-based multi-tenant hostel isolation, SPA persistent shell, client-side request deduplication | 🟢 Completed | `1690967`, `26b5821` |
| **Prompt 10: Complaint and Maintenance Management** | Student complaint submission across 10 categories & 4 severities, automated SLA escalation tracking, maintenance work orders with parts & cost tracking, supervisor verification, and feedback loop | 🟢 Completed | `3137962`, `a4087e6`, `90263f3` |
| **Prompt 11: Attendance, Leave & Visitor Management** | Daily attendance tracking with duplicate prevention, biometric corrections with audit reason, repeat absentee detection; leave applications with automated digital gate outpasses (OP-YYYYMM-XXXX), gate exit/return verification, overdue tracking; visitor registration with active visit limits, digital visitor passes (VP-YYYYMM-XXXX), gate check-in/out, and ID privacy masking | 🟢 Completed | `407949a`, `9f14e48`, `a26ea17`, Staged Commit 4 |
| **Prompt 12: Fee & Financial Management** | Fee structures, student invoicing (single & bulk INV-YYYYMM-XXXX), concessions, payments (PAY-YYYYMM-XXXX), official receipts (RCP-YYYYMM-XXXX), reversals, refunds (REF-YYYYMM-XXXX), Q05 executive financial dashboard, collections, dues, overdue aging reports, and streaming CSV export | 🟢 Completed | `5ff017e`, `4449577`, `98e7bfd` |
| **Prompt 13: Mess & Inventory Management** | Daily/weekly mess menus, dietary subscriptions, meal attendance tracking with QR verification, inventory items, suppliers, inward/outward transactions, Poka-Yoke zero-negative stock prevention, stock adjustments, low-stock/expiry alerts, consumption & stock reports, streaming CSV export | 🟢 Completed | `ba33ec7`, `fc154e6`, `98e7bfd` |
| **Prompt 14: Notifications, Announcements & Administration** | Centralized notification center with multi-channel routing, event deduplication, user preferences, institutional announcements with hostel isolation & read acknowledgement, system settings history, user admin, audit logs with RFC 4180 export, online SQLite backups | 🟢 Completed | `6c103e8`, Final Release Commit 1 |
| **Prompt 15: Final Integration, QA & Deployment** | Full integration of 21 domains, 131/131 passing tests (100% pass), empirical Q05 benchmark verification (<10ms SLA), Docker & docker-compose containerization, exhaustive academic TQM report, and complete deployment guides | 🟢 Completed | Final Release Commits 1 & 2 |

---

## 🎯 Prompt 11 Attendance, Leave & Visitor Management Deliverables Checklist

- [x] **Attendance Management Module (`backend/app/services/attendance_service.py` & `/api/v1/attendance`):**
  - Daily student attendance marking (`Present`, `Absent`, `On Leave`, `Not Marked`) with authorized staff verification.
  - Multi-level filtering by Hostel, Building, Floor, Room, Date, and Status.
  - Poka-Yoke duplicate marking prevention via database `UNIQUE(student_id, date)` constraint.
  - Transparent audit correction logging (`attendance_corrections`) with mandatory justification reasoning.
  - Daily aggregated summaries (Present, Absent, On Leave, Not Marked, Attendance %) and automated repeat absentee detection (>= 3 unexcused absences within 30 days).
  - Date-range and monthly attendance reports with per-student attendance rate calculation.
- [x] **Leave & Gate Outpass Engine (`backend/app/services/leave_service.py`, `/api/v1/leave`, `/api/v1/outpasses`):**
  - Complete multi-status student leave workflow (`Draft` -> `Submitted` -> `Approved` / `Rejected` / `Cancelled`).
  - Strict Poka-Yoke validation: student self-approval prevention, historical state transition locks, overlapping active leave blocking.
  - Automated digital gate outpass generation (`OP-YYYYMM-XXXX`) upon warden/administrator leave approval.
  - Gatekeeper exit and return verification (`/api/v1/outpasses/{id}/verify-exit`, `/api/v1/outpasses/{id}/verify-return`) preventing duplicate exits and premature returns.
  - Real-time overdue curfew tracking identifying residents outside campus past expected return time.
- [x] **Visitor Management Module (`backend/app/services/visitor_service.py` & `/api/v1/visitors`):**
  - Complete visitor registration workflow capturing visitor credentials, resident student link, purpose, and contact information.
  - Anti-abuse active visit limit: prevents duplicate active passes for the same visitor contact number.
  - Unique visitor pass generation (`VP-YYYYMM-XXXX`) with entry and expected departure window.
  - Gate check-in and check-out verification (`/api/v1/visitors/logs/{id}/check-in`, `check-out`) with real-time active visitor monitoring.
  - Overdue visit tracking flagging visitors remaining on campus beyond authorized visiting duration.
  - Role-based privacy protection: sensitive government ID proof numbers are dynamically masked (`XXXX-XXXX-1234`) for resident students and unauthorized viewers.
- [x] **Database Schema Migration 006 (`006_attendance_leave_visitor_enhancements`):**
  - Added `attendance_corrections` table with foreign key linkage and mandatory change reasoning.
  - Added `outpasses` table with unique constraint on `outpass_number` and foreign keys to `leave_requests` and verifying officers.
  - Optimized composite indexes: `idx_attendance_student_date`, `idx_attendance_date_status`, `idx_leave_student_status`, `idx_outpasses_status`, `idx_visitor_logs_status_active`.
- [x] **Alpine.js Reactive User Interface:**
  - Dedicated Attendance tab with daily summary metrics, room-by-room batch marking roster, and individual attendance records.
  - Dedicated Leave & Outpass tab with student submission modal, warden approval cards, and security guard barcode/outpass scanner interface.
  - Dedicated Visitor Pass tab with visitor registration modal, active visitor roster, overdue warnings, and one-click check-out action.
- [x] **Automated Testing Suite:**
  - 11 comprehensive unit and integration tests in `backend/tests/test_attendance_leave_visitors.py`.
  - Full suite now stands at **95 passing tests** across 8 test suites with 100% success rate.

---

## 🎯 Prompt 09 Q05 Cached Dashboard & Quick Navigation Deliverables Checklist

- [x] In-Memory Cache Service (`backend/app/services/cache_service.py`):
  - Thread-safe caching architecture utilizing `threading.RLock()`
  - Configurable TTL (60s default) with passive and active eviction
  - Telemetry tracking: cache hits, misses, hit ratio %, active entries, evictions
  - Deterministic partitioned cache keys (`dashboard:role:{role}:hostel:{hostel_id}:user:{user_id}`)
  - Multi-tenant facility isolation preventing data leakage between hostels
- [x] Automatic Dependency-Based Cache Invalidation (`backend/app/services/cache_invalidation.py`):
  - Invalidation triggers for: Student mutations, Room/Bed allocations, Check-in/Check-out, Transfers, Hostel infrastructure, Complaints, Maintenance, Payments/Finance, Admissions
  - Atomic post-commit execution: Cache is invalidated strictly *after* successful `conn.commit()`
  - Rollback resilience: Failed or aborted transactions do not corrupt or prematurely invalidate cache
- [x] Dashboard API Optimization (`GET /api/v1/metrics/dashboard`):
  - Role-specific and hostel-specific aggregate statistics
  - Sub-0.05ms warm response time ($< 50\text{ }\mu\text{s}$)
  - Cache telemetry endpoint `GET /api/v1/metrics/cache/stats`
  - Administrative flush endpoint `POST /api/v1/metrics/cache/clear`
  - Automatic cache pre-warming during application startup sequence
- [x] Quick Navigation & Frontend Performance:
  - Persistent Single Page Application (SPA) shell with Alpine.js reactive components
  - Zero full-page reloads with sub-0.1ms client-side view switching
  - State preservation across view switches (active role dashboard, search filters, pagination offsets)
  - Client-side in-flight request deduplication (`API.deduplicatedFetch`) preventing redundant queries
- [x] Performance Benchmarking (`scripts/benchmark_dashboard_cache.py`):
  - 100-iteration benchmark evaluating Cold Cache, Warm Cache, Invalidation Speed, and Multi-Tenant Isolation
  - Measured: Cold cache $0.049\text{ ms}$ (p50), Warm cache $0.001\text{ ms}$ (p50), Invalidation $0.019\text{ ms}$ (p50)
  - Measured Warm Hit Ratio: $98.8\%$
- [x] Documentation:
  - `docs/Q05_CACHED_DASHBOARD.md` (Cache engine architecture & invalidation matrix)
  - `docs/Q05_QUICK_NAVIGATION.md` (SPA navigation, state preservation, request deduplication)
  - Updated `docs/PERFORMANCE_BENCHMARKS.md` with measured numbers
- [x] Automated Testing:
  - 10 comprehensive tests in `backend/tests/test_cached_dashboard.py`
  - Total 74 automated tests passing across the entire project (100% success rate)

---

- [x] Unified Server-Side Fast Search Engine (`/api/v1/search`):
  - Multi-domain indexing: Students, Hostels, Rooms, Beds, Allocations, Complaints, Maintenance, Payments
  - Parameterized search execution eliminating SQL injection vulnerabilities
  - Case-insensitive searching across upper, lower, and mixed case tokens
  - Token prefix expansion (`Pri*`, `CSE*`, `H1*`)
  - Strict Role-Based Data Isolation (Students barred from payment and confidential records)
- [x] SQLite FTS5 Full-Text Virtual Indexing:
  - Table `search_index_fts` configured with `tokenize = 'porter unicode61'`
  - BM25 relevance ranking score returned with every matching entity
  - Real-time synchronization utility (`POST /api/v1/search/rebuild-index`) restricted to Super Admin and Auditors
- [x] Database Index Optimization (Migration `004_q05_search_and_indexes`):
  - `idx_students_name`: Composite B-Tree on `(first_name, last_name)`
  - `idx_rooms_number`: Single B-Tree on `(room_number)`
  - `idx_complaints_created_at`: Ordered B-Tree on `(created_at DESC)` avoiding temporary sort tables
  - `idx_complaints_status_date`: Composite B-Tree on `(status, created_at DESC)`
  - `idx_maintenance_status`: Single B-Tree on `(status)`
  - `idx_payments_ref_tx`: Composite B-Tree on `(payment_reference, transaction_id)`
  - `idx_allocations_status_date`: Composite B-Tree on `(allocation_status, start_date DESC)`
  - `idx_hostels_active_type`: Composite B-Tree on `(is_active, hostel_type)`
  - `idx_visitors_name_phone`: Composite B-Tree on `(name, phone)`
- [x] Query Plan Verification:
  - Validated via `EXPLAIN QUERY PLAN` confirming `SEARCH ... USING INDEX` across all target paths
- [x] Synthetic Performance Benchmarking Harness (`scripts/benchmark_search.py`):
  - Benchmarked across 1k, 10k, 50k, and 100k isolated record datasets
  - Proved FTS5 executes in $< 0.35\text{ ms}$ (p50) and $< 1.25\text{ ms}$ (p95) at 100,000 records
  - Proved unindexed table scans degrade to $> 23.7\text{ ms}$, failing Q05 SLA
- [x] Frontend Quick Search Modal (`Ctrl + K`):
  - 250ms debounced input
  - Category filter pills (*All Entities*, *Students*, *Hostels*, *Rooms*, *Allocations*, *Complaints*, *Payments*)
  - Live query latency badge (e.g., `⚡ 1.25 ms (<10ms SLA)`)
  - Loading spinner and highlighted query matches
  - Direct record navigation upon selection
- [x] Documentation:
  - `docs/Q05_FAST_SEARCH.md`: Comprehensive search architecture & security barriers
  - `docs/DATABASE_INDEXES.md`: Complete index catalog, write overhead, and query plans
  - `docs/PERFORMANCE_BENCHMARKS.md`: Empirical latency benchmarks across 4 dataset tiers
- [x] 64 automated unit, integration, and performance tests passing (100% success rate)

---

- [x] Complete Student Room and Bed Allocation Engine (`/api/v1/allocations`)
- [x] Strict 10-Layer Poka-Yoke Error Prevention System:
  1. *Rule 1:* Prevent allocating one bed to multiple active students (B-Tree Partial Unique Index `uq_active_bed_allocation`)
  2. *Rule 2:* Prevent allocating students to full rooms (Bound by capacity constraints 1-10)
  3. *Rule 3:* Prevent allocating students to inactive or maintenance beds
  4. *Rule 4:* Prevent allocating students to rooms under maintenance
  5. *Rule 5:* Prevent allocating students to inactive hostels or buildings
  6. *Rule 6:* Prevent allocating students to gender-restricted hostels (Boys vs Girls vs Co-Ed)
  7. *Rule 7:* Prevent creating duplicate active allocations for the same student (`uq_active_student_allocation`)
  8. *Rule 8:* Prevent transferring students to unavailable or occupied beds
  9. *Rule 9:* Prevent checking out students who have no active allocation and prevent duplicate checkouts
  10. *Rule 10:* Enforce backend RBAC authorization (Students cannot approve allotments or perform unauthorized transfers)
- [x] Multi-Criteria Intelligent Suggestion Engine (`/api/v1/allocations/suggestions`):
  - Student eligibility and gender compatibility
  - Student preferences (room type, floor)
  - Cohort and peer clustering (department/branch alignment, academic year alignment)
  - Space optimization (partially occupied room consolidation)
- [x] Complete Allocation Lifecycle Management:
  - Check-in (`/api/v1/allocations/{id}/checkin`)
  - Check-out with bed release and room status recalculation (`/api/v1/allocations/{id}/checkout`)
  - Atomic room and bed transfers with database transaction isolation (`/api/v1/allocations/{id}/transfer`, `/api/v1/transfers`)
- [x] Cryptographic Allocation Confirmation Slip with SHA-256 verification hash
- [x] Allocation Management Dashboard & Student Residence Profile Integration
- [x] Multi-Threaded Concurrency Test Suite proving race condition safety
- [x] 54 automated unit, integration, and Poka-Yoke tests passing (100% success rate)

---

## 🎯 Prompt 04 UI/UX & Dashboard Deliverables Checklist

- [x] Application Shell: Expandable/collapsible sidebar (72px vs 260px) with responsive mobile drawer overlay
- [x] Top Navigation Bar: Breadcrumbs, search bar with `Ctrl + K` modal, live latency telemetry pill, light/dark mode toggle, notifications bell with drawer, and user profile menu
- [x] Reusable UI Components Library (`frontend/js/components.js`):
  - Dashboard statistic cards with icons and trend metrics
  - Data table component with column sorting, status badges, and hover elevation
  - Search bar and status filter dropdowns
  - Reusable pagination controls with page bounds calculation
  - Reusable confirmation dialog & action modal
  - Global floating toast notification system (`success`, `error`, `warning`, `info`)
  - Accessible empty states with illustrations and guidance text
  - Lightweight SVG sparklines and mini bar charts rendered sub-0.1ms
- [x] Full Light and Dark Themes powered by Tailwind CSS `darkMode: 'class'` with persistent local storage
- [x] Tailored Dashboard Experiences for All 12 Roles:
  1. `super_admin`: Total hostels, total students, total users, overall occupancy, system activity feed, user directory
  2. `hostel_admin`: Hostel occupancy, room availability, student stats, pending complaints count, floor-by-floor breakdown
  3. `warden`: Student attendance check, pending leave approvals, complaints card, notices broadcasting
  4. `assistant_warden`: Daily operational rounds checklist, attendance log verification, gate entry checks
  5. `student`: Personal profile, room and bed allocation, fee clearance status, attendance rate, leave requests, isolation barrier test
  6. `accountant`: Total invoiced, total collected, outstanding dues, fee receipts review, zero pending anomalies
  7. `mess_manager`: Today's 4-Meal dining schedule (Breakfast, Lunch, Snacks, Dinner), subscriptions count, dietary inventory alert
  8. `maintenance_staff`: Assigned task count, pending repairs, weekly completed work orders, facility repair queue
  9. `security_guard`: Campus visitors count, gate entry/exit log, outpass barcode/enrollment verification scanner
  10. `admission_officer`: Application review pipeline (Submitted, Approved, Verified), candidate intake statistics
  11. `parent_guardian`: Linked ward oversight (Rohan Bakshi), attendance percentage, fee clearance receipt, leave history
  12. `auditor`: TQM audit log trail, financial consistency review, Q05 Response Time SLA performance telemetry
- [x] Backend Aggregation API: Implemented `GET /api/v1/dashboard/stats` querying live SQLite tables
- [x] 38 automated unit, integration, and API tests passing (100% success rate)


---

## 🎯 Prompt 12 Fee & Financial Management Deliverables Checklist

- [x] **Fee Structure Management (`backend/app/services/fee_service.py` & `/api/v1/fees/structures`):**
  - Full CRUD operations with institutional categories (Hostel Accommodation, Room, Mess, Security Deposit, Electricity, Maintenance, Admission, Late Fine, Other).
  - Validation: Prevents duplicate configuration by (name, academic_year, hostel_id, room_type, semester).
  - Soft-deactivation preservation: Fee structures with historical invoice references are deactivated rather than deleted to ensure financial immutability.
- [x] **Student Invoicing Engine (`FeeService` & `/api/v1/fees/invoices`):**
  - Individual invoice generation with unique format `INV-YYYYMM-XXXX`.
  - Net payable and balance tracking: `net_payable = round(total_amount + fine_amount - discount_amount, 2)` and `outstanding_balance = max(0.0, round(net_payable - paid_amount, 2))`.
  - Bulk invoice generation across eligible hostel residents with automated duplicate invoice skipping.
  - Concession/discount approvals with balance recalculation, audited rationale, and excess discount prevention.
  - Audited invoice cancellation: unpaid invoices cancelled with mandatory justification; invoices with recorded payments blocked from cancellation.
  - Official cryptographic downloadable demand notices/invoices (`/api/v1/fees/invoices/{id}/receipt`).
- [x] **Payment Processing & Audited Reversals (`PaymentService` & `/api/v1/fees/payments`):**
  - Full and partial payment recording with auto status transitions (`Issued` -> `Partially_Paid` -> `Paid`).
  - Unique transaction references `PAY-YYYYMM-XXXX` and digital receipts `RCP-YYYYMM-XXXX`.
  - Poka-Yoke duplicate transaction reference and duplicate transaction ID prevention.
  - Audited payment reversals restoring invoice outstanding balance with audit log trail.
  - Downloadable official payment receipts.
- [x] **Refund Management (`PaymentService` & `/api/v1/fees/refunds`):**
  - Four-stage lifecycle (`Requested` -> `Under_Review` -> `Approved` / `Rejected` -> `Processed`).
  - Validation: Refund requests strictly capped to payment amount minus previous non-rejected refunds.
  - Review workflows: Approval, rejection with mandatory reason, processing with transaction references.
- [x] **Financial Dashboard & Reporting (`FinancialReportService` & `/api/v1/fees/reports`):**
  - High-speed executive dashboard: Total invoiced, total collected, outstanding dues, overdue total, collection rate %, monthly collections, payment methods breakdown.
  - Sub-10ms Q05 cached aggregates with tag-based invalidation (`finance`).
  - Collections Report with date range, hostel, and payment method filters.
  - Dues Report with student contact details, room info, and min-amount filters.
  - Overdue Report with 4 aging brackets (1-30d, 31-60d, 61-90d, 90+d).
  - Streaming RFC 4180 CSV export generator for collections, dues, overdue, and refunds.
- [x] **Alpine.js Reactive User Interface:**
  - 5 subtabs: Invoices & Dues, Payments, Refunds, Fee Structures, Reports & Analytics.
  - Interactive modals: New Fee Structure, Single Invoice, Bulk Invoicing, Record Payment, Reverse Payment, Request Refund, Concession Discount, Cancel Invoice, Official Receipts.
  - Executive KPI summary cards with one-click Q05 CSV download.
- [x] **Database Schema Migration 007 (`007_fee_and_financial_enhancements`):**
  - Non-destructive schema enhancement for `fee_structures`, `invoices`, `payments`, `refunds`.
  - 13 composite B-Tree indexes for sub-10ms queries.
- [x] **Automated Testing Suite:**
  - 10 comprehensive unit and integration tests in `backend/tests/test_fee_and_finance.py`.
  - Total 105 tests passing across entire application test suite (100% success rate).

---

## 🎯 Prompt 13 Mess & Inventory Management Deliverables Checklist

- [x] **Mess Menu Management (`backend/app/services/mess_service.py` & `/api/v1/mess/menus`):**
  - Daily and weekly menu creation with multi-item scheduling across 4 meal categories: Breakfast, Lunch, Evening Snacks, Dinner.
  - Meal timings configuration, nutritional/dietary notes, and menu descriptions.
  - Menu lifecycle: Draft, Published, and Cancelled with mandatory audit rationale.
  - Poka-Yoke duplicate menu prevention enforcing `UNIQUE(hostel_id, date, meal_type)`.
  - Authorized role enforcement: Mess Manager, Super Admin, Hostel Admin, Warden.
- [x] **Mess Dietary Subscriptions (`MessService` & `/api/v1/mess/subscriptions`):**
  - Multiple subscription plans: Monthly, Semester, Custom date-range.
  - Plan types: Standard, Vegetarian, Non-Vegetarian, Special Dietary.
  - Subscriptions tracking with unique code `SUB-YYYYMM-XXXX`.
  - Poka-Yoke active overlap prevention: Blocks overlapping active subscriptions for the same student.
  - Student data isolation barrier: Students view and cancel only their own subscriptions.
- [x] **Meal Attendance Verification (`MessService` & `/api/v1/mess/attendance`):**
  - Rapid meal attendance logging with active subscription verification.
  - Dual verification workflows: Manual attendance desk and fast QR barcode token scan (`/api/v1/mess/attendance/verify-qr`).
  - Poka-Yoke double-punching prevention: Disallows duplicate attendance for the same student, date, and meal session.
  - Attendance corrections with auditable reason and audit trail logging.
- [x] **Inventory & Stock Management (`backend/app/services/inventory_service.py` & `/api/v1/inventory`):**
  - Multi-category inventory catalog: Provisions, Vegetables & Fruits, Dairy, Cleaning & Housekeeping, Electrical, Plumbing, Linen & Bedding, Office Supplies.
  - Item catalog tracking unit, stock on hand, min reorder level, max threshold, unit price, valuation, storage location, and expiry dates.
  - Real-time low-stock alerts (`stock <= min_reorder_level`) and upcoming expiry alerts (`expiry_date <= 30 days`).
  - Stock Inward (Receipt): Inward transaction with supplier, invoice reference, unit price, total value, and atomic stock increment.
  - Stock Outward (Issue): Outward transaction with department destination, purpose, and atomic stock decrement.
  - **Poka-Yoke Zero-Negative Inventory:** Rejects outward issues exceeding available on-hand stock with HTTP 400 Bad Request.
  - Stock Adjustments: Audited adjustments (Damaged, Expired, Wastage, Discrepancy) with approval workflow (`Pending_Approval` -> `Approved` / `Rejected`).
  - Stock Transfers: Multi-hostel inventory rebalancing with source and target location tracking.
- [x] **Supplier Directory (`InventoryService` & `/api/v1/inventory/suppliers`):**
  - Full CRUD operations with supplier contact person, phone, email, address, goods category, and active status.
- [x] **Mess & Inventory Reporting & RFC 4180 Streaming CSV Export (`MessInventoryReportService`):**
  - Meal consumption report with hostel, date range, and meal type breakdown.
  - Inventory stock summary valuation report with low-stock and expiry filtering.
  - Stock movement report with inward/outward/adjustment transaction tracking.
  - Streaming RFC 4180 compliant CSV export generator with high-efficiency memory streaming.
- [x] **Database Schema Migration 008 (`008_mess_and_inventory_enhancements`):**
  - Non-destructive enhancement of `mess_menus`, `mess_subscriptions`, `meal_attendance`, `inventory_items`, `inventory_transactions`, `suppliers`.
  - 15 composite B-Tree indexes for sub-10ms Q05 SLA query execution.
- [x] **Interactive Frontend Navigation & Modals:**
  - Mess & Dining module with 4 subtabs: Daily Menus, Subscriptions, Meal Attendance, Analytics & Reports.
  - Inventory module with 4 subtabs: Item Catalog, Stock Movements, Stock Adjustments, Suppliers.
  - QR Code scanner simulation and manual punch desk.
- [x] **Automated Testing Suite (`backend/tests/test_mess_and_inventory.py`):**
  - 13 comprehensive unit and integration tests covering menus, subscriptions, attendance, Poka-Yoke stock constraints, adjustments, and CSV exports.
  - Total 118 automated tests passing across entire application test suite (100% success rate).
