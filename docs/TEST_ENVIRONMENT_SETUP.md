# Hostel Management System (HMS) - Test Environment Setup Guide

**Course:** BBAT104 - Fundamentals of Total Quality Management (TQM)  
**Quality Goal:** Q05 - Zero Defects, Reproducible Quality Verification, and Test Isolation  
**Evaluation Date:** November 2, 2026  

---

## 1. Prerequisites

- **Operating System:** Windows, Linux, or macOS
- **Python Version:** Python 3.10, 3.11, 3.12, 3.13, or 3.14
- **SQLite:** SQLite 3.35+ with FTS5 support (bundled automatically with standard Python)
- **Virtual Environment:** Recommended to prevent global package conflicts

---

## 2. Local Environment Installation

From the project root (`Hostel Management System Web App`):

```bash
# 1. Create and activate virtual environment
python -m venv venv

# Windows PowerShell:
.\venv\Scripts\Activate.ps1

# Linux / macOS:
source venv/bin/activate

# 2. Install dependencies
pip install -r requirements.txt
```

---

## 3. Safe Test Execution (Zero Production Data Side-Effects)

All automated destructive and end-to-end acceptance tests utilize isolated temporary database clones (`tempfile.mkdtemp`), guaranteeing that the operational database (`data/hostel_web.db`) is never mutated or degraded during testing.

### Running Acceptance Tests
To run the full-spectrum multi-stakeholder acceptance test suite:

```bash
python -m unittest backend/tests/test_e2e_acceptance.py -v
```

Expected output:
```text
Ran 16 tests in ~15s
OK
```

### Running the Entire Automated Regression Suite
To execute all 233 automated unit, integration, and security tests:

```bash
python -m unittest discover -s backend/tests -p "test_*.py"
```

Expected output:
```text
Ran 233 tests in ~50s
OK
```

---

## 4. Database Integrity Verification Commands

To directly verify SQLite structural and referential integrity on any database file:

```bash
python -c "
from backend.app.database.connection import get_db_connection
conn = get_db_connection()
cur = conn.cursor()

# 1. Structural integrity check
cur.execute('PRAGMA integrity_check;')
print('Integrity Check:', cur.fetchone()[0])

# 2. Referential integrity foreign key check
cur.execute('PRAGMA foreign_key_check;')
violations = cur.fetchall()
print(f'Foreign Key Violations: {len(violations)}')

conn.close()
"
```

Expected output:
```text
Integrity Check: ok
Foreign Key Violations: 0
```

---

## 5. Docker Deployment & Container Verification Guide

*(Note: Docker runtime verification was marked as NOT TESTED on the Windows evaluation host due to absence of the Docker engine).*

When deploying on a host with Docker installed:

### Step 1: Provide Mandatory Production Secrets
Create a `.env` file or export secrets in your shell. The production configuration strictly requires non-placeholder keys of at least 32 characters:

```bash
# Generate random 64-character secrets
export SECRET_KEY=$(python -c "import secrets; print(secrets.token_hex(32))")
export JWT_SECRET_KEY=$(python -c "import secrets; print(secrets.token_hex(32))")
export ENVIRONMENT=production
```

### Step 2: Build and Run Container
```bash
docker compose up --build -d
```

### Step 3: Verify Health Check and Telemetry
```bash
curl -I http://localhost:8000/api/health
```

Expected response headers:
```http
HTTP/1.1 200 OK
content-type: application/json
x-response-time-ms: <latency>
```
Response body:
```json
{"status": "healthy", "service": "Hostel Management System API"}
```
