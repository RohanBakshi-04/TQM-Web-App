"""Role-Based Access Control (RBAC) Data Matrix: 15 Roles & Granular Permissions.

Enterprise Architecture Supporting 10 Core Administrative & Operational Roles
and 5 Preserved Functional Stakeholders.

Course: BBAT104 - Fundamentals of Total Quality Management (TQM)
Quality Goal: Q05 - Reduce Response Time
"""

from typing import Any, Dict, List, Set, Tuple

# 15 Standard Roles: (name, description)
ROLES_LIST: List[Tuple[str, str]] = [
    # 10 Core Administrative & Operational Roles
    ("super_admin", "Global system administrator with unrestricted control"),
    ("hostel_admin", "Hostel Director overseeing multi-hostel operations, policy, and allocations"),
    ("warden", "Chief Warden managing student welfare, discipline, hostel operations, and approvals"),
    ("assistant_warden", "Assistant Warden managing block/floor discipline, evening curfews, and daily logistics"),
    ("hostel_clerk", "Hostel Clerk managing office records, document verification, certificates, and check-in/out registers"),
    ("accountant", "Financial Accountant managing fee structures, invoicing, payment verification, and refunds"),
    ("admission_officer", "Admission Officer handling student applications, document verification, and hostel onboarding"),
    ("security_supervisor", "Security Supervisor managing gate logs, guard shift rosters, incident escalations, and perimeter safety"),
    ("security_guard", "Campus Security Officer executing gate access control, visitor passes, and outpass verification"),
    ("it_admin", "IT Administrator overseeing system health, database backups, audit telemetry, and job leases"),

    # 5 Preserved Operational & Beneficiary Stakeholders
    ("student", "Hostel resident accessing personal room, fee, attendance, and grievance details"),
    ("parent_guardian", "Parent or guardian accessing authorized data of linked wards"),
    ("mess_manager", "Mess manager handling meal planning, subscriptions, and dining hall attendance"),
    ("maintenance_staff", "Facility technician executing repairs and work order updates"),
    ("auditor", "TQM compliance officer with read-only audit and latency telemetry access"),
]

