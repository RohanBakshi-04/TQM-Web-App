"""Role-Based Access Control (RBAC) Data Matrix: 28 Consolidated Dashboard Groups, 17 Departments & Granular Permissions.

Enterprise Architecture Supporting 28 Consolidated Dashboard Groups across 17 Departments,
Individual Role Templates, Trade Specializations (Electrician, Plumber, Carpenter, etc.),
and Complete Poka-Yoke RBAC Isolation.

Course: BBAT104 - Fundamentals of Total Quality Management (TQM)
Quality Goal: Q05 - Reduce Response Time (< 10ms SLA)
"""

from typing import Any, Dict, List, Optional, Set, Tuple

# ---------------------------------------------------------------------------
# 1. Departments Registry (17 Enterprise Departments)
# ---------------------------------------------------------------------------
DEPARTMENTS_LIST: List[Tuple[str, str, str]] = [
    ("EXEC_ADMIN", "Executive Administration", "Leadership, institutional policy, and global operational governance"),
    ("HOSTEL_ADMIN", "Hostel Administration", "Warden governance, floor logistics, and resident administrative operations"),
    ("ADMISSIONS", "Admission and Accommodation", "Student admission, eligibility screening, and room allocations"),
    ("FINANCE", "Finance and Accounts", "Fee structures, billing, payment processing, ledgers, and refunds"),
    ("AUDIT_COMPLIANCE", "Audit and Compliance", "TQM quality metrics, regulatory audits, and operational compliance"),
    ("SECURITY_SAFETY", "Security and Safety", "Campus perimeter, gate security, visitor passes, and CCTV surveillance"),
    ("MESS_FOOD", "Mess and Food Services", "Dining operations, weekly menus, meal subscriptions, and kitchen inventory"),
    ("MAINTENANCE", "Maintenance and Facility Operations", "Infrastructure repairs, work orders, preventive upkeep, and trades"),
    ("HOUSEKEEPING", "Housekeeping and Sanitation", "Hostel hygiene, waste disposal, pest control, and common area upkeep"),
    ("LAUNDRY", "Laundry Management", "Linen washing, resident clothes processing, and laundry facilities"),
    ("MEDICAL_WELFARE", "Medical and Student Welfare", "Infirmary, emergency health services, first aid, and wellness support"),
    ("IT_SYSTEMS", "IT and System Administration", "System backups, database reliability, RBAC telemetry, and cybersecurity"),
    ("INVENTORY_ASSET", "Inventory and Asset Management", "Asset tracking, consumable stock audits, and storekeeping"),
    ("PROCUREMENT_VENDOR", "Procurement and Vendor Management", "Vendor orders, supply requisitions, and vendor evaluations"),
    ("STUDENT_SERVICES", "Student and Resident Services", "Resident student welfare, community life, and parent communications"),
    ("TRANSPORT_RECREATION", "Transport and Recreation", "Campus shuttles, sports facilities, gyms, and recreational spaces"),
    ("GRIEVANCE_PROTECTION", "Grievance and Student Protection", "Anti-ragging, student safety, disciplinary reviews, and dispute resolution"),
]

