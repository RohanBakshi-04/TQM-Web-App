# Hostel Management System (HMS) — Web Application

**Course:** BBAT104 – Fundamentals of Total Quality Management (TQM)  
**Academic Session:** 2026–27  
**Student Name:** Rohan Bakshi  
**Roll Number:** 2410301057  
**Branch & Section:** B.Tech Computer Science & Engineering (Section A)  
**Assigned Baseline System:** Hostel Management System (Topic Digit: 7)  
**Assigned Quality Goal:** **Q05 – REDUCE RESPONSE TIME (< 10.0 ms SLA)**  
**Remote Git Repository:** [https://github.com/RohanBakshi-04/TQM-Web-App](https://github.com/RohanBakshi-04/TQM-Web-App)

---

## 🎯 Project Overview

This project develops an enterprise-grade, high-performance web application for institutional hostel administration, built under strict Total Quality Management (TQM) principles. Targeting **Quality Goal Q05 (Reduce Response Time)**, the system achieves sub-millisecond query execution, client-side reactivity, and mistake-proofing (**Poka-Yoke**) across 21 functional domains and 15 distinct stakeholder roles (10 Core Administrative & Operational + 5 Functional):

1. **Super Administrator** (`superadmin`) — Institutional configuration, user security, custom role management, audit logs, and online backups
2. **Hostel Administrator / Director** (`hosteladmin`) — Hostels, buildings, floors, rooms, allocation policy, and capacity planning
3. **Chief Warden** (`warden`) — Primary facility head, resident student welfare, room allocation approvals, and leave approvals
4. **Assistant Warden** (`asstwarden`) — Delegated floor roll-calls, curfew monitoring, and student welfare logistics
5. **Hostel Clerk** (`clerk`) — Front-office student intake, certificate requests, document verification, and physical registers
6. **Financial Accountant** (`accountant`) — Fee structures, invoices, payment verification, caution deposit refunds, and financial ledgers
7. **Admission Officer** (`admission`) — Student onboarding, quota management, document validation, and room eligibility
8. **Security Supervisor** (`secsupervisor`) — Perimeter safety, guard shift rosters, incident escalation, and gate audit telemetry
9. **Security Guard** (`security`) — Visitor pass issuance, student outpass check-in/out, and curfew enforcement
10. **IT Administrator** (`itadmin`) — Infrastructure health, backup automation, worker leases, and audit telemetry (air-gapped from student private records)
11. **Resident Student** (`rohan`) — Room details, leave requests, grievance submission, mess subscriptions, and fee payments
12. **Parent / Guardian** (`parent`) — Multi-ward oversight, attendance monitoring, fee ledgers, and leave tracking
13. **Mess Manager** (`messmanager`) — Weekly dining schedules, dietary options, meal feedback, and grocery inventory
14. **Maintenance Staff** (`maintenance`) — Repair work orders, spare parts utilization, and status updates
15. **TQM Faculty Auditor** (`evaluator`) — Quality metrics audit, Q05 telemetry, and SLA verification

---

## ⚡ Q05 Performance Benchmark Results (Verified SLA < 10.0 ms)

All operations achieve an empirical P95 latency below 0.5 milliseconds:

| Operation / Benchmark Category | Mean Latency | Median Latency | P95 Latency | P99 Latency | SLA Target | Status |
| :--- | :---: | :---: | :---: | :---: | :---: | :---: |
| **FTS5 Global Full-Text Search** | **0.190 ms** | 0.188 ms | **0.369 ms** | 0.464 ms | < 10.0 ms | **PASSED** |
| **Entity Indexed SQL Search** | **0.009 ms** | 0.007 ms | **0.015 ms** | 0.051 ms | < 10.0 ms | **PASSED** |
| **Dashboard Cold SQL Aggregation** | **0.102 ms** | 0.068 ms | **0.266 ms** | 0.516 ms | < 10.0 ms | **PASSED** |
| **Dashboard Warm In-Memory Cache** | **0.001 ms** | 0.001 ms | **0.002 ms** | 0.006 ms | < 0.05 ms | **PASSED** |
| **Tag-Based Cache Invalidation** | **0.025 ms** | 0.022 ms | **0.031 ms** | 0.168 ms | < 10.0 ms | **PASSED** |
| **Domain Operations (Fees, Attendance)**| **0.013 ms**| 0.005 ms | **0.037 ms** | 0.093 ms | < 10.0 ms | **PASSED** |
| **Volume Scalability (100k Rows)** | **0.002 ms** | 0.002 ms | **0.003 ms** | 0.005 ms | < 10.0 ms | **PASSED** |

---

## 🏗️ Architecture & Technology Stack

- **Backend:** Python 3.10+ / FastAPI (Asynchronous REST API Engine)
- **Application Server:** Uvicorn ASGI Server
- **Database Engine & Migration Lifecycle:** SQLite 3 with Write-Ahead Logging (`WAL` mode), Foreign Key enforcement, 102 B-Tree composite indexes, and FTS5 full-text indexing across **66 database tables** (59 domain relational tables + 6 FTS5 search index tables + sqlite_sequence). Schema versioning managed through 19 atomic migrations (latest: `019_notification_deliveries_and_leases`).
- **Financial Architecture:** Authoritative integer-paise storage (`amount_paise`, `total_amount_paise`, `paid_amount_paise`) eliminating floating-point rounding errors across invoices, itemizations, and payments.
- **Authentication & Security:** Strict HttpOnly cookie-based refresh token rotation, in-memory access token management, zero refresh-token leakage in JSON responses, and unapproved student registration isolation.
- **Caching Layer:** Centralized in-memory thread-safe LRU cache with multi-tag invalidation and sub-millisecond response guarantees.
- **Frontend Architecture:** Alpine.js reactive state controller + Tailwind CSS + Lucide icons (No Node.js compilation required).
- **Containerization:** Multi-stage Docker build running as non-root `appuser` (UID 10001) with Docker Compose orchestration.
- **Poka-Yoke Defect Proofing:** Database unique partial indexes, atomic transfer transactions, event deduplication keys, and negative balance barriers.

---

## 🚀 Quick Start Guide

### Local Execution (Python Virtualenv)
```bash
# 1. Clone repository
git clone https://github.com/RohanBakshi-04/TQM-Web-App.git
cd "TQM-Web-App/Hostel Management System Web App"

# 2. Setup virtual environment
python -m venv venv
.\venv\Scripts\Activate.ps1    # On Windows
source venv/bin/activate       # On Linux/macOS

# 3. Install dependencies
pip install -r requirements.txt

# 4. Copy environment configuration
cp .env.example .env

# 5. Launch application
python run.py
```
The application will automatically initialize the database, execute all schema migrations, seed demo accounts (in development mode), and serve at `http://127.0.0.1:8000`.

### Containerized Execution (Docker Compose)

Docker Compose requires strong, non-default cryptographic secret keys supplied via a local `.env` file or environment variables.

1. **Configure Environment:**
   ```bash
   cp .env.example .env
   ```
2. **Generate Cryptographic Production Secrets (>= 32 characters):**
   ```bash
   python -c "import secrets; print(secrets.token_hex(32))"
   ```
   Paste the generated 64-character hex strings into `SECRET_KEY` and `JWT_SECRET_KEY` inside `.env`.
3. **Launch Container Service:**
   ```bash
   docker compose up -d --build
   ```
> [!NOTE]
> `docker-compose.yml` uses mandatory variable interpolation (`${SECRET_KEY:?SECRET_KEY must be set in .env}`). If production keys are missing or left as default placeholders, startup validation strictly prevents deployment.

Access the application at `http://localhost:8000`.

---

## 🧪 Automated Testing & Verification

Run the complete test suite (288 automated unit and integration tests across 20 test suites):
```bash
python -m unittest discover -s backend/tests -p "test_*.py"
```
**Result:** `Ran 288 tests in ~136s — OK (100% Pass Rate, 0 Failures, 0 Errors, 0 Skips)`.

Run the Playwright browser acceptance test suite:
```bash
python -m unittest backend/tests/test_browser_acceptance.py
```
**Result:** `Ran 5 tests in ~50s — OK (100% Pass Rate, 0 Failures, 0 Errors)`.

Run the Q05 performance benchmark suite:
```bash
python scripts/benchmark_q05.py
```

---

## 📚 Technical Documentation Directory

- [Final Remediation & Release Report](docs/FINAL_REMEDIATION_REPORT.md) — Comprehensive evidence report covering all 7 defect groups, 301 passing tests, and release sign-off
- [Remediation Status Log](REMEDIATION_STATUS.md) — Master defect tracking and remediation log across all subsystems
- [Role & Permission Matrix](docs/ROLE_PERMISSION_MATRIX.md) — 15-role enterprise RBAC enforcement, canonical codes, data scoping, and role switching safeguards
- [Registration & Onboarding Workflows](docs/REGISTRATION_WORKFLOWS.md) — Student, Faculty/Staff, and Parent onboarding chains and dual approval
- [Acceptance Test Report](docs/ACCEPTANCE_TEST_REPORT.md) — 301/301 automated tests passing with zero defects (296 backend + 5 browser)
- [Installation Guide](docs/INSTALLATION_GUIDE.md) — Comprehensive local and production setup instructions
- [User Manual](docs/USER_MANUAL.md) — Operational walkthrough for all 15 stakeholder roles
- [REST API Documentation](docs/API_DOCUMENTATION.md) — Endpoint specifications for all 21 modules
- [Production Deployment Guide](docs/DEPLOYMENT_GUIDE.md) — Nginx reverse proxy, SSL, systemd, and backup policies
- [TQM Final Project Report](docs/TQM_FINAL_PROJECT_REPORT.md) — Academic report on TQM methodology, Q05 SLA, and Poka-Yoke
- [Database Schema Specification](docs/DATABASE_SCHEMA.md) — 63 database tables (56 domain tables + 6 FTS5 search index tables + sqlite_sequence)
- [Database Indexes Catalog](docs/DATABASE_INDEXES.md) — 48 B-Tree composite indexes and query execution plans
- [Entity-Relationship Diagram](docs/ER_DIAGRAM.md) — Mermaid visual schema relationships
- [Q05 Caching & Quick Navigation](docs/Q05_CACHED_DASHBOARD.md) — Cache invalidation and multi-tenant isolation
- [Testing Report](TESTING_REPORT.md) — Comprehensive test execution logs and verification evidence
- [Changelog](CHANGELOG.md) — Chronological history across all development prompts
- [Project Progress](PROJECT_PROGRESS.md) — Requirement mapping and implementation checklist

---

## 🔐 Default Demo Credentials

> [!WARNING]
> **DEVELOPMENT & TESTING ONLY:** The credentials listed below are provisioned strictly for local developer evaluation and automated testing when `APP_ENV=development` and `ENABLE_DEMO_SEEDING=True`.
> In production environments (`APP_ENV=production`), demo account seeding is automatically disabled, and default placeholders are rejected at boot time. Never use these credentials in a public or production environment.

Universal demo account password: `Password123!`

- Super Admin: `superadmin`
- Hostel Director / Admin: `hosteladmin`
- Chief Warden: `warden`
- Assistant Warden: `asstwarden`
- Hostel Clerk: `clerk`
- Financial Accountant: `accountant`
- Admission Officer: `admission`
- Security Supervisor: `secsupervisor`
- Campus Security Guard: `security`
- IT Administrator: `itadmin`
- Resident Student: `rohan`
- Parent / Guardian: `parent`
- Mess Manager: `messmanager`
- Maintenance Staff: `maintenance`
- TQM Auditor: `evaluator`
