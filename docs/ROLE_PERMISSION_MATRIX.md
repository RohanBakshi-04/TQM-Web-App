# Hostel Management System (HMS) - Role & Permission Matrix

**Course:** BBAT104 - Fundamentals of Total Quality Management (TQM)  
**Quality Goal:** Q05 - Zero Defects, Strict RBAC Data Isolation, Multi-Stakeholder Governance  
**Evaluation Date:** November 2, 2026  
**Status:** **100% VERIFIED**

---

## 1. Overview of 12 Stakeholder Roles

The Hostel Management System implements fine-grained, hierarchical, and domain-scoped Role-Based Access Control (RBAC). Every endpoint enforces role and permission dependencies via `backend/app/services/auth_dependencies.py`.

| # | Role Key | Role Title | Scope & Authority |
|---|---|---|---|
| 1 | `super_admin` | Super Administrator | Global campus-wide governance, system settings, user lifecycle, audit trail |
| 2 | `hostel_admin` | Hostel Administrator | Multi-hostel facility management, room structures, capacity planning |
| 3 | `warden` | Hostel Warden | Single assigned hostel management, admissions, allocations, approvals, discipline |
| 4 | `assistant_warden`| Assistant Warden | Hostel operations, attendance review, leave recommendation, student welfare |
| 5 | `student` | Resident Student | Personal allocations, leave requests, complaint tickets, mess, fee payments |
| 6 | `accountant` | Financial Accountant | Fee structures, student invoicing, payment verification, refunds ledger |
| 7 | `mess_manager` | Mess & Dining Manager | Menu planning, dining schedules, inventory procurement, meal attendance |
| 8 | `maintenance_staff`| Maintenance Technician | Work order acceptance, repairs, parts logging, completion reports |
| 9 | `security_guard` | Security & Gate Guard | Gate outpass verification, visitor registration, curfew compliance |
| 10 | `admission_officer` | Admissions Officer | Registration request verification, document review, candidate onboarding |
| 11 | `parent_guardian` | Parent / Legal Guardian | Read-only telemetry for linked ward: attendance, fees, leave outpasses |
| 12 | `auditor` | Compliance Auditor | Read-only system-wide audit logs, financial reports, operational telemetry |

---

## 2. Comprehensive Endpoint Permission Matrix

