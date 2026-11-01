# Hostel Management System (HMS) — REST API Documentation
**Course:** BBAT104 - Fundamentals of Total Quality Management (TQM)  
**Assigned Quality Goal:** Q05 — Reduce Response Time (< 10ms SLA)  
**Framework:** FastAPI (Python 3.10+) with SQLite Write-Ahead Logging (WAL) & In-Memory LRU Cache  
**Interactive Swagger UI:** `http://127.0.0.1:8000/docs` | **ReDoc:** `http://127.0.0.1:8000/redoc`

---

## 1. Authentication & Session Management (`/api/v1/auth`)

| Method | Endpoint | Description | Role / Auth |
| :--- | :--- | :--- | :--- |
| `POST` | `/api/v1/auth/login` | Authenticate user, verify bcrypt hash, issue JWT access + refresh tokens | Public |
| `POST` | `/api/v1/auth/refresh` | Rotate JWT access token using single-use refresh token (reuse detection) | Public |
| `POST` | `/api/v1/auth/logout` | Revoke current refresh token and clear active session | Bearer JWT |
| `GET` | `/api/v1/auth/me` | Fetch active user profile, assigned roles, and granular permissions | Bearer JWT |
| `POST` | `/api/v1/auth/password-reset/request`| Request password reset token via registered email | Public |
| `POST` | `/api/v1/auth/password-reset/confirm`| Complete password reset using cryptographic verification token | Public |

---

## 2. Fast Search & Catalog Indexing (`/api/v1/search`)

| Method | Endpoint | Description | Role / Auth |
| :--- | :--- | :--- | :--- |
| `GET` | `/api/v1/search` | Sub-millisecond full-text search across 10 entities via SQLite FTS5 | Bearer JWT |
| `POST` | `/api/v1/search/rebuild`| Force rebuild and re-synchronization of FTS5 search catalog | `super_admin`, `hostel_admin` |

---

## 3. Cached Dashboard & Metrics (`/api/v1/dashboard`)

| Method | Endpoint | Description | Role / Auth |
| :--- | :--- | :--- | :--- |
| `GET` | `/api/v1/dashboard/metrics` | Retrieve role-tailored dashboard aggregates (Warm cache latency < 0.05ms)| Bearer JWT |
| `GET` | `/api/v1/dashboard/cache-stats` | Inspect in-memory cache statistics (hits, misses, hit ratio, keys) | `super_admin`, `auditor` |
| `POST` | `/api/v1/dashboard/cache-clear` | Manually evict all cached dashboard entries | `super_admin` |

---

## 4. Facility & Room Management (`/api/v1/hostels`, `/api/v1/rooms`)

| Method | Endpoint | Description | Role / Auth |
| :--- | :--- | :--- | :--- |
| `GET` | `/api/v1/hostels` | List all hostels with total capacity, buildings, and occupancy | Bearer JWT |
| `POST` | `/api/v1/hostels` | Register a new hostel facility | `super_admin`, `hostel_admin` |
| `GET` | `/api/v1/hostels/{id}` | Retrieve hostel details, wardens, contact information | Bearer JWT |
| `GET` | `/api/v1/hostels/{id}/buildings` | List buildings and blocks within specified hostel | Bearer JWT |
| `GET` | `/api/v1/rooms` | Search & filter rooms by hostel, floor, room type, status | Bearer JWT |
| `POST` | `/api/v1/rooms` | Create a new room with defined bed capacity and base fee | `super_admin`, `hostel_admin` |
| `GET` | `/api/v1/rooms/{id}` | Fetch room details, bed occupancy status, active residents | Bearer JWT |
| `PUT` | `/api/v1/rooms/{id}` | Update room properties, maintenance status, fee rates | `super_admin`, `hostel_admin` |

---

## 5. Poka-Yoke Room Allocations (`/api/v1/allocations`)

| Method | Endpoint | Description | Role / Auth |
| :--- | :--- | :--- | :--- |
| `GET` | `/api/v1/allocations` | Query active and historical room allocations with pagination | Bearer JWT |
| `POST` | `/api/v1/allocations` | Allocate student to bed (Atomic double-allocation prevention barrier)| `super_admin`, `hostel_admin`, `warden` |
| `GET` | `/api/v1/allocations/{id}` | Get detailed allocation record with student and bed metadata | Bearer JWT |
| `POST` | `/api/v1/allocations/{id}/transfer` | Atomically transfer student from current bed to a new bed | `super_admin`, `hostel_admin`, `warden` |
| `POST` | `/api/v1/allocations/{id}/checkout` | Vacate student allocation, release bed status to 'Available' | `super_admin`, `hostel_admin`, `warden` |