# Role Metadata for Enterprise RBAC and Stakeholder Categorization
ROLE_METADATA: Dict[str, Dict[str, Any]] = {
    "super_admin": {
        "code": "SUPER_ADMIN",
        "category": "Executive / Leadership",
        "title": "Super Administrator",
        "description": "Global system administrator with unrestricted control",
        "is_system": True,
        "is_administrative": True,
    },
    "hostel_admin": {
        "code": "HOSTEL_DIRECTOR",
        "category": "Executive / Leadership",
        "title": "Hostel Director",
        "description": "Hostel Director overseeing multi-hostel operations, policy, and allocations",
        "is_system": True,
        "is_administrative": True,
    },
    "warden": {
        "code": "CHIEF_WARDEN",
        "category": "Operational / Student Life",
        "title": "Chief Warden",
        "description": "Chief Warden managing student welfare, discipline, hostel operations, and approvals",
        "is_system": True,
        "is_administrative": True,
    },
    "assistant_warden": {
        "code": "ASSISTANT_WARDEN",
        "category": "Operational / Student Life",
        "title": "Assistant Warden",
        "description": "Assistant Warden managing block/floor discipline, evening curfews, and daily logistics",
        "is_system": True,
        "is_administrative": True,
    },
    "hostel_clerk": {
        "code": "HOSTEL_CLERK",
        "category": "Administrative / Support",
        "title": "Hostel Clerk",
        "description": "Hostel Clerk managing office records, document verification, certificates, and check-in/out registers",
        "is_system": True,
        "is_administrative": True,
    },
    "accountant": {
        "code": "ACCOUNTANT",
        "category": "Administrative / Support",
        "title": "Financial Accountant",
        "description": "Financial Accountant managing fee structures, invoicing, payment verification, and refunds",
        "is_system": True,
        "is_administrative": True,
    },
    "admission_officer": {
        "code": "ADMISSION_OFFICER",
        "category": "Administrative / Support",
        "title": "Admission Officer",
        "description": "Admission Officer handling student applications, document verification, and hostel onboarding",
        "is_system": True,
        "is_administrative": True,
    },
    "security_supervisor": {
        "code": "SECURITY_SUPERVISOR",
        "category": "Security & Gate",
        "title": "Security Supervisor",
        "description": "Security Supervisor managing gate logs, guard shift rosters, incident escalations, and perimeter safety",
        "is_system": True,
        "is_administrative": True,
    },
    "security_guard": {
        "code": "SECURITY_GUARD",
        "category": "Security & Gate",
        "title": "Security Guard",
        "description": "Campus Security Officer executing gate access control, visitor passes, and outpass verification",
        "is_system": True,
        "is_administrative": True,
    },
    "it_admin": {
        "code": "IT_ADMIN",
        "category": "Technical & Compliance",
        "title": "IT Administrator",
        "description": "IT Administrator overseeing system health, database backups, audit telemetry, and job leases",
        "is_system": True,
        "is_administrative": True,
    },
    "student": {
        "code": "STUDENT",
        "category": "Resident & Beneficiary",
        "title": "Student Resident",
        "description": "Hostel resident accessing personal room, fee, attendance, and grievance details",
        "is_system": True,
        "is_administrative": False,
    },
    "parent_guardian": {
        "code": "PARENT_GUARDIAN",
        "category": "Resident & Beneficiary",
        "title": "Parent / Guardian",
        "description": "Parent or guardian accessing authorized data of linked wards",
        "is_system": True,
        "is_administrative": False,
    },
    "mess_manager": {
        "code": "MESS_MANAGER",
        "category": "Operational / Student Life",
        "title": "Mess Manager",
        "description": "Mess manager handling meal planning, subscriptions, and dining hall attendance",
        "is_system": True,
        "is_administrative": False,
    },
    "maintenance_staff": {
        "code": "MAINTENANCE_STAFF",
        "category": "Operational / Student Life",
        "title": "Maintenance Technician",
        "description": "Facility technician executing repairs and work order updates",
        "is_system": True,
        "is_administrative": False,
    },
    "auditor": {
        "code": "AUDITOR",
        "category": "Technical & Compliance",
        "title": "TQM Compliance Auditor",
        "description": "TQM compliance officer with read-only audit and latency telemetry access",
        "is_system": True,
        "is_administrative": False,
    },
}

# Bidirectional Canonical Role Aliases & Mapping
ROLE_ALIASES: Dict[str, str] = {
    # Canonical Codes to DB Role Names
    "SUPER_ADMIN": "super_admin",
    "HOSTEL_DIRECTOR": "hostel_admin",
    "CHIEF_WARDEN": "warden",
    "ASSISTANT_WARDEN": "assistant_warden",
    "HOSTEL_CLERK": "hostel_clerk",
    "ACCOUNTANT": "accountant",
    "ADMISSION_OFFICER": "admission_officer",
    "SECURITY_SUPERVISOR": "security_supervisor",
    "SECURITY_GUARD": "security_guard",
    "IT_ADMIN": "it_admin",
    "STUDENT": "student",
    "PARENT_GUARDIAN": "parent_guardian",
    "MESS_MANAGER": "mess_manager",
    "MAINTENANCE_STAFF": "maintenance_staff",
    "AUDITOR": "auditor",

    # Direct Names
    "super_admin": "super_admin",
    "hostel_admin": "hostel_admin",
    "hostel_director": "hostel_admin",
    "warden": "warden",
    "chief_warden": "warden",
    "assistant_warden": "assistant_warden",
    "asst_warden": "assistant_warden",
    "hostel_clerk": "hostel_clerk",
    "clerk": "hostel_clerk",
    "accountant": "accountant",
    "admission_officer": "admission_officer",
    "admissions": "admission_officer",
    "security_supervisor": "security_supervisor",
    "sec_supervisor": "security_supervisor",
    "security_guard": "security_guard",
    "security": "security_guard",
    "guard": "security_guard",
    "it_admin": "it_admin",
    "itadmin": "it_admin",
    "student": "student",
    "parent_guardian": "parent_guardian",
    "parent": "parent_guardian",
    "mess_manager": "mess_manager",
    "maintenance_staff": "maintenance_staff",
    "maintenance": "maintenance_staff",
    "auditor": "auditor",
}


