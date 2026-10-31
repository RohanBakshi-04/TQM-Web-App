"""Database Schema Definitions: Operations, Maintenance, Finance, Mess, and Inventory.

Course: BBAT104 - Fundamentals of Total Quality Management (TQM)
Quality Goal: Q05 - Reduce Response Time
"""

OPERATIONS_FINANCE_TABLES_SQL = """
-- 17. Attendance Table
CREATE TABLE IF NOT EXISTS attendance (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    student_id INTEGER NOT NULL REFERENCES students(id) ON DELETE CASCADE,
    date TEXT NOT NULL,
    status TEXT NOT NULL DEFAULT 'Present' CHECK(status IN ('Present', 'Absent', 'On_Leave', 'Late')),
    marked_by INTEGER NULL REFERENCES users(id) ON DELETE SET NULL,
    remarks TEXT DEFAULT '',
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    UNIQUE(student_id, date)
);

-- 18. Leave Requests Table
CREATE TABLE IF NOT EXISTS leave_requests (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    student_id INTEGER NOT NULL REFERENCES students(id) ON DELETE CASCADE,
    start_date TEXT NOT NULL,
    end_date TEXT NOT NULL,
    reason TEXT NOT NULL,
    destination TEXT NOT NULL,
    emergency_contact TEXT NOT NULL,
    status TEXT NOT NULL DEFAULT 'Pending' CHECK(status IN ('Pending', 'Approved', 'Rejected', 'Cancelled')),
    approved_by INTEGER NULL REFERENCES users(id) ON DELETE SET NULL,
    reviewed_at TIMESTAMP NULL,
    remarks TEXT DEFAULT '',
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    CHECK(end_date >= start_date)
);

-- 19. Visitors Table
CREATE TABLE IF NOT EXISTS visitors (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    name TEXT NOT NULL,
    phone TEXT NOT NULL,
    id_proof_type TEXT NOT NULL CHECK(id_proof_type IN ('Aadhaar', 'Passport', 'Driving_License', 'Voter_ID', 'Other')),
    id_proof_number TEXT NOT NULL,
    address TEXT DEFAULT '',
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

-- 20. Visitor Logs Table
CREATE TABLE IF NOT EXISTS visitor_logs (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    visitor_id INTEGER NOT NULL REFERENCES visitors(id) ON DELETE CASCADE,
    student_id INTEGER NOT NULL REFERENCES students(id) ON DELETE CASCADE,
    check_in_time TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    check_out_time TIMESTAMP NULL,
    purpose TEXT NOT NULL,
    approved_by INTEGER NULL REFERENCES users(id) ON DELETE SET NULL,
    remarks TEXT DEFAULT ''
);

-- 21. Complaints Table (Q05 Comprehensive Workflow)
CREATE TABLE IF NOT EXISTS complaints (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    complaint_id TEXT NOT NULL UNIQUE,
    student_id INTEGER NOT NULL REFERENCES students(id) ON DELETE CASCADE,
    room_id INTEGER NULL REFERENCES rooms(id) ON DELETE SET NULL,
    bed_id INTEGER NULL REFERENCES beds(id) ON DELETE SET NULL,
    category TEXT NOT NULL CHECK(category IN ('Electrical', 'Plumbing', 'Carpentry', 'Wi-Fi and Internet', 'Cleanliness', 'Water Supply', 'Furniture', 'Security', 'Mess', 'Other', 'Internet')),
    title TEXT NOT NULL,
    description TEXT NOT NULL,
    severity TEXT NOT NULL DEFAULT 'Medium' CHECK(severity IN ('Low', 'Medium', 'High', 'Critical', 'Emergency')),
    status TEXT NOT NULL DEFAULT 'Submitted' CHECK(status IN ('Submitted', 'Pending', 'Assigned', 'In Progress', 'In_Progress', 'On Hold', 'Resolved', 'Closed', 'Rejected', 'Reopened')),
    assigned_to INTEGER NULL REFERENCES users(id) ON DELETE SET NULL,
    attachment_url TEXT NULL,
    internal_remarks TEXT NULL,
    rejection_reason TEXT NULL,
    escalated INTEGER NOT NULL DEFAULT 0,
    escalated_at TIMESTAMP NULL,
    escalation_reason TEXT NULL,
    feedback_rating INTEGER NULL CHECK(feedback_rating IS NULL OR (feedback_rating >= 1 AND feedback_rating <= 5)),
    feedback_comment TEXT NULL,
    reopened_count INTEGER NOT NULL DEFAULT 0,
    affects_occupancy INTEGER NOT NULL DEFAULT 0,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    resolved_at TIMESTAMP NULL,
    closed_at TIMESTAMP NULL
);

-- 22. Complaint Updates Table (Preserves Complete Status History & Audit Trail)
CREATE TABLE IF NOT EXISTS complaint_updates (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    complaint_id INTEGER NOT NULL REFERENCES complaints(id) ON DELETE CASCADE,
    updated_by INTEGER NULL REFERENCES users(id) ON DELETE SET NULL,
    previous_status TEXT NOT NULL,
    new_status TEXT NOT NULL,
    comment TEXT NOT NULL,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

-- 23. Maintenance Tasks Table (Q05 Work Order System)
CREATE TABLE IF NOT EXISTS maintenance_tasks (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    task_code TEXT NOT NULL UNIQUE,
    complaint_id INTEGER NULL REFERENCES complaints(id) ON DELETE SET NULL,
    room_id INTEGER NULL REFERENCES rooms(id) ON DELETE SET NULL,
    building_id INTEGER NULL REFERENCES buildings(id) ON DELETE SET NULL,
    bed_id INTEGER NULL REFERENCES beds(id) ON DELETE SET NULL,
    category TEXT NOT NULL,
    title TEXT NOT NULL,
    description TEXT NOT NULL,
    priority TEXT NOT NULL DEFAULT 'Medium' CHECK(priority IN ('Low', 'Medium', 'High', 'Critical', 'Urgent')),
    status TEXT NOT NULL DEFAULT 'Assigned' CHECK(status IN ('Open', 'Assigned', 'Accepted', 'In Progress', 'In_Progress', 'On Hold', 'Completed', 'Verified', 'Cancelled')),
    assigned_worker TEXT DEFAULT '',
    assigned_to INTEGER NULL REFERENCES users(id) ON DELETE SET NULL,
    resolution_notes TEXT DEFAULT '',
    completion_photo_url TEXT NULL,
    hold_reason TEXT NULL,
    deadline TEXT NULL,
    estimated_cost REAL NOT NULL DEFAULT 0.0 CHECK(estimated_cost >= 0),
    actual_cost REAL NOT NULL DEFAULT 0.0 CHECK(actual_cost >= 0),
    scheduled_date TEXT DEFAULT '',
    verified_by INTEGER NULL REFERENCES users(id) ON DELETE SET NULL,
    verified_at TIMESTAMP NULL,
    completed_at TIMESTAMP NULL,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

-- 24. Maintenance History Table
CREATE TABLE IF NOT EXISTS maintenance_history (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    task_id INTEGER NOT NULL REFERENCES maintenance_tasks(id) ON DELETE CASCADE,
    updated_by INTEGER NULL REFERENCES users(id) ON DELETE SET NULL,
    status TEXT NOT NULL,
    notes TEXT DEFAULT '',
    logged_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

-- 25. Fee Structures Table
CREATE TABLE IF NOT EXISTS fee_structures (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    name TEXT NOT NULL,
    room_type TEXT NOT NULL CHECK(room_type IN ('Single', 'Double', 'Triple', 'Dormitory', 'All')),
    academic_year TEXT NOT NULL,
    semester TEXT NOT NULL,
    amount REAL NOT NULL CHECK(amount >= 0),
    payment_frequency TEXT NOT NULL DEFAULT 'Semester' CHECK(payment_frequency IN ('Monthly', 'Semester', 'Annual', 'One_Time')),
    description TEXT DEFAULT '',
    is_active INTEGER NOT NULL DEFAULT 1 CHECK(is_active IN (0, 1)),
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

-- 26. Invoices Table
CREATE TABLE IF NOT EXISTS invoices (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    invoice_number TEXT NOT NULL UNIQUE,
    student_id INTEGER NOT NULL REFERENCES students(id) ON DELETE RESTRICT,
    fee_structure_id INTEGER NULL REFERENCES fee_structures(id) ON DELETE SET NULL,
    issue_date TEXT NOT NULL,
    due_date TEXT NOT NULL,
    total_amount REAL NOT NULL CHECK(total_amount >= 0),
    paid_amount REAL NOT NULL DEFAULT 0.0 CHECK(paid_amount >= 0 AND paid_amount <= total_amount),
    status TEXT NOT NULL DEFAULT 'Unpaid' CHECK(status IN ('Unpaid', 'Partially_Paid', 'Paid', 'Cancelled', 'Overdue')),
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    CHECK(due_date >= issue_date)
);

-- 27. Invoice Items Table
CREATE TABLE IF NOT EXISTS invoice_items (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    invoice_id INTEGER NOT NULL REFERENCES invoices(id) ON DELETE CASCADE,
    title TEXT NOT NULL,
    amount REAL NOT NULL CHECK(amount >= 0),
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

-- 28. Payments Table
CREATE TABLE IF NOT EXISTS payments (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    payment_reference TEXT NOT NULL UNIQUE,
    invoice_id INTEGER NOT NULL REFERENCES invoices(id) ON DELETE RESTRICT,
    student_id INTEGER NOT NULL REFERENCES students(id) ON DELETE RESTRICT,
    amount REAL NOT NULL CHECK(amount > 0),
    payment_method TEXT NOT NULL CHECK(payment_method IN ('UPI', 'Credit_Card', 'Debit_Card', 'Net_Banking', 'Cash', 'Demand_Draft')),
    payment_date TEXT NOT NULL,
    transaction_id TEXT DEFAULT '',
    status TEXT NOT NULL DEFAULT 'Completed' CHECK(status IN ('Completed', 'Pending', 'Failed', 'Refunded')),
    notes TEXT DEFAULT '',
    recorded_by INTEGER NULL REFERENCES users(id) ON DELETE SET NULL,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

-- 29. Refunds Table
CREATE TABLE IF NOT EXISTS refunds (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    refund_reference TEXT NOT NULL UNIQUE,
    payment_id INTEGER NOT NULL REFERENCES payments(id) ON DELETE RESTRICT,
    amount REAL NOT NULL CHECK(amount > 0),
    reason TEXT NOT NULL,
    status TEXT NOT NULL DEFAULT 'Processed' CHECK(status IN ('Initiated', 'Processed', 'Rejected')),
    approved_by INTEGER NULL REFERENCES users(id) ON DELETE SET NULL,
    processed_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

-- 30. Mess Menus Table
CREATE TABLE IF NOT EXISTS mess_menus (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    day_of_week TEXT NOT NULL CHECK(day_of_week IN ('Monday', 'Tuesday', 'Wednesday', 'Thursday', 'Friday', 'Saturday', 'Sunday')),
    meal_type TEXT NOT NULL CHECK(meal_type IN ('Breakfast', 'Lunch', 'Snacks', 'Dinner')),
    items_description TEXT NOT NULL,
    is_special INTEGER NOT NULL DEFAULT 0 CHECK(is_special IN (0, 1)),
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    UNIQUE(day_of_week, meal_type)
);

-- 31. Mess Subscriptions Table
CREATE TABLE IF NOT EXISTS mess_subscriptions (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    student_id INTEGER NOT NULL REFERENCES students(id) ON DELETE CASCADE,
    plan_type TEXT NOT NULL CHECK(plan_type IN ('Standard_Veg', 'Special_Veg', 'Non_Veg', 'Custom')),
    start_date TEXT NOT NULL,
    end_date TEXT NULL,
    monthly_fee REAL NOT NULL CHECK(monthly_fee >= 0),
    status TEXT NOT NULL DEFAULT 'Active' CHECK(status IN ('Active', 'Paused', 'Cancelled')),
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

-- 32. Meal Attendance Table
CREATE TABLE IF NOT EXISTS meal_attendance (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    student_id INTEGER NOT NULL REFERENCES students(id) ON DELETE CASCADE,
    date TEXT NOT NULL,
    meal_type TEXT NOT NULL CHECK(meal_type IN ('Breakfast', 'Lunch', 'Snacks', 'Dinner')),
    marked_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    UNIQUE(student_id, date, meal_type)
);

-- 33. Inventory Categories Table
CREATE TABLE IF NOT EXISTS inventory_categories (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    name TEXT NOT NULL UNIQUE,
    description TEXT DEFAULT '',
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

-- 34. Inventory Items Table
CREATE TABLE IF NOT EXISTS inventory_items (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    category_id INTEGER NULL REFERENCES inventory_categories(id) ON DELETE SET NULL,
    item_code TEXT NOT NULL UNIQUE,
    name TEXT NOT NULL,
    description TEXT DEFAULT '',
    unit TEXT NOT NULL DEFAULT 'pieces',
    quantity_in_stock INTEGER NOT NULL DEFAULT 0 CHECK(quantity_in_stock >= 0),
    min_reorder_level INTEGER NOT NULL DEFAULT 5 CHECK(min_reorder_level >= 0),
    unit_price REAL NOT NULL DEFAULT 0.0 CHECK(unit_price >= 0),
    status TEXT NOT NULL DEFAULT 'Available' CHECK(status IN ('Available', 'Low_Stock', 'Out_of_Stock', 'Discontinued')),
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

-- 35. Inventory Transactions Table
CREATE TABLE IF NOT EXISTS inventory_transactions (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    item_id INTEGER NOT NULL REFERENCES inventory_items(id) ON DELETE RESTRICT,
    transaction_type TEXT NOT NULL CHECK(transaction_type IN ('Purchase', 'Issue', 'Return', 'Disposal', 'Adjustment')),
    quantity INTEGER NOT NULL CHECK(quantity != 0),
    unit_price REAL NOT NULL DEFAULT 0.0 CHECK(unit_price >= 0),
    related_maintenance_task_id INTEGER NULL REFERENCES maintenance_tasks(id) ON DELETE SET NULL,
    performed_by INTEGER NULL REFERENCES users(id) ON DELETE SET NULL,
    notes TEXT DEFAULT '',
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);
"""
