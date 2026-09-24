"""Database Schema Definitions: Student Management & Hostel Inventory.

Course: BBAT104 - Fundamentals of Total Quality Management (TQM)
Quality Goal: Q05 - Reduce Response Time
"""

HOSTEL_STUDENT_TABLES_SQL = """
-- 6. Students Table
CREATE TABLE IF NOT EXISTS students (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    student_id TEXT NOT NULL UNIQUE,
    user_id INTEGER NULL REFERENCES users(id) ON DELETE SET NULL,
    first_name TEXT NOT NULL,
    last_name TEXT NOT NULL,
    email TEXT NOT NULL UNIQUE,
    phone TEXT NOT NULL,
    gender TEXT NOT NULL CHECK(gender IN ('Male', 'Female', 'Other')),
    date_of_birth TEXT DEFAULT '',
    blood_group TEXT DEFAULT '',
    branch TEXT NOT NULL,
    academic_year TEXT NOT NULL,
    semester TEXT DEFAULT '',
    address TEXT DEFAULT '',
    admission_date TEXT NOT NULL,
    status TEXT NOT NULL DEFAULT 'Active' CHECK(status IN ('Active', 'Graduated', 'Suspended', 'Withdrawn')),
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

-- 7. Guardians Table
CREATE TABLE IF NOT EXISTS guardians (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    name TEXT NOT NULL,
    relationship TEXT NOT NULL,
    phone TEXT NOT NULL,
    email TEXT DEFAULT '',
    occupation TEXT DEFAULT '',
    address TEXT DEFAULT '',
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

-- 8. Student Guardians Mapping
CREATE TABLE IF NOT EXISTS student_guardians (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    student_id INTEGER NOT NULL REFERENCES students(id) ON DELETE CASCADE,
    guardian_id INTEGER NOT NULL REFERENCES guardians(id) ON DELETE CASCADE,
    is_primary INTEGER NOT NULL DEFAULT 1 CHECK(is_primary IN (0, 1)),
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    UNIQUE(student_id, guardian_id)
);

-- 9. Student Documents Table
CREATE TABLE IF NOT EXISTS student_documents (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    student_id INTEGER NOT NULL REFERENCES students(id) ON DELETE CASCADE,
    document_type TEXT NOT NULL CHECK(document_type IN ('ID_Proof', 'Admission_Letter', 'Medical_Certificate', 'Photo', 'Other')),
    title TEXT NOT NULL,
    file_path TEXT NOT NULL,
    verification_status TEXT NOT NULL DEFAULT 'Pending' CHECK(verification_status IN ('Pending', 'Verified', 'Rejected')),
    uploaded_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

-- 10. Admission Applications Table
CREATE TABLE IF NOT EXISTS admission_applications (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    application_number TEXT NOT NULL UNIQUE,
    applicant_name TEXT NOT NULL,
    email TEXT NOT NULL,
    phone TEXT NOT NULL,
    gender TEXT NOT NULL CHECK(gender IN ('Male', 'Female', 'Other')),
    branch TEXT NOT NULL,
    academic_year TEXT NOT NULL,
    preferred_room_type TEXT NOT NULL DEFAULT 'Double' CHECK(preferred_room_type IN ('Single', 'Double', 'Triple', 'Dormitory')),
    application_status TEXT NOT NULL DEFAULT 'Submitted' CHECK(application_status IN ('Submitted', 'Under_Review', 'Approved', 'Rejected', 'Waitlisted')),
    applied_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    reviewed_by INTEGER NULL REFERENCES users(id) ON DELETE SET NULL,
    reviewed_at TIMESTAMP NULL,
    remarks TEXT DEFAULT ''
);

-- 11. Hostels Table
CREATE TABLE IF NOT EXISTS hostels (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    name TEXT NOT NULL UNIQUE,
    code TEXT NOT NULL UNIQUE,
    hostel_type TEXT NOT NULL CHECK(hostel_type IN ('Boys', 'Girls', 'Co-Ed')),
    address TEXT DEFAULT '',
    warden_id INTEGER NULL REFERENCES users(id) ON DELETE SET NULL,
    contact_phone TEXT DEFAULT '',
    contact_email TEXT DEFAULT '',
    is_active INTEGER NOT NULL DEFAULT 1 CHECK(is_active IN (0, 1)),
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

-- 12. Buildings Table
CREATE TABLE IF NOT EXISTS buildings (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    hostel_id INTEGER NOT NULL REFERENCES hostels(id) ON DELETE CASCADE,
    name TEXT NOT NULL,
    code TEXT NOT NULL,
    total_floors INTEGER NOT NULL CHECK(total_floors >= 1),
    is_active INTEGER NOT NULL DEFAULT 1 CHECK(is_active IN (0, 1)),
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    UNIQUE(hostel_id, name)
);

-- 13. Floors Table
CREATE TABLE IF NOT EXISTS floors (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    building_id INTEGER NOT NULL REFERENCES buildings(id) ON DELETE CASCADE,
    floor_number INTEGER NOT NULL CHECK(floor_number >= 0),
    floor_name TEXT NOT NULL,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    UNIQUE(building_id, floor_number)
);

-- 14. Rooms Table
CREATE TABLE IF NOT EXISTS rooms (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    floor_id INTEGER NOT NULL REFERENCES floors(id) ON DELETE CASCADE,
    room_number TEXT NOT NULL,
    room_type TEXT NOT NULL CHECK(room_type IN ('Single', 'Double', 'Triple', 'Dormitory')),
    capacity INTEGER NOT NULL CHECK(capacity BETWEEN 1 AND 10),
    base_fee REAL NOT NULL CHECK(base_fee >= 0),
    status TEXT NOT NULL DEFAULT 'Available' CHECK(status IN ('Available', 'Partially_Occupied', 'Full', 'Maintenance')),
    is_active INTEGER NOT NULL DEFAULT 1 CHECK(is_active IN (0, 1)),
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    UNIQUE(floor_id, room_number)
);

-- 15. Beds Table
CREATE TABLE IF NOT EXISTS beds (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    room_id INTEGER NOT NULL REFERENCES rooms(id) ON DELETE CASCADE,
    bed_number TEXT NOT NULL,
    status TEXT NOT NULL DEFAULT 'Available' CHECK(status IN ('Available', 'Occupied', 'Maintenance', 'Reserved')),
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    UNIQUE(room_id, bed_number)
);

-- 16. Room Allocations Table
CREATE TABLE IF NOT EXISTS room_allocations (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    student_id INTEGER NOT NULL REFERENCES students(id) ON DELETE RESTRICT,
    bed_id INTEGER NOT NULL REFERENCES beds(id) ON DELETE RESTRICT,
    room_id INTEGER NOT NULL REFERENCES rooms(id) ON DELETE RESTRICT,
    start_date TEXT NOT NULL,
    end_date TEXT NULL,
    fee_status TEXT NOT NULL DEFAULT 'Pending' CHECK(fee_status IN ('Paid', 'Pending', 'Overdue', 'Waived')),
    allocation_status TEXT NOT NULL DEFAULT 'Active' CHECK(allocation_status IN ('Active', 'Vacated', 'Transferred', 'Cancelled')),
    remarks TEXT DEFAULT '',
    allocated_by INTEGER NULL REFERENCES users(id) ON DELETE SET NULL,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    CHECK(end_date IS NULL OR end_date >= start_date)
);
"""
