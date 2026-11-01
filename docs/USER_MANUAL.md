# Hostel Management System (HMS) — User Manual
**Course:** BBAT104 - Fundamentals of Total Quality Management (TQM)  
**Academic Session:** 2026-27  
**Assigned Quality Goal:** Q05 — Reduce Response Time (< 10ms SLA)  
**Author:** Rohan Bakshi (Roll No: 2410301057)

---

## 1. Introduction & Overview

The **Hostel Management System (HMS)** is an enterprise-grade web application designed for comprehensive residential facility administration. Built upon Total Quality Management (TQM) principles—specifically Continuous Quality Improvement (Kaizen), Defect Prevention (Poka-Yoke), and Performance Excellence (Q05: Response Time < 10ms)—the system integrates 21 functional domains across 12 distinct stakeholder roles.

---

## 2. Global Navigation & Core Features

### 2.1 Unified Header & Search
- **Instant Global Search (`Ctrl + K` or Search Bar):** Type any query (student name, room number, complaint ID, payment reference) to retrieve debounced, sub-millisecond full-text results indexed by SQLite FTS5.
- **Emergency Announcement Banner:** Any active critical notice (e.g., severe weather warning, facility shutdown) is immediately highlighted at the top of the interface in high-contrast red.
- **Notification Center Bell:** Shows real-time badge count of unread alerts. Clicking the bell reveals a chronological slide-over panel with category badges, timestamps, and quick "Mark as Read" actions.
- **User Profile Menu:** Displays currently logged-in user name, role badge, session status, and a secure one-click Logout button.

---

## 3. Role-Based Operations Guide

### 3.1 Resident Student (`student`)
- **Dashboard:** View personal room allocation (Hostel, Block, Floor, Room, Bed), fee payment status, upcoming mess menu, and active complaints.
- **Complaints & Maintenance:**
  - Submit complaints across 10 categories (Electrical, Plumbing, Wi-Fi, Mess, etc.) with priority levels.
  - Track real-time progress (`Submitted` → `Assigned` → `In Progress` → `Resolved`).
  - Provide feedback (1-5 stars with comments) upon resolution, or reopen unresolved issues.
- **Leave & Outpasses:**
  - Submit leave requests specifying destination, reason, departure date, and expected return.
  - Track Warden approval status and automatically receive an official Outpass code (`OP-YYYYMM-XXXX`).
- **Mess & Dining:**
  - View published weekly menus for Breakfast, Lunch, Evening Snacks, and Dinner.
  - Submit dietary feedback and meal quality ratings.
- **Fee Ledger & Payments:**
  - View invoices, breakdowns, due dates, and payment history with instant PDF/printable receipt view.
- **Announcements & Notifications:**
  - Review institutional circulars and acknowledge mandatory safety drills.

---

### 3.2 Super Administrator (`super_admin`)
- **System Administration:**
  - **System Settings:** Update institutional name, academic session, curfew timings, late fine rates, and performance SLA targets.
  - **User Administration:** Search and filter users across all roles, toggle account active status (with Poka-Yoke Super Admin deactivation protection), reassign roles, and trigger secure password resets.
  - **Roles & Permissions Matrix:** Inspect all 50+ granular permissions mapped to the 12 system roles.
  - **Audit Trails:** Search and filter immutable audit records by user, entity, action, date, and export full RFC 4180 CSV logs.
  - **Database Backups:** Trigger zero-downtime online WAL SQLite backups, view backup size and timestamps, and verify database integrity via `PRAGMA integrity_check`.

---

### 3.3 Hostel Administrator (`hostel_admin`)
- **Facility Management:**
  - Manage Hostels (Boys / Girls / International), Blocks/Buildings, Floors, and Rooms.
  - Configure room configurations: Single, Double, Triple, Four-Bed, Dormitory.
  - Monitor real-time occupancy rates, vacant bed counts, and maintenance-blocked rooms.
