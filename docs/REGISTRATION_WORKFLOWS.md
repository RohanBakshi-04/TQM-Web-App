# Hostel Management System (HMS) - Stakeholder Registration & Onboarding Workflows

**Course:** BBAT104 - Fundamentals of Total Quality Management (TQM)  
**Quality Goal:** Q05 - Zero Defects, Mistake-Proofing (Poka-Yoke), Multi-Stakeholder Governance  
**Evaluation Date:** November 3, 2026  
**Status:** **ACTIVE & FULLY ENFORCED**

---

## 1. Executive Summary

The Hostel Management System (HMS) provides 3 distinct, dedicated onboarding pathways designed to mistake-proof account creation and enforce institutional verification before granting operational access:

1. **Student Registration:** Resident undergraduate and postgraduate students enrolling into campus hostels.
2. **Faculty & Staff Application:** Hostel wardens, maintenance technicians, electricians, plumbers, mess managers, security guards, and financial accountants.
3. **Parent & Legal Guardian Registration:** Family members seeking real-time telemetry on their enrolled ward's attendance, mess subscriptions, fee dues, and leave permissions.

All accounts register in an inactive state (`is_active = 0`) with `Pending_Approval` status. No access tokens or cookies are issued at registration, strictly blocking premature or unauthorized portal access until institutional approvals are complete.

---

## 2. Category 1: Student Registration Workflow

### Form Fields & Validation Rules
- **Full Name:** First Name, Last Name (strict alphabetic validation: `^[a-zA-Z\s'-]{1,50}$`).
- **Institutional Contact:** Email (institutional domain validation: `^[a-zA-Z0-9_.+-]+@[a-zA-Z0-9-]+\.[a-zA-Z0-9-.]+$`).
- **Mobile Number:** 10 digits numeric only (Poka-Yoke: no symbols, spaces, or country codes).
- **Gender:** `Male` (allocated to Boys Hostels) or `Female` (allocated to Girls Hostel).
- **Academic Details:** Department / Branch (CSE, ECE, ME, CE, IT, Management), Academic Year (1st Year, 2nd Year, etc.), Semester.
- **Student Roll / Enrollment No:** Alphanumeric identifier (`^[a-zA-Z0-9_-]{2,30}$`). Auto-generated with format `STU-YYYYMM-XXXX` if left unassigned.
- **Permanent Address:** Street address, city, state, pincode.
- **Emergency / Guardian Contact:** Primary contact name, relationship, phone number.

### Lifecycle & Approval Chain
```
[Student Submits Form]
       |
       v
[User created with is_active=0]
[Registration Request logged: status='Pending', admin_warden_status='Pending']
       |
       v
[Institutional Review by Warden or Admin]
  - Warden verifies enrollment credentials & hostel capacity
  - Warden reviews room allocation eligibility
       |
  +----+------------------+
  |                       |
  v                       v
[Approve]              [Reject]
  |                       |
  v                       v
[is_active = 1]        [Status = 'Rejected']
[Student Notified]     [Account Disabled]
```

---

## 3. Category 2: Faculty & Staff Application Workflow

### Form Fields & Validation Rules
- **Full Name & Contact:** First Name, Last Name, Email, Phone (10 numeric digits).
- **Staff Specialization / Designation:**
  - `warden`: Hostel Warden (Administration, room allocations, leave approvals)
  - `assistant_warden`: Assistant Warden (Discipline, student welfare)
  - `maintenance_staff`: General Facility, Carpentry, Masonry
  - `electrician`: Electrical systems, appliances, power safety
  - `plumber`: Water supply, pipelines, sanitary maintenance
  - `mess_manager`: Kitchen operations, menu scheduling, inventory
  - `security_guard`: Campus gate security, visitor logs, curfew enforcement
  - `accountant`: Fees, billing, payment verification, refunds
- **Hostel Assignment (for Warden):** Selection of campus hostel facility.
  - **Poka-Yoke Constraint:** Each hostel has a hard maximum quota of 2 wardens (`MAX_WARDENS = 2`). If a hostel has 2 active/pending wardens, the selection is disabled as "Not Required - Warden Capacity Full (2/2)".
- **Employee Identification:** Unique `staff_id` generated with format `STF-XXXX`.

### Lifecycle & Approval Chain
```
[Staff Submits Application]
       |
       v
[User created with is_active=0]
[Registration Request logged: status='Pending', admin_warden_status='Pending']
       |
       v
[Review strictly by System Administrator]
  (Wardens CANNOT approve fellow staff members)
       |
  +----+------------------+
  |                       |
  v                       v
[Approve]              [Reject]
  |                       |
  v                       v
[is_active = 1]        [Status = 'Rejected']
[Role Assigned]        [Rejection reason recorded]
```

---

## 4. Category 3: Parent & Guardian Registration Workflow

### Form Fields & Validation Rules
- **Parent Identity:** Full Name, Contact Email, Phone (10 numeric digits).
- **Relationship:** Father, Mother, Legal Guardian.
- **Child Identifier:** Student Roll Number, Enrollment ID, or University Email.
- **Poka-Yoke Verification:** System resolves `child_identifier` against the authoritative `students` table. If no enrolled student matches, registration is immediately rejected with `HTTP 404 Not Found`.

### Dual-Approval Multi-Stakeholder Chain
To prevent unauthorized surveillance or fraudulent parent-student associations, Parent registrations require **TWO-STEP DUAL CONFIRMATION**:

```
[Parent Submits Form with Child Roll No]
       |
       v
[Child Enrolled Record Verified in DB]
[Registration Request logged: status='Pending']
[student_approval_status='Pending', admin_warden_approval_status='Pending']
       |
       +-------------------------------+
       |                               |
       v                               v
[Step 1: Student Verification]   [Step 2: Warden/Admin Verification]
Student receives in-app alert     Warden reviews family documentation
on resident portal dashboard      and institutional admission records
       |                               |
       v                               v
[Student Approves Ward Link]     [Warden/Admin Approves Record]
       |                               |
       +---------------+---------------+
                       |
                       v
       [Both Approvals Completed?]
             /                   \
           Yes                    No
           /                        \
          v                          v
[status = 'Approved']       [Awaits Remaining Party]
[is_active = 1]
[Parent Account Active]
```

---

## 5. Security & Isolation Invariants

1. **Pending Account Lockout:** Users with `is_active = 0` are completely rejected at `/api/v1/auth/login` (`HTTP 403 Forbidden: Account is pending administrative approval`).
2. **Zero In-Memory Tokens on Registration:** Registration returns `access_token: ""`, `refresh_token: ""`, `expires_in: 0`. No sessions are initialized.
3. **Poka-Yoke Unique Email/Phone/Roll No:** Email, phone, username, and roll number uniqueness is checked across both active accounts AND pending requests, blocking race conditions and duplicate account clutter.
4. **Broadcast Synchronization:** When a registration is submitted, client applications broadcast via `BroadcastChannel('hms_registrations_sync')` to immediately notify active Warden and Admin sessions without requiring page refreshes.