# ---------------------------------------------------------------------------
# 2. Consolidated Dashboards Registry (28 Dashboard Groups)
# ---------------------------------------------------------------------------
DASHBOARDS_LIST: List[Dict[str, Any]] = [
    {
        "dashboard_id": "DASHBOARD_01",
        "title": "Super Admin Dashboard",
        "department_code": "EXEC_ADMIN",
        "description": "Global administration, user governance, RBAC role management, and audit telemetry",
        "icon": "fa-shield-halved",
        "route": "admin",
        "roles": ["super_admin"],
        "default_role": "super_admin"
    },
    {
        "dashboard_id": "DASHBOARD_02",
        "title": "Executive Management Dashboard",
        "department_code": "EXEC_ADMIN",
        "description": "Hostel Director multi-facility operations, occupancy analytics, and strategic reporting",
        "icon": "fa-hotel",
        "route": "dashboard",
        "roles": ["hostel_admin", "deputy_hostel_director"],
        "default_role": "hostel_admin"
    },
    {
        "dashboard_id": "DASHBOARD_03",
        "title": "Institutional Administration Dashboard",
        "department_code": "EXEC_ADMIN",
        "description": "Registrar and institutional coordination, student welfare policies, and academic calendars",
        "icon": "fa-building-columns",
        "route": "dashboard",
        "roles": ["institutional_admin", "registrar", "dean_student_welfare"],
        "default_role": "institutional_admin"
    },
    {
        "dashboard_id": "DASHBOARD_04",
        "title": "Chief Warden Dashboard",
        "department_code": "HOSTEL_ADMIN",
        "description": "Hostel head: student discipline, welfare, room allocations, leave approvals, and curfews",
        "icon": "fa-user-tie",
        "route": "dashboard",
        "roles": ["warden", "chief_warden", "deputy_chief_warden"],
        "default_role": "warden"
    },
    {
        "dashboard_id": "DASHBOARD_05",
        "title": "Assistant Warden Dashboard",
        "department_code": "HOSTEL_ADMIN",
        "description": "Floor-level roll calls, night inspections, preliminary grievance screening, and gate logs",
        "icon": "fa-user-shield",
        "route": "dashboard",
        "roles": ["assistant_warden", "resident_warden"],
        "default_role": "assistant_warden"
    },
    {
        "dashboard_id": "DASHBOARD_06",
        "title": "Hostel Administration Dashboard",
        "department_code": "HOSTEL_ADMIN",
        "description": "Hostel Clerk office records, verification desks, certificate generation, and registers",
        "icon": "fa-id-card-clip",
        "route": "dashboard",
        "roles": ["hostel_clerk", "hostel_administrator", "hostel_coordinator", "office_assistant", "hostel_receptionist"],
        "default_role": "hostel_clerk"
    },
    {
        "dashboard_id": "DASHBOARD_07",
        "title": "Admission Management Dashboard",
        "department_code": "ADMISSIONS",
        "description": "Applicant intake, eligibility verification, document audits, and onboarding queues",
        "icon": "fa-user-plus",
        "route": "dashboard",
        "roles": ["admission_officer", "admission_assistant", "document_verification_officer"],
        "default_role": "admission_officer"
    },
    {
        "dashboard_id": "DASHBOARD_08",
        "title": "Hostel and Room Allocation Dashboard",
        "department_code": "ADMISSIONS",
        "description": "Poka-Yoke bed allocation, capacity planning, room transfers, and occupancy tracking",
        "icon": "fa-bed",
        "route": "allocations",
        "roles": ["hostel_allotment_officer"],
        "default_role": "hostel_allotment_officer"
    },
    {
        "dashboard_id": "DASHBOARD_09",
        "title": "Finance and Accounts Dashboard",
        "department_code": "FINANCE",
        "description": "Shared finance desk: fee structures, term invoicing, cashier collections, ledgers, and refunds",
        "icon": "fa-calculator",
        "route": "finance",
        "roles": ["accountant", "chief_accountant", "accounts_assistant", "cashier", "fee_collection_officer", "refund_officer", "procurement_finance_officer"],
        "default_role": "accountant"
    },
    {
        "dashboard_id": "DASHBOARD_10",
        "title": "Audit and Compliance Dashboard",
        "department_code": "AUDIT_COMPLIANCE",
        "description": "TQM compliance audit, system telemetry inspection, response time SLAs, and non-conformance logs",
        "icon": "fa-clipboard-check",
        "route": "dashboard",
        "roles": ["auditor", "internal_auditor", "financial_auditor", "compliance_officer", "quality_assurance_officer", "legal_advisor"],
        "default_role": "auditor"
    },
    {
        "dashboard_id": "DASHBOARD_11",
        "title": "Security Command Dashboard",
        "department_code": "SECURITY_SAFETY",
        "description": "Campus security oversight, guard shift rosters, incident management, and escalation handling",
        "icon": "fa-tower-observation",
        "route": "dashboard",
        "roles": ["security_supervisor", "chief_security_officer", "assistant_security_supervisor"],
        "default_role": "security_supervisor"
    },
    {
        "dashboard_id": "DASHBOARD_12",
        "title": "Gate and Security Operations Dashboard",
        "department_code": "SECURITY_SAFETY",
        "description": "Real-time gate logging, visitor passes, biometric verification, and student outpass check-in/out",
        "icon": "fa-person-military-pointing",
        "route": "visitors",
        "roles": ["security_guard", "gate_in_charge", "visitor_management_officer"],
        "default_role": "security_guard"
    },
    {
        "dashboard_id": "DASHBOARD_13",
        "title": "Surveillance and Safety Dashboard",
        "department_code": "SECURITY_SAFETY",
        "description": "CCTV camera status, fire safety equipment, patrol telemetry, and emergency response",
        "icon": "fa-video",
        "route": "dashboard",
        "roles": ["cctv_operator", "fire_safety_officer", "emergency_response_officer", "patrol_officer"],
        "default_role": "cctv_operator"
    },
    {
        "dashboard_id": "DASHBOARD_14",
        "title": "Mess Management Dashboard",
        "department_code": "MESS_FOOD",
        "description": "Weekly menu cycles, meal subscriptions, dining attendance, and food cost accounting",
        "icon": "fa-utensils",
        "route": "mess",
        "roles": ["mess_manager", "assistant_mess_manager", "mess_supervisor", "mess_accountant"],
        "default_role": "mess_manager"
    },
    {
        "dashboard_id": "DASHBOARD_15",
        "title": "Kitchen and Food Operations Dashboard",
        "department_code": "MESS_FOOD",
        "description": "Culinary preparation, daily ration requisitions, food quality inspection, and kitchen hygiene",
        "icon": "fa-bowl-rice",
        "route": "mess",
        "roles": ["head_chef", "chef", "kitchen_assistant", "food_storekeeper", "food_quality_inspector", "nutritionist"],
        "default_role": "head_chef"
    },
    {
        "dashboard_id": "DASHBOARD_16",
        "title": "Maintenance Management Dashboard",
        "department_code": "MAINTENANCE",
        "description": "Work order triage, SLA monitoring, facility asset upkeep, and contractor coordination",
        "icon": "fa-screwdriver-wrench",
        "route": "dashboard",
        "roles": ["maintenance_manager", "maintenance_supervisor", "maintenance_helpdesk"],
        "default_role": "maintenance_manager"
    },
    {
        "dashboard_id": "DASHBOARD_17",
        "title": "Maintenance Technician Dashboard",
        "department_code": "MAINTENANCE",
        "description": "Trade-specific work orders (Electrical, Plumbing, Carpentry, HVAC, Civil, Generator)",
        "icon": "fa-toolbox",
        "route": "dashboard",
        "roles": [
            "maintenance_staff", "maintenance_technician", "electrician", "plumber", "carpenter",
            "hvac_technician", "civil_engineer", "generator_operator", "water_treatment_operator",
            "lift_technician", "fire_equipment_technician"
        ],
        "default_role": "maintenance_staff"
    },
    {
        "dashboard_id": "DASHBOARD_18",
        "title": "Housekeeping and Sanitation Dashboard",
        "department_code": "HOUSEKEEPING",
        "description": "Floor hygiene inspection, cleaning rosters, waste management, and pest control schedules",
        "icon": "fa-broom",
        "route": "dashboard",
        "roles": ["housekeeping_manager", "housekeeping_supervisor", "housekeeping_staff", "sanitation_supervisor", "waste_management_officer", "pest_control_technician", "groundskeeper"],
        "default_role": "housekeeping_staff"
    },
    {
        "dashboard_id": "DASHBOARD_19",
        "title": "Laundry Management Dashboard",
        "department_code": "LAUNDRY",
        "description": "Linen distribution, resident laundry intake, cycle scheduling, and delivery tracking",
        "icon": "fa-shirt",
        "route": "dashboard",
        "roles": ["laundry_manager", "laundry_supervisor", "laundry_staff"],
        "default_role": "laundry_staff"
    },
    {
        "dashboard_id": "DASHBOARD_20",
        "title": "Medical and Welfare Dashboard",
        "department_code": "MEDICAL_WELFARE",
        "description": "Infirmary logs, emergency treatment records, first aid inventory, and resident wellness",
        "icon": "fa-heart-pulse",
        "route": "dashboard",
        "roles": ["chief_medical_officer", "hostel_doctor", "medical_officer", "staff_nurse", "pharmacist", "mental_health_counsellor", "first_aid_officer", "medical_records_admin"],
        "default_role": "medical_officer"
    },
    {
        "dashboard_id": "DASHBOARD_21",
        "title": "IT and System Administration Dashboard",
        "department_code": "IT_SYSTEMS",
        "description": "Server health, SQLite WAL monitoring, background worker leases, backups, and security policies",
        "icon": "fa-server",
        "route": "admin",
        "roles": ["it_admin", "system_administrator", "database_administrator", "network_administrator", "cybersecurity_administrator", "application_administrator", "integration_administrator", "backup_administrator", "helpdesk_support"],
        "default_role": "it_admin"
    },
    {
        "dashboard_id": "DASHBOARD_22",
        "title": "Inventory and Asset Management Dashboard",
        "department_code": "INVENTORY_ASSET",
        "description": "Hostel property, furniture assets, stock reorder levels, and bin-card transactions",
        "icon": "fa-boxes-stacked",
        "route": "inventory",
        "roles": ["inventory_manager", "store_manager", "storekeeper", "asset_manager", "stock_auditor", "receiving_officer"],
        "default_role": "inventory_manager"
    },
    {
        "dashboard_id": "DASHBOARD_23",
        "title": "Procurement and Vendor Management Dashboard",
        "department_code": "PROCUREMENT_VENDOR",
        "description": "Purchase orders, supplier contracts, invoice verification, and vendor ratings",
        "icon": "fa-truck-field",
        "route": "inventory",
        "roles": ["procurement_manager", "purchase_officer", "purchase_assistant", "vendor_manager"],
        "default_role": "procurement_manager"
    },
    {
        "dashboard_id": "DASHBOARD_24",
        "title": "Student Resident Portal",
        "department_code": "STUDENT_SERVICES",
        "description": "Room information, daily attendance check-in, outpass/leave requests, mess menu, and complaints",
        "icon": "fa-graduation-cap",
        "route": "dashboard",
        "roles": ["student", "student_representative", "hostel_prefect", "floor_representative", "room_representative", "student_welfare_representative"],
        "default_role": "student"
    },
    {
        "dashboard_id": "DASHBOARD_25",
        "title": "Parent / Guardian Portal",
        "department_code": "STUDENT_SERVICES",
        "description": "Linked ward status, verified attendance, fee statements, and leave notification tracking",
        "icon": "fa-people-roof",
        "route": "dashboard",
        "roles": ["parent_guardian"],
        "default_role": "parent_guardian"
    },
    {
        "dashboard_id": "DASHBOARD_26",
        "title": "Transport Management Dashboard",
        "department_code": "TRANSPORT_RECREATION",
        "description": "Campus shuttle schedules, route allocations, driver rosters, and vehicle maintenance",
        "icon": "fa-bus",
        "route": "dashboard",
        "roles": ["transport_manager", "transport_supervisor", "transport_driver", "vehicle_maintenance_technician"],
        "default_role": "transport_supervisor"
    },
    {
        "dashboard_id": "DASHBOARD_27",
        "title": "Recreation and Sports Management Dashboard",
        "department_code": "TRANSPORT_RECREATION",
        "description": "Sports facility bookings, gymnasium scheduling, equipment issuance, and hostel tournaments",
        "icon": "fa-table-tennis-paddle-ball",
        "route": "dashboard",
        "roles": ["recreation_manager", "sports_coordinator", "gym_instructor", "facility_coordinator"],
        "default_role": "sports_coordinator"
    },
    {
        "dashboard_id": "DASHBOARD_28",
        "title": "Grievance and Student Protection Dashboard",
        "department_code": "GRIEVANCE_PROTECTION",
        "description": "Anti-ragging helpline, anonymous incident investigations, disciplinary hearings, and safety audits",
        "icon": "fa-handshake-angle",
        "route": "dashboard",
        "roles": ["grievance_officer", "anti_ragging_officer", "disciplinary_committee_member", "risk_management_officer", "health_safety_officer"],
        "default_role": "grievance_officer"
    }
]

# Quick Dashboard and Role Lookups
ROLE_DASHBOARD_MAP: Dict[str, str] = {}
DASHBOARD_ROLE_MAP: Dict[str, List[str]] = {}
for dash in DASHBOARDS_LIST:
    DASHBOARD_ROLE_MAP[dash["dashboard_id"]] = dash["roles"]
    for r in dash["roles"]:
        ROLE_DASHBOARD_MAP[r] = dash["dashboard_id"]

# ---------------------------------------------------------------------------
# 3. Roles Registry (Preserved 15 System Roles + Target Extended Templates)
# ---------------------------------------------------------------------------
ROLES_LIST: List[Tuple[str, str]] = [
    # 10 Core Administrative & Operational Roles (Original 15 System Baseline)
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

    # Enterprise Target Role Templates for 28 Dashboard Groups
    ("institutional_admin", "Institutional Administrator coordinating university registry and student welfare"),
    ("hostel_allotment_officer", "Hostel Allotment Officer managing room and bed allocations"),
    ("cashier", "Financial Cashier handling fee collection counter, receipts, and cash journals"),
    ("cctv_operator", "Surveillance Officer monitoring CCTV feeds and emergency alarms"),
    ("head_chef", "Head Chef overseeing kitchen operations, meal preparation, and food quality"),
    ("maintenance_manager", "Maintenance Manager managing facility work orders and SLAs"),
    ("electrician", "Maintenance Electrician executing electrical repairs and power systems"),
    ("plumber", "Maintenance Plumber executing water and drainage work orders"),
    ("carpenter", "Maintenance Carpenter executing furniture and wooden fixture repairs"),
    ("housekeeping_staff", "Housekeeping Staff maintaining hostel cleanliness and sanitation"),
    ("laundry_staff", "Laundry Staff managing linen and student laundry intake and washing"),
    ("medical_officer", "Hostel Medical Officer providing health consultations and first aid"),
    ("inventory_manager", "Inventory and Asset Manager tracking hostel property and consumables"),
    ("procurement_manager", "Procurement Manager coordinating vendor contracts and requisitions"),
    ("transport_supervisor", "Transport Supervisor managing campus shuttle and bus routes"),
    ("sports_coordinator", "Sports and Recreation Coordinator managing gyms and athletic facilities"),
    ("grievance_officer", "Student Grievance and Anti-Ragging Officer handling complaints and safety"),
]