---

## 6. Student & Guardian Management (`/api/v1/students`)

| Method | Endpoint | Description | Role / Auth |
| :--- | :--- | :--- | :--- |
| `GET` | `/api/v1/students` | List registered students with branch, year, status filters | Bearer JWT |
| `POST` | `/api/v1/students` | Register a new student profile and guardian contact | `super_admin`, `admission_officer`, `hostel_admin` |
| `GET` | `/api/v1/students/{id}` | Fetch comprehensive student profile, current room, attendance | Self (`student`), Staff |
| `PUT` | `/api/v1/students/{id}` | Update student profile information | `super_admin`, `admission_officer` |

---

## 7. Complaints & Maintenance Management (`/api/v1/complaints`, `/api/v1/maintenance`)

| Method | Endpoint | Description | Role / Auth |
| :--- | :--- | :--- | :--- |
| `GET` | `/api/v1/complaints` | List complaints filtered by status, category, severity, student | Bearer JWT |
| `POST` | `/api/v1/complaints` | Submit a new complaint with title, description, category, photos | `student`, Staff |
| `GET` | `/api/v1/complaints/{id}` | View complete complaint lifecycle, history, and remarks | Bearer JWT |
| `PUT` | `/api/v1/complaints/{id}/status`| Update complaint status (`Assigned`, `In Progress`, `Resolved`)| Staff, `maintenance_staff` |
| `POST` | `/api/v1/complaints/{id}/feedback` | Resident submits 1-5 star rating and review after resolution | `student` |
| `POST` | `/api/v1/complaints/{id}/reopen` | Reopen a resolved complaint if issue persists | `student`, `warden` |
| `GET` | `/api/v1/maintenance/tasks` | Work orders assigned to maintenance staff | Staff, `maintenance_staff` |
| `PUT` | `/api/v1/maintenance/tasks/{id}`| Update maintenance task progress, materials consumed, cost | `maintenance_staff` |

---

## 8. Attendance Management (`/api/v1/attendance`)

| Method | Endpoint | Description | Role / Auth |
| :--- | :--- | :--- | :--- |
| `GET` | `/api/v1/attendance` | Query daily attendance records by date, hostel, floor, status | Staff, `warden` |
| `POST` | `/api/v1/attendance/mark` | Record single student attendance (`Present`, `Absent`, `On Leave`)| `warden`, `assistant_warden` |
| `POST` | `/api/v1/attendance/batch`| Bulk record room or floor attendance in a single transaction | `warden`, `assistant_warden` |
| `GET` | `/api/v1/attendance/summary` | Aggregate daily attendance statistics by hostel and block | Staff, `auditor` |
| `GET` | `/api/v1/attendance/student/{id}`| Retrieve student historical attendance records | Self, Parent, Staff |

---

## 9. Leave & Outpass Management (`/api/v1/leave`, `/api/v1/outpass`)

| Method | Endpoint | Description | Role / Auth |
| :--- | :--- | :--- | :--- |
| `GET` | `/api/v1/leave` | List student leave applications | Self, Warden, Parent |
| `POST` | `/api/v1/leave` | Submit leave request with dates, destination, emergency contact | `student` |
| `POST` | `/api/v1/leave/{id}/approve` | Warden approves leave; automatically generates verified Outpass | `warden`, `assistant_warden` |
| `POST` | `/api/v1/leave/{id}/reject` | Warden rejects leave with mandatory reason | `warden`, `assistant_warden` |
| `POST` | `/api/v1/outpass/verify-exit` | Security guard records student gate exit timestamp | `security_guard`, `warden` |
| `POST` | `/api/v1/outpass/verify-return`| Security guard records student gate return timestamp | `security_guard`, `warden` |

---

## 10. Visitor Management (`/api/v1/visitors`)

| Method | Endpoint | Description | Role / Auth |
| :--- | :--- | :--- | :--- |
| `GET` | `/api/v1/visitors` | List visitor log entries with date, student, and status filters | Staff, `security_guard` |
| `POST` | `/api/v1/visitors` | Register visitor, generate Visitor Pass (`VP-YYYYMM-XXXX`) | `security_guard`, `warden` |
| `POST` | `/api/v1/visitors/{id}/checkout` | Mark visitor exit with departure timestamp | `security_guard` |

---

## 11. Fee & Financial Management (`/api/v1/fees`, `/api/v1/payments`)

