"""Role-Based Access Control (RBAC) Data Matrix: 12 Roles & Granular Permissions.

Course: BBAT104 - Fundamentals of Total Quality Management (TQM)
Quality Goal: Q05 - Reduce Response Time
"""

from typing import Dict, List, Tuple

# 12 Standard Roles
ROLES_LIST: List[Tuple[str, str]] = [
    ("super_admin", "Global system administrator with unrestricted control"),
    ("hostel_admin", "Hostel administrator managing assigned campus facilities"),
    ("warden", "Hostel chief warden overseeing student welfare, discipline, and room inventory"),
    ("assistant_warden", "Assistant warden executing delegated daily operations"),
    ("student", "Hostel resident accessing personal room, fee, attendance, and grievance details"),
    ("accountant", "Financial officer managing fee structures, invoicing, payments, and refunds"),
    ("mess_manager", "Mess manager handling meal planning, subscriptions, and dining hall attendance"),
    ("maintenance_staff", "Facility technician executing repairs and work order updates"),
    ("security_guard", "Campus security officer logging visitor ingress/egress and gate-passes"),
    ("admission_officer", "Admissions executive managing applications and document verification"),
    ("parent_guardian", "Parent or guardian accessing authorized data of linked wards"),
    ("auditor", "TQM compliance officer with read-only audit and latency telemetry access")
]

# Action verbs
ACTIONS = ["CREATE", "READ", "UPDATE", "DELETE", "APPROVE", "REJECT", "EXPORT", "MANAGE"]

# Modules
MODULES = [
    "users", "roles", "hostels", "rooms", "students", "allocations",
    "attendance", "leave_requests", "visitors", "complaints",
    "maintenance", "finance", "mess", "inventory", "audit", "settings"
]

# Permissions: (name, module, description)
PERMISSIONS_LIST: List[Tuple[str, str, str]] = [
    # User Management
    ("users:create", "users", "Create new system accounts"),
    ("users:read", "users", "View user account profiles"),
    ("users:update", "users", "Update user account information"),
    ("users:delete", "users", "Deactivate or delete user accounts"),
    ("users:manage", "users", "Full management of system users"),

    # Role Management
    ("roles:read", "roles", "View roles and assigned permissions"),
    ("roles:manage", "roles", "Configure role permissions and assignments"),

    # Hostel Inventory
    ("hostel:create", "hostels", "Create hostels, buildings, and rooms"),
    ("hostel:read", "hostels", "View hostel facilities and room availability"),
    ("hostel:update", "hostels", "Update room status, fees, and capacities"),
    ("hostel:delete", "hostels", "Remove decommissioned rooms"),
    ("hostel:manage", "hostels", "Full control over hostel inventory"),

    # Student Management
    ("student:create", "students", "Register and enroll students"),
    ("student:read", "students", "View student directory and profiles"),
    ("student:update", "students", "Update student contact and academic data"),
    ("student:delete", "students", "Archive or withdraw student records"),
    ("student:export", "students", "Export student lists to CSV"),

    # Room Allocation
    ("allocation:create", "allocations", "Allot beds to enrolled students"),
    ("allocation:read", "allocations", "View active and historical allocations"),
    ("allocation:update", "allocations", "Update allotment status and fee flags"),
    ("allocation:delete", "allocations", "Vacate and checkout students"),
    ("allocation:export", "allocations", "Export allocation records to CSV"),

    # Attendance
    ("attendance:create", "attendance", "Record student attendance and curfew"),
    ("attendance:read", "attendance", "View student attendance logs"),
    ("attendance:export", "attendance", "Export attendance reports"),

    # Leave Requests
    ("leave:create", "leave_requests", "Apply for outstation or medical leave"),
    ("leave:read", "leave_requests", "View leave applications"),
    ("leave:approve", "leave_requests", "Approve student leave requests"),
    ("leave:reject", "leave_requests", "Reject student leave requests"),

    # Visitors
    ("visitors:create", "visitors", "Log visitor check-in"),
    ("visitors:read", "visitors", "View visitor logs"),
    ("visitors:update", "visitors", "Record visitor check-out"),

    # Complaints & Grievances
    ("complaints:create", "complaints", "Submit grievance or repair ticket"),
    ("complaints:read", "complaints", "View complaint tickets"),
    ("complaints:update", "complaints", "Update complaint progress and resolution notes"),
    ("complaints:delete", "complaints", "Cancel or archive invalid complaints"),

    # Maintenance
    ("maintenance:create", "maintenance", "Log maintenance work orders"),
    ("maintenance:read", "maintenance", "View facility repair orders"),
    ("maintenance:update", "maintenance", "Update maintenance task status and costs"),

    # Financial Management
    ("finance:create", "finance", "Generate invoices and fee structures"),
    ("finance:read", "finance", "View invoices, fee records, and payments"),
    ("finance:update", "finance", "Record fee payments and receipts"),
    ("finance:approve", "finance", "Approve refunds and fee adjustments"),
    ("finance:export", "finance", "Export financial statements to CSV"),

    # Mess Management
    ("mess:create", "mess", "Create mess menus and meal slots"),
    ("mess:read", "mess", "View weekly mess menu and subscriptions"),
    ("mess:update", "mess", "Update dining subscriptions and attendance"),

    # Inventory
    ("inventory:create", "inventory", "Add inventory items and stock"),
    ("inventory:read", "inventory", "Inspect physical supplies and stock levels"),
    ("inventory:update", "inventory", "Issue stock items for maintenance"),

    # Audit & Telemetry
    ("audit:read", "audit", "Inspect immutable audit logs and Q05 telemetry"),
    ("audit:export", "audit", "Export system audit logs"),

    # Admissions
    ("admissions:read", "students", "View prospective admission applications"),
    ("admissions:approve", "students", "Approve student admissions and verify documents"),
    ("admissions:reject", "students", "Reject incomplete admission applications"),

    # System Settings
    ("settings:manage", "settings", "Configure global system settings")
]