# Role Metadata for Enterprise RBAC, Department Mapping & Dashboard Scoping
ROLE_METADATA: Dict[str, Dict[str, Any]] = {
    "super_admin": {
        "code": "SUPER_ADMIN",
        "category": "Executive / Leadership",
        "title": "Super Administrator",
        "description": "Global system administrator with unrestricted control",
        "department_code": "EXEC_ADMIN",
        "dashboard_group": "DASHBOARD_01",
        "is_system": True,
        "is_administrative": True,
    },
    "hostel_admin": {
        "code": "HOSTEL_DIRECTOR",
        "category": "Executive / Leadership",
        "title": "Hostel Director",
        "description": "Hostel Director overseeing multi-hostel operations, policy, and allocations",
        "department_code": "EXEC_ADMIN",
        "dashboard_group": "DASHBOARD_02",
        "is_system": True,
        "is_administrative": True,
    },
    "institutional_admin": {
        "code": "INSTITUTIONAL_ADMIN",
        "category": "Executive / Leadership",
        "title": "Institutional Administrator",
        "description": "Institutional Administrator coordinating university registry and student welfare",
        "department_code": "EXEC_ADMIN",
        "dashboard_group": "DASHBOARD_03",
        "is_system": True,
        "is_administrative": True,
    },
    "warden": {
        "code": "CHIEF_WARDEN",
        "category": "Operational / Student Life",
        "title": "Chief Warden",
        "description": "Chief Warden managing student welfare, discipline, hostel operations, and approvals",
        "department_code": "HOSTEL_ADMIN",
        "dashboard_group": "DASHBOARD_04",
        "is_system": True,
        "is_administrative": True,
    },
    "assistant_warden": {
        "code": "ASSISTANT_WARDEN",
        "category": "Operational / Student Life",
        "title": "Assistant Warden",
        "description": "Assistant Warden managing block/floor discipline, evening curfews, and daily logistics",
        "department_code": "HOSTEL_ADMIN",
        "dashboard_group": "DASHBOARD_05",
        "is_system": True,
        "is_administrative": True,
    },
    "hostel_clerk": {
        "code": "HOSTEL_CLERK",
        "category": "Administrative / Support",
        "title": "Hostel Clerk",
        "description": "Hostel Clerk managing office records, document verification, certificates, and check-in/out registers",
        "department_code": "HOSTEL_ADMIN",
        "dashboard_group": "DASHBOARD_06",
        "is_system": True,
        "is_administrative": True,
    },
    "admission_officer": {
        "code": "ADMISSION_OFFICER",
        "category": "Administrative / Support",
        "title": "Admission Officer",
        "description": "Admission Officer handling student applications, document verification, and hostel onboarding",
        "department_code": "ADMISSIONS",
        "dashboard_group": "DASHBOARD_07",
        "is_system": True,
        "is_administrative": True,
    },
    "hostel_allotment_officer": {
        "code": "HOSTEL_ALLOTMENT_OFFICER",
        "category": "Administrative / Support",
        "title": "Hostel Allotment Officer",
        "description": "Hostel Allotment Officer managing room and bed allocations",
        "department_code": "ADMISSIONS",
        "dashboard_group": "DASHBOARD_08",
        "is_system": True,
        "is_administrative": True,
    },
    "accountant": {
        "code": "ACCOUNTANT",
        "category": "Administrative / Support",
        "title": "Financial Accountant",
        "description": "Financial Accountant managing fee structures, invoicing, payment verification, and refunds",
        "department_code": "FINANCE",
        "dashboard_group": "DASHBOARD_09",
        "is_system": True,
        "is_administrative": True,
    },
    "cashier": {
        "code": "CASHIER",
        "category": "Administrative / Support",
        "title": "Financial Cashier",
        "description": "Counter fee collection and receipt generation",
        "department_code": "FINANCE",
        "dashboard_group": "DASHBOARD_09",
        "is_system": True,
        "is_administrative": True,
    },
    "auditor": {
        "code": "AUDITOR",
        "category": "Technical & Compliance",
        "title": "TQM Compliance Auditor",
        "description": "TQM compliance officer with read-only audit and latency telemetry access",
        "department_code": "AUDIT_COMPLIANCE",
        "dashboard_group": "DASHBOARD_10",
        "is_system": True,
        "is_administrative": False,
    },
    "security_supervisor": {
        "code": "SECURITY_SUPERVISOR",
        "category": "Security & Gate",
        "title": "Security Supervisor",
        "description": "Security Supervisor managing gate logs, guard shift rosters, incident escalations, and perimeter safety",
        "department_code": "SECURITY_SAFETY",
        "dashboard_group": "DASHBOARD_11",
        "is_system": True,
        "is_administrative": True,
    },
    "security_guard": {
        "code": "SECURITY_GUARD",
        "category": "Security & Gate",
        "title": "Security Guard",
        "description": "Campus Security Officer executing gate access control, visitor passes, and outpass verification",
        "department_code": "SECURITY_SAFETY",
        "dashboard_group": "DASHBOARD_12",
        "is_system": True,
        "is_administrative": True,
    },
    "cctv_operator": {
        "code": "CCTV_OPERATOR",
        "category": "Security & Gate",
        "title": "Surveillance Operator",
        "description": "Surveillance Officer monitoring CCTV feeds and emergency alarms",
        "department_code": "SECURITY_SAFETY",
        "dashboard_group": "DASHBOARD_13",
        "is_system": True,
        "is_administrative": False,
    },
    "mess_manager": {
        "code": "MESS_MANAGER",
        "category": "Operational / Student Life",
        "title": "Mess Manager",
        "description": "Mess manager handling meal planning, subscriptions, and dining hall attendance",
        "department_code": "MESS_FOOD",
        "dashboard_group": "DASHBOARD_14",
        "is_system": True,
        "is_administrative": False,
    },
    "head_chef": {
        "code": "HEAD_CHEF",
        "category": "Operational / Food Service",
        "title": "Head Chef",
        "description": "Head Chef overseeing kitchen operations, meal preparation, and food quality",
        "department_code": "MESS_FOOD",
        "dashboard_group": "DASHBOARD_15",
        "is_system": True,
        "is_administrative": False,
    },
    "maintenance_manager": {
        "code": "MAINTENANCE_MANAGER",
        "category": "Operational / Facility",
        "title": "Maintenance Manager",
        "description": "Maintenance Manager managing facility work orders and SLAs",
        "department_code": "MAINTENANCE",
        "dashboard_group": "DASHBOARD_16",
        "is_system": True,
        "is_administrative": True,
    },
    "maintenance_staff": {
        "code": "MAINTENANCE_STAFF",
        "category": "Operational / Student Life",
        "title": "Maintenance Technician",
        "description": "Facility technician executing repairs and work order updates",
        "department_code": "MAINTENANCE",
        "dashboard_group": "DASHBOARD_17",
        "trade": "general",
        "is_system": True,
        "is_administrative": False,
    },
    "electrician": {
        "code": "ELECTRICIAN",
        "category": "Operational / Facility",
        "title": "Maintenance Electrician",
        "description": "Maintenance Electrician executing electrical repairs and power systems",
        "department_code": "MAINTENANCE",
        "dashboard_group": "DASHBOARD_17",
        "trade": "electrical",
        "is_system": True,
        "is_administrative": False,
    },
    "plumber": {
        "code": "PLUMBER",
        "category": "Operational / Facility",
        "title": "Maintenance Plumber",
        "description": "Maintenance Plumber executing water and drainage work orders",
        "department_code": "MAINTENANCE",
        "dashboard_group": "DASHBOARD_17",
        "trade": "plumbing",
        "is_system": True,
        "is_administrative": False,
    },
    "carpenter": {
        "code": "CARPENTER",
        "category": "Operational / Facility",
        "title": "Maintenance Carpenter",
        "description": "Maintenance Carpenter executing furniture and wooden fixture repairs",
        "department_code": "MAINTENANCE",
        "dashboard_group": "DASHBOARD_17",
        "trade": "carpentry",
        "is_system": True,
        "is_administrative": False,
    },
    "housekeeping_staff": {
        "code": "HOUSEKEEPING_STAFF",
        "category": "Operational / Facility",
        "title": "Housekeeping Staff",
        "description": "Housekeeping Staff maintaining hostel cleanliness and sanitation",
        "department_code": "HOUSEKEEPING",
        "dashboard_group": "DASHBOARD_18",
        "is_system": True,
        "is_administrative": False,
    },
    "laundry_staff": {
        "code": "LAUNDRY_STAFF",
        "category": "Operational / Facility",
        "title": "Laundry Staff",
        "description": "Laundry Staff managing linen and student laundry intake and washing",
        "department_code": "LAUNDRY",
        "dashboard_group": "DASHBOARD_19",
        "is_system": True,
        "is_administrative": False,
    },
    "medical_officer": {
        "code": "MEDICAL_OFFICER",
        "category": "Student Welfare / Health",
        "title": "Medical Officer",
        "description": "Hostel Medical Officer providing health consultations and first aid",
        "department_code": "MEDICAL_WELFARE",
        "dashboard_group": "DASHBOARD_20",
        "is_system": True,
        "is_administrative": False,
    },
    "it_admin": {
        "code": "IT_ADMIN",
        "category": "Technical & Compliance",
        "title": "IT Administrator",
        "description": "IT Administrator overseeing system health, database backups, audit telemetry, and job leases",
        "department_code": "IT_SYSTEMS",
        "dashboard_group": "DASHBOARD_21",
        "is_system": True,
        "is_administrative": True,
    },
    "inventory_manager": {
        "code": "INVENTORY_MANAGER",
        "category": "Operational / Asset",
        "title": "Inventory Manager",
        "description": "Inventory and Asset Manager tracking hostel property and consumables",
        "department_code": "INVENTORY_ASSET",
        "dashboard_group": "DASHBOARD_22",
        "is_system": True,
        "is_administrative": True,
    },
    "procurement_manager": {
        "code": "PROCUREMENT_MANAGER",
        "category": "Operational / Asset",
        "title": "Procurement Manager",
        "description": "Procurement Manager coordinating vendor contracts and requisitions",
        "department_code": "PROCUREMENT_VENDOR",
        "dashboard_group": "DASHBOARD_23",
        "is_system": True,
        "is_administrative": True,
    },
    "student": {
        "code": "STUDENT",
        "category": "Resident & Beneficiary",
        "title": "Student Resident",
        "description": "Hostel resident accessing personal room, fee, attendance, and grievance details",
        "department_code": "STUDENT_SERVICES",
        "dashboard_group": "DASHBOARD_24",
        "is_system": True,
        "is_administrative": False,
    },
    "parent_guardian": {
        "code": "PARENT_GUARDIAN",
        "category": "Resident & Beneficiary",
        "title": "Parent / Guardian",
        "description": "Parent or guardian accessing authorized data of linked wards",
        "department_code": "STUDENT_SERVICES",
        "dashboard_group": "DASHBOARD_25",
        "is_system": True,
        "is_administrative": False,
    },
    "transport_supervisor": {
        "code": "TRANSPORT_SUPERVISOR",
        "category": "Operational / Logistics",
        "title": "Transport Supervisor",
        "description": "Transport Supervisor managing campus shuttle and bus routes",
        "department_code": "TRANSPORT_RECREATION",
        "dashboard_group": "DASHBOARD_26",
        "is_system": True,
        "is_administrative": False,
    },
    "sports_coordinator": {
        "code": "SPORTS_COORDINATOR",
        "category": "Student Welfare / Recreation",
        "title": "Sports & Recreation Coordinator",
        "description": "Sports and Recreation Coordinator managing gyms and athletic facilities",
        "department_code": "TRANSPORT_RECREATION",
        "dashboard_group": "DASHBOARD_27",
        "is_system": True,
        "is_administrative": False,
    },
    "grievance_officer": {
        "code": "GRIEVANCE_OFFICER",
        "category": "Student Welfare / Protection",
        "title": "Grievance & Protection Officer",
        "description": "Student Grievance and Anti-Ragging Officer handling complaints and safety",
        "department_code": "GRIEVANCE_PROTECTION",
        "dashboard_group": "DASHBOARD_28",
        "is_system": True,
        "is_administrative": True,
    },
}

