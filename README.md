# Hostel Management System (HMS) — Web Application

**Course:** BBAT104 – Fundamentals of Total Quality Management (TQM)  
**Academic Session:** 2026–27  
**Student Name:** Rohan Bakshi  
**Roll Number:** 2410301057  
**Branch & Section:** B.Tech Computer Science & Engineering (Section A)  
**Assigned Baseline System:** Hostel Management System (Topic Digit: 7)  
**Assigned Quality Goal:** **Q05 – REDUCE RESPONSE TIME**  
**Repository:** [https://github.com/RohanBakshi-04/TQM-Web-App](https://github.com/RohanBakshi-04/TQM-Web-App)

---

## 🎯 Project Overview

This project develops a high-performance, modular web application for hostel administration under Total Quality Management (TQM) principles. Specifically targeting **Quality Goal Q05 (Reduce Response Time)**, the system optimizes database querying, client rendering, and asynchronous execution across all stakeholder roles:

1. **Hostel Administrator / Warden** (Master occupancy, student onboarding, allocations, auditing)
2. **Student / Resident** (Self-service room details, fee tracking, grievance logging)
3. **Caretaker / Maintenance Staff** (Room status management, maintenance work order redressal)
4. **TQM Quality Auditor** (Response time telemetry, Poka-Yoke compliance, latency benchmarks)

---

## 🏗️ Architecture & Technology Stack

- **Backend:** Python 3.8+ / FastAPI (Asynchronous ASGI Web Engine)
- **Application Server:** Uvicorn (High-performance event-loop server)
- **Database Engine:** SQLite3 with Write-Ahead Logging (`WAL` mode) and Foreign Key integrity
- **Frontend Architecture:** Modern HTML5 + Tailwind CSS (via CDN) + Alpine.js (Reactive UI without heavy build tooling)
- **Configuration & Logging:** Centralized environment configuration and structured logging

---

## 📂 Project Directory Structure

```
Hostel Management System Web App/
├── backend/
│   ├── app/
│   │   ├── database/        # Connection manager, schemas & migrations
│   │   ├── models/          # Domain models & Pydantic schemas
│   │   ├── routers/         # Modular API endpoint routers
│   │   ├── services/        # Business logic & Q05 caching services
│   │   └── utils/           # Centralized logging & validation utilities
│   └── tests/               # Automated unit & integration tests
├── frontend/
│   ├── css/                 # Custom styles and animations
│   └── js/                  # Alpine.js application controller & API client
├── data/                    # Persistent SQLite database storage
├── docs/                    # Technical architecture & TQM specifications
├── scripts/                 # Maintenance, migration & seeding scripts
├── requirements.txt         # Production dependencies
├── run.py                   # Unified application startup script
├── README.md                # Project documentation
├── .gitignore               # Version control exclusion rules
└── .env.example             # Template environment variables
```

---

## ⚡ Quick Start & Verification

### 1. Installation
Clone the repository and install the lightweight dependencies:
```bash
git clone https://github.com/RohanBakshi-04/TQM-Web-App.git
cd "Hostel Management System Web App"
pip install -r requirements.txt
```

### 2. Launch Application
Run the startup script:
```bash
python run.py
```
The application starts at:
👉 **`http://127.0.0.1:8000`**

### 3. API Health Check & Swagger Documentation
- **Health Endpoint:** `http://127.0.0.1:8000/api/health`
- **Interactive API Docs (Swagger):** `http://127.0.0.1:8000/docs`