| Module / Route Prefix | Super Admin | Hostel Admin | Warden | Asst Warden | Student | Accountant | Mess Mgr | Maint Staff | Security | Admission | Parent | Auditor |
|---|:---:|:---:|:---:|:---:|:---:|:---:|:---:|:---:|:---:|:---:|:---:|:---:|
| **`/api/v1/auth/login`** | ✅ | ✅ | ✅ | ✅ | ✅ | ✅ | ✅ | ✅ | ✅ | ✅ | ✅ | ✅ |
| **`/api/v1/auth/me`** | ✅ | ✅ | ✅ | ✅ | ✅ | ✅ | ✅ | ✅ | ✅ | ✅ | ✅ | ✅ |
| **`/api/v1/auth/switch-role`** | Assigned | Assigned | Assigned | Assigned | Assigned | Assigned | Assigned | Assigned | Assigned | Assigned | Assigned | Assigned |
| **`/api/v1/admin/settings`** | ✅ | ❌ | ❌ | ❌ | ❌ | ❌ | ❌ | ❌ | ❌ | ❌ | ❌ | ❌ |
| **`/api/v1/admin/users`** | Full | Read | ❌ | ❌ | ❌ | ❌ | ❌ | ❌ | ❌ | ❌ | ❌ | Read |
| **`/api/v1/dashboard/stats`** | Global | Global | Hostel | Hostel | Own | Finance | Mess | Tasks | Gate | Pending | Ward | Global |
| **`/api/v1/hostels`** | Full | Full | Read Own | Read Own | Read Own | Read | Read | Read | Read | Read | Read | Read |
| **`/api/v1/rooms`** | Full | Full | Hostel | Hostel | Read Own | Read | ❌ | ❌ | ❌ | Read | ❌ | Read |
| **`/api/v1/allocations`** | Full | Full | Hostel | Hostel | Read Own | Read | ❌ | ❌ | Read | Read | Read Ward | Read |
| **`/api/v1/allocations/transfer`** | Full | Full | Hostel | Hostel | Apply Own | ❌ | ❌ | ❌ | ❌ | ❌ | ❌ | Read |
| **`/api/v1/registrations/pending`** | ✅ | ✅ | ✅ | ❌ | ❌ | ❌ | ❌ | ❌ | ❌ | ✅ | ❌ | Read |
| **`/api/v1/attendance`** | Full | Full | Hostel | Hostel | Read Own | ❌ | ❌ | ❌ | Mark Gate | ❌ | Read Ward | Read |
| **`/api/v1/leave`** | Full | Full | Approve | Review | Apply Own | ❌ | ❌ | ❌ | ❌ | ❌ | Read Ward | Read |
| **`/api/v1/outpasses`** | Full | Full | Read | Read | Read Own | ❌ | ❌ | ❌ | Verify | ❌ | Read Ward | Read |
| **`/api/v1/visitors`** | Full | Full | Read | Read | Read Own | ❌ | ❌ | ❌ | Full Gate | ❌ | ❌ | Read |
| **`/api/v1/complaints`** | Full | Full | Assign | Review | Create Own | ❌ | ❌ | ❌ | ❌ | ❌ | ❌ | Read |
| **`/api/v1/maintenance/tasks`** | Full | Full | Create | Read | ❌ | ❌ | ❌ | Accept/Done | ❌ | ❌ | ❌ | Read |
| **`/api/v1/fees/structures`** | Full | Read | Read | Read | Read | Full | ❌ | ❌ | ❌ | Read | Read | Read |
| **`/api/v1/fees/invoices`** | Full | Read | Read Own | Read Own | Own Only | Full | ❌ | ❌ | ❌ | Read | Ward Only | Read |
| **`/api/v1/fees/payments`** | Full | Read | Read Own | Read Own | Pay Own | Full | ❌ | ❌ | ❌ | ❌ | Pay Ward | Read |
| **`/api/v1/fees/refunds`** | Full | ❌ | ❌ | ❌ | Own | Process | ❌ | ❌ | ❌ | ❌ | ❌ | Read |
| **`/api/v1/mess/menus`** | Full | Read | Read | Read | Read | ❌ | Full | ❌ | ❌ | ❌ | Read | Read |
| **`/api/v1/mess/inventory`** | Full | Read | Read | ❌ | ❌ | Read | Full | ❌ | ❌ | ❌ | ❌ | Read |
| **`/api/v1/audit/logs`** | Full | ❌ | ❌ | ❌ | ❌ | ❌ | ❌ | ❌ | ❌ | ❌ | ❌ | Read |

---

## 3. Row-Level Data Isolation Rules (IDOR Defense)

1. **Student Resident Isolation:**
   - A student (`role == "student"`) cannot read, modify, or inspect records associated with any other student ID.
   - Enforced by `verify_student_isolation(student_id, current_user)` on `/api/v1/students/{id}/profile`, `/api/v1/attendance/student/{id}`, `/api/v1/fees/invoices/student/{id}`, and `/api/v1/fees/payments/student/{id}`.
   - Non-matching IDs raise `HTTP 403 Forbidden`.

2. **Parent / Guardian Ward Boundary:**
   - Parents (`role in ("parent", "parent_guardian")`) are bound to wards linked in `student_parents`.
   - Access to unlinked student records raises `HTTP 403 Forbidden`.

3. **Hostel Staff Scope:**
   - Wardens and Assistant Wardens are scoped to their assigned `linked_hostel_id`.
   - Attempting to inspect or allocate rooms, leave requests, or complaints belonging to another hostel raises `HTTP 403 Forbidden`.

4. **Multi-Role Switching:**
   - Users may only switch between roles explicitly assigned in `user_roles`.
   - Calling `/api/v1/auth/switch-role` with an unassigned role is rejected with `HTTP 403 Forbidden`.