# Bidirectional Canonical Role Aliases & Mapping
ROLE_ALIASES: Dict[str, str] = {
    # Canonical Codes to DB Role Names
    "SUPER_ADMIN": "super_admin",
    "HOSTEL_DIRECTOR": "hostel_admin",
    "DEPUTY_HOSTEL_DIRECTOR": "hostel_admin",
    "INSTITUTIONAL_ADMIN": "institutional_admin",
    "REGISTRAR": "institutional_admin",
    "DEAN_STUDENT_WELFARE": "institutional_admin",
    "CHIEF_WARDEN": "warden",
    "DEPUTY_CHIEF_WARDEN": "warden",
    "ASSISTANT_WARDEN": "assistant_warden",
    "RESIDENT_WARDEN": "assistant_warden",
    "HOSTEL_CLERK": "hostel_clerk",
    "HOSTEL_ADMINISTRATOR": "hostel_clerk",
    "HOSTEL_COORDINATOR": "hostel_clerk",
    "OFFICE_ASSISTANT": "hostel_clerk",
    "HOSTEL_RECEPTIONIST": "hostel_clerk",
    "ACCOUNTANT": "accountant",
    "CHIEF_ACCOUNTANT": "accountant",
    "ACCOUNTS_ASSISTANT": "accountant",
    "CASHIER": "cashier",
    "FEE_COLLECTION_OFFICER": "accountant",
    "REFUND_OFFICER": "accountant",
    "PROCUREMENT_FINANCE_OFFICER": "accountant",
    "ADMISSION_OFFICER": "admission_officer",
    "ADMISSION_ASSISTANT": "admission_officer",
    "DOCUMENT_VERIFICATION_OFFICER": "admission_officer",
    "HOSTEL_ALLOTMENT_OFFICER": "hostel_allotment_officer",
    "SECURITY_SUPERVISOR": "security_supervisor",
    "CHIEF_SECURITY_OFFICER": "security_supervisor",
    "ASSISTANT_SECURITY_SUPERVISOR": "security_supervisor",
    "SECURITY_GUARD": "security_guard",
    "GATE_IN_CHARGE": "security_guard",
    "VISITOR_MANAGEMENT_OFFICER": "security_guard",
    "CCTV_OPERATOR": "cctv_operator",
    "FIRE_SAFETY_OFFICER": "cctv_operator",
    "EMERGENCY_RESPONSE_OFFICER": "cctv_operator",
    "PATROL_OFFICER": "cctv_operator",
    "IT_ADMIN": "it_admin",
    "SYSTEM_ADMINISTRATOR": "it_admin",
    "DATABASE_ADMINISTRATOR": "it_admin",
    "NETWORK_ADMINISTRATOR": "it_admin",
    "CYBERSECURITY_ADMINISTRATOR": "it_admin",
    "APPLICATION_ADMINISTRATOR": "it_admin",
    "INTEGRATION_ADMINISTRATOR": "it_admin",
    "BACKUP_ADMINISTRATOR": "it_admin",
    "HELPDESK_SUPPORT": "it_admin",
    "STUDENT": "student",
    "STUDENT_REPRESENTATIVE": "student",
    "HOSTEL_PREFECT": "student",
    "FLOOR_REPRESENTATIVE": "student",
    "ROOM_REPRESENTATIVE": "student",
    "STUDENT_WELFARE_REPRESENTATIVE": "student",
    "PARENT_GUARDIAN": "parent_guardian",
    "MESS_MANAGER": "mess_manager",
    "ASSISTANT_MESS_MANAGER": "mess_manager",
    "MESS_SUPERVISOR": "mess_manager",
    "MESS_ACCOUNTANT": "mess_manager",
    "HEAD_CHEF": "head_chef",
    "CHEF": "head_chef",
    "KITCHEN_ASSISTANT": "head_chef",
    "FOOD_STOREKEEPER": "head_chef",
    "FOOD_QUALITY_INSPECTOR": "head_chef",
    "NUTRITIONIST": "head_chef",
    "MAINTENANCE_MANAGER": "maintenance_manager",
    "MAINTENANCE_SUPERVISOR": "maintenance_manager",
    "MAINTENANCE_HELPDESK": "maintenance_manager",
    "MAINTENANCE_STAFF": "maintenance_staff",
    "MAINTENANCE_TECHNICIAN": "maintenance_staff",
    "ELECTRICIAN": "electrician",
    "PLUMBER": "plumber",
    "CARPENTER": "carpenter",
    "HVAC_TECHNICIAN": "electrician",
    "CIVIL_ENGINEER": "maintenance_manager",
    "GENERATOR_OPERATOR": "electrician",
    "WATER_TREATMENT_OPERATOR": "plumber",
    "LIFT_TECHNICIAN": "electrician",
    "FIRE_EQUIPMENT_TECHNICIAN": "cctv_operator",
    "HOUSEKEEPING_MANAGER": "housekeeping_staff",
    "HOUSEKEEPING_SUPERVISOR": "housekeeping_staff",
    "HOUSEKEEPING_STAFF": "housekeeping_staff",
    "SANITATION_SUPERVISOR": "housekeeping_staff",
    "WASTE_MANAGEMENT_OFFICER": "housekeeping_staff",
    "PEST_CONTROL_TECHNICIAN": "housekeeping_staff",
    "GROUNDSKEEPER": "housekeeping_staff",
    "LAUNDRY_MANAGER": "laundry_staff",
    "LAUNDRY_SUPERVISOR": "laundry_staff",
    "LAUNDRY_STAFF": "laundry_staff",
    "CHIEF_MEDICAL_OFFICER": "medical_officer",
    "HOSTEL_DOCTOR": "medical_officer",
    "MEDICAL_OFFICER": "medical_officer",
    "STAFF_NURSE": "medical_officer",
    "PHARMACIST": "medical_officer",
    "MENTAL_HEALTH_COUNSELLOR": "medical_officer",
    "FIRST_AID_OFFICER": "medical_officer",
    "MEDICAL_RECORDS_ADMIN": "medical_officer",
    "INVENTORY_MANAGER": "inventory_manager",
    "STORE_MANAGER": "inventory_manager",
    "STOREKEEPER": "inventory_manager",
    "ASSET_MANAGER": "inventory_manager",
    "STOCK_AUDITOR": "inventory_manager",
    "RECEIVING_OFFICER": "inventory_manager",
    "PROCUREMENT_MANAGER": "procurement_manager",
    "PURCHASE_OFFICER": "procurement_manager",
    "PURCHASE_ASSISTANT": "procurement_manager",
    "VENDOR_MANAGER": "procurement_manager",
    "TRANSPORT_MANAGER": "transport_supervisor",
    "TRANSPORT_SUPERVISOR": "transport_supervisor",
    "TRANSPORT_DRIVER": "transport_supervisor",
    "VEHICLE_MAINTENANCE_TECHNICIAN": "transport_supervisor",
    "RECREATION_MANAGER": "sports_coordinator",
    "SPORTS_COORDINATOR": "sports_coordinator",
    "GYM_INSTRUCTOR": "sports_coordinator",
    "FACILITY_COORDINATOR": "sports_coordinator",
    "GRIEVANCE_OFFICER": "grievance_officer",
    "ANTI_RAGGING_OFFICER": "grievance_officer",
    "DISCIPLINARY_COMMITTEE_MEMBER": "grievance_officer",
    "RISK_MANAGEMENT_OFFICER": "grievance_officer",
    "HEALTH_SAFETY_OFFICER": "grievance_officer",
    "AUDITOR": "auditor",
    "INTERNAL_AUDITOR": "auditor",
    "FINANCIAL_AUDITOR": "auditor",
    "COMPLIANCE_OFFICER": "auditor",
    "QUALITY_ASSURANCE_OFFICER": "auditor",
    "LEGAL_ADVISOR": "auditor",

    # Direct Lowercase Names
    "super_admin": "super_admin",
    "hostel_admin": "hostel_admin",
    "hostel_director": "hostel_admin",
    "institutional_admin": "institutional_admin",
    "warden": "warden",
    "chief_warden": "warden",
    "assistant_warden": "assistant_warden",
    "asst_warden": "assistant_warden",
    "hostel_clerk": "hostel_clerk",
    "clerk": "hostel_clerk",
    "accountant": "accountant",
    "cashier": "cashier",
    "admission_officer": "admission_officer",
    "admissions": "admission_officer",
    "hostel_allotment_officer": "hostel_allotment_officer",
    "security_supervisor": "security_supervisor",
    "sec_supervisor": "security_supervisor",
    "security_guard": "security_guard",
    "security": "security_guard",
    "guard": "security_guard",
    "cctv_operator": "cctv_operator",
    "it_admin": "it_admin",
    "itadmin": "it_admin",
    "student": "student",
    "parent_guardian": "parent_guardian",
    "parent": "parent_guardian",
    "mess_manager": "mess_manager",
    "head_chef": "head_chef",
    "maintenance_manager": "maintenance_manager",
    "maintenance_staff": "maintenance_staff",
    "maintenance": "maintenance_staff",
    "electrician": "electrician",
    "plumber": "plumber",
    "carpenter": "carpenter",
    "housekeeping_staff": "housekeeping_staff",
    "laundry_staff": "laundry_staff",
    "medical_officer": "medical_officer",
    "inventory_manager": "inventory_manager",
    "procurement_manager": "procurement_manager",
    "transport_supervisor": "transport_supervisor",
    "sports_coordinator": "sports_coordinator",
    "grievance_officer": "grievance_officer",
    "auditor": "auditor",
}