- **Poka-Yoke Room Allocations:**
  - Perform student room and bed allocations.
  - Atomic double-allocation barrier ensures no two active students can ever occupy the same bed.
  - Perform room transfers with automatic audit tracking and vacate checkouts.

---

### 3.4 Warden & Assistant Warden (`warden`, `assistant_warden`)
- **Daily Attendance Marking:**
  - Filter by Hostel, Building, Floor, and Room to mark daily attendance: `Present`, `Absent`, `On Leave`.
  - Batch marking shortcuts ("Mark All Present") for rapid roll-call completion.
  - View daily attendance summaries and export monthly reports.
- **Leave & Outpass Approvals:**
  - Review submitted student leave applications with guardian contact details.
  - Approve or reject applications with mandatory remarks.
  - Generating approval immediately creates an active Outpass for security gate verification.
- **Disciplinary & Complaints:**
  - Monitor escalated complaints and oversee room cleanliness checks.

---

### 3.5 Security Guard (`security_guard`)
- **Gate Outpass Verification:**
  - Verify student exit by entering the student enrollment or Outpass code.
  - Timestamp student gate exit (`exit_verified_at`) and gate return (`return_verified_at`).
  - Flags overdue returns automatically in high-contrast amber.
- **Visitor Pass Management:**
  - Register external visitors, record visitor photo/ID type, contact phone, student being visited, and purpose of visit.
  - Generate official Visitor Pass (`VP-YYYYMM-XXXX`).
  - Check out visitors upon departure with automatic checkout timestamping.

---

### 3.6 Accountant (`accountant`)
- **Fee Structure Management:**
  - Define fee schedules: Accommodation, Mess, Electricity, Maintenance, Security Deposit.
  - Configure recurring payment terms: Monthly, Quarterly, Semester-wise, Annual.
- **Invoice Generation & Billing:**
  - Issue fee invoices to individual students or batch-generate for entire hostels/floors.
  - Apply approved scholarship discounts or waivers with recorded justifications.
- **Payment Collection & Receipts:**
  - Record payments (Online UPI, Net Banking, Demand Draft, Cash).
  - Issue official timestamped receipts with transaction references.
  - Process partial payments and calculate outstanding balance automatically.

---

### 3.7 Mess Manager (`mess_manager`)
- **Menu Planning:**
  - Schedule weekly menu schedules across 4 daily meal slots (Breakfast, Lunch, Snacks, Dinner).
  - Publish menus visible immediately to all resident students.
- **Inventory & Supplies:**
  - Manage grocery, dairy, and cleaning consumable inventory.
  - Track stock levels, set minimum reorder thresholds (`min_reorder_level`), and log purchase receipts.
  - Monitor low-stock alerts automatically triggered when inventory drops below safety buffers.
- **Meal Ratings & Feedback:**
  - Review student meal ratings to continuously improve food quality and reduce wastage.

---

### 3.8 Maintenance Staff (`maintenance_staff`)
- **Task Workbench:**
  - View assigned repair tickets filtered by trade (Electrical, Plumbing, Carpentry, Masonry).
  - Update ticket status: `In Progress`, `On Hold (Awaiting Parts)`, `Resolved`.
  - Record spare parts utilized and maintenance notes for facility records.

---

### 3.9 Admission Officer (`admission_officer`)
- **Student Onboarding:**
  - Register admitted students, verify guardian records, medical conditions, and blood groups.
  - Initiate initial room allocation requests based on student preferences and room availability.

---

### 3.10 Parent / Guardian (`parent_guardian`)
- **Ward Oversight Portal:**
  - View child's current room allocation and roommate details.
  - Monitor daily attendance records and absence alerts.
  - Review approved outpasses and gate exit/return timestamps.
  - Inspect fee dues and download receipt acknowledgments.

---

### 3.11 TQM Faculty Auditor (`auditor`)
- **Quality & SLA Evaluation:**
  - Inspect Q05 performance dashboard tracking average response times across all endpoints.
  - Audit system logs for compliance, security access violations, and role adjustments.
  - Verify Poka-Yoke defect-proofing barriers and database integrity metrics.
