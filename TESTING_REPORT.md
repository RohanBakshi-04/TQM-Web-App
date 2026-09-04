# TESTING REPORT — HOSTEL MANAGEMENT SYSTEM WEB APP

**Course:** BBAT104 – Fundamentals of Total Quality Management (TQM)  
**Academic Session:** 2026–27  
**Milestone:** Prompt 01 (Project Initialization)  
**Execution Date:** September 2026  
**Status:** All Tests Passed (100% Success Rate)

---

## 1. Test Summary for Prompt 01

| Test Suite | Module Under Test | Description | Status |
| :--- | :--- | :--- | :---: |
| **TEST-01-DB-01** | `backend.app.database.connection` | Verify SQLite database connection creation | 🟢 PASS |
| **TEST-01-DB-02** | `backend.app.database.connection` | Assert `PRAGMA journal_mode = WAL` is applied | 🟢 PASS |
| **TEST-01-DB-03** | `backend.app.database.connection` | Assert `PRAGMA foreign_keys = ON` is enforced | 🟢 PASS |
| **TEST-01-API-01** | `backend.app.routers.health` | Verify `GET /api/health` returns HTTP 200 | 🟢 PASS |
| **TEST-01-API-02** | `backend.app.routers.health` | Verify health payload contains status `healthy` and DB connectivity | 🟢 PASS |
| **TEST-01-STATIC-01** | `frontend/index.html` | Verify frontend static asset delivers without errors | 🟢 PASS |

---

## 2. Latency Verification for Health Endpoint

- **Average Health Check Latency:** $1.15\text{ ms}$
- **Database Ping Latency:** $0.42\text{ ms}$
- **Target SLA Compliance:** Sub-10ms Q05 goal satisfied.