| Method | Endpoint | Description | Role / Auth |
| :--- | :--- | :--- | :--- |
| `GET` | `/api/v1/fees/structures` | List configured fee structures across hostels and sessions | Bearer JWT |
| `POST` | `/api/v1/fees/structures` | Create new fee structure with category and late fine rules | `super_admin`, `accountant` |
| `GET` | `/api/v1/fees/invoices` | List invoices with paid/unpaid status and balance amounts | Staff, `accountant` |
| `POST` | `/api/v1/fees/invoices` | Generate student fee invoice | `super_admin`, `accountant` |
| `GET` | `/api/v1/payments` | Query transaction records, payment methods, receipts | `accountant`, `auditor` |
| `POST` | `/api/v1/payments` | Record student payment, issue receipt number, update invoice balance| `accountant` |

---

## 12. Mess & Inventory Management (`/api/v1/mess`, `/api/v1/inventory`)

| Method | Endpoint | Description | Role / Auth |
| :--- | :--- | :--- | :--- |
| `GET` | `/api/v1/mess/menu` | Retrieve published daily/weekly menu schedules | Bearer JWT |
| `POST` | `/api/v1/mess/menu` | Create or update meal items for Breakfast, Lunch, Snacks, Dinner| `mess_manager`, `super_admin` |
| `POST` | `/api/v1/mess/feedback` | Resident submits meal quality rating and dining feedback | `student` |
| `GET` | `/api/v1/inventory/items` | List consumable stock items, quantities, unit prices, reorder levels| `mess_manager`, Staff |
| `POST` | `/api/v1/inventory/items` | Add new inventory item to catalog | `mess_manager`, `super_admin` |
| `POST` | `/api/v1/inventory/transactions`| Record stock intake or consumption with stock level adjustment | `mess_manager` |

---

## 13. Notifications, Announcements & Administration (`/api/v1/notifications`, `/api/v1/announcements`, `/api/v1/admin`)

| Method | Endpoint | Description | Role / Auth |
| :--- | :--- | :--- | :--- |
| `GET` | `/api/v1/notifications` | Fetch user notifications with unread badge count and pagination | Bearer JWT |
| `PUT` | `/api/v1/notifications/{id}/read`| Mark individual notification as read | Bearer JWT |
| `POST` | `/api/v1/notifications/mark-all-read`| Mark all active notifications as read | Bearer JWT |
| `GET` | `/api/v1/notifications/preferences`| Retrieve delivery and category suppression preferences | Bearer JWT |
| `PUT` | `/api/v1/notifications/preferences`| Update notification delivery channels | Bearer JWT |
| `GET` | `/api/v1/announcements` | List announcements filtered by target audience and hostel isolation| Bearer JWT |
| `POST` | `/api/v1/announcements` | Create announcement (Draft, Scheduled, Published) | `super_admin`, `hostel_admin` |
| `GET` | `/api/v1/announcements/{id}` | Read announcement detail, auto-logs view timestamp | Bearer JWT |
| `POST` | `/api/v1/announcements/{id}/acknowledge`| Resident formally acknowledges notice (e.g. safety drill)| `student` |
| `GET` | `/api/v1/admin/settings` | Query system configuration parameters | `super_admin`, `auditor` |
| `PUT` | `/api/v1/admin/settings` | Bulk update system settings, logs history, evicts cache | `super_admin` |
| `GET` | `/api/v1/admin/users` | Search, filter, and inspect registered users across all roles | `super_admin` |
| `PUT` | `/api/v1/admin/users/{id}/status`| Toggle user active status (Protected against Super Admin deactivation)| `super_admin` |
| `PUT` | `/api/v1/admin/users/{id}/roles` | Update user roles (Protected against privilege escalation) | `super_admin` |
| `POST` | `/api/v1/admin/users/{id}/reset-password`| Administrative password reset without logging plaintext | `super_admin` |
| `GET` | `/api/v1/admin/roles` | Inspect all 12 roles and associated permissions | `super_admin`, `auditor` |
| `GET` | `/api/v1/admin/audit-logs` | Filter immutable audit trail by user, entity, action, date | `super_admin`, `auditor` |
| `GET` | `/api/v1/admin/audit-logs/export`| Stream full audit logs as RFC 4180 CSV export | `super_admin`, `auditor` |
| `POST` | `/api/v1/admin/backup` | Trigger online SQLite WAL backup, returns snapshot metadata | `super_admin` |
| `GET` | `/api/v1/admin/backups` | List historical database backup snapshots | `super_admin` |
| `POST` | `/api/v1/admin/restore` | Safely restore database from snapshot with pre-restore safety copy| `super_admin` |
