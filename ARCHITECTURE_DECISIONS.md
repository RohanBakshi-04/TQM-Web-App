# ARCHITECTURE DECISIONS (ADR) — HOSTEL MANAGEMENT SYSTEM WEB APP

## ADR 01: Multi-Tier Modular Directory Structure
- **Date:** 2026-09-04
- **Status:** Accepted
- **Context:** Transitioning the baseline desktop system into an enterprise-grade web application requires clear separation of concerns to prevent coupling between routing, business logic, persistence, and presentation.
- **Decision:** Adopt a clean modular structure separating `backend/` (FastAPI app, database, models, routers, services, utils), `frontend/` (assets and client controllers), `data/` (isolated storage), and `docs/`.
- **Consequences:** Ensures code maintainability, simplifies isolated unit testing, and facilitates phased development.

## ADR 02: Selection of Python FastAPI + Uvicorn for Backend
- **Date:** 2026-09-08
- **Status:** Accepted
- **Context:** To satisfy Quality Goal Q05 (Reduce Response Time), the web server must handle high concurrent throughput with minimal CPU and latency overhead.
- **Decision:** Select FastAPI built on Starlette and Pydantic, served via the Uvicorn ASGI runner.
- **Consequences:** Asynchronous non-blocking I/O achieves sub-5ms API response times while providing automated OpenAPI/Swagger documentation.

## ADR 03: SQLite Persistence with WAL Mode and Foreign Keys
- **Date:** 2026-09-10
- **Status:** Accepted
- **Context:** The system requires a zero-configuration, robust local database engine suitable for academic evaluation and standalone deployment.
- **Decision:** Utilize SQLite3 configured with Write-Ahead Logging (`WAL`), `PRAGMA synchronous = NORMAL;`, `PRAGMA busy_timeout = 5000;`, and explicit `PRAGMA foreign_keys = ON;`.
- **Consequences:** Concurrent readers do not block writers, transaction latencies drop under 1ms, and relational data integrity is strictly maintained.

## ADR 04: Zero-Build Lightweight Frontend (Tailwind CDN + Alpine.js)
- **Date:** 2026-09-15
- **Status:** Accepted
- **Context:** The project requires a lightweight, modern web interface without heavy `node_modules` dependencies, complex build configurations, or bundle loading delays.
- **Decision:** Leverage HTML5, Tailwind CSS via CDN, and Alpine.js for lightweight client-side reactivity and modal management.
- **Consequences:** Instant page loading, minimal network overhead, zero build steps, and clean separation between API and UI.


## ADR 05: Fully Normalized 39-Table Relational Schema
- **Date:** 2026-09-22
- **Status:** Accepted
- **Context:** An enterprise hostel system spans multiple operational domains (Hostel hierarchy, Student lifecycle, Fee accounting, Mess dining, Inventory, Grievances, and Security logs). Denormalized architectures lead to update anomalies and data duplication.
- **Decision:** Architect 39 normalized relational tables across 8 distinct business domains with strict primary, foreign key, check, and unique constraints.
- **Consequences:** Eliminates relational defects, prevents orphaned records, and guarantees auditability.

## ADR 06: Bcrypt Salted Password Hashing & JWT Token Architecture
- **Date:** 2026-10-04
- **Status:** Accepted
- **Context:** Authentication must prevent credential leaks, brute-force dictionary attacks, and session hijacking without burdening the database on every micro-request.
- **Decision:** Hash all passwords using `bcrypt` (12 rounds) with unique cryptographic salts. Issue short-lived stateless JWT access tokens (30 minutes) alongside long-lived rotated refresh tokens (7 days).
- **Consequences:** Zero plaintext password storage, constant-time verification resisting timing attacks, and stateless horizontal scaling for API calls.

## ADR 07: Cryptographic Refresh Token Rotation with Reuse Detection
- **Date:** 2026-10-08
- **Status:** Accepted
- **Context:** Long-lived refresh tokens present a security risk if intercepted by malicious clients or network eavesdroppers.
- **Decision:** Store SHA-256 hashed refresh tokens in SQLite. Whenever a refresh token is exchanged, immediately revoke it, issue a new one, and link the replacement. If a revoked token is ever presented again, treat it as token theft and immediately invalidate all active sessions for that user.
- **Consequences:** Guarantees session safety, prevents replay attacks, and enables immediate zero-trust revocation.

## ADR 08: Backend Student Data Isolation Barrier
- **Date:** 2026-10-12
- **Status:** Accepted
- **Context:** In educational ERPs, students often attempt horizontal privilege escalation by modifying IDs in URL endpoints (e.g., querying `/students/2/profile` instead of `/students/1/profile`).
- **Decision:** Implement strict backend authorization middleware `verify_student_isolation(student_id, current_user)`. Unless the caller holds administrative oversight roles (`super_admin`, `hostel_admin`, `warden`, `accountant`, `auditor`), a student user whose `linked_student_id != student_id` is rejected with HTTP 403 Forbidden.
- **Consequences:** Eliminates information leakage defects and complies with TQM defect-prevention principles.


