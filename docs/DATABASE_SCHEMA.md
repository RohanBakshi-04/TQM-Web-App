# Database Architecture & Schema Specification

**Course:** BBAT104 – Fundamentals of Total Quality Management (TQM)  
**Academic Session:** 2026–27  
**Quality Goal:** Q05 – Reduce Response Time  
**Engine:** SQLite3 with Write-Ahead Logging (`WAL` mode) & B-Tree Indexes  
**Total Tables:** 39 Tables across 8 Functional Domains  

---

## 1. Relational Domains & Tables Directory

| # | Table Name | Functional Domain | Primary Role |
| :---: | :--- | :--- | :--- |
| **1** | `users` | User & Access | System account credentials and profile |
| **2** | `roles` | User & Access | Role definitions (Admin, Warden, Student, Staff, Auditor) |
| **3** | `permissions` | User & Access | Granular action permissions per module |
| **4** | `role_permissions` | User & Access | Many-to-Many mapping between roles and permissions |
| **5** | `user_roles` | User & Access | User role assignments |
| **6** | `students` | Student Management | Student academic and personal records |
| **7** | `guardians` | Student Management | Parent / Guardian emergency contacts |
| **8** | `student_guardians` | Student Management | Relationship linkage between students and guardians |
| **9** | `student_documents` | Student Management | File storage and verification audit for student docs |
| **10** | `admission_applications` | Student Management | Prospective hostel admission requests |
| **11** | `hostels` | Hostel Management | Multi-hostel campus facility records |
| **12** | `buildings` | Hostel Management | Wings and blocks within a hostel |
| **13** | `floors` | Hostel Management | Floor levels within a building |
| **14** | `rooms` | Hostel Management | Room inventory, types, base fee & capacity |
| **15** | `beds` | Hostel Management | Discrete bed entities within a room |
| **16** | `room_allocations` | Hostel Management | Historical and active student bed allotments |
| **17** | `attendance` | Attendance & Operations | Daily student night curfew / roll call logs |
| **18** | `leave_requests` | Attendance & Operations | Gate-pass / outstation leave approval workflow |
| **19** | `visitors` | Attendance & Operations | Master visitor profiles and government ID proof |
| **20** | `visitor_logs` | Attendance & Operations | Timestamped entry and exit check logs |
| **21** | `complaints` | Complaints & Maintenance | Student maintenance and grievance tickets |
| **22** | `complaint_updates` | Complaints & Maintenance | Audit trail of ticket status transitions & notes |
| **23** | `maintenance_tasks` | Complaints & Maintenance | Scheduled facility repairs and worker assignments |
| **24** | `maintenance_history` | Complaints & Maintenance | Log of maintenance actions and actual costs |
| **25** | `fee_structures` | Financial Management | Semester / monthly fee slabs per room type |
| **26** | `invoices` | Financial Management | Dues billed to students |
| **27** | `invoice_items` | Financial Management | Line items constituting an invoice |
| **28** | `payments` | Financial Management | Digital & cash fee payment transactions |
| **29** | `refunds` | Financial Management | Security deposit and fee adjustments |
| **30** | `mess_menus` | Mess & Inventory | Weekly scheduled breakfast, lunch, and dinner menus |
| **31** | `mess_subscriptions` | Mess & Inventory | Student dining meal plans |
| **32** | `meal_attendance` | Mess & Inventory | Real-time dining hall swipe / punch logs |
| **33** | `inventory_categories` | Mess & Inventory | Grouping for furniture, plumbing, electrical supplies |
| **34** | `inventory_items` | Mess & Inventory | Physical stock quantities and re-order thresholds |
| **35** | `inventory_transactions` | Mess & Inventory | Purchase, issuance, and repair consumption logs |
| **36** | `notifications` | System Management | In-app user alerts and ticket updates |
| **37** | `announcements` | System Management | Broadcast circulars from Chief Warden |
| **38** | `audit_logs` | System Management | Immutable security and Q05 telemetry log |
| **39** | `system_settings` | System Management | Dynamic system configurations and institutional keys |

---

## 2. In-Depth Schema Definitions & Integrity Constraints

### Domain 1: User & Access Management
- **`users`**: Enforces unique username and email addresses. Password hashes use PBKDF2-HMAC-SHA256 with distinct cryptographic salts.
- **`roles` & `permissions`**: Enables granular Role-Based Access Control (RBAC). System-defined roles (`is_system = 1`) cannot be inadvertently dropped.
- **`user_roles`**: Unique composite constraint `(user_id, role_id)` prevents redundant assignment.

### Domain 2: Student Management
- **`students`**: Primary key `id` with distinct business identifier `student_id`. Enforces non-null admission dates, gender constraints, and email uniqueness. Foreign key to `users` allows seamless self-service login.
- **`student_guardians`**: Enforces `UNIQUE(student_id, guardian_id)` supporting multiple guardians (father, mother, local guardian) with primary contact flags.
- **`student_documents`**: Tracks document verification lifecycle (`Pending` $\to$ `Verified` $\to$ `Rejected`).

### Domain 3: Hostel Management Hierarchy
- **Hierarchy:** `hostels` $(1:N) \to$ `buildings` $(1:N) \to$ `floors` $(1:N) \to$ `rooms` $(1:N) \to$ `beds` $(1:N) \to$ `room_allocations`.
- **`rooms`**:
  - `capacity`: Enforces `CHECK(capacity BETWEEN 1 AND 10)`.
  - `base_fee`: Enforces `CHECK(base_fee >= 0)`.
  - `UNIQUE(floor_id, room_number)` ensures room numbers are uniquely scoped per floor.
- **`beds`**:
  - `UNIQUE(room_id, bed_number)` prevents duplicate bed labeling within any room.
- **`room_allocations`**:
  - `CHECK(end_date IS NULL OR end_date >= start_date)`.
  - Preserves historical records with status transitions (`Active`, `Vacated`, `Transferred`, `Cancelled`).
  - Uses `ON DELETE RESTRICT` on students, beds, and rooms to prevent orphan deletion.

### Domain 4: Attendance & Operations
- **`attendance`**: Unique composite index on `(student_id, date)` ensures single daily status per student.
- **`leave_requests`**: Validates `CHECK(end_date >= start_date)`.

### Domain 5: Complaints & Maintenance
- **`complaints`**: Unique ticket code format (`CMP-YYYY-XXXX`). Severity levels: `Low`, `Medium`, `High`, `Emergency`.
- **`complaint_updates`**: Captures historical timeline of remarks and status changes without overwriting original ticket submissions.

### Domain 6: Financial Management
- **`invoices`**:
  - `paid_amount`: Validated with `CHECK(paid_amount >= 0 AND paid_amount <= total_amount)`.
  - `due_date`: Enforced with `CHECK(due_date >= issue_date)`.
- **`payments`**:
  - `amount`: Enforced with strict positive constraint `CHECK(amount > 0)`.
  - Method check constraint: `UPI`, `Credit_Card`, `Debit_Card`, `Net_Banking`, `Cash`, `Demand_Draft`.

### Domain 7: Mess & Inventory
- **`mess_menus`**: Composite unique key `UNIQUE(day_of_week, meal_type)`.
- **`inventory_items`**: Check constraints for non-negative stock counts and unit prices.

### Domain 8: System Management
- **`audit_logs`**: Captures user actions, target entity, IP address, and sub-millisecond execution latency (`latency_ms >= 0`).
- **`system_settings`**: Key-value pair configuration for runtime parameters.
