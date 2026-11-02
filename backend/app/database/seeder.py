"""Safe Demonstration Data Seeder for Development and Evaluation.

Course: BBAT104 - Fundamentals of Total Quality Management (TQM)
Quality Goal: Q05 - Reduce Response Time
"""

import sqlite3
from typing import Optional
from backend.app.database.connection import get_db_connection
from backend.app.services.rbac_data import ROLES_LIST, PERMISSIONS_LIST, ROLE_PERMISSIONS_MAP
from backend.app.services.security import hash_password
from backend.app.utils.logger import logger


def seed_database(conn: Optional[sqlite3.Connection] = None) -> bool:
    """Populate database with structured demonstration records across all domains."""
    should_close = False
    if conn is None:
        conn = get_db_connection()
        should_close = True

    try:
        cursor = conn.cursor()

        # Check if users already exist to avoid duplicate seeding
        cursor.execute("SELECT COUNT(*) FROM users;")
        if cursor.fetchone()[0] > 0:
            logger.info("Database already seeded. Skipping seeder execution.")
            return False

        logger.info("Beginning database demonstration data seeding...")

        # 1. Seed 12 User Roles
        roles_data = [(name, desc, 1) for name, desc in ROLES_LIST]
        cursor.executemany("INSERT INTO roles (name, description, is_system) VALUES (?, ?, ?);", roles_data)

        # Build role_name -> role_id lookup
        cursor.execute("SELECT id, name FROM roles;")
        role_id_map = {name: r_id for r_id, name in cursor.fetchall()}

        # 2. Seed Granular Permissions
        cursor.executemany(
            "INSERT INTO permissions (name, module, description) VALUES (?, ?, ?);",
            PERMISSIONS_LIST
        )

        # Build perm_name -> perm_id lookup
        cursor.execute("SELECT id, name FROM permissions;")
        perm_id_map = {name: p_id for p_id, name in cursor.fetchall()}

        # Map Role-Permissions
        role_perm_rows = []
        for role_name, perm_names in ROLE_PERMISSIONS_MAP.items():
            r_id = role_id_map.get(role_name)
            if not r_id:
                continue
            for p_name in perm_names:
                p_id = perm_id_map.get(p_name)
                if p_id:
                    role_perm_rows.append((r_id, p_id))

        cursor.executemany(
            "INSERT OR IGNORE INTO role_permissions (role_id, permission_id) VALUES (?, ?);",
            role_perm_rows
        )
        logger.info(f"Seeded {len(roles_data)} roles and {len(role_perm_rows)} role-permission mappings.")

        # 3. Seed Demo Users for Primary Roles (bcrypt hashed)
        default_pw = "Password123!" # Consistent safe demo password for all demo accounts
        hashed_pw = hash_password(default_pw)

        demo_users = [
            ("superadmin", "superadmin@univ.edu", hashed_pw, "", "Super", "Admin", "9800000001", "super_admin", None, None),
            ("hosteladmin", "hosteladmin@univ.edu", hashed_pw, "", "Hostel", "Admin", "9800000002", "hostel_admin", None, 1),
            ("warden", "warden@univ.edu", hashed_pw, "", "Dr. Anand", "Kulkarni", "9800000003", "warden", None, 1),
            ("asstwarden", "asstwarden@univ.edu", hashed_pw, "", "Suresh", "Rao", "9800000004", "assistant_warden", None, 2),
            ("rohan", "rohan.bakshi@univ.edu", hashed_pw, "", "Rohan", "Bakshi", "9810301057", "student", 1, 1),
            ("accountant", "accountant@univ.edu", hashed_pw, "", "Manoj", "Sharma", "9800000006", "accountant", None, None),
            ("messmanager", "messmanager@univ.edu", hashed_pw, "", "Rajesh", "Verma", "9800000007", "mess_manager", None, 1),
            ("maintenance", "maintenance@univ.edu", hashed_pw, "", "Ramesh", "Kumar", "9800000008", "maintenance_staff", None, 1),
            ("security", "security@univ.edu", hashed_pw, "", "Baljit", "Singh", "9800000009", "security_guard", None, 1),
            ("admission", "admission@univ.edu", hashed_pw, "", "Geeta", "Iyer", "9800000010", "admission_officer", None, None),
            ("parent", "parent@univ.edu", hashed_pw, "", "Sunil", "Bakshi", "9800000011", "parent_guardian", 1, 1),
            ("evaluator", "evaluator@univ.edu", hashed_pw, "", "TQM Faculty", "Auditor", "9800000012", "auditor", None, None)
        ]

        user_id_map = {}
        for (uname, email, pwd, salt, fn, ln, ph, role_name, link_s, link_h) in demo_users:
            cursor.execute(
                """INSERT INTO users (username, email, password_hash, salt, first_name, last_name, phone, linked_student_id, linked_hostel_id)
                   VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?);""",
                (uname, email, pwd, salt, fn, ln, ph, link_s, link_h)
            )
            u_id = cursor.lastrowid
            user_id_map[uname] = u_id
            r_id = role_id_map[role_name]
            cursor.execute("INSERT INTO user_roles (user_id, role_id) VALUES (?, ?);", (u_id, r_id))
            staff_roles = {'super_admin', 'hostel_admin', 'warden', 'assistant_warden', 'accountant', 'mess_manager', 'maintenance_staff', 'security_guard', 'admission_officer', 'auditor'}
            if role_name in staff_roles:
                s_id = f"STF-{u_id:04d}"
                cursor.execute("UPDATE users SET staff_id = ? WHERE id = ?;", (s_id, u_id))

        # 4. Seed Hostel, Buildings, Floors, Rooms & Beds
        cursor.execute("SELECT id FROM hostels WHERE code = 'RTH-01';")
        rth_row = cursor.fetchone()
        if not rth_row:
            warden_user_id = user_id_map.get("warden", 3)
            cursor.execute(
                """INSERT INTO hostels (name, code, hostel_type, address, warden_id, contact_phone, contact_email)
                   VALUES ('Rabindranath Tagore Hostel', 'RTH-01', 'Boys', 'North Campus, Tech Avenue', ?, '011-2700101', 'tagore.hostel@univ.edu');""",
                (warden_user_id,)
            )
            hostel_id = cursor.lastrowid

            cursor.execute("INSERT INTO buildings (hostel_id, name, code, total_floors) VALUES (?, 'Aryabhata Block', 'BLK-A', 3);", (hostel_id,))
            bldg_a = cursor.lastrowid

            cursor.execute("INSERT INTO floors (building_id, floor_number, floor_name) VALUES (?, 1, 'First Floor');", (bldg_a,))
            flr_1 = cursor.lastrowid
            cursor.execute("INSERT INTO floors (building_id, floor_number, floor_name) VALUES (?, 2, 'Second Floor');", (bldg_a,))
            flr_2 = cursor.lastrowid

            # Rooms in Boys Hostel
            cursor.execute("INSERT INTO rooms (floor_id, room_number, room_type, capacity, base_fee, status) VALUES (?, '101', 'Single', 1, 6000.0, 'Full');", (flr_1,))
            r101 = cursor.lastrowid
            cursor.execute("INSERT INTO rooms (floor_id, room_number, room_type, capacity, base_fee, status) VALUES (?, '102', 'Double', 2, 4500.0, 'Partially_Occupied');", (flr_1,))
            r102 = cursor.lastrowid
            cursor.execute("INSERT INTO rooms (floor_id, room_number, room_type, capacity, base_fee, status) VALUES (?, '201', 'Double', 2, 4500.0, 'Available');", (flr_2,))
            r201 = cursor.lastrowid

            # Beds in Boys Hostel
            cursor.execute("INSERT INTO beds (room_id, bed_number, status) VALUES (?, '101-A', 'Occupied');", (r101,))
            b101_a = cursor.lastrowid
            cursor.execute("INSERT INTO beds (room_id, bed_number, status) VALUES (?, '102-A', 'Occupied');", (r102,))
            b102_a = cursor.lastrowid
            cursor.execute("INSERT INTO beds (room_id, bed_number, status) VALUES (?, '102-B', 'Available');", (r102,))
            b102_b = cursor.lastrowid
            cursor.execute("INSERT INTO beds (room_id, bed_number, status) VALUES (?, '201-A', 'Available');", (r201,))
            cursor.execute("INSERT INTO beds (room_id, bed_number, status) VALUES (?, '201-B', 'Available');", (r201,))

        else:
            hostel_id = rth_row["id"]

        cursor.execute("SELECT id FROM hostels WHERE code = 'SNH-01';")
        snh_row = cursor.fetchone()
        if not snh_row:
            warden_user_id = user_id_map.get("warden", 3)
            cursor.execute(
                """INSERT INTO hostels (name, code, hostel_type, address, warden_id, contact_phone, contact_email)
                   VALUES ('Sarojini Naidu Girls Hostel', 'SNH-01', 'Girls', 'South Campus, Green Way', ?, '011-2700102', 'sarojini.hostel@univ.edu');""",
                (warden_user_id,)
            )
            hostel_g_id = cursor.lastrowid

            cursor.execute("INSERT INTO buildings (hostel_id, name, code, total_floors) VALUES (?, 'Kalpana Chawla Block', 'BLK-G1', 2);", (hostel_g_id,))
            bldg_g = cursor.lastrowid

            cursor.execute("INSERT INTO floors (building_id, floor_number, floor_name) VALUES (?, 1, 'Ground Floor');", (bldg_g,))
            flr_g1 = cursor.lastrowid

            cursor.execute("INSERT INTO rooms (floor_id, room_number, room_type, capacity, base_fee, status) VALUES (?, 'G01', 'Double', 2, 4800.0, 'Available');", (flr_g1,))
            r_g01 = cursor.lastrowid
            cursor.execute("INSERT INTO beds (room_id, bed_number, status) VALUES (?, 'G01-A', 'Available');", (r_g01,))
            cursor.execute("INSERT INTO beds (room_id, bed_number, status) VALUES (?, 'G01-B', 'Available');", (r_g01,))

            for r_num in ['103', '104', '105']:
                cursor.execute("INSERT INTO rooms (floor_id, room_number, room_type, capacity, base_fee, status) VALUES (?, ?, 'Double', 2, 4500.0, 'Available');", (flr_1, r_num))
                r_id = cursor.lastrowid
                cursor.execute("INSERT INTO beds (room_id, bed_number, status) VALUES (?, ?, 'Available');", (r_id, f"{r_num}-A"))
                cursor.execute("INSERT INTO beds (room_id, bed_number, status) VALUES (?, ?, 'Available');", (r_id, f"{r_num}-B"))

            for r_num in ['202', '203', '204', '205']:
                cursor.execute("INSERT INTO rooms (floor_id, room_number, room_type, capacity, base_fee, status) VALUES (?, ?, 'Double', 2, 4500.0, 'Available');", (flr_2, r_num))
                r_id = cursor.lastrowid
                cursor.execute("INSERT INTO beds (room_id, bed_number, status) VALUES (?, ?, 'Available');", (r_id, f"{r_num}-A"))
                cursor.execute("INSERT INTO beds (room_id, bed_number, status) VALUES (?, ?, 'Available');", (r_id, f"{r_num}-B"))


            for r_num in ['G02', 'G03', 'G04', 'G05']:
                cursor.execute("INSERT INTO rooms (floor_id, room_number, room_type, capacity, base_fee, status) VALUES (?, ?, 'Double', 2, 4800.0, 'Available');", (flr_g1, r_num))
                r_id = cursor.lastrowid
                cursor.execute("INSERT INTO beds (room_id, bed_number, status) VALUES (?, ?, 'Available');", (r_id, f"{r_num}-A"))
                cursor.execute("INSERT INTO beds (room_id, bed_number, status) VALUES (?, ?, 'Available');", (r_id, f"{r_num}-B"))

        cursor.execute("SELECT id FROM hostels WHERE code = 'MTGH-01';")
        if not cursor.fetchone():
            cursor.execute(
                """INSERT INTO hostels (name, code, hostel_type, address, contact_phone, contact_email, is_active)
                   VALUES ('Mother Teresa Girls Hostel', 'MTGH-01', 'Girls', 'South Campus, Block C, University Enclave', '011-2700103', 'teresa.girls@univ.edu', 1);"""
            )
            hostel_mt_id = cursor.lastrowid

            cursor.execute("INSERT INTO buildings (hostel_id, name, code, total_floors, is_active) VALUES (?, 'Mother Teresa Wing', 'BLK-MTG', 2, 1);", (hostel_mt_id,))
            bldg_mt = cursor.lastrowid

            cursor.execute("INSERT INTO floors (building_id, floor_number, floor_name) VALUES (?, 1, 'First Floor');", (bldg_mt,))
            flr_mt1 = cursor.lastrowid

            for r_num in ['101', '102', '103', '104', '105', '106', '107', '108', '109', '110']:
                cursor.execute("INSERT INTO rooms (floor_id, room_number, room_type, capacity, base_fee, status, is_active) VALUES (?, ?, 'Single', 1, 6500.0, 'Available', 1);", (flr_mt1, r_num))
                r_id = cursor.lastrowid
                cursor.execute("INSERT INTO beds (room_id, bed_number, status) VALUES (?, ?, 'Available');", (r_id, f"{r_num}-A"))

        # 5. Seed Students (Fictional Demo Records)
        rohan_user_id = user_id_map.get("rohan", 5)
        students_data = [
            ("2410301057", rohan_user_id, "Rohan", "Bakshi", "rohan.bakshi@univ.edu", "9810301057", "Male", "2005-04-12", "B+", "CSE", "3rd Year", "5th", "Hostel Resident", "2026-08-01"),
            ("2410301012", None, "Priya", "Sharma", "priya.sharma@univ.edu", "9811223344", "Female", "2006-02-18", "O+", "ECE", "2nd Year", "3rd", "East Wing", "2026-08-01"),
            ("2410301034", None, "Aarav", "Patel", "aarav.patel@univ.edu", "9822334455", "Male", "2005-09-25", "A+", "CSE", "3rd Year", "5th", "North Wing", "2026-08-02")
        ]
        cursor.executemany(
            """INSERT INTO students (student_id, user_id, first_name, last_name, email, phone, gender, date_of_birth, blood_group, branch, academic_year, semester, address, admission_date)
               VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?);""",
            students_data
        )
        s_rohan = 1
        s_priya = 2
        s_aarav = 3

        # 6. Seed Guardians
        cursor.execute(
            """INSERT INTO guardians (name, relationship, phone, email, occupation, address)
               VALUES ('Sunil Bakshi', 'Father', '9810301000', 'sunil.bakshi@demo.com', 'Senior Engineer', 'Civil Lines, City');"""
        )
        g_id = cursor.lastrowid
        cursor.execute("INSERT INTO student_guardians (student_id, guardian_id, is_primary) VALUES (?, ?, 1);", (s_rohan, g_id))

        # Resolve beds and rooms for initial demo allocations
        cursor.execute("SELECT id FROM beds WHERE bed_number = '101-A' LIMIT 1;")
        b101_a = cursor.fetchone()[0]
        cursor.execute("SELECT id FROM beds WHERE bed_number = '102-A' LIMIT 1;")
        b102_a = cursor.fetchone()[0]
        cursor.execute("SELECT id FROM rooms WHERE room_number = '101' LIMIT 1;")
        r101 = cursor.fetchone()[0]
        cursor.execute("SELECT id FROM rooms WHERE room_number = '102' LIMIT 1;")
        r102 = cursor.fetchone()[0]

        # 7. Seed Room Allocations
        cursor.execute(
            """INSERT INTO room_allocations (student_id, bed_id, room_id, start_date, fee_status, allocation_status, remarks, allocated_by)
               VALUES (?, ?, ?, '2026-08-01', 'Paid', 'Active', 'Allocated for Academic Year 2026-27', 1);""",
            (s_rohan, b101_a, r101)
        )
        cursor.execute(
            """INSERT INTO room_allocations (student_id, bed_id, room_id, start_date, fee_status, allocation_status, remarks, allocated_by)
               VALUES (?, ?, ?, '2026-08-01', 'Pending', 'Active', 'Double sharing room allotment', 1);""",
            (s_aarav, b102_a, r102)
        )

        # 8. Seed Complaints & History
        maintenance_user_id = user_id_map.get("maintenance", 8)
        cursor.execute(
            """INSERT INTO complaints (complaint_id, student_id, room_id, category, title, description, severity, status, assigned_to)
               VALUES ('CMP-2026-001', ?, ?, 'Electrical', 'Study Lamp Socket Failure', 'Wall socket on study table not powering laptop charger', 'Medium', 'In_Progress', ?);""",
            (s_rohan, r101, maintenance_user_id)
        )
        cmp_id = cursor.lastrowid
        cursor.execute(
            """INSERT INTO complaint_updates (complaint_id, updated_by, previous_status, new_status, comment)
               VALUES (?, ?, 'Pending', 'In_Progress', 'Caretaker Ramesh assigned to inspect and replace socket unit.');""",
            (cmp_id, maintenance_user_id)
        )

        # 9. Seed Financials: Fee Structure, Invoice & Payment
        cursor.execute(
            """INSERT INTO fee_structures (name, room_type, academic_year, semester, amount, amount_paise, payment_frequency)
               VALUES ('Semester 5 Single Occupancy Fee', 'Single', '2026-27', '5th', 6000.0, 600000, 'Monthly');"""
        )
        fee_id = cursor.lastrowid

        cursor.execute(
            """INSERT INTO invoices (invoice_number, student_id, fee_structure_id, issue_date, due_date, total_amount, total_amount_paise, paid_amount, paid_amount_paise, status)
               VALUES ('INV-2026-08-001', ?, ?, '2026-08-01', '2026-08-15', 6000.0, 600000, 6000.0, 600000, 'Paid');""",
            (s_rohan, fee_id)
        )
        inv_id = cursor.lastrowid

        cursor.execute("INSERT INTO invoice_items (invoice_id, title, amount, amount_paise) VALUES (?, 'Room 101 Monthly Rent', 6000.0, 600000);", (inv_id,))

        cursor.execute(
            """INSERT INTO payments (payment_reference, invoice_id, student_id, amount, amount_paise, payment_method, payment_date, transaction_id, status)
               VALUES ('PAY-2026-08-01-ROH', ?, ?, 6000.0, 600000, 'UPI', '2026-08-05', 'UPI-TXN-99887766', 'Completed');""",
            (inv_id, s_rohan)
        )

        # 10. Seed Mess Menu & Inventory
        cursor.execute(
            """INSERT INTO mess_menus (day_of_week, meal_type, items_description, is_special)
               VALUES ('Monday', 'Breakfast', 'Idli, Sambhar, Coconut Chutney, Tea / Coffee', 0);"""
        )
        cursor.execute(
            """INSERT INTO mess_menus (day_of_week, meal_type, items_description, is_special)
               VALUES ('Monday', 'Lunch', 'Dal Tadka, Paneer Butter Masala, Roti, Rice, Gulab Jamun', 1);"""
        )

        cursor.execute("INSERT INTO inventory_categories (name, description) VALUES ('Electrical Supplies', 'Switches, wires, bulbs, fuses');")
        cat_id = cursor.lastrowid

        cursor.execute(
            """INSERT INTO inventory_items (category_id, item_code, name, description, unit, quantity_in_stock, min_reorder_level, unit_price)
               VALUES (?, 'ELE-SOC-16A', '16A 3-Pin Wall Socket', 'Modular electrical socket with switch', 'pieces', 45, 10, 180.0);""",
            (cat_id,)
        )

        # 11. Seed Additional Comprehensive Demo Modules (Prompt 15 Readiness)
        # Admissions
        cursor.execute(
            """INSERT OR IGNORE INTO admission_applications (application_number, applicant_name, email, phone, gender, branch, academic_year, preferred_room_type, application_status, applied_at, reviewed_by, reviewed_at, remarks)
               VALUES ('ADM-2026-001', 'Kavita Sundaram', 'kavita.s@univ.edu', '9810301099', 'Female', 'CSE', '1st Year', 'Single', 'Approved', '2026-07-15 10:00:00', 1, '2026-07-16 11:30:00', 'Merit quota allocation approved');"""
        )
        cursor.execute(
            """INSERT OR IGNORE INTO admission_applications (application_number, applicant_name, email, phone, gender, branch, academic_year, preferred_room_type, application_status, applied_at, remarks)
               VALUES ('ADM-2026-002', 'Vikramaditya Rao', 'vikram.rao@univ.edu', '9810301098', 'Male', 'ECE', '1st Year', 'Double', 'Pending', '2026-08-01 14:20:00', 'Awaiting document verification');"""
        )

        # Attendance for resident students
        cursor.execute(
            """INSERT OR IGNORE INTO attendance (student_id, date, status, marked_by, remarks)
               VALUES (?, '2026-10-31', 'Present', 3, 'Regular morning roll-call');""",
            (s_rohan,)
        )
        cursor.execute(
            """INSERT OR IGNORE INTO attendance (student_id, date, status, marked_by, remarks)
               VALUES (?, '2026-11-01', 'Present', 3, 'Biometric biometric gate punch');""",
            (s_rohan,)
        )

        # Leave & Outpass
        cursor.execute(
            """INSERT OR IGNORE INTO leave_requests (id, student_id, leave_type, start_date, end_date, departure_time, expected_return_time, reason, destination, emergency_contact, guardian_contact, status, approved_by, reviewed_at, remarks)
               VALUES (1001, ?, 'Weekend', '2026-11-07', '2026-11-09', '17:00', '20:00', 'Visiting hometown family', 'New Delhi', '9810301057', '9810309999', 'Approved', 3, '2026-11-01 09:00:00', 'Warden verified with parent');""",
            (s_rohan,)
        )
        cursor.execute(
            """INSERT OR IGNORE INTO outpasses (outpass_number, leave_request_id, student_id, status, expected_exit_time, expected_return_time)
               VALUES ('OP-202611-0001', 1001, ?, 'Approved', '2026-11-07 17:00:00', '2026-11-09 20:00:00');""",
            (s_rohan,)
        )

        # Visitors & Active Gate Pass
        cursor.execute(
            """INSERT OR IGNORE INTO visitors (id, name, phone, id_proof_type, id_proof_number, address)
               VALUES (101, 'Sunil Bakshi', '9810309999', 'Aadhaar', 'XXXX-XXXX-4589', 'D-42 Hauz Khas, New Delhi');"""
        )
        cursor.execute(
            """INSERT OR IGNORE INTO visitor_logs (pass_number, visitor_id, student_id, hostel_id, room_id, check_in_time, expected_exit_time, purpose, approval_status, status, approved_by)
               VALUES ('VP-202611-0001', 101, ?, ?, ?, '2026-11-01 14:00:00', '2026-11-01 18:00:00', 'Parent semester fee discussion', 'Approved', 'Checked_In', 3);""",
            (s_rohan, hostel_id, r101)
        )

        # Maintenance Task for the complaint
        cursor.execute(
            """INSERT OR IGNORE INTO maintenance_tasks (task_code, complaint_id, category, title, description, priority, status, assigned_to, scheduled_date)
               VALUES ('TSK-2026-001', ?, 'Electrical', 'Repair Table Socket', 'Replace damaged 16A modular switch socket in Room 101', 'Medium', 'In_Progress', ?, '2026-11-02');""",
            (cmp_id, maintenance_user_id)
        )

        # Mess Subscriptions & Meal Attendance
        cursor.execute(
            """INSERT OR IGNORE INTO mess_subscriptions (subscription_reference, student_id, hostel_id, plan_type, diet_type, start_date, end_date, monthly_fee, total_fee, status)
               VALUES ('SUB-202611-0001', ?, ?, 'Semester', 'Veg', '2026-08-01', '2026-12-31', 3500.0, 17500.0, 'Active');""",
            (s_rohan, hostel_id)
        )
        sub_id = cursor.lastrowid
        if sub_id:
            cursor.execute(
                """INSERT OR IGNORE INTO meal_attendance (student_id, subscription_id, hostel_id, date, meal_type, verification_method, status, marked_by)
                   VALUES (?, ?, ?, '2026-11-01', 'Lunch', 'QR_Code', 'Present', 7);""",
                (s_rohan, sub_id, hostel_id)
            )

        # Additional Inventory Categories, Suppliers & Stock Items
        cursor.execute("INSERT OR IGNORE INTO suppliers (name, contact_person, phone, email, address, category) VALUES ('Apex Hardware & Supplies', 'Manoj Jain', '9811223344', 'sales@apexhardware.com', 'Industrial Area, Phase 2', 'Electrical & Plumbing');")
        sup_id = cursor.lastrowid or 1

        cursor.execute("INSERT OR IGNORE INTO inventory_categories (name, description) VALUES ('Provisions & Groceries', 'Rice, pulses, oils, spices');")
        cat_gro = cursor.lastrowid
        if cat_gro:
            cursor.execute(
                """INSERT OR IGNORE INTO inventory_items (category_id, item_code, name, description, unit, quantity_in_stock, min_reorder_level, unit_price, supplier_id)
                   VALUES (?, 'GRO-BAS-RICE', 'Basmati Rice Premium (25kg)', 'Aged long grain rice', 'bags', 25, 5, 1850.0, ?);""",
                (cat_gro, sup_id)
            )

        # In-App Notifications
        cursor.execute(
            """INSERT OR IGNORE INTO notifications (user_id, title, message, category, priority, is_read, event_key, delivery_channel)
               VALUES (?, 'Fee Payment Received', 'Your payment of Rs 6,000 for Invoice INV-2026-08-001 has been confirmed.', 'fees', 'Normal', 0, 'fee:inv:1', 'in_app');""",
            (user_id_map.get("rohan", 5),)
        )
        cursor.execute(
            """INSERT OR IGNORE INTO notifications (user_id, title, message, category, priority, is_read, event_key, delivery_channel)
               VALUES (?, 'Leave Request Approved', 'Your leave request for 2026-11-07 has been approved. Outpass OP-202611-0001 generated.', 'leaves', 'Important', 0, 'leave:app:1001', 'in_app');""",
            (user_id_map.get("rohan", 5),)
        )

        # Institutional Announcements
        admin_uid = user_id_map.get("superadmin", 1)
        cursor.execute(
            """INSERT OR IGNORE INTO announcements (title, content, category, priority, target_audience, target_hostel_id, status, created_by, published_by)
               VALUES ('Welcome to Academic Session 2026-27', 'Hostel accommodation guidelines and campus dining schedules are now active.', 'General Circular', 'Normal', 'All Users', NULL, 'Published', ?, ?);""",
            (admin_uid, admin_uid)
        )
        cursor.execute(
            """INSERT OR IGNORE INTO announcements (title, content, category, priority, target_audience, target_hostel_id, status, created_by, published_by)
               VALUES ('Hostel Wi-Fi Upgradation Notice', 'High-speed 10Gbps optical fiber switches are being configured in Tagore Hostel this weekend.', 'Maintenance Notice', 'Important', 'Hostel Residents', ?, 'Published', ?, ?);""",
            (hostel_id, admin_uid, admin_uid)
        )
        cursor.execute(
            """INSERT OR IGNORE INTO announcements (title, content, category, priority, target_audience, target_hostel_id, status, created_by, published_by)
               VALUES ('MANDATORY FIRE SAFETY DRILL', 'All residents of Rabindranath Tagore Hostel must assemble at North Ground at 10:00 AM sharp on Saturday.', 'Emergency Notice', 'Critical', 'Hostel Residents', ?, 'Published', ?, ?);""",
            (hostel_id, admin_uid, admin_uid)
        )

        # 12. Seed System Settings
        cursor.execute("INSERT OR IGNORE INTO system_settings (setting_key, setting_value, category, description) VALUES ('institution_name', 'University College of Engineering', 'general', 'Institute name');")
        cursor.execute("INSERT OR IGNORE INTO system_settings (setting_key, setting_value, category, description) VALUES ('q05_latency_target_ms', '10.0', 'performance', 'Target response time SLA');")

        conn.commit()
        logger.info(f"Database seeded with {len(demo_users)} demo users across all 12 roles.")
        return True
    except Exception as e:
        logger.error(f"Seeding failed: {e}")
        conn.rollback()
        raise
    finally:
        if should_close:
            conn.close()


if __name__ == "__main__":
    seed_database()