def normalize_role_name(role_name: str) -> str:
    """Normalize any role string (code, alias, or name) to authoritative DB role name."""
    if not role_name:
        return ""
    cleaned = role_name.strip()
    return ROLE_ALIASES.get(cleaned, ROLE_ALIASES.get(cleaned.lower(), cleaned.lower()))


def get_dashboard_for_role(role_name: str) -> Optional[Dict[str, Any]]:
    """Return canonical dashboard definition for a given role name or alias."""
    norm = normalize_role_name(role_name)
    dash_id = ROLE_DASHBOARD_MAP.get(norm, "DASHBOARD_24")
    for d in DASHBOARDS_LIST:
        if d["dashboard_id"] == dash_id:
            return d
    return None


def get_department_for_role(role_name: str) -> Optional[Tuple[str, str, str]]:
    """Return (code, name, description) of department for a given role name or alias."""
    d = get_dashboard_for_role(role_name)
    if not d:
        return None
    dept_code = d.get("department_code")
    for dept in DEPARTMENTS_LIST:
        if dept[0] == dept_code:
            return dept
    return None


# Action verbs supported across granular enterprise permissions
ACTIONS = [
    "CREATE", "READ", "UPDATE", "DELETE",
    "APPROVE", "REJECT", "VERIFY", "ASSIGN",
    "EXPORT", "DOWNLOAD", "CONFIGURE", "MANAGE",
    "RESOLVE", "OPERATE", "PRESCRIBE", "PROCESS"
]

