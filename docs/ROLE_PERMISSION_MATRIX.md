# Hostel Management System (HMS) - Enterprise Role & Permission Matrix

**Course:** BBAT104 - Fundamentals of Total Quality Management (TQM)  
**Quality Goal:** Q05 - Zero Defects, Enterprise RBAC Data Isolation, Multi-Stakeholder Governance  
**Evaluation Date:** November 3, 2026  
**Status:** **100% VERIFIED (Centralized Enterprise RBAC Active & Enforced)**

---

## 1. Overview of 15 Enterprise Stakeholder Roles

The Hostel Management System implements centralized, fine-grained, domain-scoped Role-Based Access Control (RBAC) backed by **121 granular permissions** and **406 role-permission mappings** (Migration 020).

### 10 Core Administrative & Operational Roles
| # | Role Key | Canonical Code | Role Title | Category | Scope & Authority |
|---|---|---|---|---|---|
| 1 | `super_admin` | `SUPER_ADMIN` | Super Administrator | Executive / Leadership | Global campus-wide governance, system settings, user account lifecycle, online backups, custom role creation/deletion, audit trail inspection. |
| 2 | `hostel_admin` | `HOSTEL_DIRECTOR` | Hostel Director | Executive / Leadership | Strategic multi-hostel facility management, building/floor/room allocation policies, fee structure definitions, capacity planning. |
| 3 | `warden` | `CHIEF_WARDEN` | Chief Warden | Administrative / Hostels | Primary operational head for single assigned hostel facility, resident student welfare, discipline, room approvals, student leaves. |
| 4 | `assistant_warden` | `ASSISTANT_WARDEN` | Assistant Warden | Administrative / Hostels | Assists chief warden with delegated floor/block roll-calls, evening curfews, visitor pass verification, and daily student logistics. |
| 5 | `hostel_clerk` | `HOSTEL_CLERK` | Hostel Clerk | Administrative / Front Office | Front-desk administrative officer managing office records, document verification, certificate requests, physical check-in/out registers. |
| 6 | `accountant` | `ACCOUNTANT` | Financial Accountant | Financial & Accounting | Fee structure management, student invoicing, payment verification, offline demand drafts, caution deposit refund processing, CSV ledgers. |
| 7 | `admission_officer` | `ADMISSION_OFFICER` | Admissions Officer | Admissions & Enrollment | Student candidate onboarding, quota allocations, document verification, initial room eligibility checks, intake workflows. |
| 8 | `security_supervisor` | `SECURITY_SUPERVISOR` | Security Supervisor | Campus Safety & Security | Security oversight managing gate access logs, guard shift rosters, incident escalations, and campus perimeter safety. |
| 9 | `security_guard` | `SECURITY_GUARD` | Campus Security Guard | Campus Safety & Security | Digital gatekeeper dashboard, verifying student outpasses (`OP-XXXX`) on exit/return, logging visitor passes (`VP-XXXX`), curfew enforcement. |
| 10 | `it_admin` | `IT_ADMIN` | IT Administrator | Technical & Infrastructure | Technical administrator overseeing system health telemetry, database backup schedules, worker lease management, and audit logs (privacy-isolated from student personal records). |

### 5 Preserved Operational & Beneficiary Stakeholders
| # | Role Key | Canonical Code | Role Title | Category | Scope & Authority |
|---|---|---|---|---|---|
| 11 | `student` | `STUDENT` | Student Resident | Resident & Beneficiary | Personal room telemetry, roll-call attendance logs, leave & outpass applications, complaint filing, fee payments, mess dining subscriptions. |
| 12 | `parent_guardian` | `PARENT_GUARDIAN` | Parent / Guardian | Resident & Beneficiary | Multi-ward oversight dashboard, real-time attendance monitoring, leave consent, fee payment receipts, and warden communication. |
| 13 | `mess_manager` | `MESS_MANAGER` | Mess & Dining Manager | Operational / Student Life | Weekly meal planning, dietary requirements (Veg, Non-Veg, Jain), meal attendance QR verification, food inventory stock tracking. |
| 14 | `maintenance_staff` | `MAINTENANCE_STAFF` | Maintenance Worker | Operational / Student Life | Technician work orders, scheduled repairs, repair status tracking (Assigned -> In Progress -> Completed), material expense tracking. |
| 15 | `auditor` | `AUDITOR` | Compliance Auditor | Technical & Compliance | Read-only access to all operational audit trails, latency metrics, SLA compliance dashboards, defect density reports. |

