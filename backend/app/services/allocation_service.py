"""Student Room and Bed Allocation Business Logic Service with Poka-Yoke System.

Course: BBAT104 - Fundamentals of Total Quality Management (TQM)
Quality Goal: Q05 - Reduce Response Time (<10ms)
Poka-Yoke: Defect-Proof Relational Integrity & Concurrency Protection
"""

import hashlib
import sqlite3
from datetime import date, datetime
from typing import Any, Dict, List, Optional
from fastapi import HTTPException, status
from backend.app.models.allocation_dto import (
    AllocationCreate,
    CheckoutRequest,
    TransferRequestCreate,
    TransferReview,
)
from backend.app.utils.logger import logger


class AllocationService:
    """Enterprise-grade Room Allocation & Poka-Yoke Defect Prevention Engine."""

    @staticmethod
    def create_allocation(
        conn: sqlite3.Connection,
        data: AllocationCreate,
        allocated_by_user_id: Optional[int] = None
    ) -> Dict[str, Any]:
        """Allocate a student to a room bed with 10-layer Poka-Yoke validation."""
        cursor = conn.cursor()

        # Poka-Yoke Check 1: Student existence and eligibility
        student = cursor.execute("""
            SELECT id, student_id, first_name, last_name, gender, status, branch, academic_year
            FROM students
            WHERE id = ?;
        """, (data.student_id,)).fetchone()

        if not student:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=f"Student ID {data.student_id} not found.")

        if student["status"] != "Active":
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=f"Poka-Yoke Violation: Ineligible student. Student '{student['first_name']} {student['last_name']}' is '{student['status']}' (Only 'Active' students can be allocated)."
            )

        # Poka-Yoke Check 7: Prevent duplicate active allocations for the same student
        existing_alloc = cursor.execute("""
            SELECT ra.id, ra.bed_id, r.room_number, h.name AS hostel_name
            FROM room_allocations ra
            JOIN rooms r ON ra.room_id = r.id
            JOIN floors f ON r.floor_id = f.id
            JOIN buildings b ON f.building_id = b.id
            JOIN hostels h ON b.hostel_id = h.id
            WHERE ra.student_id = ? AND ra.allocation_status = 'Active';
        """, (data.student_id,)).fetchone()

        if existing_alloc:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=(
                    f"Poka-Yoke Violation: Student already possesses an Active allocation "
                    f"(Allocation ID: {existing_alloc['id']} in Room {existing_alloc['room_number']}, {existing_alloc['hostel_name']}). "
                    f"Duplicate active student allocations are strictly prohibited."
                )
            )

        # Retrieve Bed, Room, Floor, Building, and Hostel hierarchy
        bed_info = cursor.execute("""
            SELECT 
                bd.id AS bed_id, bd.bed_number, bd.status AS bed_status,
                r.id AS room_id, r.room_number, r.room_type, r.capacity, r.base_fee, 
                r.status AS room_status, r.is_active AS room_active,
                f.id AS floor_id, f.floor_number, f.floor_name,
                b.id AS building_id, b.name AS building_name, b.is_active AS building_active,
                h.id AS hostel_id, h.name AS hostel_name, h.code AS hostel_code, 
                h.hostel_type, h.is_active AS hostel_active
            FROM beds bd
            JOIN rooms r ON bd.room_id = r.id
            JOIN floors f ON r.floor_id = f.id
            JOIN buildings b ON f.building_id = b.id
            JOIN hostels h ON b.hostel_id = h.id
            WHERE bd.id = ?;
        """, (data.bed_id,)).fetchone()

        if not bed_info:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=f"Bed ID {data.bed_id} not found.")

        # Poka-Yoke Check 5: Allocating students to inactive hostels or buildings
        if not bed_info["hostel_active"] or not bed_info["building_active"] or not bed_info["room_active"]:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Poka-Yoke Violation: Cannot allocate student to an inactive hostel, building, or room."
            )

        # Poka-Yoke Check 6: Allocating students to restricted hostels (Gender mismatch)
        h_type = bed_info["hostel_type"]
        s_gender = student["gender"]
        if h_type == "Boys" and s_gender != "Male":
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=f"Poka-Yoke Violation: Gender restriction mismatch. Student gender is '{s_gender}', but '{bed_info['hostel_name']}' is restricted to 'Boys'."
            )
        elif h_type == "Girls" and s_gender != "Female":
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=f"Poka-Yoke Violation: Gender restriction mismatch. Student gender is '{s_gender}', but '{bed_info['hostel_name']}' is restricted to 'Girls'."
            )

        # Poka-Yoke Check 4: Allocating students to rooms under maintenance
        if bed_info["room_status"] == "Maintenance":
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=f"Poka-Yoke Violation: Room {bed_info['room_number']} is currently under Maintenance."
            )

        # Poka-Yoke Check 3: Allocating students to inactive or maintenance beds
        if bed_info["bed_status"] == "Maintenance":
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=f"Poka-Yoke Violation: Bed {bed_info['bed_number']} is under Maintenance."
            )

        if bed_info["bed_status"] != "Available":
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=f"Poka-Yoke Violation: Bed {bed_info['bed_number']} is not available (Current status: '{bed_info['bed_status']}')."
            )

        # Poka-Yoke Check 1: Allocating one bed to multiple active students (Concurrency check)
        bed_alloc = cursor.execute("""
            SELECT id FROM room_allocations WHERE bed_id = ? AND allocation_status = 'Active';
        """, (data.bed_id,)).fetchone()
        if bed_alloc:
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail=f"Poka-Yoke Violation: Bed {bed_info['bed_number']} already has an active allocation (Allocation ID: {bed_alloc['id']})."
            )

        # Poka-Yoke Check 2: Allocating students to full rooms
        current_occ = cursor.execute("""
            SELECT COUNT(*) FROM room_allocations WHERE room_id = ? AND allocation_status = 'Active';
        """, (bed_info["room_id"],)).fetchone()[0]

        if current_occ >= bed_info["capacity"]:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=f"Poka-Yoke Violation: Room {bed_info['room_number']} has reached maximum capacity ({current_occ}/{bed_info['capacity']})."
            )

        # Date validations
        start_dt = data.start_date.strip()
        end_dt = data.end_date.strip() if data.end_date else None
        if end_dt and end_dt < start_dt:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Poka-Yoke Violation: Expected checkout date cannot be earlier than allocation start date."
            )

        # ATOMIC EXECUTION (BEGIN IMMEDIATE in SQLite)
        try:
            cursor.execute("BEGIN IMMEDIATE;")

            # 1. Insert allocation record
            cursor.execute("""
                INSERT INTO room_allocations (
                    student_id, bed_id, room_id, start_date, end_date,
                    fee_status, allocation_status, approval_status, remarks, allocated_by,
                    checkin_date
                )
                VALUES (?, ?, ?, ?, ?, ?, 'Active', 'Approved', ?, ?, ?);
            """, (
                data.student_id,
                data.bed_id,
                bed_info["room_id"],
                start_dt,
                end_dt,
                data.fee_status or "Pending",
                data.remarks or "",
                allocated_by_user_id,
                start_dt # Automatically record initial check-in date on creation
            ))
            allocation_id = cursor.lastrowid

            # 2. Update Bed status to Occupied
            cursor.execute("UPDATE beds SET status = 'Occupied', updated_at = CURRENT_TIMESTAMP WHERE id = ?;", (data.bed_id,))

            # 3. Update Room status based on new capacity
            new_occ = current_occ + 1
            new_status = "Full" if new_occ >= bed_info["capacity"] else "Partially_Occupied"
            cursor.execute("UPDATE rooms SET status = ?, updated_at = CURRENT_TIMESTAMP WHERE id = ?;", (new_status, bed_info["room_id"]))

            # 4. Audit Log
            cursor.execute("""
                INSERT INTO audit_logs (user_id, username, action, entity_name, entity_id, details)
                VALUES (?, 'staff', 'ALLOCATE_ROOM', 'room_allocations', ?, ?);
            """, (
                allocated_by_user_id or 1,
                str(allocation_id),
                f"Student {student['student_id']} allocated to {bed_info['hostel_code']} Room {bed_info['room_number']} Bed {bed_info['bed_number']}"
            ))

            conn.commit()
            logger.info(f"Poka-Yoke Allocation Created: Student {student['student_id']} -> Bed {bed_info['bed_number']} (Allocation #{allocation_id})")

        except sqlite3.IntegrityError as err:
            conn.rollback()
            logger.error(f"Integrity constraint violation during allocation: {err}")
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail=f"Poka-Yoke Constraint Violation: Database prevented duplicate or conflicting allocation ({str(err)})."
            )
        except Exception as e:
            conn.rollback()
            raise e

        return AllocationService.get_allocation_by_id(conn, allocation_id)

    @staticmethod
    def get_allocation_by_id(conn: sqlite3.Connection, allocation_id: int) -> Dict[str, Any]:
        """Fetch complete details of an allocation including confirmation metadata."""
        cursor = conn.cursor()
        row = cursor.execute("""
            SELECT 
                ra.id, ra.student_id, ra.bed_id, ra.room_id, ra.start_date, ra.end_date,
                ra.checkin_date, ra.checkout_date, ra.checkout_reason,
                ra.fee_status, ra.allocation_status, ra.approval_status, ra.remarks,
                ra.allocated_by, ra.created_at,
                s.student_id AS student_enrollment, s.first_name || ' ' || s.last_name AS student_name,
                s.gender AS student_gender, s.branch AS student_branch, s.academic_year AS student_academic_year,
                bd.bed_number,
                r.room_number, r.room_type, r.capacity AS room_capacity, r.base_fee AS room_base_fee,
                f.id AS floor_id, f.floor_number, f.floor_name,
                b.id AS building_id, b.name AS building_name,
                h.id AS hostel_id, h.name AS hostel_name, h.code AS hostel_code
            FROM room_allocations ra
            JOIN students s ON ra.student_id = s.id
            JOIN beds bd ON ra.bed_id = bd.id
            JOIN rooms r ON ra.room_id = r.id
            JOIN floors f ON r.floor_id = f.id
            JOIN buildings b ON f.building_id = b.id
            JOIN hostels h ON b.hostel_id = h.id
            WHERE ra.id = ?;
        """, (allocation_id,)).fetchone()

        if not row:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Room allocation not found.")

        result = dict(row)

        # Generate cryptographic verification hash for confirmation slip
        hash_payload = f"ALLOC-{result['id']}-{result['student_enrollment']}-{result['bed_number']}-{result['created_at']}"
        result["confirmation_number"] = f"TQM-ALC-{result['id']:06d}"
        result["verification_hash"] = hashlib.sha256(hash_payload.encode()).hexdigest()[:16].upper()

        return result

    @staticmethod
    def get_allocations(
        conn: sqlite3.Connection,
        hostel_id: Optional[int] = None,
        building_id: Optional[int] = None,
        floor_id: Optional[int] = None,
        room_type: Optional[str] = None,
        allocation_status: Optional[str] = None,
        student_id: Optional[int] = None,
        search: Optional[str] = None,
        limit: int = 100,
        offset: int = 0
    ) -> List[Dict[str, Any]]:
        """List allocations with flexible filtering and Q05 response time SLA."""
        query = """
            SELECT 
                ra.id, ra.student_id, ra.bed_id, ra.room_id, ra.start_date, ra.end_date,
                ra.checkin_date, ra.checkout_date, ra.checkout_reason,
                ra.fee_status, ra.allocation_status, ra.approval_status, ra.remarks,
                ra.allocated_by, ra.created_at,
                s.student_id AS student_enrollment, s.first_name || ' ' || s.last_name AS student_name,
                s.gender AS student_gender, s.branch AS student_branch, s.academic_year AS student_academic_year,
                bd.bed_number,
                r.room_number, r.room_type, r.capacity AS room_capacity, r.base_fee AS room_base_fee,
                f.id AS floor_id, f.floor_number, f.floor_name,
                b.id AS building_id, b.name AS building_name,
                h.id AS hostel_id, h.name AS hostel_name, h.code AS hostel_code
            FROM room_allocations ra
            JOIN students s ON ra.student_id = s.id
            JOIN beds bd ON ra.bed_id = bd.id
            JOIN rooms r ON ra.room_id = r.id
            JOIN floors f ON r.floor_id = f.id
            JOIN buildings b ON f.building_id = b.id
            JOIN hostels h ON b.hostel_id = h.id
            WHERE 1=1
        """
        params: List[Any] = []

        if hostel_id:
            query += " AND h.id = ?"
            params.append(hostel_id)
        if building_id:
            query += " AND b.id = ?"
            params.append(building_id)
        if floor_id:
            query += " AND f.id = ?"
            params.append(floor_id)
        if room_type:
            query += " AND r.room_type = ?"
            params.append(room_type)
        if allocation_status:
            query += " AND ra.allocation_status = ?"
            params.append(allocation_status)
        if student_id:
            query += " AND ra.student_id = ?"
            params.append(student_id)
        if search:
            query += """ AND (
                s.first_name LIKE ? OR s.last_name LIKE ? OR s.student_id LIKE ? 
                OR r.room_number LIKE ? OR bd.bed_number LIKE ? OR h.name LIKE ?
            )"""
            term = f"%{search.strip()}%"
            params.extend([term, term, term, term, term, term])

        query += " ORDER BY ra.id DESC LIMIT ? OFFSET ?;"
        params.extend([limit, offset])

        cursor = conn.cursor()
        rows = cursor.execute(query, params).fetchall()
        return [dict(r) for r in rows]

    @staticmethod
    def get_available_beds(
        conn: sqlite3.Connection,
        hostel_id: Optional[int] = None,
        building_id: Optional[int] = None,
        floor_id: Optional[int] = None,
        room_type: Optional[str] = None,
        gender_compatible: Optional[str] = None
    ) -> List[Dict[str, Any]]:
        """Retrieve all currently assignable beds across the institution."""
        query = """
            SELECT 
                bd.id AS bed_id, bd.bed_number,
                r.id AS room_id, r.room_number, r.room_type, r.capacity, r.base_fee,
                (SELECT COUNT(*) FROM room_allocations ra WHERE ra.room_id = r.id AND ra.allocation_status = 'Active') AS occupied_count,
                (r.capacity - (SELECT COUNT(*) FROM room_allocations ra WHERE ra.room_id = r.id AND ra.allocation_status = 'Active')) AS available_in_room,
                f.id AS floor_id, f.floor_number, f.floor_name,
                b.id AS building_id, b.name AS building_name,
                h.id AS hostel_id, h.name AS hostel_name, h.code AS hostel_code, h.hostel_type
            FROM beds bd
            JOIN rooms r ON bd.room_id = r.id
            JOIN floors f ON r.floor_id = f.id
            JOIN buildings b ON f.building_id = b.id
            JOIN hostels h ON b.hostel_id = h.id
            WHERE bd.status = 'Available'
              AND r.status != 'Maintenance'
              AND r.is_active = 1
              AND b.is_active = 1
              AND h.is_active = 1
              AND NOT EXISTS (
                  SELECT 1 FROM room_allocations ra 
                  WHERE ra.bed_id = bd.id AND ra.allocation_status = 'Active'
              )
        """
        params: List[Any] = []

        if hostel_id:
            query += " AND h.id = ?"
            params.append(hostel_id)
        if building_id:
            query += " AND b.id = ?"
            params.append(building_id)
        if floor_id:
            query += " AND f.id = ?"
            params.append(floor_id)
        if room_type:
            query += " AND r.room_type = ?"
            params.append(room_type)
        if gender_compatible:
            if gender_compatible.lower() == "male":
                query += " AND h.hostel_type IN ('Boys', 'Co-Ed')"
            elif gender_compatible.lower() == "female":
                query += " AND h.hostel_type IN ('Girls', 'Co-Ed')"

        query += " ORDER BY h.name, b.name, f.floor_number, r.room_number, bd.bed_number;"

        cursor = conn.cursor()
        rows = cursor.execute(query, params).fetchall()
        return [dict(r) for r in rows]

    @staticmethod
    def get_room_occupants(conn: sqlite3.Connection, room_id: int) -> List[Dict[str, Any]]:
        """List active student occupants in a specified room."""
        cursor = conn.cursor()
        rows = cursor.execute("""
            SELECT 
                ra.id AS allocation_id, ra.student_id,
                s.first_name || ' ' || s.last_name AS student_name,
                s.student_id AS student_enrollment, s.gender, s.branch, s.academic_year,
                bd.id AS bed_id, bd.bed_number,
                ra.start_date, ra.fee_status, ra.allocation_status
            FROM room_allocations ra
            JOIN students s ON ra.student_id = s.id
            JOIN beds bd ON ra.bed_id = bd.id
            WHERE ra.room_id = ? AND ra.allocation_status = 'Active'
            ORDER BY bd.bed_number ASC;
        """, (room_id,)).fetchall()
        return [dict(r) for r in rows]

    @staticmethod
    def get_student_allocation_history(conn: sqlite3.Connection, student_id: int) -> List[Dict[str, Any]]:
        """Retrieve full chronological allocation and transfer history for a student."""
        cursor = conn.cursor()
        rows = cursor.execute("""
            SELECT 
                ra.id, ra.start_date, ra.end_date, ra.checkin_date, ra.checkout_date,
                ra.checkout_reason, ra.fee_status, ra.allocation_status, ra.remarks,
                bd.bed_number, r.room_number, r.room_type,
                f.floor_name, b.name AS building_name, h.name AS hostel_name, h.code AS hostel_code
            FROM room_allocations ra
            JOIN beds bd ON ra.bed_id = bd.id
            JOIN rooms r ON ra.room_id = r.id
            JOIN floors f ON r.floor_id = f.id
            JOIN buildings b ON f.building_id = b.id
            JOIN hostels h ON b.hostel_id = h.id
            WHERE ra.student_id = ?
            ORDER BY ra.id DESC;
        """, (student_id,)).fetchall()
        return [dict(r) for r in rows]