def normalize_role_name(role_name: str) -> str:
    """Normalize any role string (code, alias, or name) to authoritative DB role name."""
    if not role_name:
        return ""
    cleaned = role_name.strip()
    return ROLE_ALIASES.get(cleaned, ROLE_ALIASES.get(cleaned.lower(), cleaned.lower()))


# Action verbs supported across granular enterprise permissions
ACTIONS = [
    "CREATE", "READ", "UPDATE", "DELETE",
    "APPROVE", "REJECT", "VERIFY", "ASSIGN",
    "EXPORT", "DOWNLOAD", "CONFIGURE", "MANAGE"
]

# Operational modules
MODULES = [
    "users", "roles", "hostels", "rooms", "students", "allocations",
    "attendance", "leave_requests", "visitors", "complaints",
    "maintenance", "finance", "mess", "inventory", "audit", "settings",
    "clerk", "security", "system"
]

# Bidirectional Permission Normalization (legacy <-> enterprise module.resource.action)
PERMISSION_EQUIVALENCES: Dict[str, str] = {
    # User Management
    "users:create": "users.account.create",
    "users:read": "users.account.read",
    "users:update": "users.account.update",
    "users:delete": "users.account.delete",
    "users:manage": "users.account.manage",

    # Role Management
    "roles:read": "roles.definition.read",
    "roles:manage": "roles.definition.manage",

    # Hostel Facilities
    "hostel:create": "hostels.facility.create",
    "hostel:read": "hostels.facility.read",
    "hostel:update": "hostels.facility.update",
    "hostel:delete": "hostels.facility.delete",
    "hostel:manage": "hostels.facility.manage",

    # Student Profiles
    "student:create": "students.profile.create",
    "student:read": "students.profile.read",
    "student:update": "students.profile.update",
    "student:delete": "students.profile.delete",
    "student:export": "students.profile.export",

    # Room Allocation
    "allocation:create": "allocations.bed.create",
    "allocation:read": "allocations.bed.read",
    "allocation:update": "allocations.bed.update",
    "allocation:delete": "allocations.bed.delete",
    "allocation:export": "allocations.bed.export",

    # Attendance
    "attendance:create": "attendance.record.create",
    "attendance:read": "attendance.record.read",
    "attendance:export": "attendance.record.export",

    # Leave & Outpass
    "leave:create": "leave.request.create",
    "leave:read": "leave.request.read",
    "leave:approve": "leave.request.approve",
    "leave:reject": "leave.request.reject",

    # Visitors
    "visitors:create": "visitors.pass.create",
    "visitors:read": "visitors.pass.read",
    "visitors:update": "visitors.pass.update",

    # Complaints & Grievances
    "complaints:create": "complaints.ticket.create",
    "complaints:read": "complaints.ticket.read",
    "complaints:update": "complaints.ticket.update",
    "complaints:delete": "complaints.ticket.delete",

    # Maintenance
    "maintenance:create": "maintenance.order.create",
    "maintenance:read": "maintenance.order.read",
    "maintenance:update": "maintenance.order.update",

    # Finance
    "finance:create": "finance.invoice.create",
    "finance:read": "finance.invoice.read",
    "finance:update": "finance.payment.update",
    "finance:approve": "finance.refund.approve",
    "finance:export": "finance.report.export",

    # Mess
    "mess:create": "mess.menu.create",
    "mess:read": "mess.menu.read",
    "mess:update": "mess.menu.update",

    # Inventory
    "inventory:create": "inventory.item.create",
    "inventory:read": "inventory.item.read",
    "inventory:update": "inventory.item.update",

    # Audit & Telemetry
    "audit:read": "audit.log.read",
    "audit:export": "audit.log.export",

    # Admissions
    "admissions:read": "admissions.application.read",
    "admissions:approve": "admissions.application.approve",
    "admissions:reject": "admissions.application.reject",

    # Settings
    "settings:manage": "settings.system.manage",
}

