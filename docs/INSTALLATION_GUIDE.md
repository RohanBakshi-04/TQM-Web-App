# Hostel Management System (HMS) — Installation Guide
**Course:** BBAT104 - Fundamentals of Total Quality Management (TQM)  
**Academic Session:** 2026-27  
**Quality Goal:** Q05 — Reduce Response Time (< 10ms SLA)  
**Author:** Rohan Bakshi (Roll No: 2410301057)

---

## 1. System Requirements

### Hardware Requirements
- **Processor:** 1.8 GHz dual-core or faster (Intel Core i3 / AMD Ryzen 3 or equivalent)
- **RAM:** Minimum 2 GB (4 GB recommended)
- **Disk Storage:** Minimum 500 MB free space for application, SQLite database, and WAL logs
- **Network:** Loopback interface (`127.0.0.1`) or local LAN connection

### Software Prerequisites
- **Python:** Version 3.10, 3.11, 3.12, 3.13, or 3.14
- **Operating System:** Windows 10/11, Ubuntu 20.04/22.04 LTS, macOS Monterey/Ventura/Sonoma
- **Web Browser:** Modern Chromium-based browser (Google Chrome, Microsoft Edge, Brave) or Mozilla Firefox with JavaScript enabled
- **Optional:** Docker & Docker Compose (for containerized deployment)

---

## 2. Quick Start Installation (Local Machine)

### Step 1: Clone or Navigate to Repository
Open a terminal (PowerShell, Command Prompt, or Bash) and navigate to the project directory:
```bash
git clone https://github.com/RohanBakshi-04/TQM-Web-App.git
cd "TQM-Web-App/Hostel Management System Web App"
```

### Step 2: Set Up Python Virtual Environment
Creating a virtual environment ensures dependencies remain isolated:

**On Windows:**
```powershell
python -m venv venv
.\venv\Scripts\Activate.ps1
```

**On Linux / macOS:**
```bash
python3 -m venv venv
source venv/bin/activate
```

### Step 3: Install Required Dependencies
Install all required production packages using `pip`:
```bash
pip install -r requirements.txt
```

Verified core dependencies:
- `fastapi>=0.110.0` (High-performance asynchronous REST API framework)
- `uvicorn[standard]>=0.28.0` (Lightning-fast ASGI web server)
- `pydantic>=2.0.0` (Data validation and schema parsing)
- `python-dotenv>=1.0.0` (Environment variable configuration)
- `bcrypt>=4.0.0` (Secure one-way password hashing)
- `pyjwt>=2.8.0` (Cryptographic JWT token generation and verification)

### Step 4: Environment Configuration
Copy the provided `.env.example` template to `.env`:

**Windows (PowerShell):**
```powershell
Copy-Item .env.example .env
```

**Linux / macOS:**
```bash
cp .env.example .env
```

Configure your `.env` variables if customized ports or secrets are desired:
```ini
APP_NAME="Hostel Management System Web App"
APP_ENV="development"
DEBUG=True
HOST="127.0.0.1"
PORT=8000
SECRET_KEY="your-cryptographically-secure-random-secret"
DATABASE_PATH="data/hostel_web.db"
ENABLE_SQLITE_WAL=True
```

### Step 5: Database Initialization & Seeding
The application automatically runs migrations and seeds default demo data upon startup. To verify or manually run migrations:
```bash
python -c "from backend.app.database.init_db import initialize_database; initialize_database()"
```

### Step 6: Launch the Web Application
Start the application launcher:
```bash
python run.py
```
This launcher:
1. Verifies SQLite connection and WAL (Write-Ahead Logging) mode.
2. Applies all 9 schema migrations automatically.
3. Seeds all 12 standard demo user roles and initial system settings.
4. Indexes all entities into the FTS5 Full-Text Search catalog.
5. Launches the Uvicorn ASGI server on `http://127.0.0.1:8000`.
6. Opens your default web browser to the login portal.

---

## 3. Docker Containerized Installation

For containerized deployment with zero local Python setup:

```bash
# Build and start container
docker-compose up -d --build

# View real-time logs
docker-compose logs -f

# Verify container health
docker ps
```
Access the application at `http://localhost:8000`.

To stop the container:
```bash
docker-compose down
```

---

## 4. Default Demo Accounts

All seeded demo accounts are configured with the universal password: `Password123!`

| Role Name | Username | Email Address | Access Scope |
| :--- | :--- | :--- | :--- |
| **Super Administrator** | `superadmin` | `superadmin@univ.edu` | Full institutional authority, settings, backups |
| **Hostel Administrator**| `hosteladmin`| `hosteladmin@univ.edu`| Multi-hostel facilities, rooms, allocations |
| **Warden** | `warden` | `warden@univ.edu` | Attendance, disciplinary, outpasses, approvals |
| **Assistant Warden** | `asstwarden` | `asstwarden@univ.edu` | Day-to-day hostel monitoring & floor checks |
| **Resident Student** | `rohan` | `rohan.bakshi@univ.edu`| Profile, room view, complaints, mess, fees |
| **Accountant** | `accountant` | `accountant@univ.edu` | Fee structures, invoices, payments, receipts |
| **Mess Manager** | `messmanager`| `messmanager@univ.edu`| Menus, meal feedback, grocery inventory |
| **Maintenance Staff** | `maintenance`| `maintenance@univ.edu`| Work orders, task status, repair logs |
| **Security Guard** | `security` | `security@univ.edu` | Visitor passes, gate in/out outpass validation |
| **Admission Officer** | `admission` | `admission@univ.edu` | Inflow registrations, room assignments |
| **Parent / Guardian** | `parent` | `parent@univ.edu` | Student attendance, fees, leave updates |
| **TQM Faculty Auditor**| `evaluator` | `evaluator@univ.edu` | Audit trail review, Q05 benchmark evaluation |

---

## 5. Verification & Testing

To run the complete automated test suite (131 tests):
```bash
python -m unittest discover -s backend/tests -t .
```

To run the Quality Goal Q05 Performance Benchmark Suite:
```bash
python scripts/benchmark_q05.py
```
Ensure all measured P95 latency values report `< 10.0 ms`.