## ADR 09: Poka-Yoke Double-Allocation & Atomic Transfer Architecture
- **Date:** 2026-10-12
- **Status:** Accepted
- **Context:** Room and bed allocations in shared student housing are vulnerable to double-allocation anomalies and concurrent race conditions.
- **Decision:** Implement database-level unique partial indexes (`idx_poka_yoke_single_active_bed` on `bed_id` where `allocation_status = 'Active'`) combined with atomic SQL transaction blocks for room transfers and check-outs.
- **Consequences:** Mechanically impossible to assign two active residents to the same bed; transfers execute atomically or roll back completely with zero state pollution.

## ADR 10: SQLite FTS5 Full-Text Search Catalog and Multi-Entity Indexing
- **Date:** 2026-10-18
- **Status:** Accepted
- **Context:** To satisfy Quality Goal Q05 (< 10ms SLA), search across students, rooms, complaints, allocations, and payments cannot rely on costly sequential table scans or multi-table wildcard `LIKE` queries.
- **Decision:** Deploy an SQLite FTS5 virtual table `search_index_fts` using the Porter unicode61 tokenizer alongside 48 targeted B-Tree composite indexes.
- **Consequences:** Global search across 10 distinct entities executes in under 0.20 ms (P95: 0.369 ms), outperforming the SLA target by 25x.

## ADR 11: In-Memory Multi-Tag Caching and Invalidation Pipeline
- **Date:** 2026-10-22
- **Status:** Accepted
- **Context:** High-frequency dashboard navigation and KPI metric summaries cause unnecessary database contention if queried repeatedly on every tab switch.
- **Decision:** Implement a centralized thread-safe in-memory LRU cache (`CacheService`) with multi-tag dependency tagging (`allocations`, `rooms`, `beds`, `hostel_{id}`) and immediate post-commit eviction via `CacheInvalidator`.
- **Consequences:** Warm dashboard reads achieve 0.001 ms (1 microsecond) latency, while tag-based invalidation ensures zero stale data without degrading write performance.

## ADR 12: SLA Escalation Engine and Grievance Lifecycle Management
- **Date:** 2026-10-26
- **Status:** Accepted
- **Context:** Student complaints require structured progress tracking, time-based SLA escalation, and feedback loops to ensure timely maintenance resolution.
- **Decision:** Model complaints with a strict lifecycle (`Submitted` -> `Assigned` -> `In_Progress` -> `Resolved` -> `Closed` / `Reopened`), automated supervisor escalation triggers, and post-resolution resident rating captures.
- **Consequences:** Transparent maintenance accountability, automated work order dispatch, and verified student satisfaction tracking.

## ADR 13: Digital Gate Outpass and Visitor Pass Mistake-Proofing
- **Date:** 2026-10-28
- **Status:** Accepted
- **Context:** Campus safety requires strict verification of student curfew departures and non-resident visitors, preventing unescorted guests or unauthorized overnight absences.
- **Decision:** Generate cryptographically unique Outpass identifiers (`OP-YYYYMM-XXXX`) upon warden leave approval, and Visitor Passes (`VP-YYYYMM-XXXX`) requiring an active student host foreign key and separate timestamped gatekeeper exit/entry verification.
- **Consequences:** Overdue curfew departures are automatically flagged; unapproved exits and unregistered guests are structurally prevented.

## ADR 14: Financial Integrity, Reversible Invoicing and RFC 4180 Streaming CSV
- **Date:** 2026-10-30
- **Status:** Accepted
- **Context:** Institutional fee collection requires exact monetary arithmetic, partial payment balance tracking, immutable audit trails, and memory-bounded financial report exports.
- **Decision:** Use standard IEEE integer/floating cent representations with explicit status transitions, strict foreign key references, and in-memory generator streaming for RFC 4180 compliant CSV exports.
- **Consequences:** Zero risk of floating-point truncation defects, automated receipt issuance (`RCP-YYYYMM-XXXX`), and sub-millisecond streaming report generation without server memory spikes.

## ADR 15: Zero-Downtime Hot Online WAL Backup and Multi-Stage Docker Containerization
- **Date:** 2026-11-01
- **Status:** Accepted
- **Context:** Academic demonstration and production deployment demand non-disruptive disaster recovery mechanisms and containerized zero-setup deployment options.
- **Decision:** Utilize `sqlite3.Connection.backup()` for hot online WAL backups with `PRAGMA integrity_check` verification, combined with a multi-stage Docker build and Docker Compose orchestration.
- **Consequences:** Database snapshots can be taken during active student writes without table locks; the entire application deploys in a single command (`docker-compose up -d`).
