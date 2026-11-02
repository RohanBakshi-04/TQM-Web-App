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

This project develops an enterprise-grade, high-performance web application for institutional hostel administration, built under strict Total Quality Management (TQM) principles. Targeting **Quality Goal Q05 (Reduce Response Time)**, the system achieves sub-millisecond query execution, client-side reactivity, and mistake-proofing (**Poka-Yoke**) across 21 functional domains and 12 distinct stakeholder roles:

1. **Super Administrator** (`superadmin`) — Institutional configuration, user security, audit logs, and online backups
2. **Hostel Administrator** (`hosteladmin`) — Hostels, buildings, floors, rooms, and capacity allocation
3. **Warden** (`warden`) — Daily attendance roll-call, leave/outpass approvals, and student welfare
4. **Assistant Warden** (`asstwarden`) — Floor checks, curfew monitoring, and roll-call assistance
5. **Resident Student** (`rohan`) — Room details, leave requests, complaint submission, mess menu, and fee payment
6. **Accountant** (`accountant`) — Fee structures, invoices, payment receipts, and balance ledgers
7. **Mess Manager** (`messmanager`) — Weekly dining schedules, meal feedback, and grocery inventory
8. **Maintenance Staff** (`maintenance`) — Repair work orders, spare parts utilization, and status updates
9. **Security Guard** (`security`) — Visitor pass issuance and gate outpass verification
10. **Admission Officer** (`admission`) — Student onboarding and room allocation requests
11. **Parent / Guardian** (`parent`) — Ward attendance monitoring, fee ledger, and leave tracking
12. **TQM Faculty Auditor** (`evaluator`) — Quality metrics audit, Q05 telemetry, and SLA verification

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
- **Database Engine:** SQLite 3 with Write-Ahead Logging (`WAL` mode), Foreign Key constraints, 102 B-Tree composite indexes, and FTS5 full-text virtual indexing across 58 schema tables
- **Caching Layer:** Centralized in-memory thread-safe LRU cache with multi-tag invalidation
- **Frontend Architecture:** Alpine.js reactive state controller + Tailwind CSS + Lucide icons (No heavy Webpack/Node build steps)
- **Containerization:** Docker multi-stage build + Docker Compose orchestration
- **Poka-Yoke Defect Proofing:** Database unique partial indexes, atomic transfer transactions, and event deduplication keys

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
The application will automatically initialize the database, execute all schema migrations, seed demo accounts, and open `http://127.0.0.1:8000`.

### Containerized Execution (Docker Compose)
```bash
docker-compose up -d --build
```
Access the application at `http://localhost:8000`.

---

## 🧪 Automated Testing & Verification

Run the complete test suite (203 automated unit and integration tests):
```bash
python -m unittest discover -s backend/tests -t .
```
**Result:** `Ran 203 tests in 29.551s — OK (100% Pass Rate)`.

Run the Q05 performance benchmark suite:
```bash
python scripts/benchmark_q05.py
```

---

## 📚 Technical Documentation Directory

- [Installation Guide](docs/INSTALLATION_GUIDE.md) — Comprehensive local and production setup instructions
- [User Manual](docs/USER_MANUAL.md) — Operational walkthrough for all 12 stakeholder roles
- [REST API Documentation](docs/API_DOCUMENTATION.md) — Endpoint specifications for all 21 modules
- [Production Deployment Guide](docs/DEPLOYMENT_GUIDE.md) — Nginx reverse proxy, SSL, systemd, and backup policies
- [TQM Final Project Report](docs/TQM_FINAL_PROJECT_REPORT.md) — Academic report on TQM methodology, Q05 SLA, and Poka-Yoke
- [Database Schema Specification](docs/DATABASE_SCHEMA.md) — 58 database tables (52 domain tables + FTS5 search index) and data dictionaries
- [Database Indexes Catalog](docs/DATABASE_INDEXES.md) — 48 B-Tree composite indexes and query execution plans
- [Entity-Relationship Diagram](docs/ER_DIAGRAM.md) — Mermaid visual schema relationships
- [Q05 Caching & Quick Navigation](docs/Q05_CACHED_DASHBOARD.md) — Cache invalidation and multi-tenant isolation
- [Testing Report](TESTING_REPORT.md) — Comprehensive test execution logs and verification evidence
- [Changelog](CHANGELOG.md) — Chronological history across all 15 development prompts
- [Project Progress](PROJECT_PROGRESS.md) — Requirement mapping and implementation checklist

---

## 🔐 Default Demo Credentials

Universal demo account password: `Password123!`

- Super Admin: `superadmin`
- Hostel Admin: `hosteladmin`
- Warden: `warden`
- Assistant Warden: `asstwarden`
- Resident Student: `rohan`
- Accountant: `accountant`
- Mess Manager: `messmanager`
- Maintenance Staff: `maintenance`
- Security Guard: `security`
- Admission Officer: `admission`
- Parent / Guardian: `parent`
- TQM Auditor: `evaluator`
