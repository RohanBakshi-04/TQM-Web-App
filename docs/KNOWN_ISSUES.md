# Hostel Management System (HMS) - Known Issues, Limitations & Defect Log

**Course:** BBAT104 - Fundamentals of Total Quality Management (TQM)  
**Quality Goal:** Q05 - Zero Defects, Transparent Auditing, and Systematic Reliability  
**Evaluation Date:** November 2, 2026  
**Status:** **All Verified Source Code Defects Resolved; Operational Constraints Documented**

---

## 1. Resolved Source Code Defects

During Phase 2 acceptance testing, the following defects were systematically identified, logged, and permanently repaired:

| Defect ID | Severity | Category | Description | Root Cause | Resolution | Status |
|---|---|---|---|---|---|:---:|
| **DEF-01** | **Critical** | Security (IDOR) | Endpoint `GET /api/v1/fees/invoices/student/{student_id}` allowed students to inspect another student's billing records. | Missing student isolation verification dependency call in router. | Imported and invoked `verify_student_isolation(student_id, current_user)` in `backend/app/routers/fees.py`. | **FIXED / VERIFIED** |
| **DEF-02** | **Critical** | Security (IDOR) | Endpoint `GET /api/v1/fees/payments/student/{student_id}` allowed students to inspect payment transactions of other residents. | Missing `verify_student_isolation` check in `backend/app/routers/fees.py`. | Added `verify_student_isolation(student_id, current_user)` check before querying ledger. | **FIXED / VERIFIED** |
| **DEF-03** | **Critical** | Security (IDOR) | Endpoint `GET /api/v1/attendance/student/{student_id}` allowed unlinked parents and students to view foreign attendance logs. | Missing `verify_student_isolation` check in `backend/app/routers/attendance.py`. | Added `verify_student_isolation(student_id, current_user)` to enforce strict ward/resident boundary. | **FIXED / VERIFIED** |
| **DEF-04** | **Medium** | Database Integrity | SQLite `PRAGMA foreign_key_check` reported 81 violations on `data/hostel_web.db`. | Past manual test deletions executed while foreign keys were turned off left dangling IDs in child tables. | Introduced Migration `015_enforce_referential_integrity_and_clean_orphans`. Cleaned dangling rows. FK violations reduced to 0. | **FIXED / VERIFIED** |
| **DEF-05** | **Low** | Data Model | Fee structure creation failed when `payment_frequency` was provided as `"Per Semester"`. | SQLite CHECK constraint strictly requires `'Semester'`, `'Monthly'`, `'Quarterly'`, `'Annual'`, or `'One_Time'`. | Standardized payload and client validation to use canonical enum values. | **FIXED / VERIFIED** |

---

## 2. Operational Environment Limitations

### Limitation 1: Docker Runtime Environment (NOT TESTED)
- **Status:** **NOT TESTED**
- **Reason:** Docker engine / Docker Desktop daemon is not installed or running on the Windows evaluation host (`docker: command not found` / named pipe unavailable).
- **Impact:** Live Docker container startup (`docker compose up`) could not be executed directly in this environment.
- **Mitigation & Verification:** 
  - `docker-compose.yml` was audited to ensure zero hardcoded secrets and mandatory environment variable interpolation (`${SECRET_KEY:?error}`, `${JWT_SECRET_KEY:?error}`).
  - `backend/app/config.py` was verified to reject default insecure keys in production mode.
  - Step-by-step instructions for container deployment are provided in `docs/TEST_ENVIRONMENT_SETUP.md` and `docs/DEPLOYMENT_GUIDE.md`.

### Limitation 2: OneDrive File System Synchronization
- **Description:** SQLite WAL (`Write-Ahead Logging`) mode relies on shared memory files (`.db-shm` and `.db-wal`). When running inside cloud-synced folders (such as Microsoft OneDrive), cloud sync daemons can momentarily lock the database file during high concurrency.
- **Recommendation:** In staging and production environments, configure `DATABASE_PATH` to point to a local non-synchronized directory (e.g., `/var/lib/hms/` or `C:\ProgramData\HMS\data\`).

### Limitation 3: TestClient Cookie Deprecation Warning (Benign)
- **Description:** Starlette's `TestClient` emits a `DeprecationWarning: Setting per-request cookies=<...> is being deprecated...`.
- **Impact:** None. This is a framework-level warning from Starlette/HTTPX when passing cookies explicitly in unit tests and does not affect runtime application behavior or browser cookie handling.