# Reverse mapping for bidirectional lookup
_REVERSE_EQUIVALENCES: Dict[str, str] = {v: k for k, v in PERMISSION_EQUIVALENCES.items()}


def get_equivalent_permission(perm: str) -> str:
    """Return canonical or legacy equivalent of given permission name."""
    if perm in PERMISSION_EQUIVALENCES:
        return PERMISSION_EQUIVALENCES[perm]
    if perm in _REVERSE_EQUIVALENCES:
        return _REVERSE_EQUIVALENCES[perm]
    return perm


# Complete Granular Permissions Registry: (name, module, description)
# Contains both legacy module:action and enterprise module.resource.action formats
PERMISSIONS_LIST: List[Tuple[str, str, str]] = [
    # --- User Management ---
    ("users:create", "users", "Create new system accounts"),
    ("users:read", "users", "View user account profiles"),
    ("users:update", "users", "Update user account information"),
    ("users:delete", "users", "Deactivate or delete user accounts"),
    ("users:manage", "users", "Full management of system users"),
    ("users.account.create", "users", "Create new system user accounts"),
    ("users.account.read", "users", "View user account directory and profiles"),
    ("users.account.update", "users", "Update user profile and contact details"),
    ("users.account.delete", "users", "Deactivate or remove user accounts"),
    ("users.account.manage", "users", "Full administrative control of user accounts"),

    # --- Role & Permission Management ---
    ("roles:read", "roles", "View roles and assigned permissions"),
    ("roles:manage", "roles", "Configure role permissions and assignments"),
    ("roles.definition.read", "roles", "Inspect system roles and permission matrices"),
    ("roles.definition.manage", "roles", "Create, update, and configure role assignments"),

    # --- Hostel Facilities & Inventory ---
    ("hostel:create", "hostels", "Create hostels, buildings, and rooms"),
    ("hostel:read", "hostels", "View hostel facilities and room availability"),
    ("hostel:update", "hostels", "Update room status, fees, and capacities"),
    ("hostel:delete", "hostels", "Remove decommissioned rooms"),
    ("hostel:manage", "hostels", "Full control over hostel inventory"),
    ("hostels.facility.create", "hostels", "Create new hostels, blocks, and rooms"),
    ("hostels.facility.read", "hostels", "View hostel buildings, floors, and rooms"),
    ("hostels.facility.update", "hostels", "Modify room capacities, fees, and statuses"),
    ("hostels.facility.delete", "hostels", "Decommission rooms or facility wings"),
    ("hostels.facility.manage", "hostels", "Complete administrative oversight of hostel facilities"),

    # --- Student Profiles ---
    ("student:create", "students", "Register and enroll students"),
    ("student:read", "students", "View student directory and profiles"),
    ("student:update", "students", "Update student contact and academic data"),
    ("student:delete", "students", "Archive or withdraw student records"),
    ("student:export", "students", "Export student lists to CSV"),
    ("students.profile.create", "students", "Enroll and create new student records"),
    ("students.profile.read", "students", "Inspect student enrollment directory"),
    ("students.profile.update", "students", "Update student personal and academic information"),
    ("students.profile.delete", "students", "Archive or deactivate student records"),
    ("students.profile.export", "students", "Export student registries to CSV or PDF"),

    # --- Room Allocations ---
    ("allocation:create", "allocations", "Allot beds to enrolled students"),
    ("allocation:read", "allocations", "View active and historical allocations"),
    ("allocation:update", "allocations", "Update allotment status and fee flags"),
    ("allocation:delete", "allocations", "Vacate and checkout students"),
    ("allocation:export", "allocations", "Export allocation records to CSV"),
    ("allocations.bed.create", "allocations", "Create bed allotment for students"),
    ("allocations.bed.read", "allocations", "View active bed allocations and room rosters"),
    ("allocations.bed.update", "allocations", "Modify bed status and transfer allocations"),
    ("allocations.bed.delete", "allocations", "Process student checkout and vacate bed"),
    ("allocations.bed.export", "allocations", "Export allocation records and room charts"),

    # --- Attendance ---
    ("attendance:create", "attendance", "Record student attendance and curfew"),
    ("attendance:read", "attendance", "View student attendance logs"),
    ("attendance:export", "attendance", "Export attendance reports"),
    ("attendance.record.create", "attendance", "Mark daily evening and curfew attendance"),
    ("attendance.record.read", "attendance", "View attendance registers and history"),
    ("attendance.record.export", "attendance", "Export attendance compliance reports"),

    # --- Leave Requests & Outpasses ---
    ("leave:create", "leave_requests", "Apply for outstation or medical leave"),
    ("leave:read", "leave_requests", "View leave applications"),
    ("leave:approve", "leave_requests", "Approve student leave requests"),
    ("leave:reject", "leave_requests", "Reject student leave requests"),
    ("leave.request.create", "leave_requests", "Submit student leave or outpass requests"),
    ("leave.request.read", "leave_requests", "View leave applications and gate outpasses"),
    ("leave.request.approve", "leave_requests", "Grant authorization for outstation leaves"),
    ("leave.request.reject", "leave_requests", "Deny student leave requests with reason"),

    # --- Visitors ---
    ("visitors:create", "visitors", "Log visitor check-in"),
    ("visitors:read", "visitors", "View visitor logs"),
    ("visitors:update", "visitors", "Record visitor check-out"),
    ("visitors.pass.create", "visitors", "Issue and log visitor gate passes"),
    ("visitors.pass.read", "visitors", "View visitor entry logs and active passes"),
    ("visitors.pass.update", "visitors", "Record visitor departures and checkout times"),

    # --- Complaints & Grievances ---
    ("complaints:create", "complaints", "Submit grievance or repair ticket"),
    ("complaints:read", "complaints", "View complaint tickets"),
    ("complaints:update", "complaints", "Update complaint progress and resolution notes"),
    ("complaints:delete", "complaints", "Cancel or archive invalid complaints"),
    ("complaints.ticket.create", "complaints", "Submit new student grievance or repair ticket"),
    ("complaints.ticket.read", "complaints", "Review complaint tickets and resolution status"),
    ("complaints.ticket.update", "complaints", "Update complaint progress and assign staff"),
    ("complaints.ticket.delete", "complaints", "Archive or close resolved grievance tickets"),

    # --- Maintenance Work Orders ---
    ("maintenance:create", "maintenance", "Log maintenance work orders"),
    ("maintenance:read", "maintenance", "View facility repair orders"),
    ("maintenance:update", "maintenance", "Update maintenance task status and costs"),
    ("maintenance.order.create", "maintenance", "Generate work order for facility repairs"),
    ("maintenance.order.read", "maintenance", "View maintenance schedule and work orders"),
    ("maintenance.order.update", "maintenance", "Update work order completion and expenses"),

    # --- Financial Management ---
    ("finance:create", "finance", "Generate invoices and fee structures"),
    ("finance:read", "finance", "View invoices, fee records, and payments"),
    ("finance:update", "finance", "Record fee payments and receipts"),
    ("finance:approve", "finance", "Approve refunds and fee adjustments"),
    ("finance:export", "finance", "Export financial statements to CSV"),
    ("finance.invoice.create", "finance", "Generate student term invoices and fees"),
    ("finance.invoice.read", "finance", "View student dues, invoices, and payments"),
    ("finance.payment.update", "finance", "Record and verify student fee payments"),
    ("finance.refund.approve", "finance", "Approve student caution deposit refunds"),
    ("finance.report.export", "finance", "Export ledger reports and reconciliation sheets"),

    # --- Mess Operations ---
    ("mess:create", "mess", "Create mess menus and meal slots"),
    ("mess:read", "mess", "View weekly mess menu and subscriptions"),
    ("mess:update", "mess", "Update dining subscriptions and attendance"),
    ("mess.menu.create", "mess", "Configure meal schedules and weekly menus"),
    ("mess.menu.read", "mess", "Inspect daily meal schedules and diet plans"),
    ("mess.menu.update", "mess", "Update dining hall subscriptions and attendance"),

    # --- Physical Inventory ---
    ("inventory:create", "inventory", "Add inventory items and stock"),
    ("inventory:read", "inventory", "Inspect physical supplies and stock levels"),
    ("inventory:update", "inventory", "Issue stock items for maintenance"),
    ("inventory.item.create", "inventory", "Add hostel asset and consumable inventory"),
    ("inventory.item.read", "inventory", "View stock levels and asset allocations"),
    ("inventory.item.update", "inventory", "Issue inventory stock for repair work orders"),

    # --- Audit & Compliance ---
    ("audit:read", "audit", "Inspect immutable audit logs and Q05 telemetry"),
    ("audit:export", "audit", "Export system audit logs"),
    ("audit.log.read", "audit", "Inspect immutable security logs and response times"),
    ("audit.log.export", "audit", "Export TQM compliance logs and latency metrics"),

    # --- Admissions ---
    ("admissions:read", "students", "View prospective admission applications"),
    ("admissions:approve", "students", "Approve student admissions and verify documents"),
    ("admissions:reject", "students", "Reject incomplete admission applications"),
    ("admissions.application.read", "students", "Inspect prospective student applications"),
    ("admissions.application.approve", "students", "Authorize student onboarding and room assignment"),
    ("admissions.application.reject", "students", "Decline invalid or incomplete applications"),

    # --- System Administration ---
    ("settings:manage", "settings", "Configure global system settings"),
    ("settings.system.manage", "settings", "Configure system-wide parameters and timeouts"),

    # --- New Enterprise Stakeholder Capabilities ---
    # Hostel Clerk
    ("clerk.document.verify", "clerk", "Verify submitted physical and uploaded documents"),
    ("clerk.register.manage", "clerk", "Maintain physical check-in and out registers"),
    ("clerk.certificate.issue", "clerk", "Process and issue student bonafide and clearance certificates"),

    # Security Supervisor
    ("security.roster.manage", "security", "Manage security guard shifts and post assignments"),
    ("security.incident.escalate", "security", "Escalate security incidents and discipline infractions"),
    ("security.patrol.log", "security", "Log night perimeter patrols and gate inspections"),

    # IT Administrator
    ("system.health.read", "system", "Inspect API latency, database metrics, and server uptime"),
    ("system.backup.manage", "system", "Trigger on-demand backups and inspect snapshot integrity"),
    ("system.workers.manage", "system", "Monitor background worker locks and task schedules"),
]