---

## 2. Standardized Permission Schema (`module.resource.action`)

The system standardizes all permissions to the canonical format `module.resource.action` while maintaining bidirectional backward compatibility with legacy `module:action` syntax through `PERMISSION_EQUIVALENCES` in `backend/app/services/rbac_data.py`.

### Representative Standardized Permissions
- **Clerk & Front-Office:** `clerk.document.verify`, `clerk.register.manage`, `clerk.certificate.issue`
- **Security & Campus Safety:** `security.roster.manage`, `security.incident.escalate`, `security.patrol.log`, `visitors.pass.create`, `attendance.gate.verify`
- **IT Administration & Telemetry:** `system.health.read`, `system.backup.manage`, `system.workers.manage`, `audit.telemetry.read`
- **Admissions & Quotas:** `admissions.quota.manage`, `admissions.application.review`, `registrations.approval.action`
- **Finance & Accounting:** `fees.structures.manage`, `fees.invoices.generate`, `fees.payments.verify`, `fees.refunds.process`
- **Hostel Operations:** `hostels.facility.manage`, `rooms.inventory.manage`, `allocations.lifecycle.execute`

---

## 3. Data-Level Isolation & Field Privacy Scoping

| Stakeholder Role | Data Scoping Rule | Enforcement Mechanism |
|---|---|---|
| `it_admin` | **Air-gapped from student private records.** Access to `/api/v1/students/{id}` returns `HTTP 403 Forbidden: IT Administrators are restricted from viewing student private records.` | `verify_student_isolation` in `auth_dependencies.py` |
| `hostel_clerk` | **Scoped to assigned facility.** Can only inspect and manage registers for students allocated within their assigned `linked_hostel_id`. | `verify_student_isolation` in `auth_dependencies.py` |
| `warden` / `assistant_warden` | **Scoped to assigned facility.** Queries and mutation actions fail closed with `HTTP 403 Forbidden` if student is allocated outside `linked_hostel_id`. | `verify_student_isolation` in `auth_dependencies.py` |
| `security_guard` / `security_supervisor` | **Perimeter and Gate Scoping.** Access restricted to gate outpass verification, visitor logs, curfew breaches, and incident escalation. | Route-level `require_roles` / `require_permissions` |
| `student` | **Strict self-isolation.** Access restricted strictly to own resident records (`linked_student_id`). | `verify_student_isolation` with fail-closed rejection |
| `parent_guardian` | **Multi-ward isolation.** Access restricted strictly to verified linked wards in `parent_student_links`. | Database join verification with fail-closed rejection |

---

## 4. Role-Switching Security Safeguards

1. **Single-Role Account Immunity:** Users with only one assigned role cannot invoke `/api/v1/auth/switch-role`. Requests fail with `HTTP 403 Forbidden: Role switching is disabled for single-role accounts.`
2. **Assigned Role Boundary Enforcement:** Multi-role users can only switch between roles explicitly assigned to their account in `user_roles`.
3. **Privilege Elevation Prevention:** Unauthorized attempts to switch to unassigned roles or elevate to `super_admin` are rejected with `HTTP 403 Forbidden` and immediately logged to immutable audit trails as `UNAUTHORIZED_ROLE_SWITCH_ATTEMPT`.

---

## 5. Super Admin Role & Permission Management APIs

Super Administrators have dedicated REST endpoints to inspect and manage roles dynamically:

- `GET /api/v1/admin/roles`: List all system and custom roles with user count and assigned permissions.
- `POST /api/v1/admin/roles`: Create custom roles with name, code, category, description, and permissions. System role names are protected from collision.
- `DELETE /api/v1/admin/roles/{role_id}`: Delete custom roles. Protected system roles (`is_system_role = 1`) and roles with active assigned users are blocked from deletion.