# Role to Permission Names Mapping
ROLE_PERMISSIONS_MAP: Dict[str, List[str]] = {
    "super_admin": [p[0] for p in PERMISSIONS_LIST], # Full Access

    "hostel_admin": [
        "users:read", "hostel:manage", "hostel:create", "hostel:read", "hostel:update",
        "student:create", "student:read", "student:update", "student:export",
        "allocation:create", "allocation:read", "allocation:update", "allocation:delete", "allocation:export",
        "attendance:read", "attendance:export", "leave:read", "leave:approve", "leave:reject",
        "complaints:read", "complaints:update", "maintenance:read", "finance:read",
        "audit:read"
    ],

    "warden": [
        "hostel:read", "hostel:update",
        "student:read", "student:update", "student:export",
        "allocation:create", "allocation:read", "allocation:update", "allocation:delete",
        "attendance:create", "attendance:read", "attendance:export",
        "leave:read", "leave:approve", "leave:reject",
        "visitors:read", "complaints:read", "complaints:update",
        "maintenance:create", "maintenance:read",
        "finance:read", "mess:read", "audit:read"
    ],

    "assistant_warden": [
        "hostel:read", "student:read", "allocation:read",
        "attendance:create", "attendance:read",
        "leave:read", "leave:approve", "leave:reject",
        "visitors:create", "visitors:read", "visitors:update",
        "complaints:read", "complaints:update", "maintenance:read"
    ],

    "student": [
        "student:read", # Filtered to own profile
        "allocation:read", # Filtered to own allocation
        "attendance:read", # Filtered to own attendance
        "leave:create", "leave:read", # Filtered to own requests
        "complaints:create", "complaints:read", # Filtered to own tickets
        "finance:read", # Filtered to own invoices
        "mess:read"
    ],

    "accountant": [
        "finance:create", "finance:read", "finance:update", "finance:approve", "finance:export",
        "student:read", "allocation:read", "hostel:read"
    ],

    "mess_manager": [
        "mess:create", "mess:read", "mess:update",
        "student:read", "inventory:read", "inventory:update"
    ],

    "maintenance_staff": [
        "maintenance:read", "maintenance:update",
        "complaints:read", "complaints:update",
        "inventory:read", "inventory:update"
    ],

    "security_guard": [
        "visitors:create", "visitors:read", "visitors:update",
        "attendance:create", "attendance:read",
        "leave:read" # Verifying gate-pass outpasses
    ],

    "admission_officer": [
        "admissions:read", "admissions:approve", "admissions:reject",
        "student:create", "student:read", "student:update",
        "hostel:read"
    ],

    "parent_guardian": [
        "student:read", # Filtered to linked ward
        "allocation:read", # Filtered to linked ward
        "attendance:read", # Filtered to linked ward
        "finance:read" # Filtered to linked ward
    ],

    "auditor": [
        "audit:read", "audit:export",
        "student:read", "student:export",
        "allocation:read", "allocation:export",
        "finance:read", "finance:export",
        "complaints:read", "hostel:read"
    ]
}