# Role to Permission Names Mapping for All 15 Roles
ROLE_PERMISSIONS_MAP: Dict[str, List[str]] = {
    # 1. Super Admin: Unrestricted Global Access
    "super_admin": [p[0] for p in PERMISSIONS_LIST],

    # 2. Hostel Director (hostel_admin): Executive Facility Oversight & Policy
    "hostel_admin": [
        # Legacy
        "users:read", "hostel:manage", "hostel:create", "hostel:read", "hostel:update",
        "student:create", "student:read", "student:update", "student:export",
        "allocation:create", "allocation:read", "allocation:update", "allocation:delete", "allocation:export",
        "attendance:read", "attendance:export", "leave:read", "leave:approve", "leave:reject",
        "complaints:read", "complaints:update", "maintenance:read", "finance:read",
        "audit:read",
        # Enterprise
        "users.account.read", "hostels.facility.manage", "hostels.facility.create",
        "hostels.facility.read", "hostels.facility.update", "students.profile.create",
        "students.profile.read", "students.profile.update", "students.profile.export",
        "allocations.bed.create", "allocations.bed.read", "allocations.bed.update",
        "allocations.bed.delete", "allocations.bed.export", "attendance.record.read",
        "attendance.record.export", "leave.request.read", "leave.request.approve",
        "leave.request.reject", "complaints.ticket.read", "complaints.ticket.update",
        "maintenance.order.read", "finance.invoice.read", "audit.log.read",
        "system.health.read"
    ],

    # 3. Chief Warden (warden): Primary Hostel Operational Head
    "warden": [
        # Legacy
        "hostel:read", "hostel:update",
        "student:read", "student:update", "student:export",
        "allocation:create", "allocation:read", "allocation:update", "allocation:delete",
        "attendance:create", "attendance:read", "attendance:export",
        "leave:read", "leave:approve", "leave:reject",
        "visitors:read", "complaints:read", "complaints:update",
        "maintenance:create", "maintenance:read",
        "finance:read", "mess:read", "audit:read",
        # Enterprise
        "hostels.facility.read", "hostels.facility.update",
        "students.profile.read", "students.profile.update", "students.profile.export",
        "allocations.bed.create", "allocations.bed.read", "allocations.bed.update", "allocations.bed.delete",
        "attendance.record.create", "attendance.record.read", "attendance.record.export",
        "leave.request.read", "leave.request.approve", "leave.request.reject",
        "visitors.pass.read", "complaints.ticket.read", "complaints.ticket.update",
        "maintenance.order.create", "maintenance.order.read",
        "finance.invoice.read", "mess.menu.read", "audit.log.read"
    ],

    # 4. Assistant Warden: Block & Daily Student Life Management
    "assistant_warden": [
        # Legacy
        "hostel:read", "student:read", "allocation:read",
        "attendance:create", "attendance:read",
        "leave:read", "leave:approve", "leave:reject",
        "visitors:create", "visitors:read", "visitors:update",
        "complaints:read", "complaints:update", "maintenance:read",
        # Enterprise
        "hostels.facility.read", "students.profile.read", "allocations.bed.read",
        "attendance.record.create", "attendance.record.read",
        "leave.request.read", "leave.request.approve", "leave.request.reject",
        "visitors.pass.create", "visitors.pass.read", "visitors.pass.update",
        "complaints.ticket.read", "complaints.ticket.update", "maintenance.order.read"
    ],

    # 5. Hostel Clerk: Office Front-Desk, Records & Certificates (NEW)
    "hostel_clerk": [
        # Legacy & Enterprise
        "student:read", "students.profile.read",
        "allocation:read", "allocations.bed.read",
        "attendance:read", "attendance.record.read",
        "visitors:create", "visitors:read", "visitors:update",
        "visitors.pass.create", "visitors.pass.read", "visitors.pass.update",
        "complaints:create", "complaints:read",
        "complaints.ticket.create", "complaints.ticket.read",
        "clerk.document.verify", "clerk.register.manage", "clerk.certificate.issue"
    ],

    # 6. Financial Accountant: Fees, Invoicing & Refunds
    "accountant": [
        # Legacy
        "finance:create", "finance:read", "finance:update", "finance:approve", "finance:export",
        "student:read", "allocation:read", "hostel:read",
        # Enterprise
        "finance.invoice.create", "finance.invoice.read", "finance.payment.update",
        "finance.refund.approve", "finance.report.export",
        "students.profile.read", "allocations.bed.read", "hostels.facility.read"
    ],

    # 7. Admission Officer: Student Registration & Room Allotment Intake
    "admission_officer": [
        # Legacy
        "admissions:read", "admissions:approve", "admissions:reject",
        "student:create", "student:read", "student:update",
        "hostel:read",
        # Enterprise
        "admissions.application.read", "admissions.application.approve", "admissions.application.reject",
        "students.profile.create", "students.profile.read", "students.profile.update",
        "hostels.facility.read"
    ],

    # 8. Security Supervisor: Gate Operations & Guard Oversight (NEW)
    "security_supervisor": [
        # Legacy & Enterprise
        "visitors:create", "visitors:read", "visitors:update",
        "visitors.pass.create", "visitors.pass.read", "visitors.pass.update",
        "attendance:create", "attendance:read",
        "attendance.record.create", "attendance.record.read",
        "leave:read", "leave.request.read",
        "complaints:read", "complaints.ticket.read",
        "security.roster.manage", "security.incident.escalate", "security.patrol.log"
    ],

    # 9. Security Guard: Real-time Gate Access Control
    "security_guard": [
        # Legacy
        "visitors:create", "visitors:read", "visitors:update",
        "attendance:create", "attendance:read",
        "leave:read",
        # Enterprise
        "visitors.pass.create", "visitors.pass.read", "visitors.pass.update",
        "attendance.record.create", "attendance.record.read",
        "leave.request.read"
    ],

    # 10. IT Administrator: System Health, Backups & Audit Telemetry (NEW)
    "it_admin": [
        # Legacy & Enterprise
        "system.health.read", "system.backup.manage", "system.workers.manage",
        "audit:read", "audit:export", "audit.log.read", "audit.log.export",
        "users:read", "users.account.read",
        "roles:read", "roles.definition.read",
        "settings:manage", "settings.system.manage"
    ],

    # 11. Student: Personal Resident Account
    "student": [
        # Legacy
        "student:read", "allocation:read", "attendance:read",
        "leave:create", "leave:read",
        "complaints:create", "complaints:read",
        "finance:read", "mess:read",
        # Enterprise
        "students.profile.read", "allocations.bed.read", "attendance.record.read",
        "leave.request.create", "leave.request.read",
        "complaints.ticket.create", "complaints.ticket.read",
        "finance.invoice.read", "mess.menu.read"
    ],

    # 12. Parent / Guardian: Linked Ward Oversight
    "parent_guardian": [
        # Legacy
        "student:read", "allocation:read", "attendance:read", "finance:read",
        # Enterprise
        "students.profile.read", "allocations.bed.read",
        "attendance.record.read", "finance.invoice.read"
    ],

    # 13. Mess Manager: Dining Hall Menus & Supplies
    "mess_manager": [
        # Legacy
        "mess:create", "mess:read", "mess:update",
        "student:read", "inventory:read", "inventory:update",
        # Enterprise
        "mess.menu.create", "mess.menu.read", "mess.menu.update",
        "students.profile.read", "inventory.item.read", "inventory.item.update"
    ],

    # 14. Maintenance Technician: Repairs & Work Orders
    "maintenance_staff": [
        # Legacy
        "maintenance:read", "maintenance:update",
        "complaints:read", "complaints:update",
        "inventory:read", "inventory:update",
        # Enterprise
        "maintenance.order.read", "maintenance.order.update",
        "complaints.ticket.read", "complaints.ticket.update",
        "inventory.item.read", "inventory.item.update"
    ],

    # 15. TQM Compliance Auditor: Read-Only System Telemetry
    "auditor": [
        # Legacy
        "audit:read", "audit:export",
        "student:read", "student:export",
        "allocation:read", "allocation:export",
        "finance:read", "finance:export",
        "complaints:read", "hostel:read",
        # Enterprise
        "audit.log.read", "audit.log.export",
        "students.profile.read", "students.profile.export",
        "allocations.bed.read", "allocations.bed.export",
        "finance.invoice.read", "finance.report.export",
        "complaints.ticket.read", "hostels.facility.read",
        "system.health.read"
    ]
}