# Operational modules
MODULES = [
    "users", "roles", "hostels", "rooms", "students", "allocations",
    "attendance", "leave_requests", "visitors", "complaints",
    "maintenance", "finance", "mess", "inventory", "audit", "settings",
    "clerk", "security", "system", "departments", "dashboards",
    "surveillance", "kitchen", "housekeeping", "laundry", "medical",
    "transport", "recreation", "grievances"
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

    # SA-02: Infrastructure, Institution, Campus & Facility Equivalences
    "hostels:read": "hostels.facility.read",
    "hostels:create": "hostels.facility.create",
    "hostels:update": "hostels.facility.update",
    "hostels:delete": "hostels.facility.delete",
    "hostels:manage": "hostels.facility.manage",
    "institution:read": "institutions.profile.read",
    "institution:update": "institutions.profile.update",
    "institution:manage": "institutions.profile.update",
    "campuses:read": "campuses.facility.read",
    "campuses:create": "campuses.facility.create",
    "campuses:update": "campuses.facility.update",
    "campuses:delete": "campuses.facility.delete",
    "campuses:manage": "campuses.facility.manage",
    "infrastructure:read": "infrastructure.hierarchy.read",
    "infrastructure:manage": "infrastructure.capacity.manage",
    "infrastructure:import": "infrastructure.data.import",
    "infrastructure:export": "infrastructure.data.export",
    "buildings:read": "hostels.facility.read",
    "buildings:create": "hostels.facility.manage",
    "buildings:update": "hostels.facility.manage",
    "buildings:delete": "hostels.facility.manage",
    "rooms:read": "allocations.bed.read",
    "rooms:manage": "infrastructure.capacity.manage",
    "beds:manage": "allocations.bed.update",
    "blocks:manage": "infrastructure.capacity.manage",
    "floors:manage": "infrastructure.capacity.manage",

    # Departments & Dashboards
    "departments:read": "departments.structure.read",
    "departments:manage": "departments.structure.manage",
    "dashboards:read": "dashboards.group.read",
    "dashboards:manage": "dashboards.group.manage",

    # Specialized Operations
    "surveillance:read": "surveillance.feed.read",
    "surveillance:operate": "surveillance.feed.operate",
    "kitchen:read": "kitchen.ration.read",
    "kitchen:manage": "kitchen.ration.manage",
    "housekeeping:read": "housekeeping.task.read",
    "housekeeping:complete": "housekeeping.task.complete",
    "laundry:read": "laundry.batch.read",
    "laundry:process": "laundry.batch.process",
    "medical:read": "medical.record.read",
    "medical:prescribe": "medical.record.prescribe",
    "transport:read": "transport.schedule.read",
    "transport:operate": "transport.schedule.operate",
    "recreation:read": "recreation.facility.read",
    "recreation:manage": "recreation.facility.manage",
    "grievances:read": "grievances.incident.read",
    "grievances:resolve": "grievances.incident.resolve",
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
    ("roles:manage", "roles", "Create, modify, and delete roles"),
    ("roles.definition.read", "roles", "Inspect role definitions and permission mappings"),
    ("roles.definition.manage", "roles", "Create and assign role permission definitions"),

    # --- Hostel Facility Management ---
    ("hostel:create", "hostels", "Create new hostel blocks and facilities"),
    ("hostel:read", "hostels", "View hostel facility details"),
    ("hostel:update", "hostels", "Update hostel attributes and capacities"),
    ("hostel:delete", "hostels", "Decommission hostel blocks"),
    ("hostel:manage", "hostels", "Comprehensive hostel administration"),
    ("hostels.facility.create", "hostels", "Create new hostel buildings and blocks"),
    ("hostels.facility.read", "hostels", "Inspect hostel facility capacities and layouts"),
    ("hostels.facility.update", "hostels", "Update hostel facility parameters and status"),
    ("hostels.facility.delete", "hostels", "Decommission hostel blocks and structures"),
    ("hostels.facility.manage", "hostels", "Full authority over hostel facility entities"),

    # --- SA-02: Institution Governance ---
    ("institution:read", "institution", "View university institutional profile and configurations"),
    ("institution:update", "institution", "Modify university institutional profile and settings"),
    ("institution:manage", "institution", "Full administrative control over institutional governance"),
    ("institutions.profile.read", "institution", "View detailed institutional profile and legal metadata"),
    ("institutions.profile.update", "institution", "Update institutional contact, address, and branding"),
    ("institutions.config.update", "institution", "Configure institutional timezone, currency, and academic calendar"),

    # --- SA-02: Campus Management ---
    ("campuses:create", "campuses", "Establish new university campus locations"),
    ("campuses:read", "campuses", "Inspect campus details and infrastructure hierarchy"),
    ("campuses:update", "campuses", "Update campus parameters and operational status"),
    ("campuses:delete", "campuses", "Decommission campus entities"),
    ("campuses:manage", "campuses", "Full administrative governance over campus entities"),
    ("campuses.facility.create", "campuses", "Create new university campus locations"),
    ("campuses.facility.read", "campuses", "View campus details and infrastructure rosters"),
    ("campuses.facility.update", "campuses", "Update campus parameters and administrator assignments"),
    ("campuses.facility.delete", "campuses", "Decommission campus locations"),
    ("campuses.facility.manage", "campuses", "Complete administrative control over campus infrastructure"),

    # --- SA-02: Multi-Tier Infrastructure Hierarchy, Blocks & Capacity ---
    ("infrastructure:read", "infrastructure", "Explore complete multi-tier infrastructure hierarchy"),
    ("infrastructure:manage", "infrastructure", "Comprehensive infrastructure management across all facilities"),
    ("infrastructure:import", "infrastructure", "Execute bulk CSV/JSON infrastructure imports"),
    ("infrastructure:export", "infrastructure", "Export campus and hostel infrastructure inventories"),
    ("infrastructure.hierarchy.read", "infrastructure", "View multi-tier hierarchical infrastructure tree"),
    ("infrastructure.capacity.read", "infrastructure", "Inspect capacity, occupancy, and availability analytics"),
    ("infrastructure.capacity.manage", "infrastructure", "Adjust physical room capacities and operational thresholds"),
    ("infrastructure.data.import", "infrastructure", "Bulk import infrastructure records with rollback"),
    ("infrastructure.data.export", "infrastructure", "Export verified infrastructure datasets"),
    ("blocks:manage", "blocks", "Manage hostel residential and academic blocks"),
    ("floors:manage", "floors", "Manage building floor configurations"),
    ("rooms:manage", "rooms", "Manage room inventory, occupancy categories, and maintenance"),
    ("beds:manage", "beds", "Manage bed availability, operational states, and maintenance locks"),

    # --- Student Profiles & Records ---
    ("student:create", "students", "Register new student profiles"),
    ("student:read", "students", "View student records and directory"),
    ("student:update", "students", "Update student personal and academic info"),
    ("student:delete", "students", "Archive or remove student records"),
    ("student:export", "students", "Export student roster datasets"),
    ("students.profile.create", "students", "Onboard and register student records"),
    ("students.profile.read", "students", "View detailed student academic and residential profiles"),
    ("students.profile.update", "students", "Update student demographic and contact information"),
    ("students.profile.delete", "students", "Archive student records upon graduation or exit"),
    ("students.profile.export", "students", "Export student census and profile rosters"),

    # --- Poka-Yoke Room & Bed Allocations ---
    ("allocation:create", "allocations", "Allocate beds to students"),
    ("allocation:read", "allocations", "View bed allocation records"),
    ("allocation:update", "allocations", "Transfer and update room allocations"),
    ("allocation:delete", "allocations", "Vacate and terminate room allocations"),
    ("allocation:export", "allocations", "Export bed occupancy data"),
    ("allocations.bed.create", "allocations", "Execute atomic Poka-Yoke bed allocation"),
    ("allocations.bed.read", "allocations", "Inspect bed occupancy status and room rosters"),
    ("allocations.bed.update", "allocations", "Perform verified bed transfers between rooms"),
    ("allocations.bed.delete", "allocations", "Process student checkout and release occupied bed"),
    ("allocations.bed.export", "allocations", "Export bed allocation logs and occupancy reports"),

    # --- Attendance Management ---
    ("attendance:create", "attendance", "Mark daily resident attendance"),
    ("attendance:read", "attendance", "View attendance records and registers"),
    ("attendance:export", "attendance", "Export attendance audit data"),
    ("attendance.record.create", "attendance", "Record daily floor and curfew attendance logs"),
    ("attendance.record.read", "attendance", "View attendance rosters and percentage analytics"),
    ("attendance.record.export", "attendance", "Export compliance attendance sheets"),

    # --- Leave & Outpass Management ---
    ("leave:create", "leave_requests", "Submit leave applications"),
    ("leave:read", "leave_requests", "View leave applications"),
    ("leave:approve", "leave_requests", "Approve student leave requests"),
    ("leave:reject", "leave_requests", "Reject student leave requests"),
    ("leave.request.create", "leave_requests", "Submit student leave or night outpass requests"),
    ("leave.request.read", "leave_requests", "Inspect pending and historical leave requests"),
    ("leave.request.approve", "leave_requests", "Grant authorization for student leave outpass"),
    ("leave.request.reject", "leave_requests", "Decline leave requests with audit rationale"),

    # --- Visitor Access Control ---
    ("visitors:create", "visitors", "Register incoming visitors"),
    ("visitors:read", "visitors", "View active and past visitor logs"),
    ("visitors:update", "visitors", "Check-out and update visitor passes"),
    ("visitors.pass.create", "visitors", "Issue gated visitor access passes"),
    ("visitors.pass.read", "visitors", "Inspect visitor logbooks and entry histories"),
    ("visitors.pass.update", "visitors", "Record visitor departures and pass completions"),

    # --- Complaints & Grievances ---
    ("complaints:create", "complaints", "Lodge resident complaints"),
    ("complaints:read", "complaints", "View complaint tickets"),
    ("complaints:update", "complaints", "Update complaint status and triage"),
    ("complaints:delete", "complaints", "Archive or withdraw complaints"),
    ("complaints.ticket.create", "complaints", "Submit maintenance or facility complaints"),
    ("complaints.ticket.read", "complaints", "Inspect lodged grievances and ticket threads"),
    ("complaints.ticket.update", "complaints", "Triage, assign, and escalate complaint status"),
    ("complaints.ticket.delete", "complaints", "Close and archive resolved complaints"),

    # --- Maintenance Work Orders ---
    ("maintenance:create", "maintenance", "Create repair work orders"),
    ("maintenance:read", "maintenance", "Inspect maintenance orders"),
    ("maintenance:update", "maintenance", "Update task progress and completion"),
    ("maintenance.order.create", "maintenance", "Generate facility repair work orders"),
    ("maintenance.order.read", "maintenance", "View active maintenance queues and trade tasks"),
    ("maintenance.order.update", "maintenance", "Update work order progress, parts, and sign-offs"),

    # --- Finance, Billing & Invoicing ---
    ("finance:create", "finance", "Generate invoices and fee structures"),
    ("finance:read", "finance", "View invoices and payment receipts"),
    ("finance:update", "finance", "Record payments and fee updates"),
    ("finance:approve", "finance", "Authorize fee refunds and waivers"),
    ("finance:export", "finance", "Export financial balance ledgers"),
    ("finance.invoice.create", "finance", "Issue student semester fee invoices"),
    ("finance.invoice.read", "finance", "Inspect billing ledgers and outstanding balances"),
    ("finance.payment.update", "finance", "Record fee collection and reconcile transactions"),
    ("finance.refund.approve", "finance", "Approve caution deposit refunds and fee credits"),
    ("finance.report.export", "finance", "Export revenue, cash receipt, and fee audit sheets"),

    # --- Mess & Dining Hall Management ---
    ("mess:create", "mess", "Create weekly meal plans and menus"),
    ("mess:read", "mess", "View weekly meal schedules and menus"),
    ("mess:update", "mess", "Update meal options and dietary plans"),
    ("mess.menu.create", "mess", "Draft weekly dining hall breakfast, lunch, dinner menus"),
    ("mess.menu.read", "mess", "Inspect daily meal plans and dietary notices"),
    ("mess.menu.update", "mess", "Update dining schedules and meal subscription status"),

    # --- Inventory & Consumable Supplies ---
    ("inventory:create", "inventory", "Add inventory items and stock batches"),
    ("inventory:read", "inventory", "View stock levels and items"),
    ("inventory:update", "inventory", "Record stock consumption and adjustments"),
    ("inventory.item.create", "inventory", "Register new facility inventory SKUs"),
    ("inventory.item.read", "inventory", "Check consumable stock levels and bin locations"),
    ("inventory.item.update", "inventory", "Record inbound shipments and usage deductions"),

    # --- Audit & Latency Telemetry ---
    ("audit:read", "audit", "Inspect immutable audit log records"),
    ("audit:export", "audit", "Export audit trails for regulatory compliance"),
    ("audit.log.read", "audit", "Inspect system-wide immutable action audit trails"),
    ("audit.log.export", "audit", "Export compliance and security audit logs"),

    # --- Admissions Intake ---
    ("admissions:read", "admissions", "Review incoming student admission requests"),
    ("admissions:approve", "admissions", "Approve student admission requests"),
    ("admissions:reject", "admissions", "Reject student admission requests"),
    ("admissions.application.read", "admissions", "Review admission requests and academic credentials"),
    ("admissions.application.approve", "admissions", "Authorize hostel registration for applicant"),
    ("admissions.application.reject", "admissions", "Decline admission application with formal reason"),

    # --- System Settings & Administration ---
    ("settings:manage", "settings", "Configure global system parameters"),
    ("settings.system.manage", "settings", "Modify hostel global configurations and policies"),

    # --- Clerk Front-Desk & Certificates ---
    ("clerk.document.verify", "clerk", "Verify original student identity and educational records"),
    ("clerk.register.manage", "clerk", "Maintain physical entry/exit desk registers"),
    ("clerk.certificate.issue", "clerk", "Issue hostel residency and bonafide certificates"),

    # --- Security Supervision & Patrols ---
    ("security.roster.manage", "security", "Configure guard shift rosters and duty checkpoints"),
    ("security.incident.escalate", "security", "Escalate security perimeter incidents to Chief Warden"),
    ("security.patrol.log", "security", "Log night perimeter patrols and gate inspections"),

    # --- IT Administrator ---
    ("system.health.read", "system", "Inspect API latency, database metrics, and server uptime"),
    ("system.backup.manage", "system", "Trigger on-demand backups and inspect snapshot integrity"),
    ("system.workers.manage", "system", "Monitor background worker locks and task schedules"),

    # --- Departments & Dashboards ---
    ("departments:read", "departments", "View department structures and staff allocations"),
    ("departments:manage", "departments", "Create, update, or reorganize departments"),
    ("departments.structure.read", "departments", "View department hierarchy and members"),
    ("departments.structure.manage", "departments", "Configure departmental assignments"),
    ("dashboards:read", "dashboards", "Access assigned consolidated dashboard interfaces"),
    ("dashboards:manage", "dashboards", "Configure dashboard layouts and widget visibility"),
    ("dashboards.group.read", "dashboards", "View assigned dashboard groups and KPI widgets"),
    ("dashboards.group.manage", "dashboards", "Configure consolidated dashboard role mappings"),

    # --- Specialized Enterprise Operations ---
    ("surveillance:read", "surveillance", "Monitor CCTV feeds and safety equipment status"),
    ("surveillance:operate", "surveillance", "Operate security cameras and trigger emergency alarms"),
    ("surveillance.feed.read", "surveillance", "Inspect surveillance cameras and sensor status"),
    ("surveillance.feed.operate", "surveillance", "Control security cameras and trigger lockdown/alarms"),

    ("kitchen:read", "kitchen", "View kitchen preparation schedules and ration stocks"),
    ("kitchen:manage", "kitchen", "Manage daily rations, recipes, and culinary preparations"),
    ("kitchen.ration.read", "kitchen", "Inspect kitchen daily ration balances and requirements"),
    ("kitchen.ration.manage", "kitchen", "Approve grocery requisitions and manage preparation lines"),

    ("housekeeping:read", "housekeeping", "View housekeeping rosters and cleaning inspection logs"),
    ("housekeeping:complete", "housekeeping", "Mark cleaning tasks and sanitation inspections completed"),
    ("housekeeping.task.read", "housekeeping", "Inspect floor sanitation inspection logs"),
    ("housekeeping.task.complete", "housekeeping", "Complete assigned room and corridor cleaning tasks"),

    ("laundry:read", "laundry", "View laundry intake registers and washing cycles"),
    ("laundry:process", "laundry", "Process resident laundry batches and linen deliveries"),
    ("laundry.batch.read", "laundry", "Check active student laundry token queues"),
    ("laundry.batch.process", "laundry", "Record washing, drying, and return of resident clothes"),

    ("medical:read", "medical", "View resident health records and first aid logs"),
    ("medical:prescribe", "medical", "Log clinical consultations and medical supplies"),
    ("medical.record.read", "medical", "Review student medical histories and emergency alerts"),
    ("medical.record.prescribe", "medical", "Record infirmary visits and dispense first aid kits"),

    ("transport:read", "transport", "View campus transport routes and shuttle schedules"),
    ("transport:operate", "transport", "Update shuttle departure logs and vehicle upkeep status"),
    ("transport.schedule.read", "transport", "View campus shuttle routes and timing schedules"),
    ("transport.schedule.operate", "transport", "Record trip departures and fleet maintenance events"),

    ("recreation:read", "recreation", "View sports facility bookings and recreation schedules"),
    ("recreation:manage", "recreation", "Approve gym bookings and tournament equipment loans"),
    ("recreation.facility.read", "recreation", "View open sports grounds and gymnasium hours"),
    ("recreation.facility.manage", "recreation", "Authorize sports equipment loans and venue bookings"),

    ("grievances:read", "grievances", "Review submitted student grievances and incident reports"),
    ("grievances:resolve", "grievances", "Record official disciplinary resolutions and anti-ragging closures"),
    ("grievances.incident.read", "grievances", "Review confidential student protection complaints"),
    ("grievances.incident.resolve", "grievances", "Formalize disciplinary actions and protection orders"),
]

# Role to Permission Names Mapping for All 31 Roles
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
        "audit:read", "departments:read", "dashboards:read",
        # Enterprise
        "users.account.read", "hostels.facility.manage", "hostels.facility.create",
        "hostels.facility.read", "hostels.facility.update", "students.profile.create",
        "students.profile.read", "students.profile.update", "students.profile.export",
        "allocations.bed.create", "allocations.bed.read", "allocations.bed.update",
        "allocations.bed.delete", "allocations.bed.export", "attendance.record.read",
        "attendance.record.export", "leave.request.read", "leave.request.approve",
        "leave.request.reject", "complaints.ticket.read", "complaints.ticket.update",
        "maintenance.order.read", "finance.invoice.read", "audit.log.read",
        "system.health.read", "departments.structure.read", "dashboards.group.read",
        # SA-02 Infrastructure Management
        "campuses:read", "campuses.facility.read", "infrastructure:read", "infrastructure.hierarchy.read",
        "infrastructure.capacity.read", "infrastructure:export", "infrastructure.data.export",
        "blocks:manage", "floors:manage", "rooms:manage", "beds:manage"
    ],

    # 3. Institutional Administrator (institutional_admin): University Registry & Welfare
    "institutional_admin": [
        "users:read", "users.account.read", "hostel:read", "hostels.facility.read",
        "student:read", "student:export", "students.profile.read", "students.profile.export",
        "attendance:read", "attendance.record.read", "audit:read", "audit.log.read",
        "system.health.read", "departments:read", "departments.structure.read",
        "dashboards:read", "dashboards.group.read", "grievances:read", "grievances.incident.read",
        # SA-02 Institutional & Campus Read
        "institution:read", "institutions.profile.read", "campuses:read", "campuses.facility.read",
        "infrastructure:read", "infrastructure.hierarchy.read", "infrastructure.capacity.read"
    ],

    # 4. Chief Warden (warden): Primary Hostel Operational Head
    "warden": [
        # Legacy
        "hostel:read", "hostel:update",
        "student:read", "student:update", "student:export",
        "allocation:create", "allocation:read", "allocation:update", "allocation:delete",
        "attendance:create", "attendance:read", "attendance:export",
        "leave:read", "leave:approve", "leave:reject",
        "visitors:read", "complaints:read", "complaints:update",
        "maintenance:create", "maintenance:read",
        "finance:read", "mess:read", "audit:read", "dashboards:read",
        # Enterprise
        "hostels.facility.read", "hostels.facility.update",
        "students.profile.read", "students.profile.update", "students.profile.export",
        "allocations.bed.create", "allocations.bed.read", "allocations.bed.update", "allocations.bed.delete",
        "attendance.record.create", "attendance.record.read", "attendance.record.export",
        "leave.request.read", "leave.request.approve", "leave.request.reject",
        "visitors.pass.read", "complaints.ticket.read", "complaints.ticket.update",
        "maintenance.order.create", "maintenance.order.read",
        "finance.invoice.read", "mess.menu.read", "audit.log.read",
        "dashboards.group.read", "grievances:read", "grievances.incident.read"
    ],

    # 5. Assistant Warden: Block & Daily Student Life Management
    "assistant_warden": [
        # Legacy
        "hostel:read", "student:read", "allocation:read",
        "attendance:create", "attendance:read",
        "leave:read", "leave:approve", "leave:reject",
        "visitors:create", "visitors:read", "visitors:update",
        "complaints:read", "complaints:update", "maintenance:read", "dashboards:read",
        # Enterprise
        "hostels.facility.read", "students.profile.read", "allocations.bed.read",
        "attendance.record.create", "attendance.record.read",
        "leave.request.read", "leave.request.approve", "leave.request.reject",
        "visitors.pass.create", "visitors.pass.read", "visitors.pass.update",
        "complaints.ticket.read", "complaints.ticket.update", "maintenance.order.read",
        "dashboards.group.read"
    ],

    # 6. Hostel Clerk: Office Front-Desk, Records & Certificates
    "hostel_clerk": [
        # Legacy & Enterprise
        "student:read", "students.profile.read",
        "allocation:read", "allocations.bed.read",
        "attendance:read", "attendance.record.read",
        "visitors:create", "visitors:read", "visitors:update",
        "visitors.pass.create", "visitors.pass.read", "visitors.pass.update",
        "complaints:create", "complaints:read",
        "complaints.ticket.create", "complaints.ticket.read",
        "clerk.document.verify", "clerk.register.manage", "clerk.certificate.issue",
        "dashboards:read", "dashboards.group.read"
    ],

    # 7. Admission Officer: Student Registration & Room Allotment Intake
    "admission_officer": [
        # Legacy
        "admissions:read", "admissions:approve", "admissions:reject",
        "student:create", "student:read", "student:update",
        "hostel:read", "dashboards:read",
        # Enterprise
        "admissions.application.read", "admissions.application.approve", "admissions.application.reject",
        "students.profile.create", "students.profile.read", "students.profile.update",
        "hostels.facility.read", "dashboards.group.read"
    ],

    # 8. Hostel Allotment Officer: Room & Bed Capacity Management
    "hostel_allotment_officer": [
        "allocation:create", "allocation:read", "allocation:update", "allocation:delete", "allocation:export",
        "allocations.bed.create", "allocations.bed.read", "allocations.bed.update",
        "allocations.bed.delete", "allocations.bed.export",
        "hostel:read", "hostels.facility.read", "student:read", "students.profile.read",
        "dashboards:read", "dashboards.group.read"
    ],

    # 9. Financial Accountant: Fees, Invoicing & Refunds
    "accountant": [
        # Legacy
        "finance:create", "finance:read", "finance:update", "finance:approve", "finance:export",
        "student:read", "allocation:read", "hostel:read", "dashboards:read",
        # Enterprise
        "finance.invoice.create", "finance.invoice.read", "finance.payment.update",
        "finance.refund.approve", "finance.report.export",
        "students.profile.read", "allocations.bed.read", "hostels.facility.read",
        "dashboards.group.read"
    ],

    # 9b. Financial Cashier: Counter Receipts
    "cashier": [
        "finance:read", "finance:update", "finance.invoice.read", "finance.payment.update",
        "student:read", "students.profile.read", "dashboards:read", "dashboards.group.read"
    ],

    # 10. TQM Compliance Auditor: Read-Only System Telemetry
    "auditor": [
        # Legacy
        "audit:read", "audit:export",
        "student:read", "student:export",
        "allocation:read", "allocation:export",
        "finance:read", "finance:export",
        "complaints:read", "hostel:read", "dashboards:read",
        # Enterprise
        "audit.log.read", "audit.log.export",
        "students.profile.read", "students.profile.export",
        "allocations.bed.read", "allocations.bed.export",
        "finance.invoice.read", "finance.report.export",
        "complaints.ticket.read", "hostels.facility.read",
        "system.health.read", "dashboards.group.read"
    ],

    # 11. Security Supervisor: Gate Operations & Guard Oversight
    "security_supervisor": [
        # Legacy & Enterprise
        "visitors:create", "visitors:read", "visitors:update",
        "visitors.pass.create", "visitors.pass.read", "visitors.pass.update",
        "attendance:create", "attendance:read",
        "attendance.record.create", "attendance.record.read",
        "leave:read", "leave.request.read",
        "complaints:read", "complaints.ticket.read",
        "security.roster.manage", "security.incident.escalate", "security.patrol.log",
        "dashboards:read", "dashboards.group.read"
    ],

    # 12. Security Guard: Real-time Gate Access Control
    "security_guard": [
        # Legacy
        "visitors:create", "visitors:read", "visitors:update",
        "attendance:create", "attendance:read",
        "leave:read", "dashboards:read",
        # Enterprise
        "visitors.pass.create", "visitors.pass.read", "visitors.pass.update",
        "attendance.record.create", "attendance.record.read",
        "leave.request.read", "dashboards.group.read"
    ],

    # 13. CCTV Operator: Surveillance & Safety
    "cctv_operator": [
        "surveillance:read", "surveillance:operate",
        "surveillance.feed.read", "surveillance.feed.operate",
        "visitors:read", "visitors.pass.read", "security.patrol.log",
        "dashboards:read", "dashboards.group.read"
    ],

    # 14. Mess Manager: Dining Hall Menus & Subscriptions
    "mess_manager": [
        # Legacy
        "mess:create", "mess:read", "mess:update",
        "student:read", "inventory:read", "inventory:update", "dashboards:read",
        # Enterprise
        "mess.menu.create", "mess.menu.read", "mess.menu.update",
        "students.profile.read", "inventory.item.read", "inventory.item.update",
        "dashboards.group.read"
    ],

    # 15. Head Chef: Kitchen & Food Operations
    "head_chef": [
        "kitchen:read", "kitchen:manage",
        "kitchen.ration.read", "kitchen.ration.manage",
        "mess:read", "mess.menu.read", "inventory:read", "inventory.item.read",
        "dashboards:read", "dashboards.group.read"
    ],

    # 16. Maintenance Manager: Work Order Triage & SLA Oversight
    "maintenance_manager": [
        "maintenance:create", "maintenance:read", "maintenance:update",
        "maintenance.order.create", "maintenance.order.read", "maintenance.order.update",
        "complaints:read", "complaints:update", "complaints.ticket.read", "complaints.ticket.update",
        "inventory:read", "inventory.item.read", "dashboards:read", "dashboards.group.read"
    ],

    # 17. Maintenance Technician: General Trades
    "maintenance_staff": [
        # Legacy
        "maintenance:read", "maintenance:update",
        "complaints:read", "complaints:update",
        "inventory:read", "inventory:update", "dashboards:read",
        # Enterprise
        "maintenance.order.read", "maintenance.order.update",
        "complaints.ticket.read", "complaints.ticket.update",
        "inventory.item.read", "inventory.item.update", "dashboards.group.read"
    ],

    # 17a. Electrician: Electrical Repairs
    "electrician": [
        "maintenance:read", "maintenance:update", "maintenance.order.read", "maintenance.order.update",
        "complaints:read", "complaints.ticket.read", "inventory:read", "inventory.item.read",
        "dashboards:read", "dashboards.group.read"
    ],

    # 17b. Plumber: Water & Drainage Repairs
    "plumber": [
        "maintenance:read", "maintenance:update", "maintenance.order.read", "maintenance.order.update",
        "complaints:read", "complaints.ticket.read", "inventory:read", "inventory.item.read",
        "dashboards:read", "dashboards.group.read"
    ],

    # 17c. Carpenter: Woodwork & Furniture Repairs
    "carpenter": [
        "maintenance:read", "maintenance:update", "maintenance.order.read", "maintenance.order.update",
        "complaints:read", "complaints.ticket.read", "inventory:read", "inventory.item.read",
        "dashboards:read", "dashboards.group.read"
    ],

    # 18. Housekeeping Staff: Cleanliness & Sanitation
    "housekeeping_staff": [
        "housekeeping:read", "housekeeping:complete",
        "housekeeping.task.read", "housekeeping.task.complete",
        "complaints:read", "complaints.ticket.read", "dashboards:read", "dashboards.group.read"
    ],

    # 19. Laundry Staff: Linen & Student Laundry Intake
    "laundry_staff": [
        "laundry:read", "laundry:process",
        "laundry.batch.read", "laundry.batch.process",
        "dashboards:read", "dashboards.group.read"
    ],

    # 20. Medical Officer: Resident Clinic & First Aid
    "medical_officer": [
        "medical:read", "medical:prescribe",
        "medical.record.read", "medical.record.prescribe",
        "student:read", "students.profile.read", "dashboards:read", "dashboards.group.read"
    ],

    # 21. IT Administrator: System Health, Backups & Audit Telemetry
    "it_admin": [
        # Legacy & Enterprise
        "system.health.read", "system.backup.manage", "system.workers.manage",
        "audit:read", "audit:export", "audit.log.read", "audit.log.export",
        "users:read", "users.account.read",
        "roles:read", "roles.definition.read",
        "settings:manage", "settings.system.manage",
        "dashboards:read", "dashboards.group.read", "departments:read", "departments.structure.read"
    ],

    # 22. Inventory Manager: Hostel Property & Consumables
    "inventory_manager": [
        "inventory:create", "inventory:read", "inventory:update",
        "inventory.item.create", "inventory.item.read", "inventory.item.update",
        "dashboards:read", "dashboards.group.read"
    ],

    # 23. Procurement Manager: Vendor Contracts & Purchasing
    "procurement_manager": [
        "inventory:read", "inventory.item.read", "finance:read", "finance.invoice.read",
        "dashboards:read", "dashboards.group.read"
    ],

    # 24. Student: Personal Resident Account
    "student": [
        # Legacy
        "student:read", "allocation:read", "attendance:read",
        "leave:create", "leave:read",
        "complaints:create", "complaints:read",
        "finance:read", "mess:read", "dashboards:read",
        # Enterprise
        "students.profile.read", "allocations.bed.read", "attendance.record.read",
        "leave.request.create", "leave.request.read",
        "complaints.ticket.create", "complaints.ticket.read",
        "finance.invoice.read", "mess.menu.read", "dashboards.group.read"
    ],

    # 25. Parent / Guardian: Linked Ward Oversight
    "parent_guardian": [
        # Legacy
        "student:read", "allocation:read", "attendance:read", "finance:read", "dashboards:read",
        # Enterprise
        "students.profile.read", "allocations.bed.read",
        "attendance.record.read", "finance.invoice.read", "dashboards.group.read"
    ],

    # 26. Transport Supervisor: Shuttle Schedules & Fleet
    "transport_supervisor": [
        "transport:read", "transport:operate",
        "transport.schedule.read", "transport.schedule.operate",
        "dashboards:read", "dashboards.group.read"
    ],

    # 27. Sports Coordinator: Gyms & Athletic Facilities
    "sports_coordinator": [
        "recreation:read", "recreation:manage",
        "recreation.facility.read", "recreation.facility.manage",
        "dashboards:read", "dashboards.group.read"
    ],

    # 28. Grievance Officer: Protection & Anti-Ragging
    "grievance_officer": [
        "grievances:read", "grievances:resolve",
        "grievances.incident.read", "grievances.incident.resolve",
        "complaints:read", "complaints:update", "complaints.ticket.read", "complaints.ticket.update",
        "dashboards:read", "dashboards.group.read"
    ]
}
